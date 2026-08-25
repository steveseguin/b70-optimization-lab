#!/usr/bin/env python3
"""CPU-only tests for the Qwen3.6 Q4_0 exact-depth r2 packet."""

from __future__ import annotations

import importlib.util
import inspect
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "run-20260825-qwen36-q4-0-tp1-mtp0-q8kv-exact-depth-r2.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


RUNNER = load_module("qwen36_q4_exact_depth_r2", SCRIPT)


class R2ContractTests(unittest.TestCase):
    def test_manifest_is_fresh_r2_and_quarantines_r1(self) -> None:
        manifest = RUNNER.R1.load_json(RUNNER.MANIFEST)
        RUNNER.validate_manifest(manifest)
        self.assertEqual(
            manifest["execution_contract"]["run_root"], str(RUNNER.RUN_ROOT)
        )
        self.assertNotEqual(RUNNER.RUN_ROOT, RUNNER.R1_ROOT)
        self.assertFalse(manifest["r1_quarantine"]["raw_row_reuse_allowed"])
        self.assertEqual(manifest["r1_quarantine"]["cells_publishable_from_r1"], 0)
        self.assertFalse(
            manifest["graph_off_attestation"]["runtime_stderr_markers_required"]
        )

    def test_r1_failure_and_overlap_evidence_remain_sealed(self) -> None:
        result = RUNNER.verify_r1_quarantine()
        self.assertEqual(result["status"], "quarantined")
        self.assertFalse(result["raw_row_reuse_allowed"])
        self.assertEqual(result["cells_publishable"], 0)
        self.assertEqual(result["competing_commit"], RUNNER.COMPETING_COMMIT)

    def test_exact_binary_graph_off_proof_passes(self) -> None:
        result = RUNNER.verify_graph_off_attestation()
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["classification"], "graph-off")
        self.assertTrue(result["compile_support"]["GGML_SYCL_GRAPH"])
        self.assertFalse(result["runtime_stderr_markers_used"])
        self.assertEqual(
            result["controlled_environment"]["GGML_SYCL_ENABLE_GRAPH"], "0"
        )

    def test_exact_binary_graph_off_proof_fails_closed_on_dso_hash(self) -> None:
        with mock.patch.object(RUNNER, "SYCL_DSO_SHA256", "0" * 64):
            with self.assertRaisesRegex(RUNNER.CampaignError, "SYCL backend DSO"):
                RUNNER.verify_graph_off_attestation()

    def test_all_cross_session_locks_precede_idle_and_run_root(self) -> None:
        source = inspect.getsource(RUNNER.campaign_locks)
        for lock in (
            "/run/lock/muse-glimmer-gpu-exclusive.lock",
            "/tmp/b70-benchmark.lock",
            "/tmp/b70-gpu0.lock",
            "qwen36-b70-gpu-leases/gpu0.lock",
        ):
            self.assertIn(lock, source)
        execute_source = inspect.getsource(RUNNER.R1.execute)
        lock_index = execute_source.index("with campaign_locks() as locks")
        idle_index = execute_source.index("verify_idle()")
        root_index = execute_source.index("RUN_ROOT.mkdir")
        self.assertLess(lock_index, idle_index)
        self.assertLess(lock_index, root_index)

    def test_idle_scan_covers_llama_batched_bench(self) -> None:
        source = inspect.getsource(RUNNER.verify_idle)
        self.assertIn("[l]lama-batched-bench", source)
        run_source = inspect.getsource(RUNNER.run_benchmark)
        self.assertLess(
            run_source.index("verify_idle()"), run_source.index("subprocess.run")
        )

    def test_metadata_uses_static_attestation_not_stderr(self) -> None:
        environment = RUNNER.R1.effective_environment(Path("/tmp/q36-r2-test"))
        metadata = RUNNER.metadata(environment)
        self.assertFalse(metadata["graph"]["requested"])
        self.assertFalse(
            metadata["graph"]["static_attestation"]["runtime_stderr_markers_used"]
        )
        self.assertIn(
            "exact-DSO", metadata["graph"]["capture"]["source"]
        )
        self.assertEqual(environment["GGML_SYCL_ENABLE_GRAPH"], "0")
        self.assertEqual(environment["GGML_SYCL_GRAPH_CACHE_SIZE"], "0")

    def test_benchmark_accepts_empty_stderr_only_after_static_proof(self) -> None:
        attestation = {
            "schema": "neural.download.qwen36-graph-off-static-attestation.v1",
            "status": "passed",
            "classification": "graph-off",
        }

        def fake_run(argv, *, check, stdout, stderr, env):
            del argv, check, stderr, env
            stdout.write(json.dumps([{"row": 1}]).encode("utf-8"))
            return SimpleNamespace(returncode=0)

        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            with (
                mock.patch.object(RUNNER, "verify_idle") as idle,
                mock.patch.object(
                    RUNNER,
                    "verify_graph_off_attestation",
                    return_value=attestation,
                ) as graph,
                mock.patch.object(RUNNER.subprocess, "run", side_effect=fake_run),
            ):
                rows = RUNNER.run_benchmark(root, {"GGML_SYCL_ENABLE_GRAPH": "0"})
            self.assertEqual(rows, 1)
            idle.assert_called_once_with()
            graph.assert_called_once_with()
            self.assertEqual((root / "llama-bench.stderr.log").read_bytes(), b"")
            receipt = json.loads((root / "graph-off-attestation.json").read_text())
            self.assertEqual(receipt["status"], "passed")

    def test_plan_is_inert_and_wrong_ack_fails_before_launch(self) -> None:
        before = RUNNER.RUN_ROOT.exists()
        result = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), "--plan"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "planned-not-launched")
        self.assertFalse(payload["r1_rows_reusable"])
        self.assertFalse(payload["writes_performed"])
        self.assertEqual(RUNNER.RUN_ROOT.exists(), before)
        with self.assertRaisesRegex(RUNNER.CampaignError, "acknowledgement"):
            RUNNER.R1.execute("wrong")


if __name__ == "__main__":
    unittest.main()
