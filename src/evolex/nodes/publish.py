from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from evolex.graph.state import GraphState
from evolex.repositories.kg_store import KGStore

DEFAULT_KG_DIR = Path("data/kg")


def make_publish_node(output_dir: Path | None = None):
    """Create a publish node that writes structured output to a SQLite KG store."""
    kg_dir = output_dir or DEFAULT_KG_DIR

    def publish_node(state: GraphState) -> dict:
        kg_dir.mkdir(parents=True, exist_ok=True)
        db_path = kg_dir / f"{state['run_id']}.sqlite"
        created_at = datetime.now(UTC).isoformat()

        store = KGStore(db_path)
        try:
            entities = state.get("entities", [])
            relations = state.get("relations", [])
            quality_scores = state.get("quality_scores", [])
            final_status = (
                "published"
                if state.get("status") not in ("failed", "quarantined")
                else state.get("status", "failed")
            )

            store.insert_run(
                run_id=state["run_id"],
                document_id=state["document_id"],
                status=final_status,
                segment_count=len(state.get("segments", [])),
                entity_count=len(entities),
                relation_count=len(relations),
                started_at=created_at,
            )

            if entities:
                store.insert_entities(entities, created_at)

            if relations:
                store.insert_relations(relations, created_at)

            if quality_scores:
                store.insert_quality_scores(quality_scores, state["run_id"], created_at)

            store.commit()
        finally:
            store.close()

        return {
            "publish_output_path": str(db_path),
            "status": final_status,
        }

    return publish_node
