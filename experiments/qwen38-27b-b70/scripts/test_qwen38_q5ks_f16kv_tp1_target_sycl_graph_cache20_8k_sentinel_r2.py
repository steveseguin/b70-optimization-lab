#!/usr/bin/env python3
"""Focused inert tests for the Qwen3.8 Q5 cache-20 graph sentinel."""

import importlib.util, json, subprocess, sys, tempfile, unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNNER_PATH = HERE / "run-20260826-qwen38-q5ks-f16kv-tp1-target-sycl-graph-cache20-8k-sentinel-r2.py"
VALIDATOR_PATH = HERE / "validate-20260826-qwen38-q5ks-f16kv-tp1-target-sycl-graph-cache20-8k-sentinel-r2.py"

def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

class PacketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runner = load(RUNNER_PATH, "qwen38_q5_cache20_tested")
        cls.validator = load(VALIDATOR_PATH, "qwen38_q5_cache20_validator_tested")
        cls.overlay = cls.runner.load_overlay()
        cls.manifest = cls.runner.load_manifest()

    def test_exact_bounded_delta(self):
        delta = self.overlay["mechanism_delta"]
        self.assertEqual(delta["cache_size"], {"from":8,"to":20})
        self.assertFalse(delta["source_change"])
        self.assertFalse(delta["binary_change"])
        self.assertTrue(delta["no_automatic_capacity_escalation"])
        self.assertEqual(self.manifest["execution_contract"]["candidate_environment_delta"], {"GGML_SYCL_ENABLE_GRAPH":"1","GGML_SYCL_GRAPH_CACHE_SIZE":"20"})

    def test_failed_r1_is_a_sealed_prerequisite(self):
        failed = self.overlay["failed_r1_evidence"]
        self.assertEqual(failed["observed"]["cache_hit"], 0)
        self.assertEqual(failed["observed"]["cache_full"], 138)
        self.assertEqual(failed["timing_structure"]["non_decode_graph_requests"], 18)
        self.assertTrue(failed["must_remain_immutable"])

    def test_strict_graph_gate(self):
        good = {"summary_count":1,"requested":146,"cache_entries":20,"cache_limit":20,"cache_hit":126,"cache_miss":20,"cache_full":0,"direct_replay":126,"recorded":20,"created":20,"updated":0,"recreated":0,"replayed":146,"compatibility_rejected":0,"device_unsupported":0}
        self.assertTrue(self.validator.graph_mechanism_passes(good))
        for key, bad_value in (("cache_hit",119),("direct_replay",0),("cache_full",1),("replayed",145)):
            bad = dict(good)
            bad[key] = bad_value
            self.assertFalse(self.validator.graph_mechanism_passes(bad), key)

    def test_narrow_authority_and_protected_values(self):
        frozen = self.manifest["frozen_interpretation"]
        self.assertEqual(frozen["site_cells_authorized"], 0)
        self.assertFalse(frozen["full_graph_curve_authorized"])
        self.assertTrue(frozen["full_curve_preregistration_authorized_only_on_pass"])
        self.assertEqual(frozen["protected_decode_values"], [71.45427094575045,30.329809361830037,49.05894025767351,71.9001988117144])

    def test_inert_default_and_wrong_ack(self):
        with tempfile.TemporaryDirectory() as directory:
            before = set(Path(directory).iterdir())
            result = subprocess.run([sys.executable, str(RUNNER_PATH)], cwd=directory, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(before, set(Path(directory).iterdir()))
            self.assertTrue(json.loads(result.stdout)["default_is_inert"])
        result = subprocess.run([sys.executable, str(RUNNER_PATH), "--execute", "--ack", "wrong"], text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exact --ack required", result.stderr)

if __name__ == "__main__":
    unittest.main()
