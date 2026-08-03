from __future__ import annotations

import json
import sqlite3
from pathlib import Path


class KGStore:
    """Simple SQLite-backed knowledge graph store for Phase II publishing."""

    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path))
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS entities (
                entity_id TEXT PRIMARY KEY,
                canonical_text TEXT NOT NULL,
                type TEXT,
                merged_count INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS entity_segments (
                entity_id TEXT NOT NULL,
                segment_id TEXT NOT NULL,
                PRIMARY KEY (entity_id, segment_id),
                FOREIGN KEY (entity_id) REFERENCES entities(entity_id)
            );

            CREATE TABLE IF NOT EXISTS entity_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                mention_text TEXT NOT NULL,
                normalized_text TEXT NOT NULL,
                decision TEXT NOT NULL,
                target_entity_id TEXT,
                confidence REAL NOT NULL DEFAULT 0.0,
                reason TEXT,
                segment_id TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS relations (
                relation_id TEXT PRIMARY KEY,
                subject_entity_id TEXT NOT NULL,
                predicate TEXT NOT NULL,
                object_entity_id TEXT NOT NULL,
                evidence TEXT,
                confidence REAL NOT NULL DEFAULT 0.5,
                created_at TEXT NOT NULL,
                FOREIGN KEY (subject_entity_id) REFERENCES entities(entity_id),
                FOREIGN KEY (object_entity_id) REFERENCES entities(entity_id)
            );

            CREATE TABLE IF NOT EXISTS quality_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                target_type TEXT NOT NULL,
                target_index INTEGER NOT NULL,
                score REAL NOT NULL,
                issues TEXT,
                adjusted_confidence REAL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                document_version INTEGER NOT NULL DEFAULT 0,
                schema_version TEXT NOT NULL DEFAULT '',
                policy_version TEXT NOT NULL DEFAULT '',
                graph_version TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL,
                segment_count INTEGER NOT NULL DEFAULT 0,
                entity_count INTEGER NOT NULL DEFAULT 0,
                relation_count INTEGER NOT NULL DEFAULT 0,
                started_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS run_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                node_name TEXT NOT NULL,
                status_before TEXT,
                status_after TEXT,
                decision TEXT,
                warnings TEXT,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_relations_subject
                ON relations(subject_entity_id);
            CREATE INDEX IF NOT EXISTS idx_relations_object
                ON relations(object_entity_id);
            CREATE INDEX IF NOT EXISTS idx_quality_run
                ON quality_scores(run_id);
            CREATE INDEX IF NOT EXISTS idx_entity_decisions_run
                ON entity_decisions(run_id);
            CREATE INDEX IF NOT EXISTS idx_run_audit_run
                ON run_audit(run_id);
            """
        )

    def insert_run(
        self,
        run_id: str,
        document_id: str,
        status: str,
        segment_count: int,
        entity_count: int,
        relation_count: int,
        started_at: str,
        document_version: int = 0,
        schema_version: str = "",
        policy_version: str = "",
        graph_version: str = "",
    ) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO runs (run_id, document_id, document_version, schema_version, policy_version, graph_version, status, segment_count, entity_count, relation_count, started_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id, document_id, document_version,
                schema_version, policy_version, graph_version,
                status, segment_count, entity_count, relation_count,
                started_at,
            ),
        )

    def insert_audit_entry(
        self,
        run_id: str,
        node_name: str,
        status_before: str | None,
        status_after: str | None,
        decision: str | None = None,
        warnings: str | None = None,
        created_at: str | None = None,
    ) -> None:
        from datetime import UTC, datetime
        now = created_at or datetime.now(UTC).isoformat()
        self.conn.execute(
            "INSERT INTO run_audit (run_id, node_name, status_before, status_after, decision, warnings, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (run_id, node_name, status_before, status_after, decision, warnings, now),
        )

    def fetch_audit(self, run_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT node_name, status_before, status_after, decision, warnings, created_at FROM run_audit WHERE run_id = ? ORDER BY id",
            (run_id,),
        ).fetchall()
        return [
            {
                "node_name": r[0],
                "status_before": r[1],
                "status_after": r[2],
                "decision": r[3],
                "warnings": r[4],
                "created_at": r[5],
            }
            for r in rows
        ]

    def insert_entities(self, entities: list[dict], created_at: str) -> None:
        for ent in entities:
            self.conn.execute(
                "INSERT OR REPLACE INTO entities VALUES (?, ?, ?, ?, ?)",
                (
                    ent["entity_id"],
                    ent["canonical_text"],
                    ent.get("type", "claim"),
                    ent.get("merged_count", 1),
                    created_at,
                ),
            )
            for seg_id in ent.get("segment_ids", []):
                self.conn.execute(
                    "INSERT OR REPLACE INTO entity_segments VALUES (?, ?)",
                    (ent["entity_id"], seg_id),
                )

    def insert_relations(self, relations: list[dict], created_at: str) -> None:
        for rel in relations:
            self.conn.execute(
                "INSERT OR REPLACE INTO relations VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    rel["relation_id"],
                    rel["subject_entity_id"],
                    rel["predicate"],
                    rel["object_entity_id"],
                    rel.get("evidence", ""),
                    rel.get("confidence", 0.5),
                    created_at,
                ),
            )

    def insert_quality_scores(self, scores: list[dict], run_id: str, created_at: str) -> None:
        for score in scores:
            self.conn.execute(
                "INSERT INTO quality_scores (run_id, target_type, target_index, score, issues, adjusted_confidence, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    score["target_type"],
                    score["target_index"],
                    score["score"],
                    json.dumps(score.get("issues", [])),
                    score.get("adjusted_confidence"),
                    created_at,
                ),
            )

    def insert_entity_decisions(self, decisions: list[dict], run_id: str, created_at: str) -> None:
        for d in decisions:
            self.conn.execute(
                "INSERT INTO entity_decisions (run_id, mention_text, normalized_text, decision, target_entity_id, confidence, reason, segment_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    d.get("mention_text", ""),
                    d.get("normalized_text", ""),
                    d.get("decision", "CREATE_CANDIDATE"),
                    d.get("target_entity_id"),
                    float(d.get("confidence", 0.0)),
                    d.get("reason", ""),
                    d.get("segment_id", ""),
                    created_at,
                ),
            )

    def fetch_entity_decisions(self, run_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT mention_text, normalized_text, decision, target_entity_id, confidence, reason, segment_id FROM entity_decisions WHERE run_id = ? ORDER BY id",
            (run_id,),
        ).fetchall()
        return [
            {
                "mention_text": r[0],
                "normalized_text": r[1],
                "decision": r[2],
                "target_entity_id": r[3],
                "confidence": r[4],
                "reason": r[5],
                "segment_id": r[6],
            }
            for r in rows
        ]

    def fetch_entities(self) -> list[dict]:
        rows = self.conn.execute(
            """
            SELECT e.entity_id, e.canonical_text, e.type, e.merged_count,
                   GROUP_CONCAT(es.segment_id) AS segment_ids
            FROM entities e
            LEFT JOIN entity_segments es ON es.entity_id = e.entity_id
            GROUP BY e.entity_id, e.canonical_text, e.type, e.merged_count
            ORDER BY e.entity_id
            """
        ).fetchall()
        return [
            {
                "entity_id": row[0],
                "canonical_text": row[1],
                "type": row[2],
                "merged_count": row[3],
                "segment_ids": row[4].split(",") if row[4] else [],
            }
            for row in rows
        ]

    def fetch_relations(self) -> list[dict]:
        rows = self.conn.execute(
            """
            SELECT relation_id, subject_entity_id, predicate, object_entity_id,
                   evidence, confidence
            FROM relations
            ORDER BY relation_id
            """
        ).fetchall()
        return [
            {
                "relation_id": row[0],
                "subject_entity_id": row[1],
                "predicate": row[2],
                "object_entity_id": row[3],
                "evidence": row[4],
                "confidence": row[5],
            }
            for row in rows
        ]

    def fetch_quality_scores(self) -> list[dict]:
        rows = self.conn.execute(
            """
            SELECT target_type, target_index, score, issues, adjusted_confidence
            FROM quality_scores
            ORDER BY id
            """
        ).fetchall()
        return [
            {
                "target_type": row[0],
                "target_index": row[1],
                "score": row[2],
                "issues": json.loads(row[3]) if row[3] else [],
                "adjusted_confidence": row[4],
            }
            for row in rows
        ]

    def begin(self) -> None:
        self.conn.execute("BEGIN IMMEDIATE")

    def rollback(self) -> None:
        self.conn.rollback()

    def clear_published_snapshot(self, run_id: str) -> None:
        """Clear one per-run publication inside the caller's transaction.

        A publication database is named by run ID, so graph object tables do
        not carry a second run_id column.  Clearing and rebuilding the snapshot
        makes a retry after a lost checkpoint idempotent.  If rebuilding fails,
        the surrounding rollback restores the previous successful snapshot.
        """
        self.conn.execute("DELETE FROM relations")
        self.conn.execute("DELETE FROM entity_segments")
        self.conn.execute("DELETE FROM entities")
        self.conn.execute("DELETE FROM quality_scores WHERE run_id = ?", (run_id,))
        self.conn.execute("DELETE FROM entity_decisions WHERE run_id = ?", (run_id,))
        self.conn.execute("DELETE FROM run_audit WHERE run_id = ?", (run_id,))
        self.conn.execute("DELETE FROM runs WHERE run_id = ?", (run_id,))

    def commit(self) -> None:
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()
