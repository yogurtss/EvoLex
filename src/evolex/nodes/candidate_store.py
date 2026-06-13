from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from evolex.graph.state import GraphState
from evolex.repositories.candidates import CandidateRegistry

DEFAULT_OUTPUT_DIR = Path("data/candidates")


def make_candidate_store_node(output_dir: Path | None = None):
    candidate_dir = output_dir or DEFAULT_OUTPUT_DIR
    registry_dir = (output_dir / "registry") if output_dir else None

    def candidate_store_node(state: GraphState) -> dict:
        candidate_dir.mkdir(parents=True, exist_ok=True)
        output_path = candidate_dir / f"{state['run_id']}.jsonl"
        created_at = datetime.now(UTC).isoformat()
        run_id = state["run_id"]
        document_id = state["document_id"]

        # Registry for structured query access
        registry = CandidateRegistry(registry_dir)

        with output_path.open("w", encoding="utf-8") as handle:
            # Legacy atom records
            for atom in state.get("semantic_atoms", []):
                _write_record(handle, run_id, document_id, "atom", atom, created_at)

            # Phase III typed object records
            for obj in state.get("mentions", []):
                _write_record(handle, run_id, document_id, "mention", obj, created_at)
                registry.put_candidate(run_id, "mention", obj)
            for obj in state.get("measurements", []):
                _write_record(handle, run_id, document_id, "measurement", obj, created_at)
                registry.put_candidate(run_id, "measurement", obj)
            for obj in state.get("conditions", []):
                _write_record(handle, run_id, document_id, "condition", obj, created_at)
                registry.put_candidate(run_id, "condition", obj)
            for obj in state.get("claim_candidates", []):
                _write_record(handle, run_id, document_id, "claim", obj, created_at)
                registry.put_candidate(run_id, "claim", obj)
            for obj in state.get("evidence_spans", []):
                _write_record(handle, run_id, document_id, "evidence", obj, created_at)
                registry.put_candidate(run_id, "evidence", obj)

            # Entity decisions and policy decisions
            for d in state.get("entity_decisions", []):
                registry.put_entity_decision(run_id, d)
            for d in state.get("policy_decisions", []):
                registry.put_policy_decision(run_id, d)

        return {"candidate_output_path": str(output_path)}

    return candidate_store_node


def _write_record(
    handle,
    run_id: str,
    document_id: str,
    object_type: str,
    obj: dict,
    created_at: str,
) -> None:
    record = {
        "run_id": run_id,
        "document_id": document_id,
        "object_type": object_type,
        "object": obj,
        "created_at": created_at,
    }
    handle.write(json.dumps(record, ensure_ascii=False) + "\n")
