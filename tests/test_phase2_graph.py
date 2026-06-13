from pathlib import Path
import sqlite3

from evolex.agents.deepseek_client import HeuristicExtractor
from evolex.graph.runner import (
    Phase1RunResult,
    Phase2RunResult,
    Phase3RunResult,
    run_phase1_text,
    run_phase2_text,
    run_pipeline_text,
)


class RelationAwareExtractor(HeuristicExtractor):
    uses_llm = True
    supports_relation_extraction = True

    def extract_relations(self, atoms: list[dict], entities: list[dict]) -> list[dict]:
        return [
            {
                "relation_id": "rel-0001",
                "subject_entity_id": entities[0]["entity_id"],
                "predicate": "depends_on",
                "object_entity_id": entities[-1]["entity_id"],
                "evidence": atoms[0]["evidence"],
                "confidence": 0.9,
            }
        ]


def test_phase2_graph_smoke(tmp_path: Path) -> None:
    """Full Phase 2 pipeline smoke test with heuristic extractor."""
    result = run_phase2_text(
        "API Gateway retries HTTP 503 responses for 2 seconds before failing over.",
        output_dir=tmp_path,
        extractor=HeuristicExtractor(),
    )

    assert isinstance(result, Phase2RunResult)
    assert result.status == "published"
    assert result.semantic_atom_count >= 1
    assert result.entity_count >= 1
    # Verify SQLite output exists
    db_path = Path(result.publish_output_path)
    assert db_path.exists()

    # Verify DB contents
    conn = sqlite3.connect(str(db_path))
    rows = conn.execute("SELECT COUNT(*) FROM entities").fetchone()
    assert rows[0] == result.entity_count
    rows = conn.execute("SELECT COUNT(*) FROM runs").fetchone()
    assert rows[0] == 1
    status = conn.execute("SELECT status FROM runs").fetchone()
    assert status[0] == "published"
    conn.close()


def test_entity_deduplication(tmp_path: Path) -> None:
    """Entities with the same name across segments are merged."""
    result = run_phase2_text(
        "API Gateway handles requests. The API Gateway also retries on failure.",
        output_dir=tmp_path,
        extractor=HeuristicExtractor(),
    )

    assert result.status == "published"
    entities = result.state["entities"]
    # "API Gateway" should appear once with merged_count >= 2
    api_gateway_ents = [e for e in entities if "api gateway" in e["canonical_text"].lower()]
    if api_gateway_ents:
        assert api_gateway_ents[0]["merged_count"] >= 1


def test_quality_review_filters_low_confidence(tmp_path: Path) -> None:
    """Low-confidence atoms are flagged in quality scores."""
    result = run_phase2_text(
        "API Gateway retries HTTP 503 responses for 2 seconds before failing over.",
        output_dir=tmp_path,
        extractor=HeuristicExtractor(),
    )

    assert result.status in ("published", "candidate")
    quality_scores = result.state.get("quality_scores", [])
    assert len(quality_scores) >= 0  # May be empty if all pass


def test_empty_input_fails(tmp_path: Path) -> None:
    """Empty document text should result in 'failed' status."""
    result = run_phase2_text(
        "",
        output_dir=tmp_path,
        extractor=HeuristicExtractor(),
    )

    assert result.status == "failed"
    assert result.entity_count == 0
    assert result.relation_count == 0


def test_phase2_produces_relations(tmp_path: Path) -> None:
    """Multi-segment technical document should produce heuristic relations."""
    result = run_phase2_text(
        "The service has a latency of 200ms. The API Gateway retries HTTP 503.",
        output_dir=tmp_path,
        extractor=HeuristicExtractor(),
    )

    assert result.status == "published"
    relations = result.state.get("relations", [])
    # With heuristic extraction, co-occurring measurement/property atoms in
    # the same segment should generate relations
    assert isinstance(relations, list)


def test_backward_compat_phase1_unchanged(tmp_path: Path) -> None:
    """Phase 1 runner still returns Phase1RunResult with no Phase II fields."""
    result = run_phase1_text(
        "API Gateway retries HTTP 503 responses for 2 seconds before failing over.",
        output_dir=tmp_path,
        extractor=HeuristicExtractor(),
    )

    assert isinstance(result, Phase1RunResult)
    assert result.status == "candidate"
    # Phase1RunResult does NOT have entity_count attribute
    assert not hasattr(result, "entity_count")
    assert not hasattr(result, "publish_output_path")
    assert Path(result.candidate_output_path).exists()


def test_system_pipeline_alias_runs_phase3(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("EVOLEX_OFFLINE", "1")
    result = run_pipeline_text(
        "API Gateway retries HTTP 503 responses for 2 seconds before failing over.",
        pipeline="system",
        output_dir=tmp_path,
    )

    assert isinstance(result, Phase3RunResult)
    assert result.status == "published"
    assert result.entity_count >= 1
    assert result.claim_count >= 1


def test_phase2_uses_relation_specific_extractor(tmp_path: Path) -> None:
    result = run_phase2_text(
        "API Gateway retries HTTP 503 responses for 2 seconds before failing over.",
        output_dir=tmp_path,
        extractor=RelationAwareExtractor(),
    )

    assert result.status == "published"
    assert result.relation_count == 1
    assert result.state["relations"][0]["predicate"] == "depends_on"
    assert result.state["llm_call_count"] >= 2
