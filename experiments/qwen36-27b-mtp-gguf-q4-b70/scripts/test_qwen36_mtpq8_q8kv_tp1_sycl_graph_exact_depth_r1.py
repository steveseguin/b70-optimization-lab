#!/usr/bin/env python3
"""CPU-only contract tests for embedded-MTP Q8/q8-KV graph exact depth."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest


SCRIPT = Path(__file__).with_name("run-20260825-qwen36-mtpq8-q8kv-tp1-sycl-graph-exact-depth-r1.py")
SPEC = importlib.util.spec_from_file_location("qwen36_mtpq8_q8kv_graph_depth_r1_test", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
RUNNER = importlib.util.module_from_spec(SPEC); sys.modules[SPEC.name] = RUNNER; SPEC.loader.exec_module(RUNNER)


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = RUNNER.load_manifest(); RUNNER.validate_manifest(cls.manifest)

    def test_only_kv_selector_delta(self) -> None:
        base = RUNNER.BASE_LOAD_MANIFEST(); argv = self.manifest["argv_template"]
        self.assertEqual(self.manifest["selectors"]["kv"], "q8_0")
        self.assertEqual(argv[argv.index("-ctk") + 1], "q8_0")
        self.assertEqual(argv[argv.index("-ctv") + 1], "q8_0")
        self.assertEqual(self.manifest["model"], base["model"])
        self.assertEqual(self.manifest["runtime"], base["runtime"])
        self.assertEqual(self.manifest["source"], base["source"])
        self.assertEqual(self.manifest["environment"], base["environment"])

    def test_graph_context_and_authority_contract(self) -> None:
        self.assertEqual(self.manifest["selectors"]["active_context_tokens"], [0, 2048, 4096, 8192, 16384, 24576, 32768])
        self.assertEqual(self.manifest["graph_evidence"]["summary_count_exact"], 2)
        self.assertEqual(self.manifest["environment"]["GGML_SYCL_GRAPH_CACHE_SIZE"], "8")
        authority = self.manifest["interpretation"]
        self.assertFalse(authority["site_publication_authorized"])
        self.assertFalse(authority["record_or_submission_authorized"])
        self.assertFalse(authority["quality_claim_authorized"])

    def test_check_is_inert_and_execute_requires_ack(self) -> None:
        self.assertFalse(RUNNER.RUN_ROOT.exists())
        checked = subprocess.run([sys.executable, "-B", str(SCRIPT), "--check"], text=True, capture_output=True, check=True)
        self.assertFalse(json.loads(checked.stdout)["launched"]); self.assertFalse(RUNNER.RUN_ROOT.exists())
        denied = subprocess.run([sys.executable, "-B", str(SCRIPT), "--execute"], text=True, capture_output=True, check=False)
        self.assertEqual(denied.returncode, 2); self.assertIn("exact acknowledgement", denied.stderr)


if __name__ == "__main__":
    unittest.main()
