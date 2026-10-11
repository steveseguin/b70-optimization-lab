"""Recreate packet2 fixture bytes without its ignored build tree or torch.

This mirrors packet2/tests/run_cpu.py's fixed RNG stream, verified against its
tracked fixture hashes; bounded real samples use the tracked origin offsets.
"""
import json
import random
import struct
from common import BASE, FIXTURES, planlib, sha

KINDS = {'F32': (0, 1, 4), 'F16': (1, 1, 2), 'BF16': (30, 1, 2),
         'Q8_0': (8, 32, 34), 'Q3_K': (11, 256, 110), 'Q6_K': (14, 256, 210),
         'IQ3_XXS': (18, 256, 98), 'IQ4_NL': (20, 32, 18), 'IQ3_S': (21, 256, 110), 'IQ2_S': (22, 256, 82)}


def regenerate(records):
    rng = random.Random(20261011)
    for _ in range(20000):
        rng.getrandbits(32)  # output-cast fixtures precede the randomized grids
    def write(label, kind, raw, k, activation=30):
        x = [((i * 37) % 127 - 63) / 64 for i in range(k)]
        xb = b''.join(struct.pack('<f', v)[2:] if activation == 30 else struct.pack('<e', v) for v in x)
        (FIXTURES / (label + '.fixture')).write_bytes(struct.pack('<IIIII', KINDS[kind][0], k, 4, activation, activation) + raw + xb)
    for kind, (type_id, block, size) in KINDS.items():
        k = 2560 if block > 1 else 320
        for trial in range(2):
            blocks = []
            for n in range(4 * k // block):
                b = bytearray(rng.randbytes(size))
                if kind == 'F32': b[:] = struct.pack('<f', rng.uniform(-2, 2))
                elif kind == 'F16': b[:] = struct.pack('<e', rng.uniform(-2, 2))
                elif kind == 'BF16': b[:] = struct.pack('<f', rng.uniform(-2, 2))[2:]
                else:
                    scale = struct.pack('<e', (-1 if n % 2 else 1) * (2**(-14) if trial else .0078125))
                    if kind in ('Q3_K', 'Q6_K'): b[-2:] = scale
                    else: b[:2] = scale
                if kind == 'IQ2_S':
                    for q in range(32):
                        ix = (n * 32 + q) % 1024
                        b[2 + q] = ix & 255
                        b[66 + q // 4] = (b[66 + q // 4] & ~(3 << (2 * (q % 4)))) | ((ix >> 8) << (2 * (q % 4)))
                elif kind == 'IQ3_S':
                    for q in range(64):
                        ix = (n * 64 + q) % 512
                        b[2 + q] = ix & 255
                        b[66 + q // 8] = (b[66 + q // 8] & ~(1 << (q % 8))) | ((ix >> 8) << (q % 8))
                elif kind == 'IQ3_XXS':
                    for q in range(64): b[2 + q] = (n * 64 + q) % 256
                blocks.append(b)
            write('random%d-%s' % (trial, kind), kind, b''.join(blocks), k, 1 if trial else 30)
    for row in records:
        if not row['label'].startswith('real-'): continue
        origin = row['origin']
        path = planlib.MODEL / origin['shard']
        with path.open('rb', buffering=0) as f:
            import os
            before = os.fstat(f.fileno())
            raw = os.pread(f.fileno(), origin['bytes'], origin['offset'])
            after = os.fstat(f.fileno())
        identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        if len(raw) != origin['bytes'] or identity(before) != identity(after):
            raise ValueError('real fixture changed while sampling')
        write(row['label'], row['type'], raw, row['columns'])
