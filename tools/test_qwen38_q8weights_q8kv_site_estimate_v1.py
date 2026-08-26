#!/usr/bin/env python3
"""Focused registry/render tests for the Q8_0-weights/Q8_0-KV estimate."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
FAMILY_PATH = REPO_ROOT / "families/qwen-27b.json"
SNAPSHOT_PATH = REPO_ROOT / "data/qwen38-q8weights-q8kv-tp1-context-estimate-v1.json"
SCRIPT = REPO_ROOT / "tools/build-family-pages.py"
SPEC = importlib.util.spec_from_file_location("build_family_pages_for_q8weights_estimate", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SiteEstimateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.family = json.loads(FAMILY_PATH.read_text(encoding="utf-8"))
        cls.snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        cls.estimates = [
            estimate for estimate in cls.family["estimates"]
            if estimate["id"].startswith("q38-q8weights-q8kv-tp1-context-estimate-v1-")
        ]
        cls.contracts = {contract["id"]: contract for contract in cls.family["coverage_contracts"]}

    def test_family_is_valid_and_exactly_seven_cells_are_bound(self) -> None:
        self.assertEqual(MODULE.validate_family(self.family, FAMILY_PATH), [])
        estimated_cells = []
        for contract in self.family["coverage_contracts"]:
            cells, _ = MODULE.expand_coverage_contract(contract)
            estimated_cells.extend(cell for cell in cells if cell["state"] == "estimated")
        self.assertEqual(len(estimated_cells), 7)
        self.assertEqual(
            [cell["selectors"]["active_context_tokens"] for cell in estimated_cells],
            [0, 2048, 4096, 8192, 16384, 24576, 32768],
        )
        self.assertTrue(all(
            cell["selectors"]["artifact_id"] == "qwen38-27b-ggmlorg-q8-0-0669b98"
            and cell["selectors"]["tp"] == 1
            and cell["selectors"]["mtp"] == 0
            and cell["selectors"]["graph_mode"] == "off"
            and cell["selectors"]["kv"] == "q8_0"
            and "evidence_id" not in cell
            for cell in estimated_cells
        ))

    def test_registry_values_are_exact_snapshot_projection(self) -> None:
        self.assertEqual(len(self.estimates), 7)
        snapshot_hash = hashlib.sha256(SNAPSHOT_PATH.read_bytes()).hexdigest()
        by_depth = {point["active_context_tokens"]: point for point in self.snapshot["points"]}
        for estimate in self.estimates:
            point = by_depth[estimate["selectors"]["active_context_tokens"]]
            self.assertEqual(estimate["value"], point["decode_tok_s"]["estimate"])
            self.assertEqual(estimate["interval"]["low"], point["decode_tok_s"]["lower"])
            self.assertEqual(estimate["interval"]["high"], point["decode_tok_s"]["upper"])
            self.assertEqual(estimate["engine"]["snapshot_sha256"], snapshot_hash)
            self.assertTrue(estimate["not_for_promotion"])

    def test_evidence_and_optimization_grades_are_distinct(self) -> None:
        for estimate in self.estimates:
            self.assertEqual(estimate["evidence_grade"]["grade"], "D")
            self.assertEqual(estimate["optimization_maturity"]["state"], "unassessed")
        self.assertEqual(self.snapshot["grades"]["evidence"]["grade"], "D")
        self.assertEqual(self.snapshot["grades"]["optimization_maturity"]["state"], "unassessed")
        self.assertEqual(self.snapshot["authority"]["measured_cells"], 0)
        self.assertEqual(self.snapshot["authority"]["quality_cells"], 0)
        self.assertFalse(self.snapshot["authority"]["promotion"])

    def test_rendered_page_labels_estimates_without_curve_or_measurement_claim(self) -> None:
        rendered = MODULE.family_page(self.family)
        self.assertIn("316/1,793 classified", rendered)
        self.assertIn('class="is-estimated"><b>7</b> estimated', rendered)
        self.assertIn('class="is-missing"><b>1,477</b> missing', rendered)
        # Dense contracts expose the classified count without turning Grade-D
        # points into a public performance curve or measured-result card.
        self.assertNotIn("qwen38-q8weights-q8kv-context-estimator 1.0.0", rendered)
        self.assertNotIn("q38-q8weights-q8kv-tp1-context-estimate-v1", rendered)


if __name__ == "__main__":
    unittest.main()
