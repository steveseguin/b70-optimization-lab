#!/usr/bin/env python3
"""Extract per-layer inputs from a llama_dump file for teacher-forced layer checks.

  dsv41_llama_inject.py llama_dump.bin inject.bin

Writes, for each layer L in 0..38: l_out-L (the streams leaving layer L, [P,4,D])
followed by hc_pre-L occurrence 1 (that layer's FFN pre-mix, [P,4]) as raw f32.
cpu_run_v41 with OWN_LLAMA_INJECT=inject.bin replaces its own layer-(L+1) inputs
with these, so every layer is compared against llama.cpp from llama.cpp's input.
"""
import struct, sys
import numpy as np

want = {}
with open(sys.argv[1], "rb") as f:
    occ = {}
    while True:
        b = f.read(4)
        if len(b) < 4:
            break
        nl = struct.unpack("<I", b)[0]
        name = f.read(nl).decode()
        f.read(32)
        n = struct.unpack("<Q", f.read(8))[0]
        i = occ.get(name, 0)
        occ[name] = i + 1
        base, _, lay = name.rpartition("-")
        if lay.isdigit() and ((base == "l_out" and i == 0) or (base == "hc_pre" and i == 1)):
            want[(base, int(lay))] = np.fromfile(f, dtype=np.float32, count=n)
        else:
            f.seek(4 * n, 1)
with open(sys.argv[2], "wb") as o:
    for L in range(39):
        a, b = want[("l_out", L)], want[("hc_pre", L)]
        o.write(struct.pack("<QQ", a.size, b.size))
        a.tofile(o)
        b.tofile(o)
print("layers written: 39, floats per layer:", want[("l_out", 0)].size, want[("hc_pre", 0)].size)
