#!/usr/bin/env python3
"""CPU-only checks for the successful exact-2K R3 classifier result."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


REPO = Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen36-27b-mtp-gguf-q4-b70"
RESULT = LANE / "data/2026-08-25-qwen36-mtpq8-q8kv-tp1-mtp01234-exact2k-classification-r3-result.json"
INVENTORY = LANE / "data/2026-08-25-qwen36-mtpq8-q8kv-tp1-mtp01234-exact2k-classification-r3-raw-inventory.json"
CONTROL_HASH = "e11b5a317688e28bf0cd4b1e1d234b72327feb06a435357ef846acc5344a620d"
MTP1_HASH = "15ae89335b6e0ad365cf9f9ad524d621befbaea3580940374943a7b2e02dcf72"
MTP234_HASH = "6177d7799a71763d852b589188137db878177ff878b600de0977a5182264b3b6"
EXPECTED_CLEANUP = {"forced_kill": False, "port_closed": True, "render_node_idle": True, "server_survivor": False}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


class Exact2KClassifierR3ResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = json.loads(RESULT.read_text(encoding="utf-8"))
        cls.inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))

    def test_grade_c_and_zero_direct_authority(self) -> None:
        self.assertEqual(self.result["classification"], "grade-c-deterministic-route-divergence")
        self.assertEqual(self.result["raw_terminal"], {"schema": "neural.download.qwen36-llama-mtp01234-q8kv-exact2k-classification-terminal.v1", "status": "completed-classification-only", "overall_classification": "deterministic-route-divergence", "packet_grade": "C"})
        self.assertEqual(self.result["authority"]["site_cells"], 0)
        self.assertTrue(all(value is False for key, value in self.result["authority"].items() if key != "site_cells"))

    def test_all_18_requests_controls_and_candidate_hashes(self) -> None:
        self.assertEqual(self.result["scope"]["valid_requests"], 18)
        self.assertEqual(self.result["evidence_summary"]["cache_zero_requests"], 18)
        self.assertEqual(self.result["evidence_summary"]["repeat_stable_arms"], 6)
        self.assertEqual(self.result["evidence_summary"]["clean_lifetimes"], 6)
        arms = {arm["arm"]: arm for arm in self.result["arms"]}
        self.assertEqual(arms["control-mtp0a"]["canonical_output_token_ids_sha256"], CONTROL_HASH)
        self.assertEqual(arms["control-mtp0b"]["canonical_output_token_ids_sha256"], CONTROL_HASH)
        self.assertEqual(arms["candidate-mtp1"]["canonical_output_token_ids_sha256"], MTP1_HASH)
        for mtp in (2, 3, 4):
            self.assertEqual(arms[f"candidate-mtp{mtp}"]["canonical_output_token_ids_sha256"], MTP234_HASH)
        for arm in arms.values():
            self.assertTrue(arm["valid"])
            self.assertTrue(arm["within_arm_repeat_stable"])
            self.assertEqual(arm["cleanup"], EXPECTED_CLEANUP)
            self.assertTrue(all(row["valid"] and row["cached_tokens"] == 0 for row in arm["repeats"]))

    def test_first_divergence_and_counters_are_exact(self) -> None:
        expected_counters = {1: (69, 58, 0.84058), 2: (109, 72, 0.66055), 3: (144, 78, 0.54167), 4: (179, 81, 0.45251)}
        comparisons = {int(row["arm"].removeprefix("candidate-mtp")): row for row in self.result["route_comparisons"]}
        arms = {arm["mtp"]: arm for arm in self.result["arms"] if arm["mtp"] > 0}
        for mtp in (1, 2, 3, 4):
            row = comparisons[mtp]
            self.assertEqual(row["classification"], "deterministic-route-divergence")
            comparison = row["comparison_to_bracketing_mtp0"]
            self.assertEqual((comparison["first_divergence_zero_based_index"], comparison["first_divergence_one_based_position"], comparison["common_prefix_tokens"]), (73, 74, 73))
            self.assertEqual((comparison["control_token_id"], comparison["candidate_token_id"]), (7888, 4434))
            generated, accepted, ratio = expected_counters[mtp]
            for repeat in arms[mtp]["repeats"]:
                counters = repeat["draft_counters"]
                self.assertEqual((counters["generated"], counters["accepted"], counters["ratio"]), (generated, accepted, ratio))
                self.assertEqual(counters["rows_after"], counters["rows_before"] + 1)
        self.assertEqual(self.result["evidence_summary"]["candidate_counter_receipts"], 12)
        self.assertEqual(self.result["evidence_summary"]["positive_conserved_candidate_counter_receipts"], 12)

    def test_all_strict_checks_pass(self) -> None:
        strict = self.result["strict_validation"]
        self.assertTrue(strict["all_identity_checks_passed"])
        self.assertTrue(strict["all_r3_checks_passed"])
        self.assertEqual(strict["r3_check_count"], 65)
        self.assertTrue(all(strict["identity_checks"].values()))
        self.assertTrue(all(strict["r3_checks"].values()))

    def test_full_inventory_matches_raw_and_result(self) -> None:
        self.assertEqual(self.inventory["file_count"], 75)
        self.assertEqual(len(self.inventory["files"]), 75)
        self.assertEqual(sha256_file(INVENTORY), self.result["raw_inventory"]["sha256"])
        paths = [row["path"] for row in self.inventory["files"]]
        self.assertEqual(paths, sorted(paths))
        self.assertEqual(sum(path.endswith("/exact-depth.json") for path in paths), 18)
        self.assertEqual(sum(path.endswith("/draft-counters.json") for path in paths), 12)
        raw_root = Path(self.inventory["raw_root"])
        if raw_root.is_dir():
            self.assertEqual(set(paths), {str(path.relative_to(raw_root)) for path in raw_root.rglob("*") if path.is_file()})
            for row in self.inventory["files"]:
                self.assertEqual(sha256_file(raw_root / row["path"]), row["sha256"])
            self.assertEqual(sha256_file(raw_root / "terminal-receipt.json"), self.result["terminal_receipt_sha256"])
            self.assertEqual(sha256_file(raw_root / "identity.json"), self.result["identity_sha256"])
            for arm in self.result["arms"]:
                for repeat in arm["repeats"]:
                    receipt = json.loads((raw_root / repeat["raw_receipt_path"]).read_text(encoding="utf-8"))
                    self.assertEqual(receipt["response"]["output_token_ids_sha256"], repeat["output_token_ids_sha256"])
                    self.assertEqual(receipt["metric_window"]["conventional_99_interval_tok_s"], repeat["conventional_99_interval_tok_s"])


if __name__ == "__main__":
    unittest.main()
