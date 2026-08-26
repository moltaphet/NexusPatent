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
        "pat-ai-transformer-v1",
        "SOFTWARE_AI",
        "sha256:transformer-novel-attention-kernel",
        "ipfs://bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
        100000 * ATTO,
        "Sparse Attention Mechanism Scaling Linearly",
    )

    inv = contract.get_invention("pat-ai-transformer-v1")
    assert inv["invention_id"] == "pat-ai-transformer-v1"
    assert inv["category"] == "SOFTWARE_AI"
    assert inv["status"] == "SUBMITTED"
    assert inv["inventor"].lower().removeprefix("0x") == direct_alice.hex().lower()


def test_register_biotech_invention(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_alice

    contract.register_invention(
        "pat-crispr-v2",
        "BIOTECH_GENOMICS",
        "sha256:crispr-prime-editing-target-sequence",
        "ipfs://bafybeicrisprprimeeditingproof",
        250000 * ATTO,
        "Targeted Prime Editing With Zero Off-Target Cleavage",
    )

    inv = contract.get_invention("pat-crispr-v2")
    assert inv["invention_id"] == "pat-crispr-v2"
    assert inv["category"] == "BIOTECH_GENOMICS"


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
        pid = f"pat-valid-{idx}"
        contract.register_invention(
            pid,
            cat,
            f"sha256:hash-{idx}",
            f"ipfs://cid-{idx}",
            10000 * ATTO,
            f"Title {idx}",
        )
        assert contract.get_invention(pid)["category"] == cat


def test_register_duplicate_rejection(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_alice

    contract.register_invention(
        "pat-dup-test",
        "SOFTWARE_AI",
        "sha256:first-claim",
        "ipfs://cid-1",
        10000 * ATTO,
    )

    with pytest.raises(Exception) as exc:
        contract.register_invention(
            "pat-dup-test",
            "SOFTWARE_AI",
            "sha256:second-claim",
            "ipfs://cid-2",
            20000 * ATTO,
        )
    assert "already registered" in str(exc.value)


def test_register_empty_id_rejection(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_alice

    with pytest.raises(Exception) as exc:
        contract.register_invention(
            "",
            "SOFTWARE_AI",
            "sha256:claim",
            "ipfs://cid",
            1000 * ATTO,
        )
    assert "Invention ID cannot be empty" in str(exc.value)


def test_register_invalid_category_rejection(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_alice

    with pytest.raises(Exception) as exc:
        contract.register_invention(
            "pat-bad-cat",
            "FASHION_APPAREL",
            "sha256:claim",
            "ipfs://cid",
            1000 * ATTO,
        )
    assert "Invalid category" in str(exc.value)


def test_register_zero_valuation_rejection(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_alice

    with pytest.raises(Exception) as exc:
        contract.register_invention(
            "pat-zero-val",
            "SOFTWARE_AI",
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
    assert ex["stake_atto"] == str(EXAMINER_BOND)
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

    contract.withdraw_examiner_stake(4 * ATTO)
    ex = contract.get_examiner(direct_bob)
    assert ex["stake_atto"] == str(6 * ATTO)


def test_examiner_withdraw_excessive_rejection(direct_vm, direct_deploy, direct_bob):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_bob
    direct_vm.value = 5 * ATTO
    contract.stake_examiner()

    with pytest.raises(Exception) as exc:
        contract.withdraw_examiner_stake(6 * ATTO)
    assert "Invalid withdrawal amount" in str(exc.value)


def test_evaluate_patentability_novel_certified(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy(CONTRACT_PATH)

    direct_vm.sender = direct_alice
    contract.register_invention(
        "pat-novel-01",
        "SOFTWARE_AI",
        "sha256:quantum-circuit-optimization-dag",
        "ipfs://cid-quantum-dag-proof",
        500000 * ATTO,
        "Quantum Circuit Optimization via Topological DAG Compilation",
    )

    direct_vm.sender = direct_bob
    direct_vm.value = EXAMINER_BOND
    contract.stake_examiner()

    mock_literature_oracle(direct_vm, {"status": "ok", "total_citations": 4, "prior_art_collision": False})
    mock_ai_novelty(
        direct_vm,
        decision="APPROVED",
        novelty_score=94,
        inventive_step_score=90,
        citation_collision_rate=6,
        prior_art_collision=False,
        rationale="Novel topological compilation algorithm reducing gate depth by 48%.",
    )

    contract.evaluate_patentability("pat-novel-01")

    inv = contract.get_invention("pat-novel-01")
    assert inv["status"] == "CERTIFIED"
    assert inv["novelty_score"] == 94
    assert inv["inventive_step_score"] == 90
    assert inv["patent_index"] == 92


def test_evaluate_patentability_prior_art_rejected(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy(CONTRACT_PATH)

    direct_vm.sender = direct_alice
    contract.register_invention(
        "pat-colliding-01",
        "SOFTWARE_AI",
        "sha256:standard-relu-activation-layer",
        "ipfs://cid-relu-proof",
        10000 * ATTO,
        "Rectified Linear Activation Layer for Neural Networks",
    )

    direct_vm.sender = direct_bob
    direct_vm.value = EXAMINER_BOND
    contract.stake_examiner()

    mock_literature_oracle(direct_vm, {"status": "collision", "existing_doi": "10.5555/3104322.3104425"})
    mock_ai_novelty(
        direct_vm,
        decision="REJECTED",
        novelty_score=15,
        inventive_step_score=10,
        citation_collision_rate=92,
        prior_art_collision=True,
        rationale="Identical activation function published by Nair & Hinton in ICML 2010.",
    )

    contract.evaluate_patentability("pat-colliding-01")

    inv = contract.get_invention("pat-colliding-01")
    assert inv["status"] == "REJECTED"
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
    assert "Caller must be a bonded examiner" in str(exc.value)


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

    # Initial evaluation mock (novel)
    direct_vm.mock_web(r".*", {"status": 200, "body": json.dumps({"status": "ok"})})
    direct_vm.mock_llm(
        r".*cid-electrolyte-proof.*",
        json.dumps({
            "decision": "APPROVED",
            "novelty_score": 85,
            "inventive_step_score": 80,
            "citation_collision_rate": 10,
            "prior_art_collision": False,
            "rationale": "Novel ceramic solid state electrolyte.",
        }),
    )
    contract.evaluate_patentability("pat-to-dispute")
    assert contract.get_invention("pat-to-dispute")["status"] == "CERTIFIED"

    # Dispute evaluation mock (invalidated)
    direct_vm.sender = direct_charlie
    direct_vm.value = CHALLENGE_BOND

    direct_vm.mock_llm(
        r".*DISPUTE.*",
        json.dumps({
            "decision": "REJECTED",
            "novelty_score": 20,
            "inventive_step_score": 15,
            "citation_collision_rate": 95,
            "prior_art_collision": True,
            "rationale": "Solid-state ceramic formula was fully disclosed in Nature Materials 2021.",
        }),
    )

    contract.dispute_patent_novelty(
        "pat-to-dispute",
        "Prior disclosure in Nature Materials 2021 paper.",
        "https://nature.com/articles/s41586-021-solid-state",
    )

    inv = contract.get_invention("pat-to-dispute")
    assert inv["status"] == "INVALIDATED"
    assert inv["patent_index"] == 0


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
    direct_vm.value = 1 * ATTO  # < 3 GEN required
    with pytest.raises(Exception) as exc:
        contract.dispute_patent_novelty(
            "pat-dispute-low-bond",
            "Dispute reason",
        )
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

    # Alice grants 30% license share to Charlie
    direct_vm.sender = direct_alice
    contract.approve_licensing("pat-to-license", direct_charlie, 3000)

    inv = contract.get_invention("pat-to-license")
    assert inv["status"] == "LICENSED"
    assert inv["licensee"].lower().removeprefix("0x") == direct_charlie.hex().lower()
    assert inv["licensing_share_bps"] == 3000


def test_approve_licensing_unverified_rejection(direct_vm, direct_deploy, direct_alice, direct_charlie):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_alice
    contract.register_invention(
        "pat-unverified",
        "SOFTWARE_AI",
        "sha256:hash",
        "ipfs://cid",
        50000 * ATTO,
    )
    with pytest.raises(Exception) as exc:
        contract.approve_licensing("pat-unverified", direct_charlie, 2000)
    assert "Invention must be certified before licensing" in str(exc.value)


def test_reclaim_stale_submission_success(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_alice
    contract.register_invention(
        "pat-stale-01",
        "SOFTWARE_AI",
        "sha256:stale-claim",
        "ipfs://cid-stale",
        20000 * ATTO,
    )

    # Inventor reclaims stale unexamined submission
    contract.reclaim_stale_submission("pat-stale-01")
    inv = contract.get_invention("pat-stale-01")
    assert inv["status"] == "EXPIRED"


def test_list_inventions_and_records(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy(CONTRACT_PATH)

    direct_vm.sender = direct_bob
    direct_vm.value = EXAMINER_BOND
    contract.stake_examiner()

    direct_vm.sender = direct_alice
    contract.register_invention(
        "pat-list-test",
        "HARDWARE_SEMICONDUCTORS",
        "sha256:depin-wireless-mesh-routing",
        "ipfs://cid-hardware",
        75000 * ATTO,
    )

    inventions = contract.list_inventions()
    assert len(inventions) == 1
    assert inventions[0]["invention_id"] == "pat-list-test"
