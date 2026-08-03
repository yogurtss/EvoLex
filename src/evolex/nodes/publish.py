from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from evolex.agentic.metrics import publish_gate
from evolex.graph.state import GraphState
from evolex.repositories.kg_store import KGStore

DEFAULT_KG_DIR = Path("data/kg")


def make_publish_node(output_dir: Path | None = None):
    """Create a publish node that writes structured output to a SQLite KG store."""

    kg_dir = output_dir or DEFAULT_KG_DIR

    def publish_node(state: GraphState) -> dict:
        if state.get("evaluation_mode") == "shadow":
            return {
                "publish_output_path": "",
                "status": state.get("status", "candidate"),
            }

        if not _publication_authorized(state):
            warnings = list(state.get("warnings", []))
            warnings.append(
                "run-level publication blocked because governance prerequisites "
                "were not completed"
            )
            return {
                "publish_output_path": "",
                "status": (
                    state.get("status")
                    if state.get("status") in {"quarantined", "rejected", "failed"}
                    else "candidate"
                ),
                "warnings": warnings,
            }

        kg_dir.mkdir(parents=True, exist_ok=True)
        db_path = kg_dir / f"{state['run_id']}.sqlite"
        created_at = datetime.now(UTC).isoformat()

        store = KGStore(db_path)
        try:
            store.begin()
            store.clear_published_snapshot(str(state["run_id"]))
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
                document_version=state.get("document_version", 0),
                schema_version=state.get("schema_version", ""),
                policy_version=state.get("policy_version", ""),
                graph_version=state.get("graph_version", ""),
            )

            if entities:
                store.insert_entities(entities, created_at)

            if relations:
                store.insert_relations(relations, created_at)

            if quality_scores:
                store.insert_quality_scores(quality_scores, state["run_id"], created_at)

            entity_decisions = state.get("entity_decisions", [])
            if entity_decisions:
                store.insert_entity_decisions(entity_decisions, state["run_id"], created_at)

            # Write audit trail
            policy_decisions = state.get("policy_decisions", [])
            if policy_decisions:
                store.insert_audit_entry(
                    run_id=state["run_id"],
                    node_name="policy",
                    status_before=state.get("status", "running"),
                    status_after=final_status,
                    decision=policy_decisions[0].get("action", ""),
                    warnings=", ".join(policy_decisions[0].get("reasons", [])),
                    created_at=created_at,
                )

            store.commit()
        except Exception:
            store.rollback()
            raise
        finally:
            store.close()

        return {
            "publish_output_path": str(db_path),
            "status": final_status,
        }

    return publish_node


def _publication_authorized(state: GraphState) -> bool:
    """Defence-in-depth authorization for the side-effecting publish node."""
    pipeline_mode = str(state.get("pipeline_mode", ""))
    decisions = state.get("policy_decisions", [])
    if pipeline_mode == "phase1+2":
        return state.get("status") not in {"failed", "quarantined", "rejected"}
    if decisions and decisions[0].get("action") != "publish":
        return False
    if pipeline_mode == "agent":
        gate_passed, _, _ = publish_gate(state)
        return (
            bool(decisions)
            and bool(state.get("evolution_decision", {}).get("accepted"))
            and state.get("evolution_commit", {}).get("status") == "committed"
            and gate_passed
        )
    return bool(decisions) and state.get("status") not in {
        "failed",
        "quarantined",
        "rejected",
    }
