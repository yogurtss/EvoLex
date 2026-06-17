from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_SCHEMA_DIR = Path("data/schema_candidates")
MIN_PROMOTION_OCCURRENCES = 3
MIN_PROMOTION_DOCUMENTS = 2


def _merge_json_lists(existing_json: str | None, new_values: list[Any]) -> list[Any]:
    try:
        existing_values = json.loads(existing_json) if existing_json else []
    except json.JSONDecodeError:
        existing_values = []
    merged: list[Any] = []
    for value in [*existing_values, *new_values]:
        if value not in merged:
            merged.append(value)
    return merged


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

            CREATE TABLE IF NOT EXISTS schema_promotions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                proposal_id TEXT NOT NULL,
                proposal_type TEXT NOT NULL,
                name TEXT NOT NULL,
                action TEXT NOT NULL,
                from_schema_version TEXT NOT NULL DEFAULT '',
                target_schema_version TEXT NOT NULL DEFAULT '',
                reason TEXT NOT NULL,
                report_path TEXT,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_schema_promotions_proposal
                ON schema_promotions(proposal_id);
            CREATE INDEX IF NOT EXISTS idx_schema_promotions_action
                ON schema_promotions(action);
            """
        )

    def put_proposal(self, proposal: dict) -> None:
        """Insert or update a schema proposal.

        Proposals accumulate by ``(proposal_type, name)`` so repeated runs can
        build stability signals even when each run emits a fresh proposal_id.
        """
        conn = self._connect()
        try:
            now = datetime.now(UTC).isoformat()
            existing = conn.execute(
                "SELECT proposal_id, occurrence_count, independent_document_count, supporting_texts, evidence_spans, source_run_ids FROM schema_proposals WHERE proposal_type = ? AND name = ? ORDER BY updated_at DESC LIMIT 1",
                (proposal["proposal_type"], proposal["name"]),
            ).fetchone()

            if existing:
                existing_id = existing[0]
                supporting_texts = _merge_json_lists(existing[3], proposal.get("supporting_texts", []))
                evidence_spans = _merge_json_lists(existing[4], proposal.get("evidence_spans", []))
                source_run_ids = _merge_json_lists(existing[5], proposal.get("source_run_ids", []))
                new_count = existing[1] + proposal.get("occurrence_count", 1)
                new_docs = max(existing[2], len(source_run_ids), proposal.get("independent_document_count", 1))
                conn.execute(
                    "UPDATE schema_proposals SET occurrence_count = ?, independent_document_count = ?, supporting_texts = ?, evidence_spans = ?, source_run_ids = ?, updated_at = ? WHERE proposal_id = ?",
                    (
                        new_count,
                        new_docs,
                        json.dumps(supporting_texts, ensure_ascii=False),
                        json.dumps(evidence_spans, ensure_ascii=False),
                        json.dumps(source_run_ids, ensure_ascii=False),
                        now,
                        existing_id,
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

    def get_proposal_by_id(self, proposal_id: str) -> dict[str, Any] | None:
        proposals = self._get_proposals_where("proposal_id = ?", (proposal_id,), limit=1)
        return proposals[0] if proposals else None

    def get_promotion_candidates(self, limit: int = 20) -> list[dict[str, Any]]:
        proposals = self.get_proposals(status="candidate", limit=limit * 3)
        ready = [
            proposal for proposal in proposals
            if proposal.get("occurrence_count", 0) >= MIN_PROMOTION_OCCURRENCES
            and proposal.get("independent_document_count", 0) >= MIN_PROMOTION_DOCUMENTS
        ]
        return ready[:limit]

    def evaluate_promotion(
        self,
        proposal_id: str,
        eval_report: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        proposal = self.get_proposal_by_id(proposal_id)
        if proposal is None:
            return {
                "action": "hold",
                "proposal_id": proposal_id,
                "reasons": ["proposal_not_found"],
                "canary_ready": False,
                "rollback_recommended": False,
            }

        reasons: list[str] = []
        if proposal.get("status") != "candidate":
            reasons.append(f"status_is_{proposal.get('status')}")
        if proposal.get("occurrence_count", 0) < MIN_PROMOTION_OCCURRENCES:
            reasons.append("insufficient_occurrences")
        if proposal.get("independent_document_count", 0) < MIN_PROMOTION_DOCUMENTS:
            reasons.append("insufficient_independent_documents")

        governance = (eval_report or {}).get("governance", {})
        rollback_recommended = bool(governance.get("rollback_recommended", False))
        canary_ready = bool(governance.get("canary_ready", not rollback_recommended))
        high_risk = int(governance.get("high_risk_policy_decision_count", 0) or 0)
        if rollback_recommended:
            reasons.append("rollback_recommended")
        if high_risk:
            reasons.append("high_risk_policy_decisions")

        if rollback_recommended or high_risk:
            action = "block"
        elif reasons:
            action = "hold"
        else:
            action = "promote"

        return {
            "action": action,
            "proposal_id": proposal_id,
            "proposal_type": proposal.get("proposal_type", ""),
            "name": proposal.get("name", ""),
            "reasons": reasons or ["promotion_thresholds_met"],
            "canary_ready": canary_ready,
            "rollback_recommended": rollback_recommended,
        }

    def promote_proposal(
        self,
        proposal_id: str,
        target_schema_version: str,
        reason: str,
        report_path: str | None = None,
    ) -> dict[str, Any]:
        proposal = self.get_proposal_by_id(proposal_id)
        if proposal is None:
            raise ValueError(f"proposal not found: {proposal_id}")
        self._set_status_and_record(
            proposal=proposal,
            action="promoted",
            target_schema_version=target_schema_version,
            reason=reason,
            report_path=report_path,
        )
        return self.get_proposal_by_id(proposal_id) or proposal

    def block_proposal(
        self,
        proposal_id: str,
        reason: str,
        report_path: str | None = None,
    ) -> dict[str, Any]:
        proposal = self.get_proposal_by_id(proposal_id)
        if proposal is None:
            raise ValueError(f"proposal not found: {proposal_id}")
        self._set_status_and_record(
            proposal=proposal,
            action="blocked",
            target_schema_version=proposal.get("schema_version", ""),
            reason=reason,
            report_path=report_path,
        )
        return self.get_proposal_by_id(proposal_id) or proposal

    def get_promotions(self, limit: int = 20) -> list[dict[str, Any]]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT proposal_id, proposal_type, name, action, from_schema_version, target_schema_version, reason, report_path, created_at FROM schema_promotions ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [
                {
                    "proposal_id": r[0],
                    "proposal_type": r[1],
                    "name": r[2],
                    "action": r[3],
                    "from_schema_version": r[4],
                    "target_schema_version": r[5],
                    "reason": r[6],
                    "report_path": r[7],
                    "created_at": r[8],
                }
                for r in rows
            ]
        finally:
            conn.close()

    def _set_status_and_record(
        self,
        *,
        proposal: dict[str, Any],
        action: str,
        target_schema_version: str,
        reason: str,
        report_path: str | None,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        status = "promoted" if action == "promoted" else "blocked"
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE schema_proposals SET status = ?, updated_at = ? WHERE proposal_id = ?",
                (status, now, proposal["proposal_id"]),
            )
            conn.execute(
                "INSERT INTO schema_promotions (proposal_id, proposal_type, name, action, from_schema_version, target_schema_version, reason, report_path, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    proposal["proposal_id"],
                    proposal.get("proposal_type", ""),
                    proposal.get("name", ""),
                    status,
                    proposal.get("schema_version", ""),
                    target_schema_version,
                    reason,
                    report_path,
                    now,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def _get_proposals_where(
        self,
        where_clause: str,
        params: tuple[Any, ...],
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        conn = self._connect()
        try:
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
