#!/usr/bin/env python3
"""CPU-only tests for the Qwen3.6 Q8 graph parent sentinel R4 delta."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


SCRIPT = Path(__file__).with_name(
    "run-20260825-qwen36-q8-f16-tp1-graph-parent-sentinel-r4.py"
)
SPEC = importlib.util.spec_from_file_location("qwen36_graph_parent_sentinel_r4", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import {SCRIPT}")
RUNNER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = RUNNER
SPEC.loader.exec_module(RUNNER)
BASE = RUNNER.BASE


def candidate_log(**overrides: int) -> str:
    values = {
        "device": 0, "requested": 66, "compatibility_rejected": 0,
        "device_unsupported": 0, "cache_entries": 4, "cache_limit": 8,
        "cache_hit": 62, "cache_miss": 4, "cache_full": 0,
        "direct_replay": 62, "recorded": 4, "created": 4, "updated": 0,
        "recreated": 0, "replayed": 66,
    }
    values.update(overrides)
    return (
        "[SYCL-GRAPH] requested device=0 count=1\n"
        "[SYCL-GRAPH] recording_entered device=0 count=1\n"
        "[SYCL-GRAPH] replayed device=0 count=1 recorded=1 created=1 updated=0 recreated=0\n"
        "[SYCL-GRAPH] direct_replay device=0 count=1 cache_entries=4\n"
        "[SYCL-GRAPH] summary device={device} requested={requested} "
        "compatibility_rejected={compatibility_rejected} device_unsupported={device_unsupported} "
        "cache_entries={cache_entries} cache_limit={cache_limit} cache_hit={cache_hit} "
        "cache_miss={cache_miss} cache_full={cache_full} direct_replay={direct_replay} "
        "recorded={recorded} created={created} updated={updated} recreated={recreated} "
        "replayed={replayed}\n"
    ).format(**values)


class GraphParentSentinelR4Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest, cls.libraries = BASE.static_check()

    def test_fresh_identity_and_only_candidate_string_delta(self) -> None:
        self.assertEqual(BASE.CAMPAIGN_ID, RUNNER.R4_CAMPAIGN_ID)
        self.assertEqual(BASE.RUN_ROOT, RUNNER.R4_RUN_ROOT)
        self.assertEqual(BASE.ACK, RUNNER.R4_ACK)
        delta = self.manifest["r4_delta"]
        self.assertEqual(delta["control_gate_delta"], "none-from-r3")
        self.assertFalse(delta["predecessor"]["reuse_any_arm"])

    def test_actual_candidate_shape_passes_without_unavailable_strings(self) -> None:
        parsed = RUNNER.validate_candidate_graph_log(candidate_log())
        self.assertEqual(parsed["cache_limit"], 8)
        self.assertEqual(parsed["cache_hit"], 62)
        with self.assertRaisesRegex(BASE.GateError, "compatibility rejection"):
            RUNNER.validate_candidate_graph_log(candidate_log(compatibility_rejected=1))
        with self.assertRaisesRegex(BASE.GateError, "record/replay/cache-hit"):
            RUNNER.validate_candidate_graph_log(candidate_log(cache_hit=0))

    def test_lifecycle_parity_and_zero_authority_remain(self) -> None:
        argv = tuple(self.manifest["canary"]["common_argv"])
        self.assertIn("--single-turn", argv)
        self.assertIn("--no-show-timings", argv)
        self.assertEqual(self.manifest["lifecycle"]["child_stdin"], "/dev/null")
        interpretation = self.manifest["interpretation"]
        self.assertFalse(interpretation["seven_cell_expansion_authorized"])
        self.assertFalse(interpretation["site_publication_authorized"])
        self.assertIsNone(interpretation["speed_measurement_or_floor"])
        self.assertEqual(len(self.libraries), 34)
        self.assertEqual(len(BASE.PACKET_PATHS), 20)


if __name__ == "__main__":
    unittest.main()
