#!/usr/bin/env python3
"""CPU-only tests for the full Q8-KV MTP1/2/3/4 expansion."""

import importlib.util, json, shutil, subprocess, sys, unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNNER_PATH = HERE / "run-20260825-qwen36-mtpq8-q8kv-tp1-mtp1234-exact-depth-quality-r1.py"
VALIDATOR_PATH = HERE / "validate-20260825-qwen36-mtpq8-q8kv-tp1-mtp1234-exact-depth-quality-r1.py"
F16_TEST_PATH = HERE / "test_qwen36_mtpq8_f16_tp1_mtp124_exact_depth_quality_r1.py"

def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path); module = importlib.util.module_from_spec(spec); sys.modules[name] = module; spec.loader.exec_module(module); return module

RUNNER = load(RUNNER_PATH, "qwen36_q8kv_full_test_runner"); VALIDATOR = load(VALIDATOR_PATH, "qwen36_q8kv_full_test_validator"); F16_TEST = load(F16_TEST_PATH, "qwen36_f16_full_fixture_for_q8kv")

class Q8KVFullExpansionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = F16_TEST.MTP124ExpansionTests(); self.fixture.setUp(); self.root = self.fixture.root
        shutil.copytree(self.root / "candidate-mtp2", self.root / "candidate-mtp3")
        self.overlay = RUNNER.load_overlay(); self.manifest = RUNNER.merged_manifest(self.overlay)
        identity_path = self.root / "identity.json"; identity = json.loads(identity_path.read_text()); identity["campaign_id"] = RUNNER.CAMPAIGN_ID
        identity["parent_hashes"] = {"mtp3_r3_result": self.overlay["parents"]["sealed_mtp3_r3_result"]["sha256"], "route_r2_terminal": self.overlay["parents"]["route_screen_r2"]["raw_terminal_sha256"]}
        execution = RUNNER.Execution(self.manifest); identity["server_argv"] = {RUNNER.ARMS[m]: execution.server_argv_for_mtp(m) for m in RUNNER.ROUTES}; identity_path.write_text(json.dumps(identity))
        for mtp in RUNNER.ROUTES:
            arm = self.root / RUNNER.ARMS[mtp]; models = json.loads((arm / "models.json").read_text()); models["data"][0]["id"] = self.manifest["server_contract"]["model_alias"]; (arm / "models.json").write_text(json.dumps(models))
            for depth in RUNNER.DEPTHS:
                path = arm / f"depth-{depth}/exact-depth.json"; value = json.loads(path.read_text()); value["run_identity"]["model"] = self.manifest["server_contract"]["model_alias"]; path.write_text(json.dumps(value))
    def tearDown(self): self.fixture.tearDown()
    def validate(self): return VALIDATOR.validate(self.root, RUNNER.OVERLAY)

    def test_all_routes_quality_complete(self):
        result = self.validate(); self.assertTrue(result["screen_gate"]["passed"]); self.assertEqual(result["authority"]["candidate_routes_with_seven_quality-complete_cells_if_reviewed"], [1, 2, 3, 4]); self.assertEqual(result["authority"]["family_cells_if_reviewed"], {"1": 7, "2": 7, "3": 7, "4": 7})
    def test_q8_kv_argv_all_arms(self):
        identity = json.loads((self.root / "identity.json").read_text())
        for mtp in RUNNER.ROUTES:
            argv = identity["server_argv"][RUNNER.ARMS[mtp]]; self.assertEqual(VALIDATOR.BASE.flag_value(argv, "-ctk"), "q8_0"); self.assertEqual(VALIDATOR.BASE.flag_value(argv, "-ctv"), "q8_0")
            if mtp:
                self.assertEqual(VALIDATOR.BASE.flag_value(argv, "--spec-draft-type-k"), "q8_0")
                self.assertEqual(VALIDATOR.BASE.flag_value(argv, "--spec-draft-type-v"), "q8_0")
    def test_draft_v_selector_drift_fails_shared_frame(self):
        path = self.root / "identity.json"; identity = json.loads(path.read_text()); argv = identity["server_argv"]["candidate-mtp2"]; argv[argv.index("--spec-draft-type-v") + 1] = "f16"; path.write_text(json.dumps(identity))
        result = self.validate(); self.assertFalse(result["screen_gate"]["passed"]); self.assertEqual(result["authority"]["candidate_routes_with_seven_quality-complete_cells_if_reviewed"], [])
    def test_candidate_quality_failure_route_local(self):
        path = self.root / "candidate-mtp3/quality.json"; value = json.loads(path.read_text()); value["pass_all"] = False; path.write_text(json.dumps(value)); result = self.validate(); self.assertTrue(result["screen_gate"]["passed"]); self.assertEqual(result["authority"]["candidate_routes_with_seven_quality-complete_cells_if_reviewed"], [1, 2, 4])
    def test_control_failure_global(self):
        path = self.root / "control-mtp0/depth-24576/exact-depth.json"; value = json.loads(path.read_text()); value["response"]["output_token_ids_sha256"] = "0" * 64; path.write_text(json.dumps(value)); result = self.validate(); self.assertFalse(result["screen_gate"]["passed"]); self.assertEqual(result["authority"]["candidate_routes_with_seven_quality-complete_cells_if_reviewed"], [])
    def test_check_inert(self):
        result = subprocess.run([sys.executable, "-B", str(RUNNER_PATH), "--check"], check=True, text=True, capture_output=True); plan = json.loads(result.stdout); self.assertEqual((plan["gpu_actions"], plan["network_requests"], plan["output_writes"]), (0, 0, 0)); self.assertEqual((plan["fresh_server_lifetimes"], plan["candidate_quality_batteries"]), (5, 4))
    def test_loader_resolution_is_whitespace_tolerant(self):
        self.assertIn(r'match = re.search(rf"^\s*', RUNNER.source)
        self.assertNotIn(r'match = re.search(rf"^{re.escape', RUNNER.source)
    def test_authority_stays_false(self):
        frozen = self.overlay["frozen_interpretation"]
        self.assertIs(frozen["site_publication_authorized"], False)
        self.assertIs(frozen["headline_or_protected_replacement_authorized"], False)
        self.assertIs(frozen["f16_or_protected_speed_replacement_authorized"], False)

if __name__ == "__main__": unittest.main()
