from __future__ import annotations

from hashlib import sha256

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
    # Every schema symbol gets its own stability counter and proposal.
    grouped: dict[tuple[str, str], list[dict]] = {}
    for term in unresolved:
        category = str(term.get("category", "unknown"))
        if category.startswith("mention_type:"):
            symbol = category.split(":", 1)[1]
        else:
            symbol = _normalize_symbol(str(term.get("term", "")))
        if symbol:
            grouped.setdefault((category, symbol), []).append(term)

    for (category, symbol), terms in grouped.items():
        texts = [t.get("term", "") for t in terms if t.get("term")]
        unique_texts = sorted(set(texts))

        if category.startswith("mention_type:"):
            # New type proposal
            proposals.append({
                "proposal_id": _proposal_id("new_type", symbol),
                "proposal_type": "new_type",
                "name": symbol,
                "description": f"New schema type inferred from mentions: {', '.join(unique_texts[:5])}",
                "supporting_texts": unique_texts[:10],
                "evidence_spans": [t.get("evidence", "") for t in terms],
                "occurrence_count": len(terms),
                "independent_document_count": 1,
                "relation_pattern_consistency": 0.0,
                "evidence_coverage": 0.0,
                "source_run_ids": [state.get("run_id", "")],
                "source_document_ids": [state.get("document_id", "")],
                "schema_version": schema_version,
            })
        elif category == "predicate":
            # New relation proposal
            proposals.append({
                "proposal_id": _proposal_id("new_relation", symbol),
                "proposal_type": "new_relation",
                "name": symbol,
                "description": f"New relation predicate inferred from claims: {', '.join(unique_texts[:5])}",
                "supporting_texts": [t.get("context", "") for t in terms],
                "evidence_spans": [str(t.get("evidence", "")) for t in terms],
                "occurrence_count": len(terms),
                "independent_document_count": 1,
                "relation_pattern_consistency": 0.0,
                "evidence_coverage": 0.0,
                "source_run_ids": [state.get("run_id", "")],
                "source_document_ids": [state.get("document_id", "")],
                "schema_version": schema_version,
            })
        elif category == "new_parameter":
            # New attribute / parameter proposal
            proposals.append({
                "proposal_id": _proposal_id("new_attribute", symbol),
                "proposal_type": "new_attribute",
                "name": symbol,
                "description": f"New measurement parameter: {', '.join(unique_texts[:5])}",
                "supporting_texts": [t.get("context", "") for t in terms],
                "evidence_spans": [str(t.get("evidence", "")) for t in terms],
                "occurrence_count": len(terms),
                "independent_document_count": 1,
                "relation_pattern_consistency": 0.0,
                "evidence_coverage": 0.0,
                "source_run_ids": [state.get("run_id", "")],
                "source_document_ids": [state.get("document_id", "")],
                "schema_version": schema_version,
            })

    return {
        "schema_proposals": proposals,
    }


def _proposal_id(proposal_type: str, name: str) -> str:
    digest = sha256(f"{proposal_type}:{name.casefold().strip()}".encode()).hexdigest()[:12]
    return f"scp-{digest}"


def _normalize_symbol(value: str) -> str:
    return "_".join(value.casefold().strip().replace("-", " ").split())
