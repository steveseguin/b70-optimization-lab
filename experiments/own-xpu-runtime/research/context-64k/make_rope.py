#!/usr/bin/env python3
"""Regenerate the engine's BF16 RoPE model constant for N positions (default 65536) with the same authority as
rope.bf16 and main.cpp's runtime F32 table: glibc powf/cosf/sinf in single precision, angle = f32(f32(pos) *
powf(1e7f, -f32(2j)/64)), j = 0..31, stored [pos][j][cos, sin] as BF16 (round to nearest, ties to even).
Usage: make_rope.py OUT [POSITIONS] [OLD_TABLE]  -- prints sha256 and checks OLD_TABLE is a byte prefix."""
import ctypes, hashlib, struct, sys
libm = ctypes.CDLL('libm.so.6')
for f in ('powf', 'cosf', 'sinf'):
    getattr(libm, f).restype = ctypes.c_float
libm.powf.argtypes = [ctypes.c_float, ctypes.c_float]
libm.cosf.argtypes = libm.sinf.argtypes = [ctypes.c_float]
f32 = lambda x: struct.unpack('<f', struct.pack('<f', x))[0]
def bf16(x):
    u = struct.unpack('<I', struct.pack('<f', x))[0]
    return ((u + 0x7FFF + ((u >> 16) & 1)) >> 16) & 0xFFFF
out, n = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 65536
inv = [libm.powf(f32(1e7), f32(-float(2 * j) / 64.0)) for j in range(32)]
buf = bytearray()
for pos in range(n):
    for j in range(32):
        a = f32(f32(float(pos)) * inv[j])
        buf += struct.pack('<HH', bf16(libm.cosf(a)), bf16(libm.sinf(a)))
open(out, 'wb').write(buf)
print('positions', n, 'bytes', len(buf), 'sha256', hashlib.sha256(buf).hexdigest())
if len(sys.argv) > 3:
    old = open(sys.argv[3], 'rb').read()
    print('prefix identical over', len(old), 'bytes' if buf[:len(old)] == old else 'bytes: MISMATCH')
