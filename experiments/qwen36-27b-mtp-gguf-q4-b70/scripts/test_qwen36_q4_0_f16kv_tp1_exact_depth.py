#!/usr/bin/env python3
"""CPU-only contract tests for the Qwen3.6 Q4_0 F16 depth packet."""

from __future__ import annotations

import importlib.util
import inspect
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "run-20260825-qwen36-q4-0-f16kv-tp1-exact-depth-r1.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


RUNNER = load_module("qwen36_q4_0_f16_depth_runner", SCRIPT)


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = RUNNER.load_manifest()
        RUNNER.validate_manifest(cls.manifest)

    def test_exact_seven_cell_f16_identity(self) -> None:
        selectors = self.manifest["selectors"]
        self.assertEqual(selectors["revision"], "qwen3.6-27b")
        self.assertEqual(selectors["quantization"], "Q4_0")
        self.assertEqual(selectors["tp"], 1)
        self.assertEqual(selectors["mtp"], 0)
        self.assertEqual(selectors["graph_mode"], "off")
        self.assertEqual(selectors["kv"], "f16")
        self.assertEqual(tuple(selectors["active_context_tokens"]), RUNNER.DEPTHS)

    def test_model_runtime_and_reference_are_checksum_pinned(self) -> None:
        self.assertEqual(
            self.manifest["model"]["sha256"], RUNNER.ENGINE.MODEL_SHA256
        )
        self.assertEqual(
            self.manifest["runtime"]["binary"]["sha256"],
            RUNNER.ENGINE.BINARY_SHA256,
        )
        self.assertEqual(
            self.manifest["runtime"]["sycl_backend"]["sha256"],
            RUNNER.BASE.SYCL_DSO_SHA256,
        )
        self.assertEqual(
            RUNNER.ENGINE.sha256_file(RUNNER.BASE_MANIFEST),
            RUNNER.BASE_MANIFEST_SHA256,
        )
        self.assertEqual(
            RUNNER.ENGINE.sha256_file(RUNNER.BASE_ADAPTER),
            RUNNER.BASE_ADAPTER_SHA256,
        )

    def test_argv_is_target_only_f16_exact_depth(self) -> None:
        argv = list(RUNNER.ARGV)
        self.assertEqual(argv[argv.index("-ctk") + 1], "f16")
        self.assertEqual(argv[argv.index("-ctv") + 1], "f16")
        self.assertEqual(
            argv[argv.index("-d") + 1],
            "0,2048,4096,8192,16384,24576,32768",
        )
        self.assertNotIn("--spec-type", argv)
        self.assertNotIn("--spec-draft-n-max", argv)

    def test_fresh_root_is_isolated_from_both_q8_roots(self) -> None:
        self.assertFalse(RUNNER.RUN_ROOT.exists())
        self.assertNotEqual(RUNNER.RUN_ROOT, RUNNER.BASE.RUN_ROOT)
        self.assertNotEqual(RUNNER.RUN_ROOT, RUNNER.BASE.R1_ROOT)
        note = self.manifest["runtime_reference"]["scope"]
        self.assertIn("No q8_0 timing row", note)

    def test_coordination_has_all_four_locks_and_batched_exclusion(self) -> None:
        self.assertEqual(
            RUNNER.CANONICAL_LOCKS,
            [
                "/run/lock/muse-glimmer-gpu-exclusive.lock",
                "/tmp/b70-benchmark.lock",
                "/tmp/b70-gpu0.lock",
                "/run/user/1000/qwen36-b70-gpu-leases/gpu0.lock",
            ],
        )
        lock_source = inspect.getsource(RUNNER.BASE.campaign_locks)
        idle_source = inspect.getsource(RUNNER.BASE.verify_idle)
        self.assertIn("/tmp/b70-gpu0.lock", lock_source)
        self.assertIn("qwen36-b70-gpu-leases/gpu0.lock", lock_source)
        self.assertIn("[l]lama-batched-bench", idle_source)

    def test_metadata_is_f16_and_parser_compatible(self) -> None:
        environment = RUNNER.ENGINE.effective_environment(Path("/tmp/q36-f16-test"))
        metadata = RUNNER.metadata(environment)
        self.assertEqual(metadata["receipt_id"], RUNNER.CAMPAIGN_ID)
        self.assertEqual(metadata["cell_selectors"]["kv"], "f16")
        self.assertEqual(metadata["argv"], list(RUNNER.ARGV))
        self.assertFalse(metadata["graph"]["requested"])
        self.assertFalse(
            metadata["graph"]["static_attestation"]["runtime_stderr_markers_used"]
        )

    def test_terminal_writer_remains_create_only_and_q8_free(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            receipt = RUNNER.terminal_receipt(
                status="passed",
                stage="complete",
                started="2026-08-25T00:00:00+00:00",
                repo_head="0" * 40,
                locks=RUNNER.CANONICAL_LOCKS,
                libraries=[],
                detail={"passed": True},
            )
            self.assertFalse(receipt["q8_rows_reused"])
            self.assertFalse(receipt["q8_run_roots_touched"])
            path = root / "terminal-receipt.json"
            RUNNER.ENGINE.create_bytes(path, RUNNER.ENGINE.canonical_bytes(receipt))
            with self.assertRaises(RUNNER.CampaignError):
                RUNNER.ENGINE.create_bytes(
                    path, RUNNER.ENGINE.canonical_bytes({"status": "overwrite"})
                )

    def test_default_plan_is_inert(self) -> None:
        before = RUNNER.RUN_ROOT.exists()
        result = subprocess.run(
            [sys.executable, "-B", str(SCRIPT)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "planned-not-launched")
        self.assertFalse(payload["writes_performed"])
        self.assertEqual(RUNNER.RUN_ROOT.exists(), before)


if __name__ == "__main__":
    unittest.main()
