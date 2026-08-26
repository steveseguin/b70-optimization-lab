#!/usr/bin/env python3
"""CPU-only checks for the exact-2K R2 pre-request harness failure."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import unittest


REPO = Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen36-27b-mtp-gguf-q4-b70"
RESULT = LANE / "data/2026-08-25-qwen36-mtpq8-q8kv-tp1-mtp01234-exact2k-classification-r2-result.json"
INVENTORY = LANE / "data/2026-08-25-qwen36-mtpq8-q8kv-tp1-mtp01234-exact2k-classification-r2-raw-inventory.json"
EXPECTED_CLEANUP = {"forced_kill": False, "port_closed": True, "render_node_idle": True, "server_survivor": False}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


class Exact2KClassifierR2FailureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = json.loads(RESULT.read_text(encoding="utf-8"))
        cls.inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))

    def test_classification_and_authority_are_fail_closed(self) -> None:
        self.assertEqual(self.result["classification"], "pre-request-harness-case-id-failure-no-inference")
        self.assertEqual(self.result["raw_terminal"]["status"], "failed-evidence-preserve")
        self.assertIsNone(self.result["adjudication"]["route_classification"])
        self.assertEqual(self.result["adjudication"]["speed_measurements"], 0)
        self.assertEqual(self.result["authority"]["site_cells"], 0)
        self.assertTrue(all(value is False for key, value in self.result["authority"].items() if key != "site_cells"))

    def test_every_arm_failed_before_repeat_one_request_and_cleaned_up(self) -> None:
        self.assertEqual([arm["arm"] for arm in self.result["arms"]], ["control-mtp0a", "candidate-mtp1", "candidate-mtp2", "candidate-mtp3", "candidate-mtp4", "control-mtp0b"])
        for arm in self.result["arms"]:
            self.assertEqual(arm["arm_status"], "failed-preserve")
            self.assertIn("returned non-zero exit status 2", arm["error"])
            self.assertIn("-repeat-1", arm["error"])
            self.assertEqual(arm["cleanup"], EXPECTED_CLEANUP)
            self.assertTrue(arm["cleanup_passed"])
            self.assertEqual(arm["exact_depth_receipts"], 0)
            self.assertEqual(arm["exact_depth_stdout"]["size_bytes"], 0)
            self.assertEqual(arm["server_log"]["gpu_inference_request_markers"], 0)
            self.assertTrue(all(repeat["valid"] is False for repeat in arm["terminal_repeats"]))

    def test_zero_inference_proof_is_explicit(self) -> None:
        proof = self.result["failure"]["no_inference_proof"]
        self.assertEqual((proof["exact_depth_receipt_files"], proof["exact_depth_stdout_files"], proof["nonempty_exact_depth_stdout_files"]), (0, 6, 0))
        self.assertEqual((proof["server_logs_checked"], proof["server_request_markers_found"], proof["gpu_inference_requests"]), (6, 0, 0))
        self.assertEqual(proof["server_model_load_lifetimes"], 6)
        reproduction = self.result["failure"]["post_run_inert_reproduction"]
        self.assertEqual((reproduction["network_requests"], reproduction["output_writes"], reproduction["exit_status"]), (0, 0, 2))
        self.assertEqual(reproduction["fixture_case_at_depth_2048"], "depth-2048")
        self.assertIn("unknown fixture case id", reproduction["error"])

    def test_full_inventory_and_raw_tree_prove_no_requests(self) -> None:
        self.assertEqual(self.inventory["file_count"], 33)
        self.assertEqual(len(self.inventory["files"]), 33)
        self.assertEqual(sha256_file(INVENTORY), self.result["raw_inventory"]["sha256"])
        paths = [row["path"] for row in self.inventory["files"]]
        self.assertEqual(paths, sorted(paths))
        self.assertFalse(any(path.endswith("/exact-depth.json") for path in paths))
        self.assertEqual(sum(path.endswith("/exact-depth.stdout.json") for path in paths), 6)
        raw_root = Path(self.inventory["raw_root"])
        if raw_root.is_dir():
            self.assertEqual(set(paths), {str(path.relative_to(raw_root)) for path in raw_root.rglob("*") if path.is_file()})
            for row in self.inventory["files"]:
                self.assertEqual(sha256_file(raw_root / row["path"]), row["sha256"])
            self.assertEqual(sha256_file(raw_root / "terminal-receipt.json"), self.result["terminal_receipt_sha256"])
            self.assertEqual(sha256_file(raw_root / "identity.json"), self.result["identity_sha256"])
            markers = re.compile(r"slot launch_slot_|slot print_timing:.*(?:prompt eval time|eval time)")
            for log in raw_root.glob("*/server.log"):
                self.assertIsNone(markers.search(log.read_text(encoding="utf-8")))
            for stdout in raw_root.glob("*/repeat-1/exact-depth.stdout.json"):
                self.assertEqual(stdout.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
