from __future__ import annotations

import re

from evolex.graph.state import GraphState

SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[。！？])|(?<=[.!?])\s+|\n+")
WINDOW_SENTENCE_COUNT = 3
WINDOW_SENTENCE_STRIDE = 2


def segment_node(state: GraphState) -> dict:
    text = state.get("document_text", "")
    sentences = _sentence_spans(text)
    windows = _overlapping_windows(sentences)
    segments = []
    for index, window in enumerate(windows, start=1):
        first = window[0]
        last = window[-1]
        source_start = int(first[0])
        source_end = int(last[1])
        segments.append(
            {
                "segment_id": f"seg-{index:04d}",
                "text": text[source_start:source_end],
                "source_start": source_start,
                "source_end": source_end,
                "sentence_start_index": int(first[2]),
                "sentence_end_index": int(last[2]),
                "window_sentence_count": len(window),
            }
        )
    return {"segments": segments}


def _sentence_spans(text: str) -> list[tuple[int, int, int]]:
    """Return non-empty sentence spans without losing document offsets."""
    spans: list[tuple[int, int, int]] = []
    cursor = 0
    for boundary in SENTENCE_BOUNDARY_RE.finditer(text):
        _append_trimmed_span(spans, text, cursor, boundary.start())
        cursor = boundary.end()
    _append_trimmed_span(spans, text, cursor, len(text))
    return spans


def _append_trimmed_span(
    spans: list[tuple[int, int, int]],
    text: str,
    start: int,
    end: int,
) -> None:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    if start < end:
        spans.append((start, end, len(spans)))


def _overlapping_windows(
    sentences: list[tuple[int, int, int]],
) -> list[list[tuple[int, int, int]]]:
    """Build short overlapping contexts so adjacent-sentence facts stay visible."""
    windows: list[list[tuple[int, int, int]]] = []
    covered_until = 0
    for start in range(0, len(sentences), WINDOW_SENTENCE_STRIDE):
        window = sentences[start:start + WINDOW_SENTENCE_COUNT]
        if not window:
            continue
        end = start + len(window)
        if windows and end <= covered_until:
            continue
        windows.append(window)
        covered_until = end
    return windows
