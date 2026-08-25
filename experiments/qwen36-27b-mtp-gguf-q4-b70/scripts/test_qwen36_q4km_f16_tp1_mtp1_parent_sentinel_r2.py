from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
LANE = REPO / "experiments/qwen36-27b-mtp-gguf-q4-b70"
RUNNER = HERE / "run-20260825-qwen36-q4km-f16-tp1-mtp1-parent-sentinel-r2.sh"
VALIDATOR_PATH = HERE / "validate-20260825-qwen36-q4km-f16-tp1-mtp1-parent-sentinel-r2.py"
OVERLAY_PATH = LANE / "data/2026-08-25-qwen36-q4km-f16-tp1-mtp1-parent-sentinel-r2-prereg.json"
BASE_MANIFEST_PATH = LANE / "data/2026-08-25-qwen36-q4km-f16-tp1-mtp1-parent-sentinel-prereg.json"
R1_FAILURE_PATH = LANE / "data/2026-08-25-qwen36-q4km-f16-tp1-mtp1-parent-sentinel-r1-failure.json"

SPEC = importlib.util.spec_from_file_location("qwen36_mtp1_parent_r2_validator", VALIDATOR_PATH)
assert SPEC is not None and SPEC.loader is not None
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


def receipt(output_hash: str, speed: float) -> dict:
    return {
        "schema": "openai-token-depth-benchmark-v1",
        "status": "passed",
        "created_at_utc": "2026-08-25T18:30:00+00:00",
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
            "conventional_99_interval_tok_s": speed,
        },
        "response": {"output_token_ids_sha256": output_hash},
    }


def usage_row() -> dict:
    return {"usage": {"prompt_tokens_details": {"cached_tokens": 0}}}


def quality_capability(overlay: dict) -> dict:
    quality = overlay["quality_environment"]
    return {
        "interpreter": quality["interpreter"],
        "interpreter_realpath": quality["interpreter_realpath"],
        "interpreter_sha256": quality["interpreter_sha256"],
        "sys_prefix": quality["sys_prefix"],
        "python_version": quality["python_version"],
        "pyvenv_cfg": {
            "path": quality["pyvenv_cfg"],
            "sha256": quality["pyvenv_cfg_sha256"],
        },
        "transformers": quality["transformers"],
        "tokenizers": quality["tokenizers"],
        "numpy": quality["numpy"],
        "offline_tokenizer_probe": quality["offline_tokenizer_probe"],
    }


class R2ParentSentinelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.overlay = json.loads(OVERLAY_PATH.read_text())
        base = json.loads(BASE_MANIFEST_PATH.read_text())
        for arm in ("control-mtp0", "candidate-mtp1"):
            (self.root / arm).mkdir()
            (self.root / arm / "models.json").write_text(
                json.dumps({"data": [{"id": "qwen36-q4km-f16-tp1"}]}),
                encoding="utf-8",
            )
        output_hash = "1" * 64
        (self.root / "control-mtp0/exact-depth.json").write_text(
            json.dumps(receipt(output_hash, 22.0)), encoding="utf-8"
        )
        (self.root / "candidate-mtp1/exact-depth.json").write_text(
            json.dumps(receipt(output_hash, 30.0)), encoding="utf-8"
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
        (self.root / "candidate-mtp1/quality.stderr.log").write_text("")

        identity = [
            "campaign_id=qwen36-q4km-f16-tp1-mtp1-parent-8192-20260825-r2",
            "r2_run_root=" + self.overlay["r2_lifecycle"]["output_root"],
            base["runtime"]["binary_sha256"],
            base["model"]["sha256"],
            base["fixture"]["sha256"],
        ]
        ldd_rows = []
        for row in base["runtime"]["effective_local_shared_libraries"]:
            identity.extend(
                (
                    f'dso={row["soname"]}|{row["path"]}|{row["sha256"]}',
                    f'ldd_resolution={row["soname"]}|{row["path"]}',
                )
            )
            ldd_rows.append(f'\t{row["soname"]} => {row["path"]} (0x1)')
        capability = json.dumps(
            quality_capability(self.overlay), separators=(",", ":"), sort_keys=True
        )
        identity.extend(
            (
                f"quality_environment={capability}",
                "transformed_runner_sha256="
                + self.overlay["r2_lifecycle"]["transformed_runner_sha256"],
                "ldd_begin",
                *ldd_rows,
                "ldd_end",
            )
        )
        (self.root / "identity.txt").write_text("\n".join(identity) + "\n")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_valid_fresh_packet_passes_without_speed_floor(self) -> None:
        result = VALIDATOR.validate(
            self.root, OVERLAY_PATH, enforce_output_root=False
        )
        self.assertTrue(result["gate"]["passed"])
        self.assertEqual(result["status"], "passed-expand-mtp1-depth-curve")
        self.assertFalse(result["r1_preservation"]["rows_reused"])

    def test_frozen_target_parity_still_fails_closed(self) -> None:
        path = self.root / "candidate-mtp1/exact-depth.json"
        path.write_text(json.dumps(receipt("2" * 64, 30.0)), encoding="utf-8")
        result = VALIDATOR.validate(
            self.root, OVERLAY_PATH, enforce_output_root=False
        )
        self.assertFalse(result["gate"]["passed"])
        self.assertFalse(result["gate"]["checks"]["candidate_target_output_parity"])

    def test_quality_stderr_is_required(self) -> None:
        (self.root / "candidate-mtp1/quality.stderr.log").unlink()
        result = VALIDATOR.validate(
            self.root, OVERLAY_PATH, enforce_output_root=False
        )
        self.assertFalse(result["gate"]["passed"])
        self.assertFalse(result["gate"]["checks"]["quality_stderr_artifact_captured"])

    def test_receipts_must_postdate_r1_terminal(self) -> None:
        path = self.root / "control-mtp0/exact-depth.json"
        value = json.loads(path.read_text())
        value["created_at_utc"] = "2026-08-25T17:00:00+00:00"
        path.write_text(json.dumps(value), encoding="utf-8")
        result = VALIDATOR.validate(
            self.root, OVERLAY_PATH, enforce_output_root=False
        )
        self.assertFalse(result["gate"]["passed"])
        self.assertFalse(
            result["gate"]["checks"]["fresh_receipts_postdate_r1_terminal"]
        )

    def test_r1_failure_discloses_parity_and_incomplete_quality(self) -> None:
        failure = json.loads(R1_FAILURE_PATH.read_text())
        self.assertFalse(failure["unpassed_scientific_gates"]["target_output_parity"]["passed"])
        self.assertEqual(failure["execution_stop"]["requests_served_before_stop"], 6)
        self.assertEqual(
            failure["cleanup_status"]["classification"],
            "cleanup observed, not terminal-validator certified",
        )
        self.assertFalse(failure["interpretation"]["r1_rows_may_be_reused_by_r2"])

    def test_runner_check_is_inert_and_capability_pinned(self) -> None:
        output_root = Path(self.overlay["r2_lifecycle"]["output_root"])
        self.assertFalse(output_root.exists())
        result = subprocess.run(
            ["bash", str(RUNNER), "--check"],
            text=True,
            capture_output=True,
            check=True,
        )
        plan = json.loads(result.stdout)
        self.assertTrue(plan["default_is_inert"])
        self.assertEqual(plan["exact_ack"], self.overlay["r2_lifecycle"]["exact_ack"])
        self.assertEqual(
            plan["transformed_runner_sha256"],
            self.overlay["r2_lifecycle"]["transformed_runner_sha256"],
        )
        self.assertEqual(plan["quality_environment"], quality_capability(self.overlay))
        self.assertFalse(output_root.exists())

    def test_quality_interpreter_scope_and_stderr_transform_are_exact(self) -> None:
        source = RUNNER.read_text()
        self.assertIn("isolated offline AutoTokenizer", self.overlay["quality_environment"]["required_capability"])
        self.assertIn("python3 -B \"$QUALITY_CLIENT\"", source)
        self.assertIn("\"$QUALITY_PYTHON\" -I -B \"$QUALITY_CLIENT\"", source)
        self.assertIn("quality.stderr.log", source)
        self.assertIn("local_files_only=True", source)
        self.assertIn("numpy-2.3.5.dist-info/METADATA", source)


if __name__ == "__main__":
    unittest.main()
