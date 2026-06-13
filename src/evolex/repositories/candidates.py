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

            CREATE INDEX IF NOT EXISTS idx_candidates_run ON candidates(run_id);
            CREATE INDEX IF NOT EXISTS idx_quarantine_run ON quarantine_records(run_id);
            """
        )

    # -- writers ----------------------------------------------------------------

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
