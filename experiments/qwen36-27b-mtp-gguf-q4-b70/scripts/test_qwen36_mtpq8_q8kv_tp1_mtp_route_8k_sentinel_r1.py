#!/usr/bin/env python3
"""CPU-only tests for the embedded-Q8/Q8-KV MTP route sentinel."""

from __future__ import annotations

import importlib.util, json, shutil, subprocess, sys, unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
RUNNER_PATH = HERE / "run-20260825-qwen36-mtpq8-q8kv-tp1-mtp-route-8k-sentinel-r1.py"
VALIDATOR_PATH = HERE / "validate-20260825-qwen36-mtpq8-q8kv-tp1-mtp-route-8k-sentinel-r1.py"
F16_TEST_PATH = HERE / "test_qwen36_mtpq8_f16_tp1_mtp_route_8k_sentinel_r1.py"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None: raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module; spec.loader.exec_module(module); return module


RUNNER = load(RUNNER_PATH, "qwen36_q8kv_route_test_runner")
VALIDATOR = load(VALIDATOR_PATH, "qwen36_q8kv_route_test_validator")
F16_TEST = load(F16_TEST_PATH, "qwen36_f16_route_fixture_for_q8kv")


class Q8KVRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = F16_TEST.Route8KSentinelTests(); self.fixture.setUp(); self.root = self.fixture.root
        shutil.move(self.root / "positive-control-mtp3", self.root / "candidate-mtp3")
        self.overlay = RUNNER.load_overlay(); self.manifest = RUNNER.merged_manifest(self.overlay)
        identity_path = self.root / "identity.json"; identity = json.loads(identity_path.read_text()); identity["campaign_id"] = RUNNER.CAMPAIGN_ID
        identity["parent_hashes"] = {"f16_terminal": self.overlay["parents"]["successful_f16_expansion"]["terminal_sha256"], "q8kv_target_result": self.overlay["parents"]["q8kv_target_only"]["result_sha256"]}
        execution = RUNNER.Execution(self.manifest); identity["server_argv"] = {RUNNER.ARMS[m]: execution.server_argv_for_mtp(m) for m in RUNNER.ROUTES}; identity_path.write_text(json.dumps(identity))
        for mtp in RUNNER.ROUTES:
            arm = self.root / RUNNER.ARMS[mtp]
            models = json.loads((arm / "models.json").read_text()); models["data"][0]["id"] = self.manifest["server_contract"]["model_alias"]; (arm / "models.json").write_text(json.dumps(models))
            receipt_path = arm / "depth-8192/exact-depth.json"; receipt = json.loads(receipt_path.read_text()); receipt["run_identity"]["model"] = self.manifest["server_contract"]["model_alias"]; receipt_path.write_text(json.dumps(receipt))

    def tearDown(self) -> None: self.fixture.tearDown()
    def validate(self): return VALIDATOR.validate(self.root, RUNNER.MANIFEST)

    def test_all_four_routes_are_curve_eligible(self) -> None:
        result = self.validate(); self.assertTrue(result["screen_gate"]["passed"]); self.assertEqual(result["authority"]["routes_eligible_for_separately_preregistered_q8kv_curve"], [1, 2, 3, 4]); self.assertFalse(result["authority"]["site_publication"])

    def test_q8_target_and_draft_argv_are_exact(self) -> None:
        identity = json.loads((self.root / "identity.json").read_text())
        for mtp in RUNNER.ROUTES:
            argv = identity["server_argv"][RUNNER.ARMS[mtp]]; self.assertEqual(VALIDATOR.flag_value(argv, "-ctk"), "q8_0"); self.assertEqual(VALIDATOR.flag_value(argv, "-ctv"), "q8_0")
            if mtp: self.assertEqual(VALIDATOR.flag_value(argv, "--spec-draft-type-k"), "q8_0"); self.assertEqual(VALIDATOR.flag_value(argv, "--spec-draft-type-v"), "q8_0")

    def test_candidate_failure_is_route_local(self) -> None:
        path = self.root / "candidate-mtp2/depth-8192/draft-counters.json"; value = json.loads(path.read_text()); value["new_rows"][0]["accepted"] = value["new_rows"][0]["generated"] + 1; path.write_text(json.dumps(value))
        result = self.validate(); self.assertTrue(result["screen_gate"]["passed"]); self.assertEqual(result["authority"]["routes_eligible_for_separately_preregistered_q8kv_curve"], [1, 3, 4])

    def test_control_failure_invalidates_all(self) -> None:
        path = self.root / "control-mtp0/depth-8192/exact-depth.json"; value = json.loads(path.read_text()); value["response"]["output_token_ids_sha256"] = "0" * 64; path.write_text(json.dumps(value))
        result = self.validate(); self.assertFalse(result["screen_gate"]["passed"]); self.assertEqual(result["authority"]["routes_eligible_for_separately_preregistered_q8kv_curve"], [])

    def test_check_is_inert(self) -> None:
        result = subprocess.run([sys.executable, "-B", str(RUNNER_PATH), "--check"], check=True, text=True, capture_output=True); plan = json.loads(result.stdout); self.assertEqual((plan["gpu_actions"], plan["network_requests"], plan["output_writes"]), (0, 0, 0)); self.assertEqual(plan["fresh_server_lifetimes"], 5)


if __name__ == "__main__": unittest.main()
