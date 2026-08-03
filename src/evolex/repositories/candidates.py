from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_REGISTRY_DIR = Path("data/registry")


class CandidateRegistry:
    """Registry for candidate objects, decisions, and quarantine records.

    Each run produces a SQLite-backed registry that separates
    candidate objects from production data.
    """

    def __init__(self, registry_dir: Path | None = None) -> None:
        self.registry_dir = registry_dir or DEFAULT_REGISTRY_DIR
        self.registry_dir.mkdir(parents=True, exist_ok=True)

    def _db_path(self, run_id: str) -> Path:
        return self.registry_dir / f"{run_id}_registry.sqlite"

    def _connect(self, run_id: str):
        import sqlite3

        db_path = self._db_path(run_id)
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema(conn)
        return conn

    @staticmethod
    def _init_schema(conn) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                object_type TEXT NOT NULL,
                object_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS entity_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                decision_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS policy_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                decision_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS quarantine_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                object_type TEXT NOT NULL,
                object_id TEXT,
                reason TEXT NOT NULL,
                risk_level TEXT NOT NULL DEFAULT 'medium',
                evidence TEXT,
                suggested_action TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS audit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                node_name TEXT NOT NULL,
                status_before TEXT,
                status_after TEXT,
                decision TEXT,
                warnings TEXT,
                elapsed_seconds REAL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS merge_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                object_type TEXT NOT NULL,
                decision_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS agent_trace (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                step_index INTEGER,
                trace_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_candidates_run ON candidates(run_id);
            CREATE INDEX IF NOT EXISTS idx_quarantine_run ON quarantine_records(run_id);
            CREATE INDEX IF NOT EXISTS idx_audit_run ON audit_events(run_id);
            CREATE INDEX IF NOT EXISTS idx_merge_run ON merge_decisions(run_id);
            CREATE INDEX IF NOT EXISTS idx_agent_trace_run ON agent_trace(run_id);
            """
        )

    # -- writers ----------------------------------------------------------------

    def replace_run_snapshot(
        self,
        run_id: str,
        *,
        entity_decisions: list[dict],
        policy_decisions: list[dict],
        audit_events: list[dict],
        merge_decisions: list[dict],
        agent_trace: list[dict],
        candidates: list[tuple[str, dict]],
        quarantine_record: dict | None,
    ) -> None:
        """Atomically replace a run's registry projection.

        Registry finalization is a materialized projection of the checkpoint
        state.  Replacing it in one transaction makes a retry after a
        checkpoint-write failure idempotent instead of duplicating every row.
        """
        conn = self._connect(run_id)
        created_at = datetime.now(UTC).isoformat()
        try:
            conn.execute("BEGIN IMMEDIATE")
            for table in (
                "candidates",
                "entity_decisions",
                "policy_decisions",
                "quarantine_records",
                "audit_events",
                "merge_decisions",
                "agent_trace",
            ):
                conn.execute(f"DELETE FROM {table} WHERE run_id = ?", (run_id,))

            conn.executemany(
                "INSERT INTO entity_decisions "
                "(run_id, decision_json, created_at) VALUES (?, ?, ?)",
                [
                    (
                        run_id,
                        json.dumps(item, ensure_ascii=False),
                        created_at,
                    )
                    for item in entity_decisions
                ],
            )
            conn.executemany(
                "INSERT INTO policy_decisions "
                "(run_id, decision_json, created_at) VALUES (?, ?, ?)",
                [
                    (
                        run_id,
                        json.dumps(item, ensure_ascii=False),
                        created_at,
                    )
                    for item in policy_decisions
                ],
            )
            conn.executemany(
                "INSERT INTO audit_events "
                "(run_id, node_name, status_before, status_after, decision, "
                "warnings, elapsed_seconds, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        run_id,
                        item.get("node_name", ""),
                        item.get("status_before"),
                        item.get("status_after"),
                        item.get("decision"),
                        item.get("warnings", ""),
                        item.get("elapsed_seconds"),
                        created_at,
                    )
                    for item in audit_events
                ],
            )
            conn.executemany(
                "INSERT INTO merge_decisions "
                "(run_id, object_type, decision_json, created_at) "
                "VALUES (?, ?, ?, ?)",
                [
                    (
                        run_id,
                        item.get("object_type", "unknown"),
                        json.dumps(item, ensure_ascii=False),
                        created_at,
                    )
                    for item in merge_decisions
                ],
            )
            conn.executemany(
                "INSERT INTO agent_trace "
                "(run_id, step_index, trace_json, created_at) VALUES (?, ?, ?, ?)",
                [
                    (
                        run_id,
                        item.get("step_index"),
                        json.dumps(item, ensure_ascii=False),
                        created_at,
                    )
                    for item in agent_trace
                ],
            )
            conn.executemany(
                "INSERT INTO candidates "
                "(run_id, object_type, object_json, created_at) "
                "VALUES (?, ?, ?, ?)",
                [
                    (
                        run_id,
                        object_type,
                        json.dumps(value, ensure_ascii=False),
                        created_at,
                    )
                    for object_type, value in candidates
                ],
            )
            if quarantine_record is not None:
                conn.execute(
                    "INSERT INTO quarantine_records "
                    "(run_id, object_type, object_id, reason, risk_level, "
                    "evidence, suggested_action, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        run_id,
                        quarantine_record.get("object_type", "unknown"),
                        quarantine_record.get("object_id"),
                        quarantine_record.get("reason", ""),
                        quarantine_record.get("risk_level", "medium"),
                        quarantine_record.get("evidence", ""),
                        quarantine_record.get("suggested_action", ""),
                        created_at,
                    ),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def put_candidate(self, run_id: str, object_type: str, obj: dict) -> None:
        conn = self._connect(run_id)
        try:
            conn.execute(
                "INSERT INTO candidates (run_id, object_type, object_json, created_at) VALUES (?, ?, ?, ?)",
                (run_id, object_type, json.dumps(obj, ensure_ascii=False), datetime.now(UTC).isoformat()),
            )
            conn.commit()
        finally:
            conn.close()

    def put_entity_decision(self, run_id: str, decision: dict) -> None:
        conn = self._connect(run_id)
        try:
            conn.execute(
                "INSERT INTO entity_decisions (run_id, decision_json, created_at) VALUES (?, ?, ?)",
                (run_id, json.dumps(decision, ensure_ascii=False), datetime.now(UTC).isoformat()),
            )
            conn.commit()
        finally:
            conn.close()

    def put_policy_decision(self, run_id: str, decision: dict) -> None:
        conn = self._connect(run_id)
        try:
            conn.execute(
                "INSERT INTO policy_decisions (run_id, decision_json, created_at) VALUES (?, ?, ?)",
                (run_id, json.dumps(decision, ensure_ascii=False), datetime.now(UTC).isoformat()),
            )
            conn.commit()
        finally:
            conn.close()

    def put_quarantine(self, run_id: str, record: dict) -> None:
        conn = self._connect(run_id)
        try:
            conn.execute(
                "INSERT INTO quarantine_records (run_id, object_type, object_id, reason, risk_level, evidence, suggested_action, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    record.get("object_type", "unknown"),
                    record.get("object_id"),
                    record.get("reason", ""),
                    record.get("risk_level", "medium"),
                    record.get("evidence", ""),
                    record.get("suggested_action", ""),
                    datetime.now(UTC).isoformat(),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def put_audit_event(self, run_id: str, event: dict) -> None:
        conn = self._connect(run_id)
        try:
            conn.execute(
                "INSERT INTO audit_events (run_id, node_name, status_before, status_after, decision, warnings, elapsed_seconds, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    event.get("node_name", ""),
                    event.get("status_before"),
                    event.get("status_after"),
                    event.get("decision"),
                    event.get("warnings", ""),
                    event.get("elapsed_seconds"),
                    datetime.now(UTC).isoformat(),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def put_merge_decision(self, run_id: str, decision: dict) -> None:
        conn = self._connect(run_id)
        try:
            conn.execute(
                "INSERT INTO merge_decisions (run_id, object_type, decision_json, created_at) VALUES (?, ?, ?, ?)",
                (
                    run_id,
                    decision.get("object_type", "unknown"),
                    json.dumps(decision, ensure_ascii=False),
                    datetime.now(UTC).isoformat(),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def put_agent_trace(self, run_id: str, trace: dict) -> None:
        conn = self._connect(run_id)
        try:
            conn.execute(
                "INSERT INTO agent_trace (run_id, step_index, trace_json, created_at) VALUES (?, ?, ?, ?)",
                (
                    run_id,
                    trace.get("step_index"),
                    json.dumps(trace, ensure_ascii=False),
                    datetime.now(UTC).isoformat(),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    # -- readers ---------------------------------------------------------------

    def get_recent_candidates(self, limit: int = 10) -> list[dict[str, Any]]:
        rows = self._query_all(
            "SELECT run_id, object_type, object_json, created_at FROM candidates ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return [
            {"run_id": r[0], "object_type": r[1], "object": json.loads(r[2]), "created_at": r[3]}
            for r in rows
        ]

    def get_recent_quarantine(self, limit: int = 10) -> list[dict[str, Any]]:
        rows = self._query_all(
            "SELECT run_id, object_type, object_id, reason, risk_level, evidence, suggested_action, created_at FROM quarantine_records ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return [
            {
                "run_id": r[0],
                "object_type": r[1],
                "object_id": r[2],
                "reason": r[3],
                "risk_level": r[4],
                "evidence": r[5],
                "suggested_action": r[6],
                "created_at": r[7],
            }
            for r in rows
        ]

    def get_recent_policy_decisions(self, limit: int = 10) -> list[dict[str, Any]]:
        rows = self._query_all(
            "SELECT run_id, decision_json, created_at FROM policy_decisions ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return [
            {"run_id": r[0], "decision": json.loads(r[1]), "created_at": r[2]}
            for r in rows
        ]

    def get_recent_audit_events(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._query_all(
            "SELECT run_id, node_name, status_before, status_after, decision, warnings, elapsed_seconds, created_at FROM audit_events ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return [
            {
                "run_id": r[0],
                "node_name": r[1],
                "status_before": r[2],
                "status_after": r[3],
                "decision": r[4],
                "warnings": r[5],
                "elapsed_seconds": r[6],
                "created_at": r[7],
            }
            for r in rows
        ]

    def _query_all(self, sql: str, params: tuple = ()) -> list[Any]:
        """Query across all registry databases in the directory."""
        results: list[Any] = []
        for db_file in sorted(self.registry_dir.glob("*_registry.sqlite"), reverse=True):
            import sqlite3

            try:
                conn = sqlite3.connect(str(db_file))
                rows = conn.execute(sql, params).fetchall()
                results.extend(rows)
                conn.close()
            except sqlite3.Error:
                continue
        return results[: params[0] if params else 10]
