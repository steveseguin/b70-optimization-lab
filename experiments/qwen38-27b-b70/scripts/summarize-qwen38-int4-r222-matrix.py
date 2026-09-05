#!/usr/bin/env python3
"""Summarize the R222 INT4 fixed-K matrix roots into one table + JSON (strict rates, gates, ladder identity)."""
import glob, json, os, re, sys
OUT = "/mnt/fast-ai/bench-results"
rows = []
for root in sorted(glob.glob(f"{OUT}/qwen38-int4-fixed-k-tp*-mtp*-*-20260905-r222")):
    name = os.path.basename(root); m = re.match(r"qwen38-int4-fixed-k-tp(\d)-mtp(\d)-(full|strict|ladders)-", name)
    tp, depth, kind = m.groups(); log = f"{root}/campaign.log"
    gates = {}; rates = {}
    if os.path.exists(log):
        for line in open(log):
            g = re.search(r"\] (G\d[^:]*): (\d+/\d+)", line)
            if g: gates[g.group(1)] = g.group(2)
            r = re.search(r"\] (\S+): class_balanced_median_tok_s=([\d.]+)", line)
            if r: rates[r.group(1)] = round(float(r.group(2)), 3)
    ladders = {}
    for lad in glob.glob(f"{root}/ladder*/ladder.json"):
        d = json.load(open(lad)); ladders[os.path.basename(os.path.dirname(lad))] = [
            {"c": b["concurrency"], "tok_s": round(b["aggregate_tok_s_wall"], 1), "exact": f'{b["oracle_exact_count"]}/{b["oracle_exact_total"]}'} for b in d["batches"]]
    rows.append({"root": name, "tp": int(tp), "depth": int(depth), "kind": kind, "aborted": os.path.exists(f"{root}/ABORTED"), "gates": gates, "rates": rates, "ladders": ladders})
for r in rows:
    print(f"TP{r['tp']} depth{r['depth']} {r['kind']:7s} {'ABORTED' if r['aborted'] else ''} gates={r['gates']} rates={r['rates']}")
    for k, v in r["ladders"].items(): print(f"   {k}: " + " ".join(f"c{b['c']}={b['exact']}@{b['tok_s']}" for b in v))
if len(sys.argv) > 1: json.dump(rows, open(sys.argv[1], "w"), indent=1)
