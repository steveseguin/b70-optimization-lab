#!/usr/bin/env python3
"""Fail-closed CPU tests for the embedded-MTP Q8/F16 graph quality packet."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest


SCRIPT = Path(__file__).with_name("run-20260825-qwen36-mtpq8-f16-tp1-sycl-graph-quality-r1.py")
SPEC = importlib.util.spec_from_file_location("qwen36_mtpq8_graph_quality_r1_test", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
RUNNER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = RUNNER
SPEC.loader.exec_module(RUNNER)


def usage() -> dict:
    return {"prompt_tokens_details": {"cached_tokens": 0}}


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = RUNNER.load_manifest()
        RUNNER.validate_manifest(cls.manifest)

    def test_complete_embedded_mtp_model_identity(self) -> None:
        self.assertEqual(self.manifest["selectors"]["artifact_id"], "qwen36-27b-unsloth-mtp-q8-0-5cb35eb")
        self.assertEqual(self.manifest["model"]["repository"], "unsloth/Qwen3.6-27B-MTP-GGUF")
        self.assertEqual(self.manifest["model"]["revision"], "5cb35eb3dcbf52dbce5f87dbc64df6aaffadcace")
        self.assertEqual(self.manifest["model"]["sha256"], "9408dcb356cc061a05c139e5647cbde0698ff980c6a69f7fc214e9989f86cfa8")
        self.assertTrue(self.manifest["model"]["embedded_mtp_capability"])
        self.assertEqual(self.manifest["selectors"]["mtp"], 0)

    def test_only_allowed_identity_delta(self) -> None:
        base = RUNNER.BASE_MANIFEST_VALUE
        self.assertEqual(self.manifest["source"], base["source"])
        self.assertEqual(self.manifest["runtime"], base["runtime"])
        self.assertEqual(self.manifest["environment"], base["environment"])
        self.assertEqual(self.manifest["quality"], base["quality"])
        self.assertEqual(self.manifest["server_argv"][self.manifest["server_argv"].index("--spec-type") + 1], "none")

    def test_curve_parent_and_create_only_namespace(self) -> None:
        self.assertEqual(self.manifest["curve_parent"]["campaign_id"], "qwen36-mtpq8-f16-tp1-sycl-graph-exact-depth-20260825-r1")
        self.assertEqual(self.manifest["curve_parent"]["depths"], [0, 2048, 4096, 8192, 16384, 24576, 32768])
        self.assertEqual(self.manifest["lifecycle"]["exact_ack"], RUNNER.ACK)
        self.assertTrue(self.manifest["lifecycle"]["create_only"])

    def test_quality_validator_requires_all_thirteen_cached_zero(self) -> None:
        exact = [{"pass": True, "usage": usage()} for _ in range(4)]
        repeats = [{"usage": usage()} for _ in range(8)]
        value = {"pass_all": True, "exact_cases": exact, "repeat_case": {"repeats": 8, "pass": True, "unique_hashes": ["x"], "runs": repeats}, "long_context_case": {"requested_context_tokens": 31744, "actual_prompt_tokens": 29403, "pass": True, "usage": usage()}}
        self.assertEqual(RUNNER.BASEQ.validate_quality(value, self.manifest)["request_count"], 13)
        bad = copy.deepcopy(value)
        bad["repeat_case"]["runs"][0]["usage"]["prompt_tokens_details"]["cached_tokens"] = 1
        with self.assertRaises(RUNNER.GateError):
            RUNNER.BASEQ.validate_quality(bad, self.manifest)

    def test_graph_gate_and_claim_boundaries(self) -> None:
        good = "[SYCL-GRAPH] summary device=0 requested=20 compatibility_rejected=0 device_unsupported=0 cache_entries=8 cache_limit=8 cache_hit=12 cache_miss=8 cache_full=4 direct_replay=12 recorded=4 created=4 updated=0 recreated=0 replayed=16"
        self.assertEqual(RUNNER.BASEQ.graph_evidence(good)["summary_count"], 1)
        self.assertFalse(self.manifest["authority"]["site_publication_authorized"])
        self.assertFalse(self.manifest["authority"]["record_or_submission_authorized"])
        self.assertFalse(self.manifest["authority"]["protected_graph_off_values_may_be_replaced"])

    def test_check_is_inert_and_execute_needs_ack(self) -> None:
        self.assertFalse(RUNNER.RUN_ROOT.exists())
        checked = subprocess.run([sys.executable, "-B", str(SCRIPT), "--check"], text=True, capture_output=True, check=True)
        self.assertFalse(json.loads(checked.stdout)["launched"])
        denied = subprocess.run([sys.executable, "-B", str(SCRIPT), "--execute"], text=True, capture_output=True, check=False)
        self.assertEqual(denied.returncode, 2)
        self.assertIn("exact acknowledgement", denied.stderr)
        self.assertFalse(RUNNER.RUN_ROOT.exists())


if __name__ == "__main__":
    unittest.main()
