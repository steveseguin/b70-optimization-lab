"""CPU check of b70-w8a16-pad-rows 0.1.0: padding arithmetic, shape selection and the class patch, with a CPU matmul
standing in for the oneDNN op. No vLLM, no GPU."""
import importlib.util
import unittest
from pathlib import Path

import torch

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('pad', HERE / 'overlays/b70-w8a16-pad-rows/b70_w8a16_pad_rows.py')
pad = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pad)


class Kernel:
    def __init__(self, use):
        self._use_w8a16 = use

    def apply_block_scaled_mm(self, A, B, As, Bs):
        return ('original', A.shape[0])


class PadTest(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(pad.parse_shapes(' 8704x5120, 17408X5120 ,'), {(8704, 5120), (17408, 5120)})
        self.assertEqual(pad.parse_shapes(''), set())

    def test_padded_rows(self):
        torch.manual_seed(0)
        w = torch.randn(16, 8, dtype=torch.float64)
        seen = []

        def gemm(x):
            seen.append(x.shape[0])
            return x @ w

        for m in range(1, 9):
            a = torch.randn(m, 16, dtype=torch.float64)
            out = pad.padded(a, 6, gemm)
            self.assertEqual(tuple(out.shape), (m, 8))
            self.assertTrue(torch.equal(out, a @ w))
            self.assertTrue(out.is_contiguous())
        self.assertEqual(seen, [6, 6, 6, 6, 6, 6, 7, 8])
        self.assertEqual(tuple(pad.padded(torch.zeros(0, 16, dtype=torch.float64), 6, gemm).shape), (0, 8))

    def test_patch_selects_shape_and_mode(self):
        cls = type('XPUFp8BlockScaledMMKernel', (Kernel,), {})
        calls = []
        op = lambda a, bt, bst, p: calls.append((tuple(a.shape), tuple(bt.shape), tuple(bst.shape), p)) or 'padded'
        self.assertTrue(pad.install(cls, {(8704, 5120)}, 6, op))
        self.assertFalse(pad.install(cls, {(8704, 5120)}, 6, op))
        b = torch.empty(5120, 8704)                      # [N, K] as the kernel receives it
        bs = torch.empty(40, 68)                         # [n_blocks, k_blocks] view
        a = torch.empty(1, 8704)
        self.assertEqual(cls(True).apply_block_scaled_mm(a, b, None, bs), 'padded')
        self.assertEqual(calls, [((1, 8704), (8704, 5120), (68, 40), 6)])
        self.assertEqual(cls(False).apply_block_scaled_mm(a, b, None, bs), ('original', 1))   # W8A8 path untouched
        other = torch.empty(5120, 6144)
        self.assertEqual(cls(True).apply_block_scaled_mm(torch.empty(1, 6144), other, None, bs), ('original', 1))


if __name__ == '__main__':
    unittest.main()
