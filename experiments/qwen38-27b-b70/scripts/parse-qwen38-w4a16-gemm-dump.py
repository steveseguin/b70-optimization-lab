#!/usr/bin/env python3
"""Parse QWEN38_GEMM_W4A16 dump lines (R220 oneDNN patch) into natural-strategy tables.

usage: parse-qwen38-w4a16-gemm-dump.py DUMP_STDERR [--json OUT]
Prints, per (m=N_out, k), the row-count ranges (n) each catalog entry covers, and the unique strategy strings with
their unroll so they can be fed back as QWEN38_W4A16_GEMM_STRATEGY="<unrollM> <unrollN> <strategy>".
"""
import argparse, collections, json, re, sys
LINE = re.compile(r"QWEN38_GEMM_W4A16 m=(\d+) n=(\d+) k=(\d+) unroll=(\d+)x(\d+) wg=(\d+)x(\d+)x(\d+) k0=(\d+) wgK=(\d+) aScale2D=(\d) aqGroupM=(-?\d+) aqGroupK=(-?\d+) aOffset=(\d+) A=(\d+) B=(\d+) C=(\d+) override=(\d) entry=(.*)$")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("dump"); ap.add_argument("--json")
    a = ap.parse_args()
    rows = []
    for line in open(a.dump, errors="replace"):
        m = LINE.search(line)
        if not m: continue
        g = m.groups()
        rows.append({"m": int(g[0]), "n": int(g[1]), "k": int(g[2]), "unroll": f"{g[3]}x{g[4]}", "wg": f"{g[5]}x{g[6]}x{g[7]}", "k0": int(g[8]), "wgK": int(g[9]),
                     "aScale2D": int(g[10]), "aqGroupM": int(g[11]), "aqGroupK": int(g[12]), "aOffset": int(g[13]), "layouts": (int(g[14]), int(g[15]), int(g[16])), "override": int(g[17]), "entry": g[18].strip()})
    by_shape = collections.defaultdict(lambda: collections.defaultdict(set))
    for r in rows:
        by_shape[(r["m"], r["k"])][(r["entry"], r["unroll"], r["wg"], r["k0"], r["wgK"])].add(r["n"])
    strategies = collections.OrderedDict()
    for (m, k), ents in sorted(by_shape.items()):
        print(f"== m(N_out)={m} k={k}")
        for (entry, unroll, wg, k0, wgK), ns in sorted(ents.items(), key=lambda kv: min(kv[1])):
            ns = sorted(ns); print(f"   n={ns[0]}..{ns[-1]} ({len(ns)} sizes) unroll={unroll} wg={wg} k0={k0} wgK={wgK}\n      {entry[:200]}")
            strategies.setdefault(entry, {"unroll": unroll, "shapes": []})["shapes"].append({"m": m, "k": k, "n_min": ns[0], "n_max": ns[-1]})
    print(f"\n{len(strategies)} unique catalog entries across {len(by_shape)} shapes")
    if a.json:
        json.dump({"rows": rows, "unique_entries": [{"entry": e, **v} for e, v in strategies.items()]}, open(a.json, "w"), indent=1)
    if rows: print("problem fields (first row):", {k: rows[0][k] for k in ("aScale2D", "aqGroupM", "aqGroupK", "aOffset", "layouts")})


if __name__ == "__main__":
    sys.exit(main())
