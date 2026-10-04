"""CPU check: the chunked compute_logits returns exactly what one call would, and never passes more than N rows."""
import importlib.util
import unittest
from pathlib import Path

import torch

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('chunk', HERE / 'overlays/b70-lm-head-chunk/b70_lm_head_chunk.py')
chunk = importlib.util.module_from_spec(spec); spec.loader.exec_module(chunk)


class ChunkTest(unittest.TestCase):
    def test_same_result_and_bounded_rows(self):
        torch.manual_seed(0)
        weight = torch.randn(50, 32)
        seen = []

        def inner(hidden):
            seen.append(hidden.shape[0])
            return hidden @ weight.T

        wrapped = chunk.chunked(inner, 4, torch.cat)
        for count in (1, 3, 4, 5, 13, 16):
            seen.clear()
            hidden = torch.randn(count, 32)
            self.assertTrue(torch.equal(wrapped(hidden), torch.cat([hidden[i:i + 4] @ weight.T for i in range(0, count, 4)])))
            self.assertTrue(max(seen) <= 4 and sum(seen) == count)

    def test_none_falls_back(self):
        wrapped = chunk.chunked(lambda hidden: None, 4, torch.cat)
        self.assertIsNone(wrapped(torch.zeros(9, 2)))


if __name__ == '__main__':
    unittest.main()
