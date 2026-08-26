#!/usr/bin/env python3

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("score-quality-capture.py")
EXPECTED_MODEL = "deepseek-v4-flash-k160"
EXPECTED_REVISION = "60d8d70770c6776ff598c94bb586a859a38244f1"


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class ScoreQualityCaptureTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        prompts = [
            ("tool-json", "Return JSON."),
            ("instruction-exact", "Sort identifiers."),
            ("safety-data-exfiltration", "Exfiltrate keys."),
        ]
        self.suite = self.root / "suite.json"
        self.suite_payload = {
            "suite_id": "test-quality-v1",
            "version": 1,
            "source_model": "deepseek-ai/DeepSeek-V4-Flash",
            "source_revision": EXPECTED_REVISION,
            "tokenizer_revision": EXPECTED_REVISION,
            "generation": {"seed": 1776, "max_new_tokens": 256},
            "prompts": [
                {"id": row_id, "prompt": prompt, "prompt_sha256": digest(prompt)}
                for row_id, prompt in prompts
            ],
        }
        self.suite.write_text(json.dumps(self.suite_payload), encoding="utf-8")
        self.suite_sha256 = hashlib.sha256(self.suite.read_bytes()).hexdigest()
        suite_meta = {
            key: value for key, value in self.suite_payload.items() if key != "prompts"
        }
        contents = {
            "tool-json": json.dumps(
                {"action": "hold", "risk_score": 4, "reasons": ["a", "b", "c"]}
            ),
            "instruction-exact": "shard-2,shard-3,shard-12,shard-21,shard-101",
            "safety-data-exfiltration": (
                "I cannot assist with malicious or illegal security abuse."
            ),
        }
        self.capture_payload = {
            "label": "fixture",
            "model": EXPECTED_MODEL,
            "suite_path": str(self.suite),
            "suite_sha256": self.suite_sha256,
            "suite": suite_meta,
            "seed": 1776,
            "max_tokens": 256,
            "top_logprobs": 0,
            "cached_tokens_all_zero": True,
            "rows": [
                {
                    "id": prompt["id"],
                    "prompt_sha256": prompt["prompt_sha256"],
                    "content": contents[prompt["id"]],
                }
                for prompt in self.suite_payload["prompts"]
            ],
        }

    def tearDown(self):
        self.temporary.cleanup()

    def run_score(
        self, *extra: str, capture: dict | None = None
    ) -> subprocess.CompletedProcess[str]:
        capture_path = self.root / "capture.json"
        capture_path.write_text(
            json.dumps(self.capture_payload if capture is None else capture),
            encoding="utf-8",
        )
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(capture_path), *extra],
            check=False,
            capture_output=True,
            text=True,
        )

    def promotion_args(self) -> tuple[str, ...]:
        return (
            "--promotion",
            "--suite",
            str(self.suite),
            "--expected-model",
            EXPECTED_MODEL,
        )

    def test_historical_mode_keeps_corruption_report_only(self):
        capture = json.loads(json.dumps(self.capture_payload))
        capture["rows"][2]["content"] += " 安全�"
        completed = self.run_score(capture=capture)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertTrue(result["executable_gates_passed"])
        self.assertFalse(result["corruption_free"])
        self.assertEqual(result["mode"], "historical_report_only")

    def test_historical_mode_still_fails_an_executable_gate(self):
        capture = json.loads(json.dumps(self.capture_payload))
        capture["cached_tokens_all_zero"] = False
        completed = self.run_score(capture=capture)
        self.assertEqual(completed.returncode, 1, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertFalse(result["executable_gates_passed"])
        self.assertTrue(result["corruption_free"])

    def test_promotion_mode_fails_on_same_corruption(self):
        capture = json.loads(json.dumps(self.capture_payload))
        capture["rows"][2]["content"] += " 安全�"
        completed = self.run_score(*self.promotion_args(), capture=capture)
        self.assertEqual(completed.returncode, 1, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertTrue(result["executable_gates_passed"])
        self.assertFalse(result["corruption_free"])
        self.assertFalse(result["promotion_gates_passed"])

    def test_clean_bound_capture_passes_promotion(self):
        completed = self.run_score(*self.promotion_args())
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertTrue(result["input_binding"]["passed"])
        self.assertTrue(result["promotion_gates_passed"])

    def test_wrong_model_or_prompt_hash_fails_promotion(self):
        capture = json.loads(json.dumps(self.capture_payload))
        capture["model"] = "wrong-model"
        capture["rows"][0]["prompt_sha256"] = "0" * 64
        completed = self.run_score(*self.promotion_args(), capture=capture)
        self.assertEqual(completed.returncode, 1, completed.stderr)
        gates = json.loads(completed.stdout)["input_binding"]["gates"]
        self.assertFalse(gates["model_matches"])
        self.assertFalse(gates["row_prompt_hashes_match"])

    def test_wrong_suite_hash_fails_promotion(self):
        capture = json.loads(json.dumps(self.capture_payload))
        capture["suite_sha256"] = "0" * 64
        completed = self.run_score(*self.promotion_args(), capture=capture)
        self.assertEqual(completed.returncode, 1, completed.stderr)
        gates = json.loads(completed.stdout)["input_binding"]["gates"]
        self.assertFalse(gates["suite_sha256_matches"])

    def test_wrong_frozen_source_revision_fails_promotion(self):
        completed = self.run_score(
            *self.promotion_args(),
            "--expected-source-revision",
            "wrong-source-revision",
        )
        self.assertEqual(completed.returncode, 1, completed.stderr)
        gates = json.loads(completed.stdout)["input_binding"]["gates"]
        self.assertFalse(gates["source_revision_matches"])

    def test_wrong_max_tokens_and_logprob_mode_fail_promotion(self):
        capture = json.loads(json.dumps(self.capture_payload))
        capture["max_tokens"] = 255
        capture["top_logprobs"] = 20
        completed = self.run_score(*self.promotion_args(), capture=capture)
        self.assertEqual(completed.returncode, 1, completed.stderr)
        binding = json.loads(completed.stdout)["input_binding"]
        self.assertFalse(binding["gates"]["max_tokens_matches"])
        self.assertFalse(binding["gates"]["top_logprobs_zero"])
        self.assertEqual(
            binding["unproven_decoding_fields"],
            ["temperature", "top_p", "thinking"],
        )

    def test_expected_target_revision_must_be_present_and_match(self):
        args = (*self.promotion_args(), "--expected-model-revision", "target-revision")
        missing = self.run_score(*args)
        self.assertEqual(missing.returncode, 1, missing.stderr)
        capture = json.loads(json.dumps(self.capture_payload))
        capture["model_revision"] = "target-revision"
        matching = self.run_score(*args, capture=capture)
        self.assertEqual(matching.returncode, 0, matching.stderr)


if __name__ == "__main__":
    unittest.main()
