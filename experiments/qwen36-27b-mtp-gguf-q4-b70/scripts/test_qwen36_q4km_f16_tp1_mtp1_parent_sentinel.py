from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
VALIDATOR_PATH = HERE / "validate-20260825-qwen36-q4km-f16-tp1-mtp1-parent-sentinel-r1.py"
RUNNER_PATH = HERE / "run-20260825-qwen36-q4km-f16-tp1-mtp1-parent-sentinel-r1.sh"
MANIFEST_PATH = REPO / "experiments/qwen36-27b-mtp-gguf-q4-b70/data/2026-08-25-qwen36-q4km-f16-tp1-mtp1-parent-sentinel-prereg.json"

SPEC = importlib.util.spec_from_file_location("qwen36_mtp1_parent_validator", VALIDATOR_PATH)
assert SPEC is not None and SPEC.loader is not None
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


def receipt(output_hash: str) -> dict:
    return {
        "schema": "openai-token-depth-benchmark-v1",
        "status": "passed",
        "run_identity": {
            "model": "qwen36-q4km-f16-tp1",
            "depth": 8192,
            "active_context_tokens": 8192,
            "configured_context_capacity": 12288,
            "case_id": "depth-8192",
            "max_tokens": 128,
            "metric_events": 100,
            "metric_intervals": 99,
        },
        "fixture": {
            "fixture_sha256": "85b1050c88b4c1e6cb9c4ce7f1580284cd2aa68243dad0d0dff16460decbe5ac",
            "prompt_token_ids_sha256": "6baa17bea14f0ecad7e4edf54a05256eafaef1d447a447569fd303371c671741",
        },
        "gate": {"passed": True},
        "metric_window": {
            "timestamped_events": 100,
            "inter_token_intervals": 99,
            "conventional_99_interval_tok_s": 30.0,
        },
        "response": {"output_token_ids_sha256": output_hash},
    }


def usage_row() -> dict:
    return {"usage": {"prompt_tokens_details": {"cached_tokens": 0}}}


class ParentSentinelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for arm in ("control-mtp0", "candidate-mtp1"):
            (self.root / arm).mkdir()
        output_hash = "1" * 64
        for arm in ("control-mtp0", "candidate-mtp1"):
            (self.root / arm / "exact-depth.json").write_text(
                json.dumps(receipt(output_hash)), encoding="utf-8"
            )
        (self.root / "control-mtp0/server.log").write_text("target only\n")
        (self.root / "candidate-mtp1/server.log").write_text(
            "draft acceptance = 0.75000 ( 96 accepted / 127 generated)\n"
        )
        quality = {
            "pass_all": True,
            "exact_cases": [usage_row() for _ in range(4)],
            "repeat_case": {"repeats": 2, "runs": [usage_row(), usage_row()]},
            "long_context_case": {"pass": True, **usage_row()},
        }
        (self.root / "candidate-mtp1/quality.json").write_text(
            json.dumps(quality), encoding="utf-8"
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_valid_packet_expands_without_speed_floor(self) -> None:
        result = VALIDATOR.validate(self.root, MANIFEST_PATH)
        self.assertTrue(result["gate"]["passed"])
        self.assertEqual(result["status"], "passed-expand-mtp1-depth-curve")
        self.assertIsNone(result["speed_floor"])

    def test_target_output_mismatch_fails_closed(self) -> None:
        path = self.root / "candidate-mtp1/exact-depth.json"
        path.write_text(json.dumps(receipt("2" * 64)), encoding="utf-8")
        result = VALIDATOR.validate(self.root, MANIFEST_PATH)
        self.assertFalse(result["gate"]["passed"])
        self.assertFalse(result["gate"]["checks"]["candidate_target_output_parity"])

    def test_packet_has_all_locks_and_no_site_authority(self) -> None:
        manifest = json.loads(MANIFEST_PATH.read_text())
        self.assertEqual(len(manifest["lifecycle"]["required_locks"]), 4)
        self.assertFalse(
            manifest["frozen_interpretation"]["site_or_family_edit_authorized"]
        )
        runner = RUNNER_PATH.read_text()
        for lock in manifest["lifecycle"]["required_locks"]:
            self.assertIn(lock, runner)
        self.assertIn("set -o noclobber", runner)
        self.assertIn("--spec-draft-n-max 1", runner)
        self.assertIn('help_text="$($SERVER --help 2>&1)"', runner)
        self.assertNotIn("$SERVER --help 2>&1 | grep", runner)
        self.assertIn('"llama-batched-bench"', runner)
        self.assertIn('"vllm serve"', runner)
        self.assertIn('"VLLM::EngineCore"', runner)
        self.assertGreaterEqual(runner.count("require_idle"), 4)


if __name__ == "__main__":
    unittest.main()
