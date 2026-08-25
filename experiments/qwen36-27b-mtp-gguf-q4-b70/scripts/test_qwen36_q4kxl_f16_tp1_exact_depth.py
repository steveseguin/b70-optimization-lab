#!/usr/bin/env python3
"""CPU-only contract tests for the Qwen3.6 UD-Q4_K_XL F16 depth packet."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).with_name(
    "run-20260825-qwen36-q4kxl-f16-tp1-exact-depth-r1.py"
)
SPEC = importlib.util.spec_from_file_location("qwen36_q4kxl_f16_runner", SCRIPT)
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

    def test_exact_qwen36_seven_cell_identity(self) -> None:
        selectors = self.manifest["selectors"]
        self.assertEqual(selectors["revision"], "qwen3.6-27b")
        self.assertEqual(
            selectors["artifact_id"],
            "qwen36-27b-unsloth-mtp-ud-q4-k-xl-4085665",
        )
        self.assertEqual(selectors["quantization"], "UD-Q4_K_XL")
        self.assertEqual(selectors["tp"], 1)
        self.assertEqual(selectors["mtp"], 0)
        self.assertEqual(selectors["graph_mode"], "off")
        self.assertEqual(selectors["kv"], "f16")
        self.assertEqual(selectors["active_context_tokens"], RUNNER.DEPTHS)

    def test_model_revision_size_and_sha_are_pinned(self) -> None:
        model = self.manifest["model"]
        self.assertEqual(
            model["revision"],
            "5cb35eb3dcbf52dbce5f87dbc64df6aaffadcace",
        )
        self.assertEqual(model["size_bytes"], 17909097600)
        self.assertEqual(
            model["sha256"],
            "4085665ee36d82a672a238a43f0e5643f2f0e39f2d7bd5d373f0ef10ecf53095",
        )
        self.assertEqual(
            RUNNER.BASE.sha256_file(RUNNER.BASE_MANIFEST),
            RUNNER.BASE_MANIFEST_SHA256,
        )
        self.assertEqual(
            RUNNER.BASE.sha256_file(RUNNER.BASE_ADAPTER),
            RUNNER.BASE_ADAPTER_SHA256,
        )

    def test_argv_is_target_only_f16_exact_depth(self) -> None:
        argv = self.manifest["argv"]
        self.assertEqual(
            argv[argv.index("-d") + 1],
            "0,2048,4096,8192,16384,24576,32768",
        )
        self.assertEqual(argv[argv.index("-ctk") + 1], "f16")
        self.assertEqual(argv[argv.index("-ctv") + 1], "f16")
        self.assertNotIn("--spec-type", argv)
        self.assertNotIn("--spec-draft-n-max", argv)

    def test_graph_quality_and_speed_boundaries(self) -> None:
        self.assertEqual(
            self.manifest["environment"]["GGML_SYCL_ENABLE_GRAPH"], "0"
        )
        interpretation = self.manifest["interpretation"]
        self.assertFalse(interpretation["new_quality_gate"])
        self.assertIsNone(interpretation["speed_floor"])
        self.assertFalse(interpretation["cross_revision_or_quantization_transfer_allowed"])
        self.assertTrue(interpretation["historical_featured_speeds_are_immutable"])

    def test_coordination_covers_current_and_legacy_gpu0_owners(self) -> None:
        self.assertEqual(
            RUNNER.CANONICAL_LOCKS,
            [
                "/run/lock/muse-glimmer-gpu-exclusive.lock",
                "/tmp/b70-benchmark.lock",
                "/tmp/b70-gpu0.lock",
                "/run/user/1000/qwen36-b70-gpu-leases/gpu0.lock",
            ],
        )
        self.assertIs(RUNNER.BASE.active_model_processes, RUNNER.active_model_processes)
        self.assertIs(RUNNER.BASE.campaign_locks, RUNNER.campaign_locks)

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

    def test_metadata_is_parser_compatible(self) -> None:
        metadata = RUNNER.metadata(
            self.manifest,
            self.manifest["runtime"]["effective_shared_libraries"],
        )
        self.assertFalse(metadata["graph"]["requested"])
        self.assertNotIn("active_context_tokens", metadata["cell_selectors"])
        self.assertEqual(metadata["cell_selectors"]["kv"], "f16")
        self.assertEqual(metadata["model"]["revision"], self.manifest["model"]["revision"])

    def test_terminal_schema_is_qwen36_and_writer_is_exclusive(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            path = Path(value) / "terminal-receipt.json"
            RUNNER.write_json_exclusive(
                path,
                {"schema": "neural.download.qwen38-llama-exact-depth-terminal.v1"},
            )
            receipt = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(
                receipt["schema"],
                "neural.download.qwen36-llama-exact-depth-terminal.v1",
            )
            with self.assertRaises(FileExistsError):
                RUNNER.write_json_exclusive(path, {"state": "overwrite"})

    def test_default_plan_is_inert(self) -> None:
        output = Path(self.manifest["lifecycle"]["output_root"])
        self.assertFalse(output.exists())
        result = subprocess.run(
            [sys.executable, "-B", str(SCRIPT)],
            check=True,
            text=True,
            capture_output=True,
        )
        payload = json.loads(result.stdout)
        self.assertTrue(payload["default_is_inert"])
        self.assertEqual(payload["ack"], RUNNER.ACK)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
