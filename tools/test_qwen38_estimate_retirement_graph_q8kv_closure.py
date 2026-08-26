#!/usr/bin/env python3
"""Focused tests for estimate retirement and the speedless graph closure."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / (
    "experiments/qwen38-27b-b70/scripts/"
    "validate-20260826-qwen38-retired-estimates-q8kv-graph-8k-closure.py"
)
SPEC = importlib.util.spec_from_file_location("qwen38_coverage_adjudication", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CoverageAdjudicationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.family = json.loads((ROOT / "families/qwen-27b.json").read_text())
        cls.adjudication = json.loads(MODULE.ADJUDICATION_PATH.read_text())

    def test_current_files_pass(self) -> None:
        self.assertEqual(MODULE.validate(self.family, self.adjudication), [])

    def test_estimate_reintroduction_fails(self) -> None:
        family = copy.deepcopy(self.family)
        family["estimates"] = [{"id": "stale-estimate"}]
        self.assertIn(
            "the live family estimate registry must be empty",
            MODULE.validate(family, self.adjudication),
        )

    def test_sibling_depth_closure_fails(self) -> None:
        family = copy.deepcopy(self.family)
        contract = next(
            item for item in family["coverage_contracts"]
            if item["id"] == "qwen38-tp1-llamacpp-sycl-target-matrix"
        )
        contract["rules"].append({
            "id": "bad-overbroad-closure",
            "match": {
                "revision": "qwen3.8-27b",
                "artifact_id": "qwen38-27b-ggmlorg-q8-0-0669b98",
                "tp": 1,
                "mtp": 0,
                "active_context_tokens": 16384,
                "graph_mode": "SYCL",
                "kv": "q8_0",
            },
            "state": "closed",
        })
        self.assertIn(
            "graph/Q8-KV depth 16384 must remain missing",
            MODULE.validate(family, self.adjudication),
        )

    def test_speed_on_closed_packet_fails(self) -> None:
        family = copy.deepcopy(self.family)
        packet_id = self.adjudication["q8weights_q8kv_graph_cache64_8k_closure"]["packet_id"]
        packet = next(item for item in family["packets"] if item["id"] == packet_id)
        packet["featured_metric"] = {"metric": "decode_tok_s", "value": 15.3608}
        self.assertIn("closed graph packet must be speedless", MODULE.validate(family, self.adjudication))


if __name__ == "__main__":
    unittest.main()
