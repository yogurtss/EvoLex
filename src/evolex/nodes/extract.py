from __future__ import annotations

from evolex.agents.deepseek_client import BaseExtractor
from evolex.graph.state import GraphState


def make_extract_node(extractor: BaseExtractor):
    def extract_node(state: GraphState) -> dict:
        semantic_atoms: list[dict] = []
        llm_call_count = state.get("llm_call_count", 0)

        for segment in state.get("segments", []):
            atoms = extractor.extract(segment["text"])
            for atom in atoms:
                atom.setdefault("segment_id", segment["segment_id"])
                atom.setdefault("kg_language", "en")
                semantic_atoms.append(atom)
            if extractor.uses_llm:
                llm_call_count += 1

        return {
            "semantic_atoms": semantic_atoms,
            "llm_call_count": llm_call_count,
        }

    return extract_node
