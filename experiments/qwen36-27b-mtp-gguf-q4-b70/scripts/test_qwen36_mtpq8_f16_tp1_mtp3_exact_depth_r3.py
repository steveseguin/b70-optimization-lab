from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest


HERE = Path(__file__).resolve().parent
R3_RUNNER_PATH = HERE / "run-20260825-qwen36-mtpq8-f16-tp1-mtp3-exact-depth-r3.py"
R3_VALIDATOR_PATH = HERE / "validate-20260825-qwen36-mtpq8-f16-tp1-mtp3-exact-depth-r3.py"
R2_RUNNER_PATH = HERE / "run-20260825-qwen36-mtpq8-f16-tp1-mtp3-exact-depth-r2.py"
R1_TEST_PATH = HERE / "test_qwen36_mtpq8_f16_tp1_mtp3_exact_depth_r1.py"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


R3 = load(R3_RUNNER_PATH, "qwen36_mtp3_r3_test_runner")
VALIDATOR = load(R3_VALIDATOR_PATH, "qwen36_mtp3_r3_test_validator")
R2_FRESH = load(R2_RUNNER_PATH, "qwen36_mtp3_r2_fresh_for_r3_test")
R1_TEST = load(R1_TEST_PATH, "qwen36_mtp3_r1_fixture_for_r3")


def special_zero_receipt(output_hash: str) -> dict:
    return {
        "schema": R3.ZERO_RECEIPT_SCHEMA,
        "status": "passed",
        "run_identity": {
            "model": "qwen36-mtpq8-f16-tp1-mtp3-depth-r1",
            "display_context_axis_tokens": 0,
            "prior_active_context_tokens": 0,
            "submitted_prompt_tokens": 1,
            "configured_context_capacity": 33024,
            "case_id": "depth-0-minimal-explicit-token-90",
            "max_tokens": 128,
            "metric_events": 100,
            "metric_intervals": 99,
        },
        "fixture": {
            "fixture_sha256": "85b1050c88b4c1e6cb9c4ce7f1580284cd2aa68243dad0d0dff16460decbe5ac",
            "original_depth_zero_prompt_token_ids_sha256": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
            "minimal_explicit_prompt_token_id": 90,
            "minimal_explicit_prompt_token_ids_sha256": R3.ZERO_TOKEN_HASH,
        },
        "gate": {"passed": True},
        "metric_window": {"timestamped_events": 100, "inter_token_intervals": 99, "conventional_99_interval_tok_s": 24.0},
        "context_semantics": {"literal_empty_prompt": False, "raw_engine_zero_token_invocation": False},
        "response": {"output_token_ids_sha256": output_hash, "usage": {"prompt_tokens": 1, "prompt_tokens_details": {"cached_tokens": 0}}},
    }


class MTP3R3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = R1_TEST.MTP3ExactDepthTests()
        self.fixture.setUp()
        self.root = self.fixture.root
        identity_path = self.root / "identity.json"
        identity = json.loads(identity_path.read_text())
        identity["campaign_id"] = R3.CAMPAIGN_ID
        identity_path.write_text(json.dumps(identity))
        output_hash = "1" * 64
        for arm in ("control-mtp0", "candidate-mtp3"):
            path = self.root / arm / "depth-0/exact-depth.json"
            path.write_text(json.dumps(special_zero_receipt(output_hash)))

    def tearDown(self) -> None:
        self.fixture.tearDown()

    def test_r2_failure_cleanup_and_no_candidate_are_preserved(self) -> None:
        failure = json.loads(R3.R2_FAILURE.read_text())
        self.assertEqual(failure["cleanup"], {
            "forced_kill": False, "port_closed": True, "render_node_idle": True,
            "server_survivor": False, "candidate_directory_present": False,
        })
        self.assertEqual(failure["actions"]["candidate_server_launches"], 0)
        self.assertEqual(failure["actions"]["matrix_cells"], 0)

    def test_zero_transport_seed_and_dual_accounting_are_frozen(self) -> None:
        merged = R3.merge_manifest(R3.load_overlay())
        zero = merged["zero_context_semantics"]
        self.assertEqual(zero["submitted_prompt_token_ids"], [90])
        self.assertEqual(zero["display_context_axis_tokens"], 0)
        self.assertEqual(zero["expected_usage_prompt_tokens"], 1)
        self.assertFalse(zero["literal_empty_prompt"])
        self.assertIn("usage.prompt_tokens=1", zero["required_site_disclosure"])

    def test_positive_depth_execution_method_is_bytecode_identical(self) -> None:
        self.assertEqual(R3.ORIGINAL_RUN_DEPTH.__code__.co_code, R2_FRESH.BASE.Execution.run_depth.__code__.co_code)
        self.assertEqual(R3.ORIGINAL_RUN_DEPTH.__code__.co_consts, R2_FRESH.BASE.Execution.run_depth.__code__.co_consts)

    def test_execution_binds_existing_r3_validator(self) -> None:
        self.assertEqual(R3.BASE.VALIDATOR, R3_VALIDATOR_PATH)
        self.assertTrue(R3.BASE.VALIDATOR.is_file())

    def test_zero_receipt_builder_requires_physical_one_logical_zero(self) -> None:
        module = R3.BASE.load_depth_client(R3.BASE.referenced_path(R3.merge_manifest(R3.load_overlay())["clients"]["exact_depth"]["path"]))
        row = {
            "usage": {"prompt_tokens": 1, "completion_tokens": 128, "total_tokens": 129, "prompt_tokens_details": {"cached_tokens": 0}},
            "token_id_offsets_s": [index * 0.01 for index in range(100)], "token_ids": list(range(128)),
            "finish_reasons": ["length"], "done_seen": True, "verbose_context_shift": False,
            "verbose_truncated": False, "verbose_stop_type": "limit", "llama_cache_n": 0,
            "returned_prompt_token_ids": [90], "text_sha256": "a" * 64,
        }
        receipt = R3.zero_receipt(module, row, R3.merge_manifest(R3.load_overlay()))
        self.assertTrue(receipt["gate"]["passed"])
        self.assertEqual(receipt["run_identity"]["prior_active_context_tokens"], 0)
        self.assertEqual(receipt["run_identity"]["submitted_prompt_tokens"], 1)
        self.assertEqual(receipt["response"]["usage"]["prompt_tokens"], 1)

    def test_r3_validator_accepts_disclosed_zero_and_exact_positive_depths(self) -> None:
        result = VALIDATOR.validate(self.root, R3.OVERLAY)
        self.assertTrue(result["gate"]["passed"])
        self.assertEqual(result["context_axis_disclosure"]["x0_usage_prompt_tokens"], 1)
        self.assertEqual(result["context_axis_disclosure"]["positive_depths_exact_and_unchanged"], [2048, 4096, 8192, 16384, 24576, 32768])

    def test_r3_validator_rejects_zero_usage_prompt(self) -> None:
        path = self.root / "candidate-mtp3/depth-0/exact-depth.json"
        value = json.loads(path.read_text())
        value["response"]["usage"]["prompt_tokens"] = 0
        path.write_text(json.dumps(value))
        with self.assertRaises(VALIDATOR.BASE.GateError):
            VALIDATOR.validate(self.root, R3.OVERLAY)

    def test_static_check_is_inert(self) -> None:
        result = subprocess.run([sys.executable, "-B", str(R3_RUNNER_PATH), "--check"], check=True, text=True, capture_output=True)
        plan = json.loads(result.stdout)
        self.assertEqual(plan["campaign_id"], R3.CAMPAIGN_ID)
        self.assertEqual((plan["gpu_actions"], plan["network_requests"], plan["output_writes"]), (0, 0, 0))


if __name__ == "__main__":
    unittest.main()
