#!/usr/bin/env python3
"""Exact bit-pattern tests against the prior scalar rule; no tensor packages."""
import array
import hashlib
import random
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import finite_f32_bits as finite


def scalar(data):
    for index, (word,) in enumerate(struct.iter_unpack('<I', data)):
        if word & 0x7f800000 == 0x7f800000:
            return index
    return None


class FiniteBitsTests(unittest.TestCase):
    def test_all_finite_exponents_signs_and_mantissa_boundaries(self):
        words = [(sign << 31) | (exponent << 23) | mantissa
                 for sign in (0, 1) for exponent in range(255)
                 for mantissa in (0, 1, 0x3fffff, 0x400000, 0x7ffffe, 0x7fffff)]
        data = struct.pack('<' + 'I' * len(words), *words)
        self.assertIsNone(scalar(data))
        self.assertIsNone(finite.first_nonfinite_f32(data))

    def test_infinities_and_all_individual_nan_payload_bits(self):
        for sign in (0, 1):
            for mantissa in (0, 0x7fffff, *(1 << bit for bit in range(23))):
                word = (sign << 31) | 0x7f800000 | mantissa
                with self.subTest(word=hex(word)):
                    self.assertEqual(finite.first_nonfinite_f32(struct.pack('<I', word)), 0)

    def test_each_missing_exponent_bit_is_finite_with_full_mantissa(self):
        words = [((0xff ^ (1 << bit)) << 23) | 0x807fffff for bit in range(8)]
        data = struct.pack('<8I', *words)
        self.assertIsNone(finite.first_nonfinite_f32(data))

    def test_first_invalid_index_across_blocks_and_limb_alignments(self):
        count = 3 * finite.BLOCK_BYTES // 4 + 17
        original = struct.pack('<I', 0x7f7fffff) * count
        positions = list(range(32)) + [16382, 16383, 16384, 16385, 32767, 32768, count - 1]
        for index in positions:
            data = bytearray(original)
            struct.pack_into('<I', data, index * 4, 0xff800001)
            struct.pack_into('<I', data, (count - 1) * 4, 0x7f800000)
            with self.subTest(index=index):
                self.assertEqual(finite.first_nonfinite_f32(data), scalar(data))
                self.assertEqual(finite.first_nonfinite_f32(data), index)

    def test_neighbors_cannot_contaminate_selected_exponent(self):
        # Every finite word has many set sign/mantissa/exponent bits. Boundaries
        # must not combine those into a nonfinite exponent in another word.
        pattern = [0xff7fffff, 0x7f7fffff, 0x7effffff, 0x807fffff, 0x80000000, 1]
        data = struct.pack('<6I', *pattern) * 4096
        self.assertIsNone(finite.first_nonfinite_f32(data))

    def test_random_patterns_match_scalar_first_failure(self):
        rng = random.Random(20260914)
        words = [rng.getrandbits(32) for _ in range(50000)]
        data = struct.pack('<' + 'I' * len(words), *words)
        self.assertEqual(finite.first_nonfinite_f32(data), scalar(data))
        finite_words = [word & ~0x00800000 if word & 0x7f800000 == 0x7f800000 else word
                        for word in words]
        data = struct.pack('<' + 'I' * len(words), *finite_words)
        self.assertIsNone(finite.first_nonfinite_f32(data))
        self.assertIsNone(scalar(data))

    def test_empty_partial_block_and_incomplete_samples(self):
        self.assertIsNone(finite.first_nonfinite_f32(b''))
        for size in (4, 8, 65532, 65536, 65540):
            self.assertIsNone(finite.first_nonfinite_f32(bytes(size)))
            for tail in (1, 2, 3):
                data = bytes(size + tail)
                with self.subTest(size=size, tail=tail), self.assertRaises(struct.error):
                    finite.first_nonfinite_f32(data)
                with self.assertRaises(struct.error):
                    scalar(data)

    def test_contiguous_buffer_types_preserve_bytes(self):
        payload = struct.pack('<4I', 0x80000000, 1, 0xff7fffff, 0x3f800000)
        typed = array.array('I')
        typed.frombytes(payload)
        for value in (payload, bytearray(payload), memoryview(payload), memoryview(typed)):
            before = bytes(memoryview(value).cast('B'))
            self.assertEqual(finite.first_nonfinite_f32(value), scalar(value))
            self.assertEqual(bytes(memoryview(value).cast('B')), before)
            self.assertEqual(hashlib.sha256(before).digest(), hashlib.sha256(payload).digest())

    def test_noncontiguous_buffer_is_rejected(self):
        data = memoryview(bytes(32))[::2]
        with self.assertRaises(BufferError):
            finite.first_nonfinite_f32(data)
        with self.assertRaises(BufferError):
            scalar(data)

    def test_integer_input_blocks_stay_bounded(self):
        reads = []
        original = int.from_bytes
        def tracked(data, *args, **kwargs):
            reads.append(len(data))
            return original(data, *args, **kwargs)
        with patch.object(finite, 'int', SimpleNamespace(from_bytes=tracked), create=True):
            self.assertIsNone(finite.first_nonfinite_f32(bytes(5 * finite.BLOCK_BYTES + 20)))
        self.assertEqual(max(reads), 65536)
        self.assertEqual(sum(reads), 5 * finite.BLOCK_BYTES + 20)


if __name__ == '__main__':
    unittest.main(verbosity=2)
