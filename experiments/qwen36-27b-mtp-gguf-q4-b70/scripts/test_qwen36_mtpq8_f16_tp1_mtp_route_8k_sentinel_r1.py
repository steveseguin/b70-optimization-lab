#!/usr/bin/env python3
"""CPU-only tests for the embedded-Q8/F16 MTP route 8K sentinel."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
RUNNER_PATH = HERE / "run-20260825-qwen36-mtpq8-f16-tp1-mtp-route-8k-sentinel-r1.py"
VALIDATOR_PATH = HERE / "validate-20260825-qwen36-mtpq8-f16-tp1-mtp-route-8k-sentinel-r1.py"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


RUNNER = load(RUNNER_PATH, "qwen36_mtpq8_route_8k_test_runner")
VALIDATOR = load(VALIDATOR_PATH, "qwen36_mtpq8_route_8k_test_validator")


class Route8KSentinelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.overlay = RUNNER.load_overlay()
        self.manifest = RUNNER.merged_manifest(self.overlay)
        self.hash = self.overlay["parent_r3"]["required_8k_output_token_ids_sha256"]
        execution = RUNNER.Execution(self.manifest)
        argv = {RUNNER.ARMS[mtp]: execution.server_argv_for_mtp(mtp) for mtp in RUNNER.ROUTES}
        self.write(self.root / "identity.json", {
            "campaign_id": RUNNER.CAMPAIGN_ID,
            "git_head": "a" * 40,
            "origin_main": "a" * 40,
            "parent_r3_terminal_receipt_sha256": self.overlay["parent_r3"]["terminal_receipt_sha256"],
            "fixture_sha256": self.manifest["fixture"]["sha256"],
            "fixture_8k_prompt_token_ids_sha256": self.manifest["fixture"]["prompt_token_ids_sha256"][3],
            "model": {"sha256": self.manifest["model"]["sha256"]},
            "runtime": {
                "binary_sha256": self.manifest["runtime"]["binary_sha256"],
                "manifest_sha256": self.manifest["runtime"]["manifest_sha256"],
                "local_dsos": self.manifest["runtime"]["effective_local_shared_libraries"],
            },
            "server_argv": argv,
            "runtime_environment": {"GGML_SYCL_ENABLE_GRAPH": "0", "GGML_SYCL_GRAPH_CACHE_SIZE": "0"},
        })
        for mtp in RUNNER.ROUTES:
            self.write_pass_arm(mtp)

    def tearDown(self) -> None:
        self.temp.cleanup()

    @staticmethod
    def write(path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")

    def receipt(self, output_hash: str) -> dict:
        return {
            "schema": VALIDATOR.RECEIPT_SCHEMA,
            "status": "passed",
            "gate": {"passed": True},
            "run_identity": {
                "model": self.manifest["server_contract"]["model_alias"],
                "depth": 8192,
                "active_context_tokens": 8192,
                "configured_context_capacity": self.manifest["server_contract"]["context_capacity"],
                "case_id": "depth-8192",
                "max_tokens": 128,
                "metric_events": 100,
                "metric_intervals": 99,
            },
            "fixture": {
                "fixture_sha256": self.manifest["fixture"]["sha256"],
                "prompt_token_ids_sha256": self.manifest["fixture"]["prompt_token_ids_sha256"][3],
            },
            "metric_window": {
                "timestamped_events": 100,
                "inter_token_intervals": 99,
                "conventional_99_interval_tok_s": 30.0,
            },
            "response": {
                "usage": {
                    "prompt_tokens_details": {"cached_tokens": 0},
                    "completion_tokens": 128,
                },
                "output_token_ids_sha256": output_hash,
            },
        }

    def write_pass_arm(self, mtp: int) -> None:
        arm = RUNNER.ARMS[mtp]
        arm_root = self.root / arm
        arm_root.mkdir(parents=True, exist_ok=True)
        (arm_root / "server.log").write_text("", encoding="utf-8")
        self.write(arm_root / "models.json", {"data": [{"id": self.manifest["server_contract"]["model_alias"]}]})
        self.write(arm_root / "cleanup.json", VALIDATOR.EXPECTED_CLEANUP)
        self.write(arm_root / "arm-result.json", {
            "status": "completed-awaiting-validation",
            "error": None,
            "cleanup": VALIDATOR.EXPECTED_CLEANUP,
        })
        self.write(arm_root / "depth-8192/exact-depth.json", self.receipt(self.hash))
        if mtp > 0:
            self.write(arm_root / "depth-8192/draft-counters.json", {
                "depth": 8192,
                "rows_before": 0,
                "rows_after": 1,
                "new_rows": [{"generated": 100, "accepted": 75, "ratio": 0.75}],
            })

    def validate(self) -> dict:
        return VALIDATOR.validate(self.root, RUNNER.MANIFEST)

    def test_manifest_and_argv_are_exact_and_inert(self) -> None:
        RUNNER.validate_overlay(self.overlay)
        identity = json.loads((self.root / "identity.json").read_text())
        for mtp in RUNNER.ROUTES:
            argv = identity["server_argv"][RUNNER.ARMS[mtp]]
            self.assertEqual(VALIDATOR.flag_value(argv, "-ctk"), "f16")
            self.assertEqual(VALIDATOR.flag_value(argv, "-ctv"), "f16")
            if mtp == 0:
                self.assertEqual(VALIDATOR.flag_value(argv, "--spec-type"), "none")
            else:
                self.assertEqual(VALIDATOR.flag_value(argv, "--spec-type"), "draft-mtp")
                self.assertEqual(VALIDATOR.flag_value(argv, "--spec-draft-n-max"), str(mtp))
        self.assertTrue(self.overlay["lifecycle"]["default_is_inert"])
        self.assertFalse(self.overlay["frozen_interpretation"]["site_publication_authorized"])

    def test_all_candidates_can_be_routed_to_separate_curves(self) -> None:
        result = self.validate()
        self.assertTrue(result["screen_gate"]["passed"])
        self.assertEqual(result["authority"]["candidate_routes_eligible_for_separately_preregistered_curve"], [1, 2, 4])
        self.assertFalse(result["authority"]["headline_or_protected_replacement"])

    def test_one_candidate_parity_failure_does_not_erase_other_routes(self) -> None:
        path = self.root / "candidate-mtp2/depth-8192/exact-depth.json"
        self.write(path, self.receipt("b" * 64))
        result = self.validate()
        self.assertTrue(result["screen_gate"]["passed"])
        self.assertEqual(result["authority"]["candidate_routes_eligible_for_separately_preregistered_curve"], [1, 4])
        self.assertFalse(next(row for row in result["arms"] if row["mtp"] == 2)["passed"])

    def test_candidate_counter_failure_is_route_local(self) -> None:
        path = self.root / "candidate-mtp4/depth-8192/draft-counters.json"
        self.write(path, {"depth": 8192, "rows_before": 0, "rows_after": 1,
                          "new_rows": [{"generated": 10, "accepted": 11, "ratio": 1.1}]})
        result = self.validate()
        self.assertTrue(result["screen_gate"]["passed"])
        self.assertEqual(result["authority"]["candidate_routes_eligible_for_separately_preregistered_curve"], [1, 2])

    def test_clean_candidate_boot_failure_is_preserved_and_route_local(self) -> None:
        arm = self.root / "candidate-mtp1"
        (arm / "models.json").unlink()
        (arm / "depth-8192/exact-depth.json").unlink()
        (arm / "depth-8192/draft-counters.json").unlink()
        self.write(arm / "arm-result.json", {
            "status": "failed-preserve",
            "error": "GateError: server exited before readiness",
            "cleanup": VALIDATOR.EXPECTED_CLEANUP,
        })
        result = self.validate()
        self.assertTrue(result["screen_gate"]["passed"])
        self.assertEqual(result["authority"]["candidate_routes_eligible_for_separately_preregistered_curve"], [2, 4])
        self.assertEqual(next(row for row in result["arms"] if row["mtp"] == 1)["error"],
                         "GateError: server exited before readiness")

    def test_mtp3_positive_control_failure_invalidates_screen(self) -> None:
        path = self.root / "positive-control-mtp3/depth-8192/exact-depth.json"
        self.write(path, self.receipt("c" * 64))
        result = self.validate()
        self.assertFalse(result["screen_gate"]["passed"])
        self.assertEqual(result["authority"]["candidate_routes_eligible_for_separately_preregistered_curve"], [])


if __name__ == "__main__":
    unittest.main()
