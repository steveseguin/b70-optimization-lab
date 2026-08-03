#!/usr/bin/env python3
"""CPU-only fail-closed tests for the exact-small post-recovery harness."""

from __future__ import annotations

import hashlib
import json
import re
import shlex
import subprocess
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parents[2]
RUNNER = TOOLS / "run_laguna_replemb_measurement_leg.sh"
WRAPPER = TOOLS / "run_laguna_exact_small_postrecovery.sh"
LOCK = TOOLS / "exact-small-postrecovery-lock.json"


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
        for script in (RUNNER, WRAPPER):
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
        ):
            self.assertIn(marker, source)

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


if __name__ == "__main__":
    unittest.main()
