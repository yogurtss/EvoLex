from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from evolex.cli import app
from evolex.repositories.schema_store import SchemaCandidateStore


def _proposal(name: str, run_id: str, proposal_id: str | None = None) -> dict:
    return {
        "proposal_id": proposal_id or f"scp-{run_id}",
        "proposal_type": "new_relation",
        "name": name,
        "description": f"Proposal for {name}",
        "supporting_texts": [f"{name} evidence {run_id}"],
        "evidence_spans": [f"seg-{run_id}"],
        "occurrence_count": 1,
        "independent_document_count": 1,
        "relation_pattern_consistency": 0.5,
        "evidence_coverage": 1.0,
        "source_run_ids": [run_id],
        "schema_version": "test-0.1.0",
    }


def _ready_store(tmp_path: Path) -> tuple[SchemaCandidateStore, dict]:
    store = SchemaCandidateStore(tmp_path / "schema_candidates")
    for idx in range(3):
        store.put_proposal(_proposal("supports_feature", f"RUN-{idx}", proposal_id=f"scp-ready-{idx}"))
    proposal = store.get_proposal_by_name("supports_feature")
    assert proposal is not None
    return store, proposal


def test_promotion_candidates_require_stability_signals(tmp_path: Path) -> None:
    store = SchemaCandidateStore(tmp_path / "schema_candidates")
    store.put_proposal(_proposal("too_new", "RUN-1", proposal_id="scp-low"))

    assert store.get_promotion_candidates() == []
    decision = store.evaluate_promotion("scp-low")
    assert decision["action"] == "hold"
    assert "insufficient_occurrences" in decision["reasons"]


def test_ready_proposal_promotes_and_writes_ledger(tmp_path: Path) -> None:
    store, proposal = _ready_store(tmp_path)

    ready = store.get_promotion_candidates()
    assert ready
    decision = store.evaluate_promotion(proposal["proposal_id"])
    assert decision["action"] == "promote"

    promoted = store.promote_proposal(
        proposal["proposal_id"],
        target_schema_version="test-0.2.0",
        reason=", ".join(decision["reasons"]),
    )
    ledger = store.get_promotions()

    assert promoted["status"] == "promoted"
    assert ledger[0]["action"] == "promoted"
    assert ledger[0]["target_schema_version"] == "test-0.2.0"


def test_high_risk_report_blocks_promotion(tmp_path: Path) -> None:
    store, proposal = _ready_store(tmp_path)
    report = {
        "governance": {
            "rollback_recommended": True,
            "canary_ready": False,
            "high_risk_policy_decision_count": 1,
        }
    }

    decision = store.evaluate_promotion(proposal["proposal_id"], eval_report=report)
    assert decision["action"] == "block"

    blocked = store.block_proposal(
        proposal["proposal_id"],
        reason=", ".join(decision["reasons"]),
        report_path="shadow_report.json",
    )
    ledger = store.get_promotions()

    assert blocked["status"] == "blocked"
    assert ledger[0]["action"] == "blocked"
    assert "rollback_recommended" in ledger[0]["reason"]


def test_schema_cli_lists_and_promotes(tmp_path: Path) -> None:
    store, proposal = _ready_store(tmp_path)
    schema_dir = store.store_dir
    runner = CliRunner()

    candidates = runner.invoke(app, ["schema", "candidates", "--schema-dir", str(schema_dir)])
    ready = runner.invoke(app, ["schema", "promote-ready", "--schema-dir", str(schema_dir)])
    promoted = runner.invoke(
        app,
        [
            "schema",
            "promote",
            "--schema-dir",
            str(schema_dir),
            "--proposal-id",
            proposal["proposal_id"],
            "--target-schema-version",
            "test-0.2.0",
        ],
    )
    promotions = runner.invoke(app, ["schema", "promotions", "--schema-dir", str(schema_dir)])

    assert candidates.exit_code == 0
    assert "supports_feature" in candidates.output
    assert ready.exit_code == 0
    assert proposal["proposal_id"] in ready.output
    assert promoted.exit_code == 0
    assert "Promoted" in promoted.output
    assert promotions.exit_code == 0
    assert "test-0.2.0" in promotions.output


def test_schema_cli_blocks_high_risk_report(tmp_path: Path) -> None:
    store, proposal = _ready_store(tmp_path)
    report_path = tmp_path / "shadow_report.json"
    report_path.write_text(
        json.dumps(
            {
                "governance": {
                    "rollback_recommended": True,
                    "canary_ready": False,
                    "high_risk_policy_decision_count": 1,
                }
            }
        ),
        encoding="utf-8",
    )
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "schema",
            "promote",
            "--schema-dir",
            str(store.store_dir),
            "--proposal-id",
            proposal["proposal_id"],
            "--eval-report",
            str(report_path),
        ],
    )

    assert result.exit_code == 0
    assert "Blocked" in result.output
    assert store.get_proposal_by_id(proposal["proposal_id"])["status"] == "blocked"
