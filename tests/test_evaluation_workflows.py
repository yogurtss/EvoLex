from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from evolex.agents.deepseek_client import HeuristicTypedExtractor
from evolex.cli import app
from evolex.graph.runner import (
    replay_run,
    resume_thread,
    run_frozen_evaluation,
    run_phase3_text,
    run_shadow_evaluation,
)
from evolex.repositories.evaluation import CheckpointStore


def test_frozen_evaluation_writes_metrics_report(tmp_path: Path) -> None:
    result = run_frozen_evaluation(
        output_dir=tmp_path,
        extractor=HeuristicTypedExtractor(),
        project_root=Path.cwd(),
    )

    assert result.status == "ok"
    assert result.document_count >= 1
    assert Path(result.report_path).exists()
    assert Path(result.baseline_path).exists()
    assert result.report["totals"]["claims"] >= 1
    assert "evidence_coverage" in result.report["totals"]


def test_shadow_evaluation_is_report_only_for_publish(tmp_path: Path) -> None:
    result = run_shadow_evaluation(
        output_dir=tmp_path,
        extractor=HeuristicTypedExtractor(),
        project_root=Path.cwd(),
    )

    assert result.status == "ok"
    assert Path(result.report_path).exists()
    assert result.report["evaluation_mode"] == "shadow"
    assert result.report["governance"]["canary_ready"] in (True, False)
    assert not list((tmp_path / "eval" / "shadow_runs").glob("*.sqlite"))


def test_checkpoint_replay_records_node_sequence(tmp_path: Path) -> None:
    checkpoint_dir = tmp_path / "checkpoints"
    result = run_phase3_text(
        "API Gateway retries HTTP 503 responses for 2 seconds before failing over.",
        output_dir=tmp_path,
        extractor=HeuristicTypedExtractor(),
        checkpoint_dir=checkpoint_dir,
    )

    replay = replay_run(result.run_id, checkpoint_dir=checkpoint_dir)

    assert replay.event_count >= 1
    assert replay.events[0]["node_name"] == "ingest"
    assert replay.events[-1]["node_name"] == "registry_finalize"


def test_resume_thread_continues_from_latest_checkpoint(tmp_path: Path) -> None:
    checkpoint_dir = tmp_path / "checkpoints"
    result = run_phase3_text(
        "ICP etching at 20mTorr achieves 2.5µm/min etch rate.",
        output_dir=tmp_path,
        extractor=HeuristicTypedExtractor(),
        checkpoint_dir=checkpoint_dir,
    )
    thread_id = result.state["thread_id"]

    resumed = resume_thread(
        thread_id=thread_id,
        output_dir=tmp_path,
        checkpoint_dir=checkpoint_dir,
        extractor=HeuristicTypedExtractor(),
    )

    assert resumed.thread_id == thread_id
    assert resumed.result.run_id == result.run_id
    assert resumed.result.status in ("published", "candidate", "quarantined")


def test_checkpoint_store_latest_by_thread(tmp_path: Path) -> None:
    checkpoint_dir = tmp_path / "checkpoints"
    result = run_phase3_text(
        "API Gateway retries HTTP 503 for 2 seconds.",
        output_dir=tmp_path,
        extractor=HeuristicTypedExtractor(),
        checkpoint_dir=checkpoint_dir,
    )

    checkpoint = CheckpointStore(checkpoint_dir).latest_for_thread(result.state["thread_id"])

    assert checkpoint is not None
    assert checkpoint["run_id"] == result.run_id
    assert checkpoint["state"]["run_id"] == result.run_id


def test_eval_and_run_cli_commands(tmp_path: Path) -> None:
    runner = CliRunner()

    frozen = runner.invoke(app, ["eval", "frozen", "--output-dir", str(tmp_path)])
    shadow = runner.invoke(app, ["eval", "shadow", "--output-dir", str(tmp_path)])

    assert frozen.exit_code == 0
    assert "Frozen evaluation completed" in frozen.output
    assert shadow.exit_code == 0
    assert "Shadow evaluation completed" in shadow.output
