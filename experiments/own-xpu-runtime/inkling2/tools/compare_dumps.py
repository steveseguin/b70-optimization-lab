#!/usr/bin/env python3
"""compare_dumps.py <ref_dir> <ours_dir> [name-substring ...]

Both dirs hold <name>.f32 files and an index.tsv (name, type, ne0..ne3), as written by tools/ref_dump.cpp (the
reference) and by the engine's INK_DUMP. For every name present in both, prints the relative L2 error
|ours - ref| / |ref|, the largest absolute difference, and the cosine, in the reference's order. The first tensor
whose relative error jumps is where to look."""
import os, sys
import numpy as np

def load_index(d):
    out = {}
    order = []
    with open(os.path.join(d, 'index.tsv')) as f:
        for line in f:
            p = line.rstrip('\n').split('\t')
            if len(p) < 6:
                continue
            name = p[0]
            out[name] = [int(x) for x in p[2:6]]
            order.append(name)
    return out, order

def main():
    ref_dir, our_dir = sys.argv[1], sys.argv[2]
    subs = sys.argv[3:]
    ref, order = load_index(ref_dir)
    ours, _ = load_index(our_dir)
    worst = 0.0
    n = 0
    for name in order:
        if name not in ours or (subs and not any(s in name for s in subs)):
            continue
        a = np.fromfile(os.path.join(ref_dir, name + '.f32'), dtype=np.float32).astype(np.float64)
        b = np.fromfile(os.path.join(our_dir, name + '.f32'), dtype=np.float32).astype(np.float64)
        if a.size != b.size:
            print(f'{name:28s} SIZE ref {a.size} ours {b.size}')
            continue
        d = b - a
        rel = np.linalg.norm(d) / (np.linalg.norm(a) + 1e-30)
        cos = float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-30))
        print(f'{name:28s} rel {rel:9.2e}  maxabs {np.abs(d).max():9.2e}  cos {cos:.9f}  |ref| {np.linalg.norm(a):9.3e}')
        worst = max(worst, rel)
        n += 1
    print(f'{n} tensors compared, worst rel {worst:.2e}')

if __name__ == '__main__':
    main()
