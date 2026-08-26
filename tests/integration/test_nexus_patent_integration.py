"""GenLayer Integration Test Suite for NexusPatent."""

import pytest
from gltest import get_contract_factory
from gltest.assertions import tx_execution_succeeded


def test_nexus_patent_integration_flow():
    factory = get_contract_factory("NexusPatent")
    contract = factory.deploy(args=[])

    # 1. Submit Patent Transaction
    tx_submit = contract.submit_patent(
        args=[
            "patent-int-01",
            "Photonic Neuromorphic Co-Processor",
            "Hardware & AI Accelerators",
            "Silicon photonics waveguide circuit with optical matrix-vector multiplier.",
            "https://arxiv.org/abs/2401.00001",
        ]
    ).transact()
    assert tx_execution_succeeded(tx_submit)

    # 2. Read State via .call()
    patent = contract.get_patent(args=["patent-int-01"]).call()
    assert patent["patent_id"] == "patent-int-01"
    assert patent["title"] == "Photonic Neuromorphic Co-Processor"
    assert patent["status"] == "SUBMITTED"

    # 3. Protocol Overview View
    overview = contract.get_protocol_overview().call()
    assert overview["total_patents_submitted"] == 1
