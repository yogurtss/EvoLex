from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from evolex.cli import app
from evolex.evaluation import run_patent_benchmark


def test_patent_benchmark_measures_joint_pipeline_and_safety(tmp_path: Path) -> None:
    result = run_patent_benchmark(output_dir=tmp_path)
    report = result.report
    legacy = report["variants"]["legacy_separate"]["metrics"]
    joint = report["variants"]["joint_agent"]["metrics"]

    assert result.document_count == 8
    assert joint["relation_recall"] > legacy["relation_recall"]
    assert joint["relation_endpoint_pair_accuracy"] == 1.0
    assert joint["relation_evidence_contract_coverage"] == 1.0
    assert joint["joint_materialization_rate"] == 1.0
    assert report["canonicalization"]["duplicate_identity_reduction"] == 0.5
    assert report["evolution_safety"]["deterministic_replay_pass_rate"] == 1.0
    assert report["evolution_safety"]["rollback_probe"]["passed"] is True
    assert Path(result.json_path).exists()
    assert Path(result.markdown_path).exists()


def test_patent_benchmark_cli(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app,
        ["eval", "patent", "--output-dir", str(tmp_path)],
    )

    assert result.exit_code == 0
    assert "Patent engineering benchmark completed" in result.output
    assert "joint relation_f1: 1.0000" in result.output
