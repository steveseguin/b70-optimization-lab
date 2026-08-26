from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
LANE = HERE.parent
RUNNER_PATH = HERE / "run-20260825-qwen36-mtpq8-f16-tp1-mtp3-exact-depth-r1.py"
VALIDATOR_PATH = HERE / "validate-20260825-qwen36-mtpq8-f16-tp1-mtp3-exact-depth-r1.py"
MANIFEST_PATH = LANE / "data/2026-08-25-qwen36-mtpq8-f16-tp1-mtp3-exact-depth-r1-prereg.json"


def module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


RUNNER = module(RUNNER_PATH, "qwen36_mtp3_curve_runner_test")
VALIDATOR = module(VALIDATOR_PATH, "qwen36_mtp3_curve_validator_test")


class MTP3ExactDepthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = json.loads(MANIFEST_PATH.read_text())
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        alias = self.manifest["server_contract"]["model_alias"]
        control_argv = RUNNER.Execution(self.manifest).server_argv(False)
        candidate_argv = RUNNER.Execution(self.manifest).server_argv(True)
        identity = {
            "campaign_id": RUNNER.CAMPAIGN_ID,
            "git_head": "a" * 40,
            "origin_main": "a" * 40,
            "model": {"sha256": self.manifest["model"]["sha256"]},
            "runtime": {
                "binary_sha256": self.manifest["runtime"]["binary_sha256"],
                "manifest_sha256": self.manifest["runtime"]["manifest_sha256"],
                "local_dsos": self.manifest["runtime"]["effective_local_shared_libraries"],
            },
            "fixture_sha256": self.manifest["fixture"]["sha256"],
            "server_argv": {"control-mtp0": control_argv, "candidate-mtp3": candidate_argv},
            "runtime_environment": {"GGML_SYCL_ENABLE_GRAPH": "0", "GGML_SYCL_GRAPH_CACHE_SIZE": "0"},
        }
        (self.root / "identity.json").write_text(json.dumps(identity))
        for arm in ("control-mtp0", "candidate-mtp3"):
            arm_dir = self.root / arm; arm_dir.mkdir()
            (arm_dir / "models.json").write_text(json.dumps({"data": [{"id": alias}]}))
            (arm_dir / "server.log").write_text("target\n")
            (arm_dir / "cleanup.json").write_text(json.dumps({"forced_kill": False, "port_closed": True, "render_node_idle": True, "server_survivor": False}))
        for index, depth in enumerate(RUNNER.DEPTHS):
            for arm in ("control-mtp0", "candidate-mtp3"):
                directory = self.root / arm / f"depth-{depth}"; directory.mkdir()
                receipt = {
                    "schema": "openai-token-depth-benchmark-v1", "status": "passed", "gate": {"passed": True},
                    "run_identity": {"model": alias, "depth": depth, "active_context_tokens": depth,
                                     "configured_context_capacity": 33024, "case_id": f"depth-{depth}",
                                     "max_tokens": 128, "metric_events": 100, "metric_intervals": 99},
                    "fixture": {"fixture_sha256": self.manifest["fixture"]["sha256"],
                                "prompt_token_ids_sha256": self.manifest["fixture"]["prompt_token_ids_sha256"][index]},
                    "metric_window": {"timestamped_events": 100, "inter_token_intervals": 99,
                                      "conventional_99_interval_tok_s": 20.0 + index},
                    "response": {"output_token_ids_sha256": f"{index + 1:064x}",
                                 "usage": {"prompt_tokens_details": {"cached_tokens": 0}}},
                }
                (directory / "exact-depth.json").write_text(json.dumps(receipt))
            counter = {"depth": depth, "rows_before": index, "rows_after": index + 1,
                       "new_rows": [{"ratio": 0.75, "accepted": 75, "generated": 100}]}
            (self.root / "candidate-mtp3" / f"depth-{depth}" / "draft-counters.json").write_text(json.dumps(counter))
        usage = {"usage": {"prompt_tokens_details": {"cached_tokens": 0}}}
        quality = {"pass_all": True, "exact_cases": [usage] * 4,
                   "repeat_case": {"repeats": 2, "runs": [usage, usage]},
                   "long_context_case": {"requested_context_tokens": 29400, "pass": True, **usage}}
        (self.root / "candidate-mtp3/quality.json").write_text(json.dumps(quality))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_static_check_is_inert_and_complete(self) -> None:
        result = subprocess.run([sys.executable, "-B", str(RUNNER_PATH), "--check"], check=True, text=True, capture_output=True)
        plan = json.loads(result.stdout)
        self.assertTrue(plan["default_is_inert"])
        self.assertEqual(plan["gpu_actions"], 0)
        self.assertEqual(plan["depths"], list(RUNNER.DEPTHS))

    def test_server_identity_is_mtp3_f16_graph_off(self) -> None:
        argv = RUNNER.Execution(self.manifest).server_argv(True)
        self.assertEqual(argv[argv.index("--spec-draft-n-max") + 1], "3")
        self.assertEqual(argv[argv.index("-ctk") + 1], "f16")
        self.assertEqual(argv[argv.index("-ctv") + 1], "f16")
        self.assertNotIn("graph", " ".join(argv).lower())

    def test_validator_accepts_all_seven_exact_pairs(self) -> None:
        result = VALIDATOR.validate(self.root, MANIFEST_PATH)
        self.assertTrue(result["gate"]["passed"])
        self.assertEqual(result["authority"]["matrix_cells_if_reviewed"], 7)
        self.assertFalse(result["authority"]["site_publication"])

    def test_validator_fails_output_divergence(self) -> None:
        path = self.root / "candidate-mtp3/depth-8192/exact-depth.json"
        value = json.loads(path.read_text()); value["response"]["output_token_ids_sha256"] = "f" * 64
        path.write_text(json.dumps(value))
        result = VALIDATOR.validate(self.root, MANIFEST_PATH)
        self.assertFalse(result["gate"]["passed"])
        self.assertFalse(result["gate"]["checks"]["depth_8192_target_output_parity"])

    def test_validator_fails_unengaged_drafts(self) -> None:
        path = self.root / "candidate-mtp3/depth-32768/draft-counters.json"
        value = json.loads(path.read_text()); value["new_rows"][0].update({"accepted": 0, "ratio": 0.0})
        path.write_text(json.dumps(value))
        result = VALIDATOR.validate(self.root, MANIFEST_PATH)
        self.assertFalse(result["gate"]["checks"]["depth_32768_draft_engaged_conserved"])


if __name__ == "__main__":
    unittest.main()
