"""CPU-only exact exponent census and boundary/failure tests."""
import random
import struct
import unittest
from unittest import mock

import f32_scan137 as scan


def scalar(raw):
    return all(word & 0x7f800000 != 0x7f800000
               for (word,) in struct.iter_unpack('<I', raw))


class ExactF32Scan(unittest.TestCase):
    def test_all_upper_byte_pairs(self):
        # Exhaustive sign/exponent and upper mantissa bits; low 16 bits cannot
        # affect either predicate. Test individually so an early NaN cannot
        # hide a later false acceptance.
        for pair in range(65536):
            raw = struct.pack('<I', (pair << 16) | 0xA55A)
            self.assertEqual(scan.finite(raw), scalar(raw), hex(pair))

    def test_low_mantissas_and_signs(self):
        for sign in (0, 0x80000000):
            for exponent in (0, 1, 126, 127, 254, 255):
                for mantissa in (0, 1, 0xFFFF, 0x400000, 0x7FFFFF):
                    raw = struct.pack('<I', sign | exponent << 23 | mantissa)
                    self.assertEqual(scan.finite(raw), scalar(raw))

    def test_opposite_lanes_do_not_intersect(self):
        raw = struct.pack('<II', 0x7F000000, 0x00800000)
        self.assertTrue(scan.finite(raw * (scan.BLOCK_BYTES // 4)))
        self.assertTrue(scan.finite(raw[::-1]))

    def test_each_word_position_around_block_edges(self):
        raw = bytes(scan.BLOCK_BYTES * 2 + 12)
        for offset in (0, 4, scan.BLOCK_BYTES - 4, scan.BLOCK_BYTES,
                       scan.BLOCK_BYTES + 4, len(raw) - 4):
            for word in (0x7F800000, 0xFF800000, 0x7F800001, 0xFFFFFFFF):
                changed = raw[:offset] + struct.pack('<I', word) + raw[offset + 4:]
                self.assertFalse(scan.finite(changed), (offset, word))

    def test_empty_and_partial_final_block(self):
        for length in (0, 4, 12, scan.BLOCK_BYTES - 4, scan.BLOCK_BYTES,
                       scan.BLOCK_BYTES + 4, 786432):
            self.assertTrue(scan.finite(bytes(length)))

    def test_deterministic_finite_corpus_is_not_changed(self):
        rng = random.Random(137)
        words = [rng.getrandbits(32) & 0xFEFFFFFF for _ in range(196608)]
        raw = struct.pack('<%dI' % len(words), *words)
        before = raw
        self.assertTrue(scalar(raw))
        self.assertTrue(scan.finite(raw))
        self.assertIs(raw, before)
        self.assertEqual(raw, struct.pack('<%dI' % len(words), *words))

    def test_no_cached_verdict(self):
        good = bytes(786432)
        bad = good[:-4] + struct.pack('<I', 0x7FC00001)
        for _ in range(3):
            self.assertTrue(scan.finite(good))
            self.assertFalse(scan.finite(bad))

    def test_invalid_buffer_types(self):
        class BytesSubclass(bytes):
            pass
        for raw in (None, '', [], bytearray(4), memoryview(bytes(4)), BytesSubclass(4)):
            with self.assertRaisesRegex(ValueError, 'Immutable complete F32'):
                scan.finite(raw)

    def test_misaligned_lengths(self):
        for length in (1, 2, 3, 5, scan.BLOCK_BYTES + 1):
            with self.assertRaises(ValueError):
                scan.finite(bytes(length))

    def test_launch_option(self):
        self.assertEqual(scan.launch({}), 'parent')
        for mode in ('parent', 'bulk'):
            self.assertEqual(scan.launch({'LTX_F32_SCAN': mode}), mode)
        for mode in ('', 'on', 'off', '1', 'bulk ', True, None, 1):
            with self.assertRaises(ValueError):
                scan.launch({'LTX_F32_SCAN': mode})
        with mock.patch.dict('os.environ', {'LTX_F32_SCAN': 'bulk'}):
            self.assertEqual(scan.launch(), 'bulk')

    def test_mutated_scan_constants_refuse(self):
        for name, value in (('BLOCK_BYTES', 65535), ('BLOCK_BYTES', 0),
                            ('_HIGH_EXPONENT', bytes(256)),
                            ('_HIGH_EXPONENT', bytearray(scan._HIGH_EXPONENT))):
            with mock.patch.object(scan, name, value):
                with self.assertRaisesRegex(ValueError, 'constants changed'):
                    scan.finite(bytes(4))


if __name__ == '__main__':
    unittest.main()
