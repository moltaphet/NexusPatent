"""Comprehensive Direct Pytest Suite for NexusPatent DeSci Oracle."""

import json
import pytest
from conftest import (
    CONTRACT_PATH,
    mock_ai_novelty,
    mock_literature_oracle,
)

ATTO = 10**18
EXAMINER_BOND = 5 * ATTO
CHALLENGE_BOND = 3 * ATTO


def test_initial_state(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)
    overview = contract.get_protocol_overview()
    assert overview["total_inventions"] == 0
    assert overview["total_examiner_stake_atto"] == "0"
    assert overview["total_challenges_count"] == 0


def test_register_ai_invention(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_alice
    contract.register_invention(
        "inv-ai-agent-consensus-2026",
        "SOFTWARE_AI",
        "sha256:7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069",
        "bafybeicde2patentclaimsagenticconsensus2026",
        50000 * ATTO,
        "Byzantine Fault-Tolerant Multi-Agent LLM Consensus Engine",
    )

    inv = contract.get_invention("inv-ai-agent-consensus-2026")
    assert inv["invention_id"] == "inv-ai-agent-consensus-2026"
    assert inv["title"] == "Byzantine Fault-Tolerant Multi-Agent LLM Consensus Engine"
    assert inv["category"] == "SOFTWARE_AI"
    assert inv["status"] == "SUBMITTED"
    assert inv["novelty_score"] == 0
    assert inv["patent_index"] == 0


def test_register_biotech_invention(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_alice
    contract.register_invention(
        "inv-crispr-prime-editing-2026",
        "BIOTECH_GENOMICS",
        "sha256:88fa2b189cc3d181045a2ef044810dcba7192a0149bb88ff210b3d8819ab0011",
        "bafybeiallogeneiccartcellbaseediting2026",
        100000 * ATTO,
        "Multi-Locus Epigenetic Base Editor for Allogeneic CAR-T",
    )

    inv = contract.get_invention("inv-crispr-prime-editing-2026")
    assert inv["category"] == "BIOTECH_GENOMICS"
    assert inv["status"] == "SUBMITTED"
    assert inv["valuation_atto"] == str(100000 * ATTO)


def test_register_all_valid_categories(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_alice
    categories = [
        "BIOTECH_GENOMICS",
        "HARDWARE_SEMICONDUCTORS",
        "SOFTWARE_AI",
        "CLEANTECH_ENERGY",
        "MATERIALS_SCIENCE",
        "QUANTUM_COMPUTING",
    ]

    for idx, cat in enumerate(categories):
        inv_id = f"inv-cat-test-{idx}"
        contract.register_invention(
            inv_id,
            cat,
            f"sha256:hash_{idx}",
            f"ipfs://cid_{idx}",
            (idx + 1) * 1000 * ATTO,
            f"Invention for {cat}",
        )
        inv = contract.get_invention(inv_id)
        assert inv["category"] == cat


def test_register_duplicate_rejection(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_alice
    contract.register_invention(
        "inv-dup-01",
        "QUANTUM_COMPUTING",
        "sha256:claim1",
        "ipfs://cid1",
        10000 * ATTO,
    )

    with pytest.raises(Exception) as exc:
        contract.register_invention(
            "inv-dup-01",
            "QUANTUM_COMPUTING",
            "sha256:claim2",
            "ipfs://cid2",
            20000 * ATTO,
        )
    assert "already registered" in str(exc.value)


def test_register_empty_id_rejection(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_alice
    with pytest.raises(Exception) as exc:
        contract.register_invention(
            "",
            "QUANTUM_COMPUTING",
            "sha256:claim",
            "ipfs://cid",
            10000 * ATTO,
        )
    assert "Invention ID cannot be empty" in str(exc.value)


def test_register_invalid_category_rejection(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_alice
    with pytest.raises(Exception) as exc:
        contract.register_invention(
            "inv-invalid-cat",
            "ASTROPHYSICS_WARP_DRIVE",
            "sha256:claim",
            "ipfs://cid",
            10000 * ATTO,
        )
    assert "Invalid category" in str(exc.value)


def test_register_zero_valuation_rejection(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_alice
    with pytest.raises(Exception) as exc:
        contract.register_invention(
            "inv-zero-val",
            "MATERIALS_SCIENCE",
            "sha256:claim",
            "ipfs://cid",
            0,
        )
    assert "Valuation must be greater than zero" in str(exc.value)


def test_examiner_stake_success(direct_vm, direct_deploy, direct_bob):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_bob
    direct_vm.value = EXAMINER_BOND

    contract.stake_examiner()

    ex = contract.get_examiner(direct_bob)
    assert ex["examiner_address"].lower() == ("0x" + direct_bob.hex()).lower()
    assert ex["stake_atto"] == str(EXAMINER_BOND)
    assert ex["reputation_score"] == 100
    assert ex["is_active"] is True


def test_examiner_stake_zero_rejection(direct_vm, direct_deploy, direct_bob):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_bob
    direct_vm.value = 0

    with pytest.raises(Exception) as exc:
        contract.stake_examiner()
    assert "Stake amount must be greater than zero" in str(exc.value)


def test_examiner_withdraw_stake(direct_vm, direct_deploy, direct_bob):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_bob
    direct_vm.value = 10 * ATTO
    contract.stake_examiner()

    direct_vm.value = 0
    contract.withdraw_examiner_stake(4 * ATTO)

    ex = contract.get_examiner(direct_bob)
    assert ex["stake_atto"] == str(6 * ATTO)
    assert ex["is_active"] is True


def test_examiner_withdraw_excessive_rejection(direct_vm, direct_deploy, direct_bob):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_bob
    direct_vm.value = 5 * ATTO
    contract.stake_examiner()

    direct_vm.value = 0
    with pytest.raises(Exception) as exc:
        contract.withdraw_examiner_stake(6 * ATTO)
    assert "Invalid withdrawal amount" in str(exc.value)


def test_evaluate_patentability_novel_certified(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy(CONTRACT_PATH)

    direct_vm.sender = direct_alice
    contract.register_invention(
        "inv-photonic-qubit-2026",
        "QUANTUM_COMPUTING",
        "sha256:7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069",
        "bafybeicde2photonicquantumqubitrouting2026",
        250000 * ATTO,
        "Topological Photonic Waveguide for Fault-Tolerant Qubit Routing",
    )

    direct_vm.sender = direct_bob
    direct_vm.value = EXAMINER_BOND
    contract.stake_examiner()

    mock_literature_oracle(direct_vm)
    mock_ai_novelty(
        direct_vm,
        decision="APPROVED",
        novelty_score=92,
        inventive_step_score=88,
        citation_collision_rate=12,
        prior_art_collision=False,
        rationale="Chiral edge state modes verify non-obvious topological photonics with minimal prior art.",
    )

    contract.evaluate_patentability("inv-photonic-qubit-2026")

    inv = contract.get_invention("inv-photonic-qubit-2026")
    assert inv["status"] == "CERTIFIED"
    assert inv["novelty_score"] == 92
    assert inv["inventive_step_score"] == 88
    # PI = (92 * 40 + 88 * 45 + (100 - 12) * 15) // 100 = (3680 + 3960 + 1320) // 100 = 89
    assert inv["patent_index"] == 89
    assert inv["assigned_examiner"].lower() == ("0x" + direct_bob.hex()).lower()


def test_evaluate_patentability_prior_art_rejected(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy(CONTRACT_PATH)

    direct_vm.sender = direct_alice
    contract.register_invention(
        "inv-obvious-transformer-01",
        "SOFTWARE_AI",
        "sha256:obvious-attention-variant",
        "ipfs://cid-obvious-claims",
        5000 * ATTO,
        "Standard Multi-Head Attention With Linear Layer",
    )

    direct_vm.sender = direct_bob
    direct_vm.value = EXAMINER_BOND
    contract.stake_examiner()

    mock_literature_oracle(direct_vm)
    mock_ai_novelty(
        direct_vm,
        decision="REJECTED",
        novelty_score=35,
        inventive_step_score=20,
        citation_collision_rate=85,
        prior_art_collision=True,
        rationale="Claims heavily overlap with Vaswani et al. (2017) and lack an inventive step.",
    )

    contract.evaluate_patentability("inv-obvious-transformer-01")

    inv = contract.get_invention("inv-obvious-transformer-01")
    assert inv["status"] == "REJECTED"
    assert inv["novelty_score"] == 35
    assert inv["patent_index"] == 0


def test_evaluate_patentability_unbonded_examiner_rejection(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy(CONTRACT_PATH)

    direct_vm.sender = direct_alice
    contract.register_invention(
        "pat-unbonded-test",
        "SOFTWARE_AI",
        "sha256:claim",
        "ipfs://cid",
        10000 * ATTO,
    )

    # Bob attempts to examine without staking bond
    direct_vm.sender = direct_bob
    with pytest.raises(Exception) as exc:
        contract.evaluate_patentability("pat-unbonded-test")
    assert "not a registered examiner" in str(exc.value) or "insufficiently bonded" in str(exc.value)


def test_dispute_patent_novelty_success(direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
    contract = direct_deploy(CONTRACT_PATH)

    direct_vm.sender = direct_alice
    contract.register_invention(
        "pat-to-dispute",
        "MATERIALS_SCIENCE",
        "sha256:solid-state-electrolyte-lithium",
        "ipfs://cid-electrolyte-proof",
        1000000 * ATTO,
        "Solid-State Ceramic Electrolyte With High Ionic Conductivity",
    )

    direct_vm.sender = direct_bob
    direct_vm.value = EXAMINER_BOND
    contract.stake_examiner()

    mock_literature_oracle(direct_vm)
    mock_ai_novelty(
        direct_vm,
        decision="APPROVED",
        novelty_score=85,
        inventive_step_score=80,
        citation_collision_rate=10,
        prior_art_collision=False,
        rationale="Novel ceramic solid state electrolyte.",
    )
    contract.evaluate_patentability("pat-to-dispute")

    inv = contract.get_invention("pat-to-dispute")
    assert inv["status"] == "CERTIFIED"

    # Charlie disputes with new prior art proving collision
    direct_vm.sender = direct_charlie
    direct_vm.value = CHALLENGE_BOND

    direct_vm.clear_mocks()
    mock_literature_oracle(direct_vm, payload={"dispute_result": "PRIOR_ART_FOUND", "identical_patent": "US1098234B2"})
    mock_ai_novelty(
        direct_vm,
        decision="REJECTED",
        novelty_score=15,
        inventive_step_score=10,
        citation_collision_rate=95,
        prior_art_collision=True,
        rationale="Challenger cited US1098234B2 showing 100% identical composition.",
    )

    contract.dispute_patent_novelty(
        "pat-to-dispute",
        "Exact identical stoichiometry was published in US1098234B2 in 2021",
        "https://api.uspto.gov/patents/US1098234B2",
    )

    inv_after = contract.get_invention("pat-to-dispute")
    assert inv_after["status"] == "INVALIDATED"
    assert inv_after["patent_index"] == 0

    ex_after = contract.get_examiner(direct_bob)
    assert ex_after["disputes_lost"] == 1
    assert int(ex_after["stake_atto"]) < int(EXAMINER_BOND)


def test_dispute_patent_novelty_insufficient_bond_rejection(direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
    contract = direct_deploy(CONTRACT_PATH)

    direct_vm.sender = direct_alice
    contract.register_invention(
        "pat-dispute-low-bond",
        "CLEANTECH_ENERGY",
        "sha256:claim",
        "ipfs://cid",
        50000 * ATTO,
    )

    direct_vm.sender = direct_bob
    direct_vm.value = EXAMINER_BOND
    contract.stake_examiner()

    mock_literature_oracle(direct_vm)
    mock_ai_novelty(direct_vm, decision="APPROVED", novelty_score=88, inventive_step_score=85)
    contract.evaluate_patentability("pat-dispute-low-bond")

    direct_vm.sender = direct_charlie
    direct_vm.value = 1 * ATTO  # Less than 3 GEN

    with pytest.raises(Exception) as exc:
        contract.dispute_patent_novelty("pat-dispute-low-bond", "Some dispute")
    assert "Minimum challenge bond is 3 GEN" in str(exc.value)


def test_approve_licensing_success(direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
    contract = direct_deploy(CONTRACT_PATH)

    direct_vm.sender = direct_alice
    contract.register_invention(
        "pat-to-license",
        "QUANTUM_COMPUTING",
        "sha256:superconducting-qubit-coupler",
        "ipfs://cid-qubit-proof",
        300000 * ATTO,
        "Tunable Superconducting Qubit Coupler",
    )

    direct_vm.sender = direct_bob
    direct_vm.value = EXAMINER_BOND
    contract.stake_examiner()

    mock_literature_oracle(direct_vm)
    mock_ai_novelty(direct_vm, decision="APPROVED", novelty_score=92, inventive_step_score=88)
    contract.evaluate_patentability("pat-to-license")

    # Inventor approves 25% commercial licensing share to Charlie
    direct_vm.sender = direct_alice
    contract.approve_licensing("pat-to-license", direct_charlie, 2500)

    inv = contract.get_invention("pat-to-license")
    assert inv["status"] == "LICENSED"
    assert inv["licensee"].lower() == ("0x" + direct_charlie.hex()).lower()
    assert inv["licensing_share_bps"] == 2500


def test_approve_licensing_unverified_rejection(direct_vm, direct_deploy, direct_alice, direct_charlie):
    contract = direct_deploy(CONTRACT_PATH)

    direct_vm.sender = direct_alice
    contract.register_invention(
        "pat-unverified",
        "SOFTWARE_AI",
        "sha256:claim",
        "ipfs://cid",
        10000 * ATTO,
    )

    with pytest.raises(Exception) as exc:
        contract.approve_licensing("pat-unverified", direct_charlie, 5000)
    assert "Invention must be certified before licensing" in str(exc.value)


def test_reclaim_stale_submission_success(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)

    direct_vm.sender = direct_alice
    contract.register_invention(
        "pat-stale",
        "CLEANTECH_ENERGY",
        "sha256:stale-fusion-claim",
        "ipfs://cid-stale",
        100000 * ATTO,
    )

    contract.reclaim_stale_submission("pat-stale")

    inv = contract.get_invention("pat-stale")
    assert inv["status"] == "EXPIRED"


def test_list_inventions_and_records(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy(CONTRACT_PATH)

    direct_vm.sender = direct_alice
    contract.register_invention("pat-list-1", "SOFTWARE_AI", "sha256:1", "ipfs://1", 1000 * ATTO)
    contract.register_invention("pat-list-2", "BIOTECH_GENOMICS", "sha256:2", "ipfs://2", 2000 * ATTO)

    direct_vm.sender = direct_bob
    direct_vm.value = EXAMINER_BOND
    contract.stake_examiner()

    mock_literature_oracle(direct_vm)
    mock_ai_novelty(direct_vm, decision="APPROVED", novelty_score=90, inventive_step_score=85)
    contract.evaluate_patentability("pat-list-1")

    inventions = contract.list_inventions()
    assert len(inventions) == 2

    records = contract.get_records("pat-list-1")
    assert len(records) == 1
    assert records[0]["decision"] == "CERTIFIED"


def test_grounded_web_fetch_empty_failure_rejection(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy(CONTRACT_PATH)

    direct_vm.sender = direct_alice
    contract.register_invention(
        "pat-grounded-fail",
        "QUANTUM_COMPUTING",
        "sha256:grounded-test-claim",
        "ipfs://cid-grounded-proof",
        100000 * ATTO,
    )

    direct_vm.sender = direct_bob
    direct_vm.value = EXAMINER_BOND
    contract.stake_examiner()

    # Mock web returning empty content (< 10 bytes)
    direct_vm.mock_web(r".*", {"status": 200, "body": ""})

    with pytest.raises(Exception) as exc:
        contract.evaluate_patentability("pat-grounded-fail")
    assert "[EXTERNAL]" in str(exc.value) or "empty or insufficient" in str(exc.value)


def test_grounded_web_fetch_unreachable_rejection(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy(CONTRACT_PATH)

    direct_vm.sender = direct_alice
    contract.register_invention(
        "pat-unreachable-test",
        "BIOTECH_GENOMICS",
        "sha256:unreachable-claim",
        "ipfs://cid-unreachable",
        100000 * ATTO,
    )

    direct_vm.sender = direct_bob
    direct_vm.value = EXAMINER_BOND
    contract.stake_examiner()

    # Mock web returning 500 error or network exception
    direct_vm.mock_web(r".*", {"status": 500, "body": "Internal Server Error"})

    with pytest.raises(Exception) as exc:
        contract.evaluate_patentability("pat-unreachable-test")
    assert "[EXTERNAL]" in str(exc.value) or "500" in str(exc.value)
