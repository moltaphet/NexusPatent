"""Shared fixtures and mock helpers for NexusPatent direct-mode tests."""

import json

CONTRACT_PATH = "src/nexus_patent.py"
PATENT_PROMPT_PATTERN = r".*impartial patent examiner.*"


def mock_ai_novelty(
    direct_vm,
    decision: str = "PATENTABLE",
    confidence: int = 90,
    novelty: int = 95,
    inventive: int = 90,
    collision: int = 10,
    rationale: str = "Invention is highly novel and non-obvious.",
):
    """Mock the Multi-LLM Quorum call with structured patent metrics."""
    direct_vm.mock_llm(
        PATENT_PROMPT_PATTERN,
        json.dumps(
            {
                "decision": decision,
                "confidence": confidence,
                "novelty": novelty,
                "inventive": inventive,
                "collision": collision,
                "rationale": rationale,
            }
        ),
    )


def mock_literature_oracle(direct_vm, payload=None, status: int = 200):
    """Mock the Web2 literature / patent search API response."""
    body = json.dumps(payload if payload is not None else {"status": "clean", "citations": []})
    direct_vm.mock_web(r".*", {"status": status, "body": body})
