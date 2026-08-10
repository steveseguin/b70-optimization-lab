#!/usr/bin/env python3
"""Offline source/latch checks for the four-service live wrapper."""

from __future__ import annotations

import subprocess
import hashlib
import re
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("run-embedded-mtp-four-service-realistic.sh")


def run_fake_xpu_probe(
    script: Path,
) -> tuple[subprocess.CompletedProcess[str], str, str, str]:
    """Execute the runner's exact telemetry fragments against a fake xpu-smi."""
    source = script.read_text(encoding="utf-8")
    function_start = source.index("gpu_used_mib() {\n")
    function_end = source.index("\n}\n", function_start) + len("\n}\n")
    gpu_used_mib = source[function_start:function_end]
    discovery_start = source.index(
        'flock -w 45 "$XPU_SMI_LOCK" timeout 30 \\\n'
    )
    discovery_end = source.index(
        '> "$RUN_DIR/xpu-smi-discovery.json"', discovery_start
    ) + len('> "$RUN_DIR/xpu-smi-discovery.json"')
    discovery = source[discovery_start:discovery_end]

    with tempfile.TemporaryDirectory() as temporary:
        temporary_path = Path(temporary)
        fake_log = temporary_path / "fake-xpu.log"
        fake_xpu = temporary_path / "xpu-smi"
        fake_xpu.write_text(
            """#!/bin/sh
set -eu
test "${ZE_AFFINITY_MASK+x}" != x
test "${ONEAPI_DEVICE_SELECTOR+x}" != x
test "${SYCL_DEVICE_FILTER+x}" != x
test "${UR_DEVICE_AFFINITY_MASK+x}" != x
test "${ZES_ENABLE_SYSMAN:-}" = 1
printf '%s\n' "$*" >> "$FAKE_XPU_LOG"
case "${1:-}" in
  stats) printf '%s\n' '| GPU Memory Used | 43 MiB |' ;;
  discovery) printf '%s\n' '{"device_list":[]}' ;;
  *) exit 96 ;;
esac
""",
            encoding="utf-8",
        )
        fake_xpu.chmod(0o755)
        probe = f"""set -euo pipefail
XPU_SMI_LOCK="$1/xpu-smi.lock"
RUN_DIR="$1"
{gpu_used_mib}
export ZE_AFFINITY_MASK=masked-ze
export ONEAPI_DEVICE_SELECTOR=masked-oneapi
export SYCL_DEVICE_FILTER=masked-sycl
export UR_DEVICE_AFFINITY_MASK=masked-ur
export ZES_ENABLE_SYSMAN=parent-zes
gpu_used_mib 2 "$RUN_DIR/xpu-smi-stats.txt"
{discovery}
printf '%s|%s|%s|%s|%s\n' \
  "$ZE_AFFINITY_MASK" "$ONEAPI_DEVICE_SELECTOR" "$SYCL_DEVICE_FILTER" \
  "$UR_DEVICE_AFFINITY_MASK" "$ZES_ENABLE_SYSMAN"
"""
        completed = subprocess.run(
            ["/bin/bash", "-c", probe, "fake-xpu-probe", temporary],
            env={
                "FAKE_XPU_LOG": str(fake_log),
                "LC_ALL": "C",
                "PATH": f"{temporary}:/usr/bin:/bin",
            },
            text=True,
            capture_output=True,
            check=False,
        )
        fake_log_text = fake_log.read_text(encoding="utf-8") if fake_log.exists() else ""
        stats_text = (temporary_path / "xpu-smi-stats.txt").read_text(encoding="utf-8")
        discovery_text = (temporary_path / "xpu-smi-discovery.json").read_text(
            encoding="utf-8"
        )
    return completed, fake_log_text, stats_text, discovery_text


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
        self.assertEqual(source.count("xpu-smi discovery"), 1)
        self.assertIn('flock -w 45 "$XPU_SMI_LOCK" timeout 20 \\', source)
        self.assertIn('flock -w 45 "$XPU_SMI_LOCK" timeout 30 \\', source)
        for selector in (
            "ZE_AFFINITY_MASK",
            "ONEAPI_DEVICE_SELECTOR",
            "SYCL_DEVICE_FILTER",
            "UR_DEVICE_AFFINITY_MASK",
        ):
            self.assertEqual(source.count(f"-u {selector}"), 2)
        self.assertEqual(source.count("ZES_ENABLE_SYSMAN=1 xpu-smi"), 2)
        self.assertIn(
            "-u UR_DEVICE_AFFINITY_MASK ZES_ENABLE_SYSMAN=1 xpu-smi stats",
            source,
        )
        self.assertIn(
            "-u UR_DEVICE_AFFINITY_MASK ZES_ENABLE_SYSMAN=1 xpu-smi discovery",
            source,
        )
        self.assertNotIn("env -i", source)
        self.assertNotIn("-u ZES_ENABLE_SYSMAN", source)
        self.assertNotIn("unset ZES_ENABLE_SYSMAN", source)
        self.assertNotIn("export ZE_AFFINITY_MASK", source)
        self.assertGreater(source.index('setsid python3 "$CAPTURE" run'), next_phase)

    def test_xpu_telemetry_sanitizes_only_the_fake_process_environment(self) -> None:
        completed, fake_log, stats_text, discovery_text = run_fake_xpu_probe(SCRIPT)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(
            completed.stdout,
            "43\nmasked-ze|masked-oneapi|masked-sycl|masked-ur|parent-zes\n",
        )
        self.assertEqual(fake_log, "stats -d 2\ndiscovery -j\n")
        self.assertEqual(stats_text, "| GPU Memory Used | 43 MiB |\n")
        self.assertEqual(discovery_text, '{"device_list":[]}\n')

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
