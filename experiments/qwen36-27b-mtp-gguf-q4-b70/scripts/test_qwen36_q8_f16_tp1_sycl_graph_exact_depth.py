#!/usr/bin/env python3
"""CPU-only fail-closed tests for the unsealed Q8/F16 SYCL-graph curve."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest


SCRIPT = Path(__file__).with_name(
    "run-20260825-qwen36-q8-f16-tp1-sycl-graph-exact-depth-r1.py"
)
SPEC = importlib.util.spec_from_file_location("qwen36_q8_f16_sycl_graph_curve", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import {SCRIPT}")
RUNNER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = RUNNER
SPEC.loader.exec_module(RUNNER)


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = RUNNER.load_manifest()
        RUNNER.validate_manifest(cls.manifest)

    def test_exact_seven_cell_identity(self) -> None:
        selectors = self.manifest["selectors"]
        self.assertEqual(selectors["artifact_id"], "qwen36-27b-unsloth-q8-0-82d411a")
        self.assertEqual(selectors["tp"], 1)
        self.assertEqual(selectors["mtp"], 0)
        self.assertEqual(selectors["graph_mode"], "SYCL")
        self.assertEqual(selectors["kv"], "f16")
        self.assertEqual(selectors["active_context_tokens"], RUNNER.DEPTHS)

    def test_target_only_graph_arguments(self) -> None:
        template = self.manifest["argv_template"]
        self.assertEqual(template.count("{active_context_tokens}"), 1)
        self.assertEqual(template[template.index("-ctk") + 1], "f16")
        self.assertEqual(template[template.index("-ctv") + 1], "f16")
        self.assertNotIn("--spec-type", template)
        for depth in RUNNER.DEPTHS:
            argv = RUNNER.argv_for_depth(self.manifest, depth)
            self.assertNotIn("{active_context_tokens}", argv)
            self.assertEqual(argv[argv.index("-d") + 1], str(depth))

    def test_every_context_requires_positive_graph_evidence(self) -> None:
        graph = self.manifest["graph_evidence"]
        self.assertEqual(graph["required_for_every_context"], RUNNER.DEPTHS)
        self.assertTrue(graph["graph_estimates_forbidden"])
        required = graph["per_context_requirements"]
        for key in (
            "requested_positive", "recorded_positive", "created_positive",
            "cache_hit_positive", "direct_replay_positive", "replayed_positive",
            "replayed_equals_requested",
        ):
            self.assertTrue(required[key])
        for key in ("compatibility_rejected", "device_unsupported", "cache_full"):
            self.assertEqual(required[key], 0)

    def test_graph_summary_validator_is_strict(self) -> None:
        good = (
            "[SYCL-GRAPH] summary device=0 requested=66 compatibility_rejected=0 "
            "device_unsupported=0 cache_entries=4 cache_limit=8 cache_hit=62 "
            "cache_miss=4 cache_full=0 direct_replay=62 recorded=4 created=4 "
            "updated=0 recreated=0 replayed=66"
        )
        self.assertEqual(RUNNER.parse_graph_summary(good)["replayed"], 66)
        with self.assertRaisesRegex(RUNNER.GateError, "per-context"):
            RUNNER.parse_graph_summary(good.replace("direct_replay=62", "direct_replay=0"))
        with self.assertRaisesRegex(RUNNER.GateError, "exactly one"):
            RUNNER.parse_graph_summary("")

    def test_unsealed_placeholders_are_mandatory_blockers(self) -> None:
        self.assertNotEqual(self.manifest["sealing_status"], "sealed")
        with self.assertRaisesRegex(RUNNER.GateError, "packet is unsealed"):
            RUNNER.require_sealed_dependencies(self.manifest)
        runtime = self.manifest["runtime"]
        self.assertLess(runtime["binary"]["size_bytes"], 0)
        self.assertTrue(runtime["binary"]["sha256"].startswith(RUNNER.PLACEHOLDER_PREFIX))
        self.assertTrue(runtime["graph_backend"]["sha256"].startswith(RUNNER.PLACEHOLDER_PREFIX))
        self.assertEqual(runtime["effective_shared_libraries"], [])
        for key in ("result", "terminal_receipt", "parity_receipt"):
            self.assertTrue(
                self.manifest["parent_sentinel"][key]["sha256"].startswith(
                    RUNNER.PLACEHOLDER_PREFIX
                )
            )

    def test_default_is_inert_and_check_fails_closed(self) -> None:
        output = Path(self.manifest["lifecycle"]["output_root"])
        self.assertFalse(output.exists())
        plan = subprocess.run(
            [sys.executable, "-B", str(SCRIPT)], check=True, text=True, capture_output=True
        )
        payload = json.loads(plan.stdout)
        self.assertTrue(payload["default_is_inert"])
        self.assertFalse(payload["site_publication_authorized"])
        self.assertTrue(payload["graph_evidence_required_per_cell"])
        check = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), "--check"],
            check=False, text=True, capture_output=True,
        )
        self.assertEqual(check.returncode, 2)
        self.assertIn("packet is unsealed", check.stderr)
        self.assertFalse(output.exists())

    def test_execute_cannot_bypass_ack_or_sealing(self) -> None:
        output = Path(self.manifest["lifecycle"]["output_root"])
        missing_ack = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), "--execute"],
            check=False, text=True, capture_output=True,
        )
        self.assertEqual(missing_ack.returncode, 2)
        self.assertIn("exact acknowledgement required", missing_ack.stderr)
        unsealed = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), "--execute", "--ack", RUNNER.ACK],
            check=False, text=True, capture_output=True,
        )
        self.assertEqual(unsealed.returncode, 2)
        self.assertIn("packet is unsealed", unsealed.stderr)
        self.assertFalse(output.exists())

    def test_claim_boundaries_and_protected_graph_off_series(self) -> None:
        interpretation = self.manifest["interpretation"]
        self.assertFalse(interpretation["site_publication_authorized"])
        self.assertFalse(interpretation["record_or_submission_authorized"])
        self.assertFalse(interpretation["quality_claim_authorized"])
        self.assertTrue(interpretation["quality_gate_required_before_publication"])
        self.assertTrue(interpretation["graph_estimates_forbidden"])
        self.assertEqual(
            interpretation["protected_graph_off_measurement_id"],
            "q36-unsloth-q8-tp1-kv-f16-context",
        )
        self.assertTrue(interpretation["protected_graph_off_values_must_not_be_replaced"])
        self.assertTrue(interpretation["historical_featured_speeds_are_immutable"])

    def test_parent_sentinel_paths_do_not_overlap_this_packet(self) -> None:
        current_paths = {RUNNER.MANIFEST.resolve(), SCRIPT.resolve(), Path(__file__).resolve()}
        for key in ("preregistration", "runner", "result", "terminal_receipt", "parity_receipt"):
            value = self.manifest["parent_sentinel"][key]["path"]
            path = RUNNER._resolve(value).resolve()
            self.assertNotIn(path, current_paths)

    def test_missing_context_is_not_a_seven_cell_packet(self) -> None:
        mutated = copy.deepcopy(self.manifest)
        mutated["selectors"]["active_context_tokens"] = RUNNER.DEPTHS[:-1]
        with self.assertRaisesRegex(RUNNER.GateError, "invariant"):
            RUNNER.validate_manifest(mutated)


if __name__ == "__main__":
    unittest.main()
