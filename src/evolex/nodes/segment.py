from __future__ import annotations

import re

from evolex.graph.state import GraphState

SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？.!?])\s+|\n+")


def segment_node(state: GraphState) -> dict:
    text = state.get("document_text", "")
    raw_segments = [segment.strip() for segment in SENTENCE_SPLIT_RE.split(text)]
    segments = [
        {
            "segment_id": f"seg-{index + 1:04d}",
            "text": segment,
        }
        for index, segment in enumerate(raw_segments)
        if segment
    ]
    return {"segments": segments}
