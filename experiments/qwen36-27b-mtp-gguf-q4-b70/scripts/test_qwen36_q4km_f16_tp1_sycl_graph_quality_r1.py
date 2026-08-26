#!/usr/bin/env python3
"""Fail-closed CPU tests for Q4_K_M/F16 graph quality R1."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest


SCRIPT = Path(__file__).with_name("run-20260825-qwen36-q4km-f16-tp1-sycl-graph-quality-r1.py")


def load_runner():
    spec = importlib.util.spec_from_file_location("qwen36_q4km_f16_graph_quality_r1_test", SCRIPT)
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

    def test_complete_q4km_model_identity(self) -> None:
        model = self.manifest["model"]
        self.assertEqual(model, self.runner.CURVE.load_manifest()["model"])
        self.assertEqual(model["revision"], "5cb35eb3dcbf52dbce5f87dbc64df6aaffadcace")
        self.assertEqual(model["size_bytes"], 17106773120)
        self.assertEqual(model["sha256"], "a7cbd3ecc0e3f9b333edee61ae66bc87ed713c5d49587a8355814722ed329e0f")
        self.assertTrue(model["embedded_mtp_capability"])

    def test_only_complete_model_and_corresponding_identities_change(self) -> None:
        for key in ("source", "runtime", "environment", "quality"):
            self.assertEqual(self.manifest[key], self.base[key])
        selectors = self.manifest["selectors"]
        self.assertEqual((selectors["artifact_id"], selectors["quantization"]), ("qwen36-27b-unsloth-mtp-q4-k-m-5cb35eb", "Q4_K_M"))

    def test_f16_mtp0_spec_none_preserved(self) -> None:
        argv = self.manifest["server_argv"]
        self.assertEqual((self.manifest["selectors"]["kv"], self.manifest["selectors"]["mtp"]), ("f16", 0))
        self.assertEqual(argv[argv.index("-ctk") + 1], "f16")
        self.assertEqual(argv[argv.index("-ctv") + 1], "f16")
        self.assertEqual(argv[argv.index("--spec-type") + 1], "none")

    def test_curve_battery_and_authority(self) -> None:
        self.assertEqual(self.manifest["curve_parent"]["campaign_id"], "qwen36-q4km-f16-tp1-sycl-graph-exact-depth-20260825-r1")
        self.assertEqual(self.manifest["curve_parent"]["depths"], [0, 2048, 4096, 8192, 16384, 24576, 32768])
        quality = self.manifest["quality"]
        self.assertEqual((quality["exact_case_count"], quality["repeat_runs"], quality["expected_request_count"]), (4, 8, 13))
        self.assertEqual(quality["near_32k_needle_target_tokens"], 31744)
        self.assertFalse(self.manifest["authority"]["site_publication_authorized"])
        self.assertFalse(self.manifest["authority"]["record_or_submission_authorized"])

    def test_mutations_fail_closed(self) -> None:
        for mutation in (
            lambda v: v["model"].__setitem__("sha256", "0" * 64),
            lambda v: v["selectors"].__setitem__("quantization", "Q8_0"),
            lambda v: v["server_argv"].__setitem__(v["server_argv"].index("-ctk") + 1, "q8_0"),
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
        self.assertTrue(plan["default_is_inert"])
        self.assertEqual((plan["quantization"], plan["kv"]), ("Q4_K_M", "f16"))
        checked = subprocess.run([sys.executable, "-B", str(SCRIPT), "--check"], text=True, capture_output=True, check=True)
        self.assertFalse(json.loads(checked.stdout)["launched"])
        denied = subprocess.run([sys.executable, "-B", str(SCRIPT), "--execute"], text=True, capture_output=True, check=False)
        self.assertEqual(denied.returncode, 2)
        self.assertIn("exact acknowledgement", denied.stderr)
        self.assertFalse(self.runner.RUN_ROOT.exists())


if __name__ == "__main__":
    unittest.main()
