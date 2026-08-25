#!/usr/bin/env python3
"""Focused fail-closed tests for the sealed q8-KV graph curve R2."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import sys
import unittest


RUNNER = Path(__file__).with_name("run-20260825-qwen36-q8-q8kv-tp1-sycl-graph-exact-depth-r2.py")


def load_runner():
    spec = importlib.util.spec_from_file_location("qwen36_q8_q8kv_graph_depth_r2_test", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class Q8KvGraphDepthR2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_runner()
        cls.manifest = cls.module.load_manifest()
        cls.base = cls.module.F16_LOAD_MANIFEST()

    def test_distinct_create_only_identity(self) -> None:
        self.assertTrue(self.module.CAMPAIGN_ID.endswith("exact-depth-20260825-r2"))
        self.assertTrue(str(self.module.RUN_ROOT).endswith("exact-depth-20260825-r2"))
        self.assertEqual(self.module.ACK, f"RUN {self.module.CAMPAIGN_ID}")
        self.assertTrue(self.manifest["lifecycle"]["artifacts_are_create_only"])

    def test_exact_q8_kv_delta(self) -> None:
        self.assertEqual(self.manifest["selectors"]["kv"], "q8_0")
        argv = self.manifest["argv_template"]
        self.assertEqual(argv[argv.index("-ctk") + 1], "q8_0")
        self.assertEqual(argv[argv.index("-ctv") + 1], "q8_0")
        self.assertEqual(argv[-3:], ["-v", "-o", "json"])
        candidate = copy.deepcopy(self.manifest)
        candidate["campaign_id"] = self.base["campaign_id"]
        candidate["purpose"] = self.base["purpose"]
        candidate["selectors"]["kv"] = "f16"
        candidate["argv_template"][candidate["argv_template"].index("-ctk") + 1] = "f16"
        candidate["argv_template"][candidate["argv_template"].index("-ctv") + 1] = "f16"
        candidate["lifecycle"]["output_root"] = self.base["lifecycle"]["output_root"]
        candidate["lifecycle"]["exact_ack"] = self.base["lifecycle"]["exact_ack"]
        candidate["interpretation"]["fill_only"] = self.base["interpretation"]["fill_only"]
        self.assertEqual(candidate, self.base)

    def test_runtime_and_phase_gates_preserved(self) -> None:
        for key in ("source", "runtime", "model", "environment", "graph_evidence"):
            self.assertEqual(self.manifest[key], self.base[key])
        self.assertEqual(len(self.manifest["runtime"]["effective_shared_libraries"]), 32)
        self.assertEqual(self.manifest["graph_evidence"]["ordered_phases"], ["prefill", "decode"])
        self.assertEqual(self.manifest["environment"]["GGML_SYCL_GRAPH_CACHE_SIZE"], "8")

    def test_all_seven_contexts_preserved(self) -> None:
        self.assertEqual(self.manifest["selectors"]["active_context_tokens"], [0, 2048, 4096, 8192, 16384, 24576, 32768])

    def test_authority_closed(self) -> None:
        interpretation = self.manifest["interpretation"]
        self.assertFalse(interpretation["site_publication_authorized"])
        self.assertFalse(interpretation["quality_claim_authorized"])
        self.assertFalse(interpretation["record_or_submission_authorized"])
        self.assertTrue(interpretation["quality_gate_required_before_publication"])
        self.assertTrue(interpretation["protected_graph_off_values_must_not_be_replaced"])

    def test_extra_delta_rejected(self) -> None:
        bad = copy.deepcopy(self.manifest)
        bad["environment"]["GGML_SYCL_GRAPH_CACHE_SIZE"] = "9"
        with self.assertRaises(self.module.GateError):
            self.module.validate_manifest(bad)


if __name__ == "__main__":
    unittest.main()
