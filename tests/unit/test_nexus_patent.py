"""Comprehensive Direct Pytest Suite for NexusPatent DeSci Oracle (v2.0)."""

import pytest
from conftest import (
    CONTRACT_PATH,
    mock_ai_novelty,
    mock_literature_oracle,
)

ATTO = 10**18
EXAMINER_BOND = 5 * ATTO
CHALLENGE_BOND = 3 * ATTO


# -----------------------------------------------------------------------------
# 1. Initialization & State Verification
# -----------------------------------------------------------------------------
def test_initial_state(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)
    overview = contract.get_protocol_overview()
    assert overview["total_inventions"] == 0
    assert overview["total_examinations"] == 0
    assert overview["total_staked"] == "0"
    assert overview["total_challenges"] == 0


# -----------------------------------------------------------------------------
# 2. Invention Registration Tests
# -----------------------------------------------------------------------------
def test_register_ai_invention(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_alice

    contract.register_invention(
        "pat-ai-transformer-v1",
        "SOFTWARE_AI",
        "sha256:transformer-novel-attention-kernel",
        "Sparse attention mechanism scaling linearly with sequence length.",
        100000 * ATTO,
    )
    inv = contract.get_invention("pat-ai-transformer-v1")
    assert inv["invention_id"] == "pat-ai-transformer-v1"
    assert inv["category"] == "SOFTWARE_AI"
    assert inv["status"] == "PENDING_EXAMINATION"
    assert inv["registered_seq"] == 1


def test_register_biotech_invention(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_alice

    contract.register_invention(
        "pat-crispr-cas14-mod",
        "BIOTECH_PHARMA",
        "sha256:crispr-cas14-cleavage-variant",
        "Targeted single-stranded DNA cleavage enzyme with zero off-target binding.",
        500000 * ATTO,
    )
    inv = contract.get_invention("pat-crispr-cas14-mod")
    assert inv["category"] == "BIOTECH_PHARMA"
    assert inv["estimated_valuation_atto"] == str(500000 * ATTO)


def test_register_all_valid_categories(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_alice

    categories = [
        "SOFTWARE_AI",
        "BIOTECH_PHARMA",
        "HARDWARE_ENERGY",
        "MECHANICAL_ROBOTICS",
        "DEPIN_NETWORKS",
    ]
    for idx, cat in enumerate(categories):
        inv_id = f"pat-category-test-{idx}"
        contract.register_invention(
            inv_id,
            cat,
            "sha256:hash-sample",
            f"Abstract for {cat}",
            50000 * ATTO,
        )
        inv = contract.get_invention(inv_id)
        assert inv["category"] == cat


def test_register_duplicate_rejection(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_alice

    contract.register_invention(
        "pat-dup-01",
        "SOFTWARE_AI",
        "sha256:hash-1",
        "Summary 1",
        10000 * ATTO,
    )
    with pytest.raises(Exception) as exc:
        contract.register_invention(
            "pat-dup-01",
            "SOFTWARE_AI",
            "sha256:hash-2",
            "Summary 2",
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
            "sha256:valid-hash",
            "Summary",
            10000 * ATTO,
        )
    assert "cannot be empty" in str(exc.value)


def test_register_invalid_category_rejection(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_alice

    with pytest.raises(Exception) as exc:
        contract.register_invention(
            "pat-invalid-cat",
            "REAL_ESTATE",
            "sha256:valid-hash",
            "Summary",
            10000 * ATTO,
        )
    assert "Invalid category" in str(exc.value)


def test_register_zero_valuation_rejection(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_alice

    with pytest.raises(Exception) as exc:
        contract.register_invention(
            "pat-zero-val",
            "SOFTWARE_AI",
            "sha256:valid-hash",
            "Summary",
            0,
        )
    assert "must be greater than zero" in str(exc.value)


# -----------------------------------------------------------------------------
# 3. Examiner Staking & Slashing Tests
# -----------------------------------------------------------------------------
def test_examiner_stake_success(direct_vm, direct_deploy, direct_bob):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_bob
    direct_vm.value = 5 * ATTO

    contract.stake_examiner()
    prof = contract.get_examiner(direct_bob)
    assert prof["staked_collateral"] == str(5 * ATTO)
    assert prof["is_certified"] is True
    assert prof["total_reviews"] == 0


def test_examiner_stake_zero_rejection(direct_vm, direct_deploy, direct_bob):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_bob
    direct_vm.value = 0

    with pytest.raises(Exception) as exc:
        contract.stake_examiner()
    assert "must be greater than zero" in str(exc.value)


def test_examiner_withdraw_stake(direct_vm, direct_deploy, direct_bob):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_bob
    direct_vm.value = 10 * ATTO
    contract.stake_examiner()

    direct_vm.value = 0
    contract.withdraw_examiner_stake(4 * ATTO)

    prof = contract.get_examiner(direct_bob)
    assert prof["staked_collateral"] == str(6 * ATTO)
    assert prof["is_certified"] is True


def test_examiner_withdraw_excessive_rejection(direct_vm, direct_deploy, direct_bob):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_bob
    direct_vm.value = 5 * ATTO
    contract.stake_examiner()

    direct_vm.value = 0
    with pytest.raises(Exception) as exc:
        contract.withdraw_examiner_stake(10 * ATTO)
    assert "Withdrawal exceeds staked collateral" in str(exc.value)


# -----------------------------------------------------------------------------
# 4. Dual-Engine Prior-Art Audit Tests
# -----------------------------------------------------------------------------
def test_evaluate_patentability_novel_certified(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy(CONTRACT_PATH)

    # Alice registers invention
    direct_vm.sender = direct_alice
    contract.register_invention(
        "pat-quantum-transmon",
        "HARDWARE_ENERGY",
        "sha256:superconducting-transmon-circuit",
        "Fluxonium qubit architecture with 1ms coherence time.",
        2500000 * ATTO,
    )

    # Bob stakes examiner bond
    direct_vm.sender = direct_bob
    direct_vm.value = EXAMINER_BOND
    contract.stake_examiner()
    direct_vm.value = 0

    # Mock Web2 literature search and Multi-LLM Quorum
    mock_literature_oracle(direct_vm, {"status": "clean", "citations": []})
    mock_ai_novelty(
        direct_vm,
        decision="PATENTABLE",
        confidence=94,
        novelty=96,
        inventive=92,
        collision=8,
        rationale="Highly novel topological qubit structure.",
    )

    contract.evaluate_patentability(
        "pat-quantum-transmon",
        "Claim 1: A superconducting qubit comprising...",
        "Cryogenic dilution refrigerator test data at 10mK.",
        "No collisions found in IEEE Quantum Transactions.",
    )

    inv = contract.get_invention("pat-quantum-transmon")
    assert inv["status"] == "PATENTABLE_CERTIFIED"
    assert inv["examination_count"] == 1
    assert int(inv["patentability_index"]) >= 75


def test_evaluate_patentability_prior_art_rejected(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy(CONTRACT_PATH)

    direct_vm.sender = direct_alice
    contract.register_invention(
        "pat-colliding-claims",
        "SOFTWARE_AI",
        "sha256:standard-cnn-architecture",
        "Standard Convolutional Neural Network with 3x3 kernels.",
        50000 * ATTO,
    )

    direct_vm.sender = direct_bob
    direct_vm.value = EXAMINER_BOND
    contract.stake_examiner()
    direct_vm.value = 0

    mock_literature_oracle(
        direct_vm,
        {"citations": ["US Patent 7,200,268 (LeCun et al., 1989)"]},
    )
    mock_ai_novelty(
        direct_vm,
        decision="REJECTED",
        confidence=98,
        novelty=20,
        inventive=15,
        collision=85,
        rationale="Direct overlap with foundational LeCun 1989 CNN patents.",
    )

    contract.evaluate_patentability(
        "pat-colliding-claims",
        "Claim 1: A multi-layer CNN for digit recognition...",
        "MNIST benchmark code.",
    )

    inv = contract.get_invention("pat-colliding-claims")
    assert inv["status"] == "PRIOR_ART_REJECTED"
    assert int(inv["prior_art_collision"]) == 85


def test_evaluate_patentability_unbonded_examiner_rejection(direct_vm, direct_deploy, direct_alice, direct_charlie):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_alice
    contract.register_invention(
        "pat-test-unbonded",
        "SOFTWARE_AI",
        "sha256:hash-123",
        "Test Summary",
        50000 * ATTO,
    )

    # Charlie is unbonded
    direct_vm.sender = direct_charlie
    with pytest.raises(Exception) as exc:
        contract.evaluate_patentability(
            "pat-test-unbonded",
            "Claims",
            "Evidence",
        )
    assert "requires at least 5 GEN" in str(exc.value)


# -----------------------------------------------------------------------------
# 5. Invalidation Challenge Tests
# -----------------------------------------------------------------------------
def test_dispute_patent_novelty_success(direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
    contract = direct_deploy(CONTRACT_PATH)

    direct_vm.sender = direct_alice
    contract.register_invention(
        "pat-to-challenge",
        "SOFTWARE_AI",
        "sha256:hash-challenge",
        "Test Abstract",
        100000 * ATTO,
    )

    direct_vm.sender = direct_bob
    direct_vm.value = EXAMINER_BOND
    contract.stake_examiner()
    direct_vm.value = 0

    mock_literature_oracle(direct_vm)
    mock_ai_novelty(direct_vm, decision="PATENTABLE", confidence=90)
    contract.evaluate_patentability(
        "pat-to-challenge",
        "Claims",
        "Evidence",
    )

    # Charlie files dispute with 3 GEN bond
    direct_vm.sender = direct_charlie
    direct_vm.value = CHALLENGE_BOND
    contract.dispute_patent_novelty(
        "pat-to-challenge",
        "Uncovered prior publication on arXiv from 2021 with identical claims.",
        "ipfs://bafybeipriorartproof2021",
    )

    inv = contract.get_invention("pat-to-challenge")
    assert inv["status"] == "DISPUTED"
    assert inv["licensing_approved"] is False


def test_dispute_patent_novelty_insufficient_bond_rejection(direct_vm, direct_deploy, direct_alice, direct_charlie):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_alice
    contract.register_invention(
        "pat-test-bond",
        "SOFTWARE_AI",
        "sha256:hash",
        "Summary",
        50000 * ATTO,
    )

    direct_vm.sender = direct_charlie
    direct_vm.value = 1 * ATTO  # requires 3 GEN
    with pytest.raises(Exception) as exc:
        contract.dispute_patent_novelty(
            "pat-test-bond",
            "Reason",
            "ipfs://hash",
        )
    assert "requires at least 3 GEN bond" in str(exc.value)


# -----------------------------------------------------------------------------
# 6. Fractional Licensing Tests
# -----------------------------------------------------------------------------
def test_approve_licensing_success(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy(CONTRACT_PATH)

    direct_vm.sender = direct_alice
    contract.register_invention(
        "pat-biotech-vaccine",
        "BIOTECH_PHARMA",
        "sha256:mrna-lipid-nanoparticle-target",
        "mRNA lipid nanoparticle formulation with enhanced thermal stability.",
        1000000 * ATTO,
    )

    direct_vm.sender = direct_bob
    direct_vm.value = EXAMINER_BOND
    contract.stake_examiner()
    direct_vm.value = 0

    mock_literature_oracle(direct_vm)
    mock_ai_novelty(direct_vm, decision="PATENTABLE", confidence=95)
    contract.evaluate_patentability(
        "pat-biotech-vaccine",
        "Claims",
        "Evidence",
    )

    # Alice (inventor) approves licensing at 100 GEN per share
    direct_vm.sender = direct_alice
    denomination = 100 * ATTO
    max_shares = contract.approve_licensing(
        "pat-biotech-vaccine",
        denomination,
    )

    assert max_shares == 10000  # 1,000,000 / 100 = 10,000 shares
    inv = contract.get_invention("pat-biotech-vaccine")
    assert inv["licensing_approved"] is True
    assert inv["licensing_max_shares"] == "10000"


def test_approve_licensing_unverified_rejection(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)
    direct_vm.sender = direct_alice
    contract.register_invention(
        "pat-unverified",
        "SOFTWARE_AI",
        "sha256:hash",
        "Summary",
        50000 * ATTO,
    )
    with pytest.raises(Exception) as exc:
        contract.approve_licensing(
            "pat-unverified",
            100 * ATTO,
        )
    assert "must be PATENTABLE_CERTIFIED" in str(exc.value)


# -----------------------------------------------------------------------------
# 7. Examiner Reputation & Overview Tests
# -----------------------------------------------------------------------------
def test_examiner_reputation_tracking(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy(CONTRACT_PATH)

    direct_vm.sender = direct_bob
    direct_vm.value = EXAMINER_BOND
    contract.stake_examiner()
    direct_vm.value = 0

    direct_vm.sender = direct_alice
    contract.register_invention(
        "pat-rep-1",
        "SOFTWARE_AI",
        "sha256:hash-1",
        "Summary 1",
        10000 * ATTO,
    )

    direct_vm.sender = direct_bob
    mock_literature_oracle(direct_vm)
    mock_ai_novelty(direct_vm, decision="PATENTABLE", confidence=90)
    contract.evaluate_patentability(
        "pat-rep-1",
        "Claims",
        "Evidence",
    )

    prof = contract.get_examiner(direct_bob)
    assert prof["total_reviews"] == 1
    assert prof["certified_reviews"] == 1
    assert prof["accuracy_score"] == 100


def test_list_inventions_and_records(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy(CONTRACT_PATH)

    direct_vm.sender = direct_bob
    direct_vm.value = EXAMINER_BOND
    contract.stake_examiner()
    direct_vm.value = 0

    direct_vm.sender = direct_alice
    contract.register_invention(
        "pat-list-test",
        "DEPIN_NETWORKS",
        "sha256:depin-wireless-mesh-routing",
        "Zero-overhead decentralized packet routing protocol.",
        75000 * ATTO,
    )

    direct_vm.sender = direct_bob
    mock_literature_oracle(direct_vm)
    mock_ai_novelty(direct_vm, decision="PATENTABLE", confidence=92)
    contract.evaluate_patentability(
        "pat-list-test",
        "Claims",
        "Evidence",
    )

    inv_list = contract.list_inventions()
    assert len(inv_list) == 1
    assert inv_list[0]["invention_id"] == "pat-list-test"

    records = contract.get_records("pat-list-test")
    assert len(records) == 1
    assert records[0]["decision"] == "PATENTABLE"
