#!/usr/bin/env python3
"""Fail-closed tests for Q4_K_M/F16 graph exact-depth R1."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest


RUNNER_PATH = Path(__file__).with_name("run-20260825-qwen36-q4km-f16-tp1-sycl-graph-exact-depth-r1.py")


def load_runner():
    spec = importlib.util.spec_from_file_location("q4km_graph_r1_test", RUNNER_PATH)
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
        cls.runner.validate_manifest(cls.manifest)

    def test_complete_model_and_artifact_identity_replaced(self) -> None:
        overlay = self.runner.load_overlay()
        delta = overlay["model_identity_delta"]
        expected = delta["model"]
        self.assertEqual(self.manifest["model"], expected)
        self.assertEqual(self.manifest["selectors"]["artifact_id"], self.runner.ARTIFACT_ID)
        self.assertEqual(self.manifest["selectors"]["quantization"], "Q4_K_M")
        self.assertEqual(expected["repository"], "unsloth/Qwen3.6-27B-MTP-GGUF")
        self.assertTrue(expected["embedded_mtp_capability"])
        self.assertEqual(expected["sha256"], expected["direct_sha256"])
        self.assertEqual(expected["sha256"], expected["ordinary_sha256"])

    def test_mtp0_f16_seven_depth_selectors(self) -> None:
        selectors = self.manifest["selectors"]
        self.assertEqual(selectors["mtp"], 0)
        self.assertEqual(selectors["kv"], "f16")
        self.assertEqual(selectors["active_context_tokens"], [0, 2048, 4096, 8192, 16384, 24576, 32768])

    def test_only_model_artifact_and_lifecycle_delta(self) -> None:
        base = self.runner.BASE_LOAD_MANIFEST()
        for key in ("source", "runtime", "environment", "graph_evidence"):
            self.assertEqual(self.manifest[key], base[key])
        self.assertEqual(len(self.manifest["runtime"]["effective_shared_libraries"]), 32)

    def test_argv_uses_q4km_f16_and_verbose_json(self) -> None:
        argv = self.manifest["argv_template"]
        self.assertEqual(argv[argv.index("-m") + 1], str(self.runner.MODEL_PATH))
        self.assertEqual(argv[argv.index("-ctk") + 1], "f16")
        self.assertEqual(argv[argv.index("-ctv") + 1], "f16")
        self.assertEqual(argv[-3:], ["-v", "-o", "json"])

    def test_graph_off_reference_and_authority_are_closed(self) -> None:
        overlay = self.runner.load_overlay()
        self.assertEqual(overlay["accepted_graph_off_q4km_reference"]["measurement_id"], "q36-q4km-tp1-kv-f16-context")
        authority = overlay["authority"]
        self.assertFalse(authority["site_publication_authorized"])
        self.assertFalse(authority["quality_claim_authorized"])
        self.assertFalse(authority["record_or_submission_authorized"])
        self.assertTrue(authority["protected_graph_off_values_must_not_be_replaced"])

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
