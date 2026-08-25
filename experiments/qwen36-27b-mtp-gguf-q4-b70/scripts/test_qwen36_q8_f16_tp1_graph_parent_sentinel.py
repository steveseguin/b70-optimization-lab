#!/usr/bin/env python3
"""CPU-only contract tests for the Qwen3.6 Q8 graph parent sentinel."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest


SCRIPT = Path(__file__).with_name(
    "run-20260825-qwen36-q8-f16-tp1-graph-parent-sentinel-r1.py"
)
SPEC = importlib.util.spec_from_file_location("qwen36_q8_graph_parent_sentinel", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import {SCRIPT}")
RUNNER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = RUNNER
SPEC.loader.exec_module(RUNNER)


def summary(**overrides: int) -> str:
    values = {
        "device": 0,
        "requested": 70,
        "compatibility_rejected": 0,
        "device_unsupported": 0,
        "cache_entries": 3,
        "cache_limit": 8,
        "cache_hit": 67,
        "cache_miss": 3,
        "cache_full": 0,
        "direct_replay": 67,
        "recorded": 3,
        "created": 3,
        "updated": 0,
        "recreated": 0,
        "replayed": 70,
    }
    values.update(overrides)
    return (
        "[SYCL-GRAPH] summary device={device} requested={requested} "
        "compatibility_rejected={compatibility_rejected} "
        "device_unsupported={device_unsupported} cache_entries={cache_entries} "
        "cache_limit={cache_limit} cache_hit={cache_hit} cache_miss={cache_miss} "
        "cache_full={cache_full} direct_replay={direct_replay} recorded={recorded} "
        "created={created} updated={updated} recreated={recreated} replayed={replayed}\n"
    ).format(**values)


def candidate_log(summary_line: str | None = None) -> str:
    return "\n".join(
        (
            "GGML_SYCL_GRAPH: yes",
            "GGML_SYCL_ENABLE_GRAPH: 1",
            "GGML_SYCL_GRAPH_CACHE_SIZE: 8",
            "[SYCL-GRAPH] requested device=0 count=1",
            "[SYCL-GRAPH] recording_entered device=0 count=1",
            "[SYCL-GRAPH] replayed device=0 count=1 recorded=1 created=1 updated=0 recreated=0",
            "[SYCL-GRAPH] direct_replay device=0 count=1 cache_entries=1",
            summary_line or summary(),
        )
    )


class GraphParentSentinelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest, cls.libraries = RUNNER.static_check()

    def test_exact_parent_only_identity_and_same_binary_arms(self) -> None:
        selectors = self.manifest["selectors"]
        self.assertEqual(selectors["artifact_id"], "qwen36-27b-unsloth-q8-0-82d411a")
        self.assertEqual(selectors["quantization"], "Q8_0")
        self.assertEqual(selectors["tp"], 1)
        self.assertEqual(selectors["mtp"], 0)
        self.assertEqual(selectors["kv"], "f16")
        self.assertEqual(selectors["graph_comparison"], ["off-cache0", "on-cache8"])
        self.assertEqual(tuple(self.manifest["canary"]["common_argv"]), RUNNER.COMMON_ARGV)
        interpretation = self.manifest["interpretation"]
        self.assertFalse(interpretation["seven_cell_expansion_authorized"])
        self.assertFalse(interpretation["site_publication_authorized"])
        self.assertIsNone(interpretation["speed_measurement_or_floor"])
        lifecycle = self.manifest["lifecycle"]
        self.assertEqual(
            lifecycle["model_view_timeout_seconds"],
            RUNNER.MODEL_VIEW_TIMEOUT_SECONDS,
        )
        self.assertTrue(lifecycle["signal_cleanup_required"])
        self.assertTrue(lifecycle["packet_and_artifact_postflight_required"])
        self.assertEqual(len(RUNNER.PACKET_PATHS), 4)

    def test_thin_launcher_and_complete_canonical_dso_closure_are_frozen(self) -> None:
        thin = self.manifest["runtime"]["thin_launcher"]
        self.assertEqual(thin["path"], str(RUNNER.BINARY))
        self.assertEqual(thin["sha256"], RUNNER.BINARY_SHA256)
        self.assertEqual(len(self.libraries), 34)
        self.assertEqual(
            {row["soname"] for row in self.libraries},
            {row["soname"] for row in self.manifest["runtime"]["effective_shared_libraries"]},
        )
        self.assertIn("libllama-cli-impl.so", {row["soname"] for row in self.libraries})
        self.assertIn("libggml-sycl.so.0", {row["soname"] for row in self.libraries})
        self.assertIn("libsycl.so.9", {row["soname"] for row in self.libraries})
        self.assertIn("ld-linux-x86-64.so.2", {row["soname"] for row in self.libraries})
        for row in self.libraries:
            self.assertTrue(Path(row["realpath"]).is_absolute())
            self.assertEqual(str(Path(row["realpath"]).resolve()), row["realpath"])

    def test_source_limitation_is_explicit_and_artifact_identity_is_authority(self) -> None:
        provenance = self.manifest["runtime"]["source_provenance"]
        self.assertEqual(provenance["tree_classification"], "historical-protected-dirty-build")
        self.assertIn("does not claim", provenance["limitation"])
        self.assertIn("complete effective DSO hashes", provenance["limitation"])

    def test_inherited_library_paths_and_unsafe_graph_controls_are_rejected(self) -> None:
        rejected = RUNNER.reject_inherited_environment(
            {
                "PATH": "/usr/bin",
                "LD_LIBRARY_PATH": "/tmp/poison",
                "LIBRARY_PATH": "/tmp/poison",
                "SYCL_GRAPH_FORCE_NATIVE_RECORDING": "1",
                "GGML_SYCL_GRAPH_RECORD_QUEUE": "1",
                "GGML_SYCL_GRAPH_REPLAY_NO_UPDATE": "1",
            }
        )
        self.assertEqual(
            rejected,
            sorted(
                {
                    "LD_LIBRARY_PATH",
                    "LIBRARY_PATH",
                    "SYCL_GRAPH_FORCE_NATIVE_RECORDING",
                    "GGML_SYCL_GRAPH_RECORD_QUEUE",
                    "GGML_SYCL_GRAPH_REPLAY_NO_UPDATE",
                }
            ),
        )
        with tempfile.TemporaryDirectory() as value:
            control = RUNNER.arm_environment(Path(value), "0", "0")
            candidate = RUNNER.arm_environment(Path(value), "1", "8")
        for name in RUNNER.UNSAFE_GRAPH_VARIABLES:
            self.assertNotIn(name, control)
            self.assertNotIn(name, candidate)
        self.assertEqual(control["GGML_SYCL_ENABLE_GRAPH"], "0")
        self.assertEqual(control["GGML_SYCL_GRAPH_CACHE_SIZE"], "0")
        self.assertEqual(candidate["GGML_SYCL_ENABLE_GRAPH"], "1")
        self.assertEqual(candidate["GGML_SYCL_GRAPH_CACHE_SIZE"], "8")

    def test_control_requires_compile_on_runtime_off_and_zero_summary(self) -> None:
        text = "\n".join(
            (
                "GGML_SYCL_GRAPH: yes",
                "GGML_SYCL_ENABLE_GRAPH: 0",
                "GGML_SYCL_GRAPH_CACHE_SIZE: 0",
                summary(
                    requested=0, compatibility_rejected=0, device_unsupported=0,
                    cache_entries=0, cache_limit=0, cache_hit=0, cache_miss=0,
                    cache_full=0, direct_replay=0, recorded=0, created=0,
                    updated=0, recreated=0, replayed=0,
                ),
            )
        )
        parsed = RUNNER.validate_control_graph_log(text)
        self.assertEqual(parsed["requested"], 0)
        with self.assertRaisesRegex(RUNNER.GateError, "executed graph work"):
            RUNNER.validate_control_graph_log(text.replace("requested=0", "requested=1", 1))

    def test_candidate_requires_real_record_replay_and_direct_cache_hit(self) -> None:
        parsed = RUNNER.validate_candidate_graph_log(candidate_log())
        self.assertGreater(parsed["requested"], 0)
        self.assertGreater(parsed["recorded"], 0)
        self.assertGreater(parsed["replayed"], 0)
        self.assertGreater(parsed["direct_replay"], 0)
        self.assertEqual(parsed["compatibility_rejected"], 0)
        with self.assertRaisesRegex(RUNNER.GateError, "compatibility rejection"):
            RUNNER.validate_candidate_graph_log(
                candidate_log(summary(compatibility_rejected=1))
            )
        with self.assertRaisesRegex(RUNNER.GateError, "did not record/replay/cache-hit"):
            RUNNER.validate_candidate_graph_log(
                candidate_log(summary(cache_hit=0, direct_replay=0, replayed=0))
            )
        with self.assertRaisesRegex(RUNNER.GateError, "wrong device"):
            RUNNER.validate_candidate_graph_log(candidate_log(summary(device=1)))
        with self.assertRaisesRegex(RUNNER.GateError, "positive graph-action evidence absent"):
            RUNNER.validate_candidate_graph_log(candidate_log().replace("count=1", "count=0"))

    def test_requested_but_unreplayed_marker_set_fails(self) -> None:
        text = "\n".join(
            (
                "GGML_SYCL_GRAPH: yes",
                "GGML_SYCL_ENABLE_GRAPH: 1",
                "GGML_SYCL_GRAPH_CACHE_SIZE: 8",
                "[SYCL-GRAPH] requested device=0 count=1",
                summary(cache_hit=0, direct_replay=0, recorded=0, created=0, replayed=0),
            )
        )
        with self.assertRaisesRegex(RUNNER.GateError, "evidence absent"):
            RUNNER.validate_candidate_graph_log(text)

    def test_process_group_timeout_uses_term_then_kill_and_returns_promptly(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            begin = time.monotonic()
            with self.assertRaisesRegex(RUNNER.GateError, "timed out"):
                RUNNER.run_process_group(
                    name="timeout-fixture",
                    argv=["/bin/sh", "-c", "trap '' TERM; sleep 30 & wait"],
                    environment={"PATH": "/usr/bin:/bin"},
                    stdout_path=root / "stdout",
                    stderr_path=root / "stderr",
                    timeout_seconds=0.05,
                    grace_seconds=0.05,
                )
            self.assertLess(time.monotonic() - begin, 2.0)

    def test_sigint_and_sigterm_always_clean_the_child_process_group(self) -> None:
        for signal_name in ("INT", "TERM"):
            with self.subTest(signal_name=signal_name), tempfile.TemporaryDirectory() as value:
                root = Path(value)
                with self.assertRaisesRegex(RUNNER.CampaignInterrupted, "interrupted"):
                    with RUNNER.caught_campaign_signals():
                        RUNNER.run_process_group(
                            name=f"signal-{signal_name.lower()}-fixture",
                            argv=[
                                "/bin/sh", "-c",
                                f"echo $$; kill -{signal_name} $PPID; sleep 30",
                            ],
                            environment={"PATH": "/usr/bin:/bin"},
                            stdout_path=root / "stdout",
                            stderr_path=root / "stderr",
                            timeout_seconds=10,
                            grace_seconds=0.1,
                        )
                child_pid = int((root / "stdout").read_text().strip())
                with self.assertRaises(ProcessLookupError):
                    os.kill(child_pid, 0)

    def test_exited_leader_cannot_leave_term_ignoring_descendant(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            receipt = RUNNER.run_process_group(
                name="exited-leader-descendant-fixture",
                argv=[
                    "/bin/sh", "-c",
                    "(trap '' TERM HUP; sleep 30) & child=$!; echo $child; exit 0",
                ],
                environment={"PATH": "/usr/bin:/bin"},
                stdout_path=root / "stdout",
                stderr_path=root / "stderr",
                timeout_seconds=5,
                grace_seconds=1,
            )
            child_pid = int((root / "stdout").read_text().strip())
            self.assertTrue(receipt["term_sent"])
            self.assertTrue(receipt["kill_sent"])
            self.assertTrue(receipt["process_group_empty"])
            with self.assertRaises(ProcessLookupError):
                os.kill(child_pid, 0)

    def test_create_only_writer_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            path = Path(value) / "receipt.json"
            RUNNER.create_json(path, {"state": "first"})
            with self.assertRaisesRegex(RUNNER.GateError, "refusing to overwrite"):
                RUNNER.create_json(path, {"state": "second"})
            self.assertEqual(json.loads(path.read_text()), {"state": "first"})

    def test_gpu_compute_gate_is_real_but_not_executed_by_static_tests(self) -> None:
        compute = self.manifest["gpu_compute_gate"]
        self.assertEqual(compute["physical_card"], 0)
        self.assertEqual(compute["ze_affinity_mask"], "0")
        self.assertIn("torch.ones((1024, 1024), device=\"xpu\")", RUNNER.COMPUTE_CODE)
        self.assertIn("assert y == 2097152.0", RUNNER.COMPUTE_CODE)

    def test_default_plan_is_inert(self) -> None:
        def snapshot() -> list[tuple[str, int, int]]:
            if not RUNNER.RUN_ROOT.exists():
                return []
            return [
                (str(path.relative_to(RUNNER.RUN_ROOT)), path.stat().st_size, path.stat().st_mtime_ns)
                for path in sorted(RUNNER.RUN_ROOT.rglob("*")) if path.is_file()
            ]

        before = snapshot()
        result = subprocess.run(
            [sys.executable, "-B", str(SCRIPT)], check=True, text=True,
            capture_output=True,
        )
        plan = json.loads(result.stdout)
        self.assertTrue(plan["default_is_inert"])
        self.assertTrue(plan["parent_sentinel_only"])
        self.assertFalse(plan["seven_cell_expansion_authorized"])
        self.assertEqual(plan["exact_ack"], RUNNER.ACK)
        self.assertEqual(snapshot(), before)


if __name__ == "__main__":
    unittest.main()
