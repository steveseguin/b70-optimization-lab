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

    def test_head_mode_same_calls_one_gather(self):
        # stand-in for the image: compute_logits = per-rank projection (_apply_head), then one gather
        torch.manual_seed(1)
        weight = torch.randn(50, 32)
        seen, gathers, depth = [], [], [0]

        class Processor:
            def _apply_head(self, lm_head, hidden, bias=None):
                seen.append(hidden.shape[0])
                return hidden @ lm_head.T

        Processor._apply_head = chunk.chunked_head(Processor._apply_head, 4, torch.cat, lambda: depth[0] > 0)
        processor = Processor()

        def compute_logits(hidden):
            logits = processor._apply_head(weight, hidden, None)
            gathers.append(logits.shape[0])
            return logits

        wrapped = chunk.flagged(compute_logits, depth)
        old_mode = chunk.chunked(lambda hidden: hidden @ weight.T, 4, torch.cat)
        for count in (1, 4, 5, 13, 64):
            seen.clear(); gathers.clear()
            hidden = torch.randn(count, 32)
            self.assertTrue(torch.equal(wrapped(hidden), old_mode(hidden)))
            self.assertTrue(max(seen) <= 4 and sum(seen) == count)
            self.assertEqual(gathers, [count])
            self.assertEqual(depth[0], 0)
        # outside compute_logits (the draft head, local argmax) nothing is chunked
        seen.clear()
        processor._apply_head(weight, torch.randn(9, 32), None)
        self.assertEqual(seen, [9])
        # three-dimensional input is passed through untouched
        depth[0] = 1; seen.clear()
        processor._apply_head(weight, torch.randn(9, 2, 32), None)
        depth[0] = 0
        self.assertEqual(seen, [9])

    def test_none_falls_back(self):
        wrapped = chunk.chunked(lambda hidden: None, 4, torch.cat)
        self.assertIsNone(wrapped(torch.zeros(9, 2)))


if __name__ == '__main__':
    unittest.main()
