from __future__ import annotations

import time

import pytest

from evolex.agents.deepseek_client import LLMConfig, TypedExtractor
from evolex.nodes.extract import make_extract_node


class SlowTypedExtractor(TypedExtractor):
    uses_llm = True
    supports_relation_extraction = False

    def __init__(self, concurrency: int = 1, fail_on: str | None = None) -> None:
        self.config = LLMConfig(concurrency=concurrency)
        self.fail_on = fail_on

    def extract_typed(self, segment_text: str) -> dict[str, list[dict]]:
        if self.fail_on and self.fail_on in segment_text:
            raise RuntimeError(f"failed segment: {segment_text}")
        time.sleep(0.05)
        return {
            "mentions": [
                {
                    "text": segment_text,
                    "normalized_text": segment_text.lower(),
                    "mention_type": "entity",
                    "confidence": 0.8,
                    "evidence": segment_text,
                }
            ],
            "measurements": [],
            "conditions": [],
            "claims": [
                {
                    "claim_id": "",
                    "subject": segment_text,
                    "predicate": "related_to",
                    "object": "test",
                    "conditions": [],
                    "evidence_ids": ["ev-0001"],
                    "measurements": [],
                    "confidence": 0.8,
                    "document_id": "",
                    "document_version": 0,
                    "schema_version": "",
                    "run_id": "",
                }
            ],
            "evidence_spans": [
                {
                    "evidence_id": "ev-0001",
                    "document_id": "",
                    "segment_id": "",
                    "text": segment_text,
                    "span_start": 0,
                    "span_end": len(segment_text),
                    "run_id": "",
                }
            ],
        }


def _state() -> dict:
    return {
        "segments": [
            {"segment_id": f"seg-{idx:04d}", "text": f"Segment {idx}"}
            for idx in range(4)
        ],
        "llm_call_count": 0,
    }


def test_segment_extraction_parallelism_is_faster_and_ordered() -> None:
    serial_node = make_extract_node(SlowTypedExtractor(concurrency=1))
    parallel_node = make_extract_node(SlowTypedExtractor(concurrency=4))

    start = time.perf_counter()
    serial = serial_node(_state())
    serial_elapsed = time.perf_counter() - start

    start = time.perf_counter()
    parallel = parallel_node(_state())
    parallel_elapsed = time.perf_counter() - start

    assert parallel_elapsed < serial_elapsed * 0.75
    assert parallel["llm_call_count"] == 4
    assert [m["text"] for m in parallel["mentions"]] == [
        "Segment 0",
        "Segment 1",
        "Segment 2",
        "Segment 3",
    ]
    assert [m["text"] for m in serial["mentions"]] == [m["text"] for m in parallel["mentions"]]


def test_segment_extraction_serial_mode_preserves_current_behavior() -> None:
    result = make_extract_node(SlowTypedExtractor(concurrency=1))(_state())

    assert result["llm_call_count"] == 4
    assert [claim["subject"] for claim in result["claim_candidates"]] == [
        "Segment 0",
        "Segment 1",
        "Segment 2",
        "Segment 3",
    ]


def test_segment_extraction_failure_is_reported() -> None:
    node = make_extract_node(SlowTypedExtractor(concurrency=4, fail_on="Segment 2"))

    with pytest.raises(RuntimeError, match="failed segment"):
        node(_state())
