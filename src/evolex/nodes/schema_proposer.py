from __future__ import annotations

from evolex.graph.state import GraphState


def schema_proposer_node(state: GraphState) -> dict:
    """Generate schema proposals from unresolved terms.

    Groups unresolved terms by category and produces typed schema proposals
    (new_type, new_relation, new_parameter) with supporting evidence.
    """
    unresolved = state.get("unresolved_terms", [])
    if not unresolved:
        return {"schema_proposals": []}

    schema_version = state.get("schema_version", "")
    proposals: list[dict] = []
    proposal_num = 0

    # Group by category
    by_category: dict[str, list[dict]] = {}
    for term in unresolved:
        category = term.get("category", "unknown")
        by_category.setdefault(category, []).append(term)

    for category, terms in by_category.items():
        proposal_num += 1
        texts = [t.get("term", "") for t in terms if t.get("term")]
        unique_texts = sorted(set(texts))

        if category.startswith("mention_type:"):
            # New type proposal
            proposals.append({
                "proposal_id": f"scp-{proposal_num:04d}",
                "proposal_type": "new_type",
                "name": category.split(":", 1)[1] if ":" in category else unique_texts[0],
                "description": f"New schema type inferred from mentions: {', '.join(unique_texts[:5])}",
                "supporting_texts": unique_texts[:10],
                "evidence_spans": [t.get("evidence", "") for t in terms],
                "occurrence_count": len(terms),
                "independent_document_count": 1,
                "relation_pattern_consistency": 0.0,
                "evidence_coverage": 0.0,
                "source_run_ids": [state.get("run_id", "")],
                "schema_version": schema_version,
            })
        elif category == "predicate":
            # New relation proposal
            proposals.append({
                "proposal_id": f"scp-{proposal_num:04d}",
                "proposal_type": "new_relation",
                "name": unique_texts[0],
                "description": f"New relation predicate inferred from claims: {', '.join(unique_texts[:5])}",
                "supporting_texts": [t.get("context", "") for t in terms],
                "evidence_spans": [str(t.get("evidence", "")) for t in terms],
                "occurrence_count": len(terms),
                "independent_document_count": 1,
                "relation_pattern_consistency": 0.0,
                "evidence_coverage": 0.0,
                "source_run_ids": [state.get("run_id", "")],
                "schema_version": schema_version,
            })
        elif category == "new_parameter":
            # New attribute / parameter proposal
            proposals.append({
                "proposal_id": f"scp-{proposal_num:04d}",
                "proposal_type": "new_attribute",
                "name": unique_texts[0],
                "description": f"New measurement parameter: {', '.join(unique_texts[:5])}",
                "supporting_texts": [t.get("context", "") for t in terms],
                "evidence_spans": [str(t.get("evidence", "")) for t in terms],
                "occurrence_count": len(terms),
                "independent_document_count": 1,
                "relation_pattern_consistency": 0.0,
                "evidence_coverage": 0.0,
                "source_run_ids": [state.get("run_id", "")],
                "schema_version": schema_version,
            })

    return {
        "schema_proposals": proposals,
    }
