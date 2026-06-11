from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from evolex.graph.state import GraphState

DEFAULT_OUTPUT_DIR = Path("data/candidates")


def make_candidate_store_node(output_dir: Path | None = None):
    candidate_dir = output_dir or DEFAULT_OUTPUT_DIR

    def candidate_store_node(state: GraphState) -> dict:
        candidate_dir.mkdir(parents=True, exist_ok=True)
        output_path = candidate_dir / f"{state['run_id']}.jsonl"
        created_at = datetime.now(UTC).isoformat()

        with output_path.open("w", encoding="utf-8") as handle:
            for atom in state.get("semantic_atoms", []):
                record = {
                    "run_id": state["run_id"],
                    "document_id": state["document_id"],
                    "segment_id": atom["segment_id"],
                    "atom": atom,
                    "created_at": created_at,
                }
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")

        return {"candidate_output_path": str(output_path)}

    return candidate_store_node
