#!/usr/bin/env python3
"""CPU-only contract tests for the Qwen3.8 Q8-weight/F16-KV packet."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).with_name(
    "run-20260825-qwen38-q8weights-f16-tp1-exact-depth-r1.py"
)
SPEC = importlib.util.spec_from_file_location("qwen38_q8weights_f16_runner", SCRIPT)
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

    def test_exact_seven_depth_f16_argv(self) -> None:
        argv = self.manifest["argv"]
        self.assertEqual(
            argv[argv.index("-d") + 1],
            "0,2048,4096,8192,16384,24576,32768",
        )
        self.assertEqual(argv[argv.index("-ctk") + 1], "f16")
        self.assertEqual(argv[argv.index("-ctv") + 1], "f16")
        self.assertEqual(argv[argv.index("-sm") + 1], "layer")
        self.assertEqual(argv[-4:], ["-r", "5", "-o", "json"])

    def test_exact_q8_weight_identity_and_unstaged_disclosure(self) -> None:
        selectors = self.manifest["selectors"]
        model = self.manifest["model"]
        self.assertEqual(selectors["artifact_id"], "qwen38-27b-ggmlorg-q8-0-0669b98")
        self.assertEqual(selectors["quantization"], "Q8_0")
        self.assertEqual(model["bytes"], 28595763552)
        self.assertEqual(
            model["sha256"],
            "f5c702d8820d36fb55985bb238fc83ee3a313e920f4b752a437c3a6a9e14e4c8",
        )
        self.assertFalse(model["present_at_preregistration"])

    def test_runtime_identity_is_complete_and_graph_off(self) -> None:
        self.assertEqual(
            len(self.manifest["runtime"]["effective_shared_libraries"]), 32
        )
        environment = self.manifest["environment"]
        self.assertEqual(environment["ONEAPI_DEVICE_SELECTOR"], "level_zero:0")
        self.assertEqual(environment["GGML_SYCL_ENABLE_GRAPH"], "0")
        self.assertNotIn("ZE_AFFINITY_MASK", environment)

    def test_all_canonical_and_legacy_locks_are_frozen(self) -> None:
        self.assertEqual(
            self.manifest["lifecycle"]["lock_paths"],
            [str(path) for path in RUNNER.LOCK_PATHS],
        )
        self.assertIn("/tmp/b70-gpu0.lock", self.manifest["lifecycle"]["lock_paths"])
        self.assertIn(
            "/run/user/1000/qwen36-b70-gpu-leases/gpu0.lock",
            self.manifest["lifecycle"]["lock_paths"],
        )

    def test_batched_bench_is_part_of_process_exclusion(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('"llama-batched-bench" in cmdline', source)

    def test_fit_risk_and_speed_protection_are_explicit(self) -> None:
        self.assertEqual(
            self.manifest["fit_assessment"]["risk"], "tight-unmeasured-fit"
        )
        interpretation = self.manifest["interpretation"]
        self.assertIsNone(interpretation["speed_floor"])
        self.assertTrue(interpretation["historical_featured_speeds_are_immutable"])
        self.assertIn("seven matching missing", interpretation["replace_only"])

    def test_metadata_is_parser_compatible(self) -> None:
        metadata = RUNNER.metadata(
            self.manifest,
            self.manifest["runtime"]["effective_shared_libraries"],
        )
        self.assertFalse(metadata["graph"]["requested"])
        self.assertEqual(metadata["cell_selectors"]["kv"], "f16")
        self.assertEqual(metadata["cell_selectors"]["quantization"], "Q8_0")

    def test_inherited_runtime_variables_fail_closed(self) -> None:
        with self.assertRaisesRegex(RUNNER.GateError, "GGML_SYCL_ENABLE_GRAPH"):
            RUNNER.reject_inherited_runtime_environment(
                {"PATH": "/usr/bin", "GGML_SYCL_ENABLE_GRAPH": "1"}
            )

    def test_exclusive_writer_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            path = Path(value) / "receipt.json"
            RUNNER.write_json_exclusive(path, {"state": "first"})
            with self.assertRaises(FileExistsError):
                RUNNER.write_json_exclusive(path, {"state": "second"})

    def test_default_and_check_modes_are_inert(self) -> None:
        output = Path(self.manifest["lifecycle"]["output_root"])
        self.assertFalse(output.exists())
        for args in ([], ["--check"]):
            result = subprocess.run(
                [sys.executable, "-B", str(SCRIPT), *args],
                check=True,
                text=True,
                capture_output=True,
            )
            payload = json.loads(result.stdout)
            self.assertFalse(output.exists())
            if not args:
                self.assertTrue(payload["default_is_inert"])
            else:
                self.assertEqual(payload["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
