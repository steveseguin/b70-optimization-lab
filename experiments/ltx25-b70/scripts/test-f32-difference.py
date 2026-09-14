#!/usr/bin/env python3
"""Bounded stdlib arithmetic tests; no Torch, native F32 casts, or subprocesses."""
import argparse
import hashlib
import io
import json
import math
from pathlib import Path
import sys
import unittest

from f32_difference import finite_units, rounded_abs_difference


class DifferenceTests(unittest.TestCase):
    def assert_bits(self, units, expected):
        result = rounded_abs_difference(units)
        self.assertEqual(result['max_abs_diff_f32_bits'], f'0x{expected:08x}')
        if expected == 0x7f800000:
            self.assertEqual(result['max_abs_diff'], math.inf)
        else:
            # Binary64 represents every F32 exactly; independent rational check.
            numerator, denominator = result['max_abs_diff'].as_integer_ratio()
            self.assertEqual(numerator * (1 << 149), finite_units(expected) * denominator)
            self.assertEqual(math.copysign(1.0, result['max_abs_diff']), 1.0)

    def test_finite_words_and_signed_zero(self):
        maximum = (2**24 - 1) * 2**253
        cases = {0: 0, 0x80000000: 0, 1: 1, 0x80000001: -1,
                 0x007fffff: 2**23 - 1, 0x00800000: 2**23,
                 0x3f800000: 2**149, 0xbf800000: -(2**149),
                 0x7f7fffff: maximum, 0xff7fffff: -maximum}
        for word, expected in cases.items():
            with self.subTest(word=hex(word)):
                self.assertEqual(finite_units(word), expected)

    def test_nonfinite_and_invalid_words(self):
        for word in (0x7f800000, 0xff800000, 0x7f800001, 0x7fc00000,
                     0xffc00001, 0x7fffffff, 0xffffffff, -1, 2**32):
            with self.subTest(word=word), self.assertRaises(ValueError):
                finite_units(word)
        for word in (True, False, 1.0, None, '1'):
            with self.subTest(word=word), self.assertRaises(TypeError):
                finite_units(word)

    def test_invalid_difference(self):
        with self.assertRaises(ValueError):
            rounded_abs_difference(-1)
        for value in (True, False, 1.0, None, '1'):
            with self.subTest(value=value), self.assertRaises(TypeError):
                rounded_abs_difference(value)

    def test_subnormal_and_normal_transition(self):
        for units in (0, 1, 2, 2**22, 2**23 - 1, 2**23, 2**23 + 1, 2**24 - 1):
            with self.subTest(units=units):
                self.assert_bits(units, units)
        self.assert_bits(2**24, 0x01000000)
        self.assert_bits(2**24 + 1, 0x01000000)
        self.assert_bits(2**24 + 3, 0x01000002)

    def test_ties_and_neighbours_across_normal_exponents(self):
        # Consecutive representable words have midpoint ties determined by the
        # even low bit, including significand carry into the following exponent.
        for exponent in range(3, 255):
            for mantissa in (0, 1, 0x7fffff):
                lower = (exponent << 23) | mantissa
                if lower == 0x7f7fffff:
                    continue
                upper = lower + 1
                midpoint = (finite_units(lower) + finite_units(upper)) // 2
                with self.subTest(exponent=exponent, mantissa=mantissa):
                    self.assert_bits(midpoint - 1, lower)
                    self.assert_bits(midpoint, lower if lower % 2 == 0 else upper)
                    self.assert_bits(midpoint + 1, upper)

    def test_maximum_and_overflow_tie(self):
        maximum = (2**24 - 1) * 2**253
        boundary = maximum + 2**252
        self.assert_bits(maximum, 0x7f7fffff)
        self.assert_bits(boundary - 1, 0x7f7fffff)
        self.assert_bits(boundary, 0x7f800000)
        self.assert_bits(boundary + 1, 0x7f800000)
        self.assert_bits(2 * maximum, 0x7f800000)
        self.assert_bits(1 << 1000, 0x7f800000)

    def test_real_pair_differences(self):
        for left, right, expected in (
                (0, 0x80000000, 0), (1, 0, 1), (1, 0x80000001, 2),
                (0x00800000, 0x007fffff, 1),
                (0x3f800001, 0x3f800000, 0x34000000),
                (0x3f800000, 0xbf800000, 0x40000000),
                (0x7f7fffff, 0xff7fffff, 0x7f800000)):
            with self.subTest(left=hex(left), right=hex(right)):
                self.assert_bits(abs(finite_units(left) - finite_units(right)), expected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    scripts = Path(__file__).resolve().parent
    hashes = {name: hashlib.sha256((scripts / name).read_bytes()).hexdigest()
              for name in ('f32_difference.py', 'test-f32-difference.py')}
    transcript = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(DifferenceTests)
    result = unittest.TextTestRunner(stream=transcript, verbosity=2).run(suite)
    receipt = {'schema': 'ltx25.f32-difference-cpu.v1',
               'status': 'passed' if result.wasSuccessful() else 'failed',
               'source_sha256': hashes, 'tests_run': result.testsRun,
               'failures': len(result.failures), 'errors': len(result.errors),
               'python': sys.version, 'transcript': transcript.getvalue(),
               'arithmetic': 'exact integer units; IEEE F32 nearest ties-to-even; positive infinity on overflow',
               'torch_imported': 'torch' in sys.modules,
               'torch_mode_equivalence_tested': False,
               'native_checkpoint_tested': False, 'runtime_qualification': False}
    with args.output.open('x') as stream:
        json.dump(receipt, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write('\n')
    print(transcript.getvalue(), end='')
    print(json.dumps({'status': receipt['status'], 'source_sha256': hashes}))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
