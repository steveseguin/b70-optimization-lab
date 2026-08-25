#!/usr/bin/env python3
"""Fail-closed CPU tests for embedded-MTP Q8/q8KV graph quality R1."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest


SCRIPT = Path(__file__).with_name("run-20260825-qwen36-mtpq8-q8kv-tp1-sycl-graph-quality-r1.py")


def load_runner():
    spec = importlib.util.spec_from_file_location("qwen36_mtpq8_q8kv_graph_quality_r1_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def usage() -> dict:
    return {"prompt_tokens_details": {"cached_tokens": 0}}


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runner = load_runner()
        cls.manifest = cls.runner.load_manifest()
        cls.base = cls.runner.BASE_MANIFEST_VALUE
        cls.runner.validate_manifest(cls.manifest)

    def test_complete_embedded_model_is_unchanged(self) -> None:
        self.assertEqual(self.manifest["model"], self.base["model"])
        self.assertEqual(self.manifest["model"]["repository"], "unsloth/Qwen3.6-27B-MTP-GGUF")
        self.assertEqual(self.manifest["model"]["revision"], "5cb35eb3dcbf52dbce5f87dbc64df6aaffadcace")
        self.assertEqual(self.manifest["model"]["sha256"], "9408dcb356cc061a05c139e5647cbde0698ff980c6a69f7fc214e9989f86cfa8")
        self.assertTrue(self.manifest["model"]["embedded_mtp_capability"])
        self.assertEqual(self.manifest["selectors"]["mtp"], 0)

    def test_only_kv_and_corresponding_identities_change(self) -> None:
        for key in ("source", "runtime", "environment", "quality", "model"):
            self.assertEqual(self.manifest[key], self.base[key])
        argv = self.manifest["server_argv"]
        self.assertEqual(self.manifest["selectors"]["kv"], "q8_0")
        self.assertEqual(argv[argv.index("-ctk") + 1], "q8_0")
        self.assertEqual(argv[argv.index("-ctv") + 1], "q8_0")
        self.assertEqual(argv[argv.index("--spec-type") + 1], "none")

    def test_curve_parent_and_create_only_namespace(self) -> None:
        self.assertEqual(self.manifest["curve_parent"]["campaign_id"], "qwen36-mtpq8-q8kv-tp1-sycl-graph-exact-depth-20260825-r1")
        self.assertEqual(self.manifest["curve_parent"]["depths"], [0, 2048, 4096, 8192, 16384, 24576, 32768])
        self.assertEqual(self.manifest["lifecycle"]["output_root"], str(self.runner.RUN_ROOT))
        self.assertEqual(self.manifest["lifecycle"]["exact_ack"], self.runner.ACK)
        self.assertTrue(self.manifest["lifecycle"]["create_only"])

    def test_battery_and_authority_are_preserved(self) -> None:
        quality = self.manifest["quality"]
        self.assertEqual((quality["exact_case_count"], quality["repeat_runs"], quality["expected_request_count"]), (4, 8, 13))
        self.assertEqual(quality["near_32k_needle_target_tokens"], 31744)
        authority = self.manifest["authority"]
        self.assertFalse(authority["site_publication_authorized"])
        self.assertFalse(authority["record_or_submission_authorized"])
        self.assertFalse(authority["protected_graph_off_values_may_be_replaced"])

    def test_quality_validator_requires_thirteen_cache_zero_responses(self) -> None:
        value = {
            "pass_all": True,
            "exact_cases": [{"pass": True, "usage": usage()} for _ in range(4)],
            "repeat_case": {"repeats": 8, "pass": True, "unique_hashes": ["x"], "runs": [{"usage": usage()} for _ in range(8)]},
            "long_context_case": {"requested_context_tokens": 31744, "actual_prompt_tokens": 29403, "pass": True, "usage": usage()},
        }
        self.assertEqual(self.runner.IMPL.F16.validate_quality(value, self.manifest)["request_count"], 13)
        bad = copy.deepcopy(value)
        bad["repeat_case"]["runs"][0]["usage"]["prompt_tokens_details"]["cached_tokens"] = 1
        with self.assertRaises(self.runner.GateError):
            self.runner.IMPL.F16.validate_quality(bad, self.manifest)

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

    def test_default_and_check_are_inert_and_execute_needs_ack(self) -> None:
        self.assertFalse(self.runner.RUN_ROOT.exists())
        planned = subprocess.run([sys.executable, "-B", str(SCRIPT)], text=True, capture_output=True, check=True)
        self.assertTrue(json.loads(planned.stdout)["default_is_inert"])
        checked = subprocess.run([sys.executable, "-B", str(SCRIPT), "--check"], text=True, capture_output=True, check=True)
        self.assertFalse(json.loads(checked.stdout)["launched"])
        denied = subprocess.run([sys.executable, "-B", str(SCRIPT), "--execute"], text=True, capture_output=True, check=False)
        self.assertEqual(denied.returncode, 2)
        self.assertIn("exact acknowledgement", denied.stderr)
        self.assertFalse(self.runner.RUN_ROOT.exists())


if __name__ == "__main__":
    unittest.main()
