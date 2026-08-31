#!/usr/bin/env python3
"""Inert contract tests for the TP1 stacked-width INT4 D7 screen."""

from pathlib import Path
import unittest


HERE = Path(__file__).resolve().parent
HARNESS = HERE / "qwen38-det-cross-process-tp1-stacked-int4.py"
RUNNER = HERE / "run-20260831-qwen38-tp1-stacked-int4-cross-process-d7.sh"


class Contract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.harness = HARNESS.read_text()
        cls.runner = RUNNER.read_text()

    def test_tp1_runtime_shapes(self):
        for shape in ("(5120, 16384)", "(6144, 5120)", "(5120, 14336)", "(5120, 34816)", "(17408, 5120)"):
            self.assertIn(shape, self.harness)

    def test_all_strict_m_values(self):
        self.assertIn("ms=(1 48 49 52 53 55 56 57 59 65 71 75 78)", self.runner)

    def test_determinism_padding_and_fresh_processes(self):
        self.assertIn("VLLM_XPU_ONEDNN_INT4_DETERMINISM_PAD=1", self.runner)
        self.assertIn("for process in 1 2 3 4", self.runner)

    def test_exact_hash_gate(self):
        self.assertIn('"within_process_exact"', self.harness)
        self.assertIn('r["unique_hashes"]!=1', self.runner)


if __name__ == "__main__":
    unittest.main()
