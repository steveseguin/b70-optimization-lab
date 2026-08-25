#!/usr/bin/env python3
"""Focused fail-closed tests for the R2 verbose graph-depth wrapper."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import sys
import unittest


RUNNER = Path(__file__).with_name("run-20260825-qwen36-q8-f16-tp1-sycl-graph-exact-depth-r2.py")


def load_runner():
    spec = importlib.util.spec_from_file_location("qwen36_q8_f16_sycl_graph_depth_r2_test", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class R2PacketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_runner()
        cls.manifest = cls.module.load_manifest()

    def test_distinct_create_only_identity(self) -> None:
        self.assertTrue(self.module.CAMPAIGN_ID.endswith("exact-depth-20260825-r2"))
        self.assertTrue(str(self.module.RUN_ROOT).endswith("exact-depth-20260825-r2"))
        self.assertEqual(self.module.ACK, f"RUN {self.module.CAMPAIGN_ID}")
        self.assertTrue(self.manifest["lifecycle"]["artifacts_are_create_only"])

    def test_only_argv_delta_is_verbose(self) -> None:
        base = self.module.R1.load_json(self.module.BASE_MANIFEST)
        candidate = copy.deepcopy(self.manifest)
        self.assertEqual(candidate["argv_template"][-3:], ["-v", "-o", "json"])
        candidate["campaign_id"] = base["campaign_id"]
        candidate["purpose"] = base["purpose"]
        candidate["argv_template"] = [*candidate["argv_template"][:-3], "-o", "json"]
        candidate["lifecycle"]["output_root"] = base["lifecycle"]["output_root"]
        candidate["lifecycle"]["exact_ack"] = base["lifecycle"]["exact_ack"]
        self.assertEqual(candidate, base)

    def test_seven_contexts_and_runtime_preserved(self) -> None:
        base = self.module.R1.load_json(self.module.BASE_MANIFEST)
        self.assertEqual(self.manifest["selectors"], base["selectors"])
        self.assertEqual(self.manifest["source"], base["source"])
        self.assertEqual(self.manifest["model"], base["model"])
        self.assertEqual(self.manifest["runtime"], base["runtime"])
        self.assertEqual(len(self.manifest["runtime"]["effective_shared_libraries"]), 32)

    def test_authority_remains_closed(self) -> None:
        interpretation = self.manifest["interpretation"]
        self.assertFalse(interpretation["site_publication_authorized"])
        self.assertFalse(interpretation["record_or_submission_authorized"])
        self.assertFalse(interpretation["quality_claim_authorized"])
        self.assertTrue(interpretation["protected_graph_off_values_must_not_be_replaced"])

    def test_manifest_rejects_any_extra_change(self) -> None:
        bad = copy.deepcopy(self.manifest)
        bad["environment"]["GGML_SYCL_GRAPH_CACHE_SIZE"] = "9"
        with self.assertRaises(self.module.GateError):
            self.module.validate_manifest(bad)

    def test_base_hashes_are_current(self) -> None:
        self.assertEqual(self.module.sha256_file(self.module.BASE_MANIFEST), self.module.BASE_MANIFEST_SHA256)
        self.assertEqual(self.module.sha256_file(self.module.BASE_RUNNER), self.module.BASE_RUNNER_SHA256)


if __name__ == "__main__":
    unittest.main()
