from __future__ import annotations

from collections import defaultdict
from typing import Any


def graph_metrics(state: dict[str, Any]) -> dict[str, float]:
    entities = state.get("entities", [])
    relations = state.get("relations", [])
    claims = state.get("claim_candidates", [])
    evidence_spans = state.get("evidence_spans", [])

    entity_count = len(entities)
    relation_count = len(relations)
    possible_directed_edges = max(entity_count * max(entity_count - 1, 0), 1)
    density = relation_count / possible_directed_edges

    evidence_coverage = len(evidence_spans) / max(len(claims), 1)
    relation_evidence_coverage = _relation_evidence_coverage(relations)
    conflict_score = _conflict_score(relations)
    consistency = max(0.0, 1.0 - conflict_score)
    schema_fit = _schema_fit_score(state)

    sparse_penalty = 1.0 if entity_count > 1 and relation_count == 0 else 0.0
    sparse_penalty = max(sparse_penalty, max(0.0, 0.05 - density) / 0.05)

    return {
        "graph_density": round(density, 4),
        "graph_sparse_penalty": round(min(1.0, sparse_penalty), 4),
        "relation_consistency": round(consistency, 4),
        "evidence_coverage": round(min(1.0, evidence_coverage), 4),
        "relation_evidence_coverage": round(relation_evidence_coverage, 4),
        "conflict_score": round(conflict_score, 4),
        "schema_fit_score": round(schema_fit, 4),
    }


def publish_confidence(state: dict[str, Any]) -> float:
    metrics = graph_metrics(state)
    quality_scores = state.get("quality_scores", [])
    if quality_scores:
        quality = sum(float(item.get("score", 0.5)) for item in quality_scores) / len(quality_scores)
    else:
        quality = 0.5
    confidence = (
        0.25 * metrics["evidence_coverage"]
        + 0.20 * metrics["relation_evidence_coverage"]
        + 0.20 * metrics["relation_consistency"]
        + 0.15 * metrics["schema_fit_score"]
        + 0.20 * quality
    )
    confidence -= 0.25 * metrics["graph_sparse_penalty"]
    return round(max(0.0, min(1.0, confidence)), 4)


def _relation_evidence_coverage(relations: list[dict]) -> float:
    if not relations:
        return 0.0
    with_evidence = [
        relation for relation in relations
        if str(relation.get("evidence", "")).strip()
    ]
    return len(with_evidence) / len(relations)


def _conflict_score(relations: list[dict]) -> float:
    if not relations:
        return 0.0
    objects_by_pair: dict[tuple[str, str], set[str]] = defaultdict(set)
    for relation in relations:
        key = (
            str(relation.get("subject_entity_id", "")),
            str(relation.get("predicate", "")),
        )
        objects_by_pair[key].add(str(relation.get("object_entity_id", "")))
    conflict_pairs = sum(1 for values in objects_by_pair.values() if len(values) > 1)
    return conflict_pairs / max(len(objects_by_pair), 1)


def _schema_fit_score(state: dict[str, Any]) -> float:
    objects = list(state.get("entities", [])) + list(state.get("relations", []))
    if not objects:
        return 0.5
    unresolved = len(state.get("unresolved_terms", []))
    return max(0.0, 1.0 - unresolved / max(len(objects), 1))
