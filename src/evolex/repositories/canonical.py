from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any


DEFAULT_CANONICAL_DIR = Path("data/canonical")


class CanonicalGraphStore:
    """Cross-run canonical graph with immutable version and patch events."""

    def __init__(self, store_dir: Path | None = None) -> None:
        self.store_dir = store_dir or DEFAULT_CANONICAL_DIR
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.store_dir / "canonical_registry.sqlite"
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS graph_versions (
                version_id TEXT PRIMARY KEY,
                parent_version_id TEXT,
                patch_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                document_id TEXT NOT NULL,
                status TEXT NOT NULL,
                metrics_json TEXT,
                accepted_operation_ids_json TEXT,
                accepted_operations_hash TEXT,
                certificate_id TEXT,
                commit_manifest_hash TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS canonical_entities (
                canonical_id TEXT PRIMARY KEY,
                canonical_text TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                confidence REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                created_version TEXT NOT NULL,
                last_version TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS entity_contributions (
                canonical_id TEXT NOT NULL,
                version_id TEXT NOT NULL,
                canonical_text TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                confidence REAL NOT NULL,
                PRIMARY KEY (canonical_id, version_id),
                FOREIGN KEY (canonical_id)
                    REFERENCES canonical_entities(canonical_id),
                FOREIGN KEY (version_id) REFERENCES graph_versions(version_id)
            );

            CREATE TABLE IF NOT EXISTS entity_tombstones (
                canonical_id TEXT NOT NULL,
                version_id TEXT NOT NULL,
                PRIMARY KEY (canonical_id, version_id),
                FOREIGN KEY (canonical_id)
                    REFERENCES canonical_entities(canonical_id),
                FOREIGN KEY (version_id) REFERENCES graph_versions(version_id)
            );

            CREATE TABLE IF NOT EXISTS entity_aliases (
                canonical_id TEXT NOT NULL,
                alias_norm TEXT NOT NULL,
                alias_text TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                first_version TEXT NOT NULL,
                last_version TEXT NOT NULL,
                PRIMARY KEY (canonical_id, alias_norm),
                FOREIGN KEY (canonical_id) REFERENCES canonical_entities(canonical_id)
            );

            CREATE TABLE IF NOT EXISTS entity_alias_contributions (
                canonical_id TEXT NOT NULL,
                alias_norm TEXT NOT NULL,
                version_id TEXT NOT NULL,
                alias_text TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                PRIMARY KEY (canonical_id, alias_norm, version_id),
                FOREIGN KEY (canonical_id)
                    REFERENCES canonical_entities(canonical_id),
                FOREIGN KEY (version_id) REFERENCES graph_versions(version_id)
            );

            CREATE TABLE IF NOT EXISTS entity_mentions (
                mention_uid TEXT PRIMARY KEY,
                canonical_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                document_id TEXT NOT NULL,
                segment_id TEXT,
                mention_text TEXT NOT NULL,
                evidence_text TEXT,
                version_id TEXT NOT NULL,
                FOREIGN KEY (canonical_id) REFERENCES canonical_entities(canonical_id)
            );

            CREATE TABLE IF NOT EXISTS canonical_relations (
                canonical_relation_id TEXT PRIMARY KEY,
                subject_id TEXT NOT NULL,
                predicate TEXT NOT NULL,
                object_id TEXT NOT NULL,
                qualifiers_hash TEXT NOT NULL DEFAULT '',
                confidence REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                created_version TEXT NOT NULL,
                last_version TEXT NOT NULL,
                UNIQUE(subject_id, predicate, object_id, qualifiers_hash),
                FOREIGN KEY (subject_id) REFERENCES canonical_entities(canonical_id),
                FOREIGN KEY (object_id) REFERENCES canonical_entities(canonical_id)
            );

            CREATE TABLE IF NOT EXISTS relation_contributions (
                canonical_relation_id TEXT NOT NULL,
                version_id TEXT NOT NULL,
                subject_id TEXT NOT NULL,
                predicate TEXT NOT NULL,
                object_id TEXT NOT NULL,
                qualifiers_hash TEXT NOT NULL DEFAULT '',
                confidence REAL NOT NULL,
                PRIMARY KEY (canonical_relation_id, version_id),
                FOREIGN KEY (canonical_relation_id)
                    REFERENCES canonical_relations(canonical_relation_id),
                FOREIGN KEY (version_id) REFERENCES graph_versions(version_id)
            );

            CREATE TABLE IF NOT EXISTS relation_tombstones (
                canonical_relation_id TEXT NOT NULL,
                version_id TEXT NOT NULL,
                PRIMARY KEY (canonical_relation_id, version_id),
                FOREIGN KEY (canonical_relation_id)
                    REFERENCES canonical_relations(canonical_relation_id),
                FOREIGN KEY (version_id) REFERENCES graph_versions(version_id)
            );

            CREATE TABLE IF NOT EXISTS relation_evidence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                canonical_relation_id TEXT NOT NULL,
                evidence_uid TEXT NOT NULL,
                evidence_id TEXT,
                run_id TEXT NOT NULL,
                document_id TEXT NOT NULL,
                segment_id TEXT,
                evidence_text TEXT,
                confidence REAL NOT NULL,
                version_id TEXT NOT NULL,
                UNIQUE(canonical_relation_id, evidence_uid),
                FOREIGN KEY (canonical_relation_id)
                    REFERENCES canonical_relations(canonical_relation_id)
            );

            CREATE TABLE IF NOT EXISTS graph_events (
                event_id TEXT PRIMARY KEY,
                version_id TEXT NOT NULL,
                operation_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                object_type TEXT NOT NULL,
                object_id TEXT NOT NULL,
                before_json TEXT,
                after_json TEXT,
                inverse_json TEXT,
                evidence_contract_json TEXT,
                caused_by TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (version_id) REFERENCES graph_versions(version_id)
            );

            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_alias_lookup
                ON entity_aliases(alias_norm, entity_type);
            CREATE INDEX IF NOT EXISTS idx_entity_contributions
                ON entity_contributions(canonical_id, version_id);
            CREATE INDEX IF NOT EXISTS idx_entity_tombstones
                ON entity_tombstones(canonical_id, version_id);
            CREATE INDEX IF NOT EXISTS idx_alias_contributions
                ON entity_alias_contributions(canonical_id, alias_norm, version_id);
            CREATE INDEX IF NOT EXISTS idx_relation_key
                ON canonical_relations(subject_id, predicate, object_id);
            CREATE INDEX IF NOT EXISTS idx_relation_contributions
                ON relation_contributions(canonical_relation_id, version_id);
            CREATE INDEX IF NOT EXISTS idx_relation_tombstones
                ON relation_tombstones(canonical_relation_id, version_id);
            CREATE INDEX IF NOT EXISTS idx_evidence_relation
                ON relation_evidence(canonical_relation_id);
            CREATE INDEX IF NOT EXISTS idx_entity_mentions_document
                ON entity_mentions(document_id, run_id, canonical_id);
            CREATE INDEX IF NOT EXISTS idx_relation_evidence_document
                ON relation_evidence(document_id, run_id,
                                     canonical_relation_id);
            CREATE INDEX IF NOT EXISTS idx_graph_versions_document
                ON graph_versions(document_id, run_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_events_version
                ON graph_events(version_id);
            """
        )
        for column, definition in (
            ("accepted_operation_ids_json", "TEXT"),
            ("accepted_operations_hash", "TEXT"),
            ("certificate_id", "TEXT"),
            ("commit_manifest_hash", "TEXT"),
        ):
            self._ensure_column("graph_versions", column, definition)
        self.conn.commit()

    def _ensure_column(
        self,
        table: str,
        column: str,
        definition: str,
    ) -> None:
        existing = {
            str(row["name"])
            for row in self.conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if column not in existing:
            self.conn.execute(
                f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
            )

    def latest_version_id(self) -> str | None:
        row = self.conn.execute(
            "SELECT value FROM metadata WHERE key = 'active_version'"
        ).fetchone()
        return str(row[0]) if row else None

    def resolve_entity(self, alias_norm: str, entity_type: str) -> dict | None:
        row = self.conn.execute(
            """
            SELECT e.canonical_id, e.canonical_text, e.entity_type, e.confidence
            FROM entity_aliases a
            JOIN canonical_entities e ON e.canonical_id = a.canonical_id
            WHERE a.alias_norm = ? AND a.entity_type = ? AND e.status = 'active'
            ORDER BY e.confidence DESC, e.canonical_id
            LIMIT 1
            """,
            (alias_norm, entity_type),
        ).fetchone()
        return dict(row) if row else None

    def resolve_relation(
        self,
        subject_id: str,
        predicate: str,
        object_id: str,
        qualifiers_hash: str = "",
    ) -> dict | None:
        row = self.conn.execute(
            """
            SELECT canonical_relation_id, subject_id, predicate, object_id,
                   qualifiers_hash, confidence
            FROM canonical_relations
            WHERE subject_id = ? AND predicate = ? AND object_id = ?
              AND qualifiers_hash = ? AND status = 'active'
            """,
            (subject_id, predicate, object_id, qualifiers_hash),
        ).fetchone()
        return dict(row) if row else None

    def snapshot(self) -> dict[str, Any]:
        entities = [
            dict(row)
            for row in self.conn.execute(
                """
                SELECT canonical_id, canonical_text, entity_type, confidence,
                       created_version, last_version
                FROM canonical_entities WHERE status = 'active'
                ORDER BY canonical_id
                """
            ).fetchall()
        ]
        aliases_by_entity: dict[str, list[str]] = {}
        for row in self.conn.execute(
            """
            SELECT canonical_id, alias_text FROM entity_aliases
            ORDER BY canonical_id, alias_norm
            """
        ).fetchall():
            aliases_by_entity.setdefault(str(row["canonical_id"]), []).append(
                str(row["alias_text"])
            )
        for entity in entities:
            entity["aliases"] = aliases_by_entity.get(
                str(entity["canonical_id"]), []
            )
        relations = [
            dict(row)
            for row in self.conn.execute(
                """
                SELECT canonical_relation_id, subject_id, predicate, object_id,
                       qualifiers_hash, confidence, created_version, last_version
                FROM canonical_relations WHERE status = 'active'
                ORDER BY canonical_relation_id
                """
            ).fetchall()
        ]
        evidence = [
            dict(row)
            for row in self.conn.execute(
                """
                SELECT re.canonical_relation_id, re.evidence_uid, re.evidence_id,
                       re.run_id, re.document_id, re.segment_id, re.evidence_text,
                       re.confidence, re.version_id
                FROM relation_evidence re
                JOIN canonical_relations cr
                  ON cr.canonical_relation_id = re.canonical_relation_id
                WHERE cr.status = 'active'
                ORDER BY re.id
                """
            ).fetchall()
        ]
        mentions = [
            dict(row)
            for row in self.conn.execute(
                """
                SELECT em.mention_uid, em.canonical_id, em.run_id,
                       em.document_id, em.segment_id, em.mention_text,
                       em.evidence_text, em.version_id
                FROM entity_mentions em
                JOIN canonical_entities ce
                  ON ce.canonical_id = em.canonical_id
                WHERE ce.status = 'active'
                ORDER BY em.document_id, em.run_id, em.mention_uid
                """
            ).fetchall()
        ]
        return {
            "version_id": self.latest_version_id(),
            "entities": entities,
            "relations": relations,
            "relation_evidence": evidence,
            "entity_mentions": mentions,
        }

    def list_source_document_ids(self) -> list[str]:
        """Return stable source document IDs represented by canonical history.

        A document can remain in this list after all of its contributions have
        been compensated.  That is intentional: the batch visualizer can still
        produce an empty, auditable page for the historical source snapshot.
        System rollback records are excluded because they are control events,
        not source documents.
        """
        rows = self.conn.execute(
            """
            SELECT document_id FROM entity_mentions
            WHERE document_id <> ''
            UNION
            SELECT document_id FROM relation_evidence
            WHERE document_id <> ''
            UNION
            SELECT document_id FROM graph_versions
            WHERE document_id <> '' AND document_id NOT LIKE 'system:%'
            ORDER BY document_id
            """
        ).fetchall()
        return [str(row[0]) for row in rows]

    def history_for_document(
        self,
        document_id: str,
        *,
        run_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Return versions explicitly committed for one source document."""
        query = """
            SELECT version_id, parent_version_id, patch_id, run_id,
                   document_id, status, metrics_json,
                   accepted_operation_ids_json, accepted_operations_hash,
                   certificate_id, commit_manifest_hash, created_at
            FROM graph_versions
            WHERE document_id = ?
        """
        parameters: list[Any] = [document_id]
        if run_id is not None:
            query += " AND run_id = ?"
            parameters.append(run_id)
        query += " ORDER BY created_at DESC, version_id DESC LIMIT ?"
        parameters.append(limit)
        return [
            dict(row)
            for row in self.conn.execute(query, parameters).fetchall()
        ]

    def snapshot_for_document(
        self,
        document_id: str,
        *,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        """Build an active canonical projection grounded in one document.

        Direct object membership comes from ``entity_mentions`` and
        ``relation_evidence``.  Version contributions are used only as an
        explicit compatibility fallback for older imported patches that lack
        those direct source rows.  Shared canonical entities do not expand the
        projection into relations supported only by other documents.
        """
        global_snapshot = self.snapshot()
        run_clause = " AND run_id = ?" if run_id is not None else ""
        source_parameters: tuple[Any, ...] = (
            (document_id, run_id) if run_id is not None else (document_id,)
        )

        mentions = [
            dict(row)
            for row in self.conn.execute(
                f"""
                SELECT em.mention_uid, em.canonical_id, em.run_id,
                       em.document_id, em.segment_id, em.mention_text,
                       em.evidence_text, em.version_id
                FROM entity_mentions em
                JOIN canonical_entities ce
                  ON ce.canonical_id = em.canonical_id
                WHERE ce.status = 'active' AND em.document_id = ?
                      {run_clause}
                ORDER BY em.run_id, em.mention_uid
                """,
                source_parameters,
            ).fetchall()
        ]
        direct_evidence = [
            dict(row)
            for row in self.conn.execute(
                f"""
                SELECT re.canonical_relation_id, re.evidence_uid,
                       re.evidence_id, re.run_id, re.document_id,
                       re.segment_id, re.evidence_text, re.confidence,
                       re.version_id
                FROM relation_evidence re
                JOIN canonical_relations cr
                  ON cr.canonical_relation_id = re.canonical_relation_id
                WHERE cr.status = 'active' AND re.document_id = ?
                      {run_clause}
                ORDER BY re.id
                """,
                source_parameters,
            ).fetchall()
        ]

        version_run_clause = " AND gv.run_id = ?" if run_id is not None else ""
        contribution_parameters = source_parameters
        entity_contribution_ids = {
            str(row[0])
            for row in self.conn.execute(
                f"""
                SELECT DISTINCT ec.canonical_id
                FROM entity_contributions ec
                JOIN graph_versions gv ON gv.version_id = ec.version_id
                JOIN canonical_entities ce
                  ON ce.canonical_id = ec.canonical_id
                WHERE ce.status = 'active' AND gv.document_id = ?
                      {version_run_clause}
                """,
                contribution_parameters,
            ).fetchall()
        }
        relation_contribution_ids = {
            str(row[0])
            for row in self.conn.execute(
                f"""
                SELECT DISTINCT rc.canonical_relation_id
                FROM relation_contributions rc
                JOIN graph_versions gv ON gv.version_id = rc.version_id
                JOIN canonical_relations cr
                  ON cr.canonical_relation_id = rc.canonical_relation_id
                WHERE cr.status = 'active' AND gv.document_id = ?
                      {version_run_clause}
                """,
                contribution_parameters,
            ).fetchall()
        }

        direct_relation_ids = {
            str(item["canonical_relation_id"]) for item in direct_evidence
        }
        relation_ids = direct_relation_ids | relation_contribution_ids
        relations = [
            dict(item)
            for item in global_snapshot["relations"]
            if str(item["canonical_relation_id"]) in relation_ids
        ]
        for relation in relations:
            relation_id = str(relation["canonical_relation_id"])
            relation["provenance_mode"] = (
                "direct_relation_evidence"
                if relation_id in direct_relation_ids
                else "version_contribution_fallback"
            )
            relation["evidence_count"] = sum(
                str(item["canonical_relation_id"]) == relation_id
                for item in direct_evidence
            )

        mentioned_entity_ids = {str(item["canonical_id"]) for item in mentions}
        endpoint_entity_ids = {
            str(relation[key])
            for relation in relations
            for key in ("subject_id", "object_id")
        }
        entity_ids = (
            mentioned_entity_ids | entity_contribution_ids | endpoint_entity_ids
        )

        local_aliases: dict[str, set[str]] = {}
        for mention in mentions:
            local_aliases.setdefault(str(mention["canonical_id"]), set()).add(
                str(mention["mention_text"])
            )
        alias_rows = self.conn.execute(
            f"""
            SELECT DISTINCT eac.canonical_id, eac.alias_text
            FROM entity_alias_contributions eac
            JOIN graph_versions gv ON gv.version_id = eac.version_id
            WHERE gv.document_id = ? {version_run_clause}
            ORDER BY eac.canonical_id, eac.alias_text
            """,
            contribution_parameters,
        ).fetchall()
        for row in alias_rows:
            local_aliases.setdefault(str(row["canonical_id"]), set()).add(
                str(row["alias_text"])
            )

        shared_counts = self._entity_document_counts(entity_ids)
        entities = []
        for item in global_snapshot["entities"]:
            canonical_id = str(item["canonical_id"])
            if canonical_id not in entity_ids:
                continue
            entity = dict(item)
            entity["aliases"] = sorted(local_aliases.get(canonical_id, set()))
            entity["mention_count"] = sum(
                str(mention["canonical_id"]) == canonical_id
                for mention in mentions
            )
            entity["endpoint_only"] = canonical_id not in mentioned_entity_ids
            entity["shared_document_count"] = shared_counts.get(canonical_id, 0)
            entity["has_external_contributions"] = (
                entity["shared_document_count"] > 1
            )
            entities.append(entity)

        history = self.history_for_document(
            document_id,
            run_id=run_id,
            limit=100,
        )
        fallback_used = bool(
            (entity_contribution_ids - mentioned_entity_ids)
            or (relation_contribution_ids - direct_relation_ids)
        )
        return {
            "version_id": history[0]["version_id"] if history else None,
            "global_version_id": global_snapshot["version_id"],
            "document_id": document_id,
            "selected_run_id": run_id,
            "provenance_mode": (
                "direct_with_version_contribution_fallback"
                if fallback_used
                else "direct_source_records"
            ),
            "entities": entities,
            "relations": relations,
            "relation_evidence": direct_evidence,
            "entity_mentions": mentions,
        }

    def _entity_document_counts(
        self,
        canonical_ids: set[str],
    ) -> dict[str, int]:
        if not canonical_ids:
            return {}
        placeholders = ",".join("?" for _ in canonical_ids)
        ordered_ids = sorted(canonical_ids)
        rows = self.conn.execute(
            f"""
            WITH entity_documents AS (
                SELECT canonical_id, document_id FROM entity_mentions
                WHERE document_id <> ''
                UNION
                SELECT ec.canonical_id, gv.document_id
                FROM entity_contributions ec
                JOIN graph_versions gv ON gv.version_id = ec.version_id
                WHERE gv.document_id <> ''
                  AND gv.document_id NOT LIKE 'system:%'
            )
            SELECT canonical_id, COUNT(DISTINCT document_id) AS document_count
            FROM entity_documents
            WHERE canonical_id IN ({placeholders})
            GROUP BY canonical_id
            """,
            ordered_ids,
        ).fetchall()
        return {str(row["canonical_id"]): int(row["document_count"]) for row in rows}

    def commit_patch(
        self,
        patch: dict[str, Any],
        *,
        run_id: str,
        document_id: str,
        metrics: dict[str, Any] | None = None,
        accepted_operation_ids: set[str] | None = None,
    ) -> dict[str, Any]:
        operations = list(patch.get("operations", []))
        if accepted_operation_ids is not None:
            operations = [
                item
                for item in operations
                if str(item.get("operation_id", "")) in accepted_operation_ids
            ]
        accepted_ids = sorted(
            str(item.get("operation_id", "")) for item in operations
        )
        patch_id = str(patch.get("patch_id", "")).strip()
        if not patch_id:
            raise ValueError("canonical graph patch must have a patch_id")
        certificate_id = str(
            (metrics or {})
            .get("causal_validation_certificate", {})
            .get("certificate_id", "")
        )
        accepted_operations_hash = _content_hash(operations)
        commit_manifest = {
            "patch_id": patch_id,
            "parent_version_id": patch.get("parent_version_id"),
            "accepted_operation_ids": accepted_ids,
            "accepted_operations_hash": accepted_operations_hash,
            "certificate_id": certificate_id,
        }
        commit_manifest_hash = _content_hash(commit_manifest)
        now = datetime.now(UTC).isoformat()
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            existing_version = self.conn.execute(
                """
                SELECT version_id, parent_version_id,
                       accepted_operation_ids_json, accepted_operations_hash,
                       certificate_id, commit_manifest_hash
                FROM graph_versions WHERE patch_id = ?
                ORDER BY created_at LIMIT 1
                """,
                (patch_id,),
            ).fetchone()
            if existing_version is not None:
                stored_manifest_hash = str(
                    existing_version["commit_manifest_hash"] or ""
                )
                if stored_manifest_hash:
                    if stored_manifest_hash != commit_manifest_hash:
                        raise RuntimeError(
                            "idempotent canonical patch commit manifest mismatch"
                        )
                else:
                    stored_event_ids = sorted(
                        str(row["operation_id"])
                        for row in self.conn.execute(
                            """
                            SELECT operation_id FROM graph_events
                            WHERE version_id = ?
                            """,
                            (existing_version["version_id"],),
                        ).fetchall()
                    )
                    if stored_event_ids != accepted_ids or certificate_id:
                        raise RuntimeError(
                            "legacy idempotent patch cannot verify commit manifest"
                        )
                self.conn.commit()
                return {
                    "version_id": str(existing_version["version_id"]),
                    "parent_version_id": existing_version["parent_version_id"],
                    "operation_count": 0,
                    "db_path": str(self.db_path),
                    "idempotent_replay": True,
                    "accepted_operations_hash": (
                        existing_version["accepted_operations_hash"]
                        or accepted_operations_hash
                    ),
                    "certificate_id": existing_version["certificate_id"] or "",
                    "commit_manifest_hash": (
                        existing_version["commit_manifest_hash"]
                        or commit_manifest_hash
                    ),
                }
            parent = self.latest_version_id()
            expected_parent = patch.get("parent_version_id")
            if expected_parent != parent:
                raise RuntimeError(
                    "stale canonical patch: "
                    f"planned parent={expected_parent!r}, active parent={parent!r}"
                )
            version_id = _version_id(patch_id)
            self.conn.execute(
                """
                INSERT INTO graph_versions
                (version_id, parent_version_id, patch_id, run_id, document_id,
                 status, metrics_json, accepted_operation_ids_json,
                 accepted_operations_hash, certificate_id,
                 commit_manifest_hash, created_at)
                VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, ?, ?)
                """,
                (
                    version_id,
                    parent,
                    patch_id,
                    run_id,
                    document_id,
                    json.dumps(metrics or {}, ensure_ascii=False, sort_keys=True),
                    json.dumps(accepted_ids, ensure_ascii=False),
                    accepted_operations_hash,
                    certificate_id,
                    commit_manifest_hash,
                    now,
                ),
            )
            for index, operation in enumerate(operations, start=1):
                before, after, inverse = self._apply_operation(
                    operation,
                    version_id=version_id,
                    run_id=run_id,
                    document_id=document_id,
                )
                self.conn.execute(
                    """
                    INSERT INTO graph_events
                    (event_id, version_id, operation_id, event_type, object_type,
                     object_id, before_json, after_json, inverse_json,
                     evidence_contract_json, caused_by, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"{version_id}:evt-{index:04d}",
                        version_id,
                        operation.get("operation_id", ""),
                        operation.get("action", ""),
                        operation.get("object_type", ""),
                        operation.get("object_id", ""),
                        _json(before),
                        _json(after),
                        _json(inverse),
                        _json(operation.get("evidence_contract", {})),
                        operation.get("caused_by", "EvolutionAgent"),
                        now,
                    ),
                )
            self.conn.execute(
                """
                INSERT INTO metadata(key, value) VALUES ('active_version', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (version_id,),
            )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        return {
            "version_id": version_id,
            "parent_version_id": parent,
            "operation_count": len(operations),
            "db_path": str(self.db_path),
            "accepted_operations_hash": accepted_operations_hash,
            "certificate_id": certificate_id,
            "commit_manifest_hash": commit_manifest_hash,
        }

    def rollback_version(self, version_id: str, reason: str) -> dict[str, Any]:
        """Create a compensating version while preserving later changes."""
        events = self.conn.execute(
            """
            SELECT * FROM graph_events WHERE version_id = ?
            ORDER BY rowid DESC
            """,
            (version_id,),
        ).fetchall()
        if not events:
            raise ValueError(f"version not found or has no events: {version_id}")

        compensation_ops: list[dict[str, Any]] = []
        skipped: list[str] = []
        for row in events:
            inverse = json.loads(row["inverse_json"] or "{}")
            object_type = str(row["object_type"])
            object_id = str(row["object_id"])
            if not self._safe_to_compensate(
                object_type,
                object_id,
                version_id,
                inverse=inverse,
            ):
                skipped.append(str(row["operation_id"]))
                continue
            inverse["operation_id"] = f"undo:{row['operation_id']}"
            inverse["caused_by"] = f"rollback:{version_id}:{reason}"
            inverse.setdefault("after", {})["source_version_id"] = version_id
            compensation_ops.append(inverse)

        patch = {
            "patch_id": f"rollback-{version_id}",
            "parent_version_id": self.latest_version_id(),
            "operations": compensation_ops,
        }
        result = self.commit_patch(
            patch,
            run_id=f"ROLLBACK-{version_id}",
            document_id="system:rollback",
            metrics={"reason": reason, "skipped_operation_ids": skipped},
        )
        result["skipped_operation_ids"] = skipped
        return result

    def history(self, limit: int = 50) -> list[dict[str, Any]]:
        return [
            dict(row)
            for row in self.conn.execute(
                """
                SELECT version_id, parent_version_id, patch_id, run_id,
                       document_id, status, metrics_json,
                       accepted_operation_ids_json, accepted_operations_hash,
                       certificate_id, commit_manifest_hash, created_at
                FROM graph_versions ORDER BY created_at DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        ]

    def _apply_operation(
        self,
        operation: dict[str, Any],
        *,
        version_id: str,
        run_id: str,
        document_id: str,
    ) -> tuple[dict, dict, dict]:
        action = str(operation.get("action", ""))
        payload = dict(operation.get("after", {}))
        if action == "upsert_entity":
            return self._upsert_entity(
                payload,
                operation,
                version_id=version_id,
                run_id=run_id,
                document_id=document_id,
            )
        if action == "upsert_relation":
            return self._upsert_relation(
                payload,
                operation,
                version_id=version_id,
                run_id=run_id,
                document_id=document_id,
            )
        if action == "delete_entity":
            return self._delete_entity(payload, version_id)
        if action == "delete_relation":
            return self._delete_relation(payload, version_id)
        if action == "restore_entity_status":
            return self._restore_entity_status(payload, version_id)
        if action == "restore_relation_status":
            return self._restore_relation_status(payload, version_id)
        if action == "compensate_entity":
            return self._compensate_entity(payload, version_id)
        if action == "compensate_relation":
            return self._compensate_relation(payload, version_id)
        raise ValueError(f"unsupported canonical graph operation: {action}")

    def _upsert_entity(
        self,
        payload: dict,
        operation: dict,
        *,
        version_id: str,
        run_id: str,
        document_id: str,
    ) -> tuple[dict, dict, dict]:
        canonical_id = str(payload["canonical_id"])
        existing = self.conn.execute(
            "SELECT * FROM canonical_entities WHERE canonical_id = ?",
            (canonical_id,),
        ).fetchone()
        before = dict(existing) if existing else {}
        surviving_contribution_count = self.conn.execute(
            """
            SELECT COUNT(*) FROM entity_contributions
            WHERE canonical_id = ?
            """,
            (canonical_id,),
        ).fetchone()[0]
        new_lifecycle = not bool(existing) or surviving_contribution_count == 0
        existing_aliases = {
            str(row[0])
            for row in self.conn.execute(
                "SELECT alias_norm FROM entity_aliases WHERE canonical_id = ?",
                (canonical_id,),
            ).fetchall()
        }
        existing_mentions = {
            str(row[0])
            for row in self.conn.execute(
                "SELECT mention_uid FROM entity_mentions WHERE canonical_id = ?",
                (canonical_id,),
            ).fetchall()
        }
        if existing and new_lifecycle:
            self.conn.execute(
                """
                UPDATE canonical_entities
                SET canonical_text = ?, entity_type = ?, confidence = ?,
                    status = 'active', created_version = ?, last_version = ?
                WHERE canonical_id = ?
                """,
                (
                    payload["canonical_text"],
                    payload["entity_type"],
                    float(payload.get("confidence", 0.5)),
                    version_id,
                    version_id,
                    canonical_id,
                ),
            )
        else:
            self.conn.execute(
                """
                INSERT INTO canonical_entities
                (canonical_id, canonical_text, entity_type, confidence, status,
                 created_version, last_version)
                VALUES (?, ?, ?, ?, 'active', ?, ?)
                ON CONFLICT(canonical_id) DO UPDATE SET
                    confidence = MAX(confidence, excluded.confidence),
                    status = 'active',
                    last_version = excluded.last_version
                """,
                (
                    canonical_id,
                    payload["canonical_text"],
                    payload["entity_type"],
                    float(payload.get("confidence", 0.5)),
                    version_id,
                    version_id,
                ),
            )
        self.conn.execute(
            """
            INSERT INTO entity_contributions
            (canonical_id, version_id, canonical_text, entity_type, confidence)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(canonical_id, version_id) DO UPDATE SET
                canonical_text = excluded.canonical_text,
                entity_type = excluded.entity_type,
                confidence = excluded.confidence
            """,
            (
                canonical_id,
                version_id,
                payload["canonical_text"],
                payload["entity_type"],
                float(payload.get("confidence", 0.5)),
            ),
        )
        aliases = payload.get("aliases", [payload["canonical_text"]])
        for alias in aliases:
            alias_norm = _normalize_alias(str(alias))
            self.conn.execute(
                """
                INSERT INTO entity_aliases
                (canonical_id, alias_norm, alias_text, entity_type,
                 first_version, last_version)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(canonical_id, alias_norm) DO UPDATE SET
                    alias_text = excluded.alias_text,
                    last_version = excluded.last_version
                """,
                (
                    canonical_id,
                    alias_norm,
                    str(alias),
                    payload["entity_type"],
                    version_id,
                    version_id,
                ),
            )
            self.conn.execute(
                """
                INSERT INTO entity_alias_contributions
                (canonical_id, alias_norm, version_id, alias_text, entity_type)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(canonical_id, alias_norm, version_id) DO UPDATE SET
                    alias_text = excluded.alias_text,
                    entity_type = excluded.entity_type
                """,
                (
                    canonical_id,
                    alias_norm,
                    version_id,
                    str(alias),
                    payload["entity_type"],
                ),
            )
        for mention in operation.get("mentions", []):
            self.conn.execute(
                """
                INSERT OR IGNORE INTO entity_mentions
                (mention_uid, canonical_id, run_id, document_id, segment_id,
                 mention_text, evidence_text, version_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    mention.get("mention_uid"),
                    canonical_id,
                    run_id,
                    document_id,
                    mention.get("segment_id", ""),
                    mention.get("mention_text", ""),
                    mention.get("evidence_text", ""),
                    version_id,
                ),
            )
        after = dict(payload)
        inverse = {
            "action": "compensate_entity",
            "object_type": "entity",
            "object_id": canonical_id,
            "after": {
                "canonical_id": canonical_id,
                "entity": before,
                "created_by_source_version": new_lifecycle,
                "source_version_id": version_id,
                "remove_alias_norms": [
                    _normalize_alias(str(alias))
                    for alias in aliases
                    if _normalize_alias(str(alias)) not in existing_aliases
                ],
                "remove_mention_uids": [
                    str(item.get("mention_uid", ""))
                    for item in operation.get("mentions", [])
                    if str(item.get("mention_uid", "")) not in existing_mentions
                ],
            },
        }
        return before, after, inverse

    def _upsert_relation(
        self,
        payload: dict,
        operation: dict,
        *,
        version_id: str,
        run_id: str,
        document_id: str,
    ) -> tuple[dict, dict, dict]:
        relation_id = str(payload["canonical_relation_id"])
        existing = self.conn.execute(
            "SELECT * FROM canonical_relations WHERE canonical_relation_id = ?",
            (relation_id,),
        ).fetchone()
        before = dict(existing) if existing else {}
        surviving_contribution_count = self.conn.execute(
            """
            SELECT COUNT(*) FROM relation_contributions
            WHERE canonical_relation_id = ?
            """,
            (relation_id,),
        ).fetchone()[0]
        new_lifecycle = not bool(existing) or surviving_contribution_count == 0
        existing_evidence_uids = {
            str(row[0])
            for row in self.conn.execute(
                """
                SELECT evidence_uid FROM relation_evidence
                WHERE canonical_relation_id = ?
                """,
                (relation_id,),
            ).fetchall()
        }
        if existing and new_lifecycle:
            self.conn.execute(
                """
                UPDATE canonical_relations
                SET subject_id = ?, predicate = ?, object_id = ?,
                    qualifiers_hash = ?, confidence = ?, status = 'active',
                    created_version = ?, last_version = ?
                WHERE canonical_relation_id = ?
                """,
                (
                    payload["subject_id"],
                    payload["predicate"],
                    payload["object_id"],
                    payload.get("qualifiers_hash", ""),
                    float(payload.get("confidence", 0.5)),
                    version_id,
                    version_id,
                    relation_id,
                ),
            )
        else:
            self.conn.execute(
                """
                INSERT INTO canonical_relations
                (canonical_relation_id, subject_id, predicate, object_id,
                 qualifiers_hash, confidence, status, created_version, last_version)
                VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?)
                ON CONFLICT(canonical_relation_id) DO UPDATE SET
                    confidence = MAX(confidence, excluded.confidence),
                    status = 'active',
                    last_version = excluded.last_version
                """,
                (
                    relation_id,
                    payload["subject_id"],
                    payload["predicate"],
                    payload["object_id"],
                    payload.get("qualifiers_hash", ""),
                    float(payload.get("confidence", 0.5)),
                    version_id,
                    version_id,
                ),
            )
        self.conn.execute(
            """
            INSERT INTO relation_contributions
            (canonical_relation_id, version_id, subject_id, predicate, object_id,
             qualifiers_hash, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(canonical_relation_id, version_id) DO UPDATE SET
                subject_id = excluded.subject_id,
                predicate = excluded.predicate,
                object_id = excluded.object_id,
                qualifiers_hash = excluded.qualifiers_hash,
                confidence = excluded.confidence
            """,
            (
                relation_id,
                version_id,
                payload["subject_id"],
                payload["predicate"],
                payload["object_id"],
                payload.get("qualifiers_hash", ""),
                float(payload.get("confidence", 0.5)),
            ),
        )
        for evidence in operation.get("evidence", []):
            self.conn.execute(
                """
                INSERT OR IGNORE INTO relation_evidence
                (canonical_relation_id, evidence_uid, evidence_id, run_id,
                 document_id, segment_id, evidence_text, confidence, version_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    relation_id,
                    evidence.get("evidence_uid"),
                    evidence.get("evidence_id", ""),
                    run_id,
                    document_id,
                    evidence.get("segment_id", ""),
                    evidence.get("evidence_text", ""),
                    float(evidence.get("confidence", payload.get("confidence", 0.5))),
                    version_id,
                ),
            )
        inverse = {
            "action": "compensate_relation",
            "object_type": "relation",
            "object_id": relation_id,
            "after": {
                "canonical_relation_id": relation_id,
                "relation": before,
                "created_by_source_version": new_lifecycle,
                "source_version_id": version_id,
                "remove_evidence_uids": [
                    str(item.get("evidence_uid", ""))
                    for item in operation.get("evidence", [])
                    if str(item.get("evidence_uid", ""))
                    not in existing_evidence_uids
                ],
            },
        }
        return before, dict(payload), inverse

    def _delete_entity(
        self,
        payload: dict,
        version_id: str,
    ) -> tuple[dict, dict, dict]:
        canonical_id = str(payload["canonical_id"])
        existing = self.conn.execute(
            "SELECT * FROM canonical_entities WHERE canonical_id = ?",
            (canonical_id,),
        ).fetchone()
        before = dict(existing) if existing else {}
        self.conn.execute(
            """
            INSERT OR IGNORE INTO entity_tombstones(canonical_id, version_id)
            VALUES (?, ?)
            """,
            (canonical_id, version_id),
        )
        self.conn.execute(
            """
            UPDATE canonical_entities
            SET status = 'retracted', last_version = ?
            WHERE canonical_id = ?
            """,
            (version_id, canonical_id),
        )
        inverse = {
            "action": "restore_entity_status",
            "object_type": "entity",
            "object_id": canonical_id,
            "after": {
                "canonical_id": canonical_id,
                "status": before.get("status", "active"),
                "source_version_id": version_id,
            },
        }
        return before, {"canonical_id": canonical_id, "status": "retracted"}, inverse

    def _delete_relation(
        self,
        payload: dict,
        version_id: str,
    ) -> tuple[dict, dict, dict]:
        relation_id = str(payload["canonical_relation_id"])
        existing = self.conn.execute(
            "SELECT * FROM canonical_relations WHERE canonical_relation_id = ?",
            (relation_id,),
        ).fetchone()
        before = dict(existing) if existing else {}
        self.conn.execute(
            """
            INSERT OR IGNORE INTO relation_tombstones
            (canonical_relation_id, version_id) VALUES (?, ?)
            """,
            (relation_id, version_id),
        )
        self.conn.execute(
            """
            UPDATE canonical_relations
            SET status = 'retracted', last_version = ?
            WHERE canonical_relation_id = ?
            """,
            (version_id, relation_id),
        )
        inverse = {
            "action": "restore_relation_status",
            "object_type": "relation",
            "object_id": relation_id,
            "after": {
                "canonical_relation_id": relation_id,
                "status": before.get("status", "active"),
                "source_version_id": version_id,
            },
        }
        return before, {"canonical_relation_id": relation_id, "status": "retracted"}, inverse

    def _restore_entity_status(
        self,
        payload: dict,
        version_id: str,
    ) -> tuple[dict, dict, dict]:
        canonical_id = str(payload["canonical_id"])
        current = self.conn.execute(
            "SELECT * FROM canonical_entities WHERE canonical_id = ?",
            (canonical_id,),
        ).fetchone()
        before = dict(current) if current else {}
        source_version_id = str(payload.get("source_version_id", ""))
        self.conn.execute(
            """
            DELETE FROM entity_tombstones
            WHERE canonical_id = ? AND version_id = ?
            """,
            (canonical_id, source_version_id),
        )
        remaining = self._entity_contribution_summary(canonical_id)
        if remaining is None:
            self.conn.execute(
                """
                UPDATE canonical_entities
                SET status = 'retracted', last_version = ?
                WHERE canonical_id = ?
                """,
                (version_id, canonical_id),
            )
        else:
            status = (
                "active"
                if self._latest_entity_event_is_contribution(canonical_id)
                else "retracted"
            )
            self.conn.execute(
                """
                UPDATE canonical_entities
                SET canonical_text = ?, entity_type = ?, confidence = ?,
                    status = ?, created_version = ?, last_version = ?
                WHERE canonical_id = ?
                """,
                (
                    remaining["canonical_text"],
                    remaining["entity_type"],
                    remaining["confidence"],
                    status,
                    remaining["created_version"],
                    version_id,
                    canonical_id,
                ),
            )
        after = dict(
            self.conn.execute(
                "SELECT * FROM canonical_entities WHERE canonical_id = ?",
                (canonical_id,),
            ).fetchone()
            or {}
        )
        inverse = {
            "action": "delete_entity",
            "object_type": "entity",
            "object_id": canonical_id,
            "after": {"canonical_id": canonical_id},
        }
        return before, after, inverse

    def _restore_relation_status(
        self,
        payload: dict,
        version_id: str,
    ) -> tuple[dict, dict, dict]:
        relation_id = str(payload["canonical_relation_id"])
        current = self.conn.execute(
            """
            SELECT * FROM canonical_relations
            WHERE canonical_relation_id = ?
            """,
            (relation_id,),
        ).fetchone()
        before = dict(current) if current else {}
        source_version_id = str(payload.get("source_version_id", ""))
        self.conn.execute(
            """
            DELETE FROM relation_tombstones
            WHERE canonical_relation_id = ? AND version_id = ?
            """,
            (relation_id, source_version_id),
        )
        remaining = self._relation_contribution_summary(relation_id)
        if remaining is None:
            self.conn.execute(
                """
                UPDATE canonical_relations
                SET status = 'retracted', last_version = ?
                WHERE canonical_relation_id = ?
                """,
                (version_id, relation_id),
            )
        else:
            status = (
                "active"
                if self._latest_relation_event_is_contribution(relation_id)
                else "retracted"
            )
            self.conn.execute(
                """
                UPDATE canonical_relations
                SET subject_id = ?, predicate = ?, object_id = ?,
                    qualifiers_hash = ?, confidence = ?, status = ?,
                    created_version = ?, last_version = ?
                WHERE canonical_relation_id = ?
                """,
                (
                    remaining["subject_id"],
                    remaining["predicate"],
                    remaining["object_id"],
                    remaining["qualifiers_hash"],
                    remaining["confidence"],
                    status,
                    remaining["created_version"],
                    version_id,
                    relation_id,
                ),
            )
        after = dict(
            self.conn.execute(
                """
                SELECT * FROM canonical_relations
                WHERE canonical_relation_id = ?
                """,
                (relation_id,),
            ).fetchone()
            or {}
        )
        inverse = {
            "action": "delete_relation",
            "object_type": "relation",
            "object_id": relation_id,
            "after": {"canonical_relation_id": relation_id},
        }
        return before, after, inverse

    def _compensate_entity(
        self,
        payload: dict,
        version_id: str,
    ) -> tuple[dict, dict, dict]:
        entity = dict(payload.get("entity", {}))
        canonical_id = str(
            entity.get("canonical_id") or payload.get("canonical_id", "")
        )
        source_version_id = str(payload.get("source_version_id", ""))
        current = self.conn.execute(
            "SELECT * FROM canonical_entities WHERE canonical_id = ?",
            (canonical_id,),
        ).fetchone()
        before = dict(current) if current else {}
        self.conn.execute(
            """
            DELETE FROM entity_contributions
            WHERE canonical_id = ? AND version_id = ?
            """,
            (canonical_id, source_version_id),
        )
        self.conn.execute(
            """
            DELETE FROM entity_alias_contributions
            WHERE canonical_id = ? AND version_id = ?
            """,
            (canonical_id, source_version_id),
        )
        self.conn.execute(
            """
            DELETE FROM entity_mentions
            WHERE canonical_id = ? AND version_id = ?
            """,
            (canonical_id, source_version_id),
        )
        self._refresh_entity_aliases(canonical_id)

        current_last_version = str(before.get("last_version", ""))
        if entity and current_last_version == source_version_id:
            self.conn.execute(
                """
                UPDATE canonical_entities
                SET canonical_text = ?, entity_type = ?, confidence = ?,
                    status = ?, last_version = ?
                WHERE canonical_id = ?
                """,
                (
                    entity.get("canonical_text", ""),
                    entity.get("entity_type", "entity"),
                    float(entity.get("confidence", 0.5)),
                    entity.get("status", "active"),
                    version_id,
                    canonical_id,
                ),
            )
        elif before.get("status") != "retracted":
            remaining = self._entity_contribution_summary(canonical_id)
            if remaining is None:
                self.conn.execute(
                    """
                    UPDATE canonical_entities
                    SET status = 'retracted', last_version = ?
                    WHERE canonical_id = ?
                    """,
                    (version_id, canonical_id),
                )
            else:
                self.conn.execute(
                    """
                    UPDATE canonical_entities
                    SET canonical_text = ?, entity_type = ?, confidence = ?,
                        status = 'active', created_version = ?, last_version = ?
                    WHERE canonical_id = ?
                    """,
                    (
                        remaining["canonical_text"],
                        remaining["entity_type"],
                        remaining["confidence"],
                        remaining["created_version"],
                        version_id,
                        canonical_id,
                    ),
                )
        inverse = {
            "action": "upsert_entity",
            "object_type": "entity",
            "object_id": canonical_id,
            "after": before,
        }
        after = dict(
            self.conn.execute(
                "SELECT * FROM canonical_entities WHERE canonical_id = ?",
                (canonical_id,),
            ).fetchone()
            or {}
        )
        return before, after, inverse

    def _compensate_relation(
        self,
        payload: dict,
        version_id: str,
    ) -> tuple[dict, dict, dict]:
        relation = dict(payload.get("relation", {}))
        relation_id = str(
            relation.get("canonical_relation_id")
            or payload.get("canonical_relation_id", "")
        )
        source_version_id = str(payload.get("source_version_id", ""))
        current = self.conn.execute(
            """
            SELECT * FROM canonical_relations
            WHERE canonical_relation_id = ?
            """,
            (relation_id,),
        ).fetchone()
        before = dict(current) if current else {}
        self.conn.execute(
            """
            DELETE FROM relation_contributions
            WHERE canonical_relation_id = ? AND version_id = ?
            """,
            (relation_id, source_version_id),
        )
        self.conn.execute(
            """
            DELETE FROM relation_evidence
            WHERE canonical_relation_id = ? AND version_id = ?
            """,
            (relation_id, source_version_id),
        )
        current_last_version = str(before.get("last_version", ""))
        if relation and current_last_version == source_version_id:
            self.conn.execute(
                """
                UPDATE canonical_relations
                SET subject_id = ?, predicate = ?, object_id = ?,
                    qualifiers_hash = ?, confidence = ?, status = ?,
                    last_version = ?
                WHERE canonical_relation_id = ?
                """,
                (
                    relation.get("subject_id", ""),
                    relation.get("predicate", ""),
                    relation.get("object_id", ""),
                    relation.get("qualifiers_hash", ""),
                    float(relation.get("confidence", 0.5)),
                    relation.get("status", "active"),
                    version_id,
                    relation_id,
                ),
            )
        elif before.get("status") != "retracted":
            remaining = self._relation_contribution_summary(relation_id)
            if remaining is None:
                self.conn.execute(
                    """
                    UPDATE canonical_relations
                    SET status = 'retracted', last_version = ?
                    WHERE canonical_relation_id = ?
                    """,
                    (version_id, relation_id),
                )
            else:
                self.conn.execute(
                    """
                    UPDATE canonical_relations
                    SET subject_id = ?, predicate = ?, object_id = ?,
                        qualifiers_hash = ?, confidence = ?, status = 'active',
                        created_version = ?, last_version = ?
                    WHERE canonical_relation_id = ?
                    """,
                    (
                        remaining["subject_id"],
                        remaining["predicate"],
                        remaining["object_id"],
                        remaining["qualifiers_hash"],
                        remaining["confidence"],
                        remaining["created_version"],
                        version_id,
                        relation_id,
                    ),
                )
        inverse = {
            "action": "upsert_relation",
            "object_type": "relation",
            "object_id": relation_id,
            "after": before,
        }
        after = dict(
            self.conn.execute(
                """
                SELECT * FROM canonical_relations
                WHERE canonical_relation_id = ?
                """,
                (relation_id,),
            ).fetchone()
            or {}
        )
        return before, after, inverse

    def _entity_contribution_summary(
        self,
        canonical_id: str,
    ) -> dict[str, Any] | None:
        rows = self.conn.execute(
            """
            SELECT ec.canonical_text, ec.entity_type, ec.confidence,
                   ec.version_id, gv.created_at, gv.rowid AS graph_order
            FROM entity_contributions ec
            JOIN graph_versions gv ON gv.version_id = ec.version_id
            WHERE ec.canonical_id = ?
            ORDER BY gv.created_at, graph_order
            """,
            (canonical_id,),
        ).fetchall()
        if not rows:
            return None
        latest = rows[-1]
        return {
            "canonical_text": str(latest["canonical_text"]),
            "entity_type": str(latest["entity_type"]),
            "confidence": max(float(row["confidence"]) for row in rows),
            "created_version": str(rows[0]["version_id"]),
        }

    def _relation_contribution_summary(
        self,
        relation_id: str,
    ) -> dict[str, Any] | None:
        rows = self.conn.execute(
            """
            SELECT rc.subject_id, rc.predicate, rc.object_id,
                   rc.qualifiers_hash, rc.confidence, rc.version_id,
                   gv.created_at, gv.rowid AS graph_order
            FROM relation_contributions rc
            JOIN graph_versions gv ON gv.version_id = rc.version_id
            WHERE rc.canonical_relation_id = ?
            ORDER BY gv.created_at, graph_order
            """,
            (relation_id,),
        ).fetchall()
        if not rows:
            return None
        latest = rows[-1]
        return {
            "subject_id": str(latest["subject_id"]),
            "predicate": str(latest["predicate"]),
            "object_id": str(latest["object_id"]),
            "qualifiers_hash": str(latest["qualifiers_hash"]),
            "confidence": max(float(row["confidence"]) for row in rows),
            "created_version": str(rows[0]["version_id"]),
        }

    def _latest_entity_event_is_contribution(self, canonical_id: str) -> bool:
        row = self.conn.execute(
            """
            SELECT event_kind FROM (
                SELECT 'contribution' AS event_kind, gv.created_at,
                       gv.rowid AS graph_order
                FROM entity_contributions ec
                JOIN graph_versions gv ON gv.version_id = ec.version_id
                WHERE ec.canonical_id = ?
                UNION ALL
                SELECT 'tombstone' AS event_kind, gv.created_at,
                       gv.rowid AS graph_order
                FROM entity_tombstones et
                JOIN graph_versions gv ON gv.version_id = et.version_id
                WHERE et.canonical_id = ?
            )
            ORDER BY created_at DESC, graph_order DESC
            LIMIT 1
            """,
            (canonical_id, canonical_id),
        ).fetchone()
        return bool(row and row["event_kind"] == "contribution")

    def _latest_relation_event_is_contribution(self, relation_id: str) -> bool:
        row = self.conn.execute(
            """
            SELECT event_kind FROM (
                SELECT 'contribution' AS event_kind, gv.created_at,
                       gv.rowid AS graph_order
                FROM relation_contributions rc
                JOIN graph_versions gv ON gv.version_id = rc.version_id
                WHERE rc.canonical_relation_id = ?
                UNION ALL
                SELECT 'tombstone' AS event_kind, gv.created_at,
                       gv.rowid AS graph_order
                FROM relation_tombstones rt
                JOIN graph_versions gv ON gv.version_id = rt.version_id
                WHERE rt.canonical_relation_id = ?
            )
            ORDER BY created_at DESC, graph_order DESC
            LIMIT 1
            """,
            (relation_id, relation_id),
        ).fetchone()
        return bool(row and row["event_kind"] == "contribution")

    def _refresh_entity_aliases(self, canonical_id: str) -> None:
        rows = self.conn.execute(
            """
            SELECT eac.alias_norm, eac.alias_text, eac.entity_type,
                   eac.version_id, gv.created_at, gv.rowid AS graph_order
            FROM entity_alias_contributions eac
            JOIN graph_versions gv ON gv.version_id = eac.version_id
            WHERE eac.canonical_id = ?
            ORDER BY eac.alias_norm, gv.created_at, graph_order
            """,
            (canonical_id,),
        ).fetchall()
        grouped: dict[str, list[sqlite3.Row]] = {}
        for row in rows:
            grouped.setdefault(str(row["alias_norm"]), []).append(row)
        if grouped:
            placeholders = ",".join("?" for _ in grouped)
            self.conn.execute(
                f"""
                DELETE FROM entity_aliases
                WHERE canonical_id = ? AND alias_norm NOT IN ({placeholders})
                """,
                (canonical_id, *grouped),
            )
        else:
            self.conn.execute(
                "DELETE FROM entity_aliases WHERE canonical_id = ?",
                (canonical_id,),
            )
        for alias_norm, members in grouped.items():
            earliest = members[0]
            latest = members[-1]
            self.conn.execute(
                """
                INSERT INTO entity_aliases
                (canonical_id, alias_norm, alias_text, entity_type,
                 first_version, last_version)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(canonical_id, alias_norm) DO UPDATE SET
                    alias_text = excluded.alias_text,
                    entity_type = excluded.entity_type,
                    first_version = excluded.first_version,
                    last_version = excluded.last_version
                """,
                (
                    canonical_id,
                    alias_norm,
                    latest["alias_text"],
                    latest["entity_type"],
                    earliest["version_id"],
                    latest["version_id"],
                ),
            )

    def _safe_to_compensate(
        self,
        object_type: str,
        object_id: str,
        version_id: str,
        *,
        inverse: dict[str, Any],
    ) -> bool:
        if inverse.get("action") == "restore_entity_status":
            row = self.conn.execute(
                """
                SELECT 1 FROM entity_tombstones
                WHERE canonical_id = ? AND version_id = ?
                """,
                (object_id, version_id),
            ).fetchone()
            return bool(row)
        if inverse.get("action") == "restore_relation_status":
            row = self.conn.execute(
                """
                SELECT 1 FROM relation_tombstones
                WHERE canonical_relation_id = ? AND version_id = ?
                """,
                (object_id, version_id),
            ).fetchone()
            return bool(row)
        if inverse.get("action") in {
            "compensate_entity",
            "compensate_relation",
        }:
            table = (
                "canonical_entities"
                if object_type == "entity"
                else "canonical_relations"
            )
            id_column = (
                "canonical_id"
                if object_type == "entity"
                else "canonical_relation_id"
            )
            row = self.conn.execute(
                f"SELECT 1 FROM {table} WHERE {id_column} = ?",
                (object_id,),
            ).fetchone()
            if not row:
                return False
            inverse_payload = dict(inverse.get("after", {}))
            if (
                object_type == "entity"
                and inverse_payload.get("created_by_source_version")
            ):
                surviving_contribution = self.conn.execute(
                    """
                    SELECT 1 FROM entity_contributions
                    WHERE canonical_id = ? AND version_id != ?
                    LIMIT 1
                    """,
                    (object_id, version_id),
                ).fetchone()
                later_dependency = self.conn.execute(
                    """
                    SELECT 1 FROM canonical_relations
                    WHERE status = 'active'
                      AND (subject_id = ? OR object_id = ?)
                      AND last_version != ?
                    LIMIT 1
                    """,
                    (object_id, object_id, version_id),
                ).fetchone()
                if later_dependency and not surviving_contribution:
                    return False
            return True
        if object_type == "entity":
            row = self.conn.execute(
                "SELECT last_version FROM canonical_entities WHERE canonical_id = ?",
                (object_id,),
            ).fetchone()
        else:
            row = self.conn.execute(
                """
                SELECT last_version FROM canonical_relations
                WHERE canonical_relation_id = ?
                """,
                (object_id,),
            ).fetchone()
        return bool(row and str(row[0]) == version_id)

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "CanonicalGraphStore":
        return self

    def __exit__(self, *_args) -> None:
        self.close()


def _normalize_alias(value: str) -> str:
    return " ".join(value.casefold().replace("_", " ").split())


def _version_id(patch_id: str) -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S%f")
    suffix = patch_id.replace("patch-", "")[:10] or "manual"
    return f"gv-{timestamp}-{suffix}"


def _json(value: Any) -> str:
    return json.dumps(value or {}, ensure_ascii=False, sort_keys=True)


def _content_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(encoded.encode()).hexdigest()
