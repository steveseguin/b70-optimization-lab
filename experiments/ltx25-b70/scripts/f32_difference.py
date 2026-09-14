"""Exact IEEE binary32 diagnostics for finite values, using integer arithmetic.

Acceptance must still compare raw bytes: numerical differences erase signed zero.
These functions specify round-to-nearest, ties-to-even independently of a native
runtime's rounding or flush-to-zero mode. Actual Torch equivalence is untested.
"""
import math


def finite_units(word):
    """Return the finite uint32 F32 word's exact value in units of 2**-149.

    Both signed zeros return integer zero. All infinities and NaNs are rejected.
    """
    if type(word) is not int:
        raise TypeError('word must be a uint32 integer')
    if not 0 <= word < 2**32:
        raise ValueError('word must be a uint32 integer')
    exponent = (word >> 23) & 0xff
    mantissa = word & 0x7fffff
    if exponent == 0xff:
        raise ValueError('nonfinite F32 word')
    units = mantissa if exponent == 0 else (mantissa | (1 << 23)) << (exponent - 1)
    return -units if word & 0x80000000 else units


def rounded_abs_difference(max_delta_units):
    """Round a nonnegative exact difference to F32 once, returning bits and value.

    Round-to-nearest is monotone, so callers may maximize exact integer absolute
    differences first. Overflow becomes positive infinity, including the tie at
    the boundary between maximum finite F32 and the next power of two.
    """
    if type(max_delta_units) is not int:
        raise TypeError('difference must be a nonnegative integer')
    if max_delta_units < 0:
        raise ValueError('difference must be a nonnegative integer')
    if max_delta_units < 1 << 23:
        bits = max_delta_units
        value = math.ldexp(max_delta_units, -149)
    elif max_delta_units.bit_length() > 277:
        bits, value = 0x7f800000, math.inf
    else:
        shift = max(0, max_delta_units.bit_length() - 24)
        significand = max_delta_units >> shift
        if shift:
            remainder = max_delta_units - (significand << shift)
            halfway = 1 << (shift - 1)
            if remainder > halfway or (remainder == halfway and significand & 1):
                significand += 1
        if significand == 1 << 24:
            significand >>= 1
            shift += 1
        if shift >= 254:
            bits, value = 0x7f800000, math.inf
        else:
            bits = ((shift + 1) << 23) | (significand - (1 << 23))
            value = math.ldexp(significand, shift - 149)
    return {'max_abs_diff': value, 'max_abs_diff_f32_bits': f'0x{bits:08x}'}
