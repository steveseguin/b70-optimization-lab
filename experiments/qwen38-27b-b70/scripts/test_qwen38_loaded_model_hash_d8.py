#!/usr/bin/env python3
"""Inert contract tests for loaded-model hash D8."""

from pathlib import Path
import unittest


HERE = Path(__file__).resolve().parent


class Contract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hook = (HERE / "qwen38-loaded-model-hash-sitecustomize.py").read_text()
        cls.runner = (HERE / "run-20260831-qwen38-loaded-model-hash-d8.sh").read_text()

    def test_complete_loaded_state_is_hashed(self):
        self.assertIn("named_parameters(remove_duplicate=False)", self.hook)
        self.assertIn("named_buffers(remove_duplicate=False)", self.hook)
        for field in ('"dtype"', '"shape"', '"stride"', '"sha256"'):
            self.assertIn(field, self.hook)

    def test_receipt_is_atomic(self):
        self.assertIn("os.replace(temporary, destination)", self.hook)

    def test_scalar_tensor_has_stable_byte_view(self):
        self.assertIn("cpu().reshape(-1).view(torch.uint8)", self.hook)

    def test_fresh_processes_and_no_requests(self):
        self.assertIn("for process in 1 2 3 4", self.runner)
        self.assertNotIn("/v1/completions", self.runner)

    def test_direct_model_gate_and_tp1(self):
        self.assertIn("verify-model-direct.py", self.runner)
        self.assertIn("--tensor-parallel-size 1", self.runner)
        self.assertIn("--volume /dev/dri/by-path:/dev/dri/by-path:ro", self.runner)
        self.assertIn("--group-add video --group-add render", self.runner)


if __name__ == "__main__":
    unittest.main()
