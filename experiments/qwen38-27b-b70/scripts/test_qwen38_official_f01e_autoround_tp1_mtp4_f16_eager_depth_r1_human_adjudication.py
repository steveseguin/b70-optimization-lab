#!/usr/bin/env python3
"""Contract tests for the additive TP1/MTP4 depth adjudication."""

from __future__ import annotations

import copy
import hashlib
import json
import runpy
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen38-27b-b70"
RESULT = LANE / "data/2026-08-26-qwen38-official-f01e-autoround-tp1-mtp4-f16-eager-depth-r1-human-adjudication-result.json"
VALIDATOR = LANE / "scripts/validate-20260826-qwen38-official-f01e-autoround-tp1-mtp4-f16-eager-depth-r1-human-adjudication.py"


def digest(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class AdjudicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = json.loads(RESULT.read_text(encoding="utf-8"))
        cls.validate = staticmethod(
            runpy.run_path(str(VALIDATOR), run_name="adjudication_validator_test")["validate"]
        )

    def test_composed_validator_passes(self):
        self.assertEqual(
            self.validate(RESULT),
            {
                "status": "pass",
                "lab_screened": 3,
                "lab_measured": 0,
                "quarantined": 2,
                "closed": 1,
                "missing": 1,
                "selected_speed_depths": [4096, 16384, 24576],
            },
        )

    def test_both_immutable_sources_and_validators_are_pinned(self):
        for binding in self.result["source_artifacts"].values():
            self.assertEqual(digest(REPO / binding["result_path"]), binding["result_sha256"])
            self.assertEqual(digest(REPO / binding["validator_path"]), binding["validator_sha256"])
            self.assertTrue(Path(binding["raw_root"]).is_dir())
            self.assertEqual(len(binding["terminal_receipt_sha256"]), 64)
            self.assertEqual(len(binding["arm_result_sha256"]), 64)

    def test_exact_conservative_mapping_and_no_selected_bad_speeds(self):
        cells = {cell["x"]: cell for cell in self.result["cells"]}
        self.assertEqual(
            {depth: cell["publication_state"] for depth, cell in cells.items()},
            {0: "missing", 2048: "quarantined", 4096: "lab-screened", 8192: "quarantined", 16384: "lab-screened", 24576: "lab-screened", 32768: "closed"},
        )
        self.assertEqual(
            [cells[x]["decode_tok_s"] for x in (4096, 16384, 24576)],
            [14.850597409841217, 12.361817762397319, 13.116686989341177],
        )
        for depth in (2048, 8192, 32768):
            self.assertNotIn("decode_tok_s", cells[depth])
            self.assertNotIn("ttft_s", cells[depth])
            self.assertFalse(cells[depth]["speed_publication_authorized"])
        self.assertEqual(cells[32768]["returned_tokens"], 121)
        self.assertFalse(cells[32768]["usage_present"])

    def test_cross_boot_conflict_preserves_both_receipts(self):
        conflict = next(cell for cell in self.result["cells"] if cell["x"] == 8192)["cross_boot_conflict"]
        self.assertTrue(conflict["passed_parent"]["target_parity_passed"])
        self.assertEqual(conflict["passed_parent"]["quality_grade"], "C")
        self.assertFalse(conflict["later_expansion"]["target_parity_passed"])
        self.assertEqual(conflict["later_expansion"]["first_divergence"]["one_based"], 99)
        self.assertNotEqual(conflict["later_expansion"]["candidate_token_ids_sha256"], conflict["later_expansion"]["target_token_ids_sha256"])

    def test_authority_is_additive_and_protected_values_are_exact(self):
        authority = self.result["authority"]
        self.assertEqual(authority["lab_screened_speed_cells"], 3)
        self.assertEqual(authority["lab_measured_cells"], 0)
        self.assertFalse(authority["headline_or_protected_replacement"])
        self.assertFalse(authority["parent_8k_speed_selection"])
        self.assertEqual(authority["protected_decode_values_unchanged"], [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144])

    def test_validator_rejects_boundary_mutations(self):
        mutations = []
        changed = copy.deepcopy(self.result)
        next(cell for cell in changed["cells"] if cell["x"] == 4096)["decode_tok_s"] = 99.0
        mutations.append(changed)
        changed = copy.deepcopy(self.result)
        next(cell for cell in changed["cells"] if cell["x"] == 8192)["decode_tok_s"] = 15.694764790035633
        mutations.append(changed)
        changed = copy.deepcopy(self.result)
        next(cell for cell in changed["cells"] if cell["x"] == 8192)["cross_boot_conflict"]["passed_parent"]["target_parity_passed"] = False
        mutations.append(changed)
        changed = copy.deepcopy(self.result)
        next(cell for cell in changed["cells"] if cell["x"] == 32768)["publication_state"] = "lab-screened"
        mutations.append(changed)
        changed = copy.deepcopy(self.result)
        changed["authority"]["protected_decode_values_unchanged"][0] = 0
        mutations.append(changed)
        changed = copy.deepcopy(self.result)
        changed["source_artifacts"]["expansion"]["result_sha256"] = "0" * 64
        mutations.append(changed)

        for index, payload in enumerate(mutations):
            with self.subTest(index=index), tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "mutated.json"
                path.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaises(RuntimeError):
                    self.validate(path)


if __name__ == "__main__":
    unittest.main()
