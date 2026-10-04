"""CPU check of the chunked-upload overlay: same bytes, bounded pieces, everything else untouched."""
import importlib.util
import unittest
from pathlib import Path

import torch

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('cu', HERE / 'overlays/b70-chunked-upload/b70_chunked_upload.py')
cu = importlib.util.module_from_spec(spec); spec.loader.exec_module(cu)


class ChunkedUploadTest(unittest.TestCase):
    def test_pieces_cover_everything_once(self):
        for count, size, chunk in ((10, 2, 6), (7, 4, 4), (1, 8, 1), (1000, 2, 128)):
            got = cu.pieces(count, size, chunk)
            self.assertEqual(got[0][0], 0); self.assertEqual(got[-1][1], count)
            self.assertTrue(all(a[1] == b[0] for a, b in zip(got, got[1:])))
            self.assertTrue(all((stop - start) * size <= max(chunk, size) for start, stop in got))

    def test_copy_same_bytes_bounded_pieces(self):
        # 'cpu' stands in for the card: the wrapper is told the card is called 'cpu'
        seen, original = [], torch.Tensor.copy_

        def spy(dst, src, *a, **k):
            seen.append(src.numel() * src.element_size())
            return original(dst, src, *a, **k)

        done = []
        copy_ = cu.wrap_copy(spy, over_bytes=1000, chunk_bytes=256, card='cpu', counter=done)
        src = torch.randn(40, 50).to(torch.float16)          # 4000 bytes
        dst = torch.zeros(40, 50, dtype=torch.float16)
        self.assertIs(copy_(dst, src), dst)
        self.assertTrue(torch.equal(dst, src))
        self.assertEqual(sum(seen), 4000); self.assertTrue(max(seen) <= 256); self.assertEqual(done, [4000])
        # a copy that converts the number type is chunked too and gives exactly what one call gives
        wide = torch.randn(40, 50, dtype=torch.float32) * 1e3
        for dtype in (torch.bfloat16, torch.float16):
            seen.clear()
            dst_c, dst_ref = torch.zeros(40, 50, dtype=dtype), torch.zeros(40, 50, dtype=dtype)
            copy_(dst_c, wide); original(dst_ref, wide)
            self.assertTrue(torch.equal(dst_c.view(torch.int16), dst_ref.view(torch.int16)))
            self.assertTrue(len(seen) > 1 and max(seen) <= 256 * 2)
        bf = torch.randn(40, 50).to(torch.bfloat16)
        dst_c, dst_ref = torch.zeros(40, 50, dtype=torch.float16), torch.zeros(40, 50, dtype=torch.float16)
        copy_(dst_c, bf); original(dst_ref, bf)
        self.assertTrue(torch.equal(dst_c.view(torch.int16), dst_ref.view(torch.int16)))
        done.clear(); done.append(4000)
        # small, broadcast and non-contiguous copies go to the original in one call
        for dst2, src2 in ((torch.zeros(4, 5, dtype=torch.float16), torch.ones(4, 5, dtype=torch.float16)),
                           (torch.zeros(3, 40, 50, dtype=torch.float16), src),
                           (torch.zeros(50, 40, dtype=torch.float16), src.t())):
            seen.clear()
            copy_(dst2, src2)
            self.assertEqual(len(seen), 1)
            self.assertTrue(torch.equal(dst2, src2.to(dst2.dtype).expand_as(dst2)))
        self.assertEqual(done, [4000])

    def test_to_device_only(self):
        seen, original_copy, original_to = [], torch.Tensor.copy_, torch.Tensor.to

        def spy(dst, src, *a, **k):
            seen.append(src.numel() * src.element_size())
            return original_copy(dst, src, *a, **k)

        def device_of(value):
            return value if isinstance(value, torch.device) else torch.device(value) if isinstance(value, str) else None

        to = cu.wrap_to(original_to, spy, torch.empty, device_of, over_bytes=1000, chunk_bytes=256, card='cpu')
        src = torch.randn(40, 50).to(torch.float16)
        for call in (lambda: to(src, 'cpu'), lambda: to(src, torch.device('cpu')), lambda: to(src, device='cpu')):
            seen.clear()
            out = call()
            self.assertTrue(torch.equal(out, src)); self.assertIsNot(out, src)
            self.assertEqual(sum(seen), 4000); self.assertTrue(max(seen) <= 256)
        # the other direction (card back to host) is chunked the same way: here the "card" is a fake device type
        class Fake:
            """Enough of a tensor for eligible(): pretends to live on the card."""
            def __init__(self, t): self.t = t
            device = torch.device('meta'); layout = torch.strided; is_sparse = False
            def __getattr__(self, name): return getattr(self.t, name)
        self.assertTrue(cu.eligible(torch.zeros(40, 50, dtype=torch.float16), Fake(src), 1000, 'meta'))
        self.assertTrue(cu.eligible(Fake(torch.zeros(40, 50, dtype=torch.float16)), src, 1000, 'meta'))
        self.assertFalse(cu.eligible(torch.zeros(40, 50, dtype=torch.float16), src, 1000, 'meta'))   # host to host
        seen.clear()
        self.assertEqual(to(src, torch.float32).dtype, torch.float32)      # dtype call: original
        self.assertEqual(to(src, 'cpu', torch.float32).dtype, torch.float32)
        self.assertEqual(to(src, device='cpu', non_blocking=True).shape, src.shape)
        self.assertEqual(seen, [])


if __name__ == '__main__':
    unittest.main()
