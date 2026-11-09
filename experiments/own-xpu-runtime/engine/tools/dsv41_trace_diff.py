#!/usr/bin/env python3
"""Compare two DeepSeek V4.1 decode traces (cpu_run_v41 reference vs own_run_v41 device).

Record format: [u32 step][u32 layer][u32 tag][u32 n][n x f32]; tags in
src/stage2/packet3/backend/trace_tags_v41.hpp.

  dsv41_trace_diff.py ref.trc dev.trc [--all] [--tol 0.05]

Prints one line per record present in both files: relative L2 error
|dev-ref| / |ref|, max abs error, and for id-like tags an exact compare. Without
--all only the first record over the tolerance in each (step, layer) is shown,
plus a per-layer summary of the block outputs (streams_ffn).
"""
import sys
import numpy as np

TAGS = ["?", "embed", "engram", "attn_mix_pre", "attn_mix_post", "attn_mix_comb", "attn_in", "q", "kv",
        "cidx", "attn_o", "attn_oa", "attn_out", "streams_attn", "ffn_mix_pre", "ffn_in", "route_logits",
        "route_ids", "route_prob", "shared_down", "ffn_out", "streams_ffn", "final_n", "logits", "pub_ckv",
        "pub_ik"]
ID_TAGS = {"cidx", "route_ids"}


def read(path):
    out, order = {}, []
    with open(path, "rb") as f:
        while True:
            h = np.fromfile(f, dtype=np.uint32, count=4)
            if h.size < 4:
                break
            v = np.fromfile(f, dtype=np.float32, count=int(h[3]))
            if v.size < h[3]:
                break
            key = (int(h[0]), int(h[1]), TAGS[int(h[2])] if h[2] < len(TAGS) else str(h[2]))
            out[key] = v
            order.append(key)
    return out, order


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    show_all = "--all" in sys.argv
    tol = float(sys.argv[sys.argv.index("--tol") + 1]) if "--tol" in sys.argv else 0.05
    ref, _ = read(args[0])
    dev, order = read(args[1])
    worst = {}
    first_bad = None
    shown = set()
    n_cmp = 0
    for key in order:
        if key not in ref:
            continue
        a, b = ref[key], dev[key]
        if a.size != b.size:
            print(f"step {key[0]} L{key[1]:02d} {key[2]:14s} SIZE {a.size} vs {b.size}")
            continue
        n_cmp += 1
        step, layer, tag = key
        if tag == "route_prob" and (step, layer, "route_ids") in ref and (step, layer, "route_ids") in dev:
            # near-ties swap the top-6 order; pair the probabilities by expert id
            ra, rb = ref[(step, layer, "route_ids")], dev[(step, layer, "route_ids")]
            a = a[np.argsort(ra, kind="stable")]
            b = b[np.argsort(rb, kind="stable")]
        if tag in ID_TAGS:
            same = np.array_equal(a, b) if tag == "cidx" else sorted(a.tolist()) == sorted(b.tolist())
            rel, mx = (0.0 if same else 1.0), float(np.max(np.abs(a - b)))
            note = "ids equal" if same else f"IDS DIFFER ref={a[:8].astype(int).tolist()} dev={b[:8].astype(int).tolist()}"
        else:
            fin = np.isfinite(a) & np.isfinite(b)
            bad_nan = int((~np.isfinite(b)).sum())
            d = (b - a)[fin]
            rel = float(np.linalg.norm(d) / (np.linalg.norm(a[fin]) + 1e-30))
            mx = float(np.max(np.abs(d))) if d.size else 0.0
            note = f"NONFINITE dev={bad_nan}" if bad_nan and not np.array_equal(np.isfinite(a), np.isfinite(b)) else ""
            if tag == "logits":
                note += f" argmax ref={int(np.argmax(a))} dev={int(np.argmax(b))}"
        bad = rel > tol or "DIFFER" in note or "NONFINITE" in note
        if bad and first_bad is None:
            first_bad = key
        worst[(step, layer)] = max(worst.get((step, layer), 0.0), rel)
        if show_all or (bad and (step, layer) not in shown) or tag in ("streams_ffn", "logits"):
            flag = "  <-- over tol" if bad else ""
            print(f"step {step} L{layer:02d} {tag:14s} rel {rel:9.3e}  maxabs {mx:9.3e}  n {a.size:6d} {note}{flag}")
            if bad:
                shown.add((step, layer))
    print(f"compared {n_cmp} records; tolerance {tol}")
    print("FIRST OVER TOLERANCE:", first_bad if first_bad else "none")
    return 1 if first_bad else 0


if __name__ == "__main__":
    sys.exit(main())
