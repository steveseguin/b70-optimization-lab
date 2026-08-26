#!/usr/bin/env python3
"""Mutation tests for the qualified TP1/MTP2 PIECEWISE exact-4K validator."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
VALIDATOR = HERE / "validate-20260826-qwen38-official-f01e-autoround-tp1-mtp2-f16-piecewise-4k-sentinel-r1-result.py"
SPEC = importlib.util.spec_from_file_location("validator", VALIDATOR)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class ValidatorTests(unittest.TestCase):
    def test_qualified_packet_passes(self):
        report = MODULE.validate(MODULE.ROOT, MODULE.RESULT)
        self.assertEqual(report["status"], "pass-qualified")
        self.assertFalse(report["runner_cache_gate_enforced"])
        self.assertEqual(report["postrun_cache_audit"], "pass")
        self.assertEqual(report["cells_pending"], 1)
        self.assertEqual(report["cells_published"], 0)
        self.assertEqual((report["accepted"], report["drafted"]), (80, 94))

    def mutate_result(self, mutate):
        value = json.loads(MODULE.RESULT.read_text())
        mutate(value)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.json"
            path.write_text(json.dumps(value))
            with self.assertRaises(RuntimeError):
                MODULE.validate(MODULE.ROOT, path)

    def test_rejects_speed_change(self):
        self.mutate_result(lambda value: value["point"].__setitem__("decode_tok_s", 12.5))

    def test_rejects_lost_runner_defect(self):
        self.mutate_result(lambda value: value["cache_isolation"].__setitem__("original_terminal_enforced_cache_gate", True))

    def test_rejects_cache_audit_hash_change(self):
        self.mutate_result(lambda value: value["cache_isolation"].__setitem__("audit_sha256", "0" * 64))

    def test_rejects_corruption_caveat_change(self):
        self.mutate_result(lambda value: value["historical_corruption_caveats"]["same_image_mtp2_eager"]["2048"]["first_divergence"].__setitem__("one_based", 91))

    def test_rejects_publication_claim(self):
        self.mutate_result(lambda value: value["authority"].__setitem__("site_cells_published_by_this_packet", 1))

    def test_rejects_scope_expansion(self):
        self.mutate_result(lambda value: value["human_adjudication"]["selected_depths"].append(8192))


if __name__ == "__main__":
    unittest.main()
