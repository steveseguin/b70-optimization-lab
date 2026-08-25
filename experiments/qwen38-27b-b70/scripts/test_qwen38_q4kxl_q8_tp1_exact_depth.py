#!/usr/bin/env python3
"""CPU-only contract tests for the Qwen3.8 Q4XL exact-depth launcher."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("run-20260825-qwen38-q4kxl-q8-tp1-exact-depth-r1.py")
SPEC = importlib.util.spec_from_file_location("qwen38_q4xl_depth_runner", SCRIPT)
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

    def test_exact_seven_depth_argv(self) -> None:
        argv = self.manifest["argv"]
        self.assertEqual(
            argv[argv.index("-d") + 1],
            "0,2048,4096,8192,16384,24576,32768",
        )
        self.assertEqual(argv[-4:], ["-r", "5", "-o", "json"])
        self.assertEqual(argv[argv.index("-ctk") + 1], "q8_0")
        self.assertEqual(argv[argv.index("-ctv") + 1], "q8_0")
        self.assertEqual(argv[argv.index("-sm") + 1], "layer")

    def test_runtime_environment_is_graph_off_and_exact(self) -> None:
        environment = self.manifest["environment"]
        self.assertEqual(environment["ONEAPI_DEVICE_SELECTOR"], "level_zero:0")
        self.assertEqual(environment["GGML_SYCL_ENABLE_GRAPH"], "0")
        self.assertNotIn("ZE_AFFINITY_MASK", environment)
        self.assertNotIn("XPU_GRAPH", environment)
        self.assertEqual(environment["GGML_SYCL_FUSE_EXT"], "31")

    def test_complete_effective_library_inventory(self) -> None:
        rows = self.manifest["runtime"]["effective_shared_libraries"]
        self.assertEqual(len(rows), 32)
        hashes = {row[0]: row[3] for row in rows}
        expected = {
            "libllama-bench-impl.so": "c21080b126440203a3e930cec32e289e388869f1cc0825a8266049d7980ac56a",
            "libggml-base.so.0": "131981ff0c2052e0ae5e8172a2d5acd2eb9756e218db20817501fb704668483a",
            "libggml-cpu.so.0": "8ddab8fd6c96a574ef0454dd02b595b517bef119cd423f59fcc61971c6101863",
            "libggml-sycl.so.0": "4c9c74743dd87d35850adece253351bca6bf44dd90b8c70766ef3c92cd2acaf0",
            "libggml.so.0": "facf9e3be0cbe9d6cd3dc022e2de63f84f5d7fa1ce71a8ce2ff4662abcd38afc",
            "libllama-common.so.0": "261ab40059d154ccde8ad402cab0c7b7f64543519f7774ee20ca2b63adb4ff59",
            "libllama.so.0": "5f8a26e8186fa210761ab522f07eb23fa750acdf29f9378b983e6f4f996af2f5",
        }
        for soname, digest in expected.items():
            self.assertEqual(hashes[soname], digest)

    def test_metadata_is_parser_compatible_and_quality_scoped(self) -> None:
        metadata = RUNNER.metadata(
            self.manifest,
            self.manifest["runtime"]["effective_shared_libraries"],
        )
        self.assertEqual(metadata["graph"]["requested"], False)
        self.assertEqual(metadata["declared_depths"][0], 0)
        self.assertNotIn("active_context_tokens", metadata["cell_selectors"])
        self.assertFalse(self.manifest["interpretation"]["new_quality_gate"])
        self.assertIsNone(self.manifest["interpretation"]["speed_floor"])

    def test_inherited_runtime_variables_fail_closed(self) -> None:
        with self.assertRaisesRegex(RUNNER.GateError, "GGML_SYCL_ENABLE_GRAPH"):
            RUNNER.reject_inherited_runtime_environment(
                {"PATH": "/usr/bin", "GGML_SYCL_ENABLE_GRAPH": "1"}
            )
        RUNNER.reject_inherited_runtime_environment({"PATH": "/usr/bin"})

    def test_exclusive_writer_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            path = Path(value) / "receipt.json"
            RUNNER.write_json_exclusive(path, {"state": "first"})
            with self.assertRaises(FileExistsError):
                RUNNER.write_json_exclusive(path, {"state": "second"})

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
