#!/usr/bin/env python3
"""CPU-only tests for the Qwen3.6 Q8 graph parent sentinel R2 delta."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).with_name(
    "run-20260825-qwen36-q8-f16-tp1-graph-parent-sentinel-r2.py"
)
SPEC = importlib.util.spec_from_file_location("qwen36_graph_parent_sentinel_r2", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import {SCRIPT}")
RUNNER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = RUNNER
SPEC.loader.exec_module(RUNNER)
BASE = RUNNER.BASE


class GraphParentSentinelR2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest, cls.libraries = BASE.static_check()

    def test_fresh_identity_and_r1_quarantine(self) -> None:
        self.assertEqual(BASE.CAMPAIGN_ID, RUNNER.R2_CAMPAIGN_ID)
        self.assertEqual(BASE.RUN_ROOT, RUNNER.R2_RUN_ROOT)
        self.assertEqual(BASE.ACK, RUNNER.R2_ACK)
        predecessor = self.manifest["r2_delta"]["predecessor"]
        self.assertFalse(predecessor["reuse_any_arm"])
        self.assertEqual(
            predecessor["terminal_sha256"],
            "dfe5befea05b65df0271e3b00c0ba69f2fa847e4330b41b2eba5c1e1651f70c8",
        )

    def test_lifecycle_and_observability_flags_are_exact(self) -> None:
        argv = tuple(self.manifest["canary"]["common_argv"])
        self.assertEqual(argv, BASE.COMMON_ARGV)
        self.assertEqual(argv.count("--single-turn"), 1)
        self.assertEqual(argv.count("--no-show-timings"), 1)
        index = argv.index("--log-verbosity")
        self.assertEqual(argv[index + 1], "4")
        lifecycle = self.manifest["lifecycle"]
        self.assertEqual(lifecycle["child_stdin"], "/dev/null")
        self.assertTrue(lifecycle["single_turn_required"])
        self.assertTrue(lifecycle["ui_timings_disabled"])
        self.assertEqual(lifecycle["graph_log_verbosity"], 4)

    def test_process_stdin_is_devnull_and_eof_is_immediate(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            receipt = RUNNER.run_process_group(
                name="stdin-eof-fixture",
                argv=["/bin/sh", "-c", "if read value; then exit 9; else echo eof; fi"],
                environment={"PATH": "/usr/bin:/bin"},
                stdout_path=root / "stdout",
                stderr_path=root / "stderr",
                timeout_seconds=2,
            )
            self.assertEqual((root / "stdout").read_text(), "eof\n")
            self.assertEqual(receipt["stdin"], "/dev/null")
            self.assertFalse(receipt["timed_out"])

    def test_parent_only_authority_and_full_dependency_seal(self) -> None:
        interpretation = self.manifest["interpretation"]
        self.assertFalse(interpretation["seven_cell_expansion_authorized"])
        self.assertFalse(interpretation["site_publication_authorized"])
        self.assertFalse(interpretation["record_or_submission_authorized"])
        self.assertIsNone(interpretation["speed_measurement_or_floor"])
        self.assertEqual(len(self.libraries), 34)
        self.assertEqual(len(BASE.PACKET_PATHS), 8)


if __name__ == "__main__":
    unittest.main()
