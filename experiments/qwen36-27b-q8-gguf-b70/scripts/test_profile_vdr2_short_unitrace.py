#!/usr/bin/env python3
"""Offline static/plan checks for the profiler-only VDR2 wrapper."""

import os
import json
import pathlib
import subprocess
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).with_name("profile-vdr2-short-unitrace.sh")
SUMMARIZER = pathlib.Path(__file__).with_name("summarize-vdr2-unitrace.py")


class ProfilePlanTest(unittest.TestCase):
    def test_direct_wrapper_is_executable(self):
        self.assertTrue(os.access(SCRIPT, os.X_OK))

    def test_plan_is_exact_and_offline(self):
        env = os.environ.copy()
        env.update(
            STAMP="20260810T000000.000000000Z",
            SESSION="QwenVDR2" + "a" * 48,
            PORT="19940",
            RUN_DIR="/tmp/qwen-profile-run",
            TRACE_DIR="/tmp/qwen-profile-trace",
        )
        plan = subprocess.run(
            [str(SCRIPT), "--print-plan"],
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        ).stdout
        required = (
            "classification=profiler-only",
            "performance_promotable=false",
            "--device-timing",
            "--kernel-submission",
            "--verbose",
            "--pid",
            "--devices-to-sample 0",
            "--follow-child-process 0",
            "--start-paused",
            "reorder_mul_mat_vec_q8_0_q8_1_sycl",
            "--result-dir /tmp/qwen-profile-trace",
            "-c 32768",
            "-np 1",
            "-ub 1024",
            "--ignore-eos",
            "--require-full-512-metric",
            "--require-post-512-canary",
            "--band short",
            "resume_decode_min=100",
            "trace_cycles_min=45",
            "trace_cycles_max=55",
            "control_timeout_s=900",
            "trace_cap_bytes=104857600",
            "capture_window_target_decode_cycles=50",
            "baseline_token_ns=60281000",
        )
        for value in required:
            self.assertIn(value, plan)
        self.assertNotIn("run-validation.sh", plan)
        self.assertNotIn("--teardown-on-signal", plan)

    def test_rejects_short_session_and_shared_dirs(self):
        base = os.environ.copy()
        base["SESSION"] = "short"
        self.assertNotEqual(
            subprocess.run([str(SCRIPT), "--print-plan"], env=base).returncode, 0
        )
        base["SESSION"] = "b" * 40
        base["RUN_DIR"] = base["TRACE_DIR"] = "/tmp/same"
        self.assertNotEqual(
            subprocess.run([str(SCRIPT), "--print-plan"], env=base).returncode, 0
        )

    def test_trace_summary_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            trace = root / "trace" / "llama.1"
            trace.mkdir(parents=True)
            (trace / "device_timing.txt").write_text(
                "Total Device Time for L0 backend (ns): 64000\n"
                '"reorder_mul_mat_vec_q8_0_q8_1_sycl", 3200, 64000, 100, 20, 10, 30\n'
                '"reorder_mul_mat_vec_q8_0_q8_1_sycl", AOT, 32, 7, 0, 0, 0, 128\n'
            )
            (trace / "device_submission.txt").write_text(
                '"reorder_mul_mat_vec_q8_0_q8_1_sycl", 3200, 1000, 1, 2000, 2, 64000, 100\n'
            )
            out = root / "summary.json"
            subprocess.run(
                [
                    str(SUMMARIZER),
                    "--trace-dir",
                    str(root / "trace"),
                    "--kernel",
                    "reorder_mul_mat_vec_q8_0_q8_1_sycl",
                    "--expected-decode-cycles",
                    "50",
                    "--baseline-token-ns",
                    "60281000",
                    "--out",
                    str(out),
                ],
                check=True,
            )
            summary = json.loads(out.read_text())
            self.assertTrue(summary["passed"])
            self.assertEqual(summary["kernel_calls"], 3200)
            self.assertEqual(summary["calls_per_nominal_decode_cycle"], 64)
            self.assertEqual(summary["submission_execute_ns"], 64000)
            self.assertGreater(summary["nominal_hotspot_share"], 0)

    def test_static_safety_gates_are_present(self):
        source = SCRIPT.read_text()
        summary_source = SUMMARIZER.read_text()
        for value in (
            "offloaded[[:space:]]+65/65 layers to GPU",
            "trace-files.sha256",
            "TRACE_CAP_BYTES",
            "latest_task0_decoded >= resume_decoded + TRACE_CYCLES_MIN",
            "observed_decode_cycles >= TRACE_CYCLES_MIN",
            "observed_decode_cycles <= TRACE_CYCLES_MAX",
        ):
            self.assertIn(value, source)
        for value in (
            "ncols_variant_absent",
            "verbose_kernel_properties_present",
            "kernel_submission_nonempty",
        ):
            self.assertIn(value, summary_source)


if __name__ == "__main__":
    unittest.main()
