"""Shared fixtures and mock helpers for NexusPatent direct-mode tests."""

import json

CONTRACT_PATH = "src/nexus_patent.py"
PATENT_PROMPT_PATTERN = r".*impartial Patent Examiner and DeSci Prior-Art Auditor.*"


def mock_ai_novelty(
    direct_vm,
    decision: str = "APPROVED",
    novelty_score: int = 95,
    inventive_step_score: int = 90,
    citation_collision_rate: int = 10,
    prior_art_collision: bool = False,
    rationale: str = "Invention is highly novel and non-obvious with zero prior art collisions.",
    confidence: int = 90,
    novelty: int = None,
    inventive: int = None,
    collision: int = None,
):
    """Mock the Multi-LLM Quorum call with structured patent metrics."""
    n_score = novelty if novelty is not None else novelty_score
    i_score = inventive if inventive is not None else inventive_step_score
    c_score = collision if collision is not None else citation_collision_rate

    direct_vm.mock_llm(
        PATENT_PROMPT_PATTERN,
        json.dumps(
            {
                "decision": decision,
                "novelty_score": n_score,
                "inventive_step_score": i_score,
                "citation_collision_rate": c_score,
                "prior_art_collision": prior_art_collision,
                "rationale": rationale,
            }
        ),
    )


def mock_literature_oracle(direct_vm, payload=None, status: int = 200):
    """Mock the Web2 literature / patent search API response."""
    body = json.dumps(payload if payload is not None else {"status": "ok", "total_citations": 4, "prior_art_collision": False})
    direct_vm.mock_web(r".*", {"status": status, "body": body})
