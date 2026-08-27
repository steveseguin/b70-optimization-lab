#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path
from unittest import mock


PATH = Path(__file__).with_name("bench-openai-concurrency.py")
SPEC = importlib.util.spec_from_file_location("bench_openai_concurrency", PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FakeResponse:
    def __init__(self, events: list[dict[str, object] | str]) -> None:
        self.lines = [
            f"data: {event if isinstance(event, str) else json.dumps(event)}\n".encode()
            for event in events
        ]

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def __iter__(self):
        return iter(self.lines)


def run_with_events(events: list[dict[str, object] | str]) -> dict[str, object]:
    with mock.patch.object(MODULE.urllib.request, "urlopen", return_value=FakeResponse(events)):
        return MODULE.stream_completion(
            "http://127.0.0.1:8000",
            "model",
            "prompt",
            2,
            1,
            10,
        )


class StreamCompletionTests(unittest.TestCase):
    def test_valid_stream_requires_text_and_usage(self) -> None:
        result = run_with_events([
            {"choices": [{"text": "hello"}], "usage": None},
            {
                "choices": [],
                "usage": {
                    "prompt_tokens": 4,
                    "completion_tokens": 2,
                    "total_tokens": 6,
                },
            },
            "[DONE]",
        ])
        self.assertEqual(result["prompt_tokens"], 4)
        self.assertEqual(result["completion_tokens"], 2)
        self.assertEqual(result["chunks"], 1)

    def test_error_event_fails_closed(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "error event"):
            run_with_events([{"error": {"message": "engine unavailable"}}])

    def test_empty_done_event_fails_closed(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "prompt-token usage"):
            run_with_events(["[DONE]"])

    def test_usage_without_generated_text_fails_closed(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "generated text"):
            run_with_events([
                {
                    "choices": [],
                    "usage": {
                        "prompt_tokens": 4,
                        "completion_tokens": 2,
                        "total_tokens": 6,
                    },
                },
                "[DONE]",
            ])

    def test_partial_completion_fails_closed(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "completion-token usage"):
            run_with_events([
                {"choices": [{"text": "hello"}]},
                {
                    "choices": [],
                    "usage": {
                        "prompt_tokens": 4,
                        "completion_tokens": 1,
                        "total_tokens": 5,
                    },
                },
                "[DONE]",
            ])

    def test_inconsistent_total_fails_closed(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "total-token usage"):
            run_with_events([
                {"choices": [{"text": "hello"}]},
                {
                    "choices": [],
                    "usage": {
                        "prompt_tokens": 4,
                        "completion_tokens": 2,
                        "total_tokens": 5,
                    },
                },
                "[DONE]",
            ])


if __name__ == "__main__":
    unittest.main()
