#!/usr/bin/env python3
"""CPU-only integrity checks for the failed/partial Q8KV expansion result."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


REPO = Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen36-27b-mtp-gguf-q4-b70"
RESULT = LANE / "data/2026-08-25-qwen36-mtpq8-q8kv-tp1-mtp1234-exact-depth-quality-r1-result.json"
INVENTORY = LANE / "data/2026-08-25-qwen36-mtpq8-q8kv-tp1-mtp1234-exact-depth-quality-r1-raw-inventory.json"
DEPTHS = [0, 2048, 4096, 8192, 16384, 24576, 32768]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


class Q8KVPartialResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = json.loads(RESULT.read_text(encoding="utf-8"))
        cls.inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))

    def test_failure_and_zero_authority_are_frozen(self) -> None:
        self.assertEqual(self.result["classification"], "failed-global-cross-kv-seal-partial-quality-positive-no-publication")
        self.assertFalse(self.result["raw_terminal"]["screen_gate"]["passed"])
        self.assertEqual(self.result["raw_terminal"]["status"], "failed-invalid-control-frame-do-not-publish")
        self.assertEqual(self.result["authority"]["family_matrix_cells"], 0)
        self.assertTrue(all(value is False for key, value in self.result["authority"].items() if key != "family_matrix_cells"))

    def test_all_cells_speeds_hashes_and_counters_are_present(self) -> None:
        arms = self.result["arms"]
        self.assertEqual([arm["mtp"] for arm in arms], [0, 1, 2, 3, 4])
        for arm in arms:
            self.assertEqual([cell["active_context_tokens"] for cell in arm["cells"]], DEPTHS)
            self.assertTrue(arm["cleanup_passed"])
            for cell in arm["cells"]:
                self.assertGreater(cell["serving_decode_tok_s_99_interval"], 0)
                self.assertRegex(cell["output_token_ids_sha256"], r"^[0-9a-f]{64}$")
                self.assertRegex(cell["receipt_sha256"], r"^[0-9a-f]{64}$")
                self.assertEqual(cell["cached_tokens"], 0)
                if arm["mtp"] == 0:
                    self.assertIsNone(cell["draft_counters"])
                else:
                    counters = cell["draft_counters"]
                    self.assertGreater(counters["generated"], 0)
                    self.assertGreater(counters["accepted"], 0)
                    self.assertLessEqual(counters["accepted"], counters["generated"])
                    self.assertTrue(counters["conservation_gate_passed"])

    def test_parity_failure_is_recorded_without_erasing_local_matches(self) -> None:
        frozen = self.result["frozen_adjudication"]
        self.assertEqual(frozen["control_mismatch_vs_inherited_f16_sealed_depths"], [0, 2048, 24576])
        self.assertEqual(frozen["candidate_mismatch_vs_fresh_q8kv_control_depths"], {str(mtp): [2048] for mtp in (1, 2, 3, 4)})
        self.assertEqual((frozen["candidate_fresh_q8kv_control_match_cells"], frozen["candidate_inherited_f16_sealed_match_cells"], frozen["candidate_combined_preregistered_pass_cells"]), (24, 17, 16))
        by_mtp = {arm["mtp"]: arm for arm in self.result["arms"]}
        hashes_2k = {mtp: next(cell for cell in arm["cells"] if cell["active_context_tokens"] == 2048)["output_token_ids_sha256"] for mtp, arm in by_mtp.items()}
        self.assertEqual(len({hashes_2k[0], hashes_2k[1], hashes_2k[2]}), 3)
        self.assertEqual(hashes_2k[2], hashes_2k[3])
        self.assertEqual(hashes_2k[2], hashes_2k[4])

    def test_all_quality_batteries_passed_but_do_not_publish(self) -> None:
        for arm in self.result["arms"][1:]:
            quality = arm["quality"]
            self.assertTrue(quality["passed"])
            self.assertEqual(quality["exact_canaries"], {"count": 4, "passed": True})
            self.assertEqual(quality["repeat"]["repeats"], 2)
            self.assertTrue(quality["repeat"]["passed"])
            self.assertEqual(quality["needle"]["actual_prompt_tokens"], 27234)
            self.assertEqual(quality["needle"]["service_prompt_tokens"], 27246)
            self.assertTrue(quality["needle"]["passed"])
            self.assertEqual(quality["all_request_cached_tokens"], [0] * 7)
        self.assertFalse(self.result["authority"]["site_publication"])

    def test_inventory_is_complete_and_locally_verifiable(self) -> None:
        self.assertEqual(self.inventory["file_count"], 133)
        self.assertEqual(len(self.inventory["files"]), 133)
        self.assertEqual(sha256_file(INVENTORY), self.result["raw_inventory"]["sha256"])
        paths = [row["path"] for row in self.inventory["files"]]
        self.assertEqual(paths, sorted(paths))
        self.assertIn("terminal-receipt.json", paths)
        self.assertIn("candidate-mtp4/depth-32768/draft-counters.json", paths)
        raw_root = Path(self.inventory["raw_root"])
        if raw_root.is_dir():
            self.assertEqual(set(paths), {str(path.relative_to(raw_root)) for path in raw_root.rglob("*") if path.is_file()})
            for row in self.inventory["files"]:
                self.assertEqual(sha256_file(raw_root / row["path"]), row["sha256"])
            self.assertEqual(sha256_file(raw_root / "terminal-receipt.json"), self.result["terminal_receipt_sha256"])
            self.assertEqual(sha256_file(raw_root / "identity.json"), self.result["identity_sha256"])
            terminal = json.loads((raw_root / "terminal-receipt.json").read_text(encoding="utf-8"))
            for preserved_arm, raw_arm in zip(self.result["arms"], terminal["arms"], strict=True):
                self.assertEqual(preserved_arm["mtp"], raw_arm["mtp"])
                for preserved, raw in zip(preserved_arm["cells"], raw_arm["cells"], strict=True):
                    self.assertEqual(preserved["serving_decode_tok_s_99_interval"], raw["receipt"]["serving_decode_tok_s_99_interval"])
                    self.assertEqual(preserved["output_token_ids_sha256"], raw["receipt"]["output_token_ids_sha256"])
                    self.assertEqual(preserved["receipt_sha256"], raw["receipt_sha256"])
                    expected_counters = raw["draft_counters"]
                    if expected_counters is not None:
                        expected_counters = {"generated": expected_counters["generated"], "accepted": expected_counters["accepted"], "ratio": expected_counters["ratio"], "conservation_gate_passed": expected_counters["passed"]}
                    self.assertEqual(preserved["draft_counters"], expected_counters)


if __name__ == "__main__":
    unittest.main()
