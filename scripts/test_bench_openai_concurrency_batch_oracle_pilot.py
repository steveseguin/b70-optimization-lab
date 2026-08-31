#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock


PATH = Path(__file__).with_name("bench-openai-concurrency-batch-oracle-pilot.py")
SPEC = importlib.util.spec_from_file_location("concurrency_batch_oracle_pilot", PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class BatchOraclePilotTests(unittest.TestCase):
    def test_first_and_only_requests_are_the_concurrent_batch(self) -> None:
        calls: list[str] = []
        lock = threading.Lock()

        def fake_post_stream(**kwargs: object) -> dict[str, object]:
            prompt = str(kwargs["prompt"])
            with lock:
                calls.append(prompt)
            digest = hashlib.sha256(prompt.encode()).digest()
            token_ids = [digest[0], digest[1], digest[2]]
            return {
                "completion_tokens": 3,
                "token_ids": token_ids,
                "sha256": hashlib.sha256(bytes(token_ids)).hexdigest(),
                "tok_s_wall_full": 10.0,
                "usage": {"prompt_tokens_details": {"cached_tokens": 0}},
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "result.json"
            argv = [
                str(PATH),
                "--model", "test-model",
                "--suite", str(Path(temp_dir) / "unused.json"),
                "--concurrency", "4",
                "--max-tokens", "3",
                "--return-token-ids",
                "--out", str(output),
            ]
            with (
                mock.patch.object(
                    MODULE._BASE,
                    "load_suite",
                    return_value=(
                        {"system_prompt": "test"},
                        [
                            {"id": "prose", "prompt": "Write prose."},
                            {"id": "code", "prompt": "Write code."},
                        ],
                    ),
                ),
                mock.patch.object(MODULE._BASE, "post_stream", side_effect=fake_post_stream),
                mock.patch.object(sys, "argv", argv),
            ):
                self.assertEqual(MODULE.main(), 0)

            result = json.loads(output.read_text())
            self.assertEqual(len(calls), 4)
            self.assertEqual(len(set(calls)), 4)
            self.assertEqual(result["oracle"]["request_count"], 4)
            self.assertEqual(len(result["batches"]), 1)
            self.assertEqual(result["batches"][0]["request_count"], 4)
            self.assertTrue(result["batches"][0]["cached_tokens_all_zero"])
            self.assertEqual(
                result["config"]["oracle_source"],
                "first-and-only-same-shape-batch",
            )


if __name__ == "__main__":
    unittest.main()
