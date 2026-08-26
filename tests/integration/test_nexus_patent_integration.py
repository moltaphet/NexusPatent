"""GenLayer Integration Test Suite for NexusPatent."""

import pytest
from gltest import get_contract_factory
from gltest.assertions import tx_execution_succeeded


def test_nexus_patent_integration_flow():
    factory = get_contract_factory("NexusPatent")
    contract = factory.deploy(args=[])

    # 1. Register Invention Transaction
    tx_reg = contract.register_invention(
        args=[
            "pat-int-01",
            "SOFTWARE_AI",
            "sha256:optical-matrix-multiplier",
            "Silicon photonics waveguide circuit with optical matrix-vector multiplier.",
            100000 * 10**18,
        ]
    ).transact()
    assert tx_execution_succeeded(tx_reg)

    # 2. Read State via .call()
    inv = contract.get_invention(args=["pat-int-01"]).call()
    assert inv["invention_id"] == "pat-int-01"
    assert inv["status"] == "REGISTERED"

    # 3. Protocol Overview View
    overview = contract.get_protocol_overview().call()
    assert overview["total_inventions"] == 1
