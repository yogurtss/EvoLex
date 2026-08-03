from __future__ import annotations

import re
from itertools import combinations
from typing import Any

from evolex.graph.state import GraphState


ALIAS_CANONICAL: dict[str, str] = {
    "api gw": "api gateway",
    "api_gw": "api gateway",
    "apigw": "api gateway",
    "application programming interface gateway": "api gateway",
    "kg": "knowledge graph",
    "kgs": "knowledge graph",
    "llm": "large language model",
    "llms": "large language model",
}
AUTO_MERGE_THRESHOLD = 0.90
PROPOSAL_THRESHOLD = 0.65


def entity_merge_node(state: GraphState) -> dict:
    """Propose and apply evidence-constrained, same-type entity merges.

    Exact mention linking remains the resolver's job.  This node handles
    canonical equivalence that requires an explicit Agent decision (aliases,
    acronyms, and high-overlap variants).  Every accepted merge retains the
    source IDs and a contract describing why it was safe.
    """
    entities = [dict(item) for item in state.get("entities", [])]
    if len(entities) < 2:
        return {
            "entities": entities,
            "entity_merge_proposals": [],
            "merge_decisions": list(state.get("merge_decisions", [])),
            "mention_entity_map": dict(state.get("mention_entity_map", {})),
        }

    proposals: list[dict[str, Any]] = []
    eligible_pairs: list[tuple[str, str]] = []
    for left, right in combinations(entities, 2):
        same_type = str(left.get("type", "")) == str(right.get("type", ""))
        lexical_score, match_reason = _entity_similarity(left, right)
        if not same_type or lexical_score < PROPOSAL_THRESHOLD:
            continue
        provenance_complete = bool(left.get("source_mention_ids")) and bool(
            right.get("source_mention_ids")
        )
        accepted = lexical_score >= AUTO_MERGE_THRESHOLD and provenance_complete
        proposal = {
            "proposal_id": f"em-{len(proposals) + 1:04d}",
            "proposal_type": "entity_merge",
            "source_entity_id": right.get("entity_id", ""),
            "target_entity_id": left.get("entity_id", ""),
            "source_text": right.get("canonical_text", ""),
            "target_text": left.get("canonical_text", ""),
            "entity_type": left.get("type", ""),
            "score": round(lexical_score, 4),
            "status": "accepted" if accepted else "held",
            "reason": match_reason,
            "evidence_contract": {
                "same_type": same_type,
                "lexical_equivalence": round(lexical_score, 4),
                "provenance_complete": provenance_complete,
                "source_mention_count": len(
                    set(left.get("source_mention_ids", []))
                    | set(right.get("source_mention_ids", []))
                ),
                "independent_segment_count": len(
                    set(left.get("segment_ids", []))
                    | set(right.get("segment_ids", []))
                ),
            },
            "agent_name": "EntityCanonicalizationAgent",
        }
        proposals.append(proposal)
        if accepted:
            eligible_pairs.append(
                (str(right.get("entity_id", "")), str(left.get("entity_id", "")))
            )

    parent = {str(entity.get("entity_id", "")): str(entity.get("entity_id", "")) for entity in entities}

    def find(entity_id: str) -> str:
        while parent.get(entity_id, entity_id) != entity_id:
            parent[entity_id] = parent[parent[entity_id]]
            entity_id = parent[entity_id]
        return entity_id

    entity_by_id = {
        str(entity.get("entity_id", "")): entity for entity in entities
    }
    cluster_members = {
        str(entity.get("entity_id", "")): {str(entity.get("entity_id", ""))}
        for entity in entities
    }
    for source_id, target_id in eligible_pairs:
        source_root = find(source_id)
        target_root = find(target_id)
        if source_root == target_root:
            continue
        source_members = cluster_members[source_root]
        target_members = cluster_members[target_root]
        complete_link_safe = all(
            entity_by_id[left_id].get("type") == entity_by_id[right_id].get("type")
            and _entity_similarity(
                entity_by_id[left_id],
                entity_by_id[right_id],
            )[0] >= AUTO_MERGE_THRESHOLD
            for left_id in source_members
            for right_id in target_members
        )
        if not complete_link_safe:
            continue
        parent[source_root] = target_root
        cluster_members[target_root] = source_members | target_members
        del cluster_members[source_root]

    for proposal in proposals:
        source_id = str(proposal.get("source_entity_id", ""))
        target_id = str(proposal.get("target_entity_id", ""))
        if proposal["status"] == "accepted" and find(source_id) != find(target_id):
            proposal["status"] = "held"
            proposal["reason"] = "blocked_by_complete_link_cluster_constraint"

    grouped: dict[str, list[dict]] = {}
    for entity in entities:
        grouped.setdefault(find(str(entity.get("entity_id", ""))), []).append(entity)

    merged_entities: list[dict] = []
    for root_id, members in grouped.items():
        target = dict(next(item for item in members if item.get("entity_id") == root_id))
        target["aliases"] = _unique(
            value
            for item in members
            for value in [item.get("canonical_text", ""), *item.get("aliases", [])]
            if value
        )
        target["source_entity_ids"] = _unique(
            str(item.get("entity_id", "")) for item in members if item.get("entity_id")
        )
        target["source_mention_ids"] = _unique(
            value for item in members for value in item.get("source_mention_ids", [])
        )
        target["source_mention_indices"] = _unique(
            value for item in members for value in item.get("source_mention_indices", [])
        )
        target["source_atom_indices"] = _unique(
            value for item in members for value in item.get("source_atom_indices", [])
        )
        target["segment_ids"] = _unique(
            value for item in members for value in item.get("segment_ids", [])
        )
        target["merged_count"] = sum(int(item.get("merged_count", 1)) for item in members)
        target["confidence"] = round(
            max(float(item.get("confidence", 0.5)) for item in members),
            4,
        )
        merged_entities.append(target)

    remap = {entity_id: find(entity_id) for entity_id in parent}
    decisions = []
    for raw in state.get("entity_decisions", []):
        decision = dict(raw)
        old_target = str(decision.get("target_entity_id", ""))
        new_target = remap.get(old_target, old_target)
        if old_target and new_target != old_target:
            decision["target_entity_id"] = new_target
            decision["decision"] = "LINK"
            decision["reason"] = f"agent_same_type_merge:{old_target}->{new_target}"
        decisions.append(decision)

    mention_entity_map = {
        str(item.get("mention_id", "")): str(item.get("target_entity_id", ""))
        for item in decisions
        if item.get("mention_id")
        and item.get("target_entity_id")
        and item.get("decision") in {"LINK", "CREATE_CANDIDATE"}
    }
    merge_decisions = list(state.get("merge_decisions", []))
    merge_decisions.extend(
        {
            "object_type": "entity",
            "action": "MERGE" if proposal["status"] == "accepted" else "HOLD",
            **proposal,
        }
        for proposal in proposals
    )
    return {
        "entities": merged_entities,
        "entity_decisions": decisions,
        "mention_entity_map": mention_entity_map,
        "entity_merge_proposals": proposals,
        "merge_decisions": merge_decisions,
    }


def _entity_similarity(left: dict, right: dict) -> tuple[float, str]:
    left_text = _basic_normalize(str(left.get("canonical_text", "")))
    right_text = _basic_normalize(str(right.get("canonical_text", "")))
    if not left_text or not right_text:
        return 0.0, "empty_normalized_text"
    if left_text == right_text:
        return 1.0, "exact_normalized_match"

    left_alias = ALIAS_CANONICAL.get(left_text, left_text)
    right_alias = ALIAS_CANONICAL.get(right_text, right_text)
    if left_alias == right_alias:
        return 0.97, "curated_alias_equivalence"

    if _acronym(left_alias) == right_alias.replace(" ", "") or _acronym(
        right_alias
    ) == left_alias.replace(" ", ""):
        return 0.92, "acronym_equivalence"

    left_tokens = set(left_alias.split())
    right_tokens = set(right_alias.split())
    union = left_tokens | right_tokens
    jaccard = len(left_tokens & right_tokens) / len(union) if union else 0.0
    if jaccard >= 0.8:
        return 0.84 + 0.08 * jaccard, "high_token_overlap"
    if jaccard >= 0.5:
        return 0.65 + 0.15 * jaccard, "candidate_token_overlap"
    return jaccard, "insufficient_equivalence"


def _basic_normalize(text: str) -> str:
    normalized = text.casefold().strip()
    normalized = re.sub(r"[_\-/]+", " ", normalized)
    normalized = "".join(
        character if character.isalnum() or character.isspace() else " "
        for character in normalized
    )
    return re.sub(r"\s+", " ", normalized).strip()


def _acronym(text: str) -> str:
    return "".join(token[0] for token in text.split() if token)


def _unique(values):
    result = []
    for value in values:
        if value not in result:
            result.append(value)
    return result
