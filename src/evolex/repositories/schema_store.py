from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_SCHEMA_DIR = Path("data/schema_candidates")
MIN_PROMOTION_OCCURRENCES = 3
MIN_PROMOTION_DOCUMENTS = 2
BASE_SCHEMA_VERSION = "evolex-base-0.1.0"
BASE_TYPES = {
    "entity", "process", "material", "tool", "measurement",
    "property", "claim", "event", "condition",
}
BASE_PREDICATES = {
    "has_measurement", "has_property", "depends_on", "related_to",
    "has_condition", "has_parameter", "affects", "increases",
    "decreases", "part_of", "uses", "includes", "achieves", "retries",
}
BASE_ATTRIBUTES = {
    "time", "temperature", "pressure", "voltage", "current", "rate", "percentage",
}


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

        conn = sqlite3.connect(str(self._db_path), timeout=30.0)
        conn.execute("PRAGMA busy_timeout=30000")
        try:
            conn.execute("PRAGMA journal_mode=WAL")
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower():
                conn.close()
                raise
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
                source_document_ids TEXT,
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

            CREATE TABLE IF NOT EXISTS schema_versions (
                version_id TEXT PRIMARY KEY,
                parent_version_id TEXT,
                types_json TEXT NOT NULL,
                predicates_json TEXT NOT NULL,
                attributes_json TEXT NOT NULL,
                activated_by_proposal_id TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS schema_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(schema_proposals)").fetchall()
        }
        if "source_document_ids" not in columns:
            conn.execute(
                "ALTER TABLE schema_proposals ADD COLUMN source_document_ids TEXT"
            )
        now = datetime.now(UTC).isoformat()
        conn.execute(
            """
            INSERT OR IGNORE INTO schema_versions
            (version_id, parent_version_id, types_json, predicates_json,
             attributes_json, activated_by_proposal_id, created_at)
            VALUES (?, NULL, ?, ?, ?, NULL, ?)
            """,
            (
                BASE_SCHEMA_VERSION,
                json.dumps(sorted(BASE_TYPES)),
                json.dumps(sorted(BASE_PREDICATES)),
                json.dumps(sorted(BASE_ATTRIBUTES)),
                now,
            ),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO schema_metadata(key, value)
            VALUES ('active_schema_version', ?)
            """,
            (BASE_SCHEMA_VERSION,),
        )
        conn.commit()

    def put_proposal(self, proposal: dict) -> None:
        """Insert or update a schema proposal.

        Proposals accumulate by ``(proposal_type, name)`` so repeated runs can
        build stability signals even when each run emits a fresh proposal_id.
        """
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            now = datetime.now(UTC).isoformat()
            existing = conn.execute(
                "SELECT proposal_id, occurrence_count, independent_document_count, supporting_texts, evidence_spans, source_run_ids, source_document_ids FROM schema_proposals WHERE proposal_type = ? AND name = ? ORDER BY updated_at DESC LIMIT 1",
                (proposal["proposal_type"], proposal["name"]),
            ).fetchone()

            if existing:
                existing_id = existing[0]
                existing_run_ids = _merge_json_lists(existing[5], [])
                incoming_run_ids = list(proposal.get("source_run_ids", []))
                supporting_texts = _merge_json_lists(existing[3], proposal.get("supporting_texts", []))
                evidence_spans = _merge_json_lists(existing[4], proposal.get("evidence_spans", []))
                source_run_ids = _merge_json_lists(existing[5], incoming_run_ids)
                source_document_ids = _merge_json_lists(
                    existing[6],
                    proposal.get(
                        "source_document_ids",
                        proposal.get("source_run_ids", []),
                    ),
                )
                replayed_observation = bool(incoming_run_ids) and set(
                    incoming_run_ids
                ).issubset(set(existing_run_ids))
                new_count = (
                    existing[1]
                    if replayed_observation
                    else existing[1] + proposal.get("occurrence_count", 1)
                )
                new_docs = max(existing[2], len(source_document_ids))
                conn.execute(
                    "UPDATE schema_proposals SET occurrence_count = ?, independent_document_count = ?, supporting_texts = ?, evidence_spans = ?, source_run_ids = ?, source_document_ids = ?, updated_at = ? WHERE proposal_id = ?",
                    (
                        new_count,
                        new_docs,
                        json.dumps(supporting_texts, ensure_ascii=False),
                        json.dumps(evidence_spans, ensure_ascii=False),
                        json.dumps(source_run_ids, ensure_ascii=False),
                        json.dumps(source_document_ids, ensure_ascii=False),
                        now,
                        existing_id,
                    ),
                )
            else:
                conn.execute(
                    "INSERT INTO schema_proposals (proposal_id, proposal_type, name, description, supporting_texts, evidence_spans, occurrence_count, independent_document_count, relation_pattern_consistency, evidence_coverage, source_run_ids, source_document_ids, schema_version, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        proposal["proposal_id"],
                        proposal["proposal_type"],
                        proposal["name"],
                        proposal.get("description", ""),
                        json.dumps(proposal.get("supporting_texts", [])),
                        json.dumps(proposal.get("evidence_spans", [])),
                        proposal.get("occurrence_count", 1),
                        len(
                            set(
                                proposal.get(
                                    "source_document_ids",
                                    proposal.get("source_run_ids", []),
                                )
                            )
                        )
                        or proposal.get("independent_document_count", 1),
                        proposal.get("relation_pattern_consistency", 0.0),
                        proposal.get("evidence_coverage", 0.0),
                        json.dumps(proposal.get("source_run_ids", [])),
                        json.dumps(
                            proposal.get(
                                "source_document_ids",
                                proposal.get("source_run_ids", []),
                            )
                        ),
                        proposal.get("schema_version", ""),
                        "candidate",
                        now,
                        now,
                    ),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
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
                f"SELECT proposal_id, proposal_type, name, description, supporting_texts, evidence_spans, occurrence_count, independent_document_count, relation_pattern_consistency, evidence_coverage, source_run_ids, source_document_ids, schema_version, status, created_at, updated_at FROM schema_proposals WHERE {where_clause} ORDER BY occurrence_count DESC, updated_at DESC LIMIT ?",
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
                    "source_document_ids": json.loads(r[11]) if r[11] else [],
                    "schema_version": r[12],
                    "status": r[13],
                    "created_at": r[14],
                    "updated_at": r[15],
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
        if not target_schema_version.strip():
            raise ValueError("target schema version must not be empty")
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            active_row = conn.execute(
                """
                SELECT v.version_id, v.parent_version_id, v.types_json,
                       v.predicates_json, v.attributes_json,
                       v.activated_by_proposal_id, v.created_at
                FROM schema_metadata m
                JOIN schema_versions v ON v.version_id = m.value
                WHERE m.key = 'active_schema_version'
                """
            ).fetchone()
            if active_row is None:
                raise RuntimeError("active schema metadata is missing")
            active = {
                "version_id": active_row[0],
                "types": json.loads(active_row[2]),
                "predicates": json.loads(active_row[3]),
                "attributes": json.loads(active_row[4]),
            }
            if target_schema_version == active["version_id"]:
                raise ValueError(
                    f"target schema version is already active: {target_schema_version}"
                )
            current_status = conn.execute(
                "SELECT status FROM schema_proposals WHERE proposal_id = ?",
                (proposal_id,),
            ).fetchone()
            if current_status is None:
                raise ValueError(f"proposal not found: {proposal_id}")
            if current_status[0] != "candidate":
                raise ValueError(
                    f"proposal is not a candidate: {proposal_id} ({current_status[0]})"
                )

            types = set(active["types"])
            predicates = set(active["predicates"])
            attributes = set(active["attributes"])
            proposal_type = proposal.get("proposal_type")
            name = str(proposal.get("name", "")).strip()
            if proposal_type == "new_type":
                types.add(name)
            elif proposal_type == "new_relation":
                predicates.add(name)
            elif proposal_type == "new_attribute":
                attributes.add(name)

            now = datetime.now(UTC).isoformat()
            exists = conn.execute(
                "SELECT 1 FROM schema_versions WHERE version_id = ?",
                (target_schema_version,),
            ).fetchone()
            if exists:
                raise ValueError(
                    f"target schema version already exists: {target_schema_version}"
                )
            conn.execute(
                """
                INSERT INTO schema_versions
                (version_id, parent_version_id, types_json, predicates_json,
                 attributes_json, activated_by_proposal_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    target_schema_version,
                    active.get("version_id"),
                    json.dumps(sorted(types), ensure_ascii=False),
                    json.dumps(sorted(predicates), ensure_ascii=False),
                    json.dumps(sorted(attributes), ensure_ascii=False),
                    proposal.get("proposal_id"),
                    now,
                ),
            )
            conn.execute(
                "UPDATE schema_proposals SET status = 'promoted', updated_at = ? "
                "WHERE proposal_id = ?",
                (now, proposal_id),
            )
            conn.execute(
                """
                INSERT INTO schema_promotions
                (proposal_id, proposal_type, name, action, from_schema_version,
                 target_schema_version, reason, report_path, created_at)
                VALUES (?, ?, ?, 'promoted', ?, ?, ?, ?, ?)
                """,
                (
                    proposal_id,
                    proposal.get("proposal_type", ""),
                    proposal.get("name", ""),
                    active.get("version_id", ""),
                    target_schema_version,
                    reason,
                    report_path,
                    now,
                ),
            )
            conn.execute(
                """
                INSERT INTO schema_metadata(key, value)
                VALUES ('active_schema_version', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (target_schema_version,),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return self.get_proposal_by_id(proposal_id) or proposal

    def block_proposal(
        self,
        proposal_id: str,
        reason: str,
        report_path: str | None = None,
    ) -> dict[str, Any]:
        self._set_status_and_record(
            proposal_id=proposal_id,
            action="blocked",
            reason=reason,
            report_path=report_path,
        )
        proposal = self.get_proposal_by_id(proposal_id)
        if proposal is None:
            raise RuntimeError(f"blocked proposal disappeared: {proposal_id}")
        return proposal

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

    def get_active_schema(self) -> dict[str, Any]:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT v.version_id, v.parent_version_id, v.types_json,
                       v.predicates_json, v.attributes_json,
                       v.activated_by_proposal_id, v.created_at
                FROM schema_metadata m
                JOIN schema_versions v ON v.version_id = m.value
                WHERE m.key = 'active_schema_version'
                """
            ).fetchone()
            if row is None:
                return {
                    "version_id": BASE_SCHEMA_VERSION,
                    "types": sorted(BASE_TYPES),
                    "predicates": sorted(BASE_PREDICATES),
                    "attributes": sorted(BASE_ATTRIBUTES),
                }
            return {
                "version_id": row[0],
                "parent_version_id": row[1],
                "types": json.loads(row[2]),
                "predicates": json.loads(row[3]),
                "attributes": json.loads(row[4]),
                "activated_by_proposal_id": row[5],
                "created_at": row[6],
            }
        finally:
            conn.close()

    def activate_schema_version(self, version_id: str) -> dict[str, Any]:
        conn = self._connect()
        try:
            exists = conn.execute(
                "SELECT 1 FROM schema_versions WHERE version_id = ?",
                (version_id,),
            ).fetchone()
            if not exists:
                raise ValueError(f"schema version not found: {version_id}")
            conn.execute(
                """
                INSERT INTO schema_metadata(key, value)
                VALUES ('active_schema_version', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (version_id,),
            )
            conn.commit()
        finally:
            conn.close()
        return self.get_active_schema()

    def _set_status_and_record(
        self,
        *,
        proposal_id: str,
        action: str,
        reason: str,
        report_path: str | None,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        status = "promoted" if action == "promoted" else "blocked"
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            proposal = conn.execute(
                """
                SELECT proposal_type, name, schema_version, status
                FROM schema_proposals
                WHERE proposal_id = ?
                """,
                (proposal_id,),
            ).fetchone()
            if proposal is None:
                raise ValueError(f"proposal not found: {proposal_id}")
            if proposal[3] != "candidate":
                raise ValueError(
                    f"proposal is not a candidate: {proposal_id} ({proposal[3]})"
                )

            updated = conn.execute(
                """
                UPDATE schema_proposals
                SET status = ?, updated_at = ?
                WHERE proposal_id = ? AND status = 'candidate'
                """,
                (status, now, proposal_id),
            )
            if updated.rowcount != 1:
                raise RuntimeError(
                    f"proposal terminal transition lost race: {proposal_id}"
                )
            conn.execute(
                "INSERT INTO schema_promotions (proposal_id, proposal_type, name, action, from_schema_version, target_schema_version, reason, report_path, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    proposal_id,
                    proposal[0],
                    proposal[1],
                    status,
                    proposal[2],
                    proposal[2],
                    reason,
                    report_path,
                    now,
                ),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _activate_promotion(
        self,
        proposal: dict[str, Any],
        target_schema_version: str,
    ) -> None:
        active = self.get_active_schema()
        if target_schema_version == active.get("version_id"):
            raise ValueError(
                f"target schema version is already active: {target_schema_version}"
            )
        types = set(active.get("types", []))
        predicates = set(active.get("predicates", []))
        attributes = set(active.get("attributes", []))
        proposal_type = proposal.get("proposal_type")
        name = str(proposal.get("name", "")).strip()
        if proposal_type == "new_type":
            types.add(name)
        elif proposal_type == "new_relation":
            predicates.add(name)
        elif proposal_type == "new_attribute":
            attributes.add(name)

        now = datetime.now(UTC).isoformat()
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO schema_versions
                (version_id, parent_version_id, types_json, predicates_json,
                 attributes_json, activated_by_proposal_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    target_schema_version,
                    active.get("version_id"),
                    json.dumps(sorted(types), ensure_ascii=False),
                    json.dumps(sorted(predicates), ensure_ascii=False),
                    json.dumps(sorted(attributes), ensure_ascii=False),
                    proposal.get("proposal_id"),
                    now,
                ),
            )
            conn.execute(
                """
                INSERT INTO schema_metadata(key, value)
                VALUES ('active_schema_version', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (target_schema_version,),
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
                f"SELECT proposal_id, proposal_type, name, description, supporting_texts, evidence_spans, occurrence_count, independent_document_count, relation_pattern_consistency, evidence_coverage, source_run_ids, source_document_ids, schema_version, status, created_at, updated_at FROM schema_proposals WHERE {where_clause} ORDER BY occurrence_count DESC, updated_at DESC LIMIT ?",
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
                    "source_document_ids": json.loads(r[11]) if r[11] else [],
                    "schema_version": r[12],
                    "status": r[13],
                    "created_at": r[14],
                    "updated_at": r[15],
                }
                for r in rows
            ]
        finally:
            conn.close()
