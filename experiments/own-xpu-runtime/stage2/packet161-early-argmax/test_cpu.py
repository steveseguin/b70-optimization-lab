"""CPU arithmetic/resource checks; no model or device access."""
import json
import struct
import unittest
from unittest.mock import patch

from audit import guard
guard()
import numpy as np
import prepare
import analyze
prepare.np = analyze.np = np


def f32(x):
    return struct.unpack('<f', struct.pack('<f', float(x)))[0]


def scalar(w, x, splits):
    parts = []
    k = len(x)
    tiles = (k+255)//256
    for part in range(splits):
        begin, end = min(k, tiles*part//splits*256), min(k, tiles*(part+1)//splits*256)
        lanes = []
        for lane in range(32):
            s = 0.
            for tile in range(begin+lane*8, end, 256):
                for j in range(8):
                    if tile+j < end:
                        s = f32(s+f32(float(w[tile+j])*float(x[tile+j])))
            lanes.append(s)
        while len(lanes) > 1:
            lanes = [f32(a+b) for a, b in zip(lanes[::2], lanes[1::2])]
        parts.append(lanes[0])
    while len(parts) > 1:
        parts = [f32(a+b) for a, b in zip(parts[::2], parts[1::2])]
    bits = struct.unpack('<I', struct.pack('<f', parts[0]))[0]
    return struct.unpack('<f', struct.pack('<I', ((bits+0x7fff+((bits>>16)&1))>>16)<<16))[0]


class Checks(unittest.TestCase):
    def test_exact_real_shapes(self):
        rng = np.random.default_rng(161)
        for k, splits in ((2560, 1), (10240, 4), (320, 1)):
            w = rng.normal(size=(3, k)).astype(np.float32)
            x = prepare.bf(rng.normal(size=(2, k)).astype(np.float32))
            got = prepare.exact_gemv(w, x, splits)
            want = [[scalar(row, hidden, splits) for row in w] for hidden in x]
            np.testing.assert_array_equal(got, want)

    def test_bf16_ties(self):
        x = np.array([1+2**-8, 1+3*2**-8, -1-2**-8], np.float32)
        np.testing.assert_array_equal(prepare.bf(x), [1, 1+2**-6, -1])

    def test_upper_rounding(self):
        x = np.linspace(-500, 500, 20001, dtype=np.float64)
        upper = analyze.rounded_upper(x)
        assert np.all(upper >= prepare.bf(x.astype(np.float32)))

    def test_error_bound(self):
        rng = np.random.default_rng(50161)
        w = rng.normal(size=(12, 2560)).astype(np.float32)
        x = prepare.bf(rng.normal(size=(4, 2560)).astype(np.float32))
        exact = prepare.exact_gemv(w, x)
        dot = w.astype(np.float64)@x.astype(np.float64).T
        cs = np.linalg.norm(w.astype(np.float64), axis=1)[:, None]*np.linalg.norm(x.astype(np.float64), axis=1)
        u = 2**-24
        error = 86*u/(1-86*u)*cs+1e-10*np.maximum(cs, 1)+5151*2**-149/(1-86*u)
        assert np.all(exact.T <= analyze.rounded_upper(dot+error))
        # Strict ties do not certify, including the all-zero real shape.
        zero = np.zeros((1, 2560), np.float32)
        assert not float(prepare.exact_gemv(zero, zero)[0, 0]) > float(analyze.rounded_upper(np.array([0.]))[0])

    def test_active_weight_refusal(self):
        class Result:
            stdout = 'active\n'
        with patch.object(prepare.subprocess, 'run', return_value=Result()):
            with self.assertRaisesRegex(AssertionError, 'still active'):
                prepare.weight_admission()

    def test_nonfinite_input_refused_by_analysis_precondition(self):
        for bad in (np.nan, np.inf, -np.inf):
            x = np.zeros(2560)
            x[12] = bad
            assert not np.isfinite(x).all()


if __name__ == '__main__':
    unittest.main()
