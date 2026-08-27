import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).parents[1] / "bench-openai-long-context-suite.py"
SPEC = importlib.util.spec_from_file_location("bench_openai_long_context_suite", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FakeResponse:
    def __init__(self, events):
        self.lines = [f"data: {json.dumps(event)}\n".encode() for event in events]
        self.lines.append(b"data: [DONE]\n")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def __iter__(self):
        return iter(self.lines)


class StreamTokenIdentityTests(unittest.TestCase):
    def test_preserves_complete_stream_token_ids_and_digest(self) -> None:
        events = [
            {"choices": [{"token_ids": [7, 8], "delta": {"content": "ok"}}]},
            {"choices": [{"token_ids": [9], "delta": {"content": "!"}}]},
            {"usage": {"prompt_tokens": 12, "completion_tokens": 3,
                       "prompt_tokens_details": {"cached_tokens": 0}}, "choices": []},
        ]
        with patch.object(MODULE.urllib.request, "urlopen", return_value=FakeResponse(events)):
            row = MODULE.stream_chat(
                "http://127.0.0.1:1", "model", "prompt", 3, 1, 42, {}, True
            )
        self.assertEqual(row["token_ids"], [7, 8, 9])
        self.assertTrue(row["token_ids_complete"])
        self.assertEqual(
            row["token_ids_sha256"],
            "a41ad919bdd6044484ca97585e715e69b10493c6d5c044d08d761bffcfc835dd",
        )

    def test_marks_partial_stream_token_ids_incomplete(self) -> None:
        events = [
            {"choices": [{"token_ids": [7], "delta": {"content": "ok"}}]},
            {"usage": {"prompt_tokens": 12, "completion_tokens": 2}, "choices": []},
        ]
        with patch.object(MODULE.urllib.request, "urlopen", return_value=FakeResponse(events)):
            row = MODULE.stream_chat(
                "http://127.0.0.1:1", "model", "prompt", 2, 1, 42, {}, True
            )
        self.assertFalse(row["token_ids_complete"])


if __name__ == "__main__":
    unittest.main()
