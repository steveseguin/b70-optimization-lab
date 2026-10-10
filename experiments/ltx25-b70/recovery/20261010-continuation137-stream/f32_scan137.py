"""Exact, bounded F32 finiteness predicate. No float conversion or runtime import.

For a little-endian word, exponent 255 requires byte 3's low seven bits
and byte 2's high bit all set. Translate byte 3 to a mask and intersect
the corresponding byte 2. Each byte occupies its own eight-bit lane in
the integers; AND cannot carry across lanes. Every input byte is immutable.
"""
import os

BLOCK_BYTES = 65536
_HIGH_EXPONENT = bytes(128 if value & 127 == 127 else 0 for value in range(256))


def launch(environ=None):
    value = (os.environ if environ is None else environ).get('LTX_F32_SCAN', 'parent')
    if type(value) is not str or value not in ('parent', 'bulk'):
        raise ValueError('LTX_F32_SCAN must be parent or bulk')
    return value


def finite(raw):
    """Same verdict as every (word & 0x7f800000) != 0x7f800000.

    Empty bytes pass, matching all(). Bounded slices use no cache and no
    mutable view. Sign, mantissa, signed zero and subnormals stay untouched.
    """
    if type(raw) is not bytes or len(raw) % 4:
        raise ValueError('Immutable complete F32 bytes required')
    if (type(BLOCK_BYTES) is not int or BLOCK_BYTES != 65536 or
            type(_HIGH_EXPONENT) is not bytes or
            _HIGH_EXPONENT != b'\0' * 127 + b'\x80' + b'\0' * 127 + b'\x80'):
        raise ValueError('F32 scan constants changed')
    for start in range(0, len(raw), BLOCK_BYTES):
        block = raw[start:start + BLOCK_BYTES]
        high = int.from_bytes(block[3::4].translate(_HIGH_EXPONENT), 'little')
        low = int.from_bytes(block[2::4], 'little')
        if high & low:
            return False
    return True
