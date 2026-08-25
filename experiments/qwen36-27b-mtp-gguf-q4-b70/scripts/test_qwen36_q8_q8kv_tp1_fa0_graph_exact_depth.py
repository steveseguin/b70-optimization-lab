#!/usr/bin/env python3
"""CPU-only contract tests for the q8_0-KV fa0 graph curve."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest


SCRIPT = Path(__file__).with_name(
    "run-20260825-qwen36-q8-q8kv-tp1-fa0-graph-exact-depth-r1.py"
)
SPEC = importlib.util.spec_from_file_location("qwen36_q8_q8kv_fa0_graph_curve", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import {SCRIPT}")
RUNNER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = RUNNER
SPEC.loader.exec_module(RUNNER)


class Q8KvFa0GraphCurveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = RUNNER.load_manifest()

    def test_distinct_exact_seven_cell_identity(self) -> None:
        RUNNER.validate_manifest(self.manifest)
        selectors = self.manifest["selectors"]
        self.assertEqual(selectors["artifact_id"], "qwen36-27b-unsloth-q8-0-82d411a")
        self.assertEqual(selectors["quantization"], "Q8_0")
        self.assertEqual(selectors["tp"], 1)
        self.assertEqual(selectors["mtp"], 0)
        self.assertEqual(selectors["graph_mode"], "on")
        self.assertEqual(selectors["kv"], "q8_0")
        self.assertEqual(selectors["active_context_tokens"], RUNNER.DEPTHS)
        self.assertNotIn("f16", RUNNER.CAMPAIGN_ID)
        self.assertNotIn("f16", str(RUNNER.RUN_ROOT))

    def test_build_and_parent_fail_closed(self) -> None:
        with self.assertRaisesRegex(RUNNER.GateError, "build identity is unsealed"):
            RUNNER.require_sealed_build(self.manifest)
        value = copy.deepcopy(self.manifest)
        value["build_identity_status"] = "sealed"
        value["runtime"]["binary"].update(size_bytes=1, sha256="0" * 64)
        value["runtime"]["graph_backend"].update(size_bytes=1, sha256="1" * 64)
        value["runtime"]["effective_shared_libraries"] = [
            [f"libexample{index}.so", f"/tmp/libexample{index}.so", f"/tmp/libexample{index}.so", "2" * 64]
            for index in range(32)
        ]
        RUNNER.require_sealed_build(value)
        with self.assertRaisesRegex(RUNNER.GateError, "parent receipt identity is unsealed"):
            RUNNER.verify_parent(value)
        with self.assertRaisesRegex(RUNNER.GateError, "build identity is unsealed"):
            RUNNER.static_check()

    def test_graph_on_is_only_runtime_delta_from_accepted_q8_lane(self) -> None:
        accepted = RUNNER.Q8_OFF.load_manifest()["environment"]
        graph = self.manifest["environment"]
        changed = {name for name in set(accepted) | set(graph) if accepted.get(name) != graph.get(name)}
        self.assertEqual(changed, {"GGML_SYCL_ENABLE_GRAPH", "GGML_SYCL_GRAPH_CACHE_SIZE"})
        self.assertEqual(graph["GGML_SYCL_ENABLE_GRAPH"], "1")
        self.assertEqual(graph["GGML_SYCL_GRAPH_CACHE_SIZE"], "8")
        self.assertEqual(RUNNER.COMMON_ARGV[RUNNER.COMMON_ARGV.index("-ctk") + 1], "q8_0")
        self.assertEqual(RUNNER.COMMON_ARGV[RUNNER.COMMON_ARGV.index("-ctv") + 1], "q8_0")

    def test_each_depth_has_a_distinct_exact_argv(self) -> None:
        argvs = [RUNNER.cell_argv(depth) for depth in RUNNER.DEPTHS]
        self.assertEqual(len(set(argvs)), 7)
        for depth, argv in zip(RUNNER.DEPTHS, argvs, strict=True):
            self.assertEqual(argv[-2:], ("-d", str(depth)))
            self.assertEqual(Path(argv[0]), RUNNER.BINARY)
            self.assertNotIn("--spec-type", argv)

    def test_per_cell_graph_contract_is_strict(self) -> None:
        summary = (
            "[SYCL-GRAPH] summary device=0 requested=66 compatibility_rejected=0 "
            "device_unsupported=0 cache_entries=4 cache_limit=8 cache_hit=62 "
            "cache_miss=4 cache_full=0 direct_replay=62 recorded=4 created=4 "
            "updated=0 recreated=0 replayed=66"
        )
        parsed = RUNNER.parse_graph_summary(summary)
        self.assertEqual(parsed["replayed"], parsed["requested"])
        with self.assertRaises(RUNNER.GateError):
            RUNNER.parse_graph_summary(summary.replace("cache_full=0", "cache_full=1"))

    def test_publication_requires_q8_specific_quality_and_never_replaces_off(self) -> None:
        gate = self.manifest["q8_kv_publication_gate"]
        self.assertEqual(gate["status"], "pending-separate-parity-and-quality-receipt")
        self.assertTrue(gate["graph_off_on_exact_output_parity_required"])
        self.assertTrue(gate["q8_0_kv_quality_battery_required"])
        self.assertFalse(gate["site_publication_authority"])
        interpretation = self.manifest["interpretation"]
        self.assertTrue(interpretation["graph_estimates_forbidden"])
        self.assertTrue(interpretation["protected_graph_off_values_are_immutable"])
        self.assertTrue(interpretation["graph_on_cells_are_append_only"])
        self.assertFalse(interpretation["site_publication_authorized"])
        self.assertFalse(interpretation["quality_claim_authorized"])

    def test_graph_off_evidence_is_checksum_pinned(self) -> None:
        for key in ("manifest", "runner", "result", "result_note"):
            self.assertEqual(
                RUNNER.BASE.sha256_file(RUNNER.REPO / RUNNER.Q8_OFF_REFERENCE[key]),
                RUNNER.Q8_OFF_REFERENCE[f"{key}_sha256"],
            )

    def test_default_plan_is_inert_and_check_rejects_placeholders(self) -> None:
        result = subprocess.run([sys.executable, "-B", str(SCRIPT)], text=True, capture_output=True, check=True)
        plan = json.loads(result.stdout)
        self.assertTrue(plan["default_is_inert"])
        self.assertTrue(plan["graph_estimates_forbidden"])
        self.assertFalse(plan["site_publication_authorized"])
        self.assertFalse(plan["writes_performed"])
        check = subprocess.run([sys.executable, "-B", str(SCRIPT), "--check"], text=True, capture_output=True, check=False)
        self.assertEqual(check.returncode, 2)
        self.assertIn("build identity is unsealed", check.stderr)


if __name__ == "__main__":
    unittest.main()
