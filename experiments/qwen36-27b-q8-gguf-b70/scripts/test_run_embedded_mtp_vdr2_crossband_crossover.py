#!/usr/bin/env python3
"""Offline source checks for the default-off cross-band crossover wrapper."""

from __future__ import annotations

import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("run-embedded-mtp-vdr2-crossband-crossover.sh")
CAPTURE = Path(__file__).with_name("capture-exact-tokens.py")
METRIC_GATES = Path(__file__).with_name("embedded_mtp_vdr2_gates.py")
CROSSBAND_GATES = Path(__file__).with_name("embedded_mtp_crossband_gates.py")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CrossbandWrapperStaticTests(unittest.TestCase):
    def test_pending_live_path_stops_before_external_commands(self) -> None:
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
        self.assertIn("PENDING independent review", completed.stderr)

    def test_wrong_ack_stops_before_external_commands_after_activation(self) -> None:
        activated = SCRIPT.read_text().replace(
            'LIVE_ENABLE_STATE="PENDING"',
            'LIVE_ENABLE_STATE="REVIEWED_AND_PINNED"',
            1,
        )
        with tempfile.TemporaryDirectory() as temporary:
            probe = Path(temporary) / "runner.sh"
            probe.write_text(activated, encoding="utf-8")
            completed = subprocess.run(
                ["/bin/bash", str(probe)],
                cwd=Path("/"),
                env={"PATH": "/definitely-empty", "LC_ALL": "C"},
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
        self.assertIn('LIVE_ENABLE_STATE="PENDING"', source)
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

    def test_startup_and_residency_are_serialized_and_child_cleanup_is_stable(self) -> None:
        source = SCRIPT.read_text()
        pairs = (
            ("launch_arm 1 0 middle control 128", "wait_arm_ready 1 0 middle control"),
            ("launch_arm 1 1 middle mtp3 128", "wait_arm_ready 1 1 middle mtp3"),
            ("launch_arm 1 2 near32k control 1024", "wait_arm_ready 1 2 near32k control"),
            ("launch_arm 1 3 near32k mtp3 1024", "wait_arm_ready 1 3 near32k mtp3"),
            ("launch_arm 2 0 middle mtp3 128", "wait_arm_ready 2 0 middle mtp3"),
            ("launch_arm 2 1 middle control 128", "wait_arm_ready 2 1 middle control"),
            ("launch_arm 2 2 near32k mtp3 1024", "wait_arm_ready 2 2 near32k mtp3"),
            ("launch_arm 2 3 near32k control 1024", "wait_arm_ready 2 3 near32k control"),
        )
        for index, (launch, ready) in enumerate(pairs):
            with self.subTest(launch=launch):
                launch_at = source.index(launch)
                ready_at = source.index(ready)
                self.assertLess(launch_at, ready_at)
                if index + 1 < len(pairs) and index not in (3,):
                    self.assertLess(ready_at, source.index(pairs[index + 1][0]))
        self.assertIn('flock -w 45 "$XPU_SMI_LOCK" timeout 20 xpu-smi stats', source)
        self.assertIn('flock -w 45 "$XPU_SMI_LOCK" timeout 30 xpu-smi discovery', source)
        self.assertIn("CHILD_FINALIZING=0", source)
        self.assertIn('CHILD_SERVER_PID=""', source)
        self.assertIn("CHILD_CLEANUP_CONCLUSIVE=1", source)
        self.assertIn("FAIL_UNSEALED_ACTIVE_SERVER", source)
        self.assertNotIn("local child_finalizing=0", source)
        self.assertIn('printf \'%s\\n\' "$server_starttime" > "$arm_dir/server.starttime"', source)
        self.assertIn("recorded_server_identity_matches", source)
        self.assertIn("cleanup_recorded_servers", source)
        self.assertIn("process_group_is_live", source)
        self.assertIn('kill -TERM -- "-$pid"', source)
        self.assertIn('kill -KILL -- "-$pid"', source)
        self.assertIn("wait_for_all_ports_closed", source)
        self.assertIn("FAIL_UNSEALED_ACTIVE_OR_UNVERIFIED_SERVER", source)
        run_wave = source[source.index("run_wave() {") : source.index("run_wave 1")]
        group_check = run_wave.rindex('if process_group_is_live "$pid"; then failed=1; fi')
        failed_guard = run_wave.rindex("(( failed == 0 )) || return 1")
        clear = run_wave.rindex("ACTIVE_CHILD_PIDS=()")
        self.assertLess(group_check, failed_guard)
        self.assertLess(failed_guard, clear)
        finalize = source[source.index("finalize() {") : source.index("trap finalize EXIT")]
        late_port_check = finalize.index('if port_is_listening "$port"; then')
        cleanup_guard = finalize.index("if (( cleanup_conclusive == 0 )); then")
        self.assertIn(
            "cleanup_conclusive=0",
            finalize[late_port_check:cleanup_guard],
        )

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
