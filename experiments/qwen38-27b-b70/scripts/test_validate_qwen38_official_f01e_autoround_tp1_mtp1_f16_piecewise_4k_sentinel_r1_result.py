#!/usr/bin/env python3
"""Tests for the TP1/MTP1 PIECEWISE exact-4K raw validator."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
VALIDATOR = HERE / "validate-20260826-qwen38-official-f01e-autoround-tp1-mtp1-f16-piecewise-4k-sentinel-r1-result.py"
SPEC = importlib.util.spec_from_file_location("validator", VALIDATOR)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class ValidatorTests(unittest.TestCase):
    def test_raw_packet_passes(self):
        report = MODULE.validate(MODULE.ROOT, MODULE.RESULT)
        self.assertEqual(report["cells_published"], 1)
        self.assertEqual(report["exact_context"], 4096)
        self.assertEqual(report["graph_mode"], "PIECEWISE")
        self.assertTrue(report["dual_parent_parity"])

    def mutate_result(self, mutate):
        value = json.loads(MODULE.RESULT.read_text())
        mutate(value)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.json"
            path.write_text(json.dumps(value))
            with self.assertRaises(RuntimeError):
                MODULE.validate(MODULE.ROOT, path)

    def test_rejects_speed_change(self):
        self.mutate_result(lambda value: value["point"].__setitem__("decode_tok_s", 9.0))

    def test_rejects_scope_expansion(self):
        self.mutate_result(lambda value: value["human_adjudication"]["selected_depths"].append(8192))

    def test_rejects_protected_replacement(self):
        self.mutate_result(lambda value: value["authority"].__setitem__("historical_or_protected_replacement", True))


if __name__ == "__main__":
    unittest.main()
