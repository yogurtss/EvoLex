"""E2E test for Phase 3 pipeline using DeepSeek v4 flash.

Usage:
    export DEEPSEEK_API_KEY=sk-...
    python scripts/e2e_test.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from evolex.graph.runner import run_pipeline_text
from evolex.agents.deepseek_client import DeepSeekExtractor

API_KEY = os.environ.get("DEEPSEEK_API_KEY")
if not API_KEY:
    api_file = Path(__file__).parent.parent / "api.txt"
    if api_file.exists():
        API_KEY = api_file.read_text(encoding="utf-8").strip()
if not API_KEY:
    print("ERROR: DEEPSEEK_API_KEY not set and api.txt not found.")
    sys.exit(1)

TEST_DOC = Path(__file__).parent.parent / "tests" / "data" / "semiconductor_test.md"
if not TEST_DOC.exists():
    print(f"ERROR: Test doc not found at {TEST_DOC}")
    sys.exit(1)

OUTPUT_DIR = Path("/tmp/evolex_e2e")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def main():
    doc_text = TEST_DOC.read_text(encoding="utf-8")
    print(f"Document: {len(doc_text)} chars from {TEST_DOC.name}")

    extractor = DeepSeekExtractor(
        api_key=API_KEY,
        model="deepseek-v4-flash",
        on_event=lambda stage, msg: print(f"  [{stage}] {msg[:80]}"),
    )

    print("\nRunning Phase 3 pipeline...")
    result = run_pipeline_text(
        document_text=doc_text,
        pipeline="phase3",
        output_dir=OUTPUT_DIR,
        extractor=extractor,
        document_version=2,
    )

    print(f"\n{'='*60}")
    print("Phase 3 E2E Test Results")
    print(f"{'='*60}")
    print(f"Status:        {result.status}")
    print(f"Claims:        {result.claim_count}")
    print(f"Evidence:      {result.evidence_count}")
    print(f"Entities:      {result.entity_count}")
    print(f"Relations:     {result.relation_count}")
    print(f"Policy Action: {result.policy_action}")
    print(f"Candidate:     {result.candidate_output_path}")
    print(f"Publish:       {result.publish_output_path}")

    state = result.state

    # Policy decisions
    if state.get("policy_decisions"):
        print("\nPolicy Decisions:")
        for d in state["policy_decisions"]:
            print(f"  action={d.get('action')} risk={d.get('risk_level')}")
            print(f"  reasons={d.get('reasons')}")

    # Entity decisions summary
    if state.get("entity_decisions"):
        decides: dict[str, int] = {}
        for d in state["entity_decisions"]:
            decides[d["decision"]] = decides.get(d["decision"], 0) + 1
        print(f"\nEntity Decisions: {decides}")

    # Schema proposals
    if state.get("schema_proposals"):
        print(f"\nSchema Proposals: {len(state['schema_proposals'])}")
        for p in state["schema_proposals"][:5]:
            print(f"  [{p['proposal_type']}] {p['name']} (x{p['occurrence_count']})")

    # LLM usage
    if state.get("llm_call_count", 0) > 0:
        print(f"\nLLM Calls: {state['llm_call_count']}")

    # Version fields
    print(f"\nVersion Info:")
    print(f"  document_version: {state.get('document_version')}")
    print(f"  schema_version:   {state.get('schema_version')}")
    print(f"  policy_version:   {state.get('policy_version')}")

    # Verify key assertions
    assert "policy_decisions" in state, "Missing policy_decisions"
    assert "entity_decisions" in state or "schema_proposals" in state, \
        "Missing entity_decisions or schema_proposals"

    # Verify claim-to-evidence linkage
    evidence_ids = {ev.get("evidence_id") for ev in state.get("evidence_spans", [])}
    for claim in state.get("claim_candidates", []):
        for eid in claim.get("evidence_ids", []):
            assert eid in evidence_ids, \
                f"Claim {claim.get('claim_id')} references missing evidence {eid}"
    print(f"\n✓ All {result.claim_count} claims link to valid evidence")

    print(f"\n{'='*60}")
    print("✓ E2E TEST PASSED")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
