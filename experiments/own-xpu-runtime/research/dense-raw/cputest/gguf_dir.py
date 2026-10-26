#!/usr/bin/env python3
"""Minimal GGUF (v3) tensor directory reader: prints name, shard, absolute offset, bytes, ggml type, dims.
Used to list the dense Q6_K / Q8_0 tensors the p33 expanded layout covers (dense-raw lab, 2026-10-26)."""
import struct, sys, json
from pathlib import Path

TYPE_SIZE = {0: (1, 4), 1: (1, 2), 8: (32, 34), 14: (256, 210), 30: (1, 2), 18: (256, 98), 20: (32, 18), 21: (256, 110),
             22: (256, 82), 23: (256, 136), 12: (256, 144), 13: (256, 176), 11: (256, 110), 42: (64, 18)}

def rd(f, fmt):
    s = struct.calcsize(fmt); return struct.unpack('<' + fmt, f.read(s))

def rstr(f):
    (n,) = rd(f, 'Q'); return f.read(n).decode('utf-8', 'replace')

def rval(f, t):
    if t in (0, 1): return rd(f, 'B' if t == 0 else 'b')[0]
    if t in (2, 3): return rd(f, 'H' if t == 2 else 'h')[0]
    if t in (4, 5): return rd(f, 'I' if t == 4 else 'i')[0]
    if t == 6: return rd(f, 'f')[0]
    if t == 7: return rd(f, '?')[0]
    if t == 8: return rstr(f)
    if t == 9:
        (et,) = rd(f, 'I'); (n,) = rd(f, 'Q'); return [rval(f, et) for _ in range(n)]
    if t in (10, 11): return rd(f, 'Q' if t == 10 else 'q')[0]
    if t == 12: return rd(f, 'd')[0]
    raise ValueError(t)

def directory(path):
    out = []
    with open(path, 'rb') as f:
        assert f.read(4) == b'GGUF'
        (ver,) = rd(f, 'I'); (nt,) = rd(f, 'Q'); (nkv,) = rd(f, 'Q')
        align = 32
        for _ in range(nkv):
            k = rstr(f); (t,) = rd(f, 'I'); v = rval(f, t)
            if k == 'general.alignment': align = v
        infos = []
        for _ in range(nt):
            name = rstr(f); (nd,) = rd(f, 'I'); dims = list(rd(f, 'Q' * nd)); (t,) = rd(f, 'I'); (off,) = rd(f, 'Q')
            infos.append((name, dims, t, off))
        base = (f.tell() + align - 1) // align * align
    for name, dims, t, off in infos:
        el, by = TYPE_SIZE[t]; n = 1
        for d in dims: n *= d
        out.append(dict(name=name, file=str(path), offset=base + off, bytes=n // el * by, type=t, dims=dims))
    return out

if __name__ == '__main__':
    d = Path(sys.argv[1]); rows = []
    for p in sorted(d.glob('*.gguf')): rows += directory(p)
    json.dump(rows, sys.stdout)
