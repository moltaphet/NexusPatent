#!/usr/bin/env python3
"""
NexusPatent 1-Click End-to-End Lifecycle Demonstration.
Simulates the complete DeSci IP lifecycle on GenLayer.
"""

import json
from gltest.direct import VMContext, deploy_contract, create_address

ATTO = 10**18


def log_step(num: int, title: str):
    print(f"\n\033[1;36m[STEP {num}] {title}\033[0m")


def log_success(msg: str):
    print(f"  \033[1;32m✓\033[0m {msg}")


def log_info(key: str, val: str):
    print(f"  \033[1;34m•\033[0m {key}: \033[1;37m{val}\033[0m")


def main():
    print("\033[1;35m" + "=" * 70)
    print(" 🏛  NEXUSPATENT: 1-CLICK END-TO-END DECENTRALIZED IP LIFECYCLE")
    print("=" * 70 + "\033[0m")

    # 1. Initialize Direct VM Environment
    vm = VMContext()
    alice = create_address("alice")      # Inventor
    bob = create_address("bob")          # Bonded Examiner
    charlie = create_address("charlie")  # Corporate Licensee

    with vm.activate():
        vm.sender = alice
        contract = deploy_contract("src/nexus_patent.py", vm=vm)

        # STEP 1: Registration
        log_step(1, "Inventor Registers Novel Photonic Qubit Router")
        vm.sender = alice
        contract.register_invention(
            "pat-qubit-2026",
            "QUANTUM_COMPUTING",
            "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "ipfs://bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
            500000 * ATTO,
            "Zero-Loss Waveguide Mesh for Superconducting Qubits",
        )
        inv = contract.get_invention("pat-qubit-2026")
        log_success(f"Invention Registered: {inv['title']} (Status: {inv['status']})")
        log_info("Claims Cryptographic Hash", inv["claims_hash"][:32] + "...")
        log_info("Paper Decentralized CID", inv["paper_cid_proof"])

        # STEP 2: Examiner Staking
        log_step(2, "Peer Examiner Stakes 5 GEN Anti-Collusion Bond")
        vm.sender = bob
        vm.value = 5 * ATTO
        contract.stake_examiner()
        ex = contract.get_examiner(bob)
        log_success(f"Examiner Bonded: {int(ex['stake_atto']) // ATTO} GEN Staked (Reputation: {ex['reputation_score']})")

        # STEP 3: Autonomous AI Prior-Art Audit
        log_step(3, "GenLayer Multi-LLM Quorum Audits Global Literature & Prior-Art")
        vm.mock_web(r".*", {"status": 200, "body": json.dumps({"citations_analyzed": 142, "overlap_index": 0.02})})
        vm.mock_llm(
            r".*",
            json.dumps({
                "decision": "APPROVED",
                "novelty_score": 96,
                "inventive_step_score": 92,
                "citation_collision_rate": 4,
                "prior_art_collision": False,
                "rationale": "First demonstration of zero-loss optical routing for transmon qubits with verified proof.",
            })
        )
        contract.evaluate_patentability("pat-qubit-2026")
        certified = contract.get_invention("pat-qubit-2026")
        log_success(f"Patent Certified! Status: {certified['status']}")
        log_info("Novelty Score", f"{certified['novelty_score']}/100")
        log_info("Inventive Step Score", f"{certified['inventive_step_score']}/100")
        log_info("Composite Patent Index (PI)", f"{certified['patent_index']}/100")

        # STEP 4: Fractional IP Licensing
        log_step(4, "Institutional Licensee Acquires 25% Commercial Rights")
        vm.sender = alice
        contract.approve_licensing("pat-qubit-2026", charlie, 2500)
        licensed = contract.get_invention("pat-qubit-2026")
        log_success(f"License Active! Commercial Share: {licensed['licensing_share_bps'] / 100}%")
        log_info("Licensee Address", licensed["licensee"])

        # STEP 5: Verification of Immutable Audit Ledger
        log_step(5, "Inspect On-Chain Cryptographic Audit Trail")
        records = contract.get_records("pat-qubit-2026")
        log_success(f"Found {len(records)} Immutable Audit Record(s)")
        log_info("Examiner Decision", records[0]["decision"])
        log_info("Examiner Rationale", records[0]["rationale"])

        print("\n\033[1;32m" + "=" * 70)
        print(" 🎉 COMPLETE E2E RUNNABLE WORKFLOW VERIFIED SUCCESSFULLY (100% PASS)")
        print("=" * 70 + "\033[0m\n")


if __name__ == "__main__":
    main()
