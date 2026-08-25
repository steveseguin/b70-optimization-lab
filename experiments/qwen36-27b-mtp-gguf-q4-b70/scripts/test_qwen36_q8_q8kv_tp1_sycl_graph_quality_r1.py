#!/usr/bin/env python3
"""CPU-only contract tests for the q8_0-KV graph quality packet."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest


SCRIPT = Path(__file__).with_name("run-20260825-qwen36-q8-q8kv-tp1-sycl-graph-quality-r1.py")
SPEC = importlib.util.spec_from_file_location("qwen36_q8kv_graph_quality_r1_test", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
RUNNER = importlib.util.module_from_spec(SPEC); sys.modules[SPEC.name] = RUNNER; SPEC.loader.exec_module(RUNNER)


def usage() -> dict:
    return {"prompt_tokens_details": {"cached_tokens": 0}}


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = RUNNER.load_manifest(); RUNNER.validate_manifest(cls.manifest)

    def test_only_kv_service_selector_delta(self) -> None:
        argv = self.manifest["server_argv"]
        self.assertEqual(self.manifest["selectors"]["kv"], "q8_0")
        self.assertEqual(argv[argv.index("-ctk") + 1], "q8_0")
        self.assertEqual(argv[argv.index("-ctv") + 1], "q8_0")
        self.assertEqual(argv[argv.index("--port") + 1], "19437")
        self.assertEqual(self.manifest["environment"], RUNNER.CURVE.load_manifest()["environment"])

    def test_runtime_and_quality_contract_preserved(self) -> None:
        base = RUNNER.F16.load_manifest()
        self.assertEqual(self.manifest["runtime"], base["runtime"])
        self.assertEqual(self.manifest["source"], base["source"])
        self.assertEqual(self.manifest["quality"], base["quality"])
        self.assertEqual(self.manifest["runtime"]["server_effective_shared_libraries"]["count"], 33)

    def test_quality_requires_thirteen_cached_zero(self) -> None:
        value = {"pass_all": True, "exact_cases": [{"pass": True, "usage": usage()} for _ in range(4)],
            "repeat_case": {"repeats": 8, "pass": True, "unique_hashes": ["x"], "runs": [{"usage": usage()} for _ in range(8)]},
            "long_context_case": {"requested_context_tokens": 31744, "actual_prompt_tokens": 29403, "pass": True, "usage": usage()}}
        self.assertEqual(RUNNER.F16.validate_quality(value, self.manifest)["request_count"], 13)
        bad = copy.deepcopy(value); bad["exact_cases"][0]["usage"]["prompt_tokens_details"]["cached_tokens"] = 1
        with self.assertRaises(RUNNER.GateError): RUNNER.F16.validate_quality(bad, self.manifest)

    def test_graph_gate_and_authority(self) -> None:
        summary = "[SYCL-GRAPH] summary device=0 requested=20 compatibility_rejected=0 device_unsupported=0 cache_entries=8 cache_limit=8 cache_hit=12 cache_miss=8 cache_full=4 direct_replay=12 recorded=4 created=4 updated=0 recreated=0 replayed=16"
        self.assertEqual(RUNNER.F16.graph_evidence(summary)["summary_count"], 1)
        authority = self.manifest["authority"]
        self.assertFalse(authority["site_publication_authorized"])
        self.assertTrue(authority["publication_requires_tracked_adjudication_and_separate_ingestion"])

    def test_check_is_inert_and_execute_requires_ack(self) -> None:
        self.assertFalse(RUNNER.RUN_ROOT.exists())
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), "--check"], text=True, capture_output=True, check=True)
        self.assertFalse(json.loads(result.stdout)["launched"]); self.assertFalse(RUNNER.RUN_ROOT.exists())
        denied = subprocess.run([sys.executable, "-B", str(SCRIPT), "--execute"], text=True, capture_output=True, check=False)
        self.assertEqual(denied.returncode, 2); self.assertIn("exact acknowledgement", denied.stderr)


if __name__ == "__main__": unittest.main()
