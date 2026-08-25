#!/usr/bin/env python3
"""CPU-only contract tests for target-only Qwen3.6 Q8_0 q8_0 packet."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).with_name(
    "run-20260825-qwen36-q8-q8kv-tp1-exact-depth-r1.py"
)
SPEC = importlib.util.spec_from_file_location("qwen36_q8_q8kv_runner", SCRIPT)
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

    def test_exact_target_only_q8_seven_cell_identity(self) -> None:
        selectors = self.manifest["selectors"]
        self.assertEqual(selectors["revision"], "qwen3.6-27b")
        self.assertEqual(
            selectors["artifact_id"], "qwen36-27b-unsloth-q8-0-82d411a"
        )
        self.assertEqual(selectors["quantization"], "Q8_0")
        self.assertEqual(selectors["tp"], 1)
        self.assertEqual(selectors["mtp"], 0)
        self.assertEqual(selectors["graph_mode"], "off")
        self.assertEqual(selectors["kv"], "q8_0")
        self.assertEqual(selectors["active_context_tokens"], RUNNER.DEPTHS)

    def test_model_and_both_read_views_are_pinned(self) -> None:
        model = self.manifest["model"]
        expected = "f93f517f38e696d35a1a7df2c0e3155a64f4c4dcd662107a146ae263f7fb14ce"
        self.assertEqual(model["repository"], "unsloth/Qwen3.6-27B-GGUF")
        self.assertEqual(
            model["revision"], "82d411acf4a06cfb8d9b073a5211bf410bfc29bf"
        )
        self.assertEqual(model["size_bytes"], 28595763424)
        self.assertEqual(model["sha256"], expected)
        self.assertEqual(model["direct_sha256"], expected)
        self.assertEqual(model["ordinary_sha256"], expected)
        self.assertFalse(model["embedded_mtp_capability"])

    def test_f16_reference_and_runtime_are_checksum_pinned(self) -> None:
        self.assertEqual(
            RUNNER.ENGINE.sha256_file(RUNNER.REFERENCE_MANIFEST),
            RUNNER.REFERENCE_MANIFEST_SHA256,
        )
        self.assertEqual(
            RUNNER.ENGINE.sha256_file(RUNNER.REFERENCE_ADAPTER),
            RUNNER.REFERENCE_ADAPTER_SHA256,
        )
        runtime = self.manifest["runtime"]
        self.assertEqual(runtime["source_head"], RUNNER.ENGINE.SOURCE_HEAD)
        self.assertEqual(
            runtime["binary"]["sha256"],
            "908b78b77fc28ad23b2924b7f32f56f4a8415eac9c2a79a244dee85b49b19030",
        )
        self.assertEqual(len(runtime["effective_shared_libraries"]), 32)

    def test_target_only_q8_argv_and_graph_off(self) -> None:
        argv = self.manifest["argv"]
        self.assertEqual(
            argv[argv.index("-d") + 1], "0,2048,4096,8192,16384,24576,32768"
        )
        self.assertEqual(argv[argv.index("-ctk") + 1], "q8_0")
        self.assertEqual(argv[argv.index("-ctv") + 1], "q8_0")
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
        self.assertIs(RUNNER.ENGINE.preflight, RUNNER.REFERENCE.REFERENCE.preflight)
        interpretation = self.manifest["interpretation"]
        self.assertIsNone(interpretation["speed_floor"])
        self.assertFalse(interpretation["new_quality_gate"])
        self.assertFalse(interpretation["site_publication_authorized"])
        self.assertFalse(interpretation["record_or_submission_authorized"])
        self.assertFalse(interpretation["quality_claim_authorized"])

    def test_repaired_process_scanner_ignores_evidence_names(self) -> None:
        classifier = RUNNER.REFERENCE.REFERENCE.REFERENCE.is_active_model_process
        self.assertFalse(
            classifier("sha256sum", ["sha256sum", "/tmp/llama-bench.json"])
        )
        self.assertFalse(classifier("rg", ["rg", "VLLM::EngineCore", "/tmp/log"]))
        self.assertTrue(classifier("llama-server", ["/opt/llama-server"]))

    def test_metadata_is_q8_scoped_and_requires_model_view_receipt(self) -> None:
        RUNNER.REFERENCE.REFERENCE._MODEL_VIEW_RECEIPT = None
        with self.assertRaisesRegex(RUNNER.ENGINE.GateError, "receipt is absent"):
            RUNNER.metadata(
                self.manifest, self.manifest["runtime"]["effective_shared_libraries"]
            )
        expected = self.manifest["model"]["sha256"]
        RUNNER.REFERENCE.REFERENCE._MODEL_VIEW_RECEIPT = {
            "status": "verified",
            "direct_sha256": expected,
            "ordinary_sha256": expected,
            "views_coherent": True,
        }
        metadata = RUNNER.metadata(
            self.manifest, self.manifest["runtime"]["effective_shared_libraries"]
        )
        self.assertEqual(metadata["receipt_id"], RUNNER.CAMPAIGN_ID)
        self.assertEqual(metadata["cell_selectors"]["kv"], "q8_0")
        self.assertFalse(metadata["model"]["embedded_mtp_capability"])
        self.assertTrue(metadata["model_view_verification"]["views_coherent"])

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
