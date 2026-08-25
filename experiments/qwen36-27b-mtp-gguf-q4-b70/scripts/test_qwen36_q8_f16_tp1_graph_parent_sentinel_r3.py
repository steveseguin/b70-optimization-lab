#!/usr/bin/env python3
"""CPU-only tests for the Qwen3.6 Q8 graph parent sentinel R3 delta."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


SCRIPT = Path(__file__).with_name(
    "run-20260825-qwen36-q8-f16-tp1-graph-parent-sentinel-r3.py"
)
SPEC = importlib.util.spec_from_file_location("qwen36_graph_parent_sentinel_r3", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import {SCRIPT}")
RUNNER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = RUNNER
SPEC.loader.exec_module(RUNNER)
BASE = RUNNER.BASE


def summary(**overrides: int) -> str:
    values = {
        "device": 0, "requested": 0, "compatibility_rejected": 0,
        "device_unsupported": 0, "cache_entries": 0, "cache_limit": 0,
        "cache_hit": 0, "cache_miss": 0, "cache_full": 0,
        "direct_replay": 0, "recorded": 0, "created": 0, "updated": 0,
        "recreated": 0, "replayed": 0,
    }
    values.update(overrides)
    return (
        "[SYCL-GRAPH] summary device={device} requested={requested} "
        "compatibility_rejected={compatibility_rejected} device_unsupported={device_unsupported} "
        "cache_entries={cache_entries} cache_limit={cache_limit} cache_hit={cache_hit} "
        "cache_miss={cache_miss} cache_full={cache_full} direct_replay={direct_replay} "
        "recorded={recorded} created={created} updated={updated} recreated={recreated} "
        "replayed={replayed}\n"
    ).format(**values)


class GraphParentSentinelR3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest, cls.libraries = BASE.static_check()

    def test_fresh_identity_and_unchanged_candidate_gate(self) -> None:
        self.assertEqual(BASE.CAMPAIGN_ID, RUNNER.R3_CAMPAIGN_ID)
        self.assertEqual(BASE.RUN_ROOT, RUNNER.R3_RUN_ROOT)
        self.assertEqual(BASE.ACK, RUNNER.R3_ACK)
        self.assertEqual(self.manifest["r3_delta"]["candidate_gate_delta"], "none")
        self.assertFalse(self.manifest["r3_delta"]["predecessor"]["reuse_any_arm"])

    def test_exact_all_zero_summary_is_sufficient_control_authority(self) -> None:
        parsed = RUNNER.validate_control_graph_log(summary())
        self.assertEqual(parsed["device"], 0)
        self.assertEqual(parsed["requested"], 0)
        with self.assertRaisesRegex(BASE.GateError, "executed graph work"):
            RUNNER.validate_control_graph_log(summary(cache_hit=1))
        with self.assertRaisesRegex(BASE.GateError, "wrong device"):
            RUNNER.validate_control_graph_log(summary(device=1))

    def test_missing_duplicate_or_action_marker_fails(self) -> None:
        with self.assertRaisesRegex(BASE.GateError, "exactly one"):
            RUNNER.validate_control_graph_log("")
        with self.assertRaisesRegex(BASE.GateError, "exactly one"):
            RUNNER.validate_control_graph_log(summary() + summary())
        with self.assertRaisesRegex(BASE.GateError, "graph-action markers"):
            RUNNER.validate_control_graph_log("[SYCL-GRAPH] requested device=0 count=1\n" + summary())

    def test_r2_lifecycle_repairs_and_zero_authority_remain(self) -> None:
        argv = tuple(self.manifest["canary"]["common_argv"])
        self.assertIn("--single-turn", argv)
        self.assertIn("--no-show-timings", argv)
        self.assertEqual(argv[argv.index("--log-verbosity") + 1], "4")
        self.assertEqual(self.manifest["lifecycle"]["child_stdin"], "/dev/null")
        interpretation = self.manifest["interpretation"]
        self.assertFalse(interpretation["seven_cell_expansion_authorized"])
        self.assertFalse(interpretation["site_publication_authorized"])
        self.assertIsNone(interpretation["speed_measurement_or_floor"])
        self.assertEqual(len(self.libraries), 34)
        self.assertEqual(len(BASE.PACKET_PATHS), 14)


if __name__ == "__main__":
    unittest.main()
