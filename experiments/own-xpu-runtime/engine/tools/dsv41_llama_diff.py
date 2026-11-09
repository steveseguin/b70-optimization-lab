#!/usr/bin/env python3
"""Cross-check the CPU reference runner against llama.cpp, tensor by tensor.

  dsv41_llama_diff.py llama_dump.bin own_pdump.bin [--all] [--tol 0.05] [--tokens P] [--median]

llama_dump.bin: written by the out-of-tree llama_dump tool (llama.cpp CPU build,
named graph tensors). own_pdump.bin: cpu_run_v41 with OWN_PDUMP=path (prefill).
Both use: u32 name_len, name, i64 ne[4], u64 n, n x f32. Prints the relative L2
error of ours against llama.cpp per tensor and the first one over tolerance.
llama.cpp's CPU backend quantizes activations to 8 bits inside quantized
matmuls, so ~1% noise is expected; a structural difference shows as >> 5%.
"""
import struct
import sys
import numpy as np


def read(path):
    out, order = {}, []
    with open(path, "rb") as f:
        while True:
            b = f.read(4)
            if len(b) < 4:
                break
            nl = struct.unpack("<I", b)[0]
            name = f.read(nl).decode()
            ne = struct.unpack("<4q", f.read(32))
            n = struct.unpack("<Q", f.read(8))[0]
            v = np.fromfile(f, dtype=np.float32, count=n)
            i = 0
            while (name, i) in out:
                i += 1
            out[(name, i)] = (ne, v)
            order.append((name, i))
    return out, order


# ours -> (llama name, occurrence)
def llama_key(name):
    base, _, lay = name.rpartition("-")
    if not lay.isdigit():
        return (name, 0)
    m = {"hc_pre_a": ("hc_pre", 0), "hc_pre_f": ("hc_pre", 1), "hc_post_a": ("hc_post", 0),
         "hc_post_f": ("hc_post", 1), "hc_comb_a": ("hc_comb", 0), "hc_comb_f": ("hc_comb", 1),
         "attn_wo_a": ("attn_wo_a-%s (permuted) (cont)", 0)}
    if base in m:
        n, occ = m[base]
        return ((n % lay) if "%s" in n else f"{n}-{lay}", occ)
    return (name, 0)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    show_all = "--all" in sys.argv
    tol = float(sys.argv[sys.argv.index("--tol") + 1]) if "--tol" in sys.argv else 0.05
    ntok = int(sys.argv[sys.argv.index("--tokens") + 1]) if "--tokens" in sys.argv else 0
    per_token = "--median" in sys.argv  # judge by the per-token median (teacher-forced runs)
    ll, _ = read(args[0])
    own, order = read(args[1])
    first = None
    for key in order:
        lk = llama_key(key[0])
        if lk not in ll:
            if show_all:
                print(f"{key[0]:22s} (no llama tensor {lk})")
            continue
        a = ll[lk][1]
        b = own[key][1]
        if a.size != b.size:
            if b.size < a.size and a.size % b.size == 0:  # ours = last token only
                a = a[-b.size:]
            else:
                print(f"{key[0]:22s} SIZE llama {ll[lk][0]} ours {b.size}")
                continue
        d = b - a
        rel = float(np.linalg.norm(d) / (np.linalg.norm(a) + 1e-30))
        tok = ""
        if ntok and a.size % ntok == 0 and a.size // ntok >= 64:  # per-token view: routing flips hit single tokens
            da, aa = d.reshape(ntok, -1), a.reshape(ntok, -1)
            pt = np.linalg.norm(da, axis=1) / (np.linalg.norm(aa, axis=1) + 1e-30)
            tok = f"  per-token median {np.median(pt):.3e} max {pt.max():.3e} over-tol {int((pt > tol).sum())}/{ntok}"
            if per_token:
                rel = float(np.median(pt))
        bad = rel > tol
        if bad and first is None:
            first = key[0]
        if show_all or bad or key[0].startswith("l_out") or key[0].startswith("result"):
            extra = ""
            if key[0] == "result_output":
                ta, tb = np.argsort(-a)[:5], np.argsort(-b)[:5]
                extra = f" llama top5 {ta.tolist()} gaps {np.round(a[ta[0]] - a[ta], 2).tolist()} | ours {tb.tolist()} gaps {np.round(b[tb[0]] - b[tb], 2).tolist()}"
            print(f"{key[0]:22s} rel {rel:9.3e}  maxabs {float(np.max(np.abs(d))):9.3e}  n {a.size:8d}{tok}{'  <-- over tol' if bad else ''}{extra}")
    print("FIRST OVER TOLERANCE:", first if first else "none")


if __name__ == "__main__":
    main()
