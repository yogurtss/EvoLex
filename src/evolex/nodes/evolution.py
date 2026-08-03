from __future__ import annotations

import json
from hashlib import sha256
from itertools import combinations
from pathlib import Path
from typing import Any

from evolex.graph.state import GraphState
from evolex.nodes.entity_merge import ALIAS_CANONICAL
from evolex.repositories.canonical import CanonicalGraphStore


def make_evolution_plan_node(output_dir: Path | None = None):
    canonical_dir = (output_dir / "canonical") if output_dir else None

    def evolution_plan_node(state: GraphState) -> dict:
        with CanonicalGraphStore(canonical_dir) as store:
            baseline = store.snapshot()
            patch = _build_patch(state, store)
        return {
            "canonical_baseline": baseline,
            "graph_patch": patch,
            "canonical_entity_map": patch["canonical_entity_map"],
        }

    return evolution_plan_node


def evolution_shadow_node(state: GraphState) -> dict:
    patch = state.get("graph_patch", {})
    baseline = state.get("canonical_baseline", {})
    evaluation = _evaluate_patch(patch, baseline)
    return {"shadow_evaluation": evaluation}


def evolution_consensus_node(state: GraphState) -> dict:
    patch = state.get("graph_patch", {})
    evaluation = state.get("shadow_evaluation", {})
    operations = list(patch.get("operations", []))
    accepted_ids = set(evaluation.get("accepted_operation_ids", []))
    accepted_operations = [
        item
        for item in operations
        if str(item.get("operation_id", "")) in accepted_ids
    ]

    evidence_ok = all(
        bool(item.get("evidence_contract", {}).get("provenance_complete"))
        for item in accepted_operations
    )
    impact_domain_grounded = bool(
        evaluation.get("impact_domain", {}).get("evidence_grounded", False)
    )
    deterministic = bool(evaluation.get("deterministic_replay", False))
    non_interference = bool(evaluation.get("non_interference_passed", False))
    constraints = bool(evaluation.get("passed_after_compensation", False))
    positive_utility = float(evaluation.get("utility", 0.0)) >= 0.0
    certificate_verified = _validation_certificate_matches(
        patch,
        state.get("canonical_baseline", {}),
        evaluation,
    )

    votes = [
        _vote(
            "EvidenceContractAgent",
            evidence_ok and impact_domain_grounded,
            "provenance contract and evidence-derived impact domain",
        ),
        _vote("DeterministicReplayAgent", deterministic, "replay hash"),
        _vote("NonInterferenceAgent", non_interference, "unaffected subgraph hash"),
        _vote("InvariantAgent", constraints, "impact-scoped invariant queries"),
        _vote(
            "CausalCertificateAgent",
            certificate_verified,
            "baseline, impact-domain, query-causality, exclusion and retained-patch binding",
        ),
        _vote("UtilityAgent", positive_utility, "quality-risk utility"),
    ]
    approvals = sum(1 for vote in votes if vote["approve"])
    accepted = (
        bool(accepted_operations)
        and evidence_ok
        and impact_domain_grounded
        and deterministic
        and non_interference
        and constraints
        and certificate_verified
        and positive_utility
        and approvals >= 5
    )
    certificate = evaluation.get("causal_validation_certificate", {})
    decision = {
        "decision": "accept" if accepted else "hold",
        "accepted": accepted,
        "quorum": approvals,
        "required_quorum": 5,
        "votes": votes,
        "certificate_verified": certificate_verified,
        "certificate_id": str(certificate.get("certificate_id", "")),
        "accepted_operation_ids": sorted(accepted_ids) if accepted else [],
        "compensation_operation_ids": list(
            evaluation.get("compensation_operation_ids", [])
        ),
        "reason": (
            "evidence contracts and impact-scoped shadow gates passed"
            if accepted
            else "one or more evolution safety gates did not pass"
        ),
    }
    return {"evolution_decision": decision}


def make_evolution_commit_node(output_dir: Path | None = None):
    canonical_dir = (output_dir / "canonical") if output_dir else None

    def evolution_commit_node(state: GraphState) -> dict:
        decision = state.get("evolution_decision", {})
        if not decision.get("accepted"):
            return {
                "evolution_commit": {
                    "status": "held",
                    "reason": decision.get("reason", "evolution_not_accepted"),
                }
            }
        evaluation = state.get("shadow_evaluation", {})
        if not _validation_certificate_matches(
            state.get("graph_patch", {}),
            state.get("canonical_baseline", {}),
            evaluation,
        ) or not _decision_matches_certificate(decision, evaluation):
            warnings = list(state.get("warnings", []))
            warnings.append(
                "causal validation certificate or commit selection verification failed"
            )
            return {
                "evolution_commit": {
                    "status": "failed",
                    "reason": "causal_validation_certificate_or_selection_mismatch",
                },
                "status": "quarantined",
                "warnings": warnings,
            }
        certificate = evaluation.get("causal_validation_certificate", {})
        if state.get("evaluation_mode") == "shadow":
            return {
                "evolution_commit": {
                    "status": "shadow_only",
                    "operation_count": len(
                        decision.get("accepted_operation_ids", [])
                    ),
                    "certificate_id": certificate.get("certificate_id", ""),
                }
            }
        try:
            with CanonicalGraphStore(canonical_dir) as store:
                result = store.commit_patch(
                    state.get("graph_patch", {}),
                    run_id=str(state.get("run_id", "")),
                    document_id=str(state.get("document_id", "")),
                    metrics=state.get("shadow_evaluation", {}),
                    accepted_operation_ids=set(
                        decision.get("accepted_operation_ids", [])
                    ),
                )
        except Exception as exc:
            warnings = list(state.get("warnings", []))
            warnings.append(f"canonical evolution commit failed: {exc}")
            return {
                "evolution_commit": {
                    "status": "failed",
                    "reason": str(exc),
                },
                "status": "quarantined",
                "warnings": warnings,
            }
        return {
            "evolution_commit": {
                "status": "committed",
                **result,
                "certificate_id": certificate.get("certificate_id", ""),
            },
            "causal_validation_certificate": certificate,
            "canonical_store_path": result["db_path"],
            "canonical_version_id": result["version_id"],
            "graph_version": result["version_id"],
        }

    return evolution_commit_node


def _build_patch(
    state: GraphState,
    store: CanonicalGraphStore,
) -> dict[str, Any]:
    entities = state.get("entities", [])
    mentions_by_id = {
        str(item.get("mention_id", "")): item for item in state.get("mentions", [])
    }
    evidence_by_id = {
        str(item.get("evidence_id", "")): item
        for item in state.get("evidence_spans", [])
    }
    canonical_entity_map: dict[str, str] = {}
    entity_operations: dict[str, dict[str, Any]] = {}

    for entity in entities:
        aliases = _unique(
            [
                str(entity.get("canonical_text", "")),
                *[str(value) for value in entity.get("aliases", [])],
            ]
        )
        entity_type = str(entity.get("type", "entity"))
        resolved = None
        for alias in aliases:
            resolved = store.resolve_entity(_normalize(alias), entity_type)
            if resolved:
                break
        canonical_id = (
            str(resolved["canonical_id"])
            if resolved
            else _stable_id(
                "ce",
                f"{entity_type}:{_normalize(str(entity.get('canonical_text', '')))}",
            )
        )
        local_id = str(entity.get("entity_id", ""))
        canonical_entity_map[local_id] = canonical_id
        source_mention_ids = list(entity.get("source_mention_ids", []))
        mentions = [
            {
                "mention_uid": f"{state.get('run_id', '')}:{mention_id}",
                "mention_text": mentions_by_id.get(mention_id, {}).get("text", ""),
                "segment_id": mentions_by_id.get(mention_id, {}).get("segment_id", ""),
                "evidence_text": mentions_by_id.get(mention_id, {}).get("evidence", ""),
            }
            for mention_id in source_mention_ids
            if mention_id in mentions_by_id
        ]
        operation = entity_operations.setdefault(
            canonical_id,
            {
                "operation_id": f"op-e-{len(entity_operations) + 1:04d}",
                "action": "upsert_entity",
                "object_type": "entity",
                "object_id": canonical_id,
                "after": {
                    "canonical_id": canonical_id,
                    "canonical_text": str(entity.get("canonical_text", "")),
                    "entity_type": entity_type,
                    "confidence": float(entity.get("confidence", 0.5)),
                    "aliases": [],
                },
                "mentions": [],
                "affected_domain": {
                    "entity_ids": [canonical_id],
                    "entity_types": [entity_type],
                    "predicates": [],
                    "relation_ids": [],
                    "source_document_ids": [str(state.get("document_id", ""))],
                    "source_segment_ids": [],
                    "evidence_ids": [],
                    "basis": "entity_evidence_contract",
                },
                "evidence_contract": {
                    "provenance_complete": True,
                    "source_mention_ids": [],
                    "source_segment_ids": [],
                    "source_document_ids": [str(state.get("document_id", ""))],
                    "same_type": True,
                },
                "caused_by": "EvolutionPlanningAgent",
            },
        )
        operation["after"]["aliases"] = _unique(
            [*operation["after"]["aliases"], *aliases]
        )
        operation["mentions"] = _unique_dicts(
            [*operation["mentions"], *mentions],
            key="mention_uid",
        )
        contract = operation["evidence_contract"]
        contract["source_mention_ids"] = _unique(
            [*contract["source_mention_ids"], *source_mention_ids]
        )
        contract["source_segment_ids"] = _unique(
            [
                *contract["source_segment_ids"],
                *[str(value) for value in entity.get("segment_ids", [])],
            ]
        )
        contract["provenance_complete"] = bool(
            contract["source_mention_ids"]
            and contract["source_segment_ids"]
            and mentions
        )
        operation["affected_domain"]["source_segment_ids"] = list(
            contract["source_segment_ids"]
        )

    relation_operations: list[dict[str, Any]] = []
    for relation in state.get("relations", []):
        subject_id = canonical_entity_map.get(
            str(relation.get("subject_entity_id", ""))
        )
        object_id = canonical_entity_map.get(
            str(relation.get("object_entity_id", ""))
        )
        if not subject_id or not object_id:
            continue
        predicate = str(relation.get("predicate", "related_to"))
        qualifiers_hash = str(relation.get("qualifiers_hash", ""))
        relation_id = _stable_id(
            "cr",
            f"{subject_id}|{predicate}|{object_id}|{qualifiers_hash}",
        )
        evidence_ids = [str(value) for value in relation.get("evidence_ids", [])]
        evidence = [
            {
                "evidence_uid": f"{state.get('run_id', '')}:{evidence_id}",
                "evidence_id": evidence_id,
                "segment_id": evidence_by_id.get(evidence_id, {}).get(
                    "segment_id", ""
                ),
                "evidence_text": evidence_by_id.get(evidence_id, {}).get(
                    "text", relation.get("evidence", "")
                ),
                "confidence": float(relation.get("confidence", 0.5)),
            }
            for evidence_id in evidence_ids
        ]
        relation_operations.append(
            {
                "operation_id": f"op-r-{len(relation_operations) + 1:04d}",
                "action": "upsert_relation",
                "object_type": "relation",
                "object_id": relation_id,
                "after": {
                    "canonical_relation_id": relation_id,
                    "subject_id": subject_id,
                    "predicate": predicate,
                    "object_id": object_id,
                    "qualifiers_hash": qualifiers_hash,
                    "confidence": float(relation.get("confidence", 0.5)),
                },
                "evidence": evidence,
                "depends_on_entity_ids": [subject_id, object_id],
                "affected_domain": {
                    "entity_ids": [subject_id, object_id],
                    "entity_types": [],
                    "predicates": [predicate],
                    "relation_ids": [relation_id],
                    "source_document_ids": [str(state.get("document_id", ""))],
                    "source_segment_ids": _unique(
                        str(item.get("segment_id", "")) for item in evidence
                        if item.get("segment_id")
                    ),
                    "evidence_ids": evidence_ids,
                    "basis": "relation_evidence_contract_and_endpoint_dependency",
                },
                "evidence_contract": {
                    "provenance_complete": bool(
                        evidence
                        and all(
                            item.get("evidence_id")
                            and item.get("segment_id")
                            and item.get("evidence_text")
                            for item in evidence
                        )
                    ),
                    "endpoint_mapping_complete": True,
                    "evidence_ids": evidence_ids,
                    "source_candidate_ids": list(
                        relation.get("source_relation_candidate_ids", [])
                    ),
                    "source_document_ids": [str(state.get("document_id", ""))],
                },
                "caused_by": "EvolutionPlanningAgent",
            }
        )

    operations = [*entity_operations.values(), *relation_operations]
    digest_payload = json.dumps(
        operations,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    patch_id = f"patch-{sha256(digest_payload.encode()).hexdigest()[:16]}"
    return {
        "patch_id": patch_id,
        "parent_version_id": store.latest_version_id(),
        "run_id": state.get("run_id", ""),
        "document_id": state.get("document_id", ""),
        "canonical_entity_map": canonical_entity_map,
        "operations": operations,
        "operation_count": len(operations),
        "impact_domain_seed": _merge_declared_impact_domains(operations),
        "protection_profile": (
            "evidence-contract-coupled impact queries with minimal compensation"
        ),
    }


def _evaluate_patch(
    patch: dict[str, Any],
    baseline: dict[str, Any],
) -> dict[str, Any]:
    operations = list(patch.get("operations", []))
    first = _apply_shadow(operations, baseline)
    frozen_impact_domain = first["impact_domain"]
    second = _apply_shadow(
        operations,
        baseline,
        frozen_impact_domain=frozen_impact_domain,
    )
    deterministic_replay = _snapshot_hash(first["snapshot"]) == _snapshot_hash(
        second["snapshot"]
    )

    failed = _verify_failed_query_attributions(
        operations,
        baseline,
        first["failed_queries"],
        frozen_impact_domain,
    )
    failed_by_query_id = {
        str(item.get("query_id", "")): item for item in failed
    }
    attributed_query_results = [
        failed_by_query_id.get(str(item.get("query_id", "")), item)
        for item in first["query_results"]
    ]
    compensation_plan = _minimum_cost_compensation(
        operations,
        baseline,
        failed,
        frozen_impact_domain,
    )
    compensation_ids = set(compensation_plan["operation_ids"])
    accepted_ids = [
        str(item.get("operation_id", ""))
        for item in operations
        if str(item.get("operation_id", "")) not in compensation_ids
    ]
    accepted_operations = [
        item
        for item in operations
        if str(item.get("operation_id", "")) in set(accepted_ids)
    ]
    compensated = _apply_shadow(
        accepted_operations,
        baseline,
        frozen_impact_domain=frozen_impact_domain,
    )
    retained_impact_domain = _derive_impact_domain(
        accepted_operations,
        baseline,
    )
    utility = (
        0.3 * compensated["metrics"]["entity_gain"]
        + 0.6 * compensated["metrics"]["relation_gain"]
        + 0.2 * compensated["metrics"]["evidence_gain"]
        - 1.0 * len(compensation_ids)
        - 1.5 * len(compensated["failed_queries"])
    )
    result = {
        "passed": not failed,
        "passed_after_compensation": not compensated["failed_queries"],
        "deterministic_replay": deterministic_replay,
        "non_interference_passed": compensated["non_interference_passed"],
        "generated_query_count": len(first["query_results"]),
        "query_results": attributed_query_results,
        "failed_queries": failed,
        "accepted_operation_ids": accepted_ids,
        "compensation_operation_ids": sorted(compensation_ids),
        "minimal_compensation_patch": [
            {
                "action": "exclude_operation",
                "operation_id": operation_id,
                "causal_failed_query_ids": [
                    item["query_id"]
                    for item in failed
                    if operation_id in item.get("caused_by_operation_ids", [])
                ],
                "selection_basis": (
                    "failed_query_cause"
                    if any(
                        operation_id in item.get("caused_by_operation_ids", [])
                        for item in failed
                    )
                    else "dependency_closure"
                ),
            }
            for operation_id in sorted(compensation_ids)
        ],
        "compensation_solver": compensation_plan,
        "impact_domain": frozen_impact_domain,
        "retained_impact_domain": retained_impact_domain,
        "original_impact_domain": first["impact_domain"],
        "metrics": compensated["metrics"],
        "utility": round(utility, 4),
        "shadow_snapshot_hash": _snapshot_hash(compensated["snapshot"]),
    }
    result["causal_validation_certificate"] = _build_validation_certificate(
        patch,
        baseline,
        result,
    )
    return result


def _verify_failed_query_attributions(
    operations: list[dict[str, Any]],
    baseline: dict[str, Any],
    failed_queries: list[dict[str, Any]],
    frozen_impact_domain: dict[str, Any],
) -> list[dict[str, Any]]:
    """Verify operation-to-failure links by dependency-closed counterfactual replay.

    A linked operation is treated as a counterfactual exclusion seed only when
    removing that operation together with relation operations that depend on an
    excluded entity makes the target query no longer fail on the same baseline.
    """
    operation_ids = {
        str(item.get("operation_id", "")) for item in operations
    }
    verified_queries: list[dict[str, Any]] = []
    for query in failed_queries:
        attributed_ids = sorted(
            {
                str(value)
                for value in query.get("caused_by_operation_ids", [])
                if str(value) in operation_ids
            }
        )
        counterfactual_checks: list[dict[str, Any]] = []
        verified_ids: list[str] = []
        for operation_id in attributed_ids:
            exclusion_closure = _dependency_closed_exclusions(
                {operation_id},
                operations,
            )
            replay = _replay_without(
                operations,
                baseline,
                exclusion_closure,
                frozen_impact_domain,
            )
            target_still_fails = any(
                str(item.get("query_id", ""))
                == str(query.get("query_id", ""))
                and not bool(item.get("passed", False))
                for item in replay.get("query_results", [])
            )
            resolved = not target_still_fails
            counterfactual_checks.append(
                {
                    "operation_id": operation_id,
                    "exclusion_closure_ids": sorted(exclusion_closure),
                    "target_failure_resolved": resolved,
                }
            )
            if resolved:
                verified_ids.append(operation_id)
        verified = dict(query)
        verified["associated_operation_ids"] = attributed_ids
        verified["counterfactual_checks"] = counterfactual_checks
        verified["counterfactual_cause_operation_ids"] = verified_ids
        verified["caused_by_operation_ids"] = verified_ids
        verified["attribution_status"] = (
            "counterfactually_verified" if verified_ids else "unresolved"
        )
        verified_queries.append(verified)
    return verified_queries


def _build_validation_certificate(
    patch: dict[str, Any],
    baseline: dict[str, Any],
    evaluation: dict[str, Any],
) -> dict[str, Any]:
    """Bind the causal validation chain into a deterministic certificate.

    The certificate is not a cryptographic signature.  It is a content-addressed
    manifest that makes a gate decision invalid when its baseline, evidence-
    derived scope, query attribution, exclusion set, or retained patch changes.
    """
    operations = list(patch.get("operations", []))
    accepted_ids = sorted(
        str(value) for value in evaluation.get("accepted_operation_ids", [])
    )
    accepted_id_set = set(accepted_ids)
    retained_operations = [
        operation
        for operation in operations
        if str(operation.get("operation_id", "")) in accepted_id_set
    ]
    query_causality = sorted(
        [
            {
                "query_id": str(query.get("query_id", "")),
                "passed": bool(query.get("passed", False)),
                "caused_by_operation_ids": sorted(
                    str(value)
                    for value in query.get("caused_by_operation_ids", [])
                ),
                "associated_operation_ids": sorted(
                    str(value)
                    for value in query.get("associated_operation_ids", [])
                ),
                "counterfactual_cause_operation_ids": sorted(
                    str(value)
                    for value in query.get(
                        "counterfactual_cause_operation_ids", []
                    )
                ),
                "counterfactual_checks_hash": _snapshot_hash(
                    query.get("counterfactual_checks", [])
                ),
                "attribution_status": str(
                    query.get("attribution_status", "not_applicable")
                ),
                "impact_domain_hash": str(
                    query.get("impact_domain_hash", "")
                ),
            }
            for query in evaluation.get("query_results", [])
        ],
        key=lambda item: item["query_id"],
    )
    solver = evaluation.get("compensation_solver", {})
    payload = {
        "schema": "evolex.causal-validation-certificate.v1",
        "patch_id": str(patch.get("patch_id", "")),
        "parent_version_id": patch.get("parent_version_id"),
        "baseline_snapshot_hash": _snapshot_hash(baseline),
        "candidate_operations_hash": _snapshot_hash(operations),
        "original_impact_domain_hash": str(
            evaluation.get("original_impact_domain", {}).get("domain_hash", "")
        ),
        "frozen_impact_domain_hash": str(
            evaluation.get("impact_domain", {}).get("domain_hash", "")
        ),
        "retained_declared_impact_domain_hash": str(
            evaluation.get("retained_impact_domain", {}).get(
                "domain_hash", ""
            )
        ),
        "query_causality_hash": _snapshot_hash(query_causality),
        "query_causality": query_causality,
        "excluded_operation_ids": sorted(
            str(value)
            for value in evaluation.get("compensation_operation_ids", [])
        ),
        "solver_mode": str(solver.get("solver_mode", "")),
        "solver_optimality": str(solver.get("optimality", "")),
        "solver_result_hash": _snapshot_hash(solver),
        "accepted_operation_ids": accepted_ids,
        "retained_operations_hash": _snapshot_hash(retained_operations),
        "final_impact_domain_hash": str(
            evaluation.get("impact_domain", {}).get("domain_hash", "")
        ),
        "final_shadow_snapshot_hash": str(
            evaluation.get("shadow_snapshot_hash", "")
        ),
        "gate_results": {
            "impact_domain_evidence_grounded": bool(
                evaluation.get("impact_domain", {}).get(
                    "evidence_grounded", False
                )
            ),
            "deterministic_replay": bool(
                evaluation.get("deterministic_replay", False)
            ),
            "non_interference_passed": bool(
                evaluation.get("non_interference_passed", False)
            ),
            "passed_after_compensation": bool(
                evaluation.get("passed_after_compensation", False)
            ),
            "utility": float(evaluation.get("utility", 0.0)),
        },
    }
    return {
        **payload,
        "certificate_id": f"cvc-{_snapshot_hash(payload)}",
    }


def _validation_certificate_matches(
    patch: dict[str, Any],
    baseline: dict[str, Any],
    evaluation: dict[str, Any],
) -> bool:
    certificate = evaluation.get("causal_validation_certificate")
    if not isinstance(certificate, dict) or not certificate:
        return False
    return certificate == _build_validation_certificate(
        patch,
        baseline,
        evaluation,
    )


def _decision_matches_certificate(
    decision: dict[str, Any],
    evaluation: dict[str, Any],
) -> bool:
    certificate = evaluation.get("causal_validation_certificate", {})
    certificate_ids = sorted(
        str(value) for value in certificate.get("accepted_operation_ids", [])
    )
    evaluation_ids = sorted(
        str(value) for value in evaluation.get("accepted_operation_ids", [])
    )
    decision_ids = sorted(
        str(value) for value in decision.get("accepted_operation_ids", [])
    )
    return bool(decision.get("accepted")) and (
        decision_ids == evaluation_ids == certificate_ids
        and str(decision.get("certificate_id", ""))
        == str(certificate.get("certificate_id", ""))
    )


def _apply_shadow(
    operations: list[dict[str, Any]],
    baseline: dict[str, Any],
    *,
    frozen_impact_domain: dict[str, Any] | None = None,
) -> dict[str, Any]:
    impact_domain = (
        dict(frozen_impact_domain)
        if frozen_impact_domain is not None
        else _derive_impact_domain(operations, baseline)
    )
    entities = {
        str(item["canonical_id"]): dict(item)
        for item in baseline.get("entities", [])
    }
    relations = {
        str(item["canonical_relation_id"]): dict(item)
        for item in baseline.get("relations", [])
    }
    evidence_count_before = len(baseline.get("relation_evidence", []))
    evidence_count = evidence_count_before
    affected_entity_ids = set(impact_domain["entity_ids"])
    affected_relation_ids = set(impact_domain["relation_ids"])
    query_results: list[dict[str, Any]] = []

    for operation in operations:
        operation_id = str(operation.get("operation_id", ""))
        payload = dict(operation.get("after", {}))
        contract = operation.get("evidence_contract", {})
        if operation.get("object_type") == "entity":
            canonical_id = str(payload.get("canonical_id", ""))
            affected_entity_ids.add(canonical_id)
            entities[canonical_id] = payload
            query_results.extend(
                [
                    _query(
                        f"q:{operation_id}:entity_exists",
                        bool(canonical_id and canonical_id in entities),
                        [operation_id],
                        "canonical entity exists after patch",
                        impact_domain,
                    ),
                    _query(
                        f"q:{operation_id}:entity_provenance",
                        bool(contract.get("provenance_complete")),
                        [operation_id],
                        "entity evidence contract is complete",
                        impact_domain,
                    ),
                ]
            )
        elif operation.get("object_type") == "relation":
            relation_id = str(payload.get("canonical_relation_id", ""))
            affected_relation_ids.add(relation_id)
            subject = str(payload.get("subject_id", ""))
            obj = str(payload.get("object_id", ""))
            endpoints_exist = subject in entities and obj in entities
            if endpoints_exist:
                relations[relation_id] = payload
                evidence_count += len(operation.get("evidence", []))
            query_results.extend(
                [
                    _query(
                        f"q:{operation_id}:endpoints",
                        endpoints_exist,
                        [operation_id],
                        "relation endpoints resolve in the shadow graph",
                        impact_domain,
                    ),
                    _query(
                        f"q:{operation_id}:relation_provenance",
                        bool(contract.get("provenance_complete")),
                        [operation_id],
                        "relation evidence contract is complete",
                        impact_domain,
                    ),
                ]
            )

    relation_keys = [
        (
            item.get("subject_id"),
            item.get("predicate"),
            item.get("object_id"),
            item.get("qualifiers_hash", ""),
        )
        for item in relations.values()
    ]
    duplicate_free = len(relation_keys) == len(set(relation_keys))
    relation_operation_ids = [
        str(item.get("operation_id", ""))
        for item in operations
        if item.get("object_type") == "relation"
    ]
    query_results.append(
        _query(
            "q:patch:canonical_relation_uniqueness",
            duplicate_free,
            relation_operation_ids,
            "canonical relation keys remain unique",
            impact_domain,
        )
    )

    baseline_unaffected = _unaffected_projection(
        baseline,
        affected_entity_ids,
        affected_relation_ids,
    )
    shadow_snapshot = {
        "entities": sorted(entities.values(), key=lambda item: str(item.get("canonical_id"))),
        "relations": sorted(
            relations.values(),
            key=lambda item: str(item.get("canonical_relation_id")),
        ),
    }
    shadow_unaffected = _unaffected_projection(
        shadow_snapshot,
        affected_entity_ids,
        affected_relation_ids,
    )
    non_interference = _snapshot_hash(baseline_unaffected) == _snapshot_hash(
        shadow_unaffected
    )
    query_results.append(
        _query(
            "q:patch:unaffected_subgraph_hash",
            non_interference,
            [str(item.get("operation_id", "")) for item in operations],
            "objects outside the evidence-derived impact domain are unchanged",
            impact_domain,
        )
    )
    failed_queries = [item for item in query_results if not item["passed"]]
    return {
        "snapshot": shadow_snapshot,
        "query_results": query_results,
        "failed_queries": failed_queries,
        "non_interference_passed": non_interference,
        "impact_domain": impact_domain,
        "metrics": {
            "entity_gain": len(entities) - len(baseline.get("entities", [])),
            "relation_gain": len(relations) - len(baseline.get("relations", [])),
            "evidence_gain": evidence_count - evidence_count_before,
            "failed_query_count": len(failed_queries),
        },
    }


def _minimum_cost_compensation(
    operations: list[dict[str, Any]],
    baseline: dict[str, Any],
    failed_queries: list[dict[str, Any]],
    frozen_impact_domain: dict[str, Any],
) -> dict[str, Any]:
    """Solve a causal, dependency-closed compensation problem.

    The exact solver enumerates the causal candidate space when it contains at
    most 16 operations.  Each candidate exclusion set is closed over relation
    dependencies and replayed against the same baseline.  Larger candidate
    spaces use a deterministic deletion-minimal fallback and are explicitly
    labelled as such rather than being presented as globally optimal.
    """
    if not failed_queries:
        return {
            "operation_ids": [],
            "solver_mode": "exact_enumeration",
            "optimality": "global_over_causal_candidate_space",
            "candidate_operation_ids": [],
            "candidate_count": 0,
            "evaluated_subset_count": 1,
            "objective": _compensation_objective([], operations),
            "constraints": {
                "all_invariants_pass": True,
                "dependency_closed": True,
                "non_interference_passed": True,
            },
        }

    operation_by_id = {
        str(item.get("operation_id", "")): item for item in operations
    }
    direct_causes = {
        str(operation_id)
        for query in failed_queries
        for operation_id in query.get("caused_by_operation_ids", [])
        if str(operation_id) in operation_by_id
    }
    candidate_ids = _dependency_closed_exclusions(
        direct_causes,
        operations,
    )
    ordered_candidates = sorted(candidate_ids)
    evaluated = 0
    best_ids: set[str] | None = None
    best_objective: dict[str, float] | None = None
    fallback_pass_count = 0

    if len(ordered_candidates) <= 16:
        seen_closed_sets: set[tuple[str, ...]] = set()
        for size in range(len(ordered_candidates) + 1):
            for selected in combinations(ordered_candidates, size):
                closed = _dependency_closed_exclusions(
                    set(selected),
                    operations,
                )
                marker = tuple(sorted(closed))
                if marker in seen_closed_sets:
                    continue
                seen_closed_sets.add(marker)
                evaluated += 1
                replay = _replay_without(
                    operations,
                    baseline,
                    closed,
                    frozen_impact_domain,
                )
                if replay["failed_queries"] or not replay["non_interference_passed"]:
                    continue
                objective = _compensation_objective(closed, operations)
                if best_objective is None or _objective_key(objective) < _objective_key(
                    best_objective
                ):
                    best_ids = closed
                    best_objective = objective
        solver_mode = "exact_enumeration"
        optimality = "global_over_causal_candidate_space"
    else:
        best_ids = set(candidate_ids)
        changed = True
        while changed:
            changed = False
            fallback_pass_count += 1
            for operation_id in sorted(set(best_ids)):
                trial = _dependency_closed_exclusions(
                    best_ids - {operation_id},
                    operations,
                )
                if trial == best_ids:
                    continue
                evaluated += 1
                replay = _replay_without(
                    operations,
                    baseline,
                    trial,
                    frozen_impact_domain,
                )
                if (
                    not replay["failed_queries"]
                    and replay["non_interference_passed"]
                ):
                    best_ids = trial
                    changed = True
        best_objective = _compensation_objective(best_ids, operations)
        solver_mode = "deterministic_fixed_point_deletion_fallback"
        optimality = "single_deletion_local_minimum_not_global"

    if best_ids is None:
        best_ids = _dependency_closed_exclusions(direct_causes, operations)
        best_objective = _compensation_objective(best_ids, operations)
        solver_mode = "causal_closure_fallback"
        optimality = "feasibility_not_proven"

    final_replay = _replay_without(
        operations,
        baseline,
        best_ids,
        frozen_impact_domain,
    )
    return {
        "operation_ids": sorted(best_ids),
        "solver_mode": solver_mode,
        "optimality": optimality,
        "candidate_operation_ids": ordered_candidates,
        "candidate_count": len(ordered_candidates),
        "evaluated_subset_count": evaluated,
        "fallback_pass_count": fallback_pass_count,
        "objective": best_objective,
        "objective_formula": (
            "1.0*excluded_operations + 0.05*blast_radius "
            "+ 0.02*evidence_loss"
        ),
        "constraints": {
            "all_invariants_pass": not final_replay["failed_queries"],
            "dependency_closed": _is_dependency_closed(best_ids, operations),
            "non_interference_passed": final_replay["non_interference_passed"],
        },
    }


def _replay_without(
    operations: list[dict[str, Any]],
    baseline: dict[str, Any],
    excluded_ids: set[str],
    frozen_impact_domain: dict[str, Any],
) -> dict[str, Any]:
    remaining = [
        item
        for item in operations
        if str(item.get("operation_id", "")) not in excluded_ids
    ]
    return _apply_shadow(
        remaining,
        baseline,
        frozen_impact_domain=frozen_impact_domain,
    )


def _dependency_closed_exclusions(
    selected_ids: set[str],
    operations: list[dict[str, Any]],
) -> set[str]:
    excluded = set(selected_ids)
    changed = True
    while changed:
        changed = False
        excluded_entity_ids = {
            str(item.get("object_id", ""))
            for item in operations
            if str(item.get("operation_id", "")) in excluded
            and item.get("object_type") == "entity"
        }
        for operation in operations:
            operation_id = str(operation.get("operation_id", ""))
            if operation_id in excluded or operation.get("object_type") != "relation":
                continue
            if excluded_entity_ids.intersection(
                str(value)
                for value in operation.get("depends_on_entity_ids", [])
            ):
                excluded.add(operation_id)
                changed = True
    return excluded


def _is_dependency_closed(
    excluded_ids: set[str],
    operations: list[dict[str, Any]],
) -> bool:
    return _dependency_closed_exclusions(excluded_ids, operations) == excluded_ids


def _compensation_objective(
    excluded_ids,
    operations: list[dict[str, Any]],
) -> dict[str, float]:
    excluded = set(excluded_ids)
    selected = [
        item
        for item in operations
        if str(item.get("operation_id", "")) in excluded
    ]
    blast_radius = sum(
        len(set(item.get("affected_domain", {}).get("entity_ids", [])))
        + len(set(item.get("affected_domain", {}).get("relation_ids", [])))
        + len(set(item.get("affected_domain", {}).get("predicates", [])))
        for item in selected
    )
    evidence_loss = sum(
        len(item.get("evidence", []))
        + len(item.get("mentions", []))
        + len(item.get("evidence_contract", {}).get("evidence_ids", []))
        for item in selected
    )
    edit_count = len(excluded)
    weighted_cost = edit_count + 0.05 * blast_radius + 0.02 * evidence_loss
    retained_confidence = sum(
        float(item.get("after", {}).get("confidence", 0.0))
        for item in operations
        if str(item.get("operation_id", "")) not in excluded
    )
    return {
        "weighted_cost": round(weighted_cost, 6),
        "excluded_operation_count": float(edit_count),
        "blast_radius": float(blast_radius),
        "evidence_loss": float(evidence_loss),
        "retained_confidence": round(retained_confidence, 6),
    }


def _objective_key(objective: dict[str, float]) -> tuple[float, float, float, float]:
    return (
        float(objective["weighted_cost"]),
        float(objective["excluded_operation_count"]),
        float(objective["evidence_loss"]),
        -float(objective["retained_confidence"]),
    )


def _merge_declared_impact_domains(
    operations: list[dict[str, Any]],
) -> dict[str, Any]:
    merged: dict[str, set[str]] = {
        "entity_ids": set(),
        "entity_types": set(),
        "predicates": set(),
        "relation_ids": set(),
        "source_document_ids": set(),
        "source_segment_ids": set(),
        "evidence_ids": set(),
        "operation_ids": set(),
    }
    bases: set[str] = set()
    for operation in operations:
        operation_id = str(operation.get("operation_id", ""))
        if operation_id:
            merged["operation_ids"].add(operation_id)
        domain = operation.get("affected_domain", {})
        for key in (
            "entity_ids",
            "entity_types",
            "predicates",
            "relation_ids",
            "source_document_ids",
            "source_segment_ids",
            "evidence_ids",
        ):
            merged[key].update(
                str(value) for value in domain.get(key, []) if str(value)
            )
        basis = str(domain.get("basis", "")).strip()
        if basis:
            bases.add(basis)
    return {
        key: sorted(values) for key, values in merged.items()
    } | {"basis": sorted(bases)}


def _derive_impact_domain(
    operations: list[dict[str, Any]],
    baseline: dict[str, Any],
) -> dict[str, Any]:
    """Expand evidence-declared patch scope through graph endpoint dependencies."""
    domain = _merge_declared_impact_domains(operations)
    entity_ids = set(domain["entity_ids"])
    relation_ids = set(domain["relation_ids"])
    predicates = set(domain["predicates"])
    basis_records: list[dict[str, Any]] = []

    for operation in operations:
        payload = operation.get("after", {})
        contract = operation.get("evidence_contract", {})
        object_type = operation.get("object_type")
        if object_type == "entity":
            canonical_id = str(payload.get("canonical_id", ""))
            if canonical_id:
                entity_ids.add(canonical_id)
        elif object_type == "relation":
            relation_id = str(payload.get("canonical_relation_id", ""))
            if relation_id:
                relation_ids.add(relation_id)
            for key in ("subject_id", "object_id"):
                entity_id = str(payload.get(key, ""))
                if entity_id:
                    entity_ids.add(entity_id)
            predicate = str(payload.get("predicate", ""))
            if predicate:
                predicates.add(predicate)
        basis_records.append(
            {
                "operation_id": str(operation.get("operation_id", "")),
                "source_document_ids": sorted(
                    str(value)
                    for value in contract.get("source_document_ids", [])
                    if str(value)
                ),
                "source_segment_ids": sorted(
                    str(value)
                    for value in (
                        contract.get("source_segment_ids", [])
                        or operation.get("affected_domain", {}).get(
                            "source_segment_ids", []
                        )
                    )
                    if str(value)
                ),
                "evidence_ids": sorted(
                    str(value)
                    for value in contract.get("evidence_ids", [])
                    if str(value)
                ),
                "provenance_complete": bool(
                    contract.get("provenance_complete")
                ),
            }
        )

    # One-hop expansion is deterministic: any baseline edge incident to a
    # declared endpoint, explicitly named relation, or declared predicate is
    # part of the blast radius; its opposite endpoint is included as well.
    for relation in baseline.get("relations", []):
        relation_id = str(relation.get("canonical_relation_id", ""))
        subject_id = str(relation.get("subject_id", ""))
        object_id = str(relation.get("object_id", ""))
        predicate = str(relation.get("predicate", ""))
        if (
            relation_id in relation_ids
            or subject_id in entity_ids
            or object_id in entity_ids
            or predicate in predicates
        ):
            relation_ids.add(relation_id)
            entity_ids.update((subject_id, object_id))

    result = {
        **domain,
        "entity_ids": sorted(value for value in entity_ids if value),
        "relation_ids": sorted(value for value in relation_ids if value),
        "predicates": sorted(value for value in predicates if value),
        "basis_records": basis_records,
        "evidence_grounded": all(
            record["provenance_complete"]
            and record["source_document_ids"]
            and (record["source_segment_ids"] or record["evidence_ids"])
            for record in basis_records
        )
        if basis_records
        else True,
        "expansion_rule": (
            "declared evidence scope plus one-hop endpoint and predicate dependency"
        ),
    }
    result["domain_hash"] = _snapshot_hash(result)
    return result


def _unaffected_projection(
    snapshot: dict[str, Any],
    affected_entity_ids: set[str],
    affected_relation_ids: set[str],
) -> dict[str, Any]:
    return {
        "entities": [
            item
            for item in snapshot.get("entities", [])
            if str(item.get("canonical_id", "")) not in affected_entity_ids
        ],
        "relations": [
            item
            for item in snapshot.get("relations", [])
            if str(item.get("canonical_relation_id", ""))
            not in affected_relation_ids
        ],
    }


def _query(
    query_id: str,
    passed: bool,
    operation_ids: list[str],
    description: str,
    impact_domain: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = {
        "query_id": query_id,
        "passed": bool(passed),
        "description": description,
        "caused_by_operation_ids": _unique(operation_ids),
    }
    if impact_domain is not None:
        result["impact_domain_hash"] = impact_domain.get("domain_hash", "")
    return result


def _vote(agent_name: str, approve: bool, basis: str) -> dict[str, Any]:
    return {
        "agent_name": agent_name,
        "approve": bool(approve),
        "basis": basis,
    }


def _stable_id(prefix: str, value: str) -> str:
    return f"{prefix}-{sha256(value.encode()).hexdigest()[:16]}"


def _normalize(value: str) -> str:
    normalized = " ".join(value.casefold().replace("_", " ").split())
    return ALIAS_CANONICAL.get(normalized, normalized)


def _snapshot_hash(snapshot: dict[str, Any]) -> str:
    encoded = json.dumps(
        snapshot,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(encoded.encode()).hexdigest()


def _unique(values):
    result = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


def _unique_dicts(values: list[dict], key: str) -> list[dict]:
    result: list[dict] = []
    seen: set[str] = set()
    for value in values:
        marker = str(value.get(key, ""))
        if marker in seen:
            continue
        seen.add(marker)
        result.append(value)
    return result
