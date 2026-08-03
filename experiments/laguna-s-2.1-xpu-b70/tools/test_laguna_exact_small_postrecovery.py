#!/usr/bin/env python3
"""CPU-only fail-closed tests for the exact-small post-recovery harness."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shlex
import signal
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parents[2]
RUNNER = TOOLS / "run_laguna_replemb_measurement_leg.sh"
WRAPPER = TOOLS / "run_laguna_exact_small_postrecovery.sh"
RESOURCE_WRAPPER = TOOLS / "run_laguna_exact_small_swap24.sh"
SWAP_HELPER = TOOLS / "manage_laguna_swap_file.py"
SAFETY_HELPER = TOOLS / "laguna_resource_safety.sh"
LOCK = TOOLS / "exact-small-postrecovery-lock.json"
SWAP24_LOCK = TOOLS / "exact-small-swap24-lock.json"
SWAP24_LOCK_FILES = {
    "CURRENT.md",
    "data/laguna-device-recovery-scheduler-gate-20260802.json",
    "data/laguna-exact-small-portfolio-component-20260801.json",
    "data/laguna-exact-small-portfolio-runtime-lock-20260801.json",
    "data/laguna-exact-small-postrecovery-smoke-20260803.json",
    "data/laguna-shared-elementwise-m12-record-20260731.json",
    "experiments/laguna-s-2.1-xpu-b70/RESUME.md",
    "experiments/laguna-s-2.1-xpu-b70/notes/"
    "2026-08-01-exact-small-component-portfolio-preregistration.md",
    "experiments/laguna-s-2.1-xpu-b70/notes/"
    "2026-08-02-exact-small-postrecovery-preregistration.md",
    "experiments/laguna-s-2.1-xpu-b70/notes/"
    "2026-08-02-exact-small-postrecovery-result.md",
    "experiments/laguna-s-2.1-xpu-b70/notes/"
    "2026-08-02-exact-small-swap24-preregistration.md",
    "experiments/laguna-s-2.1-xpu-b70/realistic-suite-v1.json",
    "experiments/laguna-s-2.1-xpu-b70/tools/capture_laguna_m8_idle_snapshot.py",
    "experiments/laguna-s-2.1-xpu-b70/tools/compare_exact_runs.py",
    "experiments/laguna-s-2.1-xpu-b70/tools/exact-small-postrecovery-lock.json",
    "experiments/laguna-s-2.1-xpu-b70/tools/laguna_nvme_paths.sh",
    "experiments/laguna-s-2.1-xpu-b70/tools/laguna_resource_safety.sh",
    "experiments/laguna-s-2.1-xpu-b70/tools/manage_laguna_swap_file.py",
    "experiments/laguna-s-2.1-xpu-b70/tools/run_laguna_dflash_segmented_smoke.py",
    "experiments/laguna-s-2.1-xpu-b70/tools/run_laguna_exact_small_postrecovery.sh",
    "experiments/laguna-s-2.1-xpu-b70/tools/run_laguna_exact_small_swap24.sh",
    "experiments/laguna-s-2.1-xpu-b70/tools/run_laguna_replemb_measurement_leg.sh",
    "experiments/laguna-s-2.1-xpu-b70/tools/serve_laguna_mwide_graph_nvme.sh",
    "experiments/laguna-s-2.1-xpu-b70/tools/test_laguna_exact_small_postrecovery.py",
    "repro/laguna-s-2.1-int4-b70-102tps-20260726/manifests/"
    "model-release-files.sha256",
    "repro/laguna-s-2.1-int4-b70-102tps-20260726/verify-runtime.py",
    "scripts/bench-openai-realistic-suite.py",
    "scripts/qualify_realistic_window_metrics.py",
}


def base_args() -> list[str]:
    return [
        "candidate",
        "B1",
        "/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/host-test",
        "12",
        "11",
        "1",
        "0",
        "0",
        "1",
        "0",
        "0",
        "0",
        "1",
        "1",
        "0",
        "0",
        "",
        "64",
        "1",
        "",
        "6",
        "0",
        "1",
        "0",
        "0",
        "1",
        "1",
        "0.90",
        "0",
        "0",
        "0",
        "1",
        "0",
        "1",
        "1",
        "0",
        "0",
        "0",
        "1",
        "0",
        "",
        "96",
        "-1",
        "0",
        "0",
        "0",
        "1",
        "1",
        "1",
    ]


class ExactSmallHarnessTests(unittest.TestCase):
    maxDiff = None

    def run_invalid(self, args: list[str], message: str) -> None:
        completed = subprocess.run(
            [str(RUNNER), *args],
            text=True,
            capture_output=True,
            check=False,
            env={
                "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                "HOME": "/home/steve",
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
                "LAGUNA_RUNNER_VALIDATE_ONLY": "1",
            },
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn(message, completed.stdout + completed.stderr)

    def test_shell_syntax(self) -> None:
        for script in (RUNNER, WRAPPER, RESOURCE_WRAPPER):
            completed = subprocess.run(
                ["bash", "-n", str(script)], capture_output=True, text=True
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_runner_wires_both_selectors_and_worker_proof(self) -> None:
        source = RUNNER.read_text()
        required = (
            'decode_no_kloop_barriers="${48:-0}"',
            'scale_lane_dedup="${49:-0}"',
            'VLLM_XPU_LAGUNA_DECODE_NO_KLOOP_BARRIERS="$decode_no_kloop_barriers"',
            'VLLM_XPU_LAGUNA_SCALE_LANE_DEDUP="$scale_lane_dedup"',
            "printf 'decode_no_kloop_barriers=%s\\n'",
            "printf 'scale_lane_dedup=%s\\n'",
            'grep -Fx "VLLM_XPU_LAGUNA_DECODE_NO_KLOOP_BARRIERS=$decode_no_kloop_barriers"',
            'grep -Fx "VLLM_XPU_LAGUNA_SCALE_LANE_DEDUP=$scale_lane_dedup"',
            "exact-small-worker-environments.txt",
            "exact-small-worker-grouped-gemm-maps.txt",
            "LAGUNA_MOE_ROWS num_rows=12",
            "dispatched_ranks != expected",
            "mapped_dispatch_ranks != expected",
            "VLLM_XPU_LAGUNA_DFLASH_FP8_W8A16=1",
            "VLLM_XPU_LAGUNA_DFLASH_INLINE_ATTENTION_GRAPHS=1",
        )
        for marker in required:
            self.assertIn(marker, source)

    def test_wrapper_frozen_argument_vector(self) -> None:
        source = WRAPPER.read_text()
        match = re.search(r"leg_args=\(\n(?P<body>.*?)\n  \)", source, re.DOTALL)
        self.assertIsNotNone(match)
        args = shlex.split(match.group("body"), posix=True)
        self.assertEqual(len(args), 49)
        resolved = [
            {
                "$label": "B1",
                "$run_dir": base_args()[2],
                "$smoke": "1",
            }.get(value, value)
            for value in args
        ]
        self.assertEqual(resolved, base_args())
        self.assertEqual(args[0], "candidate")
        self.assertEqual(args[3:6], ["12", "11", "1"])
        self.assertEqual(args[18], "1")
        self.assertEqual(args[21:24], ["0", "1", "0"])
        self.assertEqual(args[25], "1")
        self.assertEqual(args[33:35], ["1", "1"])
        self.assertEqual(args[38], "1")
        self.assertEqual(args[46:49], ["1", "1", "1"])

    def test_malformed_grouped_selectors_fail(self) -> None:
        for index, value in ((47, "2"), (48, "yes")):
            args = base_args()
            args[index] = value
            self.run_invalid(args, "must be 0 or 1")

    def test_grouped_selectors_must_be_paired(self) -> None:
        for no_kloop, lane_dedup in (("1", "0"), ("0", "1")):
            args = base_args()
            args[47], args[48] = no_kloop, lane_dedup
            self.run_invalid(args, "must be enabled together")

    def test_portfolio_dependencies_fail_closed(self) -> None:
        cases = (
            (0, "control", "candidate treatment"),
            (3, "8", "M=12 and SPEC=11"),
            (4, "8", "M=12 and SPEC=11"),
            (12, "0", "width-12 GRF128/transposed scales"),
            (18, "0", "LAGUNA_LOG_MOE_ROWS=1"),
            (21, "", "SCALE_VEC=1, SCALE_FOLD=0, DEQUANT_MAD=0"),
            (22, "", "SCALE_VEC=1, SCALE_FOLD=0, DEQUANT_MAD=0"),
            (23, "", "SCALE_VEC=1, SCALE_FOLD=0, DEQUANT_MAD=0"),
            (26, "0", "authorized only for the 2x400 non-scored smoke"),
            (33, "0", "width-12 GRF128/transposed scales"),
            (34, "0", "width-12 GRF128/transposed scales"),
            (38, "0", "M12_MAPPED_TAIL=1 requires M12_SHARED_ELEMENTWISE=1"),
            (46, "0", "requires M12_MAPPED_TAIL=1"),
        )
        for index, value, message in cases:
            with self.subTest(index=index, value=value):
                args = base_args()
                args[index] = value
                if index == 0:
                    args[1] = "A1"
                self.run_invalid(args, message)

    def test_validate_only_accepts_frozen_vector_without_action(self) -> None:
        completed = subprocess.run(
            [str(RUNNER), *base_args()],
            text=True,
            capture_output=True,
            check=False,
            env={
                "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                "HOME": "/home/steve",
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
                "LAGUNA_RUNNER_VALIDATE_ONLY": "1",
            },
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout, "argument_validation=PASS\n")

    def test_wrapper_has_host_memory_and_journal_guards(self) -> None:
        source = WRAPPER.read_text()
        for marker in (
            "mem_available_floor_kb=8388608",
            "combined_mem_floor_kb=16777216",
            "combined_swap_floor_kb=4194304",
            "kernel-journal-${phase}.log",
            "device-error-scan-${phase}.log",
            "/swap.img:8388604",
            "eno1",
            "10.0.0.65",
            "current boot differs from passed recovery boot",
            "DRM opener check failed or matched",
            "gemma4-26b-q8-quad-backends.service",
            "/usr/bin/env -i",
            "tag or run roots differ from the one-shot authorization",
            "laguna-exact-small-postrecovery.lock",
            "terminal_audit",
            "stop_runner_bounded",
            "cleanup_recorded_service",
            "verify_no_worker_survivors",
            "journal_grep_status=$?",
            "(( journal_grep_status == 1 ))",
            "(( grep_status == 1 ))",
            '[[ -c "/dev/dri/$card" && -c "/dev/dri/$render" ]]',
            "/swap-laguna-longctx.img:16777212",
            "LAGUNA_EXACT_SMALL_SWAP24_ARMED",
            "exact-small-swap24-lock.json",
        ):
            self.assertIn(marker, source)

        resource_source = RESOURCE_WRAPPER.read_text()
        for marker in (
            "required_lock_files=(",
            "execution lock file set mismatch",
            "manage_laguna_swap_file.py",
            "/usr/sbin/mkswap",
            "/usr/sbin/swapon",
            "/usr/sbin/swapoff",
            "swap_identity_matches",
            "inspect_swap_state",
            "/usr/bin/setsid",
            "verify_no_model_survivors",
            "seal_core_roots",
            "core_group_status",
            "core_group_status=1",
            'core_pgid="$active_core_pid"',
            "laguna_wait_for_dedicated_group",
            "laguna_stop_process_bounded",
            "load_swap_identity_record",
            "laguna_swapoff_allowed",
            "laguna_remove_allowed",
            "laguna_cleanup_passes",
            "UNVERIFIED_CHECK_PERMISSIONS_AND_PROCESS_EXIT",
            "resource-status.txt",
            "chmod -R a-w",
        ):
            self.assertIn(marker, resource_source)

        helper_source = SWAP_HELPER.read_text()
        for marker in (
            "os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW",
            "os.posix_fallocate",
            "created_identity",
            "signal.SIGTERM",
            "signal.pthread_sigmask",
            "interrupt_allocation",
            "opened = os.fstat(fd)",
            "require_identity",
            "remove_inactive",
            'if swap_state() != "INACTIVE"',
        ):
            self.assertIn(marker, helper_source)

    def test_swap_helper_read_only_state(self) -> None:
        completed = subprocess.run(
            ["python3", str(SWAP_HELPER), "state"],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout, "INACTIVE\n")

    def test_swap_helper_signal_closes_initial_inode_gap(self) -> None:
        spec = importlib.util.spec_from_file_location("laguna_swap_helper_test", SWAP_HELPER)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)
        with tempfile.TemporaryDirectory() as temp_dir:
            helper.SWAP_PATH = Path(temp_dir) / "signal-test.swap"
            helper.SWAP_SIZE = 4096
            original_fstat = helper.os.fstat
            first_call = True

            def interrupt_first_fstat(fd: int) -> os.stat_result:
                nonlocal first_call
                if first_call:
                    first_call = False
                    os.kill(os.getpid(), signal.SIGTERM)
                return original_fstat(fd)

            with mock.patch.object(helper.os, "fstat", side_effect=interrupt_first_fstat):
                with self.assertRaises(InterruptedError):
                    helper.create()
            self.assertFalse(helper.SWAP_PATH.exists())

    def test_cleanup_decisions_fail_closed(self) -> None:
        helper = shlex.quote(str(SAFETY_HELPER))
        script = f"""
source {helper}
laguna_swapoff_allowed 0 0 0 0 0 0 ACTIVE || exit 10
laguna_remove_allowed 0 0 0 0 0 0 0 0 INACTIVE PRESENT || exit 11
laguna_cleanup_passes 0 0 0 0 0 0 0 0 0 0 0 1 /swap.img:8388604 ABSENT || exit 12
for index in 1 2 3 4 5 6; do
  values=(0 0 0 0 0 0)
  values[index-1]=1
  ! laguna_swapoff_allowed "${{values[@]}}" ACTIVE || exit $((20 + index))
done
for index in 1 2 3 4 5 6 7 8; do
  values=(0 0 0 0 0 0 0 0)
  values[index-1]=1
  ! laguna_remove_allowed "${{values[@]}}" INACTIVE PRESENT || exit $((30 + index))
done
for index in 1 2 3 4 5 6 7 8 9 10 11; do
  values=(0 0 0 0 0 0 0 0 0 0 0 1)
  values[index-1]=1
  ! laguna_cleanup_passes "${{values[@]}}" /swap.img:8388604 ABSENT || exit $((50 + index))
done
! laguna_swapoff_allowed 0 0 0 0 0 0 UNKNOWN || exit 70
! laguna_remove_allowed 0 0 0 0 0 0 0 0 ACTIVE PRESENT || exit 71
! laguna_remove_allowed 0 0 0 0 0 0 0 0 INACTIVE ABSENT || exit 72
! laguna_cleanup_passes 0 0 0 0 0 0 0 0 0 0 0 0 /swap.img:8388604 ABSENT || exit 73
! laguna_cleanup_passes 0 0 0 0 0 0 0 0 0 0 0 2 /swap.img:8388604 ABSENT || exit 74
! laguna_cleanup_passes 0 0 0 0 0 0 0 0 0 0 0 1 wrong ABSENT || exit 75
! laguna_cleanup_passes 0 0 0 0 0 0 0 0 0 0 0 1 /swap.img:8388604 PRESENT || exit 76
"""
        completed = subprocess.run(
            ["bash", "-c", script], text=True, capture_output=True, check=False
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_persistent_process_group_is_killed_and_reported_forced(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            child_file = Path(temp_dir) / "child.pid"
            unrelated = subprocess.Popen(["sleep", "30"])
            leader = subprocess.Popen(
                [
                    "setsid",
                    "bash",
                    "-c",
                    f"trap '' TERM; (trap '' TERM; while :; do sleep 1; done) & "
                    f"echo $! > {shlex.quote(str(child_file))}",
                ]
            )
            try:
                self.assertEqual(leader.wait(timeout=5), 0)
                for _ in range(100):
                    if child_file.exists() and child_file.read_text().strip():
                        break
                    time.sleep(0.01)
                child_pid = int(child_file.read_text().strip())
                pgid = os.getpgid(child_pid)
                script = f"""
source {shlex.quote(str(SAFETY_HELPER))}
laguna_wait_for_dedicated_group {pgid} 5 0.01 || exit 9
laguna_process_group_exists {pgid} || exit 10
laguna_stop_process_group_bounded {pgid} 100 0.01
stop_status=$?
laguna_process_group_exists {pgid}
group_status=$?
printf 'stop_status=%s group_status=%s\n' "$stop_status" "$group_status"
"""
                completed = subprocess.run(
                    ["bash", "-c", script],
                    text=True,
                    capture_output=True,
                    check=False,
                    timeout=10,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertEqual(
                    completed.stdout, "stop_status=1 group_status=1\n"
                )
                self.assertIsNone(unrelated.poll())
            finally:
                if unrelated.poll() is None:
                    unrelated.terminate()
                    unrelated.wait(timeout=5)
                if child_file.exists():
                    try:
                        os.killpg(os.getpgid(int(child_file.read_text())), signal.SIGKILL)
                    except (ProcessLookupError, PermissionError):
                        pass

    def test_pre_setsid_child_is_stopped_without_touching_unrelated_process(self) -> None:
        child = subprocess.Popen(
            [
                "python3",
                "-c",
                "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); "
                "time.sleep(30)",
            ]
        )
        unrelated = subprocess.Popen(["sleep", "30"])
        try:
            time.sleep(0.1)
            script = f"""
source {shlex.quote(str(SAFETY_HELPER))}
laguna_wait_for_dedicated_group {child.pid} 5 0.01
handshake_status=$?
laguna_stop_process_bounded {child.pid} 20 0.01
stop_status=$?
laguna_process_is_running {child.pid}
running_status=$?
printf 'handshake_status=%s stop_status=%s running_status=%s\n' \
  "$handshake_status" "$stop_status" "$running_status"
"""
            completed = subprocess.run(
                ["bash", "-c", script],
                text=True,
                capture_output=True,
                check=False,
                timeout=10,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(
                completed.stdout,
                "handshake_status=1 stop_status=1 running_status=1\n",
            )
            self.assertIsNone(unrelated.poll())
        finally:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=5)
            if unrelated.poll() is None:
                unrelated.terminate()
            unrelated.wait(timeout=5)

    def test_swap24_wrappers_freeze_exact_lock_file_set(self) -> None:
        for script in (WRAPPER, RESOURCE_WRAPPER):
            source = script.read_text()
            match = re.search(
                r"required_lock_files=\(\n(?P<body>.*?)\n\)",
                source,
                re.DOTALL,
            )
            self.assertIsNotNone(match, script.name)
            observed = set(shlex.split(match.group("body"), posix=True))
            self.assertEqual(observed, SWAP24_LOCK_FILES, script.name)

    def test_wrapper_rejects_ambient_coordinator_state(self) -> None:
        completed = subprocess.run(
            [str(WRAPPER), "not-the-authorized-tag"],
            text=True,
            capture_output=True,
            check=False,
            env={
                "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                "HOME": "/home/steve",
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
                "LAGUNA_EXACT_SMALL_CLEAN_ENV": "1",
                "GIT_CONFIG_COUNT": "0",
            },
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn(
            "unexpected coordinator environment variable: GIT_CONFIG_COUNT",
            completed.stderr,
        )

    def test_core_requires_swap24_resource_arm(self) -> None:
        completed = subprocess.run(
            [str(WRAPPER), "not-the-authorized-tag"],
            text=True,
            capture_output=True,
            check=False,
            env={
                "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                "HOME": "/home/steve",
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
            },
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("swap24 resource wrapper did not arm the smoke", completed.stderr)

    def test_resource_wrapper_rejects_ambient_state(self) -> None:
        completed = subprocess.run(
            [str(RESOURCE_WRAPPER), "not-the-authorized-tag"],
            text=True,
            capture_output=True,
            check=False,
            env={
                "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                "HOME": "/home/steve",
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
                "LAGUNA_EXACT_SMALL_SWAP24_CLEAN_ENV": "1",
                "GIT_CONFIG_COUNT": "0",
            },
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn(
            "unexpected swap24 coordinator environment variable: GIT_CONFIG_COUNT",
            completed.stderr,
        )

    def test_execution_lock_if_present(self) -> None:
        if not LOCK.exists():
            self.skipTest("execution lock is created only after the harness commit")
        payload = json.loads(LOCK.read_text())
        self.assertEqual(
            payload["schema"],
            "laguna-exact-small-postrecovery-execution-lock-v1",
        )
        self.assertEqual(payload["status"], "PASS")
        self.assertEqual(payload["authorized"]["tag"], "20260803T010333Z")
        self.assertEqual(
            payload["authorized"]["campaign_root"],
            "/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/"
            "laguna-exact-small-postrecovery-20260803T010333Z-campaign",
        )
        self.assertEqual(
            payload["authorized"]["smoke_root"],
            "/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/"
            "laguna-exact-small-postrecovery-20260803T010333Z-smoke",
        )
        for relative, expected in payload["files"].items():
            historical = subprocess.check_output(
                [
                    "git",
                    "-C",
                    str(REPO),
                    "show",
                    f"{payload['harness_commit']}:{relative}",
                ]
            )
            observed = hashlib.sha256(historical).hexdigest()
            self.assertEqual(observed, expected, relative)
        lock_commit = subprocess.check_output(
            ["git", "-C", str(REPO), "log", "-1", "--format=%H", "--", str(LOCK)],
            text=True,
        ).strip()
        changed = subprocess.check_output(
            [
                "git",
                "-C",
                str(REPO),
                "diff-tree",
                "--no-commit-id",
                "--name-only",
                "-r",
                lock_commit,
            ],
            text=True,
        ).splitlines()
        self.assertEqual(
            changed,
            [str(LOCK.relative_to(REPO))],
        )
        parent = subprocess.check_output(
            ["git", "-C", str(REPO), "rev-parse", f"{lock_commit}^"],
            text=True,
        ).strip()
        self.assertEqual(parent, payload["harness_commit"])

    def test_swap24_execution_lock_if_present(self) -> None:
        if not SWAP24_LOCK.exists():
            self.skipTest("swap24 lock is created only after the resource harness commit")
        payload = json.loads(SWAP24_LOCK.read_text())
        self.assertEqual(
            payload["schema"],
            "laguna-exact-small-swap24-execution-lock-v1",
        )
        self.assertEqual(payload["status"], "PASS")
        self.assertIsInstance(payload["files"], dict)
        self.assertEqual(set(payload["files"]), SWAP24_LOCK_FILES)
        self.assertEqual(payload["authorized"]["tag"], "20260803T014822Z")
        self.assertEqual(
            payload["authorized"]["campaign_root"],
            "/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/"
            "laguna-exact-small-postrecovery-20260803T014822Z-campaign",
        )
        self.assertEqual(
            payload["authorized"]["smoke_root"],
            "/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/"
            "laguna-exact-small-postrecovery-20260803T014822Z-smoke",
        )
        self.assertEqual(
            payload["authorized"]["resource_root"],
            "/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/"
            "laguna-exact-small-postrecovery-20260803T014822Z-swap24-resource",
        )
        for relative, expected in payload["files"].items():
            historical = subprocess.check_output(
                [
                    "git",
                    "-C",
                    str(REPO),
                    "show",
                    f"{payload['harness_commit']}:{relative}",
                ]
            )
            self.assertEqual(hashlib.sha256(historical).hexdigest(), expected, relative)
        lock_commit = subprocess.check_output(
            [
                "git",
                "-C",
                str(REPO),
                "log",
                "-1",
                "--format=%H",
                "--",
                str(SWAP24_LOCK),
            ],
            text=True,
        ).strip()
        head = subprocess.check_output(
            ["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True
        ).strip()
        self.assertEqual(head, lock_commit)
        changed = subprocess.check_output(
            [
                "git",
                "-C",
                str(REPO),
                "diff-tree",
                "--no-commit-id",
                "--name-only",
                "-r",
                lock_commit,
            ],
            text=True,
        ).splitlines()
        self.assertEqual(changed, [str(SWAP24_LOCK.relative_to(REPO))])
        parent = subprocess.check_output(
            ["git", "-C", str(REPO), "rev-parse", f"{lock_commit}^"],
            text=True,
        ).strip()
        self.assertEqual(parent, payload["harness_commit"])


if __name__ == "__main__":
    unittest.main()
