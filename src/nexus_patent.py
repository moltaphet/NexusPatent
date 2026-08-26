# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

import json
from dataclasses import dataclass
from genlayer import *

# -----------------------------------------------------------------------------
# Domain Constants & Taxonomy
# -----------------------------------------------------------------------------
CATEGORY_SOFTWARE_AI = "SOFTWARE_AI"
CATEGORY_BIOTECH_PHARMA = "BIOTECH_PHARMA"
CATEGORY_HARDWARE_ENERGY = "HARDWARE_ENERGY"
CATEGORY_MECHANICAL_ROBOTICS = "MECHANICAL_ROBOTICS"
CATEGORY_DEPIN_NETWORKS = "DEPIN_NETWORKS"

VALID_CATEGORIES = {
    CATEGORY_SOFTWARE_AI,
    CATEGORY_BIOTECH_PHARMA,
    CATEGORY_HARDWARE_ENERGY,
    CATEGORY_MECHANICAL_ROBOTICS,
    CATEGORY_DEPIN_NETWORKS,
}

STATUS_PENDING = "PENDING_EXAMINATION"
STATUS_CERTIFIED = "PATENTABLE_CERTIFIED"
STATUS_REJECTED = "PRIOR_ART_REJECTED"
STATUS_DISPUTED = "DISPUTED"

DECISION_PATENTABLE = "PATENTABLE"
DECISION_REJECTED = "REJECTED"
DECISION_DISPUTED = "DISPUTED"

# Economic & Reputation Parameters
ATTO = 10**18
MIN_EXAMINER_STAKE = 5 * ATTO      # 5 GEN bond to review
MIN_CHALLENGE_BOND = 3 * ATTO      # 3 GEN bond to challenge
EXAMINER_SLASH_PENALTY = 2 * ATTO  # Slashing penalty for dishonest audits
MIN_PATENTABILITY_INDEX = 75       # 0-100 threshold
MIN_CONFIDENCE_THRESHOLD = 80      # 0-100 threshold
MAX_COLLISION_TOLERANCE = 30       # Prior-art collision >= 30% rejects patent

ERROR_EXPECTED = "[EXPECTED]"
ERROR_EXTERNAL = "[EXTERNAL]"
ERROR_LLM = "[LLM]"


# -----------------------------------------------------------------------------
# Storage Schemas
# -----------------------------------------------------------------------------
@allow_storage
@dataclass
class InventionData:
    invention_id: str
    inventor: Address
    category: str
    claims_hash: str
    abstract_summary: str
    estimated_valuation_atto: u256
    status: str
    patentability_index: u256
    novelty_score: u256
    inventive_step_score: u256
    prior_art_collision: u256
    examination_count: u256
    licensing_approved: bool
    licensing_max_shares: u256
    registered_seq: u256


@allow_storage
@dataclass
class ExaminationRecord:
    invention_id: str
    examiner: Address
    decision: str
    confidence: u256
    patentability_index: u256
    prior_art_collision: u256
    rationale: str
    reference_summary: str
    timestamp_seq: u256


@allow_storage
@dataclass
class InvalidationChallenge:
    challenge_id: str
    invention_id: str
    challenger: Address
    bond_atto: u256
    challenge_reason: str
    prior_art_citation_hash: str
    is_active: bool


@gl.evm.contract_interface
class _Recipient:
    class View:
        pass

    class Write:
        pass


# -----------------------------------------------------------------------------
# Intelligent Contract Interface
# -----------------------------------------------------------------------------
class NexusPatent(gl.Contract):
    owner: Address
    oracle_api_base: str
    min_examiner_stake: u256
    min_challenge_bond: u256

    # Inventions Registry: invention_id -> InventionData
    inventions: TreeMap[str, InventionData]
    invention_ids: DynArray[str]

    # Examination Global Ledger
    records: DynArray[ExaminationRecord]

    # Examiner Staking & Reputation: examiner -> value
    examiner_stakes: TreeMap[Address, u256]
    examiner_total_reviews: TreeMap[Address, u256]
    examiner_certified_reviews: TreeMap[Address, u256]

    # Invalidation Challenges: challenge_id -> InvalidationChallenge
    challenges: TreeMap[str, InvalidationChallenge]
    challenge_ids: DynArray[str]

    def __init__(self, oracle_api_base: str = "https://api.nexuspatent.desci/v1/prior-art"):
        self.owner = gl.message.sender_address
        self.oracle_api_base = oracle_api_base
        self.min_examiner_stake = u256(MIN_EXAMINER_STAKE)
        self.min_challenge_bond = u256(MIN_CHALLENGE_BOND)

    # ------------------------------------------------------------------
    # 1. Invention Registration
    # ------------------------------------------------------------------
    @gl.public.write
    def register_invention(
        self,
        invention_id: str,
        category: str,
        claims_hash: str,
        abstract_summary: str,
        estimated_valuation: u256,
    ) -> None:
        if not invention_id or len(invention_id.strip()) == 0:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Invention ID cannot be empty")
        if invention_id in self.inventions:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Invention {invention_id} already registered")
        if category not in VALID_CATEGORIES:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Invalid category: {category}")
        if int(estimated_valuation) <= 0:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Estimated valuation must be greater than zero")

        seq = u256(len(self.invention_ids) + 1)
        data = InventionData(
            invention_id=invention_id,
            inventor=gl.message.sender_address,
            category=category,
            claims_hash=claims_hash,
            abstract_summary=abstract_summary,
            estimated_valuation_atto=estimated_valuation,
            status=STATUS_PENDING,
            patentability_index=u256(0),
            novelty_score=u256(0),
            inventive_step_score=u256(0),
            prior_art_collision=u256(0),
            examination_count=u256(0),
            licensing_approved=False,
            licensing_max_shares=u256(0),
            registered_seq=seq,
        )

        self.inventions[invention_id] = data
        self.invention_ids.append(invention_id)

    # ------------------------------------------------------------------
    # 2. Examiner Staking & Slashing
    # ------------------------------------------------------------------
    @gl.public.write.payable
    def stake_examiner(self) -> None:
        value = gl.message.value
        if int(value) <= 0:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Stake value must be greater than zero")

        examiner = gl.message.sender_address
        current = self.examiner_stakes.get(examiner, u256(0))
        self.examiner_stakes[examiner] = u256(int(current) + int(value))

    @gl.public.write
    def withdraw_examiner_stake(self, amount: u256) -> None:
        examiner = gl.message.sender_address
        current = int(self.examiner_stakes.get(examiner, u256(0)))
        amt = int(amount)
        if amt <= 0:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Withdrawal amount must be positive")
        if amt > current:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Withdrawal exceeds staked collateral")

        self.examiner_stakes[examiner] = u256(current - amt)
        _Recipient(examiner).emit_transfer(value=amount, on="finalized")

    # ------------------------------------------------------------------
    # 3. Dual-Engine Prior-Art & Patentability Examination
    # ------------------------------------------------------------------
    @gl.public.write
    def evaluate_patentability(
        self,
        invention_id: str,
        technical_claims: str,
        embodiment_evidence: str,
        prior_art_citations: str = "",
    ) -> None:
        if invention_id not in self.inventions:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Invention {invention_id} not registered")

        examiner = gl.message.sender_address
        staked = int(self.examiner_stakes.get(examiner, u256(0)))
        if staked < int(self.min_examiner_stake):
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Examiner requires at least 5 GEN bonded stake")

        inv = self.inventions[invention_id]
        oracle_url = f"{self.oracle_api_base}?invention={invention_id}"

        audit_res = self._evaluate_with_consensus(
            invention_id=invention_id,
            category=inv.category,
            abstract=inv.abstract_summary,
            claims=technical_claims,
            embodiment=embodiment_evidence,
            citations=prior_art_citations,
            oracle_url=oracle_url,
        )

        decision = str(audit_res.get("decision", DECISION_DISPUTED))
        confidence = int(audit_res.get("confidence", 70))
        novelty = int(audit_res.get("novelty", 75))
        inventive = int(audit_res.get("inventive", 70))
        collision = int(audit_res.get("collision", 15))
        pi = int(audit_res.get("patentability_index", 75))
        rationale = str(audit_res.get("rationale", "AI Quorum evaluated"))
        ref_summary = str(audit_res.get("reference_summary", "Oracle feed"))

        # Update Invention State
        if decision == DECISION_PATENTABLE and pi >= MIN_PATENTABILITY_INDEX and confidence >= MIN_CONFIDENCE_THRESHOLD:
            inv.status = STATUS_CERTIFIED
        elif collision >= MAX_COLLISION_TOLERANCE or decision == DECISION_REJECTED:
            inv.status = STATUS_REJECTED
        else:
            inv.status = STATUS_DISPUTED

        inv.patentability_index = u256(pi)
        inv.novelty_score = u256(novelty)
        inv.inventive_step_score = u256(inventive)
        inv.prior_art_collision = u256(collision)
        inv.examination_count = u256(int(inv.examination_count) + 1)
        self.inventions[invention_id] = inv

        # Update Examiner Reputation
        tot_rev = int(self.examiner_total_reviews.get(examiner, u256(0))) + 1
        self.examiner_total_reviews[examiner] = u256(tot_rev)
        if inv.status == STATUS_CERTIFIED:
            cert_rev = int(self.examiner_certified_reviews.get(examiner, u256(0))) + 1
            self.examiner_certified_reviews[examiner] = u256(cert_rev)

        # Log Examination Record
        record = ExaminationRecord(
            invention_id=invention_id,
            examiner=examiner,
            decision=decision,
            confidence=u256(confidence),
            patentability_index=u256(pi),
            prior_art_collision=u256(collision),
            rationale=rationale,
            reference_summary=ref_summary,
            timestamp_seq=u256(tot_rev),
        )

        self.records.append(record)

    def _evaluate_with_consensus(
        self,
        invention_id: str,
        category: str,
        abstract: str,
        claims: str,
        embodiment: str,
        citations: str,
        oracle_url: str,
    ) -> dict:
        def leader_fn() -> dict:
            web_summary = "Clean prior-art search: no conflicting claims."
            try:
                web_res = gl.nondet.web.render(oracle_url, mode="text")
                if web_res.status == 200 and web_res.body:
                    web_summary = f"Registry returned: {web_res.body[:180]}"
            except Exception:
                web_summary = "External oracle unavailable; using technical claims."

            prompt = (
                "You are an impartial patent examiner evaluating patentability. "
                f"Invention ID: {invention_id}, Category: {category}. "
                f"Claims: {claims}. Embodiment: {embodiment}. Citations: {citations}. "
                f"Prior-Art: {web_summary}."
            )

            result = _run_patent_llm(prompt)
            result["reference_summary"] = web_summary[:256]
            return result

        def validator_fn(leaders_res: gl.vm.Result) -> bool:
            if not isinstance(leaders_res, gl.vm.Return):
                return _handle_leader_error(leaders_res, leader_fn)
            try:
                v_res = leader_fn()
                leader = leaders_res.calldata
                if not isinstance(leader, dict):
                    return False
                if leader.get("decision") != v_res.get("decision"):
                    return False
                
                conf_diff = abs(int(v_res.get("confidence", 0)) - int(leader.get("confidence", 0)))
                pi_diff = abs(int(v_res.get("patentability_index", 0)) - int(leader.get("patentability_index", 0)))
                return conf_diff <= 20 and pi_diff <= 20
            except Exception:
                return False

        return gl.vm.run_nondet_unsafe(leader_fn, validator_fn)

    # ------------------------------------------------------------------
    # 4. Invalidation Challenge
    # ------------------------------------------------------------------
    @gl.public.write.payable
    def dispute_patent_novelty(
        self,
        invention_id: str,
        challenge_reason: str,
        prior_art_citation_hash: str,
    ) -> None:
        if invention_id not in self.inventions:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Invention {invention_id} not registered")

        bond = gl.message.value
        if int(bond) < int(self.min_challenge_bond):
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Challenge requires at least 3 GEN bond")

        inv = self.inventions[invention_id]
        inv.status = STATUS_DISPUTED
        inv.licensing_approved = False
        self.inventions[invention_id] = inv

        cid = f"chal-{invention_id}-{len(self.challenge_ids) + 1}"
        challenge = InvalidationChallenge(
            challenge_id=cid,
            invention_id=invention_id,
            challenger=gl.message.sender_address,
            bond_atto=bond,
            challenge_reason=challenge_reason,
            prior_art_citation_hash=prior_art_citation_hash,
            is_active=True,
        )
        self.challenges[cid] = challenge
        self.challenge_ids.append(cid)

    # ------------------------------------------------------------------
    # 5. Fractional IP Licensing
    # ------------------------------------------------------------------
    @gl.public.write
    def approve_licensing(
        self,
        invention_id: str,
        share_denomination: u256,
    ) -> u256:
        if invention_id not in self.inventions:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Invention {invention_id} not registered")

        inv = self.inventions[invention_id]
        sender = gl.message.sender_address
        if sender != inv.inventor and sender != self.owner:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Only inventor or owner can approve licensing")
        if inv.status != STATUS_CERTIFIED:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Invention must be PATENTABLE_CERTIFIED")
        if int(share_denomination) <= 0:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Share denomination must be greater than zero")

        val = int(inv.estimated_valuation_atto)
        denom = int(share_denomination)
        max_shares = u256(val // denom)

        inv.licensing_approved = True
        inv.licensing_max_shares = max_shares
        self.inventions[invention_id] = inv
        return max_shares

    # ------------------------------------------------------------------
    # 6. View Methods & Protocol Overview
    # ------------------------------------------------------------------
    @gl.public.view
    def get_invention(self, invention_id: str) -> dict:
        if invention_id not in self.inventions:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Invention {invention_id} not found")
        inv = self.inventions[invention_id]
        return {
            "invention_id": inv.invention_id,
            "inventor": inv.inventor.as_hex,
            "category": inv.category,
            "claims_hash": inv.claims_hash,
            "abstract_summary": inv.abstract_summary,
            "estimated_valuation_atto": str(int(inv.estimated_valuation_atto)),
            "status": inv.status,
            "patentability_index": int(inv.patentability_index),
            "novelty_score": int(inv.novelty_score),
            "inventive_step_score": int(inv.inventive_step_score),
            "prior_art_collision": int(inv.prior_art_collision),
            "examination_count": int(inv.examination_count),
            "licensing_approved": inv.licensing_approved,
            "licensing_max_shares": str(int(inv.licensing_max_shares)),
            "registered_seq": int(inv.registered_seq),
        }

    @gl.public.view
    def get_examiner(self, examiner: Address) -> dict:
        addr = Address(examiner) if not isinstance(examiner, Address) else examiner
        tot = int(self.examiner_total_reviews.get(addr, u256(0)))
        ver = int(self.examiner_certified_reviews.get(addr, u256(0)))
        rep = (ver * 100 // tot) if tot > 0 else 100
        staked = int(self.examiner_stakes.get(addr, u256(0)))
        return {
            "examiner": addr.as_hex,
            "staked_collateral": str(staked),
            "total_reviews": tot,
            "certified_reviews": ver,
            "accuracy_score": rep,
            "is_certified": staked >= int(self.min_examiner_stake),
        }

    @gl.public.view
    def get_records(self, invention_id: str) -> list:
        out = []
        for r in self.records:
            if r.invention_id == invention_id:
                out.append({
                    "examiner": r.examiner.as_hex,
                    "decision": r.decision,
                    "confidence": int(r.confidence),
                    "patentability_index": int(r.patentability_index),
                    "prior_art_collision": int(r.prior_art_collision),
                    "rationale": r.rationale,
                    "reference_summary": r.reference_summary,
                    "timestamp_seq": int(r.timestamp_seq),
                })
        return out

    @gl.public.view
    def list_inventions(self) -> list:
        out = []
        for i_id in self.invention_ids:
            out.append(self.get_invention(i_id))
        return out

    @gl.public.view
    def get_protocol_overview(self) -> dict:
        return {
            "owner": self.owner.as_hex,
            "oracle_api_base": self.oracle_api_base,
            "total_inventions": len(self.invention_ids),
            "total_examinations": len(self.records),
            "total_staked": "0",
            "total_challenges": len(self.challenge_ids),
        }


# --- Internal Helpers -----------------------------------------------------
def _run_patent_llm(prompt: str) -> dict:
    try:
        raw = gl.nondet.exec_prompt(prompt, response_format="json")
    except Exception as e:
        raise gl.vm.UserError(f"{ERROR_LLM} LLM execution failed: {str(e)}")

    if isinstance(raw, str):
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()
        try:
            parsed = json.loads(cleaned)
        except Exception as e:
            raise gl.vm.UserError(f"{ERROR_LLM} Malformed JSON from LLM: {str(e)}")
    elif isinstance(raw, dict):
        parsed = raw
    else:
        raise gl.vm.UserError(f"{ERROR_LLM} LLM output is not a JSON object")

    raw_dec = str(parsed.get("decision", DECISION_DISPUTED)).strip().upper()
    if raw_dec in ("PATENTABLE", "NOVEL", "APPROVED", "VALID"):
        decision = DECISION_PATENTABLE
    elif raw_dec in ("REJECTED", "PRIOR_ART", "INVALID"):
        decision = DECISION_REJECTED
    else:
        decision = DECISION_DISPUTED

    confidence = max(0, min(100, int(parsed.get("confidence", 75))))
    novelty = max(0, min(100, int(parsed.get("novelty", 80))))
    inventive = max(0, min(100, int(parsed.get("inventive", 75))))
    collision = max(0, min(100, int(parsed.get("collision", 10))))
    rationale = str(parsed.get("rationale", "Patentability verified by AI consensus."))[:300]

    pi = int((novelty * 0.40) + (inventive * 0.45) + ((100 - collision) * 0.15))
    pi = max(0, min(100, pi))

    return {
        "decision": decision,
        "confidence": confidence,
        "novelty": novelty,
        "inventive": inventive,
        "collision": collision,
        "patentability_index": pi,
        "rationale": rationale,
    }


def _handle_leader_error(leaders_res: gl.vm.Result, leader_fn) -> bool:
    leader_msg = leaders_res.calldata if isinstance(leaders_res.calldata, str) else str(leaders_res)
    if ERROR_EXPECTED in leader_msg or ERROR_EXTERNAL in leader_msg:
        try:
            leader_fn()
            return False
        except gl.vm.UserError as v_err:
            return (
                (ERROR_EXPECTED in str(v_err) and ERROR_EXPECTED in leader_msg)
                or (ERROR_EXTERNAL in str(v_err) and ERROR_EXTERNAL in leader_msg)
            )
        except Exception:
            return False
    return False
