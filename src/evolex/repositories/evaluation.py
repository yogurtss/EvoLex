from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_CHECKPOINT_DIR = Path("data/checkpoints")
DEFAULT_EVAL_DIR = Path("data/eval")


@dataclass(frozen=True)
class FrozenDocument:
    document_id: str
    path: Path
    text: str


class CheckpointStore:
    """SQLite-backed snapshots of GraphState after each completed node."""

    def __init__(self, store_dir: Path | None = None) -> None:
        self.store_dir = store_dir or DEFAULT_CHECKPOINT_DIR
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.store_dir / "checkpoints.db"

    def _connect(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema(conn)
        return conn

    @staticmethod
    def _init_schema(conn) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS checkpoints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                thread_id TEXT NOT NULL,
                node_name TEXT NOT NULL,
                step_index INTEGER NOT NULL,
                state_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_checkpoints_run
                ON checkpoints(run_id, step_index);
            CREATE INDEX IF NOT EXISTS idx_checkpoints_thread
                ON checkpoints(thread_id, step_index);
            """
        )

    def put_checkpoint(self, state: dict, node_name: str, step_index: int) -> None:
        run_id = str(state.get("run_id", ""))
        thread_id = str(state.get("thread_id", ""))
        if not run_id or not thread_id:
            return
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO checkpoints (run_id, thread_id, node_name, step_index, state_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    thread_id,
                    node_name,
                    step_index,
                    json.dumps(_jsonable_state(state), ensure_ascii=False, sort_keys=True),
                    datetime.now(UTC).isoformat(),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def latest_for_thread(self, thread_id: str) -> dict[str, Any] | None:
        return self._fetch_one(
            "SELECT run_id, thread_id, node_name, step_index, state_json, created_at FROM checkpoints WHERE thread_id = ? ORDER BY id DESC LIMIT 1",
            (thread_id,),
        )

    def latest_for_run(self, run_id: str) -> dict[str, Any] | None:
        return self._fetch_one(
            "SELECT run_id, thread_id, node_name, step_index, state_json, created_at FROM checkpoints WHERE run_id = ? ORDER BY step_index DESC, id DESC LIMIT 1",
            (run_id,),
        )

    def replay_run(self, run_id: str) -> list[dict[str, Any]]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT node_name, step_index, state_json, created_at FROM checkpoints WHERE run_id = ? ORDER BY step_index, id",
                (run_id,),
            ).fetchall()
            events: list[dict[str, Any]] = []
            for row in rows:
                state = json.loads(row[2])
                policy_decisions = state.get("policy_decisions", [])
                events.append(
                    {
                        "run_id": run_id,
                        "node_name": row[0],
                        "step_index": row[1],
                        "status": state.get("status"),
                        "decision": (
                            policy_decisions[0].get("action")
                            if policy_decisions else None
                        ),
                        "warning_count": len(state.get("warnings", [])),
                        "created_at": row[3],
                    }
                )
            return events
        finally:
            conn.close()

    def _fetch_one(self, sql: str, params: tuple[Any, ...]) -> dict[str, Any] | None:
        conn = self._connect()
        try:
            row = conn.execute(sql, params).fetchone()
            if row is None:
                return None
            return {
                "run_id": row[0],
                "thread_id": row[1],
                "node_name": row[2],
                "step_index": row[3],
                "state": json.loads(row[4]),
                "created_at": row[5],
            }
        finally:
            conn.close()


class FrozenCorpusStore:
    """Small local frozen corpus used for deterministic regression checks."""

    def __init__(self, eval_dir: Path | None = None) -> None:
        self.eval_dir = eval_dir or DEFAULT_EVAL_DIR
        self.eval_dir.mkdir(parents=True, exist_ok=True)
        self.baseline_path = self.eval_dir / "frozen_baseline.json"
        self.report_path = self.eval_dir / "frozen_report.json"

    def load_documents(self, project_root: Path | None = None) -> list[FrozenDocument]:
        root = project_root or Path.cwd()
        candidates = [
            root / "examples" / "technical_note.txt",
            root / "tests" / "data" / "semiconductor_test.md",
        ]
        docs: list[FrozenDocument] = []
        for path in candidates:
            if path.exists() and path.is_file():
                docs.append(
                    FrozenDocument(
                        document_id=path.stem,
                        path=path,
                        text=path.read_text(encoding="utf-8"),
                    )
                )
        if docs:
            return docs
        return [
            FrozenDocument(
                document_id="builtin-api-gateway",
                path=root / "<builtin>",
                text="API Gateway retries HTTP 503 responses for 2 seconds before failing over.",
            )
        ]

    def save_baseline(self, report: dict[str, Any]) -> Path:
        self.baseline_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return self.baseline_path

    def load_baseline(self) -> dict[str, Any] | None:
        if not self.baseline_path.exists():
            return None
        return json.loads(self.baseline_path.read_text(encoding="utf-8"))

    def save_report(self, report: dict[str, Any]) -> Path:
        self.report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return self.report_path


class ShadowReportStore:
    """JSON reports for shadow comparisons that do not write production KG."""

    def __init__(self, eval_dir: Path | None = None) -> None:
        self.eval_dir = eval_dir or DEFAULT_EVAL_DIR
        self.eval_dir.mkdir(parents=True, exist_ok=True)

    def save_report(self, report: dict[str, Any]) -> Path:
        run_id = report.get("shadow_run_id") or datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        path = self.eval_dir / f"shadow_report_{run_id}.json"
        path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return path


def summarize_state(state: dict[str, Any]) -> dict[str, Any]:
    entity_decisions = state.get("entity_decisions", [])
    unsupported = [
        item for item in state.get("critic_results", [])
        if item.get("verdict") != "approved"
    ]
    ambiguous = [
        item for item in entity_decisions
        if item.get("decision") == "AMBIGUOUS"
    ]
    evidence_count = len(state.get("evidence_spans", []))
    claim_count = len(state.get("claim_candidates", []))
    return {
        "run_id": state.get("run_id", ""),
        "document_id": state.get("document_id", ""),
        "status": state.get("status", ""),
        "claims": claim_count,
        "evidence": evidence_count,
        "evidence_coverage": round(evidence_count / claim_count, 3) if claim_count else 0.0,
        "entities": len(state.get("entities", [])),
        "relations": len(state.get("relations", [])),
        "unsupported": len(unsupported),
        "ambiguous": len(ambiguous),
        "entity_remaps": len([d for d in entity_decisions if d.get("decision") == "LINK"]),
        "policy_action": _policy_action(state),
        "publish_output_path": state.get("publish_output_path", ""),
    }


def diff_metrics(baseline: dict[str, Any] | None, current: dict[str, Any]) -> dict[str, Any]:
    if not baseline:
        return {"baseline_available": False}
    keys = ("claims", "evidence", "entities", "relations", "unsupported", "ambiguous", "entity_remaps")
    return {
        "baseline_available": True,
        **{
            f"{key}_delta": int(current.get(key, 0)) - int(baseline.get(key, 0))
            for key in keys
        },
        "evidence_coverage_delta": round(
            float(current.get("evidence_coverage", 0.0))
            - float(baseline.get("evidence_coverage", 0.0)),
            3,
        ),
    }


def governance_snapshot(
    *,
    schema_proposals: list[dict[str, Any]],
    policy_decisions: list[dict[str, Any]],
) -> dict[str, Any]:
    high_risk = [
        item for item in policy_decisions
        if item.get("decision", {}).get("risk_level") == "high"
    ]
    mature_proposals = [
        item for item in schema_proposals
        if item.get("occurrence_count", 0) >= 3
        and item.get("independent_document_count", 0) >= 2
    ]
    return {
        "schema_proposal_count": len(schema_proposals),
        "mature_schema_proposal_count": len(mature_proposals),
        "policy_decision_count": len(policy_decisions),
        "high_risk_policy_decision_count": len(high_risk),
        "canary_ready": not high_risk,
        "rollback_recommended": bool(high_risk),
    }


def _policy_action(state: dict[str, Any]) -> str:
    decisions = state.get("policy_decisions", [])
    if not decisions:
        return "unknown"
    return str(decisions[0].get("action", "unknown"))


def _jsonable_state(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonable_state(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable_state(v) for v in value]
    if isinstance(value, tuple):
        return [_jsonable_state(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    return value
