from pathlib import Path

from evolex.agents.deepseek_client import HeuristicExtractor
from evolex.graph.runner import run_phase1_text


def test_phase1_graph_smoke(tmp_path: Path) -> None:
    result = run_phase1_text(
        "API Gateway retries HTTP 503 responses for 2 seconds before failing over.",
        output_dir=tmp_path,
        extractor=HeuristicExtractor(),
    )

    assert result.status == "candidate"
    assert result.semantic_atom_count >= 1
    assert Path(result.candidate_output_path).exists()
    for atom in result.state["semantic_atoms"]:
        assert atom["type"].isascii()
        assert atom["text"].isascii()
        assert atom["kg_language"] == "en"
