#!/usr/bin/env python3
"""CPU-only tests for the Qwen3.6 Q8 graph parent sentinel R5 delta."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


SCRIPT = Path(__file__).with_name(
    "run-20260825-qwen36-q8-f16-tp1-graph-parent-sentinel-r5.py"
)
SPEC = importlib.util.spec_from_file_location("qwen36_graph_parent_sentinel_r5", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import {SCRIPT}")
RUNNER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = RUNNER
SPEC.loader.exec_module(RUNNER)
BASE = RUNNER.BASE


class GraphParentSentinelR5Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest, cls.libraries = BASE.static_check()

    def test_fresh_identity_and_no_graph_or_parity_delta(self) -> None:
        self.assertEqual(BASE.CAMPAIGN_ID, RUNNER.R5_CAMPAIGN_ID)
        self.assertEqual(BASE.RUN_ROOT, RUNNER.R5_RUN_ROOT)
        self.assertEqual(BASE.ACK, RUNNER.R5_ACK)
        self.assertEqual(self.manifest["r5_delta"]["graph_and_parity_delta"], "none-from-r4")
        self.assertFalse(self.manifest["r5_delta"]["predecessor"]["reuse_any_arm"])

    def test_remote_policy_is_prelaunch_only(self) -> None:
        policy = self.manifest["r5_delta"]["postflight_remote_policy"]
        self.assertTrue(policy["live_origin_equality_required_prelaunch"])
        self.assertTrue(policy["local_launch_head_and_packet_blobs_frozen_postlaunch"])
        self.assertFalse(policy["live_origin_equality_required_postlaunch"])
        self.assertIsNot(RUNNER.ORIGINAL_VERIFY, RUNNER.verify_clean_pushed_main)

    def test_all_lifecycle_and_zero_authority_gates_remain(self) -> None:
        self.assertEqual(len(self.libraries), 34)
        self.assertEqual(len(BASE.PACKET_PATHS), 26)
        self.assertEqual(self.manifest["lifecycle"]["child_stdin"], "/dev/null")
        interpretation = self.manifest["interpretation"]
        self.assertFalse(interpretation["seven_cell_expansion_authorized"])
        self.assertFalse(interpretation["site_publication_authorized"])
        self.assertIsNone(interpretation["speed_measurement_or_floor"])


if __name__ == "__main__":
    unittest.main()
