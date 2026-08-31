#!/usr/bin/env python3
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent


class Contract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = (HERE / "build-current-deterministic-int4-image.sh").read_text()
        cls.wrapper = (HERE / "build-m1pad2-deterministic-int4-image.sh").read_text()

    def test_base_accepts_hash_bound_patch_override(self):
        self.assertIn("PATCH_RELATIVE:-", self.base)
        self.assertIn("EXPECTED_PATCH_SHA256:-", self.base)
        self.assertIn('sha256sum "${patch}"', self.base)

    def test_wrapper_freezes_patch_and_new_image(self):
        self.assertIn("vllm-xpu-kernels-qwen38-onednn-int4-m1pad2-determinism-20260831.patch", self.wrapper)
        self.assertIn("1ffbdc4b0e1220011dfa77d859c2c625d5d4896117c0fe221a5f163bc2ba044e", self.wrapper)
        self.assertIn("qwen38-autoround-m1pad2-deterministic-r1", self.wrapper)


if __name__ == "__main__":
    unittest.main()
