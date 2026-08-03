from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from evolex.agents.deepseek_client import HeuristicTypedExtractor
from evolex.cli import app
from evolex.graph.runner import run_pipeline_text
from evolex.nodes.entity_merge import entity_merge_node
from evolex.nodes.evolution import evolution_shadow_node
from evolex.nodes.extract import make_extract_node
from evolex.nodes.relation_merge import relation_merge_node
from evolex.nodes.schema_gap import make_schema_gap_node
from evolex.repositories.canonical import CanonicalGraphStore
from evolex.repositories.schema_store import SchemaCandidateStore
from evolex.visualization import build_dashboard


def test_joint_extraction_materializes_relations_without_second_pass(tmp_path: Path) -> None:
    result = run_pipeline_text(
        "API Gateway retries HTTP errors. API GW depends on Retry Policy.",
        pipeline="agent",
        output_dir=tmp_path,
        extractor=HeuristicTypedExtractor(),
    )

    actions = [
        item.get("selected_action") for item in result.state.get("agent_trace", [])
    ]
    assert result.state["relation_extraction_mode"] == "joint"
    assert result.relation_count == 2
    assert actions.count("relation_extract_tool") == 1
    assert result.state["joint_relation_yield"] == 2
    assert all(
        relation.get("source_relation_candidate_ids")
        for relation in result.state["relations"]
    )


def test_segment_namespacing_preserves_unique_evidence_and_endpoints() -> None:
    node = make_extract_node(HeuristicTypedExtractor())
    state = {
        "run_id": "RUN-test",
        "document_id": "DOC-test",
        "document_version": 1,
        "schema_version": "schema-test",
        "segments": [
            {"segment_id": "seg-0001", "text": "API Gateway retries HTTP errors."},
            {"segment_id": "seg-0002", "text": "API GW depends on Retry Policy."},
        ],
    }

    result = node(state)

    evidence_ids = [item["evidence_id"] for item in result["evidence_spans"]]
    assert len(evidence_ids) == len(set(evidence_ids))
    assert all(value.startswith("seg-") for value in evidence_ids)
    assert all(item["segment_id"] for item in result["evidence_spans"])
    claim_ids = [item["claim_id"] for item in result["claim_candidates"]]
    assert len(claim_ids) == len(set(claim_ids))
    assert all(value.startswith("seg-") for value in claim_ids)
    mention_ids = {item["mention_id"] for item in result["mentions"]}
    assert all(
        item["subject_mention_id"] in mention_ids
        and item["object_mention_id"] in mention_ids
        for item in result["relation_candidates"]
    )


def test_entity_merge_agent_is_same_type_and_reversible() -> None:
    state = {
        "entities": [
            {
                "entity_id": "ent-1",
                "canonical_text": "API Gateway",
                "type": "tool",
                "source_mention_ids": ["seg-1:m1"],
                "source_mention_indices": [0],
                "source_atom_indices": [],
                "segment_ids": ["seg-1"],
                "aliases": ["API Gateway"],
                "merged_count": 1,
                "confidence": 0.8,
            },
            {
                "entity_id": "ent-2",
                "canonical_text": "API GW",
                "type": "tool",
                "source_mention_ids": ["seg-2:m1"],
                "source_mention_indices": [1],
                "source_atom_indices": [],
                "segment_ids": ["seg-2"],
                "aliases": ["API GW"],
                "merged_count": 1,
                "confidence": 0.7,
            },
            {
                "entity_id": "ent-3",
                "canonical_text": "API GW",
                "type": "process",
                "source_mention_ids": ["seg-3:m1"],
                "source_mention_indices": [2],
                "source_atom_indices": [],
                "segment_ids": ["seg-3"],
                "aliases": ["API GW"],
                "merged_count": 1,
                "confidence": 0.7,
            },
        ],
        "entity_decisions": [
            {
                "mention_id": "seg-1:m1",
                "target_entity_id": "ent-1",
                "decision": "CREATE_CANDIDATE",
            },
            {
                "mention_id": "seg-2:m1",
                "target_entity_id": "ent-2",
                "decision": "CREATE_CANDIDATE",
            },
            {
                "mention_id": "seg-3:m1",
                "target_entity_id": "ent-3",
                "decision": "CREATE_CANDIDATE",
            },
        ],
    }

    result = entity_merge_node(state)

    assert len(result["entities"]) == 2
    tool = next(item for item in result["entities"] if item["type"] == "tool")
    assert set(tool["source_entity_ids"]) == {"ent-1", "ent-2"}
    assert set(tool["aliases"]) == {"API Gateway", "API GW"}
    assert any(
        item["status"] == "accepted"
        and item["evidence_contract"]["same_type"]
        for item in result["entity_merge_proposals"]
    )


def test_relation_merge_agent_aggregates_predicate_alias_and_evidence() -> None:
    result = relation_merge_node(
        {
            "relations": [
                {
                    "relation_id": "r1",
                    "subject_entity_id": "e1",
                    "predicate": "requires",
                    "object_entity_id": "e2",
                    "evidence": "A requires B.",
                    "evidence_ids": ["ev1"],
                    "segment_ids": ["seg1"],
                    "confidence": 0.7,
                },
                {
                    "relation_id": "r2",
                    "subject_entity_id": "e1",
                    "predicate": "depends_on",
                    "object_entity_id": "e2",
                    "evidence": "A depends on B.",
                    "evidence_ids": ["ev2"],
                    "segment_ids": ["seg2"],
                    "confidence": 0.8,
                },
            ]
        }
    )

    assert len(result["relations"]) == 1
    relation = result["relations"][0]
    assert relation["predicate"] == "depends_on"
    assert set(relation["evidence_ids"]) == {"ev1", "ev2"}
    assert set(relation["source_relation_ids"]) == {"r1", "r2"}
    assert len(relation["source_assertions"]) == 2
    assert result["relation_identity_hypotheses"][0]["reversible"] is True


def test_relation_merge_preserves_distinct_qualified_assertions() -> None:
    result = relation_merge_node(
        {
            "relations": [
                {
                    "relation_id": "r-2025",
                    "subject_entity_id": "e1",
                    "predicate": "has_owner",
                    "object_entity_id": "e2",
                    "qualifiers": {"valid_year": 2025},
                    "evidence": "A was owned by B in 2025.",
                    "evidence_ids": ["ev-2025"],
                    "segment_ids": ["seg-2025"],
                    "confidence": 0.8,
                },
                {
                    "relation_id": "r-2026",
                    "subject_entity_id": "e1",
                    "predicate": "has_owner",
                    "object_entity_id": "e2",
                    "qualifiers": {"valid_year": 2026},
                    "evidence": "A was owned by B in 2026.",
                    "evidence_ids": ["ev-2026"],
                    "segment_ids": ["seg-2026"],
                    "confidence": 0.9,
                },
            ]
        }
    )

    assert len(result["relations"]) == 2
    assert len(
        {item["qualifiers_hash"] for item in result["relations"]}
    ) == 2
    assert {
        item["qualifiers"]["valid_year"] for item in result["relations"]
    } == {2025, 2026}
    assert all(
        len(item["source_assertions"]) == 1
        for item in result["relations"]
    )


def test_cli_preserves_agent_pipeline_alias(monkeypatch) -> None:
    captured = {}
    monkeypatch.setattr(
        "evolex.cli.run_repl",
        lambda **kwargs: captured.update(kwargs),
    )

    result = CliRunner().invoke(app, ["chat", "--pipeline", "agent"])

    assert result.exit_code == 0
    assert captured["pipeline"] == "agent"


def test_canonical_registry_merges_aliases_across_runs(tmp_path: Path) -> None:
    run_pipeline_text(
        "API Gateway retries HTTP errors.",
        pipeline="agent",
        output_dir=tmp_path,
        extractor=HeuristicTypedExtractor(),
    )
    run_pipeline_text(
        "API GW retries HTTP failures.",
        pipeline="agent",
        output_dir=tmp_path,
        extractor=HeuristicTypedExtractor(),
    )

    with CanonicalGraphStore(tmp_path / "canonical") as store:
        snapshot = store.snapshot()
        history = store.history()

    assert len(snapshot["entities"]) == 2
    assert len(snapshot["relations"]) == 1
    assert len(snapshot["relation_evidence"]) == 2
    assert len(history) == 2


def test_shadow_gate_derives_minimal_compensation_from_failed_contract() -> None:
    state = {
        "canonical_baseline": {
            "entities": [],
            "relations": [],
            "relation_evidence": [],
        },
        "graph_patch": {
            "operations": [
                {
                    "operation_id": "op-e-1",
                    "object_type": "entity",
                    "object_id": "ce-1",
                    "after": {
                        "canonical_id": "ce-1",
                        "canonical_text": "A",
                        "entity_type": "entity",
                        "aliases": ["A"],
                        "confidence": 0.8,
                    },
                    "evidence_contract": {"provenance_complete": False},
                },
                {
                    "operation_id": "op-r-1",
                    "object_type": "relation",
                    "object_id": "cr-1",
                    "after": {
                        "canonical_relation_id": "cr-1",
                        "subject_id": "ce-1",
                        "predicate": "related_to",
                        "object_id": "ce-missing",
                        "confidence": 0.7,
                    },
                    "depends_on_entity_ids": ["ce-1", "ce-missing"],
                    "evidence_contract": {"provenance_complete": True},
                    "evidence": [{"evidence_uid": "ev-1"}],
                },
            ]
        },
    }

    result = evolution_shadow_node(state)["shadow_evaluation"]

    assert set(result["compensation_operation_ids"]) == {"op-e-1", "op-r-1"}
    assert result["passed_after_compensation"] is True
    assert len(result["minimal_compensation_patch"]) == 2


def test_promoted_schema_changes_gap_detection(tmp_path: Path) -> None:
    schema_dir = tmp_path / "schema"
    store = SchemaCandidateStore(schema_dir)
    for index in range(3):
        store.put_proposal(
            {
                "proposal_id": f"scp-{index}",
                "proposal_type": "new_relation",
                "name": "supports_feature",
                "description": "",
                "supporting_texts": [f"evidence-{index}"],
                "evidence_spans": [f"seg-{index}"],
                "source_run_ids": [f"run-{index}"],
                "source_document_ids": [f"doc-{index}"],
                "schema_version": "base",
            }
        )
    proposal = store.get_proposal_by_name("supports_feature")
    assert proposal is not None
    store.promote_proposal(
        proposal["proposal_id"],
        target_schema_version="schema-0.2.0",
        reason="test gate passed",
    )

    gap = make_schema_gap_node(schema_dir)(
        {
            "run_id": "run-new",
            "claim_candidates": [
                {
                    "subject": "A",
                    "predicate": "supports_feature",
                    "object": "B",
                }
            ],
        }
    )

    assert gap["schema_version"] == "schema-0.2.0"
    assert gap["unresolved_terms"] == []


def test_dashboard_contains_graph_evolution_and_agent_trace(tmp_path: Path) -> None:
    result = run_pipeline_text(
        "API Gateway retries HTTP errors.",
        pipeline="agent",
        output_dir=tmp_path,
        extractor=HeuristicTypedExtractor(),
    )
    output = build_dashboard(
        output_path=tmp_path / "dashboard.html",
        canonical_dir=tmp_path / "canonical",
        registry_dir=tmp_path / "registry",
        schema_dir=tmp_path / "schema_candidates",
    )
    html = output.read_text(encoding="utf-8")

    assert "Knowledge Graph Evolution Control Plane" in html
    assert "Agent Decision Trace" in html
    assert "API Gateway" in html
    assert "evolution_commit_tool" in html
    assert "因果验证凭证与提交清单" in html
    assert "certificate_id" in html
    assert "冻结影响域摘要" in html
    assert "frozen_impact_domain_hash" in html
    assert "反事实检查数" in html
    assert "反事实原因操作" in html
    assert "solver mode / optimality" in html
    assert "commit_manifest_hash" in html
    assert "accepted_operations_hash" in html
    assert "N/A" in html
    assert "表示字段不存在" in html
    assert "不推断额外的 run_id–version_id 严格关联" in html

    certificate = result.state["shadow_evaluation"][
        "causal_validation_certificate"
    ]
    commit = result.state["evolution_commit"]
    assert certificate["certificate_id"] in html
    assert certificate["frozen_impact_domain_hash"] in html
    assert commit["commit_manifest_hash"] in html
    assert commit["accepted_operations_hash"] in html


def test_version_rollback_appends_compensation_without_deleting_history(
    tmp_path: Path,
) -> None:
    result = run_pipeline_text(
        "API Gateway retries HTTP errors.",
        pipeline="agent",
        output_dir=tmp_path,
        extractor=HeuristicTypedExtractor(),
    )
    version_id = result.state["canonical_version_id"]

    with CanonicalGraphStore(tmp_path / "canonical") as store:
        compensation = store.rollback_version(version_id, "test rollback")
        snapshot = store.snapshot()
        history = store.history()

    assert compensation["operation_count"] == 3
    assert snapshot["entities"] == []
    assert snapshot["relations"] == []
    assert snapshot["relation_evidence"] == []
    assert len(history) == 2
