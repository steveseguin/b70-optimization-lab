#!/usr/bin/env python3
"""Focused tests for the Flash-Next repeat protocol."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent


def load(name: str, filename: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


quality = load("qwen38_quality", "qwen38-text-quality-suite.py")
probe = load("qwen38_repeat_probe", "qwen38-repeat-sensitivity-probe.py")


class RepeatProtocolTests(unittest.TestCase):
    def test_logic_case_uses_semantic_casefold_match(self):
        logic = next(
            case for case in quality.make_exact_cases() if case["name"] == "logic"
        )
        self.assertEqual(logic["expected"], "yes")
        self.assertEqual(logic["match"], "casefold")
        self.assertTrue(quality.exact_case_pass(logic, {"normalized": "Yes"}))
        self.assertTrue(quality.exact_case_pass(logic, {"normalized": "YES"}))
        self.assertFalse(quality.exact_case_pass(logic, {"normalized": "No"}))

    def _run_quality_repeats(self, contents: list[str]) -> dict[str, Any]:
        iterator = iter(contents)

        def fake_completion(*args: Any, **kwargs: Any) -> dict[str, Any]:
            content = next(iterator)
            return {
                "request_id": kwargs.get("request_id"),
                "content": content,
                "normalized": content,
                "sha256": quality.sha256_text(content),
                "elapsed_s": 0.1,
                "usage": {"prompt_tokens_details": {"cached_tokens": 0}},
            }

        original = quality.chat_completion
        quality.chat_completion = fake_completion
        try:
            return quality.run_repeat_case(
                "http://127.0.0.1:1",
                "model",
                1,
                1,
                len(contents),
                {"enable_thinking": False},
                0,
                "test",
            )
        finally:
            quality.chat_completion = original

    def test_fixed_repeat_requires_prescribed_answer(self) -> None:
        expected = "blue, green, red, yellow"
        result = self._run_quality_repeats([expected] * 4)
        self.assertTrue(result["pass"])
        self.assertEqual(result["expected"], expected)
        self.assertEqual(result["protocol"], "fixed-set-v2")

    def test_alternate_valid_open_choice_answer_no_longer_passes(self) -> None:
        result = self._run_quality_repeats(
            ["blue, green, red, yellow", "black, blue, green, red"]
        )
        self.assertFalse(result["pass"])

    def test_probe_requests_one_token_and_named_scores(self) -> None:
        body = probe.payload("model", probe.PHASES["open_choice"], 7)
        self.assertEqual(body["max_tokens"], 1)
        self.assertEqual(body["temperature"], 0)
        self.assertTrue(body["logprobs"])
        self.assertEqual(
            body["logprob_token_ids"], [probe.BLUE_TOKEN_ID, probe.BLACK_TOKEN_ID]
        )

    def test_probe_requires_both_named_scores(self) -> None:
        both = [{"token": "blue"}, {"token": "black"}]
        only_one = [{"token": "blue"}]
        self.assertTrue(probe.required_named_scores_present(both))
        self.assertFalse(probe.required_named_scores_present(only_one))
        self.assertFalse(probe.required_named_scores_present([]))

    def test_baseline_compares_repeat_protocol_and_aggregate(self) -> None:
        current = {"exact_cases": [], "repeat_case": {
            "protocol": "fixed-set-v2",
            "unique_hashes": ["a"],
            "pass": True,
        }, "long_context_case": None}
        baseline = {"exact_cases": [], "repeat_case": {
            "protocol": "open-choice-v1",
            "unique_hashes": ["a", "b"],
            "pass": False,
        }, "long_context_case": None}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "baseline.json"
            path.write_text(json.dumps(baseline))
            comparisons = quality.compare_to_baseline(current, path)
        self.assertFalse(comparisons["repeat:protocol_same"])
        self.assertFalse(comparisons["repeat:all_hashes_same"])
        self.assertFalse(comparisons["repeat:aggregate_pass_same"])

    def test_base_url_rejects_credentials(self) -> None:
        with self.assertRaises(ValueError):
            probe.validate_base_url("http://user:secret@127.0.0.1:1")


if __name__ == "__main__":
    unittest.main()
