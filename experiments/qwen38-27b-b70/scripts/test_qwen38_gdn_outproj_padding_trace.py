#!/usr/bin/env python3
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent


class Contract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hook = (HERE / "qwen38-gdn-outproj-padding-trace-sitecustomize.py").read_text()
        cls.wrapper = (HERE / "run-20260831-qwen38-gdn0-outproj-padding-d32.sh").read_text()

    def test_frozen_boundary(self):
        self.assertIn("TARGET_LAYER=0", self.wrapper)
        self.assertIn("TARGET_CALL=2", self.wrapper)

    def test_frozen_padding_sweep(self):
        self.assertIn("PAD_ROWS = (1, 2, 4, 8, 16, 32, 64, 128, 256, 512)", self.hook)
        self.assertIn("for _ in range(2)", self.hook)
        self.assertIn("projection_input[0].copy_(normalized[0])", self.hook)

    def test_ordinary_result_is_returned(self):
        self.assertIn("ordinary_output = projected", self.hook)
        self.assertIn("return ordinary_output", self.hook)


if __name__ == "__main__":
    unittest.main()
