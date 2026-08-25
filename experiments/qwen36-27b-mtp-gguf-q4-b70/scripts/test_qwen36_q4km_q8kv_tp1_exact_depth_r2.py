#!/usr/bin/env python3
"""CPU-only contract tests for the Qwen3.6 Q4_K_M q8_0 r2 packet."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest


SCRIPT = Path(__file__).with_name("run-20260825-qwen36-q4km-q8kv-tp1-exact-depth-r2.py")
SPEC = importlib.util.spec_from_file_location("qwen36_q4km_q8kv_r2_runner", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import {SCRIPT}")
RUNNER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = RUNNER
SPEC.loader.exec_module(RUNNER)


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = RUNNER.load_manifest()
        RUNNER.validate_manifest(cls.manifest)

    def test_r1_is_hash_pinned_and_nonpublishable(self) -> None:
        quarantine = self.manifest["r1_quarantine"]
        self.assertFalse(quarantine["raw_row_reuse_allowed"])
        self.assertEqual(quarantine["cells_publishable_from_r1"], 0)
        self.assertEqual(RUNNER.ENGINE.sha256_file(RUNNER.FAILURE_RECORD), RUNNER.FAILURE_RECORD_SHA256)
        self.assertEqual(RUNNER.ENGINE.sha256_file(RUNNER.FAILURE_NOTE), RUNNER.FAILURE_NOTE_SHA256)

    def test_evidence_filenames_are_not_model_processes(self) -> None:
        fixtures = (
            ("bash", ["/bin/bash", "-lc", "sha256sum /tmp/run/llama-bench.json"]),
            ("sha256sum", ["sha256sum", "/tmp/run/llama-bench.json"]),
            ("tail", ["tail", "-f", "/tmp/run/llama-bench.stderr.log"]),
            ("rg", ["rg", "error", "/tmp/run/llama-batched-bench.log"]),
            ("bash", ["bash", "-lc", "tail -f '/tmp/vllm serve.log'"]),
            ("tail", ["tail", "-f", "/tmp/vllm.entrypoints.log"]),
            ("rg", ["rg", "VLLM::EngineCore", "/tmp/evidence.log"]),
            ("rg", ["rg", "-m", "vllm.entrypoints.log"]),
        )
        for comm, argv in fixtures:
            with self.subTest(comm=comm):
                self.assertFalse(RUNNER.is_active_model_process(comm, argv))

    def test_real_model_executables_are_detected(self) -> None:
        fixtures = (
            ("llama-bench", ["/opt/bin/llama-bench", "-m", "model.gguf"]),
            ("llama-batched-b", ["/opt/bin/llama-batched-bench"]),
            ("llama-server", ["/opt/bin/llama-server"]),
            ("python3", ["python3", "-m", "vllm.entrypoints.openai.api_server"]),
            ("vllm", ["/opt/bin/vllm", "serve", "model"]),
            ("VLLM::EngineCor", ["VLLM::EngineCore"]),
        )
        for comm, argv in fixtures:
            with self.subTest(comm=comm):
                self.assertTrue(RUNNER.is_active_model_process(comm, argv))

    def test_r2_identity_and_create_only_root(self) -> None:
        self.assertEqual(self.manifest["campaign_id"], RUNNER.CAMPAIGN_ID)
        self.assertTrue(self.manifest["lifecycle"]["output_root"].endswith("-r2"))
        self.assertFalse(Path(self.manifest["lifecycle"]["output_root"]).exists())
        self.assertFalse(self.manifest["interpretation"]["r1_rows_transfer_allowed"])

    def test_default_is_inert_and_static_check_passes(self) -> None:
        RUNNER.static_check()
        result = subprocess.run([sys.executable, "-B", str(SCRIPT)], check=True, text=True, capture_output=True)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["default_is_inert"])
        self.assertEqual(payload["ack"], RUNNER.ACK)


if __name__ == "__main__":
    unittest.main()
