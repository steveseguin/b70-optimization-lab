#!/usr/bin/env python3
"""CPU-only contract tests for the Qwen3.6 MTP-Q8 F16 depth packet."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).with_name(
    "run-20260825-qwen36-mtpq8-f16-tp1-exact-depth-r1.py"
)
SPEC = importlib.util.spec_from_file_location("qwen36_mtpq8_f16_runner", SCRIPT)
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

    def test_exact_qwen36_mtpq8_seven_cell_identity(self) -> None:
        selectors = self.manifest["selectors"]
        self.assertEqual(selectors["revision"], "qwen3.6-27b")
        self.assertEqual(
            selectors["artifact_id"], "qwen36-27b-unsloth-mtp-q8-0-5cb35eb"
        )
        self.assertEqual(selectors["quantization"], "Q8_0")
        self.assertEqual(selectors["tp"], 1)
        self.assertEqual(selectors["mtp"], 0)
        self.assertEqual(selectors["graph_mode"], "off")
        self.assertEqual(selectors["kv"], "f16")
        self.assertEqual(selectors["active_context_tokens"], RUNNER.DEPTHS)

    def test_model_and_both_read_views_are_pinned(self) -> None:
        model = self.manifest["model"]
        expected = "9408dcb356cc061a05c139e5647cbde0698ff980c6a69f7fc214e9989f86cfa8"
        self.assertEqual(model["size_bytes"], 29047084160)
        self.assertEqual(model["sha256"], expected)
        self.assertEqual(model["direct_sha256"], expected)
        self.assertEqual(model["ordinary_sha256"], expected)
        self.assertTrue(model["embedded_mtp_capability"])
        self.assertEqual(
            RUNNER.ENGINE.sha256_file(RUNNER.MODEL_VERIFIER),
            RUNNER.MODEL_VERIFIER_SHA256,
        )

    def test_runtime_binary_libraries_and_repaired_adapter_are_pinned(self) -> None:
        runtime = self.manifest["runtime"]
        self.assertEqual(runtime["source_head"], RUNNER.ENGINE.SOURCE_HEAD)
        self.assertEqual(
            runtime["binary"]["sha256"],
            "908b78b77fc28ad23b2924b7f32f56f4a8415eac9c2a79a244dee85b49b19030",
        )
        self.assertEqual(len(runtime["effective_shared_libraries"]), 32)
        self.assertEqual(
            RUNNER.ENGINE.sha256_file(RUNNER.REFERENCE_MANIFEST),
            RUNNER.REFERENCE_MANIFEST_SHA256,
        )
        self.assertEqual(
            RUNNER.ENGINE.sha256_file(RUNNER.REFERENCE_ADAPTER),
            RUNNER.REFERENCE_ADAPTER_SHA256,
        )
        self.assertIs(
            RUNNER.ENGINE.active_model_processes,
            RUNNER.REFERENCE.active_model_processes,
        )

    def test_target_only_f16_argv_and_graph_off(self) -> None:
        argv = self.manifest["argv"]
        self.assertEqual(
            argv[argv.index("-d") + 1], "0,2048,4096,8192,16384,24576,32768"
        )
        self.assertEqual(argv[argv.index("-ctk") + 1], "f16")
        self.assertEqual(argv[argv.index("-ctv") + 1], "f16")
        self.assertNotIn("--spec-type", argv)
        self.assertEqual(self.manifest["environment"]["GGML_SYCL_ENABLE_GRAPH"], "0")

    def test_create_only_coordination_and_claim_boundaries(self) -> None:
        lifecycle = self.manifest["lifecycle"]
        self.assertTrue(lifecycle["requires_clean_pushed_main"])
        self.assertTrue(lifecycle["requires_no_server_or_container"])
        self.assertEqual(lifecycle["output_fstype"], "ext4")
        self.assertEqual(lifecycle["timeout_seconds"], 5400)
        self.assertTrue(lifecycle["artifacts_are_create_only"])
        self.assertTrue(lifecycle["terminal_receipt_required"])
        self.assertEqual(lifecycle["required_locks"], RUNNER.CANONICAL_LOCKS)
        interpretation = self.manifest["interpretation"]
        self.assertIsNone(interpretation["speed_floor"])
        self.assertFalse(interpretation["new_quality_gate"])
        self.assertFalse(interpretation["site_publication_authorized"])
        self.assertFalse(interpretation["record_or_submission_authorized"])
        self.assertFalse(interpretation["quality_claim_authorized"])

    def test_repaired_process_scanner_ignores_evidence_names(self) -> None:
        classifier = RUNNER.REFERENCE.is_active_model_process
        self.assertFalse(
            classifier("sha256sum", ["sha256sum", "/tmp/llama-bench.json"])
        )
        self.assertFalse(classifier("tail", ["tail", "-f", "/tmp/vllm serve.log"]))
        self.assertTrue(classifier("llama-batched-b", ["/opt/llama-batched-bench"]))

    def test_preflight_orders_direct_before_inherited_ordinary_check(self) -> None:
        expected = self.manifest["model"]["direct_sha256"]
        order: list[str] = []

        def direct(_: Path):
            order.append("direct")
            return expected, "mock-odirect"

        def inherited(_: dict):
            order.append("ordinary")
            return "head", {}, self.manifest["runtime"]["effective_shared_libraries"]

        with (
            mock.patch.object(RUNNER.ENGINE, "reject_inherited_runtime_environment"),
            mock.patch.object(RUNNER.ENGINE, "require_clean_pushed_main"),
            mock.patch.object(
                RUNNER.ENGINE,
                "git_output",
                side_effect=[RUNNER.ENGINE.SOURCE_HEAD, ""],
            ),
            mock.patch.object(RUNNER.VERIFIER, "hash_direct", side_effect=direct),
            mock.patch.object(RUNNER, "ORIGINAL_ENGINE_PREFLIGHT", side_effect=inherited),
        ):
            RUNNER.preflight(self.manifest)
        self.assertEqual(order, ["direct", "ordinary"])
        self.assertEqual(RUNNER._MODEL_VIEW_RECEIPT["status"], "verified")
        self.assertTrue(RUNNER._MODEL_VIEW_RECEIPT["views_coherent"])

    def test_terminal_schema_is_qwen36_and_writer_is_exclusive(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            path = Path(value) / "terminal-receipt.json"
            RUNNER.write_json_exclusive(path, {"state": "passed"})
            receipt = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(
                receipt["schema"],
                "neural.download.qwen36-llama-exact-depth-terminal.v1",
            )
            self.assertFalse(receipt["site_publication_authorized"])
            self.assertFalse(receipt["record_or_submission_authorized"])
            self.assertFalse(receipt["quality_claim_authorized"])
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
