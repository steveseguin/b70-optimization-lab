#!/usr/bin/env python3
"""Build a Q38_EXPERT_HOST_PLACEMENT JSON from top-k id dumps: per rank (linear placement,
128 local experts per rank), choose never-hit (layer, local expert) pairs, coldest first,
until the requested host bytes per rank are reached; layers are filled evenly."""
import argparse, collections, json, re
import torch

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", action="append", required=True, help="moe-topk-ids-rank0.pt files (union of hits)")
    ap.add_argument("--host-gib-per-rank", type=float, required=True)
    ap.add_argument("--rank", type=int, default=0, help="rank whose local experts to place (linear placement)")
    ap.add_argument("--layers", type=int, default=48); ap.add_argument("--experts-per-rank", type=int, default=128)
    ap.add_argument("--bytes-per-expert", type=int, default=128 * 0 + (1280 * 2560 + 2560 * 640))  # w13 + w2 rows in FP8
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    hits = collections.Counter(); rows = 0
    for path in a.dump:
        for name, ids in torch.load(path, weights_only=False):
            s = str(getattr(name, "value", name)); m = re.search(r"layers\.(\d+)\.", s); L = int(m.group(1))
            for row in ids.tolist():
                rows += 1
                for e in row: hits[(L, int(e))] += 1
    lo, hi = a.rank * a.experts_per_rank, (a.rank + 1) * a.experts_per_rank
    budget = int(a.host_gib_per_rank * 2**30) // a.bytes_per_expert
    per_layer = budget // a.layers + 1
    placement = {}; total = 0
    for L in range(a.layers):
        cand = sorted((hits.get((L, e), 0), e) for e in range(lo, hi))
        chosen = [e - lo for c, e in cand[:per_layer] if c == 0][: max(0, budget - total)]
        if chosen: placement[str(L)] = sorted(chosen); total += len(chosen)
    json.dump(placement, open(a.out, "w"), indent=0)
    print(f"rows {rows}, never-hit pairs in rank {a.rank}: {sum(1 for L in range(a.layers) for e in range(lo, hi) if hits.get((L, e), 0) == 0)} of {a.layers * a.experts_per_rank}; placed {total} experts ({total * a.bytes_per_expert / 2**30:.2f} GiB) across {len(placement)} layers -> {a.out}")

if __name__ == "__main__":
    main()
