from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_SCHEMA_DIR = Path("data/schema_candidates")


class SchemaCandidateStore:
    """Persistent store for schema proposals.

    Unlike CandidateRegistry (per-run), SchemaCandidateStore accumulates
    proposals across runs so that stability signals can be built up.
    """

    def __init__(self, store_dir: Path | None = None) -> None:
        self.store_dir = store_dir or DEFAULT_SCHEMA_DIR
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = self.store_dir / "schema_candidates.db"

    def _connect(self):
        import sqlite3

        conn = sqlite3.connect(str(self._db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema(conn)
        return conn

    @staticmethod
    def _init_schema(conn) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_proposals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                proposal_id TEXT UNIQUE NOT NULL,
                proposal_type TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                supporting_texts TEXT,
                evidence_spans TEXT,
                occurrence_count INTEGER NOT NULL DEFAULT 1,
                independent_document_count INTEGER NOT NULL DEFAULT 1,
                relation_pattern_consistency REAL NOT NULL DEFAULT 0.0,
                evidence_coverage REAL NOT NULL DEFAULT 0.0,
                source_run_ids TEXT,
                schema_version TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'candidate',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_proposal_type
                ON schema_proposals(proposal_type);
            CREATE INDEX IF NOT EXISTS idx_proposal_status
                ON schema_proposals(status);
            """
        )

    def put_proposal(self, proposal: dict) -> None:
        """Insert or update a schema proposal (upsert by proposal_id)."""
        conn = self._connect()
        try:
            now = datetime.now(UTC).isoformat()
            existing = conn.execute(
                "SELECT occurrence_count, independent_document_count, supporting_texts, evidence_spans FROM schema_proposals WHERE proposal_id = ?",
                (proposal["proposal_id"],),
            ).fetchone()

            if existing:
                # Accumulate
                new_count = existing[0] + proposal.get("occurrence_count", 1)
                new_docs = max(existing[1], proposal.get("independent_document_count", 1))
                conn.execute(
                    "UPDATE schema_proposals SET occurrence_count = ?, independent_document_count = ?, supporting_texts = ?, evidence_spans = ?, updated_at = ? WHERE proposal_id = ?",
                    (
                        new_count,
                        new_docs,
                        json.dumps(proposal.get("supporting_texts", [])),
                        json.dumps(proposal.get("evidence_spans", [])),
                        now,
                        proposal["proposal_id"],
                    ),
                )
            else:
                conn.execute(
                    "INSERT INTO schema_proposals (proposal_id, proposal_type, name, description, supporting_texts, evidence_spans, occurrence_count, independent_document_count, relation_pattern_consistency, evidence_coverage, source_run_ids, schema_version, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        proposal["proposal_id"],
                        proposal["proposal_type"],
                        proposal["name"],
                        proposal.get("description", ""),
                        json.dumps(proposal.get("supporting_texts", [])),
                        json.dumps(proposal.get("evidence_spans", [])),
                        proposal.get("occurrence_count", 1),
                        proposal.get("independent_document_count", 1),
                        proposal.get("relation_pattern_consistency", 0.0),
                        proposal.get("evidence_coverage", 0.0),
                        json.dumps(proposal.get("source_run_ids", [])),
                        proposal.get("schema_version", ""),
                        "candidate",
                        now,
                        now,
                    ),
                )
            conn.commit()
        finally:
            conn.close()

    def get_proposals(
        self,
        proposal_type: str | None = None,
        status: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        conn = self._connect()
        try:
            conditions: list[str] = []
            params: list[Any] = []
            if proposal_type:
                conditions.append("proposal_type = ?")
                params.append(proposal_type)
            if status:
                conditions.append("status = ?")
                params.append(status)

            where_clause = " AND ".join(conditions) if conditions else "1=1"
            rows = conn.execute(
                f"SELECT proposal_id, proposal_type, name, description, supporting_texts, evidence_spans, occurrence_count, independent_document_count, relation_pattern_consistency, evidence_coverage, source_run_ids, schema_version, status, created_at, updated_at FROM schema_proposals WHERE {where_clause} ORDER BY occurrence_count DESC, updated_at DESC LIMIT ?",
                (*params, limit),
            ).fetchall()

            return [
                {
                    "proposal_id": r[0],
                    "proposal_type": r[1],
                    "name": r[2],
                    "description": r[3],
                    "supporting_texts": json.loads(r[4]) if r[4] else [],
                    "evidence_spans": json.loads(r[5]) if r[5] else [],
                    "occurrence_count": r[6],
                    "independent_document_count": r[7],
                    "relation_pattern_consistency": r[8],
                    "evidence_coverage": r[9],
                    "source_run_ids": json.loads(r[10]) if r[10] else [],
                    "schema_version": r[11],
                    "status": r[12],
                    "created_at": r[13],
                    "updated_at": r[14],
                }
                for r in rows
            ]
        finally:
            conn.close()

    def get_proposal_by_name(self, name: str) -> dict[str, Any] | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT proposal_id, proposal_type, name, description, occurrence_count, independent_document_count, status, evidence_coverage FROM schema_proposals WHERE name = ? ORDER BY updated_at DESC LIMIT 1",
                (name,),
            ).fetchone()
            if row is None:
                return None
            return {
                "proposal_id": row[0],
                "proposal_type": row[1],
                "name": row[2],
                "description": row[3],
                "occurrence_count": row[4],
                "independent_document_count": row[5],
                "status": row[6],
                "evidence_coverage": row[7],
            }
        finally:
            conn.close()
