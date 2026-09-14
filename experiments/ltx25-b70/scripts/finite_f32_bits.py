"""Exact bounded finite-F32 scan using integer bit intersections, no floats.

Samples are their original little-endian IEEE754 bytes. This changes no sample
and uses at most one 64KiB block plus fixed-size integer temporaries.
"""
import struct

BLOCK_BYTES = 65536
# Select bit23 (the least significant exponent bit) in every packed F32 word.
EXPONENT_STARTS = int.from_bytes(b'\x00\x00\x80\x00' * (BLOCK_BYTES // 4), 'little')


def first_nonfinite_f32(data):
    """Return the first infinity/NaN sample index, or None for all-finite data.

    Compatible contiguous byte buffers are read without conversion. Callers
    must own immutable contents during the scan. Incomplete samples are errors.
    """
    with memoryview(data) as raw:
        if not raw.c_contiguous:
            raise BufferError('memoryview: underlying buffer is not C-contiguous')
        with raw.cast('B') as view:
            if len(view) % 4:
                raise struct.error('iterative unpacking requires a buffer of a multiple of 4 bytes')
            for offset in range(0, len(view), BLOCK_BYTES):
                bits = int.from_bytes(view[offset:offset + BLOCK_BYTES], 'little', signed=False)
                # After these three intersections, bit i is set iff all eight
                # original bits i..i+7 were set. At each selected bit23 this
                # examines only exponent bits23..30, never sign or mantissa.
                bits &= bits >> 4
                bits &= bits >> 2
                bits &= bits >> 1
                hits = bits & EXPONENT_STARTS
                if hits:
                    first_bit = hits & -hits
                    return offset // 4 + (first_bit.bit_length() - 1) // 32
    return None
