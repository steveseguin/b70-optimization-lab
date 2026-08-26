#!/usr/bin/env python3
"""CPU-only tests for the combined MTP1/2/4 exact-depth quality packet."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest


HERE = Path(__file__).resolve().parent
RUNNER_PATH = HERE / "run-20260825-qwen36-mtpq8-f16-tp1-mtp124-exact-depth-quality-r1.py"
VALIDATOR_PATH = HERE / "validate-20260825-qwen36-mtpq8-f16-tp1-mtp124-exact-depth-quality-r1.py"
R3_TEST_PATH = HERE / "test_qwen36_mtpq8_f16_tp1_mtp3_exact_depth_r3.py"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None: raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module; spec.loader.exec_module(module); return module


RUNNER = load(RUNNER_PATH, "qwen36_mtp124_test_runner")
VALIDATOR = load(VALIDATOR_PATH, "qwen36_mtp124_test_validator")
R3_TEST = load(R3_TEST_PATH, "qwen36_mtp3_r3_fixture_for_mtp124")


class MTP124ExpansionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = R3_TEST.MTP3R3Tests(); self.fixture.setUp(); self.root = self.fixture.root
        self.overlay = RUNNER.load_overlay(); self.manifest = RUNNER.merged_manifest(self.overlay)
        source = self.root / "candidate-mtp3"
        for mtp in (1, 2, 4): shutil.copytree(source, self.root / f"candidate-mtp{mtp}")
        shutil.rmtree(source)
        for mtp in RUNNER.ROUTES:
            arm = RUNNER.ARMS[mtp]; arm_root = self.root / arm
            models = json.loads((arm_root / "models.json").read_text()); models["data"][0]["id"] = self.manifest["server_contract"]["model_alias"]
            (arm_root / "models.json").write_text(json.dumps(models))
            for depth in RUNNER.DEPTHS:
                path = arm_root / f"depth-{depth}/exact-depth.json"; value = json.loads(path.read_text())
                value["run_identity"]["model"] = self.manifest["server_contract"]["model_alias"]
                value["response"]["output_token_ids_sha256"] = self.overlay["sealed_target_output_hashes"][str(depth)]
                path.write_text(json.dumps(value))
            (arm_root / "arm-result.json").write_text(json.dumps({"status": "completed-awaiting-validation", "error": None, "cleanup": VALIDATOR.EXPECTED_CLEANUP}))
        identity_path = self.root / "identity.json"; identity = json.loads(identity_path.read_text())
        identity["campaign_id"] = RUNNER.CAMPAIGN_ID
        identity["fixture_sha256"] = self.manifest["fixture"]["sha256"]
        identity["parent_hashes"] = {"mtp3_r3_result": self.overlay["parents"]["sealed_mtp3_r3_result"]["sha256"], "route_r2_terminal": self.overlay["parents"]["route_screen_r2"]["raw_terminal_sha256"]}
        execution = RUNNER.Execution(self.manifest)
        identity["server_argv"] = {RUNNER.ARMS[mtp]: execution.server_argv_for_mtp(mtp) for mtp in RUNNER.ROUTES}
        identity_path.write_text(json.dumps(identity))

    def tearDown(self) -> None: self.fixture.tearDown()

    def validate(self): return VALIDATOR.validate(self.root, RUNNER.MANIFEST)

    def test_all_three_routes_have_seven_quality_complete_cells(self) -> None:
        result = self.validate(); self.assertTrue(result["screen_gate"]["passed"])
        self.assertEqual(result["authority"]["candidate_routes_with_seven_quality-complete_cells_if_reviewed"], [1, 2, 4])
        self.assertEqual(result["authority"]["family_cells_if_reviewed"], {"1": 7, "2": 7, "4": 7})
        self.assertFalse(result["authority"]["site_publication"])

    def test_candidate_quality_failure_is_route_local(self) -> None:
        path = self.root / "candidate-mtp2/quality.json"; value = json.loads(path.read_text()); value["pass_all"] = False; path.write_text(json.dumps(value))
        result = self.validate(); self.assertTrue(result["screen_gate"]["passed"])
        self.assertEqual(result["authority"]["candidate_routes_with_seven_quality-complete_cells_if_reviewed"], [1, 4])

    def test_candidate_parity_failure_is_route_local(self) -> None:
        path = self.root / "candidate-mtp4/depth-16384/exact-depth.json"; value = json.loads(path.read_text()); value["response"]["output_token_ids_sha256"] = "f" * 64; path.write_text(json.dumps(value))
        result = self.validate(); self.assertTrue(result["screen_gate"]["passed"])
        self.assertEqual(result["authority"]["candidate_routes_with_seven_quality-complete_cells_if_reviewed"], [1, 2])

    def test_control_failure_invalidates_all(self) -> None:
        path = self.root / "control-mtp0/depth-4096/exact-depth.json"; value = json.loads(path.read_text()); value["response"]["output_token_ids_sha256"] = "e" * 64; path.write_text(json.dumps(value))
        result = self.validate(); self.assertFalse(result["screen_gate"]["passed"])
        self.assertEqual(result["authority"]["candidate_routes_with_seven_quality-complete_cells_if_reviewed"], [])

    def test_x0_and_route_argv_are_frozen(self) -> None:
        result = self.validate(); self.assertEqual(result["context_axis_disclosure"]["x0_physical_prompt_tokens"], 1)
        identity = json.loads((self.root / "identity.json").read_text())
        for mtp in (1, 2, 4): self.assertEqual(VALIDATOR.flag_value(identity["server_argv"][f"candidate-mtp{mtp}"], "--spec-draft-n-max"), str(mtp))

    def test_check_is_inert(self) -> None:
        result = subprocess.run([sys.executable, "-B", str(RUNNER_PATH), "--check"], check=True, text=True, capture_output=True)
        plan = json.loads(result.stdout); self.assertEqual((plan["gpu_actions"], plan["network_requests"], plan["output_writes"]), (0, 0, 0)); self.assertEqual(plan["candidate_quality_batteries"], 3)


if __name__ == "__main__": unittest.main()
