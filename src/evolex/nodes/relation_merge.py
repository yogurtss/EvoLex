from __future__ import annotations

import json
import math
from collections import defaultdict
from hashlib import sha256
from typing import Any

from evolex.graph.state import GraphState


PREDICATE_ALIASES: dict[str, str] = {
    "rely_on": "depends_on",
    "relies_on": "depends_on",
    "requires": "depends_on",
    "dependent_on": "depends_on",
    "is_part_of": "part_of",
    "belongs_to": "part_of",
    "has_measurement_value": "has_measurement",
    "measured_at": "has_measurement",
    "associated_with": "related_to",
}
SYMMETRIC_PREDICATES = {"related_to", "associated_with", "interacts_with"}
FUNCTIONAL_PREDICATES = {"has_status", "has_version", "located_in", "has_owner"}


def canonicalize_predicate(value: str) -> str:
    normalized = value.casefold().strip().replace(" ", "_")
    return PREDICATE_ALIASES.get(normalized, normalized)


def relation_merge_node(state: GraphState) -> dict:
    """Canonicalize relation types and merge duplicate evidence assertions.

    The merged relation remains a reversible identity hypothesis: all source
    relation IDs, candidate IDs, evidence IDs, and predicate aliases are kept.
    A later conflict or rollback can therefore reconstruct the pre-merge set.
    """
    raw_relations = [dict(item) for item in state.get("relations", [])]
    grouped: dict[tuple[str, str, str, str], list[dict]] = defaultdict(list)
    for relation in raw_relations:
        original_predicate = str(relation.get("predicate", "related_to"))
        predicate = canonicalize_predicate(original_predicate)
        subject = str(relation.get("subject_entity_id", ""))
        obj = str(relation.get("object_entity_id", ""))
        if predicate in SYMMETRIC_PREDICATES and obj < subject:
            subject, obj = obj, subject
        qualifiers = relation.get("qualifiers", {})
        qualifiers_hash = str(relation.get("qualifiers_hash", "")).strip()
        if not qualifiers_hash and qualifiers:
            qualifiers_hash = _qualifier_hash(qualifiers)
        relation["predicate"] = predicate
        relation["original_predicate"] = original_predicate
        relation["subject_entity_id"] = subject
        relation["object_entity_id"] = obj
        relation["qualifiers"] = qualifiers
        relation["qualifiers_hash"] = qualifiers_hash
        grouped[(subject, predicate, obj, qualifiers_hash)].append(relation)

    merged_relations: list[dict] = []
    proposals: list[dict[str, Any]] = []
    merge_decisions = list(state.get("merge_decisions", []))
    for key, members in grouped.items():
        subject, predicate, obj, qualifiers_hash = key
        qualifiers = members[0].get("qualifiers", {})
        source_ids = _unique(
            str(item.get("relation_id", "")) for item in members if item.get("relation_id")
        )
        source_candidate_ids = _unique(
            value
            for item in members
            for value in item.get("source_relation_candidate_ids", [])
            if value
        )
        evidence_ids = _unique(
            value for item in members for value in item.get("evidence_ids", []) if value
        )
        evidence_texts = _unique(
            str(item.get("evidence", "")) for item in members if item.get("evidence")
        )
        segment_ids = _unique(
            value for item in members for value in item.get("segment_ids", []) if value
        )
        predicate_aliases = _unique(
            str(item.get("original_predicate", predicate)) for item in members
        )
        source_assertions = [
            {
                "relation_id": str(item.get("relation_id", "")),
                "source_relation_candidate_ids": list(
                    item.get("source_relation_candidate_ids", [])
                ),
                "subject_entity_id": str(
                    item.get("subject_entity_id", "")
                ),
                "original_predicate": str(
                    item.get("original_predicate", predicate)
                ),
                "object_entity_id": str(
                    item.get("object_entity_id", "")
                ),
                "qualifiers": item.get("qualifiers", {}),
                "qualifiers_hash": str(
                    item.get("qualifiers_hash", "")
                ),
                "evidence_ids": list(item.get("evidence_ids", [])),
                "evidence": str(item.get("evidence", "")),
                "segment_ids": list(item.get("segment_ids", [])),
                "confidence": float(item.get("confidence", 0.5)),
            }
            for item in members
        ]
        independent_evidence = max(len(set(segment_ids)), 1)
        confidence = _aggregate_confidence(
            [float(item.get("confidence", 0.5)) for item in members],
            independent_evidence=independent_evidence,
        )
        hypothesis_id = f"rh-{len(merged_relations) + 1:04d}"
        merged_relations.append(
            {
                "relation_id": f"rel-{len(merged_relations) + 1:04d}",
                "subject_entity_id": subject,
                "predicate": predicate,
                "object_entity_id": obj,
                "qualifiers": qualifiers,
                "qualifiers_hash": qualifiers_hash,
                "evidence": evidence_texts[0] if evidence_texts else "",
                "evidence_texts": evidence_texts,
                "evidence_ids": evidence_ids,
                "segment_ids": segment_ids,
                "source_relation_ids": source_ids,
                "source_relation_candidate_ids": source_candidate_ids,
                "predicate_aliases": predicate_aliases,
                "source_assertions": source_assertions,
                "identity_hypothesis_id": hypothesis_id,
                "confidence": confidence,
                "extraction_mode": (
                    "joint"
                    if any(item.get("extraction_mode") == "joint" for item in members)
                    else members[0].get("extraction_mode", "fallback")
                ),
            }
        )
        if len(members) > 1 or any(alias != predicate for alias in predicate_aliases):
            proposal = {
                "proposal_id": f"rm-{len(proposals) + 1:04d}",
                "proposal_type": "relation_merge",
                "identity_hypothesis_id": hypothesis_id,
                "subject_entity_id": subject,
                "canonical_predicate": predicate,
                "object_entity_id": obj,
                "qualifiers_hash": qualifiers_hash,
                "source_relation_ids": source_ids,
                "source_relation_candidate_ids": source_candidate_ids,
                "predicate_aliases": predicate_aliases,
                "status": "accepted",
                "score": confidence,
                "evidence_contract": {
                    "endpoint_identity_preserved": True,
                    "independent_evidence_count": len(set(segment_ids)),
                    "evidence_anchor_count": len(set(evidence_ids)),
                    "source_relation_count": len(members),
                    "reversible": bool(source_ids or source_candidate_ids),
                    "source_assertion_count": len(source_assertions),
                },
                "agent_name": "RelationCanonicalizationAgent",
            }
            proposals.append(proposal)
            merge_decisions.append(
                {
                    "object_type": "relation",
                    "action": "MERGE",
                    **proposal,
                }
            )

    conflicts = _relation_conflicts(merged_relations)
    return {
        "relations": merged_relations,
        "relation_merge_proposals": proposals,
        "relation_identity_hypotheses": [
            {
                "identity_hypothesis_id": relation["identity_hypothesis_id"],
                "canonical_key": [
                    relation["subject_entity_id"],
                    relation["predicate"],
                    relation["object_entity_id"],
                    relation["qualifiers_hash"],
                ],
                "source_relation_ids": relation["source_relation_ids"],
                "source_relation_candidate_ids": relation[
                    "source_relation_candidate_ids"
                ],
                "evidence_ids": relation["evidence_ids"],
                "source_assertions": relation["source_assertions"],
                "reversible": True,
            }
            for relation in merged_relations
        ],
        "relation_conflicts": conflicts,
        "merge_decisions": merge_decisions,
    }


def _aggregate_confidence(values: list[float], independent_evidence: int) -> float:
    """Bounded noisy-OR with an independence discount."""
    if not values:
        return 0.0
    discounted = [
        max(0.0, min(1.0, value)) * (0.85 if index else 1.0)
        for index, value in enumerate(sorted(values, reverse=True))
    ]
    combined = 1.0 - math.prod(1.0 - value for value in discounted)
    independence_cap = min(0.99, max(values) + 0.08 * max(independent_evidence - 1, 0))
    return round(min(combined, independence_cap), 4)


def _relation_conflicts(relations: list[dict]) -> list[dict]:
    objects_by_key: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for relation in relations:
        predicate = str(relation.get("predicate", ""))
        if predicate in FUNCTIONAL_PREDICATES:
            key = (str(relation.get("subject_entity_id", "")), predicate)
            objects_by_key[key].append(relation)

    conflicts: list[dict] = []
    for (subject, predicate), members in objects_by_key.items():
        objects = {str(item.get("object_entity_id", "")) for item in members}
        if len(objects) <= 1:
            continue
        conflicts.append(
            {
                "conflict_id": f"rcf-{len(conflicts) + 1:04d}",
                "subject_entity_id": subject,
                "predicate": predicate,
                "object_entity_ids": sorted(objects),
                "evidence_ids": _unique(
                    value
                    for item in members
                    for value in item.get("evidence_ids", [])
                    if value
                ),
                "status": "unresolved",
                "agent_name": "RelationConflictAgent",
            }
        )
    return conflicts


def _qualifier_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return sha256(encoded.encode()).hexdigest()


def _unique(values):
    result = []
    for value in values:
        if value not in result:
            result.append(value)
    return result
