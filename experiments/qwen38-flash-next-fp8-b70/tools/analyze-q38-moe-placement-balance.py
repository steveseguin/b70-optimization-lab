#!/usr/bin/env python3
"""Per-rank MoE load under expert placements, from a Q38_DUMP_TOPK dump (list of (layer_name, topk_ids[M, top_k])).
For each decode step and MoE layer, counts distinct local experts hit per rank (= Triton blocks per rank at M=1) under
linear (expert e -> rank e // 128), round_robin (e % 4) and a greedy frequency-balanced static placement built from the
first half of the steps and evaluated on the second half. Reports mean per-step sums of max-over-ranks and of
(max - mean) across the 48 layers, i.e. the skew a collective absorbs, in blocks.
    analyze-q38-moe-placement-balance.py <moe-topk-ids-rank0.pt> [--experts 512] [--ranks 4] [--out json]
"""
from __future__ import annotations
import argparse, collections, json, statistics
import torch

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("dump"); ap.add_argument("--experts", type=int, default=512); ap.add_argument("--ranks", type=int, default=4); ap.add_argument("--out")
    a = ap.parse_args()
    entries = torch.load(a.dump, map_location="cpu")
    layers = sorted({name for name, _ in entries}, key=lambda n: int(n.split("layers.")[1].split(".")[0]) if "layers." in n else 0)
    per_layer = collections.defaultdict(list)
    for name, ids in entries:
        if ids.shape[0] != 1: continue
        per_layer[name].append(sorted(set(int(v) for v in ids.reshape(-1).tolist())))
    n_steps = min(len(v) for v in per_layer.values())
    print(f"layers {len(per_layer)}, decode steps {n_steps}, top-k {entries[0][1].shape[-1]}")
    E, R = a.experts, a.ranks; per_rank = E // R
    freq = {name: collections.Counter() for name in per_layer}
    for name, steps in per_layer.items():
        for s in steps[: n_steps // 2]:
            freq[name].update(s)
    def greedy(name):
        loads = [0] * R; place = {}
        for e, c in sorted(freq[name].items(), key=lambda kv: -kv[1]):
            r = min(range(R), key=lambda r: loads[r]); place[e] = r; loads[r] += c
        cold = [e for e in range(E) if e not in place]
        for i, e in enumerate(cold): place[e] = i % R
        return place
    placements = {"linear": lambda name: {e: e // per_rank for e in range(E)},
                  "round_robin": lambda name: {e: e % R for e in range(E)},
                  "greedy_balanced(train first half)": greedy}
    out = {}
    for pname, fn in placements.items():
        sum_max = []; sum_skew = []; sum_mean = []
        for step in range(n_steps // 2, n_steps):
            m = 0; sk = 0.0; mn = 0.0
            for name in per_layer:
                place = fn(name); hits = [0] * R
                for e in per_layer[name][step]: hits[place[e]] += 1
                mx = max(hits); me = sum(hits) / R
                m += mx; sk += mx - me; mn += me
            sum_max.append(m); sum_skew.append(sk); sum_mean.append(mn)
        out[pname] = dict(steps=len(sum_max), sum_max_blocks_per_step=round(statistics.mean(sum_max), 1), sum_mean_blocks_per_step=round(statistics.mean(sum_mean), 1), sum_skew_blocks_per_step=round(statistics.mean(sum_skew), 1), max_step=max(sum_max))
        print(f"{pname:36s} per step over 48 layers: sum(max rank blocks)={out[pname]['sum_max_blocks_per_step']:6.1f}  sum(mean)={out[pname]['sum_mean_blocks_per_step']:6.1f}  sum(max-mean)={out[pname]['sum_skew_blocks_per_step']:6.1f}  worst step {out[pname]['max_step']}")
    hot = sorted(((sum(freq[n].values()), n) for n in freq), reverse=True)[:3]
    top_experts = collections.Counter()
    for n in freq: top_experts.update(freq[n])
    print("most-hit experts overall (first half):", top_experts.most_common(8))
    if a.out: json.dump(out, open(a.out, "w"), indent=1)

if __name__ == "__main__":
    main()
