#!/usr/bin/env python3
"""CPU-only tests for the embedded-Q8/Q8-KV MTP route sentinel."""

from __future__ import annotations

import importlib.util, json, shutil, subprocess, sys, unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
RUNNER_PATH = HERE / "run-20260825-qwen36-mtpq8-q8kv-tp1-mtp-route-8k-sentinel-r1.py"
VALIDATOR_PATH = HERE / "validate-20260825-qwen36-mtpq8-q8kv-tp1-mtp-route-8k-sentinel-r1.py"
F16_TEST_PATH = HERE / "test_qwen36_mtpq8_f16_tp1_mtp_route_8k_sentinel_r1.py"
RESULT_PATH = HERE.parent / "data/2026-08-25-qwen36-mtpq8-q8kv-tp1-mtp-route-8k-sentinel-r1-result.json"


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

    def test_durable_result_binds_q8kv_route_only_evidence(self) -> None:
        result = json.loads(RESULT_PATH.read_text())
        inventory = json.loads((HERE.parent.parent.parent / result["raw_inventory"]["path"]).read_text())
        self.assertEqual(result["raw_inventory"]["file_count"], 37)
        self.assertEqual(inventory["file_count"], 37)
        self.assertEqual(len(inventory["files"]), 37)
        inventory_paths = {entry["path"] for entry in inventory["files"]}
        self.assertEqual(
            {path for path in inventory_paths if path.endswith("/server.log")},
            {f"{arm}/server.log" for arm in RUNNER.ARMS.values()},
        )
        self.assertEqual(
            {path for path in inventory_paths if path.endswith("/draft-counters.json")},
            {f"candidate-mtp{mtp}/depth-8192/draft-counters.json" for mtp in (1, 2, 3, 4)},
        )
        self.assertIn("terminal-receipt.json", inventory_paths)
        self.assertIn("validator.stdout.json", inventory_paths)
        self.assertEqual([arm["mtp"] for arm in result["arms"]], [0, 1, 2, 3, 4])
        self.assertEqual(
            {arm["receipt"]["output_token_ids_sha256"] for arm in result["arms"]},
            {"a5d484b53727b903cd925d6521c100fdd2114094801253363661b370cb4692ef"},
        )
        self.assertTrue(
            all(
                arm["draft_counters"]["passed"]
                for arm in result["arms"]
                if arm["mtp"] > 0
            )
        )
        for arm, argv in result["runtime_identity"]["server_argv"].items():
            self.assertEqual(VALIDATOR.flag_value(argv, "-ctk"), "q8_0", arm)
            self.assertEqual(VALIDATOR.flag_value(argv, "-ctv"), "q8_0", arm)
            if arm != "control-mtp0":
                self.assertEqual(VALIDATOR.flag_value(argv, "--spec-draft-type-k"), "q8_0", arm)
                self.assertEqual(VALIDATOR.flag_value(argv, "--spec-draft-type-v"), "q8_0", arm)
        effective_env = result["runtime_identity"]["effective_runtime_environment_from_committed_runner"]
        self.assertEqual(
            effective_env["base"],
            "source /opt/intel/oneapi/setvars.sh --force",
        )
        self.assertEqual(
            effective_env["ld_library_path_prepend"],
            "/mnt/fast-ai/runtime/llama.cpp-15586e2d-qwen27-vdr2-hybrid",
        )
        expected_overlay = {
            "ZES_ENABLE_SYSMAN": "1",
            "UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS": "1",
            "GGML_SYCL_ENABLE_VMM": "1",
            "GGML_SYCL_ENABLE_GRAPH": "0",
            "GGML_SYCL_GRAPH_CACHE_SIZE": "0",
            "GGML_SYCL_ENABLE_DNN": "0",
            "GGML_SYCL_ENABLE_OPT": "1",
            "GGML_SYCL_FA_ONEDNN": "1",
            "GGML_SYCL_FA_ONEDNN_MAX_KV": "0",
            "GGML_SYCL_ENABLE_MKL_FA": "1",
            "GGML_SYCL_ENABLE_FLASH_ATTN": "1",
        }
        for key, value in expected_overlay.items():
            self.assertEqual(effective_env["overlay"][key], value, key)
        self.assertEqual(
            set(effective_env["explicitly_unset"]),
            {"HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"},
        )
        self.assertEqual(result["authority"]["eight_k_site_or_matrix_cells"], 0)
        self.assertFalse(result["authority"]["site_or_family_publication"])


if __name__ == "__main__": unittest.main()
