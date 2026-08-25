#!/usr/bin/env python3
from pathlib import Path
import json
import unittest


ROOT = Path(__file__).resolve().parents[3]
RUNNER = Path(__file__).with_name("run-qwen38-q8weights-f16-tp1-local-r2.sh")
MANIFEST = ROOT / "experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q8weights-f16-tp1-local-r2-prereg.json"
RESULT = ROOT / "experiments/qwen38-27b-b70/data/qwen38-q8weights-f16-tp1-local-20260825-r2/result.json"


class LocalQ8DepthR2Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = RUNNER.read_text(encoding="utf-8")
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_exact_matrix_and_identity(self):
        self.assertIn('-d "0,2048,4096,8192,16384,24576,32768"', self.text)
        self.assertIn("-ctk f16 -ctv f16", self.text)
        self.assertIn(self.manifest["model"]["sha256"], self.text)
        self.assertIn(self.manifest["runtime"]["binary_sha256"], self.text)

    def test_safe_lifecycle(self):
        for fragment in ("status --porcelain", "ls-remote", "flock -n 6", "flock -n 9", "docker ps -q", "create-only output", "MemoryMax=13G"):
            self.assertIn(fragment, self.text)

    def test_failure_is_not_silently_resized(self):
        self.assertIn("unsupported-fit", self.text)
        self.assertNotIn("ctk q8_0", self.text)

    def test_committed_result_is_the_complete_exact_matrix(self):
        result = json.loads(RESULT.read_text(encoding="utf-8"))
        self.assertEqual(result["classification"], "complete-raw-engine")
        rows = result["rows"]
        self.assertEqual(len(rows), 14)
        observed = {
            (row["n_depth"], "decode" if row["n_gen"] == 128 else "prefill")
            for row in rows
        }
        expected = {
            (depth, kind)
            for depth in (0, 2048, 4096, 8192, 16384, 24576, 32768)
            for kind in ("decode", "prefill")
        }
        self.assertEqual(observed, expected)
        self.assertTrue(all(len(row["samples_ts"]) == 5 for row in rows))


if __name__ == "__main__":
    unittest.main()
