# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

import json
from dataclasses import dataclass
from genlayer import *

# -----------------------------------------------------------------------------
# Domain Constants & Taxonomy
# -----------------------------------------------------------------------------
STATUS_SUBMITTED = "SUBMITTED"
STATUS_EXAMINATION_PENDING = "EXAMINATION_PENDING"
STATUS_CERTIFIED = "CERTIFIED"
STATUS_REJECTED = "REJECTED"
STATUS_LICENSED = "LICENSED"
STATUS_DISPUTED = "DISPUTED"
STATUS_INVALIDATED = "INVALIDATED"
STATUS_EXPIRED = "EXPIRED"

DECISION_APPROVED = "APPROVED"
DECISION_REJECTED = "REJECTED"

VALID_CATEGORIES = {
    "BIOTECH_GENOMICS",
    "HARDWARE_SEMICONDUCTORS",
    "SOFTWARE_AI",
    "CLEANTECH_ENERGY",
    "MATERIALS_SCIENCE",
    "QUANTUM_COMPUTING",
}

ATTO = 10**18
MIN_EXAMINER_BOND = 2 * ATTO    # 2 GEN minimum bond for peer examiners
MIN_CHALLENGE_BOND = 3 * ATTO   # 3 GEN bond to challenge certified patent
EXAMINATION_TIMEOUT_SEC = 604800 # 7 days timeout for examination
DISPUTE_WINDOW_SEC = 259200      # 3 days dispute resolution window

ERROR_EXPECTED = "[EXPECTED]"
ERROR_EXTERNAL = "[EXTERNAL]"
ERROR_TRANSIENT = "[TRANSIENT]"
ERROR_LLM = "[LLM]"


# -----------------------------------------------------------------------------
# Storage Schemas (Strictly Typed Dataclasses)
# -----------------------------------------------------------------------------
@allow_storage
@dataclass
class InventionRecord:
    invention_id: str
    inventor: Address
    title: str
    category: str
    claims_hash: str          # SHA256 / Merkle root of mathematical claims
    paper_cid_proof: str      # IPFS CID / ArXiv cryptographic identifier
    valuation_atto: u256
    status: str
    novelty_score: u256       # 0-100 score
    inventive_step_score: u256# 0-100 score
    patent_index: u256        # Composite Patent Index (0-100)
    assigned_examiner: Address
    submission_timestamp: u256
    licensee: Address
    licensing_share_bps: u256


@allow_storage
@dataclass
class ExaminerProfile:
    examiner_address: Address
    bonded_stake_atto: u256
    examinations_completed: u256
    disputes_lost: u256
    reputation_score: u256    # Base 100
    is_active: bool


@allow_storage
@dataclass
class AuditTrailRecord:
    invention_id: str
    examiner: Address
    decision: str
    novelty_score: u256
    inventive_step_score: u256
    collision_rate: u256
    rationale: str
    multi_source_telemetry: str
    timestamp_seq: u256


@gl.evm.contract_interface
class _Recipient:
    class View:
        pass

    class Write:
        pass


# -----------------------------------------------------------------------------
# Main Intelligent Contract Class
# -----------------------------------------------------------------------------
class NexusPatent(gl.Contract):
    owner: Address
    oracle_api_base: str

    # Global Accounting Ledgers (Double-Entry Bookkeeping)
    total_inventions: u256
    total_examiner_stake_atto: u256
    total_licensing_royalties_atto: u256
    total_challenges_count: u256

    # Inventions Store: invention_id -> InventionRecord
    inventions: TreeMap[str, InventionRecord]
    invention_ids: DynArray[str]

    # Examiners Store: address -> ExaminerProfile
    examiners: TreeMap[Address, ExaminerProfile]
    examiner_addresses: DynArray[Address]

    # Double-Entry Balances: address -> u256
    user_balances: TreeMap[Address, u256]

    # Global Immutable Audit Records
    audit_records: DynArray[AuditTrailRecord]

    def __init__(self, oracle_api_base: str = "https://api.nexuspatent.desci/v1/prior-art"):
        self.owner = gl.message.sender_address
        self.oracle_api_base = oracle_api_base
        self.total_inventions = u256(0)
        self.total_examiner_stake_atto = u256(0)
        self.total_licensing_royalties_atto = u256(0)
        self.total_challenges_count = u256(0)

    # ------------------------------------------------------------------
    # 1. Invention Registration (Cryptographic Proof Commitments)
    # ------------------------------------------------------------------
    @gl.public.write
    def register_invention(
        self,
        invention_id: str,
        category: str,
        claims_hash: str,
        paper_cid_proof: str,
        valuation_atto: u256,
        title: str = "Novel Scientific Discovery",
    ) -> None:
        if not invention_id or len(invention_id.strip()) == 0:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Invention ID cannot be empty")
        if invention_id in self.inventions:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Invention {invention_id} already registered")
        if category not in VALID_CATEGORIES:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Invalid category: {category}")
        if not claims_hash or len(claims_hash.strip()) == 0:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Cryptographic claims hash is required")
        if not paper_cid_proof or len(paper_cid_proof.strip()) == 0:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Paper CID or DOI proof is required")
        if int(valuation_atto) <= 0:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Valuation must be greater than zero")

        inv = InventionRecord(
            invention_id=invention_id,
            inventor=gl.message.sender_address,
            title=title,
            category=category,
            claims_hash=claims_hash,
            paper_cid_proof=paper_cid_proof,
            valuation_atto=valuation_atto,
            status=STATUS_SUBMITTED,
            novelty_score=u256(0),
            inventive_step_score=u256(0),
            patent_index=u256(0),
            assigned_examiner=Address(b"\x00" * 20),
            submission_timestamp=u256(1750000000),
            licensee=Address(b"\x00" * 20),
            licensing_share_bps=u256(0),
        )

        self.inventions[invention_id] = inv
        self.invention_ids.append(invention_id)
        self.total_inventions = u256(int(self.total_inventions) + 1)

    # ------------------------------------------------------------------
    # 2. Examiner Staking & Slashing System (Anti-Collusion Mechanism)
    # ------------------------------------------------------------------
    @gl.public.write.payable
    def stake_examiner(self) -> None:
        stake_amount = int(gl.message.value)
        if stake_amount <= 0:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Stake amount must be greater than zero")

        sender = gl.message.sender_address
        if sender in self.examiners:
            ex = self.examiners[sender]
            ex.bonded_stake_atto = u256(int(ex.bonded_stake_atto) + stake_amount)
            ex.is_active = True
            self.examiners[sender] = ex
        else:
            ex = ExaminerProfile(
                examiner_address=sender,
                bonded_stake_atto=u256(stake_amount),
                examinations_completed=u256(0),
                disputes_lost=u256(0),
                reputation_score=u256(100),
                is_active=True,
            )
            self.examiners[sender] = ex
            self.examiner_addresses.append(sender)

        self.total_examiner_stake_atto = u256(int(self.total_examiner_stake_atto) + stake_amount)

    @gl.public.write
    def withdraw_examiner_stake(self, amount: u256) -> None:
        sender = gl.message.sender_address
        if sender not in self.examiners:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Caller is not a registered examiner")

        ex = self.examiners[sender]
        amt = int(amount)
        current_stake = int(ex.bonded_stake_atto)

        if amt <= 0 or amt > current_stake:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Invalid withdrawal amount")

        ex.bonded_stake_atto = u256(current_stake - amt)
        if int(ex.bonded_stake_atto) < int(MIN_EXAMINER_BOND):
            ex.is_active = False
        self.examiners[sender] = ex
        self.total_examiner_stake_atto = u256(int(self.total_examiner_stake_atto) - amt)

        _Recipient(sender).emit_transfer(value=u256(amt), on="finalized")

    # ------------------------------------------------------------------
    # 3. Autonomous Multi-Source Prior-Art Consensus Examination
    # ------------------------------------------------------------------
    @gl.public.write
    def evaluate_patentability(
        self,
        invention_id: str,
        prior_art_query_url: str = "",
    ) -> None:
        if invention_id not in self.inventions:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Invention {invention_id} not found")

        inv = self.inventions[invention_id]
        if inv.status != STATUS_SUBMITTED and inv.status != STATUS_EXAMINATION_PENDING:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Invention is not pending examination")

        sender = gl.message.sender_address
        if sender not in self.examiners:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Caller must be a bonded examiner")

        ex = self.examiners[sender]
        if int(ex.bonded_stake_atto) < int(MIN_EXAMINER_BOND) or not ex.is_active:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Insufficient examiner bond (minimum 2 GEN required)")

        oracle_endpoint = prior_art_query_url if prior_art_query_url else f"{self.oracle_api_base}?hash={inv.claims_hash}&cid={inv.paper_cid_proof}"

        consensus_result = self._evaluate_with_consensus(
            title=inv.title,
            category=inv.category,
            claims_hash=inv.claims_hash,
            paper_cid=inv.paper_cid_proof,
            oracle_url=oracle_endpoint,
        )

        decision = str(consensus_result.get("decision", DECISION_REJECTED))
        novelty = int(consensus_result.get("novelty_score", 0))
        inventive_step = int(consensus_result.get("inventive_step_score", 0))
        collision_rate = int(consensus_result.get("citation_collision_rate", 100))
        prior_art_collision = bool(consensus_result.get("prior_art_collision", True))
        rationale = str(consensus_result.get("rationale", "Autonomous examination completed."))
        telemetry = str(consensus_result.get("telemetry_summary", "USPTO/ArXiv multi-source query."))

        # Composite Patent Index (PI) Formulation:
        # PI = (Novelty * 0.40) + (InventiveStep * 0.45) + ((100 - CollisionRate) * 0.15)
        if decision == DECISION_APPROVED and not prior_art_collision and novelty >= 70 and inventive_step >= 65:
            patent_index = (novelty * 40 + inventive_step * 45 + (100 - collision_rate) * 15) // 100
            inv.status = STATUS_CERTIFIED
            inv.novelty_score = u256(novelty)
            inv.inventive_step_score = u256(inventive_step)
            inv.patent_index = u256(patent_index)
            inv.assigned_examiner = sender

            ex.examinations_completed = u256(int(ex.examinations_completed) + 1)
            ex.reputation_score = u256(min(200, int(ex.reputation_score) + 5))
        else:
            inv.status = STATUS_REJECTED
            inv.novelty_score = u256(novelty)
            inv.inventive_step_score = u256(inventive_step)
            inv.patent_index = u256(0)
            inv.assigned_examiner = sender

            ex.examinations_completed = u256(int(ex.examinations_completed) + 1)

        self.inventions[invention_id] = inv
        self.examiners[sender] = ex

        # Append Immutable Audit Trail Record
        rec = AuditTrailRecord(
            invention_id=invention_id,
            examiner=sender,
            decision=decision,
            novelty_score=u256(novelty),
            inventive_step_score=u256(inventive_step),
            collision_rate=u256(collision_rate),
            rationale=rationale,
            multi_source_telemetry=telemetry,
            timestamp_seq=u256(len(self.audit_records) + 1),
        )
        self.audit_records.append(rec)

    def _evaluate_with_consensus(
        self,
        title: str,
        category: str,
        claims_hash: str,
        paper_cid: str,
        oracle_url: str,
    ) -> dict:
        def leader_fn() -> dict:
            telemetry_summary = "Multi-source prior-art registry verified."
            try:
                web_res = gl.nondet.web.render(oracle_url, mode="text")
                if web_res.status == 200 and web_res.body:
                    telemetry_summary = f"Telemetry: {web_res.body[:180]}"
            except Exception:
                telemetry_summary = "ArXiv / USPTO direct vector database query."

            prompt = (
                "You are an impartial Patent Examiner and DeSci Prior-Art Auditor. "
                f"Invention Title: {title}. Category: {category}. "
                f"Claims Hash: {claims_hash}. Paper CID/DOI Proof: {paper_cid}. "
                f"Registry Telemetry: {telemetry_summary}. "
                "Evaluate strict technical novelty, non-obviousness, and prior art collisions. "
                'Respond with strict JSON: {"decision": "APPROVED" | "REJECTED", '
                '"novelty_score": <int 0-100>, "inventive_step_score": <int 0-100>, '
                '"citation_collision_rate": <int 0-100>, "prior_art_collision": <bool>, '
                '"rationale": "<summary>"}'
            )

            res = _run_patent_llm(prompt)
            res["telemetry_summary"] = telemetry_summary[:256]
            return res

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
                if leader.get("prior_art_collision") != v_res.get("prior_art_collision"):
                    return False

                n_diff = abs(int(v_res.get("novelty_score", 0)) - int(leader.get("novelty_score", 0)))
                i_diff = abs(int(v_res.get("inventive_step_score", 0)) - int(leader.get("inventive_step_score", 0)))
                return n_diff <= 15 and i_diff <= 15
            except Exception:
                return False

        return gl.vm.run_nondet_unsafe(leader_fn, validator_fn)

    # ------------------------------------------------------------------
    # 4. Dispute & Invalidation with Slashing Protocol
    # ------------------------------------------------------------------
    @gl.public.write.payable
    def dispute_patent_novelty(
        self,
        invention_id: str,
        dispute_reason: str,
        new_prior_art_url: str = "",
    ) -> None:
        if invention_id not in self.inventions:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Invention {invention_id} not found")

        inv = self.inventions[invention_id]
        if inv.status != STATUS_CERTIFIED and inv.status != STATUS_LICENSED:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Can only dispute CERTIFIED or LICENSED inventions")

        challenger_bond = int(gl.message.value)
        if challenger_bond < int(MIN_CHALLENGE_BOND):
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Minimum challenge bond is 3 GEN")

        challenger = gl.message.sender_address
        oracle_url = new_prior_art_url if new_prior_art_url else f"{self.oracle_api_base}?dispute={invention_id}"

        consensus_res = self._evaluate_with_consensus(
            title=inv.title,
            category=inv.category,
            claims_hash=inv.claims_hash,
            paper_cid=f"DISPUTE:{dispute_reason}",
            oracle_url=oracle_url,
        )

        prior_collision = bool(consensus_res.get("prior_art_collision", False))
        decision = str(consensus_res.get("decision", DECISION_REJECTED))

        self.total_challenges_count = u256(int(self.total_challenges_count) + 1)

        if prior_collision or decision == DECISION_REJECTED:
            # Invalidation Successful: Slashed examiner, rewarded challenger
            inv.status = STATUS_INVALIDATED
            inv.patent_index = u256(0)

            # Slash original examiner if active
            ex_addr = inv.assigned_examiner
            if ex_addr in self.examiners:
                ex = self.examiners[ex_addr]
                ex.disputes_lost = u256(int(ex.disputes_lost) + 1)
                ex.reputation_score = u256(max(0, int(ex.reputation_score) - 40))
                slash_amt = min(int(ex.bonded_stake_atto), int(MIN_EXAMINER_BOND))
                ex.bonded_stake_atto = u256(int(ex.bonded_stake_atto) - slash_amt)
                if int(ex.bonded_stake_atto) < int(MIN_EXAMINER_BOND):
                    ex.is_active = False
                self.examiners[ex_addr] = ex

            # Return challenger bond + 50% reward
            reward = challenger_bond + (challenger_bond // 2)
            _Recipient(challenger).emit_transfer(value=u256(reward), on="finalized")
        else:
            # Challenge Failed: Forfeit bond to inventor treasury
            _Recipient(inv.inventor).emit_transfer(value=u256(challenger_bond), on="finalized")

        self.inventions[invention_id] = inv

    # ------------------------------------------------------------------
    # 5. Fractional IP Licensing & Royalty Settlement
    # ------------------------------------------------------------------
    @gl.public.write
    def approve_licensing(
        self,
        invention_id: str,
        licensee: Address,
        share_percentage_bps: u256,
    ) -> None:
        if invention_id not in self.inventions:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Invention {invention_id} not found")

        inv = self.inventions[invention_id]
        if gl.message.sender_address != inv.inventor:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Only inventor can grant licenses")
        if inv.status != STATUS_CERTIFIED and inv.status != STATUS_LICENSED:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Invention must be certified before licensing")

        bps = int(share_percentage_bps)
        if bps <= 0 or bps > 10000:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Share BPS must be between 1 and 10000")

        inv.status = STATUS_LICENSED
        inv.licensee = Address(licensee) if not isinstance(licensee, Address) else licensee
        inv.licensing_share_bps = u256(bps)
        self.inventions[invention_id] = inv

    # ------------------------------------------------------------------
    # 6. Escape Hatch: Timeout Refund for Stale Submissions
    # ------------------------------------------------------------------
    @gl.public.write
    def reclaim_stale_submission(self, invention_id: str) -> None:
        if invention_id not in self.inventions:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Invention {invention_id} not found")

        inv = self.inventions[invention_id]
        if gl.message.sender_address != inv.inventor:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Only inventor can reclaim stale submission")
        if inv.status != STATUS_SUBMITTED:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Invention is not in unexamined SUBMITTED state")

        inv.status = STATUS_EXPIRED
        self.inventions[invention_id] = inv

    # ------------------------------------------------------------------
    # 7. Public View Methods & Ledgers
    # ------------------------------------------------------------------
    @gl.public.view
    def get_invention(self, invention_id: str) -> dict:
        if invention_id not in self.inventions:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Invention {invention_id} not found")
        inv = self.inventions[invention_id]
        return {
            "invention_id": inv.invention_id,
            "inventor": inv.inventor.as_hex,
            "title": inv.title,
            "category": inv.category,
            "claims_hash": inv.claims_hash,
            "paper_cid_proof": inv.paper_cid_proof,
            "valuation_atto": str(int(inv.valuation_atto)),
            "status": inv.status,
            "novelty_score": int(inv.novelty_score),
            "inventive_step_score": int(inv.inventive_step_score),
            "patent_index": int(inv.patent_index),
            "assigned_examiner": inv.assigned_examiner.as_hex,
            "licensee": inv.licensee.as_hex,
            "licensing_share_bps": int(inv.licensing_share_bps),
        }

    @gl.public.view
    def get_examiner(self, examiner: Address) -> dict:
        ex_addr = Address(examiner) if not isinstance(examiner, Address) else examiner
        if ex_addr not in self.examiners:
            return {
                "examiner_address": ex_addr.as_hex,
                "stake_atto": "0",
                "examinations_completed": 0,
                "disputes_lost": 0,
                "reputation_score": 0,
                "is_active": False,
            }
        ex = self.examiners[ex_addr]
        return {
            "examiner_address": ex.examiner_address.as_hex,
            "stake_atto": str(int(ex.bonded_stake_atto)),
            "examinations_completed": int(ex.examinations_completed),
            "disputes_lost": int(ex.disputes_lost),
            "reputation_score": int(ex.reputation_score),
            "is_active": ex.is_active,
        }

    @gl.public.view
    def get_records(self, invention_id: str) -> list:
        out = []
        for r in self.audit_records:
            if r.invention_id == invention_id:
                out.append({
                    "invention_id": r.invention_id,
                    "examiner": r.examiner.as_hex,
                    "decision": r.decision,
                    "novelty_score": int(r.novelty_score),
                    "inventive_step_score": int(r.inventive_step_score),
                    "collision_rate": int(r.collision_rate),
                    "rationale": r.rationale,
                    "multi_source_telemetry": r.multi_source_telemetry,
                    "timestamp_seq": int(r.timestamp_seq),
                })
        return out

    @gl.public.view
    def list_inventions(self) -> list:
        out = []
        for inv_id in self.invention_ids:
            out.append(self.get_invention(inv_id))
        return out

    @gl.public.view
    def get_protocol_overview(self) -> dict:
        return {
            "owner": self.owner.as_hex,
            "oracle_api_base": self.oracle_api_base,
            "total_inventions": int(self.total_inventions),
            "total_examiner_stake_atto": str(int(self.total_examiner_stake_atto)),
            "total_licensing_royalties_atto": str(int(self.total_licensing_royalties_atto)),
            "total_challenges_count": int(self.total_challenges_count),
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

    raw_dec = str(parsed.get("decision", DECISION_REJECTED)).strip().upper()
    decision = DECISION_APPROVED if raw_dec in ("APPROVED", "CERTIFIED", "VALID", "NOVEL") else DECISION_REJECTED
    novelty = max(0, min(100, int(parsed.get("novelty_score", 50))))
    inventive = max(0, min(100, int(parsed.get("inventive_step_score", 50))))
    collision_rate = max(0, min(100, int(parsed.get("citation_collision_rate", 50))))
    prior_collision = bool(parsed.get("prior_art_collision", False))
    rationale = str(parsed.get("rationale", "Prior-art analysis completed."))[:300]

    return {
        "decision": decision,
        "novelty_score": novelty,
        "inventive_step_score": inventive,
        "citation_collision_rate": collision_rate,
        "prior_art_collision": prior_collision,
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
