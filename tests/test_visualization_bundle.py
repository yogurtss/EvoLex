from __future__ import annotations

import json
from pathlib import Path
import re

from evolex.repositories.canonical import CanonicalGraphStore
from evolex.repositories.candidates import CandidateRegistry
from evolex.visualization.dashboard import build_dashboard, build_dashboard_bundle


def _dashboard_payload(path: Path) -> dict:
    source = path.read_text(encoding="utf-8")
    prefix = "const DATA="
    start = source.index(prefix) + len(prefix)
    end = source.index(";\nconst S=", start)
    return json.loads(source[start:end])


def _assert_self_contained(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    assert not re.search(r"<script\b[^>]*\bsrc\s*=", source, re.IGNORECASE)
    assert not re.search(r"<link\b", source, re.IGNORECASE)
    assert not re.search(r"https?://", source, re.IGNORECASE)
    assert not re.search(
        r"(?:src|href)\s*=\s*['\"]\s*(?:https?:)?//",
        source,
        re.IGNORECASE,
    )
    assert "fetch(" not in source.casefold()
    assert "@import" not in source.casefold()


def _entity_operation(
    *,
    operation_id: str,
    canonical_id: str,
    text: str,
    run_id: str,
    segment_id: str,
) -> dict:
    return {
        "operation_id": operation_id,
        "action": "upsert_entity",
        "object_type": "entity",
        "object_id": canonical_id,
        "after": {
            "canonical_id": canonical_id,
            "canonical_text": text,
            "entity_type": "component",
            "confidence": 0.9,
            "aliases": [text],
        },
        "mentions": [
            {
                "mention_uid": f"{run_id}:{operation_id}:mention",
                "mention_text": text,
                "segment_id": segment_id,
                "evidence_text": f"{text} is explicitly mentioned.",
            }
        ],
        "evidence_contract": {"provenance_complete": True},
    }


def _relation_operation(
    *,
    operation_id: str,
    relation_id: str,
    subject_id: str,
    object_id: str,
    run_id: str,
    segment_id: str,
    evidence_text: str,
) -> dict:
    return {
        "operation_id": operation_id,
        "action": "upsert_relation",
        "object_type": "relation",
        "object_id": relation_id,
        "after": {
            "canonical_relation_id": relation_id,
            "subject_id": subject_id,
            "predicate": "connects_to",
            "object_id": object_id,
            "qualifiers_hash": "",
            "confidence": 0.88,
        },
        "evidence": [
            {
                "evidence_uid": f"{run_id}:{operation_id}:evidence",
                "evidence_id": f"ev-{operation_id}",
                "segment_id": segment_id,
                "evidence_text": evidence_text,
                "confidence": 0.88,
            }
        ],
        "evidence_contract": {"provenance_complete": True},
    }


def _commit_connected_document(
    store: CanonicalGraphStore,
    *,
    document_id: str,
    run_id: str,
    private_id: str,
    private_text: str,
    relation_id: str,
    evidence_text: str,
) -> None:
    operations = [
        _entity_operation(
            operation_id=f"op-{run_id}-shared",
            canonical_id="ce-shared",
            text="Shared Hub",
            run_id=run_id,
            segment_id=f"seg-{run_id}-1",
        ),
        _entity_operation(
            operation_id=f"op-{run_id}-private",
            canonical_id=private_id,
            text=private_text,
            run_id=run_id,
            segment_id=f"seg-{run_id}-2",
        ),
        _relation_operation(
            operation_id=f"op-{run_id}-relation",
            relation_id=relation_id,
            subject_id="ce-shared",
            object_id=private_id,
            run_id=run_id,
            segment_id=f"seg-{run_id}-3",
            evidence_text=evidence_text,
        ),
    ]
    store.commit_patch(
        {
            "patch_id": f"patch-{run_id}",
            "parent_version_id": store.latest_version_id(),
            "operations": operations,
        },
        run_id=run_id,
        document_id=document_id,
    )


def _commit_empty_document_version(
    store: CanonicalGraphStore,
    *,
    document_id: str,
    run_id: str,
) -> None:
    store.commit_patch(
        {
            "patch_id": f"patch-{run_id}",
            "parent_version_id": store.latest_version_id(),
            "operations": [],
        },
        run_id=run_id,
        document_id=document_id,
    )


def test_empty_store_still_builds_index_and_global_page(tmp_path: Path) -> None:
    bundle = build_dashboard_bundle(
        output_dir=tmp_path / "visualizations",
        canonical_dir=tmp_path / "canonical",
        registry_dir=tmp_path / "registry",
        schema_dir=tmp_path / "schema",
    )

    assert bundle.index_path.is_file()
    assert bundle.global_path.is_file()
    assert bundle.document_paths == {}
    assert "暂无源文档" in bundle.index_path.read_text(encoding="utf-8")

    payload = _dashboard_payload(bundle.global_path)
    assert payload["scope"]["kind"] == "global"
    assert payload["document_ids"] == []
    assert payload["snapshot"]["entities"] == []
    assert payload["snapshot"]["relations"] == []
    assert payload["snapshot"]["relation_evidence"] == []

    _assert_self_contained(bundle.index_path)
    _assert_self_contained(bundle.global_path)


def test_document_pages_are_isolated_and_global_page_is_the_union(
    tmp_path: Path,
) -> None:
    canonical_dir = tmp_path / "canonical"
    with CanonicalGraphStore(canonical_dir) as store:
        _commit_connected_document(
            store,
            document_id="DOC-alpha",
            run_id="RUN-alpha",
            private_id="ce-alpha",
            private_text="Alpha Private Node",
            relation_id="cr-alpha",
            evidence_text="alpha-evidence-only",
        )
        _commit_connected_document(
            store,
            document_id="DOC-beta",
            run_id="RUN-beta",
            private_id="ce-beta",
            private_text="Beta Private Node",
            relation_id="cr-beta",
            evidence_text="beta-evidence-only",
        )

    bundle = build_dashboard_bundle(
        output_dir=tmp_path / "visualizations",
        canonical_dir=canonical_dir,
        registry_dir=tmp_path / "registry",
        schema_dir=tmp_path / "schema",
    )
    alpha = _dashboard_payload(bundle.document_paths["DOC-alpha"])
    beta = _dashboard_payload(bundle.document_paths["DOC-beta"])
    global_payload = _dashboard_payload(bundle.global_path)

    assert {item["canonical_id"] for item in alpha["snapshot"]["entities"]} == {
        "ce-shared",
        "ce-alpha",
    }
    assert {item["canonical_relation_id"] for item in alpha["snapshot"]["relations"]} == {
        "cr-alpha"
    }
    assert {
        item["document_id"]
        for item in alpha["snapshot"]["relation_evidence"]
    } == {"DOC-alpha"}
    assert {
        item["evidence_text"]
        for item in alpha["snapshot"]["relation_evidence"]
    } == {"alpha-evidence-only"}

    assert {item["canonical_id"] for item in beta["snapshot"]["entities"]} == {
        "ce-shared",
        "ce-beta",
    }
    assert {item["canonical_relation_id"] for item in beta["snapshot"]["relations"]} == {
        "cr-beta"
    }
    assert {
        item["document_id"]
        for item in beta["snapshot"]["relation_evidence"]
    } == {"DOC-beta"}
    assert {
        item["evidence_text"]
        for item in beta["snapshot"]["relation_evidence"]
    } == {"beta-evidence-only"}

    global_snapshot = global_payload["snapshot"]
    assert {item["canonical_id"] for item in global_snapshot["entities"]} == {
        "ce-shared",
        "ce-alpha",
        "ce-beta",
    }
    assert {
        item["canonical_relation_id"] for item in global_snapshot["relations"]
    } == {"cr-alpha", "cr-beta"}
    assert {
        item["evidence_text"] for item in global_snapshot["relation_evidence"]
    } == {"alpha-evidence-only", "beta-evidence-only"}
    assert set(global_payload["document_ids"]) == {"DOC-alpha", "DOC-beta"}

    alpha_source = bundle.document_paths["DOC-alpha"].read_text(encoding="utf-8")
    beta_source = bundle.document_paths["DOC-beta"].read_text(encoding="utf-8")
    assert "Beta Private Node" not in alpha_source
    assert "beta-evidence-only" not in alpha_source
    assert "Alpha Private Node" not in beta_source
    assert "alpha-evidence-only" not in beta_source

    for path in [
        bundle.index_path,
        bundle.global_path,
        *bundle.document_paths.values(),
    ]:
        _assert_self_contained(path)


def test_version_only_documents_get_empty_pages_and_collision_safe_names(
    tmp_path: Path,
) -> None:
    canonical_dir = tmp_path / "canonical"
    document_ids = ("DOC/collision", "DOC?collision")
    with CanonicalGraphStore(canonical_dir) as store:
        _commit_empty_document_version(
            store,
            document_id=document_ids[0],
            run_id="RUN-empty-a",
        )
        _commit_empty_document_version(
            store,
            document_id=document_ids[1],
            run_id="RUN-empty-b",
        )

    first = build_dashboard_bundle(
        output_dir=tmp_path / "first",
        canonical_dir=canonical_dir,
        registry_dir=tmp_path / "registry",
        schema_dir=tmp_path / "schema",
    )
    second = build_dashboard_bundle(
        output_dir=tmp_path / "second",
        canonical_dir=canonical_dir,
        registry_dir=tmp_path / "registry",
        schema_dir=tmp_path / "schema",
    )

    first_names = {
        document_id: first.document_paths[document_id].name
        for document_id in document_ids
    }
    second_names = {
        document_id: second.document_paths[document_id].name
        for document_id in document_ids
    }
    assert first_names == second_names
    assert first_names[document_ids[0]] != first_names[document_ids[1]]

    for document_id, path in first.document_paths.items():
        assert path.parent == first.output_dir / "documents"
        assert path.name == Path(path.name).name
        assert re.fullmatch(r"evolex-doc-[A-Za-z0-9._-]+\.html", path.name)
        payload = _dashboard_payload(path)
        assert payload["scope"]["kind"] == "document"
        assert payload["scope"]["document_id"] == document_id
        assert payload["snapshot"]["entities"] == []
        assert payload["snapshot"]["relations"] == []
        assert payload["snapshot"]["relation_evidence"] == []
        assert len(payload["history"]) == 1
        _assert_self_contained(path)

    index_source = first.index_path.read_text(encoding="utf-8")
    assert all(document_id in index_source for document_id in document_ids)
    assert all(name in index_source for name in first_names.values())


def test_single_document_builder_uses_the_same_isolated_projection(
    tmp_path: Path,
) -> None:
    canonical_dir = tmp_path / "canonical"
    with CanonicalGraphStore(canonical_dir) as store:
        _commit_connected_document(
            store,
            document_id="DOC-one",
            run_id="RUN-one",
            private_id="ce-one",
            private_text="One Private Node",
            relation_id="cr-one",
            evidence_text="one-evidence-only",
        )
        _commit_connected_document(
            store,
            document_id="DOC-other",
            run_id="RUN-other",
            private_id="ce-other",
            private_text="Other Private Node",
            relation_id="cr-other",
            evidence_text="other-evidence-only",
        )

    output = build_dashboard(
        output_path=tmp_path / "single.html",
        canonical_dir=canonical_dir,
        registry_dir=tmp_path / "registry",
        schema_dir=tmp_path / "schema",
        document_id="DOC-one",
    )
    payload = _dashboard_payload(output)

    assert payload["scope"]["document_id"] == "DOC-one"
    assert {item["canonical_relation_id"] for item in payload["snapshot"]["relations"]} == {
        "cr-one"
    }
    assert {
        item["evidence_text"]
        for item in payload["snapshot"]["relation_evidence"]
    } == {"one-evidence-only"}
    assert "Other Private Node" not in output.read_text(encoding="utf-8")
    assert "other-evidence-only" not in output.read_text(encoding="utf-8")
    _assert_self_contained(output)


def test_multiple_runs_share_one_document_page_and_bind_latest_registry(
    tmp_path: Path,
) -> None:
    canonical_dir = tmp_path / "canonical"
    document_id = "DOC-same-content"
    with CanonicalGraphStore(canonical_dir) as store:
        _commit_connected_document(
            store,
            document_id=document_id,
            run_id="RUN-old",
            private_id="ce-old",
            private_text="Old Run Node",
            relation_id="cr-old",
            evidence_text="old-run-evidence",
        )
        _commit_connected_document(
            store,
            document_id=document_id,
            run_id="RUN-new",
            private_id="ce-new",
            private_text="New Run Node",
            relation_id="cr-new",
            evidence_text="new-run-evidence",
        )

    registry_dir = tmp_path / "registry"
    registry = CandidateRegistry(registry_dir)
    for run_id, action in (
        ("RUN-old", "old-registry-action"),
        ("RUN-new", "new-registry-action"),
    ):
        registry.replace_run_snapshot(
            run_id,
            entity_decisions=[],
            policy_decisions=[],
            audit_events=[],
            merge_decisions=[],
            agent_trace=[
                {
                    "step_index": 1,
                    "agent_name": "audit-agent",
                    "selected_action": action,
                }
            ],
            candidates=[],
            quarantine_record=None,
        )
    (registry_dir / "RUN-old_registry.sqlite").touch()

    bundle = build_dashboard_bundle(
        output_dir=tmp_path / "visualizations",
        canonical_dir=canonical_dir,
        registry_dir=registry_dir,
        schema_dir=tmp_path / "schema",
    )

    assert set(bundle.document_paths) == {document_id}
    payload = _dashboard_payload(bundle.document_paths[document_id])
    assert {item["run_id"] for item in payload["history"]} == {
        "RUN-old",
        "RUN-new",
    }
    assert {
        item["canonical_relation_id"]
        for item in payload["snapshot"]["relations"]
    } == {"cr-old", "cr-new"}
    assert payload["scope"]["selected_run_id"] == "RUN-new"
    assert payload["governance"]["binding_status"] == "exact_run_id"
    assert payload["governance"]["registry_run_ids"] == ["RUN-new"]
    assert payload["governance"]["agent_trace"][0]["selected_action"] == (
        "new-registry-action"
    )
    source = bundle.document_paths[document_id].read_text(encoding="utf-8")
    assert "old-registry-action" not in source
