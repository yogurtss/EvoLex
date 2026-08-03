"""End-to-end acceptance test using DeepSeek v4 flash.

Usage:
    DEEPSEEK_API_KEY=sk-... python -m pytest tests/test_e2e_deepseek.py -v

Or with the API key file:
    DEEPSEEK_API_KEY=$(cat api.txt) python -m pytest tests/test_e2e_deepseek.py -v
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from evolex.agents.deepseek_client import DeepSeekExtractor

pytestmark = [
    pytest.mark.skipif(
        not os.environ.get("DEEPSEEK_API_KEY"),
        reason="DEEPSEEK_API_KEY not set",
    ),
    pytest.mark.slow,
]

TEST_DOC = Path(__file__).parent / "data" / "semiconductor_test.md"


def test_phase3_deepseek_smoke(tmp_path: Path) -> None:
    """Run Phase 3 pipeline with DeepSeek v4 flash on a semiconductor document."""
    from evolex.graph.runner import run_pipeline_text

    doc_text = TEST_DOC.read_text(encoding="utf-8")
    api_key = os.environ["DEEPSEEK_API_KEY"]

    extractor = DeepSeekExtractor(
        api_key=api_key,
        model="deepseek-v4-flash",
    )

    result = run_pipeline_text(
        document_text=doc_text,
        pipeline="phase3",
        output_dir=tmp_path,
        extractor=extractor,
        document_version=2,
    )

    # Core assertions
    assert result.status in ("published", "candidate", "quarantined"), \
        f"Unexpected final status: {result.status}"
    assert result.claim_count >= 0, f"Unexpected claim count: {result.claim_count}"
    assert result.entity_count >= 0, f"Unexpected entity count: {result.entity_count}"
    assert result.relation_count >= 0, f"Unexpected relation count: {result.relation_count}"

    state = result.state

    # Check state has Phase 3 fields
    assert "policy_decisions" in state
    assert "entity_decisions" in state or "schema_proposals" in state

    # Check version fields
    assert state.get("document_version") == 2
    assert state.get("schema_version") == "evolex-base-0.1.0"
    assert state.get("policy_version") == "policy-0.1.0"

    # Print summary for inspection
    print(f"\n{'='*60}")
    print("Phase 3 E2E Test Results")
    print(f"{'='*60}")
    print(f"Status:        {result.status}")
    print(f"Claims:        {result.claim_count}")
    print(f"Evidence:      {result.evidence_count}")
    print(f"Entities:      {result.entity_count}")
    print(f"Relations:     {result.relation_count}")
    print(f"Policy Action: {result.policy_action}")

    if state.get("policy_decisions"):
        for d in state["policy_decisions"]:
            print(f"  Policy: action={d.get('action')} reasons={d.get('reasons')}")

    if state.get("entity_decisions"):
        decides: dict[str, int] = {}
        for d in state["entity_decisions"]:
            decides[d["decision"]] = decides.get(d["decision"], 0) + 1
        print(f"  Entity decisions: {decides}")

    if state.get("schema_proposals"):
        print(f"  Schema proposals: {len(state['schema_proposals'])}")
        for p in state["schema_proposals"][:3]:
            print(f"    [{p['proposal_type']}] {p['name']}")

    if state.get("llm_call_count", 0) > 0:
        print(f"  LLM calls: {state['llm_call_count']}")

    print(f"{'='*60}\n")


def test_phase3_deepseek_claim_evidence_link(tmp_path: Path) -> None:
    """Claims extracted by DeepSeek link to existing evidence spans."""
    from evolex.graph.runner import run_pipeline_text

    doc_text = TEST_DOC.read_text(encoding="utf-8")
    extractor = DeepSeekExtractor(
        api_key=os.environ["DEEPSEEK_API_KEY"],
        model="deepseek-v4-flash",
    )

    result = run_pipeline_text(
        document_text=doc_text[:2000],  # first section
        pipeline="phase3",
        output_dir=tmp_path,
        extractor=extractor,
        document_version=1,
    )

    state = result.state
    evidence_ids = {ev.get("evidence_id") for ev in state.get("evidence_spans", [])}

    for claim in state.get("claim_candidates", []):
        for eid in claim.get("evidence_ids", []):
            assert eid in evidence_ids, \
                f"Claim {claim.get('claim_id')} references missing evidence {eid}"


def test_phase3_deepseek_policy_produces_decision(tmp_path: Path) -> None:
    """DeepSeek extraction followed by policy node produces a decision."""
    from evolex.graph.runner import run_pipeline_text

    doc_text = "Deep reactive ion etching (DRIE) at 40mTorr achieves 5µm/min etch rate in silicon."
    extractor = DeepSeekExtractor(
        api_key=os.environ["DEEPSEEK_API_KEY"],
        model="deepseek-v4-flash",
    )

    result = run_pipeline_text(
        document_text=doc_text,
        pipeline="phase3",
        output_dir=tmp_path,
        extractor=extractor,
        document_version=1,
    )

    assert len(result.state.get("policy_decisions", [])) >= 1
    decision = result.state["policy_decisions"][0]
    assert "action" in decision
    assert "reasons" in decision
