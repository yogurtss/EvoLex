from __future__ import annotations

from evolex.graph.state import GraphState


def ingest_node(state: GraphState) -> dict:
    document_text = state.get("document_text", "").strip()
    if not document_text:
        return {
            "status": "failed",
            "warnings": state.get("warnings", []) + ["document_text is empty"],
        }

    return {
        "document_text": document_text,
        "status": "running",
    }
