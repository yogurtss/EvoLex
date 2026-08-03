from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from evolex.agents.deepseek_client import HeuristicExtractor, HeuristicTypedExtractor
from evolex.graph.runner import run_pipeline_text
from evolex.repositories.canonical import CanonicalGraphStore


DEFAULT_CORPUS = Path("benchmarks/patent_joint_kg_corpus.json")


@dataclass(frozen=True)
class PatentBenchmarkResult:
    status: str
    document_count: int
    json_path: str
    markdown_path: str
    report: dict[str, Any]


def run_patent_benchmark(
    output_dir: Path | None = None,
    corpus_path: Path | None = None,
) -> PatentBenchmarkResult:
    """Compare the historical separate path with the joint Agent path.

    This workflow is intentionally deterministic and network-free.  It is an
    engineering regression for this repository, not an external academic
    benchmark and not evidence of state-of-the-art performance.
    """
    target_dir = output_dir or Path("data/patent_benchmark")
    target_dir.mkdir(parents=True, exist_ok=True)
    corpus_file = corpus_path or DEFAULT_CORPUS
    corpus = json.loads(corpus_file.read_text(encoding="utf-8"))
    documents = list(corpus.get("documents", []))
    if not documents:
        raise ValueError(f"benchmark corpus contains no documents: {corpus_file}")

    legacy = _run_variant(
        name="legacy_separate",
        pipeline="system",
        extractor=HeuristicExtractor(),
        documents=documents,
        output_dir=target_dir / "legacy_separate",
    )
    joint = _run_variant(
        name="joint_agent",
        pipeline="agent",
        extractor=HeuristicTypedExtractor(),
        documents=documents,
        output_dir=target_dir / "joint_agent",
    )
    alias_metrics = _alias_metrics(
        documents,
        target_dir / "joint_agent" / "canonical",
    )
    rollback_metrics = _rollback_probe(target_dir / "rollback_probe")

    report: dict[str, Any] = {
        "status": "ok",
        "benchmark_type": "deterministic_project_engineering_regression",
        "created_at": datetime.now(UTC).isoformat(),
        "corpus_path": str(corpus_file),
        "document_count": len(documents),
        "protocol": {
            "legacy_separate": (
                "HeuristicExtractor -> independent typed conversion -> "
                "post-resolution relation fallback"
            ),
            "joint_agent": (
                "HeuristicTypedExtractor joint mention/relation candidates -> "
                "mention-ID endpoint resolution -> entity/relation canonicalization "
                "Agents -> evidence contract -> shadow gate -> canonical commit"
            ),
            "network_calls": 0,
            "limitations": list(corpus.get("limitations", [])),
        },
        "variants": {
            "legacy_separate": legacy,
            "joint_agent": joint,
        },
        "canonicalization": alias_metrics,
        "evolution_safety": {
            **joint["evolution_safety"],
            "rollback_probe": rollback_metrics,
        },
        "deltas": _metric_deltas(legacy["metrics"], joint["metrics"]),
        "interpretation": [
            (
                "On this frozen project-owned corpus, joint extraction preserves "
                "mention-scoped relation endpoints and evidence IDs through materialization."
            ),
            (
                "The canonical registry consolidates the declared API Gateway/API GW "
                "alias group across independent document runs."
            ),
            (
                "Shadow replay and compensating rollback are executable safety checks; "
                "they do not establish novelty or freedom to operate."
            ),
        ],
    }

    json_path = target_dir / "patent_benchmark_report.json"
    markdown_path = target_dir / "patent_benchmark_report.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    markdown_path.write_text(_render_markdown(report), encoding="utf-8")
    return PatentBenchmarkResult(
        status="ok",
        document_count=len(documents),
        json_path=str(json_path),
        markdown_path=str(markdown_path),
        report=report,
    )


def _run_variant(
    *,
    name: str,
    pipeline: str,
    extractor,
    documents: list[dict[str, Any]],
    output_dir: Path,
) -> dict[str, Any]:
    gold_entities: set[tuple[str, str]] = set()
    predicted_entities: set[tuple[str, str]] = set()
    gold_relations: set[tuple[str, str, str, str]] = set()
    predicted_relations: set[tuple[str, str, str, str]] = set()
    predicted_endpoint_pairs: set[tuple[str, str, str]] = set()
    endpoint_valid = 0
    relation_count = 0
    evidence_complete = 0
    joint_materialized = 0
    published = 0
    states: list[dict[str, Any]] = []
    document_reports: list[dict[str, Any]] = []
    started = perf_counter()

    for document in documents:
        result = run_pipeline_text(
            str(document["text"]),
            pipeline=pipeline,
            output_dir=output_dir,
            extractor=extractor,
        )
        state = result.state
        states.append(state)
        document_id = str(document["id"])
        entities = list(state.get("entities", []))
        entity_by_id = {
            str(item.get("entity_id", "")): _normalize(
                str(item.get("canonical_text", ""))
            )
            for item in entities
        }
        gold_doc_entities = {
            _normalize(str(value)) for value in document.get("entities", [])
        }
        predicted_doc_entities = set(entity_by_id.values())
        gold_entities.update((document_id, value) for value in gold_doc_entities)
        predicted_entities.update(
            (document_id, value) for value in predicted_doc_entities if value
        )

        gold_doc_relations = {
            (
                _normalize(str(item[0])),
                _predicate(str(item[1])),
                _normalize(str(item[2])),
            )
            for item in document.get("relations", [])
        }
        gold_relations.update(
            (document_id, subject, predicate, obj)
            for subject, predicate, obj in gold_doc_relations
        )
        predicted_doc_relations: set[tuple[str, str, str]] = set()
        for relation in state.get("relations", []):
            relation_count += 1
            subject_id = str(relation.get("subject_entity_id", ""))
            object_id = str(relation.get("object_entity_id", ""))
            subject = entity_by_id.get(subject_id, "")
            obj = entity_by_id.get(object_id, "")
            predicate = _predicate(str(relation.get("predicate", "")))
            if subject and obj:
                endpoint_valid += 1
            predicted_doc_relations.add((subject, predicate, obj))
            predicted_relations.add((document_id, subject, predicate, obj))
            predicted_endpoint_pairs.add((document_id, subject, obj))
            if (
                relation.get("evidence")
                and relation.get("evidence_ids")
                and relation.get("segment_ids")
            ):
                evidence_complete += 1
            if relation.get("extraction_mode") == "joint":
                joint_materialized += 1
        if result.status == "published":
            published += 1
        document_reports.append(
            {
                "document_id": document_id,
                "status": result.status,
                "policy_action": result.policy_action,
                "relation_extraction_mode": state.get(
                    "relation_extraction_mode", "none"
                ),
                "gold_entities": sorted(gold_doc_entities),
                "predicted_entities": sorted(predicted_doc_entities),
                "gold_relations": sorted(gold_doc_relations),
                "predicted_relations": sorted(predicted_doc_relations),
            }
        )

    entity_scores = _prf(gold_entities, predicted_entities)
    relation_scores = _prf(gold_relations, predicted_relations)
    gold_endpoint_pairs = {
        (document_id, subject, obj)
        for document_id, subject, _predicate_name, obj in gold_relations
    }
    endpoint_scores = _prf(gold_endpoint_pairs, predicted_endpoint_pairs)
    elapsed = perf_counter() - started
    safety_states = [
        state
        for state in states
        if state.get("shadow_evaluation") or state.get("evolution_decision")
    ]
    return {
        "name": name,
        "metrics": {
            "entity_precision": entity_scores["precision"],
            "entity_recall": entity_scores["recall"],
            "entity_f1": entity_scores["f1"],
            "relation_precision": relation_scores["precision"],
            "relation_recall": relation_scores["recall"],
            "relation_f1": relation_scores["f1"],
            "relation_endpoint_pair_accuracy": endpoint_scores["recall"],
            "endpoint_id_validity": _ratio(endpoint_valid, relation_count),
            "relation_evidence_contract_coverage": _ratio(
                evidence_complete, relation_count
            ),
            "joint_materialization_rate": _ratio(joint_materialized, relation_count),
            "publish_rate": _ratio(published, len(documents)),
            "elapsed_seconds": round(elapsed, 4),
            "predicted_entity_count": len(predicted_entities),
            "predicted_relation_count": len(predicted_relations),
        },
        "counts": {
            "gold_entities": len(gold_entities),
            "predicted_entities": len(predicted_entities),
            "gold_relations": len(gold_relations),
            "predicted_relations": len(predicted_relations),
        },
        "evolution_safety": {
            "evaluated_patch_count": len(safety_states),
            "shadow_gate_pass_rate": _ratio(
                sum(
                    bool(state.get("shadow_evaluation", {}).get(
                        "passed_after_compensation"
                    ))
                    for state in safety_states
                ),
                len(safety_states),
            ),
            "deterministic_replay_pass_rate": _ratio(
                sum(
                    bool(state.get("shadow_evaluation", {}).get(
                        "deterministic_replay"
                    ))
                    for state in safety_states
                ),
                len(safety_states),
            ),
            "consensus_accept_rate": _ratio(
                sum(
                    bool(state.get("evolution_decision", {}).get("accepted"))
                    for state in safety_states
                ),
                len(safety_states),
            ),
            "committed_version_count": sum(
                state.get("evolution_commit", {}).get("status") == "committed"
                for state in safety_states
            ),
        },
        "documents": document_reports,
    }


def _alias_metrics(
    documents: list[dict[str, Any]],
    canonical_dir: Path,
) -> dict[str, Any]:
    groups: dict[str, set[str]] = {}
    for document in documents:
        for group_name, aliases in document.get("alias_groups", {}).items():
            groups.setdefault(str(group_name), set()).update(
                _normalize(str(alias)) for alias in aliases
            )
    with CanonicalGraphStore(canonical_dir) as store:
        snapshot = store.snapshot()
    canonical_entities = list(snapshot.get("entities", []))
    details = []
    baseline_surface_count = 0
    canonical_identity_count = 0
    for group_name, aliases in sorted(groups.items()):
        baseline_surface_count += len(aliases)
        matching = []
        for entity in canonical_entities:
            entity_aliases = {
                _normalize(str(value)) for value in entity.get("aliases", [])
            }
            entity_aliases.add(_normalize(str(entity.get("canonical_text", ""))))
            if entity_aliases & aliases:
                matching.append(str(entity.get("canonical_id", "")))
        identity_count = len(set(matching))
        canonical_identity_count += identity_count
        details.append(
            {
                "group": group_name,
                "declared_surface_forms": sorted(aliases),
                "canonical_identity_ids": sorted(set(matching)),
                "canonical_identity_count": identity_count,
            }
        )
    reduction = _ratio(
        baseline_surface_count - canonical_identity_count,
        baseline_surface_count,
    )
    return {
        "alias_group_count": len(groups),
        "surface_identity_count_before": baseline_surface_count,
        "canonical_identity_count_after": canonical_identity_count,
        "duplicate_identity_reduction": reduction,
        "groups": details,
    }


def _rollback_probe(output_dir: Path) -> dict[str, Any]:
    with CanonicalGraphStore(output_dir / "canonical") as store:
        initial = store.snapshot()
        initial_history_count = len(store.history(limit=10000))
    result = run_pipeline_text(
        "Rollback Probe depends on Version Ledger.",
        pipeline="agent",
        output_dir=output_dir,
        extractor=HeuristicTypedExtractor(),
    )
    version_id = str(result.state.get("canonical_version_id", ""))
    with CanonicalGraphStore(output_dir / "canonical") as store:
        before = store.snapshot()
        history_before_rollback = len(store.history(limit=10000))
        compensation = store.rollback_version(
            version_id,
            reason="deterministic patent benchmark rollback probe",
        )
        after = store.snapshot()
        history_after_rollback = len(store.history(limit=10000))
    state_restored = (
        len(after.get("entities", [])) == len(initial.get("entities", []))
        and len(after.get("relations", [])) == len(initial.get("relations", []))
        and len(after.get("relation_evidence", []))
        == len(initial.get("relation_evidence", []))
    )
    return {
        "target_version_id": version_id,
        "pre_rollback_entity_count": len(before.get("entities", [])),
        "pre_rollback_relation_count": len(before.get("relations", [])),
        "post_rollback_entity_count": len(after.get("entities", [])),
        "post_rollback_relation_count": len(after.get("relations", [])),
        "initial_history_count": initial_history_count,
        "history_preserved": (
            history_after_rollback == history_before_rollback + 1
        ),
        "compensation_version_id": compensation.get("version_id", ""),
        "compensation_operation_count": compensation.get("operation_count", 0),
        "passed": bool(
            version_id
            and before.get("entities")
            and before.get("relations")
            and state_restored
            and history_after_rollback == history_before_rollback + 1
        ),
    }


def _metric_deltas(
    legacy: dict[str, Any],
    joint: dict[str, Any],
) -> dict[str, float]:
    comparable = (
        "entity_f1",
        "relation_f1",
        "relation_endpoint_pair_accuracy",
        "endpoint_id_validity",
        "relation_evidence_contract_coverage",
        "joint_materialization_rate",
        "publish_rate",
    )
    return {
        key: round(float(joint.get(key, 0.0)) - float(legacy.get(key, 0.0)), 4)
        for key in comparable
    }


def _prf(gold: set, predicted: set) -> dict[str, float]:
    true_positive = len(gold & predicted)
    precision = _ratio(true_positive, len(predicted))
    recall = _ratio(true_positive, len(gold))
    f1 = (
        round(2 * precision * recall / (precision + recall), 4)
        if precision + recall
        else 0.0
    )
    return {"precision": precision, "recall": recall, "f1": f1}


def _ratio(numerator: int | float, denominator: int | float) -> float:
    if not denominator:
        return 0.0
    return round(float(numerator) / float(denominator), 4)


def _normalize(value: str) -> str:
    normalized = value.casefold().strip()
    normalized = re.sub(r"[_\-/]+", " ", normalized)
    normalized = re.sub(r"[^a-z0-9\s]+", "", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _predicate(value: str) -> str:
    aliases = {
        "requires": "depends_on",
        "rely_on": "depends_on",
        "relies_on": "depends_on",
        "is_part_of": "part_of",
        "associated_with": "related_to",
    }
    normalized = value.casefold().strip().replace(" ", "_")
    return aliases.get(normalized, normalized)


def _render_markdown(report: dict[str, Any]) -> str:
    legacy = report["variants"]["legacy_separate"]["metrics"]
    joint = report["variants"]["joint_agent"]["metrics"]
    labels = (
        ("Entity F1", "entity_f1"),
        ("Relation F1", "relation_f1"),
        ("Correct relation endpoint-pair recall", "relation_endpoint_pair_accuracy"),
        ("Endpoint ID validity", "endpoint_id_validity"),
        ("Relation evidence-contract coverage", "relation_evidence_contract_coverage"),
        ("Joint materialization rate", "joint_materialization_rate"),
        ("Publish rate", "publish_rate"),
    )
    lines = [
        "# EvoLex Joint Extraction Patent Engineering Benchmark",
        "",
        "> This is a deterministic project-owned engineering regression, not an "
        "external benchmark or a state-of-the-art claim.",
        "",
        f"Corpus documents: {report['document_count']}; network calls: 0.",
        "",
        "| Metric | Legacy separate | Joint + Agent | Delta |",
        "|---|---:|---:|---:|",
    ]
    for label, key in labels:
        delta = float(joint.get(key, 0.0)) - float(legacy.get(key, 0.0))
        lines.append(
            f"| {label} | {legacy.get(key, 0.0):.4f} | "
            f"{joint.get(key, 0.0):.4f} | {delta:+.4f} |"
        )
    canonical = report["canonicalization"]
    safety = report["evolution_safety"]
    rollback = safety["rollback_probe"]
    lines.extend(
        [
            "",
            "## Canonicalization and evolution safety",
            "",
            f"- Declared alias surface identities before canonicalization: "
            f"{canonical['surface_identity_count_before']}.",
            f"- Canonical identities after cross-document Agent consolidation: "
            f"{canonical['canonical_identity_count_after']}.",
            f"- Duplicate identity reduction on declared alias groups: "
            f"{canonical['duplicate_identity_reduction']:.4f}.",
            f"- Shadow gate pass rate: {safety['shadow_gate_pass_rate']:.4f}.",
            f"- Deterministic replay pass rate: "
            f"{safety['deterministic_replay_pass_rate']:.4f}.",
            f"- Consensus accept rate: {safety['consensus_accept_rate']:.4f}.",
            f"- Compensating rollback probe passed: {rollback['passed']}.",
            f"- Version history preserved after rollback: "
            f"{rollback['history_preserved']}.",
            "",
            "## Limitations",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in report["protocol"]["limitations"])
    lines.append("")
    return "\n".join(lines)
