#!/usr/bin/env python3
"""Fail-closed CPU tests for Q4_K_M/q8KV graph quality R1."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest


SCRIPT = Path(__file__).with_name("run-20260825-qwen36-q4km-q8kv-tp1-sycl-graph-quality-r1.py")


def load_runner():
    spec = importlib.util.spec_from_file_location("qwen36_q4km_q8kv_graph_quality_r1_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runner = load_runner()
        cls.manifest = cls.runner.load_manifest()
        cls.base = cls.runner.BASE_MANIFEST_VALUE
        cls.runner.validate_manifest(cls.manifest)

    def test_complete_q4km_model_unchanged(self) -> None:
        self.assertEqual(self.manifest["model"], self.base["model"])
        self.assertEqual(self.manifest["model"]["sha256"], "a7cbd3ecc0e3f9b333edee61ae66bc87ed713c5d49587a8355814722ed329e0f")
        self.assertEqual(self.manifest["selectors"]["quantization"], "Q4_K_M")

    def test_kv_only_runtime_delta(self) -> None:
        for key in ("source", "runtime", "environment", "quality", "model"):
            self.assertEqual(self.manifest[key], self.base[key])
        argv = self.manifest["server_argv"]
        self.assertEqual(self.manifest["selectors"]["kv"], "q8_0")
        self.assertEqual(argv[argv.index("-ctk") + 1], "q8_0")
        self.assertEqual(argv[argv.index("-ctv") + 1], "q8_0")

    def test_mtp0_spec_none_curve_and_battery(self) -> None:
        argv = self.manifest["server_argv"]
        self.assertEqual(self.manifest["selectors"]["mtp"], 0)
        self.assertEqual(argv[argv.index("--spec-type") + 1], "none")
        self.assertEqual(self.manifest["curve_parent"]["campaign_id"], "qwen36-q4km-q8kv-tp1-sycl-graph-exact-depth-20260825-r1")
        self.assertEqual(self.manifest["curve_parent"]["depths"], [0, 2048, 4096, 8192, 16384, 24576, 32768])
        q = self.manifest["quality"]
        self.assertEqual((q["exact_case_count"], q["repeat_runs"], q["expected_request_count"]), (4, 8, 13))

    def test_authority_closed(self) -> None:
        authority = self.manifest["authority"]
        self.assertFalse(authority["site_publication_authorized"])
        self.assertFalse(authority["record_or_submission_authorized"])
        self.assertFalse(authority["protected_graph_off_values_may_be_replaced"])

    def test_mutations_fail_closed(self) -> None:
        for mutation in (
            lambda v: v["model"].__setitem__("sha256", "0" * 64),
            lambda v: v["selectors"].__setitem__("kv", "f16"),
            lambda v: v["environment"].__setitem__("GGML_SYCL_GRAPH_CACHE_SIZE", "9"),
        ):
            bad = copy.deepcopy(self.manifest)
            mutation(bad)
            with self.assertRaises(self.runner.GateError):
                self.runner.validate_manifest(bad)

    def test_default_check_inert_and_execute_needs_ack(self) -> None:
        self.assertFalse(self.runner.RUN_ROOT.exists())
        planned = subprocess.run([sys.executable, "-B", str(SCRIPT)], text=True, capture_output=True, check=True)
        plan = json.loads(planned.stdout)
        self.assertEqual((plan["quantization"], plan["kv"]), ("Q4_K_M", "q8_0"))
        checked = subprocess.run([sys.executable, "-B", str(SCRIPT), "--check"], text=True, capture_output=True, check=True)
        self.assertFalse(json.loads(checked.stdout)["launched"])
        denied = subprocess.run([sys.executable, "-B", str(SCRIPT), "--execute"], text=True, capture_output=True, check=False)
        self.assertEqual(denied.returncode, 2)
        self.assertIn("exact acknowledgement", denied.stderr)
        self.assertFalse(self.runner.RUN_ROOT.exists())


if __name__ == "__main__":
    unittest.main()
