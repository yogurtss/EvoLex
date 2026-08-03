from __future__ import annotations

import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path

import pytest

from evolex.agentic.agents import AgentProposal
from evolex.agentic.controller import (
    AgenticKGRunner,
    _completed_tools,
    _prepare_tool_execution,
)
from evolex.agentic.metrics import graph_metrics
from evolex.agents.deepseek_client import HeuristicTypedExtractor
from evolex.graph.runner import resume_thread, run_pipeline_text
from evolex.nodes.entity_merge import entity_merge_node
from evolex.nodes.entity_resolve import entity_resolve_node
from evolex.nodes.evolution import (
    evolution_consensus_node,
    evolution_shadow_node,
    make_evolution_commit_node,
)
from evolex.nodes.policy_node import policy_node
from evolex.nodes.publish import make_publish_node
from evolex.nodes.registry_finalize import make_registry_finalize_node
from evolex.nodes.relation_extract import make_relation_extract_node
from evolex.nodes.schema_gap import make_schema_gap_node
from evolex.nodes.schema_proposer import schema_proposer_node
from evolex.nodes.validate import validate_node
from evolex.repositories.canonical import CanonicalGraphStore
from evolex.repositories.evaluation import CheckpointStore
from evolex.repositories.evaluation import governance_snapshot
from evolex.repositories.schema_store import SchemaCandidateStore


def _entity(entity_id: str, text: str, segment: str) -> dict:
    return {
        "entity_id": entity_id,
        "canonical_text": text,
        "type": "entity",
        "source_mention_ids": [f"{segment}:m1"],
        "source_mention_indices": [0],
        "source_atom_indices": [],
        "segment_ids": [segment],
        "aliases": [text],
        "merged_count": 1,
        "confidence": 0.8,
    }


def _canonical_entity_op(
    operation_id: str,
    text: str,
    confidence: float,
    mention_uid: str,
) -> dict:
    return {
        "operation_id": operation_id,
        "action": "upsert_entity",
        "object_type": "entity",
        "object_id": "ce-1",
        "after": {
            "canonical_id": "ce-1",
            "canonical_text": text,
            "entity_type": "entity",
            "confidence": confidence,
            "aliases": [text],
        },
        "mentions": [
            {
                "mention_uid": mention_uid,
                "mention_text": text,
                "segment_id": mention_uid,
                "evidence_text": text,
            }
        ],
        "evidence_contract": {},
    }


def _canonical_relation_op(
    operation_id: str,
    confidence: float,
    evidence_uid: str,
) -> dict:
    return {
        "operation_id": operation_id,
        "action": "upsert_relation",
        "object_type": "relation",
        "object_id": "cr-1",
        "after": {
            "canonical_relation_id": "cr-1",
            "subject_id": "ce-subject",
            "predicate": "uses",
            "object_id": "ce-object",
            "qualifiers_hash": "",
            "confidence": confidence,
        },
        "evidence": [
            {
                "evidence_uid": evidence_uid,
                "evidence_id": evidence_uid,
                "segment_id": evidence_uid,
                "evidence_text": evidence_uid,
                "confidence": confidence,
            }
        ],
        "evidence_contract": {},
    }


def test_entity_merge_preserves_distinct_unicode_entities() -> None:
    result = entity_merge_node(
        {
            "entities": [
                _entity("e1", "知识图谱", "s1"),
                _entity("e2", "大语言模型", "s2"),
            ]
        }
    )

    assert len(result["entities"]) == 2
    assert result["entity_merge_proposals"] == []


def test_resolver_applies_curated_alias_and_unit_synonyms() -> None:
    result = entity_resolve_node(
        {
            "mentions": [
                {
                    "mention_id": "m1",
                    "text": "API GW",
                    "mention_type": "tool",
                    "confidence": 0.8,
                },
                {
                    "mention_id": "m2",
                    "text": "API Gateway",
                    "mention_type": "tool",
                    "confidence": 0.8,
                },
                {
                    "mention_id": "m3",
                    "text": "msec",
                    "mention_type": "measurement",
                    "confidence": 0.8,
                },
                {
                    "mention_id": "m4",
                    "text": "milliseconds",
                    "mention_type": "measurement",
                    "confidence": 0.8,
                },
            ]
        }
    )

    assert len(result["entities"]) == 2
    assert result["mention_entity_map"]["m1"] == result["mention_entity_map"]["m2"]
    assert result["mention_entity_map"]["m3"] == result["mention_entity_map"]["m4"]
    alias_sets = [set(item["aliases"]) for item in result["entities"]]
    assert {"API GW", "API Gateway"} in alias_sets
    assert {"msec", "milliseconds"} in alias_sets


def test_entity_merge_uses_complete_link_to_block_transitive_overmerge() -> None:
    result = entity_merge_node(
        {
            "entities": [
                _entity("e1", "alpha beta gamma delta", "s1"),
                _entity("e2", "alpha beta gamma delta epsilon", "s2"),
                _entity("e3", "beta gamma delta epsilon", "s3"),
            ]
        }
    )

    assert len(result["entities"]) == 2
    assert any(
        proposal["status"] == "held"
        and proposal["reason"] == "blocked_by_complete_link_cluster_constraint"
        for proposal in result["entity_merge_proposals"]
    )


def test_relation_endpoint_collapse_is_an_auditable_failure() -> None:
    node = make_relation_extract_node(HeuristicTypedExtractor())
    result = node(
        {
            "entities": [_entity("e1", "API Gateway", "s1")],
            "semantic_atoms": [],
            "mention_entity_map": {"s1:m1": "e1", "s1:m2": "e1"},
            "relation_candidates": [
                {
                    "relation_candidate_id": "rc1",
                    "subject_mention_id": "s1:m1",
                    "predicate": "related_to",
                    "object_mention_id": "s1:m2",
                    "endpoint_validation_status": "valid",
                }
            ],
        }
    )

    assert result["relations"] == []
    assert result["relation_endpoint_failures"][0]["errors"] == [
        "canonical_endpoint_collapse"
    ]
    assert any("none had two resolved endpoints" in item for item in result["warnings"])


def test_claim_cannot_reference_evidence_removed_by_validation() -> None:
    result = validate_node(
        {
            "semantic_atoms": [],
            "claim_candidates": [
                {
                    "claim_id": "claim-1",
                    "subject": "A",
                    "predicate": "uses",
                    "object": "B",
                    "evidence_ids": ["ev-invalid"],
                }
            ],
            "evidence_spans": [
                {
                    "evidence_id": "ev-invalid",
                    "document_id": "doc-1",
                }
            ],
            "relation_candidates": [
                {
                    "relation_candidate_id": "rc-invalid",
                    "subject_mention_id": "m1",
                    "predicate": "uses",
                    "object_mention_id": "m2",
                    "evidence_ids": ["ev-invalid"],
                }
            ],
            "status": "running",
        }
    )

    assert result["claim_candidates"] == []
    assert result["evidence_spans"] == []
    assert result["relation_candidates"] == []
    assert result["relation_evidence_failures"] == [
        {
            "relation_candidate_id": "rc-invalid",
            "errors": ["invalid_or_missing_evidence_reference"],
            "missing_fields": [],
            "invalid_evidence_ids": ["ev-invalid"],
        }
    ]
    assert result["status"] == "quarantined"
    claim_result = next(
        item for item in result["validation_results"] if "claim_index" in item
    )
    assert claim_result["has_evidence"] is False


def test_schema_is_pinned_for_the_entire_run(tmp_path: Path) -> None:
    store = SchemaCandidateStore(tmp_path)
    pinned = store.get_active_schema()
    store.put_proposal(
        {
            "proposal_id": "scp-pin",
            "proposal_type": "new_relation",
            "name": "supports_feature",
            "source_run_ids": ["run-1"],
            "source_document_ids": ["doc-1"],
            "schema_version": pinned["version_id"],
        }
    )
    store.promote_proposal(
        "scp-pin",
        target_schema_version="schema-after-run-start",
        reason="test",
    )

    result = make_schema_gap_node(tmp_path)(
        {
            "active_schema": pinned,
            "schema_version": pinned["version_id"],
            "claim_candidates": [
                {
                    "subject": "A",
                    "predicate": "supports_feature",
                    "object": "B",
                }
            ],
        }
    )

    assert result["schema_version"] == pinned["version_id"]
    assert result["unresolved_terms"][0]["term"] == "supports_feature"


def test_schema_gap_reuses_relation_predicate_canonicalization() -> None:
    result = make_schema_gap_node()(
        {
            "active_schema": {
                "version_id": "schema-test",
                "types": ["entity"],
                "predicates": ["depends_on"],
                "attributes": [],
            },
            "schema_version": "schema-test",
            "claim_candidates": [
                {
                    "subject": "A",
                    "predicate": "requires",
                    "object": "B",
                }
            ],
        }
    )
    assert result["unresolved_terms"] == []


def test_schema_proposer_keeps_distinct_unknown_symbols_separate() -> None:
    result = schema_proposer_node(
        {
            "run_id": "run-1",
            "document_id": "doc-1",
            "schema_version": "schema-test",
            "unresolved_terms": [
                {
                    "term": "supports",
                    "category": "predicate",
                    "context": "A supports B",
                    "evidence": ["ev-1"],
                },
                {
                    "term": "controls",
                    "category": "predicate",
                    "context": "A controls C",
                    "evidence": ["ev-2"],
                },
                {
                    "term": "Surface Roughness",
                    "category": "new_parameter",
                    "context": "roughness=2",
                    "evidence": ["ev-3"],
                },
            ],
        }
    )
    symbols = {
        (item["proposal_type"], item["name"])
        for item in result["schema_proposals"]
    }
    assert symbols == {
        ("new_relation", "supports"),
        ("new_relation", "controls"),
        ("new_attribute", "surface_roughness"),
    }


def test_schema_proposal_replay_does_not_inflate_support(tmp_path: Path) -> None:
    store = SchemaCandidateStore(tmp_path)
    first = {
        "proposal_id": "scp-repeat",
        "proposal_type": "new_relation",
        "name": "supports_feature",
        "occurrence_count": 1,
        "source_run_ids": ["run-1"],
        "source_document_ids": ["doc-1"],
    }
    store.put_proposal(first)
    store.put_proposal(first)
    store.put_proposal(
        {
            **first,
            "proposal_id": "scp-second",
            "source_run_ids": ["run-2"],
            "source_document_ids": ["doc-2"],
        }
    )

    proposal = store.get_proposal_by_name("supports_feature")
    assert proposal is not None
    assert proposal["occurrence_count"] == 2
    assert proposal["independent_document_count"] == 2


def test_concurrent_schema_observations_do_not_lose_stability_evidence(
    tmp_path: Path,
) -> None:
    schema_dir = tmp_path / "schema-observations"
    observation_count = 24

    def observe(index: int) -> None:
        SchemaCandidateStore(schema_dir).put_proposal(
            {
                "proposal_id": f"scp-concurrent-{index}",
                "proposal_type": "new_relation",
                "name": "supports_concurrently",
                "occurrence_count": 1,
                "source_run_ids": [f"run-{index}"],
                "source_document_ids": [f"doc-{index}"],
            }
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        for future in [
            executor.submit(observe, index)
            for index in range(observation_count)
        ]:
            future.result()

    proposal = SchemaCandidateStore(schema_dir).get_proposal_by_name(
        "supports_concurrently"
    )
    assert proposal is not None
    assert proposal["occurrence_count"] == observation_count
    assert proposal["independent_document_count"] == observation_count


def test_concurrent_schema_promotions_form_one_lossless_version_chain(
    tmp_path: Path,
) -> None:
    schema_dir = tmp_path / "schema"
    store = SchemaCandidateStore(schema_dir)
    for suffix in ("alpha", "beta"):
        store.put_proposal(
            {
                "proposal_id": f"scp-{suffix}",
                "proposal_type": "new_relation",
                "name": f"supports_{suffix}",
                "source_run_ids": [f"run-{suffix}"],
                "source_document_ids": [f"doc-{suffix}"],
            }
        )

    start = threading.Barrier(2)

    def promote(suffix: str) -> None:
        start.wait()
        SchemaCandidateStore(schema_dir).promote_proposal(
            f"scp-{suffix}",
            target_schema_version=f"schema-{suffix}",
            reason="concurrency regression",
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(promote, suffix) for suffix in ("alpha", "beta")]
        for future in futures:
            future.result()

    active = store.get_active_schema()
    assert {"supports_alpha", "supports_beta"} <= set(active["predicates"])


def test_schema_terminal_decision_cannot_be_overwritten(tmp_path: Path) -> None:
    promoted_store = SchemaCandidateStore(tmp_path / "promoted")
    promoted_store.put_proposal(
        {
            "proposal_id": "scp-promoted",
            "proposal_type": "new_relation",
            "name": "supports_promoted",
            "source_run_ids": ["run-promoted"],
            "source_document_ids": ["doc-promoted"],
        }
    )
    promoted_store.promote_proposal(
        "scp-promoted",
        target_schema_version="schema-promoted",
        reason="terminal transition regression",
    )
    with pytest.raises(ValueError, match="not a candidate"):
        promoted_store.block_proposal("scp-promoted", reason="stale block")
    assert promoted_store.get_proposal_by_id("scp-promoted")["status"] == "promoted"
    assert "supports_promoted" in promoted_store.get_active_schema()["predicates"]

    blocked_store = SchemaCandidateStore(tmp_path / "blocked")
    blocked_store.put_proposal(
        {
            "proposal_id": "scp-blocked",
            "proposal_type": "new_relation",
            "name": "supports_blocked",
            "source_run_ids": ["run-blocked"],
            "source_document_ids": ["doc-blocked"],
        }
    )
    blocked_store.block_proposal("scp-blocked", reason="terminal transition regression")
    with pytest.raises(ValueError, match="not a candidate"):
        blocked_store.promote_proposal(
            "scp-blocked",
            target_schema_version="schema-blocked",
            reason="stale promotion",
        )
    assert blocked_store.get_proposal_by_id("scp-blocked")["status"] == "blocked"
    assert "supports_blocked" not in blocked_store.get_active_schema()["predicates"]


def test_concurrent_schema_promote_and_block_choose_one_terminal_state(
    tmp_path: Path,
) -> None:
    schema_dir = tmp_path / "schema-terminal-race"
    store = SchemaCandidateStore(schema_dir)
    store.put_proposal(
        {
            "proposal_id": "scp-terminal-race",
            "proposal_type": "new_relation",
            "name": "supports_terminal_race",
            "source_run_ids": ["run-terminal-race"],
            "source_document_ids": ["doc-terminal-race"],
        }
    )
    start = threading.Barrier(2)

    def promote() -> str:
        start.wait()
        try:
            SchemaCandidateStore(schema_dir).promote_proposal(
                "scp-terminal-race",
                target_schema_version="schema-terminal-race",
                reason="concurrent promotion",
            )
            return "promoted"
        except ValueError:
            return "rejected"

    def block() -> str:
        start.wait()
        try:
            SchemaCandidateStore(schema_dir).block_proposal(
                "scp-terminal-race",
                reason="concurrent block",
            )
            return "blocked"
        except ValueError:
            return "rejected"

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(operation) for operation in (promote, block)]
        outcomes = [future.result() for future in futures]

    proposal = store.get_proposal_by_id("scp-terminal-race")
    assert proposal is not None
    active_contains = "supports_terminal_race" in store.get_active_schema()["predicates"]
    ledger = [
        item
        for item in store.get_promotions()
        if item["proposal_id"] == "scp-terminal-race"
    ]

    assert outcomes.count("rejected") == 1
    assert (proposal["status"], active_contains) in {
        ("promoted", True),
        ("blocked", False),
    }
    assert len(ledger) == 1
    assert ledger[0]["action"] == proposal["status"]


def test_agent_rerun_invalidates_all_downstream_artifacts() -> None:
    actions = [
        "ingest_tool",
        "profile_tool",
        "segment_tool",
        "extract_tool",
        "validate_tool",
        "candidate_store_tool",
        "entity_resolve_tool",
        "entity_merge_tool",
        "relation_extract_tool",
        "relation_merge_tool",
    ]
    state = {
        "agent_trace": [
            {"selected_action": action, "step_index": index}
            for index, action in enumerate(actions, start=1)
        ],
        "entities": [{"entity_id": "stale"}],
        "relations": [{"relation_id": "stale"}],
        "validation_results": [{"ok": True}],
        "relation_identity_hypotheses": [{"identity_hypothesis_id": "stale"}],
    }

    invalidated = _prepare_tool_execution(state, "extract_tool")

    assert "entity_resolve_tool" in invalidated
    assert "relation_merge_tool" in invalidated
    assert "entity_resolve_tool" not in _completed_tools(state)
    assert "relation_merge_tool" not in _completed_tools(state)
    assert "entities" not in state
    assert "relations" not in state
    assert state["tool_revisions"]["extract_tool"] == 1


def test_negative_utility_is_a_hard_consensus_gate() -> None:
    result = evolution_consensus_node(
        {
            "graph_patch": {
                "operations": [
                    {
                        "operation_id": "op-1",
                        "evidence_contract": {"provenance_complete": True},
                    }
                ]
            },
            "shadow_evaluation": {
                "accepted_operation_ids": ["op-1"],
                "impact_domain": {"evidence_grounded": True},
                "deterministic_replay": True,
                "non_interference_passed": True,
                "passed_after_compensation": True,
                "utility": -0.01,
            },
        }
    )

    decision = result["evolution_decision"]
    assert decision["accepted"] is False
    assert decision["decision"] == "hold"
    assert decision["quorum"] == 4


def test_multivalued_relation_is_not_scored_as_functional_conflict() -> None:
    relations = [
        {
            "subject_entity_id": "A",
            "predicate": "uses",
            "object_entity_id": "B",
        },
        {
            "subject_entity_id": "A",
            "predicate": "uses",
            "object_entity_id": "C",
        },
    ]
    assert graph_metrics({"relations": relations})["conflict_score"] == 0.0

    relations[0]["predicate"] = "has_owner"
    relations[1]["predicate"] = "has_owner"
    assert graph_metrics({"relations": relations})["conflict_score"] == 1.0


def test_policy_records_normalized_risk_level_for_governance_gate() -> None:
    result = policy_node(
        {
            "validation_results": [{"ok": True}],
            "critic_results": [{"verdict": "approved"}],
            "claim_candidates": [{"claim_id": "c1"}],
            "evidence_spans": [{"evidence_id": "e1"}],
            "schema_proposals": [{"proposal_type": "type_merge"}],
        }
    )
    decision = result["policy_decisions"][0]
    governance = governance_snapshot(
        schema_proposals=[],
        policy_decisions=[{"decision": decision}],
    )
    assert decision["change_type"] == "type_merge"
    assert decision["risk_level"] == "high"
    assert decision["action"] == "quarantine"
    assert governance["high_risk_policy_decision_count"] == 1
    assert governance["canary_ready"] is False
    assert governance["rollback_recommended"] is True


def test_canonical_commit_rejects_stale_parent_and_is_idempotent(
    tmp_path: Path,
) -> None:
    operation = {
        "operation_id": "op-e-1",
        "action": "upsert_entity",
        "object_type": "entity",
        "object_id": "ce-1",
        "after": {
            "canonical_id": "ce-1",
            "canonical_text": "A",
            "entity_type": "entity",
            "confidence": 0.8,
            "aliases": ["A"],
        },
        "mentions": [],
        "evidence_contract": {},
    }
    first_patch = {
        "patch_id": "patch-first",
        "parent_version_id": None,
        "operations": [operation],
    }
    stale_patch = {
        "patch_id": "patch-stale",
        "parent_version_id": None,
        "operations": [],
    }
    with CanonicalGraphStore(tmp_path) as store:
        first = store.commit_patch(first_patch, run_id="r1", document_id="d1")
        replay = store.commit_patch(first_patch, run_id="r1", document_id="d1")
        with pytest.raises(RuntimeError, match="stale canonical patch"):
            store.commit_patch(stale_patch, run_id="r2", document_id="d2")
        history = store.history()

    assert replay["version_id"] == first["version_id"]
    assert replay["idempotent_replay"] is True
    assert len(history) == 1


def test_idempotent_patch_rejects_different_certificate_bound_selection(
    tmp_path: Path,
) -> None:
    first_operation = _canonical_entity_op("op-e-1", "A", 0.8, "seg-1:m1")
    second_operation = deepcopy(first_operation)
    second_operation["operation_id"] = "op-e-2"
    second_operation["object_id"] = "ce-2"
    second_operation["after"]["canonical_id"] = "ce-2"
    second_operation["after"]["canonical_text"] = "B"
    second_operation["after"]["aliases"] = ["B"]
    second_operation["mentions"][0]["mention_uid"] = "seg-1:m2"
    patch = {
        "patch_id": "patch-selection-bound",
        "parent_version_id": None,
        "operations": [first_operation, second_operation],
    }
    first_metrics = {
        "causal_validation_certificate": {"certificate_id": "cvc-first"}
    }
    conflicting_metrics = {
        "causal_validation_certificate": {"certificate_id": "cvc-second"}
    }
    with CanonicalGraphStore(tmp_path) as store:
        committed = store.commit_patch(
            patch,
            run_id="r1",
            document_id="d1",
            metrics=first_metrics,
            accepted_operation_ids={"op-e-1"},
        )
        replay = store.commit_patch(
            patch,
            run_id="r1",
            document_id="d1",
            metrics=first_metrics,
            accepted_operation_ids={"op-e-1"},
        )
        with pytest.raises(RuntimeError, match="commit manifest mismatch"):
            store.commit_patch(
                patch,
                run_id="r1",
                document_id="d1",
                metrics=conflicting_metrics,
                accepted_operation_ids={"op-e-2"},
            )

    assert replay["version_id"] == committed["version_id"]
    assert replay["idempotent_replay"] is True
    assert replay["certificate_id"] == "cvc-first"
    assert replay["commit_manifest_hash"] == committed["commit_manifest_hash"]


def test_old_version_rollback_recomputes_entity_and_relation_from_later_contributions(
    tmp_path: Path,
) -> None:
    with CanonicalGraphStore(tmp_path) as store:
        v1 = store.commit_patch(
            {
                "patch_id": "patch-v1",
                "parent_version_id": None,
                "operations": [
                    _canonical_entity_op("op-e-v1", "A", 0.9, "m-v1"),
                ],
            },
            run_id="r1",
            document_id="d1",
        )
        v2 = store.commit_patch(
            {
                "patch_id": "patch-v2",
                "parent_version_id": v1["version_id"],
                "operations": [
                    _canonical_entity_op("op-e-v2", "Alpha", 0.4, "m-v2"),
                ],
            },
            run_id="r2",
            document_id="d2",
        )
        store.rollback_version(v1["version_id"], "remove old contribution")
        snapshot = store.snapshot()
        mention_rows = store.conn.execute(
            """
            SELECT mention_uid, version_id FROM entity_mentions
            WHERE canonical_id = 'ce-1' ORDER BY mention_uid
            """
        ).fetchall()

    assert snapshot["entities"][0]["canonical_text"] == "Alpha"
    assert snapshot["entities"][0]["confidence"] == pytest.approx(0.4)
    assert snapshot["entities"][0]["created_version"] == v2["version_id"]
    assert snapshot["entities"][0]["aliases"] == ["Alpha"]
    assert [(row[0], row[1]) for row in mention_rows] == [
        ("m-v2", v2["version_id"])
    ]


def test_old_rollback_never_reactivates_later_entity_or_relation_delete(
    tmp_path: Path,
) -> None:
    with CanonicalGraphStore(tmp_path) as store:
        setup = store.commit_patch(
            {
                "patch_id": "patch-setup",
                "parent_version_id": None,
                "operations": [
                    {
                        **_canonical_entity_op(
                            "op-subject", "Subject", 0.7, "m-subject"
                        ),
                        "object_id": "ce-subject",
                        "after": {
                            **_canonical_entity_op(
                                "op-subject", "Subject", 0.7, "m-subject"
                            )["after"],
                            "canonical_id": "ce-subject",
                        },
                    },
                    {
                        **_canonical_entity_op(
                            "op-object", "Object", 0.7, "m-object"
                        ),
                        "object_id": "ce-object",
                        "after": {
                            **_canonical_entity_op(
                                "op-object", "Object", 0.7, "m-object"
                            )["after"],
                            "canonical_id": "ce-object",
                        },
                    },
                ],
            },
            run_id="setup",
            document_id="setup",
        )
        v1 = store.commit_patch(
            {
                "patch_id": "patch-relation-v1",
                "parent_version_id": setup["version_id"],
                "operations": [
                    _canonical_entity_op("op-e-v1", "A", 0.9, "m-v1"),
                    _canonical_relation_op("op-r-v1", 0.9, "ev-v1"),
                ],
            },
            run_id="r1",
            document_id="d1",
        )
        v2 = store.commit_patch(
            {
                "patch_id": "patch-later-update",
                "parent_version_id": v1["version_id"],
                "operations": [
                    _canonical_entity_op("op-e-v2", "Alpha", 0.4, "m-v2"),
                    _canonical_relation_op("op-r-v2", 0.4, "ev-v2"),
                ],
            },
            run_id="r2",
            document_id="d2",
        )
        v3 = store.commit_patch(
            {
                "patch_id": "patch-later-delete",
                "parent_version_id": v2["version_id"],
                "operations": [
                    {
                        "operation_id": "delete-e",
                        "action": "delete_entity",
                        "object_type": "entity",
                        "object_id": "ce-1",
                        "after": {"canonical_id": "ce-1"},
                    },
                    {
                        "operation_id": "delete-r",
                        "action": "delete_relation",
                        "object_type": "relation",
                        "object_id": "cr-1",
                        "after": {"canonical_relation_id": "cr-1"},
                    },
                ],
            },
            run_id="r3",
            document_id="d3",
        )
        store.rollback_version(v1["version_id"], "old version rollback")
        entity_row = store.conn.execute(
            "SELECT status, last_version FROM canonical_entities WHERE canonical_id = 'ce-1'"
        ).fetchone()
        relation_row = store.conn.execute(
            """
            SELECT status, last_version FROM canonical_relations
            WHERE canonical_relation_id = 'cr-1'
            """
        ).fetchone()
        deleted_entity_state = tuple(entity_row)
        deleted_relation_state = tuple(relation_row)
        store.rollback_version(v3["version_id"], "restore later delete")
        restored = store.snapshot()

    assert deleted_entity_state == ("retracted", v3["version_id"])
    assert deleted_relation_state == ("retracted", v3["version_id"])
    restored_entity = next(
        item for item in restored["entities"] if item["canonical_id"] == "ce-1"
    )
    restored_relation = next(
        item
        for item in restored["relations"]
        if item["canonical_relation_id"] == "cr-1"
    )
    assert restored_entity["canonical_text"] == "Alpha"
    assert restored_entity["confidence"] == pytest.approx(0.4)
    assert restored_entity["aliases"] == ["Alpha"]
    assert restored_relation["confidence"] == pytest.approx(0.4)
    assert [
        item["evidence_uid"]
        for item in restored["relation_evidence"]
        if item["canonical_relation_id"] == "cr-1"
    ] == ["ev-v2"]


def test_interleaved_rollback_recomputes_status_from_upserts_and_tombstones(
    tmp_path: Path,
) -> None:
    with CanonicalGraphStore(tmp_path) as store:
        setup = store.commit_patch(
            {
                "patch_id": "patch-interleaved-setup",
                "parent_version_id": None,
                "operations": [
                    {
                        **_canonical_entity_op(
                            "op-subject", "Subject", 0.7, "m-subject"
                        ),
                        "object_id": "ce-subject",
                        "after": {
                            **_canonical_entity_op(
                                "op-subject", "Subject", 0.7, "m-subject"
                            )["after"],
                            "canonical_id": "ce-subject",
                        },
                    },
                    {
                        **_canonical_entity_op(
                            "op-object", "Object", 0.7, "m-object"
                        ),
                        "object_id": "ce-object",
                        "after": {
                            **_canonical_entity_op(
                                "op-object", "Object", 0.7, "m-object"
                            )["after"],
                            "canonical_id": "ce-object",
                        },
                    },
                ],
            },
            run_id="setup",
            document_id="setup",
        )
        v1 = store.commit_patch(
            {
                "patch_id": "patch-interleaved-v1",
                "parent_version_id": setup["version_id"],
                "operations": [
                    _canonical_entity_op("op-e-v1", "A", 0.9, "m-v1"),
                    _canonical_relation_op("op-r-v1", 0.9, "ev-v1"),
                ],
            },
            run_id="r1",
            document_id="d1",
        )
        v2 = store.commit_patch(
            {
                "patch_id": "patch-interleaved-v2-delete",
                "parent_version_id": v1["version_id"],
                "operations": [
                    {
                        "operation_id": "delete-e-v2",
                        "action": "delete_entity",
                        "object_type": "entity",
                        "object_id": "ce-1",
                        "after": {"canonical_id": "ce-1"},
                    },
                    {
                        "operation_id": "delete-r-v2",
                        "action": "delete_relation",
                        "object_type": "relation",
                        "object_id": "cr-1",
                        "after": {"canonical_relation_id": "cr-1"},
                    },
                ],
            },
            run_id="r2",
            document_id="d2",
        )
        v3 = store.commit_patch(
            {
                "patch_id": "patch-interleaved-v3-upsert",
                "parent_version_id": v2["version_id"],
                "operations": [
                    _canonical_entity_op("op-e-v3", "Alpha", 0.4, "m-v3"),
                    _canonical_relation_op("op-r-v3", 0.4, "ev-v3"),
                ],
            },
            run_id="r3",
            document_id="d3",
        )

        store.rollback_version(v3["version_id"], "remove later upsert")
        after_v3_rollback = store.snapshot()
        store.rollback_version(v2["version_id"], "remove earlier tombstone")
        after_v2_rollback = store.snapshot()

    assert all(
        item["canonical_id"] != "ce-1"
        for item in after_v3_rollback["entities"]
    )
    assert all(
        item["canonical_relation_id"] != "cr-1"
        for item in after_v3_rollback["relations"]
    )
    restored_entity = next(
        item
        for item in after_v2_rollback["entities"]
        if item["canonical_id"] == "ce-1"
    )
    restored_relation = next(
        item
        for item in after_v2_rollback["relations"]
        if item["canonical_relation_id"] == "cr-1"
    )
    assert restored_entity["canonical_text"] == "A"
    assert restored_entity["confidence"] == pytest.approx(0.9)
    assert restored_entity["aliases"] == ["A"]
    assert restored_relation["confidence"] == pytest.approx(0.9)
    assert [
        item["evidence_uid"]
        for item in after_v2_rollback["relation_evidence"]
        if item["canonical_relation_id"] == "cr-1"
    ] == ["ev-v1"]


def test_recreate_after_full_compensation_starts_a_fresh_object_lifecycle(
    tmp_path: Path,
) -> None:
    with CanonicalGraphStore(tmp_path) as store:
        setup = store.commit_patch(
            {
                "patch_id": "patch-recreate-setup",
                "parent_version_id": None,
                "operations": [
                    {
                        **_canonical_entity_op(
                            "op-subject", "Subject", 0.7, "m-subject"
                        ),
                        "object_id": "ce-subject",
                        "after": {
                            **_canonical_entity_op(
                                "op-subject", "Subject", 0.7, "m-subject"
                            )["after"],
                            "canonical_id": "ce-subject",
                        },
                    },
                    {
                        **_canonical_entity_op(
                            "op-object", "Object", 0.7, "m-object"
                        ),
                        "object_id": "ce-object",
                        "after": {
                            **_canonical_entity_op(
                                "op-object", "Object", 0.7, "m-object"
                            )["after"],
                            "canonical_id": "ce-object",
                        },
                    },
                ],
            },
            run_id="setup",
            document_id="setup",
        )
        old = store.commit_patch(
            {
                "patch_id": "patch-recreate-old",
                "parent_version_id": setup["version_id"],
                "operations": [
                    _canonical_entity_op("op-old-e", "Old", 0.95, "m-old"),
                    _canonical_relation_op("op-old-r", 0.95, "ev-old"),
                ],
            },
            run_id="old",
            document_id="old",
        )
        compensation = store.rollback_version(
            old["version_id"], "remove old lifecycle"
        )
        new = store.commit_patch(
            {
                "patch_id": "patch-recreate-new",
                "parent_version_id": compensation["version_id"],
                "operations": [
                    _canonical_entity_op("op-new-e", "New", 0.4, "m-new"),
                    _canonical_relation_op("op-new-r", 0.4, "ev-new"),
                ],
            },
            run_id="new",
            document_id="new",
        )
        snapshot = store.snapshot()

    recreated_entity = next(
        item for item in snapshot["entities"] if item["canonical_id"] == "ce-1"
    )
    recreated_relation = next(
        item
        for item in snapshot["relations"]
        if item["canonical_relation_id"] == "cr-1"
    )
    assert recreated_entity["canonical_text"] == "New"
    assert recreated_entity["confidence"] == pytest.approx(0.4)
    assert recreated_entity["created_version"] == new["version_id"]
    assert recreated_entity["aliases"] == ["New"]
    assert recreated_relation["confidence"] == pytest.approx(0.4)
    assert recreated_relation["created_version"] == new["version_id"]
    assert [
        item["evidence_uid"]
        for item in snapshot["relation_evidence"]
        if item["canonical_relation_id"] == "cr-1"
    ] == ["ev-new"]


def test_shadow_uses_evidence_impact_domain_and_exact_compensation() -> None:
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
                        "confidence": 0.8,
                    },
                    "affected_domain": {
                        "entity_ids": ["ce-1"],
                        "source_document_ids": ["doc-1"],
                        "source_segment_ids": ["seg-1"],
                        "basis": "entity_evidence_contract",
                    },
                    "evidence_contract": {
                        "provenance_complete": False,
                        "source_document_ids": ["doc-1"],
                        "source_segment_ids": ["seg-1"],
                    },
                },
                {
                    "operation_id": "op-e-2",
                    "object_type": "entity",
                    "object_id": "ce-2",
                    "after": {
                        "canonical_id": "ce-2",
                        "canonical_text": "B",
                        "entity_type": "entity",
                        "confidence": 0.8,
                    },
                    "affected_domain": {
                        "entity_ids": ["ce-2"],
                        "source_document_ids": ["doc-1"],
                        "source_segment_ids": ["seg-1"],
                        "basis": "entity_evidence_contract",
                    },
                    "evidence_contract": {
                        "provenance_complete": True,
                        "source_document_ids": ["doc-1"],
                        "source_segment_ids": ["seg-1"],
                    },
                },
            ]
        },
    }

    evaluation = evolution_shadow_node(state)["shadow_evaluation"]
    solver = evaluation["compensation_solver"]

    assert evaluation["compensation_operation_ids"] == ["op-e-1"]
    assert solver["solver_mode"] == "exact_enumeration"
    assert solver["optimality"] == "global_over_causal_candidate_space"
    assert solver["constraints"]["all_invariants_pass"] is True
    assert evaluation["impact_domain"]["source_document_ids"] == ["doc-1"]
    assert evaluation["impact_domain"]["source_segment_ids"] == ["seg-1"]
    assert evaluation["impact_domain"]["entity_ids"] == ["ce-1", "ce-2"]
    assert evaluation["retained_impact_domain"]["entity_ids"] == ["ce-2"]
    assert (
        evaluation["causal_validation_certificate"]["frozen_impact_domain_hash"]
        == evaluation["impact_domain"]["domain_hash"]
    )
    certificate = evaluation["causal_validation_certificate"]
    assert certificate["schema"] == "evolex.causal-validation-certificate.v1"
    assert certificate["excluded_operation_ids"] == ["op-e-1"]
    assert certificate["accepted_operation_ids"] == ["op-e-2"]
    assert certificate["certificate_id"].startswith("cvc-")
    provenance_failure = next(
        item
        for item in evaluation["failed_queries"]
        if item["query_id"] == "q:op-e-1:entity_provenance"
    )
    assert provenance_failure["attribution_status"] == "counterfactually_verified"
    assert provenance_failure["counterfactual_cause_operation_ids"] == ["op-e-1"]
    assert provenance_failure["counterfactual_checks"] == [
        {
            "operation_id": "op-e-1",
            "exclusion_closure_ids": ["op-e-1"],
            "target_failure_resolved": True,
        }
    ]
    altered_attribution = deepcopy(evaluation)
    altered_failure = next(
        item
        for item in altered_attribution["failed_queries"]
        if item["query_id"] == "q:op-e-1:entity_provenance"
    )
    altered_failure["counterfactual_checks"][0][
        "target_failure_resolved"
    ] = False
    altered_decision = evolution_consensus_node(
        {**state, "shadow_evaluation": altered_attribution}
    )["evolution_decision"]
    assert altered_decision["certificate_verified"] is False


def test_large_causal_candidate_space_uses_labelled_fixed_point_fallback() -> None:
    operations = []
    for index in range(17):
        entity_id = f"ce-{index:02d}"
        operations.append(
            {
                "operation_id": f"op-e-{index:02d}",
                "object_type": "entity",
                "object_id": entity_id,
                "after": {
                    "canonical_id": entity_id,
                    "canonical_text": f"Entity {index}",
                    "entity_type": "entity",
                    "confidence": 0.8,
                },
                "affected_domain": {
                    "entity_ids": [entity_id],
                    "source_document_ids": ["doc-1"],
                    "source_segment_ids": [f"seg-{index:02d}"],
                    "basis": "entity_evidence_contract",
                },
                "evidence_contract": {
                    "provenance_complete": False,
                    "source_document_ids": ["doc-1"],
                    "source_segment_ids": [f"seg-{index:02d}"],
                },
            }
        )
    state = {
        "canonical_baseline": {
            "version_id": None,
            "entities": [],
            "relations": [],
            "relation_evidence": [],
        },
        "graph_patch": {
            "patch_id": "patch-large-fallback",
            "parent_version_id": None,
            "operations": operations,
        },
    }

    evaluation = evolution_shadow_node(state)["shadow_evaluation"]
    solver = evaluation["compensation_solver"]

    assert solver["candidate_count"] == 17
    assert solver["solver_mode"] == "deterministic_fixed_point_deletion_fallback"
    assert solver["optimality"] == "single_deletion_local_minimum_not_global"
    assert solver["fallback_pass_count"] >= 1
    assert solver["constraints"]["all_invariants_pass"] is True
    assert len(evaluation["compensation_operation_ids"]) == 17


def test_causal_validation_certificate_blocks_attribution_tampering() -> None:
    state = {
        "canonical_baseline": {
            "version_id": None,
            "entities": [],
            "relations": [],
            "relation_evidence": [],
        },
        "graph_patch": {
            "patch_id": "patch-certificate-test",
            "parent_version_id": None,
            "operations": [
                {
                    "operation_id": "op-e-1",
                    "object_type": "entity",
                    "object_id": "ce-1",
                    "after": {
                        "canonical_id": "ce-1",
                        "canonical_text": "A",
                        "entity_type": "entity",
                        "confidence": 0.8,
                    },
                    "affected_domain": {
                        "entity_ids": ["ce-1"],
                        "source_document_ids": ["doc-1"],
                        "source_segment_ids": ["seg-1"],
                        "basis": "entity_evidence_contract",
                    },
                    "evidence_contract": {
                        "provenance_complete": True,
                        "source_document_ids": ["doc-1"],
                        "source_segment_ids": ["seg-1"],
                    },
                }
            ],
        },
    }
    evaluation = evolution_shadow_node(state)["shadow_evaluation"]
    accepted = evolution_consensus_node(
        {**state, "shadow_evaluation": evaluation}
    )["evolution_decision"]
    assert accepted["accepted"] is True
    assert accepted["certificate_verified"] is True

    tampered = deepcopy(evaluation)
    tampered["query_results"][0]["caused_by_operation_ids"] = ["op-forged"]
    rejected = evolution_consensus_node(
        {**state, "shadow_evaluation": tampered}
    )["evolution_decision"]
    assert rejected["accepted"] is False
    assert rejected["certificate_verified"] is False

    altered_baseline = deepcopy(state["canonical_baseline"])
    altered_baseline["version_id"] = "version-forged"
    rejected_baseline = evolution_consensus_node(
        {
            **state,
            "canonical_baseline": altered_baseline,
            "shadow_evaluation": evaluation,
        }
    )["evolution_decision"]
    assert rejected_baseline["certificate_verified"] is False

    for mutate in (
        lambda item: item["compensation_solver"].__setitem__(
            "solver_mode", "forged_solver"
        ),
        lambda item: item["compensation_operation_ids"].append("op-forged"),
        lambda item: item.__setitem__("shadow_snapshot_hash", "forged_hash"),
    ):
        altered_evaluation = deepcopy(evaluation)
        mutate(altered_evaluation)
        rejected_content = evolution_consensus_node(
            {**state, "shadow_evaluation": altered_evaluation}
        )["evolution_decision"]
        assert rejected_content["certificate_verified"] is False

    forged_decision = deepcopy(accepted)
    forged_decision["accepted_operation_ids"] = ["op-e-1", "op-forged"]
    commit_result = make_evolution_commit_node()(
        {
            **state,
            "shadow_evaluation": evaluation,
            "evolution_decision": forged_decision,
            "evaluation_mode": "shadow",
        }
    )
    assert commit_result["evolution_commit"]["status"] == "failed"
    assert commit_result["status"] == "quarantined"


def test_agent_commit_precedes_publication_and_versions_match(
    tmp_path: Path,
) -> None:
    result = run_pipeline_text(
        "API Gateway retries HTTP errors.",
        pipeline="agent",
        output_dir=tmp_path,
        extractor=HeuristicTypedExtractor(),
    )
    actions = [
        item["selected_action"] for item in result.state.get("agent_trace", [])
    ]
    commit_index = actions.index("evolution_commit_tool")
    publish_index = actions.index("publish_tool")
    with sqlite3.connect(result.publish_output_path) as connection:
        stored_version = connection.execute(
            "SELECT graph_version FROM runs WHERE run_id = ?",
            (result.run_id,),
        ).fetchone()[0]

    assert commit_index < publish_index
    assert stored_version == result.state["canonical_version_id"]


def test_low_publish_confidence_blocks_canonical_commit_before_delivery_downgrade(
    tmp_path: Path,
) -> None:
    result = run_pipeline_text(
        "x",
        pipeline="agent",
        output_dir=tmp_path,
        extractor=HeuristicTypedExtractor(),
    )
    decision = result.state["policy_decisions"][0]
    with CanonicalGraphStore(tmp_path / "canonical") as store:
        snapshot = store.snapshot()

    assert decision["policy_engine_action"] == "publish"
    assert decision["action"] == "candidate"
    assert decision["canonical_action"] == "held"
    assert decision["delivery_action"] == "candidate"
    assert result.state.get("evolution_commit", {}).get("status") != "committed"
    assert snapshot["version_id"] is None
    assert snapshot["entities"] == []


def test_agent_resume_keeps_checkpoint_steps_monotonic(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    result = run_pipeline_text(
        "API Gateway retries HTTP errors.",
        pipeline="agent",
        output_dir=source_dir,
        extractor=HeuristicTypedExtractor(),
    )
    state = dict(result.state)
    actions = [
        item.get("selected_action") for item in state.get("agent_trace", [])
    ]
    plan_index = actions.index("evolution_plan_tool")
    state["agent_trace"] = state["agent_trace"][: plan_index + 1]
    state["status"] = "running"
    for field in (
        "shadow_evaluation",
        "evolution_decision",
        "quality_scores",
        "critic_results",
        "policy_decisions",
        "publish_output_path",
        "evolution_commit",
        "canonical_store_path",
        "canonical_version_id",
        "registry_output_path",
    ):
        state.pop(field, None)
    state["invalidated_tools"] = []

    checkpoint_dir = tmp_path / "resume-checkpoints"
    store = CheckpointStore(checkpoint_dir)
    store.put_checkpoint(state, node_name="evolution_plan", step_index=999)
    resumed = resume_thread(
        thread_id=state["thread_id"],
        output_dir=tmp_path / "resumed-output",
        checkpoint_dir=checkpoint_dir,
        extractor=HeuristicTypedExtractor(),
        pipeline="agent",
    )
    latest = store.latest_for_thread(state["thread_id"])

    assert resumed.resumed_from_node == "evolution_plan"
    assert resumed.result.state["evolution_commit"]["status"] == "committed"
    assert latest is not None
    assert latest["step_index"] > 999
    assert latest["node_name"] == "registry_finalize"


def test_resume_inherits_pipeline_and_heuristic_runtime_from_checkpoint(
    tmp_path: Path,
) -> None:
    checkpoint_dir = tmp_path / "checkpoints"
    result = run_pipeline_text(
        "API Gateway retries HTTP errors.",
        pipeline="agent",
        output_dir=tmp_path / "source",
        checkpoint_dir=checkpoint_dir,
        extractor=HeuristicTypedExtractor(),
    )

    assert result.state["pipeline_mode"] == "agent"
    assert (
        result.state["model_routes"]["extractor_class"]
        == "HeuristicTypedExtractor"
    )
    resumed = resume_thread(
        thread_id=result.state["thread_id"],
        output_dir=tmp_path / "resumed",
        checkpoint_dir=checkpoint_dir,
    )
    assert resumed.result.state["pipeline_mode"] == "agent"
    with pytest.raises(ValueError, match="does not match checkpoint"):
        resume_thread(
            thread_id=result.state["thread_id"],
            output_dir=tmp_path / "wrong-mode",
            checkpoint_dir=checkpoint_dir,
            pipeline="system",
        )


def test_latest_checkpoint_uses_most_recent_run_not_largest_old_step(
    tmp_path: Path,
) -> None:
    store = CheckpointStore(tmp_path)
    thread_id = "thread-shared"
    store.put_checkpoint(
        {"run_id": "old-long-run", "thread_id": thread_id},
        node_name="registry_finalize",
        step_index=100,
    )
    store.put_checkpoint(
        {"run_id": "new-short-run", "thread_id": thread_id},
        node_name="extract",
        step_index=2,
    )

    latest = store.latest_for_thread(thread_id)
    assert latest is not None
    assert latest["run_id"] == "new-short-run"
    assert latest["step_index"] == 2


def test_phase3_resume_consumes_policy_publish_edge(tmp_path: Path) -> None:
    checkpoint_dir = tmp_path / "checkpoints"
    output_dir = tmp_path / "resumed-output"
    state = {
        "run_id": "RUN-policy-edge",
        "thread_id": "document:DOC-policy-edge:v1:v3",
        "document_id": "DOC-policy-edge",
        "document_version": 1,
        "pipeline_mode": "phase3",
        "status": "candidate",
        "schema_version": "schema-test",
        "policy_version": "policy-test",
        "graph_version": "graph-test",
        "model_routes": {
            "extractor_class": "HeuristicTypedExtractor",
            "uses_llm": "false",
        },
        "policy_decisions": [{"action": "publish", "reasons": []}],
        "entities": [],
        "relations": [],
        "warnings": [],
    }
    CheckpointStore(checkpoint_dir).put_checkpoint(
        state,
        node_name="policy",
        step_index=10,
    )
    executed: list[str] = []

    resumed = resume_thread(
        thread_id=state["thread_id"],
        output_dir=output_dir,
        checkpoint_dir=checkpoint_dir,
        extractor=HeuristicTypedExtractor(),
        on_node=executed.append,
    )

    assert resumed.result.status == "published"
    assert resumed.result.publish_output_path
    assert Path(resumed.result.publish_output_path).exists()
    assert executed == ["publish", "registry_finalize"]


def test_phase3_resume_consumes_quality_quarantine_edge(tmp_path: Path) -> None:
    checkpoint_dir = tmp_path / "checkpoints"
    output_dir = tmp_path / "resumed-output"
    state = {
        "run_id": "RUN-quality-edge",
        "thread_id": "document:DOC-quality-edge:v1:v3",
        "document_id": "DOC-quality-edge",
        "document_version": 1,
        "pipeline_mode": "phase3",
        "status": "quarantined",
        "schema_version": "schema-test",
        "policy_version": "policy-test",
        "graph_version": "graph-test",
        "model_routes": {
            "extractor_class": "HeuristicTypedExtractor",
            "uses_llm": "false",
        },
        "warnings": ["deterministic validation failed"],
    }
    CheckpointStore(checkpoint_dir).put_checkpoint(
        state,
        node_name="quality_review",
        step_index=8,
    )
    executed: list[str] = []

    resumed = resume_thread(
        thread_id=state["thread_id"],
        output_dir=output_dir,
        checkpoint_dir=checkpoint_dir,
        extractor=HeuristicTypedExtractor(),
        on_node=executed.append,
    )

    assert resumed.result.status == "quarantined"
    assert not resumed.result.publish_output_path
    assert executed == ["quarantine", "registry_finalize"]
    assert not resumed.result.state.get("critic_results")
    assert not resumed.result.state.get("policy_decisions")


def test_rogue_agent_cannot_publish_before_governance_dependencies(
    tmp_path: Path,
) -> None:
    class RogueAgent:
        def propose(self, state, uncertainty, completed_tools):
            return [
                AgentProposal.from_scores(
                    agent_name="RogueAgent",
                    proposed_action="publish_tool",
                    expected_information_gain_value=1.0,
                    risk=0.0,
                    cost=0.0,
                    reason="attempt to bypass governance",
                )
            ]

    runner = AgenticKGRunner(
        extractor=HeuristicTypedExtractor(),
        output_dir=tmp_path,
    )
    runner.agents = [RogueAgent()]
    state = runner.invoke(
        {
            "run_id": "RUN-rogue",
            "thread_id": "document:DOC-rogue:v1:agent",
            "document_id": "DOC-rogue",
            "document_version": 1,
            "pipeline_mode": "agent",
            "document_text": "A depends on B.",
            "schema_version": "schema-test",
            "active_schema": {
                "version_id": "schema-test",
                "types": [],
                "predicates": [],
                "attributes": [],
            },
            "policy_version": "policy-test",
            "graph_version": "graph-test",
            "model_routes": {
                "extractor_class": "HeuristicTypedExtractor",
                "uses_llm": "false",
            },
            "status": "running",
        }
    )

    actions = [
        item.get("selected_action") for item in state.get("agent_trace", [])
    ]
    assert "publish_tool" not in actions
    assert "publish_tool" not in _completed_tools(state)
    assert state["status"] == "quarantined"
    assert state["policy_decisions"][0]["policy_engine_action"] == "not_evaluated"
    assert not (tmp_path / "RUN-rogue.sqlite").exists()


def test_publish_failure_rolls_back_the_entire_run_snapshot(
    tmp_path: Path,
) -> None:
    node = make_publish_node(tmp_path)
    state = {
        "run_id": "RUN-atomic-failure",
        "document_id": "DOC-atomic-failure",
        "document_version": 1,
        "pipeline_mode": "phase1+2",
        "status": "candidate",
        "entities": [
            {
                "entity_id": "e1",
                "canonical_text": "A",
                "type": "entity",
                "merged_count": 1,
                "segment_ids": ["s1"],
            }
        ],
        "relations": [
            {
                "relation_id": "r1",
                "subject_entity_id": "e1",
                "predicate": "depends_on",
                "object_entity_id": "missing",
                "evidence": "A depends on missing.",
                "confidence": 0.8,
            }
        ],
    }

    with pytest.raises(sqlite3.IntegrityError):
        node(state)

    with sqlite3.connect(tmp_path / "RUN-atomic-failure.sqlite") as connection:
        assert connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM entities").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM relations").fetchone()[0] == 0


def test_publish_retry_replaces_instead_of_duplicating_run_projection(
    tmp_path: Path,
) -> None:
    node = make_publish_node(tmp_path)
    state = {
        "run_id": "RUN-idempotent-publish",
        "document_id": "DOC-idempotent-publish",
        "document_version": 1,
        "pipeline_mode": "phase3",
        "status": "candidate",
        "policy_decisions": [{"action": "publish", "reasons": []}],
        "entities": [
            {
                "entity_id": "e1",
                "canonical_text": "A",
                "type": "entity",
                "merged_count": 1,
                "segment_ids": ["s1"],
            },
            {
                "entity_id": "e2",
                "canonical_text": "B",
                "type": "entity",
                "merged_count": 1,
                "segment_ids": ["s1"],
            },
        ],
        "relations": [
            {
                "relation_id": "r1",
                "subject_entity_id": "e1",
                "predicate": "depends_on",
                "object_entity_id": "e2",
                "evidence": "A depends on B.",
                "confidence": 0.8,
            }
        ],
        "quality_scores": [
            {
                "target_type": "relation",
                "target_index": 0,
                "score": 0.8,
                "issues": [],
                "adjusted_confidence": 0.8,
            }
        ],
        "entity_decisions": [
            {
                "mention_text": "A",
                "normalized_text": "a",
                "decision": "CREATE_CANDIDATE",
                "target_entity_id": "e1",
                "confidence": 0.8,
                "reason": "new_entity",
                "segment_id": "s1",
            }
        ],
    }

    first = node(state)
    second = node(state)

    assert first["status"] == second["status"] == "published"
    with sqlite3.connect(second["publish_output_path"]) as connection:
        counts = {
            table: connection.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]
            for table in (
                "runs",
                "entities",
                "relations",
                "quality_scores",
                "entity_decisions",
                "run_audit",
            )
        }
    assert counts == {
        "runs": 1,
        "entities": 2,
        "relations": 1,
        "quality_scores": 1,
        "entity_decisions": 1,
        "run_audit": 1,
    }


def test_policy_publish_checkpoint_remains_pre_delivery_candidate() -> None:
    result = policy_node(
        {
            "validation_results": [{"ok": True}],
            "critic_results": [{"verdict": "approved"}],
            "claim_candidates": [{"claim_id": "c1"}],
            "evidence_spans": [{"evidence_id": "e1"}],
            "evolution_decision": {"accepted": True},
        }
    )

    decision = result["policy_decisions"][0]
    assert decision["action"] == "publish"
    assert decision["canonical_action"] == "pending"
    assert decision["delivery_action"] == "pending"
    assert result["status"] == "candidate"


def test_published_status_is_monotonic_at_agent_budget_boundary(
    tmp_path: Path,
) -> None:
    result = run_pipeline_text(
        "API Gateway retries HTTP errors.",
        pipeline="agent",
        output_dir=tmp_path,
        extractor=HeuristicTypedExtractor(),
    )
    assert result.status == "published"
    state = deepcopy(result.state)
    state["agent_trace"] = [
        item
        for item in state["agent_trace"]
        if item.get("selected_action") != "registry_finalize_tool"
    ]
    state["completed_tools"] = [
        item
        for item in state.get("completed_tools", [])
        if item != "registry_finalize_tool"
    ]
    state.pop("registry_output_path", None)
    state["agent_budget"] = {
        **state.get("agent_budget", {}),
        "max_rounds": len(state["agent_trace"]),
    }
    trace_count = len(state["agent_trace"])

    resumed = AgenticKGRunner(
        extractor=HeuristicTypedExtractor(),
        output_dir=tmp_path,
    ).invoke(state)

    assert resumed["status"] == "published"
    assert len(resumed["agent_trace"]) == trace_count
    assert "registry_finalize_tool" in _completed_tools(resumed)


def test_low_eig_consecutive_count_survives_runner_reconstruction(
    tmp_path: Path,
) -> None:
    state = {
        "status": "running",
        "agent_budget": {
            "min_utility": 0.5,
            "max_low_eig_rounds": 2,
        },
    }
    proposal = AgentProposal.from_scores(
        agent_name="LowGainAgent",
        proposed_action="ingest_tool",
        expected_information_gain_value=0.0,
        risk=1.0,
        cost=10.0,
        reason="low gain",
    )

    first_runner = AgenticKGRunner(
        extractor=HeuristicTypedExtractor(),
        output_dir=tmp_path,
    )
    assert first_runner._low_gain_stop(state, proposal) is False
    assert state["low_eig_rounds"] == 1

    reconstructed_runner = AgenticKGRunner(
        extractor=HeuristicTypedExtractor(),
        output_dir=tmp_path,
    )
    assert reconstructed_runner._low_gain_stop(state, proposal) is True
    assert state["low_eig_rounds"] == 2


def test_completed_custom_extractor_checkpoint_returns_without_reconstruction(
    tmp_path: Path,
) -> None:
    store = CheckpointStore(tmp_path)
    state = {
        "run_id": "RUN-custom-complete",
        "thread_id": "document:DOC-custom:v1:agent",
        "document_id": "DOC-custom",
        "document_version": 1,
        "pipeline_mode": "agent",
        "status": "candidate",
        "model_routes": {
            "extractor_class": "CustomTypedExtractor",
            "uses_llm": "false",
        },
    }
    store.put_checkpoint(
        state,
        node_name="registry_finalize",
        step_index=10,
    )

    resumed = resume_thread(
        thread_id=state["thread_id"],
        checkpoint_dir=tmp_path,
    )

    assert resumed.result.run_id == state["run_id"]
    assert resumed.result.status == "candidate"


def test_in_progress_custom_extractor_checkpoint_fails_closed(
    tmp_path: Path,
) -> None:
    store = CheckpointStore(tmp_path)
    state = {
        "run_id": "RUN-custom-in-progress",
        "thread_id": "document:DOC-custom-progress:v1:agent",
        "document_id": "DOC-custom-progress",
        "document_version": 1,
        "pipeline_mode": "agent",
        "status": "running",
        "model_routes": {
            "extractor_class": "CustomTypedExtractor",
            "uses_llm": "false",
        },
    }
    store.put_checkpoint(state, node_name="segment", step_index=3)

    with pytest.raises(ValueError, match="cannot be reconstructed safely"):
        resume_thread(
            thread_id=state["thread_id"],
            checkpoint_dir=tmp_path,
        )


def test_registry_finalize_retry_replaces_run_snapshot(
    tmp_path: Path,
) -> None:
    node = make_registry_finalize_node(tmp_path)
    state = {
        "run_id": "RUN-registry-idempotent",
        "status": "quarantined",
        "policy_decisions": [
            {
                "action": "quarantine",
                "risk_level": "high",
                "reasons": ["test"],
            }
        ],
        "entity_decisions": [{"decision": "CREATE_CANDIDATE"}],
        "audit_events": [{"node_name": "policy"}],
        "merge_decisions": [{"object_type": "entity", "action": "HOLD"}],
        "agent_trace": [{"selected_action": "policy_tool", "step_index": 1}],
        "graph_patch": {"patch_id": "patch-1"},
    }

    first = node(state)
    second = node(state)

    assert first["registry_output_path"] == second["registry_output_path"]
    with sqlite3.connect(second["registry_output_path"]) as connection:
        counts = {
            table: connection.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]
            for table in (
                "candidates",
                "entity_decisions",
                "policy_decisions",
                "quarantine_records",
                "audit_events",
                "merge_decisions",
                "agent_trace",
            )
        }
    assert counts == {
        "candidates": 1,
        "entity_decisions": 1,
        "policy_decisions": 1,
        "quarantine_records": 1,
        "audit_events": 1,
        "merge_decisions": 1,
        "agent_trace": 1,
    }
