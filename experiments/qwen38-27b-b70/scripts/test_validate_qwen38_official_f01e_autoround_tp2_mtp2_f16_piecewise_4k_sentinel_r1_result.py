#!/usr/bin/env python3
"""Mutation tests for the pending TP2/MTP2 PIECEWISE/F16 exact-4K validator."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
VALIDATOR = HERE / (
    "validate-20260826-qwen38-official-f01e-autoround-"
    "tp2-mtp2-f16-piecewise-4k-sentinel-r1-result.py"
)
SPEC = importlib.util.spec_from_file_location("validator", VALIDATOR)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class ValidatorTests(unittest.TestCase):
    def test_raw_packet_passes(self):
        report = MODULE.validate(MODULE.ROOT, MODULE.RESULT)
        self.assertEqual(report["terminal_class"], "passed-quality-clean-sentinel")
        self.assertEqual(report["raw_files_bound"], 25)
        self.assertEqual(report["measured_cells_pending_publication"], 1)
        self.assertEqual(report["site_cells_published"], 0)
        self.assertEqual(report["exact_context"], 4096)
        self.assertEqual(report["mtp"], 2)
        self.assertEqual(report["graph_mode"], "PIECEWISE")
        self.assertEqual(report["accepted"], 80)
        self.assertEqual(report["drafted"], 94)
        self.assertTrue(report["dual_parent_parity"])

    def mutate_result(self, mutate):
        value = json.loads(MODULE.RESULT.read_text())
        mutate(value)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.json"
            path.write_text(json.dumps(value))
            with self.assertRaises(RuntimeError):
                MODULE.validate(MODULE.ROOT, path)

    def test_rejects_raw_hash_change(self):
        self.mutate_result(lambda value: value["raw_sha256"].__setitem__("server.log", "0" * 64))

    def test_rejects_raw_manifest_omission(self):
        self.mutate_result(lambda value: value["raw_sha256"].pop("server.log"))

    def test_rejects_speed_change(self):
        self.mutate_result(lambda value: value["point"].__setitem__("decode_tok_s", 19.0))

    def test_rejects_mtp_change(self):
        self.mutate_result(lambda value: value["config"].__setitem__("mtp", 1))

    def test_rejects_parent_hash_change(self):
        self.mutate_result(
            lambda value: value["dual_parent_oracle"].__setitem__("candidate_token_ids_sha256", "0" * 64)
        )

    def test_rejects_publication_claim(self):
        self.mutate_result(
            lambda value: value["authority"].__setitem__("site_cells_published_by_this_packet", 1)
        )

    def test_rejects_scope_expansion(self):
        self.mutate_result(lambda value: value["publication_candidate"]["selected_depths"].append(8192))

    def test_rejects_protected_replacement(self):
        self.mutate_result(
            lambda value: value["authority"].__setitem__("historical_or_protected_replacement", True)
        )


if __name__ == "__main__":
    unittest.main()
