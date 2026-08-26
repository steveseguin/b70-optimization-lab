#!/usr/bin/env python3
"""CPU-only fail-closed tests for Q8-KV exact-2K classification R2."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
RUNNER_PATH = HERE / "run-20260825-qwen36-mtpq8-q8kv-tp1-mtp01234-exact2k-classification-r2.py"
VALIDATOR_PATH = HERE / "validate-20260825-qwen36-mtpq8-q8kv-tp1-mtp01234-exact2k-classification-r2.py"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


RUNNER = load(RUNNER_PATH, "qwen36_q8kv_exact2k_classification_test_runner")
VALIDATOR = load(VALIDATOR_PATH, "qwen36_q8kv_exact2k_classification_test_validator")


class ClassificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = Path(tempfile.mkdtemp(prefix="q8kv-exact2k-classification-r2-"))
        self.root = self.temp / "root"
        self.root.mkdir()
        self.manifest = RUNNER.load_manifest()
        self.runtime = RUNNER.runtime_manifest(self.manifest)
        execution = RUNNER.R1.Execution(self.runtime)
        env = {
            "ONEAPI_DEVICE_SELECTOR": "level_zero:*", "ZE_AFFINITY_MASK": "0",
            "ZES_ENABLE_SYSMAN": "1", "UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS": "1",
            "GGML_SYCL_ENABLE_VMM": "1", "GGML_SYCL_ENABLE_GRAPH": "0",
            "GGML_SYCL_GRAPH_CACHE_SIZE": "0", "GGML_SYCL_ENABLE_DNN": "0",
            "GGML_SYCL_ENABLE_OPT": "1", "GGML_SYCL_FA_ONEDNN": "1",
            "GGML_SYCL_FA_ONEDNN_MAX_KV": "0", "GGML_SYCL_ENABLE_MKL_FA": "1",
            "GGML_SYCL_ENABLE_FLASH_ATTN": "1", "NO_PROXY": "127.0.0.1,localhost",
            "no_proxy": "127.0.0.1,localhost",
        }
        self.write(self.root / "identity.json", {
            "campaign_id": RUNNER.CAMPAIGN_ID,
            "model": {key: self.runtime["model"][key] for key in ("path", "size_bytes", "sha256", "repository", "revision")},
            "runtime": {
                **{key: self.runtime["runtime"][key] for key in ("binary", "binary_sha256", "manifest", "manifest_sha256", "source_commit")},
                "local_dsos": self.runtime["runtime"]["effective_local_shared_libraries"],
            },
            "fixture_sha256": self.runtime["fixture"]["sha256"],
            "server_argv": {arm: execution.server_argv_for_mtp(route) for arm, route in RUNNER.ARM_PLAN},
            "runtime_environment": env,
            "failed_r1_parent_hashes": {
                "terminal": self.manifest["failed_r1_parent"]["raw"]["terminal-receipt.json"],
                "identity": self.manifest["failed_r1_parent"]["raw"]["identity.json"],
            },
        })
        base = list(range(128))
        variants = {
            "control-mtp0a": base,
            "candidate-mtp1": base,
            "candidate-mtp2": base[:26] + [900] + base[27:],
            "candidate-mtp3": base[:26] + [900] + base[27:],
            "candidate-mtp4": base[:26] + [900] + base[27:],
            "control-mtp0b": base,
        }
        for arm, route in RUNNER.ARM_PLAN:
            arm_dir = self.root / arm
            arm_dir.mkdir()
            self.write(arm_dir / "models.json", {"data": [{"id": self.runtime["server_contract"]["model_alias"]}]})
            cleanup = {"forced_kill": False, "port_closed": True, "render_node_idle": True, "server_survivor": False}
            self.write(arm_dir / "arm-result.json", {"status": "completed-awaiting-classification", "error": None, "cleanup": cleanup})
            for repeat in RUNNER.REPEATS:
                directory = arm_dir / f"repeat-{repeat}"
                directory.mkdir()
                tokens = variants[arm]
                self.write(directory / "exact-depth.json", {
                    "status": "passed", "gate": {"passed": True},
                    "response": {
                        "token_ids": tokens,
                        "output_token_ids_sha256": VALIDATOR.token_ids_sha256(tokens),
                        "llama_cache_n": 0,
                    },
                })
                if route > 0:
                    self.write(directory / "draft-counters.json", {
                        "active_context_tokens": 2048, "repeat": repeat,
                        "rows_before": repeat - 1, "rows_after": repeat,
                        "new_rows": [{"accepted": 60, "generated": 70, "ratio": 0.85714}],
                    })

    def tearDown(self) -> None:
        shutil.rmtree(self.temp)

    @staticmethod
    def write(path: Path, value: object) -> None:
        path.write_text(json.dumps(value), encoding="utf-8")

    def validate(self) -> dict:
        return VALIDATOR.validate(self.root, RUNNER.MANIFEST)

    def change_tokens(self, arm: str, repeat: int, tokens: list[int]) -> None:
        path = self.root / arm / f"repeat-{repeat}/exact-depth.json"
        value = json.loads(path.read_text())
        value["response"]["token_ids"] = tokens
        value["response"]["output_token_ids_sha256"] = VALIDATOR.token_ids_sha256(tokens)
        self.write(path, value)

    def test_repeat_stable_route_divergence_is_grade_c(self) -> None:
        result = self.validate()
        self.assertEqual((result["overall_classification"], result["packet_grade"]), ("deterministic-route-divergence", "C"))
        rows = {row["arm"]: row for row in result["route_comparisons"]}
        self.assertEqual(rows["candidate-mtp1"]["classification"], "exact-repeat-stable")
        self.assertEqual(rows["candidate-mtp2"]["classification"], "deterministic-route-divergence")
        self.assertEqual(rows["candidate-mtp2"]["comparison_to_bracketing_mtp0"]["first_divergence_zero_based_index"], 26)
        self.assertEqual(result["authority"]["site_cells"], 0)

    def test_all_exact_is_bounded_grade_b(self) -> None:
        base = list(range(128))
        for arm in ("candidate-mtp2", "candidate-mtp3", "candidate-mtp4"):
            for repeat in RUNNER.REPEATS:
                self.change_tokens(arm, repeat, base)
        result = self.validate()
        self.assertEqual((result["overall_classification"], result["packet_grade"]), ("all-routes-exact-repeat-stable", "B"))
        self.assertNotEqual(result["packet_grade"], "A")
        self.assertFalse(result["authority"]["curve_expansion"])

    def test_within_arm_noise_is_grade_d(self) -> None:
        tokens = list(range(128)); tokens[50] = 12345
        self.change_tokens("candidate-mtp3", 3, tokens)
        result = self.validate()
        self.assertEqual((result["overall_classification"], result["packet_grade"]), ("within-arm-run-noise", "D"))

    def test_bracketing_control_drift_is_grade_d(self) -> None:
        tokens = list(range(128)); tokens[10] = 777
        for repeat in RUNNER.REPEATS:
            self.change_tokens("control-mtp0b", repeat, tokens)
        result = self.validate()
        self.assertEqual((result["overall_classification"], result["packet_grade"]), ("temporal-control-drift", "D"))
        self.assertFalse(result["controls"]["temporally_equal"])

    def test_bad_counter_is_invalid_evidence(self) -> None:
        path = self.root / "candidate-mtp2/repeat-2/draft-counters.json"
        value = json.loads(path.read_text()); value["new_rows"][0]["accepted"] = 71; self.write(path, value)
        result = self.validate()
        self.assertEqual((result["overall_classification"], result["packet_grade"]), ("invalid-evidence", "D"))

    def test_prior_r1_hash_is_not_forced_oracle(self) -> None:
        result = self.validate()
        self.assertFalse(result["arms"][0]["matches_failed_r1_prior_observation"])
        self.assertTrue(result["arms"][0]["prior_observation_is_not_an_acceptance_gate"])

    def test_check_is_inert_and_bracketed(self) -> None:
        result = subprocess.run([sys.executable, "-B", str(RUNNER_PATH), "--check"], check=True, text=True, capture_output=True)
        plan = json.loads(result.stdout)
        self.assertEqual((plan["gpu_actions"], plan["network_requests"], plan["output_writes"]), (0, 0, 0))
        self.assertEqual((plan["fresh_server_lifetimes"], plan["total_requests"]), (6, 18))
        self.assertEqual(plan["arms"][0::5], ["control-mtp0a", "control-mtp0b"])

    def test_ldd_parser_accepts_leading_tabs(self) -> None:
        runtime = {
            "binary": "/tmp/runtime/llama-server",
            "effective_local_shared_libraries": [
                {"soname": "libllama-server-impl.so", "path": "/tmp/runtime/libllama-server-impl.so"},
                {"soname": "libggml.so", "path": "/tmp/runtime/libggml.so"},
            ],
        }
        ldd = "\tlibllama-server-impl.so => /tmp/runtime/libllama-server-impl.so (0x1)\n    libggml.so => /tmp/runtime/libggml.so (0x2)\n"
        self.assertEqual(RUNNER.verify_ldd_closure(ldd, runtime), runtime["effective_local_shared_libraries"])


if __name__ == "__main__":
    unittest.main()
