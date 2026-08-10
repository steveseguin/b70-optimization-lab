#!/usr/bin/env python3
"""Offline source/latch checks for the four-service live wrapper."""

from __future__ import annotations

import subprocess
import hashlib
import re
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("run-embedded-mtp-four-service-realistic.sh")


class FourServiceWrapperTests(unittest.TestCase):
    def test_pending_path_stops_before_any_external_command(self) -> None:
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

    def test_explicit_empty_argument_cannot_bypass_live_latch(self) -> None:
        completed = subprocess.run(
            ["/bin/bash", str(SCRIPT), ""],
            cwd=Path("/"),
            env={"PATH": "/definitely-empty", "LC_ALL": "C"},
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(completed.stdout, "")
        self.assertIn("explicit empty arguments are invalid", completed.stderr)

    def test_live_state_and_identity_are_fixed(self) -> None:
        source = SCRIPT.read_text()
        self.assertIn('LIVE_ENABLE_STATE="PENDING"', source)
        self.assertNotIn("--spec-draft-model", source)
        self.assertIn("-c 32768", source)
        self.assertIn("-np 1", source)
        self.assertIn("--spec-draft-n-max 3", source)
        self.assertIn("--spec-draft-n-min 0", source)
        self.assertIn("-lv 4", source)
        self.assertNotIn("--verbose", source)
        self.assertIn("MIN_LOADED_DELTA_MIB=29000", source)
        self.assertIn("MAX_LOADED_MIB=31500", source)
        self.assertIn("aggregate_retention_floor=0.95", source)
        self.assertIn("service_retention_floor=0.90", source)
        self.assertIn("service_fairness_floor=0.90", source)
        self.assertIn("prompt_d99_retention_floor=0.80", source)
        self.assertIn("for wave in 0 1 2; do", source)
        self.assertIn("CAPTURE_DEADLINE=$((SECONDS + CAPTURE_TIMEOUT_S))", source)
        self.assertIn('while pid_running "$CAPTURE_PID"; do', source)
        self.assertIn('setsid python3 "$CAPTURE" run', source)
        self.assertIn('kill -TERM -- "-${CAPTURE_PGID:-$CAPTURE_PID}"', source)
        self.assertIn("capture_deadline=$((SECONDS + CAPTURE_TERM_GRACE_S))", source)
        self.assertGreaterEqual(source.count('--max-time "$CURL_REQUEST_TIMEOUT_S"'), 3)

    def test_startup_and_xpu_stats_are_serialized_without_serializing_capture(
        self,
    ) -> None:
        source = SCRIPT.read_text()
        launch_start = source.index('  env ZE_AFFINITY_MASK="$gpu" "${server_cmd[@]}"')
        readiness = source.index("  SERVICE_READINESS_DEADLINE=", launch_start)
        readiness_loop = source.index("  until curl --noproxy '*'", readiness)
        next_phase = source.index(
            '\nfor gpu in 0 1 2 3; do\n  python3 "$SERVER_GATES" gate-server',
            readiness_loop,
        )
        launch_section = source[launch_start:next_phase]
        self.assertIn("SERVER_PIDS[$gpu]=$!", launch_section)
        self.assertIn('pid_running "${SERVER_PIDS[$gpu]}"', launch_section)
        self.assertIn("SECONDS < SERVICE_READINESS_DEADLINE", launch_section)
        self.assertNotIn(
            "READINESS_DEADLINE=", source.replace("SERVICE_READINESS_DEADLINE=", "")
        )
        self.assertIn(
            'XPU_SMI_LOCK="/run/user/$(id -u)/qwen36-b70-xpu-smi-stats.lock"',
            source,
        )
        self.assertEqual(source.count("xpu-smi stats"), 1)
        self.assertIn('flock -w 45 "$XPU_SMI_LOCK" timeout 20 xpu-smi stats', source)
        self.assertGreater(source.index('setsid python3 "$CAPTURE" run'), next_phase)

    def test_fault_scans_preserve_status_and_fail_closed(self) -> None:
        source = SCRIPT.read_text()
        scan_start = source.index("scan_errors() {\n")
        scan_end = source.index("\n}\n\nseal_artifacts()", scan_start)
        scan = source[scan_start:scan_end]
        self.assertNotIn("|| true", scan)
        self.assertIn('> "$RUN_DIR/kernel-journal.stderr.txt"', scan)
        self.assertIn('> "$RUN_DIR/device-error-scan.stderr.txt"', scan)
        self.assertIn('> "$RUN_DIR/server-log-find.stderr.txt"', scan)
        self.assertIn('> "$RUN_DIR/server-error-scan.stderr.txt"', scan)
        self.assertIn("journal_rc == 0 && device_grep_rc == 1", scan)
        self.assertIn("find_rc == 0 && server_grep_rc == 1", scan)
        self.assertIn('schema:"qwen36-four-service-error-scan-v1"', scan)
        self.assertIn("ERROR_SCAN_PASSED=1", scan)
        self.assertIn("(( ERROR_SCAN_PASSED == 1 )) || final_status=1", source)

    def test_sealed_single_service_harness_is_not_called(self) -> None:
        source = SCRIPT.read_text()
        self.assertNotIn("run-embedded-mtp-vdr2-realistic.sh", source)
        self.assertNotIn("embedded_mtp_realistic_gates.py", source)
        self.assertIn("capture-embedded-mtp-four-service-realistic.py", source)
        self.assertIn("embedded_mtp_four_service_realistic_gates.py", source)

    def test_helper_hashes_are_frozen_but_live_latch_is_pending(self) -> None:
        source = SCRIPT.read_text()
        capture = SCRIPT.with_name("capture-embedded-mtp-four-service-realistic.py")
        gates = SCRIPT.with_name("embedded_mtp_four_service_realistic_gates.py")
        expected_capture = re.search(
            r'^EXPECTED_CAPTURE_SHA256="([0-9a-f]{64})"$', source, re.MULTILINE
        )
        expected_gates = re.search(
            r'^EXPECTED_SCALE_GATES_SHA256="([0-9a-f]{64})"$', source, re.MULTILINE
        )
        self.assertIsNotNone(expected_capture)
        self.assertIsNotNone(expected_gates)
        assert expected_capture is not None and expected_gates is not None
        self.assertEqual(
            expected_capture.group(1), hashlib.sha256(capture.read_bytes()).hexdigest()
        )
        self.assertEqual(
            expected_gates.group(1), hashlib.sha256(gates.read_bytes()).hexdigest()
        )
        self.assertIn('LIVE_ENABLE_STATE="PENDING"', source)


if __name__ == "__main__":
    unittest.main()
