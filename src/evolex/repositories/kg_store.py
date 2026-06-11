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
                status TEXT NOT NULL,
                segment_count INTEGER NOT NULL DEFAULT 0,
                entity_count INTEGER NOT NULL DEFAULT 0,
                relation_count INTEGER NOT NULL DEFAULT 0,
                started_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_relations_subject
                ON relations(subject_entity_id);
            CREATE INDEX IF NOT EXISTS idx_relations_object
                ON relations(object_entity_id);
            CREATE INDEX IF NOT EXISTS idx_quality_run
                ON quality_scores(run_id);
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
    ) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO runs VALUES (?, ?, ?, ?, ?, ?, ?)",
            (run_id, document_id, status, segment_count, entity_count, relation_count, started_at),
        )

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

    def commit(self) -> None:
        self.conn.commit()

    def close(self) -> None:
        self.conn.commit()
        self.conn.close()
