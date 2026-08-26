#!/usr/bin/env python3
"""Fail-closed tests for Q4_K_M/q8_0-KV graph exact-depth R1."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest


RUNNER_PATH = Path(__file__).with_name("run-20260825-qwen36-q4km-q8kv-tp1-sycl-graph-exact-depth-r1.py")


def load_runner():
    spec = importlib.util.spec_from_file_location("q4km_q8kv_graph_r1_test", RUNNER_PATH)
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
        cls.base = cls.runner.BASE_LOAD_MANIFEST()
        cls.runner.validate_manifest(cls.manifest)

    def test_only_kv_selector_delta(self) -> None:
        argv = self.manifest["argv_template"]
        self.assertEqual(self.manifest["selectors"]["kv"], "q8_0")
        self.assertEqual(argv[argv.index("-ctk") + 1], "q8_0")
        self.assertEqual(argv[argv.index("-ctv") + 1], "q8_0")
        for key in ("model", "runtime", "source", "environment", "graph_evidence"):
            self.assertEqual(self.manifest[key], self.base[key])

    def test_exact_q4km_mtp0_context_identity(self) -> None:
        selectors = self.manifest["selectors"]
        self.assertEqual(selectors["artifact_id"], "qwen36-27b-unsloth-mtp-q4-k-m-5cb35eb")
        self.assertEqual(selectors["quantization"], "Q4_K_M")
        self.assertEqual(selectors["mtp"], 0)
        self.assertEqual(selectors["active_context_tokens"], [0, 2048, 4096, 8192, 16384, 24576, 32768])
        self.assertEqual(len(self.manifest["runtime"]["effective_shared_libraries"]), 32)

    def test_graph_off_reference_and_authority_closed(self) -> None:
        overlay = self.runner.load_overlay()
        self.assertEqual(overlay["accepted_graph_off_q4km_q8kv_reference"]["measurement_id"], "q36-q4km-tp1-kv-q8-context")
        authority = overlay["authority"]
        self.assertFalse(authority["site_publication_authorized"])
        self.assertFalse(authority["quality_claim_authorized"])
        self.assertFalse(authority["record_or_submission_authorized"])
        self.assertTrue(authority["graph_estimates_forbidden"])
        self.assertTrue(authority["protected_graph_off_values_must_not_be_replaced"])

    def test_mutations_fail_closed(self) -> None:
        for mutation in (
            lambda value: value["selectors"].__setitem__("kv", "f16"),
            lambda value: value["model"].__setitem__("sha256", "0" * 64),
            lambda value: value["environment"].__setitem__("GGML_SYCL_GRAPH_CACHE_SIZE", "9"),
        ):
            bad = copy.deepcopy(self.manifest)
            mutation(bad)
            with self.assertRaises(self.runner.GateError):
                self.runner.validate_manifest(bad)

    def test_check_is_inert_and_execute_requires_ack(self) -> None:
        self.assertFalse(self.runner.RUN_ROOT.exists())
        checked = subprocess.run([sys.executable, "-B", str(RUNNER_PATH), "--check"], check=True, text=True, capture_output=True)
        self.assertFalse(json.loads(checked.stdout)["launched"])
        denied = subprocess.run([sys.executable, "-B", str(RUNNER_PATH), "--execute"], check=False, text=True, capture_output=True)
        self.assertEqual(denied.returncode, 2)
        self.assertIn("exact acknowledgement", denied.stderr)
        self.assertFalse(self.runner.RUN_ROOT.exists())


if __name__ == "__main__":
    unittest.main()
