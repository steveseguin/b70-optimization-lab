#!/usr/bin/env python3
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent


class Contract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hook = (HERE / "qwen38-gdn-stage-trace-sitecustomize.py").read_text()
        cls.wrapper = (HERE / "run-20260831-qwen38-gdn0-stages-decode2-d31.sh").read_text()

    def test_frozen_boundary(self):
        self.assertIn("TARGET_LAYER=0", self.wrapper)
        self.assertIn("TARGET_CALL=2", self.wrapper)
        self.assertIn("qwen38-gdn-stage-trace-sitecustomize.py", self.wrapper)

    def test_no_hash_before_production_computation_finishes(self):
        out_projection = self.hook.index("output, _ = self.out_proj(flattened)")
        first_hash = self.hook.index('"hidden_input": _hash_tensor')
        self.assertLess(out_projection, first_hash)

    def test_all_causal_boundaries_are_recorded(self):
        for boundary in (
            "hidden_input", "projected_qkvz", "projected_ba",
            "core_pre_norm", "output_gate", "after_norm", "output",
        ):
            self.assertIn(f'"{boundary}"', self.hook)

    def test_current_xpu_core_signature_includes_state(self):
        self.assertIn("self._xpu_conv_state", self.hook)
        self.assertIn("self._xpu_ssm_state", self.hook)


if __name__ == "__main__":
    unittest.main()
