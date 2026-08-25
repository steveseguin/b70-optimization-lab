#!/usr/bin/env python3
"""CPU-only tests for the frozen Qwen3.6 Q4_0 exact-depth packet."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "run-20260825-qwen36-q4-0-tp1-mtp0-q8kv-exact-depth-r1.py"
REPO = HERE.parents[2]
PARSER_PATH = REPO / "scripts/parse-llama-bench-exact-depth.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


RUNNER = load_module("qwen36_q4_0_exact_depth_runner", SCRIPT)
sys.path.insert(0, str(PARSER_PATH.parent))
RECEIPT_PARSER = load_module("qwen36_q4_0_exact_depth_receipt_parser", PARSER_PATH)


class FrozenContractTests(unittest.TestCase):
    def test_manifest_matches_frozen_contract(self) -> None:
        manifest = RUNNER.load_json(RUNNER.MANIFEST)
        RUNNER.validate_manifest(manifest)
        identity = manifest["run_identity"]
        self.assertIsNone(identity["artifact_revision"])
        self.assertIn("must not inherit", identity["artifact_revision_status"])
        self.assertEqual(identity["mtp_depth"], 0)
        self.assertEqual(identity["graph_mode"], "off")
        self.assertEqual(identity["kv_cache_dtype"], "q8_0")
        self.assertIsNone(manifest["benchmark_contract"]["speed_floor"])
        self.assertFalse(manifest["benchmark_contract"]["cross_quant_transfer_allowed"])

    def test_argv_is_exact_target_only_seven_depth_shape(self) -> None:
        self.assertEqual(
            RUNNER.ARGV,
            (
                str(RUNNER.BINARY),
                "-m",
                str(RUNNER.MODEL),
                "-dev",
                "SYCL0",
                "-ngl",
                "99",
                "-sm",
                "layer",
                "-p",
                "2048",
                "-n",
                "128",
                "-d",
                "0,2048,4096,8192,16384,24576,32768",
                "-b",
                "2048",
                "-ub",
                "512",
                "-fa",
                "on",
                "-ctk",
                "q8_0",
                "-ctv",
                "q8_0",
                "-t",
                "16",
                "--poll",
                "50",
                "-r",
                "5",
                "-o",
                "json",
            ),
        )
        self.assertNotIn("--spec-type", RUNNER.ARGV)
        self.assertNotIn("--spec-draft-n-max", RUNNER.ARGV)

    def test_metadata_is_parser_valid_and_honest_about_quality(self) -> None:
        env = RUNNER.effective_environment(Path("/tmp/frozen-depth-test"))
        metadata = RUNNER.metadata(env)
        validated = RECEIPT_PARSER.validate_metadata(metadata)
        self.assertEqual(validated["declared_depths"], list(RUNNER.DEPTHS))
        self.assertEqual(validated["graph"]["classification"], "off")
        self.assertEqual(validated["cell_selectors"]["mtp"], 0)
        self.assertEqual(validated["cell_selectors"]["kv"], "q8_0")
        self.assertNotIn("active_context_tokens", validated["cell_selectors"])
        manifest = RUNNER.load_json(RUNNER.MANIFEST)
        self.assertEqual(
            manifest["quality_boundary"]["current_packet_quality_state"],
            "not-tested",
        )
        self.assertIn("not transferred", manifest["quality_boundary"]["disclosure"])

    def test_inherited_runtime_controls_are_rejected(self) -> None:
        inherited = {
            "PATH": "/usr/bin",
            "GGML_SYCL_ENABLE_GRAPH": "1",
            "LLAMA_MTP_DEVICE_UNROLL": "1",
            "ZE_AFFINITY_MASK": "3",
            "OMP_NUM_THREADS": "64",
            "LD_LIBRARY_PATH": "/tmp/other",
        }
        self.assertEqual(
            RUNNER.reject_inherited_environment(inherited),
            [
                "GGML_SYCL_ENABLE_GRAPH",
                "LD_LIBRARY_PATH",
                "LLAMA_MTP_DEVICE_UNROLL",
                "OMP_NUM_THREADS",
                "ZE_AFFINITY_MASK",
            ],
        )
        controlled = RUNNER.effective_environment(Path("/tmp/run"))
        self.assertEqual(controlled["GGML_SYCL_ENABLE_GRAPH"], "0")
        self.assertEqual(controlled["GGML_SYCL_GRAPH_CACHE_SIZE"], "0")
        self.assertEqual(controlled["ONEAPI_DEVICE_SELECTOR"], "level_zero:*")
        self.assertEqual(controlled["ZE_AFFINITY_MASK"], "0")

    def test_ldd_parser_requires_resolved_absolute_unique_rows(self) -> None:
        parsed = RUNNER.parse_ldd_output(
            """
            linux-vdso.so.1 (0x1)
            libm.so.6 => /lib/x86_64-linux-gnu/libm.so.6 (0x2)
            /lib64/ld-linux-x86-64.so.2 (0x3)
            """
        )
        self.assertEqual(set(parsed), {"libm.so.6", "ld-linux-x86-64.so.2"})
        with self.assertRaisesRegex(RUNNER.CampaignError, "unresolved"):
            RUNNER.parse_ldd_output("libexample.so.1 => not found")
        with self.assertRaisesRegex(RUNNER.CampaignError, "duplicate"):
            RUNNER.parse_ldd_output(
                "libm.so.6 => /lib/x86_64-linux-gnu/libm.so.6 (0x1)\n"
                "libm.so.6 => /lib/x86_64-linux-gnu/libm.so.6 (0x2)\n"
            )

    def test_graph_off_requires_both_runtime_markers(self) -> None:
        RUNNER.verify_graph_off_log(
            "GGML_SYCL_ENABLE_GRAPH: 0\nGGML_SYCL_GRAPH_CACHE_SIZE: 0\n"
        )
        with self.assertRaisesRegex(RUNNER.CampaignError, "GRAPH_CACHE_SIZE"):
            RUNNER.verify_graph_off_log("GGML_SYCL_ENABLE_GRAPH: 0\n")

    def test_create_only_helper_never_overwrites(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            target = Path(value) / "receipt.json"
            RUNNER.create_bytes(target, b"first\n")
            self.assertEqual(target.read_bytes(), b"first\n")
            with self.assertRaisesRegex(RUNNER.CampaignError, "overwrite"):
                RUNNER.create_bytes(target, b"second\n")
            self.assertEqual(target.read_bytes(), b"first\n")

    def test_terminal_receipt_preserves_evidence_boundaries(self) -> None:
        receipt = RUNNER.terminal_receipt(
            status="passed",
            stage="complete",
            started="2026-08-25T00:00:00+00:00",
            repo_head="a" * 40,
            locks=["/tmp/lock"],
            libraries=[],
            detail={"cell_count": 7},
        )
        self.assertEqual(receipt["measurement_class"], "raw-engine")
        self.assertFalse(receipt["is_http_serving_metric"])
        self.assertEqual(receipt["current_packet_quality_state"], "not-tested")
        self.assertFalse(
            receipt["historical_quality_citation"]["transferred_to_current_cells"]
        )
        self.assertIsNone(receipt["speed_floor"])

    def test_plan_mode_is_inert_and_wrong_ack_fails_before_launch(self) -> None:
        before = RUNNER.RUN_ROOT.exists()
        result = subprocess.run(
            [sys.executable, "-B", str(SCRIPT)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["mode"], "plan")
        self.assertFalse(payload["writes_performed"])
        self.assertEqual(RUNNER.RUN_ROOT.exists(), before)
        with self.assertRaisesRegex(RUNNER.CampaignError, "acknowledgement"):
            RUNNER.execute("wrong")


if __name__ == "__main__":
    unittest.main()
