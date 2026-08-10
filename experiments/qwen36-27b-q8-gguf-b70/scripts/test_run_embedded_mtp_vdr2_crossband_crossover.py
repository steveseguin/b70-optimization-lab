#!/usr/bin/env python3
"""Offline source checks for the default-off cross-band crossover wrapper."""

from __future__ import annotations

import hashlib
import subprocess
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("run-embedded-mtp-vdr2-crossband-crossover.sh")
CAPTURE = Path(__file__).with_name("capture-exact-tokens.py")
METRIC_GATES = Path(__file__).with_name("embedded_mtp_vdr2_gates.py")
CROSSBAND_GATES = Path(__file__).with_name("embedded_mtp_crossband_gates.py")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CrossbandWrapperStaticTests(unittest.TestCase):
    def test_missing_ack_stops_before_external_commands(self) -> None:
        completed = subprocess.run(
            ["/bin/bash", str(SCRIPT)],
            cwd=Path("/"),
            env={"PATH": "/definitely-empty", "LC_ALL": "C"},
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(completed.stdout, "")
        self.assertIn("requires the exact acknowledgement", completed.stderr)

    def test_wrong_ack_stops_before_external_commands(self) -> None:
        completed = subprocess.run(
            ["/bin/bash", str(SCRIPT)],
            cwd=Path("/"),
            env={
                "PATH": "/definitely-empty",
                "LC_ALL": "C",
                "QWEN36_EMBEDDED_MTP_CROSSBAND_LIVE_ACK": "INTENTIONALLY_WRONG",
            },
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(completed.stdout, "")
        self.assertIn("requires the exact acknowledgement", completed.stderr)

    def test_offline_preflight_checks_only_pinned_local_inputs(self) -> None:
        completed = subprocess.run(
            ["/bin/bash", str(SCRIPT), "--offline-preflight"],
            cwd=Path("/"),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(
            completed.stdout,
            "offline embedded-MTP cross-band preflight: PASS\n",
        )

    def test_helpers_are_frozen_and_existing_sealed_helpers_are_unchanged(self) -> None:
        source = SCRIPT.read_text()
        expected = {
            CAPTURE: "94595b6962e64981723a063b6ec23b80c3701a22d0e256e85b596e6bf75f5b05",
            METRIC_GATES: "7af3cf19eee537a8381b4583b09649e6a616b375b72685b569c96f7094363a2b",
            CROSSBAND_GATES: "9154afc0ea874d26cc2028bad922921ca54d8a2b70f75341aff97990a3e9695b",
        }
        self.assertIn('LIVE_ENABLE_STATE="REVIEWED_AND_PINNED"', source)
        for path, digest in expected.items():
            with self.subTest(path=path.name):
                self.assertEqual(sha256(path), digest)
                self.assertIn(digest, source)

    def test_two_wave_split_crossover_is_literal_and_balanced(self) -> None:
        source = SCRIPT.read_text()
        launches = [
            "launch_arm 1 0 middle control 128",
            "launch_arm 1 1 middle mtp3 128",
            "launch_arm 1 2 near32k control 1024",
            "launch_arm 1 3 near32k mtp3 1024",
            "launch_arm 2 0 middle mtp3 128",
            "launch_arm 2 1 middle control 128",
            "launch_arm 2 2 near32k mtp3 1024",
            "launch_arm 2 3 near32k control 1024",
        ]
        positions = [source.index(launch) for launch in launches]
        self.assertEqual(positions, sorted(positions))
        self.assertLess(source.index("run_wave 1"), source.index("run_wave 2"))
        self.assertIn("setsid --wait env", source)
        self.assertIn('ready_count": 4', source)
        self.assertIn("for gpu in 0 1 2 3; do", source)
        self.assertIn('flock -n "$lease_fd"', source)

    def test_capture_is_forced_512_without_historical_oracle_or_canary(self) -> None:
        source = SCRIPT.read_text()
        start = source.index('python3 "$CAPTURE"')
        end = source.index('python3 "$METRIC_GATES" gate-metrics', start)
        capture_call = source[start:end]
        for required in (
            '--band "$band"',
            "--max-tokens 512",
            "--ignore-eos",
            "--require-exact-token-count",
            "--require-full-512-metric",
            "--slot-id 0",
            "--seed 1",
        ):
            self.assertIn(required, capture_call)
        for forbidden in (
            "--oracle-json",
            "--prefix-oracle-json",
            "--require-post-512-canary",
            "--post-512-canary",
            "--spec-draft-model",
        ):
            self.assertNotIn(forbidden, capture_call)
        self.assertLess(source.index("ready_count == 4"), start)

    def test_fail_closed_evidence_and_cleanup_joins_are_present(self) -> None:
        source = SCRIPT.read_text()
        for required in (
            '"prompt_counter_exact"',
            '"predicted_counter_exact"',
            '"full_token_ids_exact"',
            '"full_content_exact"',
            '"same-card-integrated-model-control-v1"',
            '"VALID_CROSSBAND_NO_MTP_WIN"',
            '"INVALID_CROSSBAND_EVIDENCE"',
        ):
            self.assertIn(required, CROSSBAND_GATES.read_text())
        for required in (
            "forced_kill=$forced",
            "cleanup_survivor=$survivor",
            "port_closed=$port_closed",
            "vram_returned=$vram_returned",
            'kill -TERM -- "-$pid"',
            '"performance_promotable": False',
            '"localmaxxing_submission_ready": False',
        ):
            self.assertIn(required, source)


if __name__ == "__main__":
    unittest.main()
