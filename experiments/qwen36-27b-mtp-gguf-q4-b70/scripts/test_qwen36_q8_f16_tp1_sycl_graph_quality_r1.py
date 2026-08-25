#!/usr/bin/env python3
"""CPU-only contract tests for the graph quality packet."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest


SCRIPT = Path(__file__).with_name("run-20260825-qwen36-q8-f16-tp1-sycl-graph-quality-r1.py")
SPEC = importlib.util.spec_from_file_location("qwen36_graph_quality_r1_test", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
RUNNER = importlib.util.module_from_spec(SPEC); sys.modules[SPEC.name] = RUNNER; SPEC.loader.exec_module(RUNNER)


def usage() -> dict:
    return {"prompt_tokens_details": {"cached_tokens": 0}}


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = RUNNER.load_manifest(); RUNNER.validate_manifest(cls.manifest)

    def test_exact_curve_identity_and_patch_order(self) -> None:
        self.assertEqual(self.manifest["environment"], RUNNER.CURVE.load_manifest()["environment"])
        self.assertEqual(self.manifest["environment"]["GGML_SYCL_GRAPH_CACHE_SIZE"], "8")
        patches = self.manifest["source"]["patch_chain_in_order"]
        self.assertEqual([row["sha256"] for row in patches], [
            "1a8589f894fde7d87aac35c59bc81e3701bf7f6d9ba54f35808ae262325d7892",
            "1575acc5ee07b37eb98186a09d201a895d36501c223dc114110a43ee08f4e0a3",
            "3def9e5eeb42d9bd1dc4b0c759092572db178651ecafc5255943753bd8b485f6",
        ])

    def test_server_and_quality_contract(self) -> None:
        self.assertEqual(self.manifest["runtime"]["server"]["sha256"], "b82fcfc3bda77b0446c11daa5da62b39ddf941202150d9b44a9092968658e19b")
        self.assertEqual(self.manifest["runtime"]["server_effective_shared_libraries"]["count"], 33)
        self.assertEqual(self.manifest["quality"]["exact_case_count"], 4)
        self.assertEqual(self.manifest["quality"]["repeat_runs"], 8)
        self.assertEqual(self.manifest["quality"]["near_32k_needle_target_tokens"], 31744)
        self.assertEqual(self.manifest["quality"]["expected_request_count"], 13)

    def test_quality_validator_requires_all_thirteen_cached_zero(self) -> None:
        exact = [{"pass": True, "usage": usage()} for _ in range(4)]
        repeats = [{"usage": usage()} for _ in range(8)]
        value = {"pass_all": True, "exact_cases": exact, "repeat_case": {"repeats": 8, "pass": True, "unique_hashes": ["x"], "runs": repeats}, "long_context_case": {"requested_context_tokens": 31744, "actual_prompt_tokens": 31800, "pass": True, "usage": usage()}}
        self.assertEqual(RUNNER.validate_quality(value, self.manifest)["request_count"], 13)
        bad = copy.deepcopy(value); bad["repeat_case"]["runs"][3]["usage"]["prompt_tokens_details"]["cached_tokens"] = 1
        with self.assertRaises(RUNNER.GateError):
            RUNNER.validate_quality(bad, self.manifest)

    def test_graph_mechanism_gate(self) -> None:
        good = "[SYCL-GRAPH] summary device=0 requested=20 compatibility_rejected=0 device_unsupported=0 cache_entries=8 cache_limit=8 cache_hit=12 cache_miss=8 cache_full=4 direct_replay=12 recorded=4 created=4 updated=0 recreated=0 replayed=16"
        self.assertEqual(RUNNER.graph_evidence(good)["summary_count"], 1)
        with self.assertRaises(RUNNER.GateError):
            RUNNER.graph_evidence(good.replace("device_unsupported=0", "device_unsupported=1"))

    def test_coverage_and_claim_boundaries(self) -> None:
        authority = self.manifest["authority"]
        self.assertTrue(authority["quality_may_cover_all_seven_curve_cells_on_pass"])
        self.assertFalse(authority["per_depth_quality_reruns_required"])
        self.assertTrue(authority["raw_engine_speed_measurements_unchanged"])
        self.assertTrue(authority["mixed_partial_prefill_graph_claim_preserved"])
        self.assertFalse(authority["protected_graph_off_values_may_be_replaced"])

    def test_check_is_cpu_only_and_inert(self) -> None:
        self.assertFalse(RUNNER.RUN_ROOT.exists())
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), "--check"], text=True, capture_output=True, check=True)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "PASS"); self.assertFalse(payload["launched"])
        self.assertFalse(RUNNER.RUN_ROOT.exists())

    def test_execute_requires_exact_ack(self) -> None:
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), "--execute"], text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 2); self.assertIn("exact acknowledgement", result.stderr)
        self.assertFalse(RUNNER.RUN_ROOT.exists())


if __name__ == "__main__":
    unittest.main()
