#!/usr/bin/env python3
"""Contract tests for the target-parity-aware TP1 graph adjudication."""

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
RESULT = LANE / "data/2026-08-26-qwen38-official-f01e-autoround-tp1-mtp0-f16-piecewise-depth-r3-human-adjudication-result.json"
VALIDATOR = LANE / "scripts/validate-20260826-qwen38-official-f01e-autoround-tp1-mtp0-f16-piecewise-depth-r3-human-adjudication.py"


def digest(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class AdjudicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = json.loads(RESULT.read_text(encoding="utf-8"))
        cls.validate = staticmethod(runpy.run_path(str(VALIDATOR), run_name="graph_adjudication_test")["validate"])

    def test_composed_validator_passes(self):
        self.assertEqual(
            self.validate(RESULT),
            {"status": "pass", "lab_measured": 5, "quarantined": 1, "missing": 1, "selected_speed_depths": [2048, 4096, 16384, 24576, 32768]},
        )

    def test_original_compact_result_and_validator_are_pinned(self):
        source = self.result["source_artifacts"]["original_compact"]
        self.assertEqual(digest(REPO / source["result_path"]), source["result_sha256"])
        self.assertEqual(digest(REPO / source["validator_path"]), source["validator_sha256"])
        self.assertTrue(Path(source["raw_root"]).is_dir())

    def test_only_five_target_matching_depths_keep_speeds(self):
        cells = {cell["x"]: cell for cell in self.result["cells"]}
        self.assertEqual(
            {depth: cell["publication_state"] for depth, cell in cells.items()},
            {0: "missing", 2048: "lab-measured", 4096: "lab-measured", 8192: "quarantined", 16384: "lab-measured", 24576: "lab-measured", 32768: "lab-measured"},
        )
        self.assertEqual(
            [cells[x]["decode_tok_s"] for x in (2048, 4096, 16384, 24576, 32768)],
            [30.075429359128265, 29.41347238250489, 28.192761390148664, 27.463520678399885, 26.759466347975422],
        )
        self.assertNotIn("decode_tok_s", cells[8192])
        self.assertNotIn("ttft_ms", cells[8192])
        self.assertFalse(cells[8192]["speed_publication_authorized"])

    def test_8k_token99_conflict_is_exact(self):
        cell = next(cell for cell in self.result["cells"] if cell["x"] == 8192)
        self.assertEqual(cell["candidate_token_ids_sha256"], "dd31856f45269d222efe0f6f5f1ac9342b6c9ae55e5ce9129fc02b27abdb7e8e")
        self.assertEqual(cell["target_token_ids_sha256"], "34e792ccf3c1d795b686750f27990de2ca605c22046c97b3fff8ad0a7fc82e53")
        self.assertEqual(cell["first_divergence"], {"zero_based": 98, "one_based": 99, "candidate": 411, "target": 579})

    def test_missing_original_cross_arm_gate_is_disclosed(self):
        controls = self.result["evidence_controls"]
        self.assertTrue(controls["original_validator_passes_but_does_not_compare_arms"])
        self.assertEqual(controls["corrective_gate"], "all 128 PIECEWISE token IDs must equal same-image eager MTP0 at the same exact depth")

    def test_authority_is_additive_and_protected(self):
        authority = self.result["authority"]
        self.assertEqual(authority["lab_measured_speed_cells"], 5)
        self.assertEqual(authority["quarantined_cells"], 1)
        self.assertFalse(authority["headline_or_protected_replacement"])
        self.assertFalse(authority["quarantined_8k_speed_selection"])
        self.assertEqual(authority["protected_decode_values_unchanged"], [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144])

    def test_validator_rejects_boundary_mutations(self):
        mutations = []
        changed = copy.deepcopy(self.result)
        next(cell for cell in changed["cells"] if cell["x"] == 2048)["decode_tok_s"] = 99.0
        mutations.append(changed)
        changed = copy.deepcopy(self.result)
        next(cell for cell in changed["cells"] if cell["x"] == 8192)["decode_tok_s"] = 29.01975248295894
        mutations.append(changed)
        changed = copy.deepcopy(self.result)
        next(cell for cell in changed["cells"] if cell["x"] == 8192)["publication_state"] = "lab-measured"
        mutations.append(changed)
        changed = copy.deepcopy(self.result)
        changed["source_artifacts"]["original_compact"]["validator_sha256"] = "0" * 64
        mutations.append(changed)
        changed = copy.deepcopy(self.result)
        changed["source_artifacts"]["raw_receipts"]["piecewise-f16"]["container_inspect_sha256"] = "0" * 64
        mutations.append(changed)
        changed = copy.deepcopy(self.result)
        changed["authority"]["protected_decode_values_unchanged"][0] = 0
        mutations.append(changed)

        for index, payload in enumerate(mutations):
            with self.subTest(index=index), tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "mutated.json"
                path.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaises(RuntimeError):
                    self.validate(path)


if __name__ == "__main__":
    unittest.main()
