from __future__ import annotations

from evolex.graph.state import GraphState

DEFAULT_MIN_SCORE = 0.3


def make_quality_review_node(min_score: float = DEFAULT_MIN_SCORE):
    """Create a quality review node that scores and filters atoms and relations.

    Checks applied:
    - Low confidence: atom confidence < 0.5
    - Trivial text: atom text fewer than 3 characters
    - Duplicate detection: atoms with identical (text, type), lower-confidence flagged
    - Dangling reference: relation references non-existent entity_id
    - Threshold filter: items with adjusted_confidence below min_score are removed
    """

    def quality_review_node(state: GraphState) -> dict:
        atoms: list[dict] = list(state.get("semantic_atoms", []))
        relations: list[dict] = list(state.get("relations", []))
        entities: list[dict] = state.get("entities", [])

        quality_scores: list[dict] = []
        entity_ids = {ent["entity_id"] for ent in entities}

        # --- Review atoms ---
        seen_text_type: dict[tuple[str, str], int] = {}  # (text, type) -> first_seen_index
        surviving_atoms: list[dict] = []

        for idx, atom in enumerate(atoms):
            issues: list[str] = []
            confidence = atom.get("confidence", 0.5)
            adjusted = confidence

            # Low confidence check
            if confidence < 0.5:
                issues.append("low_confidence")
                adjusted = max(adjusted, confidence)  # keep original for scoring

            # Trivial text check
            text = str(atom.get("text", ""))
            if len(text.strip()) < 3:
                issues.append("trivial_text")
                adjusted = min(adjusted, 0.2)

            # Duplicate check
            text_type_key = (text.strip().lower(), atom.get("type", "claim"))
            if text_type_key in seen_text_type:
                issues.append("duplicate")
                adjusted = min(adjusted, 0.25)
            else:
                seen_text_type[text_type_key] = idx

            quality_scores.append({
                "target_type": "atom",
                "target_index": idx,
                "score": round(adjusted, 2),
                "issues": issues,
                "adjusted_confidence": round(adjusted, 2),
            })

            if adjusted >= min_score:
                surviving_atoms.append(atom)

        # --- Review relations ---
        surviving_relations: list[dict] = []
        for idx, rel in enumerate(relations):
            issues: list[str] = []
            confidence = rel.get("confidence", 0.5)
            adjusted = confidence

            # Dangling reference check
            subj = rel.get("subject_entity_id", "")
            obj = rel.get("object_entity_id", "")
            if subj and subj not in entity_ids:
                issues.append("dangling_subject_reference")
                adjusted = min(adjusted, 0.2)
            if obj and obj not in entity_ids:
                issues.append("dangling_object_reference")
                adjusted = min(adjusted, 0.2)

            quality_scores.append({
                "target_type": "relation",
                "target_index": idx,
                "score": round(adjusted, 2),
                "issues": issues,
                "adjusted_confidence": round(adjusted, 2),
            })

            if adjusted >= min_score:
                surviving_relations.append(rel)

        # Determine status — preserve "failed" from earlier nodes
        existing_status: str = state.get("status", "candidate")
        if existing_status == "failed":
            status = "failed"
        elif not surviving_atoms and atoms:
            status = "quarantined"
        else:
            status = existing_status

        return {
            "semantic_atoms": surviving_atoms,
            "relations": surviving_relations,
            "quality_scores": quality_scores,
            "status": status,
        }

    return quality_review_node
