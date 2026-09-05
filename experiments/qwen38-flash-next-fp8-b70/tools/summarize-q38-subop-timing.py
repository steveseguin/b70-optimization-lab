#!/usr/bin/env python3
"""Reduce Q38_STEP_TIMING / Q38_LAYER_TIMING / Q38_SUBOP_TIMING server-log lines to per-rank medians by token count (M)."""
from __future__ import annotations
import argparse, collections, json, re, statistics
PAT = re.compile(r"\(Worker_(TP\d)_EP\d[^)]*\).*Q38_(STEP|LAYER|SUBOP)_TIMING (?:step|forward)=(\d+) tokens=(\d+) (.*)$")

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("server_log"); ap.add_argument("--out"); ap.add_argument("--tokens", default="1,2,3")
    a = ap.parse_args(); keep = {int(t) for t in a.tokens.split(",")}
    acc = collections.defaultdict(lambda: collections.defaultdict(list))
    for line in open(a.server_log, errors="replace"):
        m = PAT.search(line)
        if not m: continue
        rank, kind, _, tokens, rest = m.groups(); tokens = int(tokens)
        if tokens not in keep: continue
        for kv in rest.split():
            k, v = kv.split("="); acc[(kind, tokens, rank)][k].append(float(v))
    out = {}
    for (kind, tokens, rank), d in sorted(acc.items()):
        key = f"{kind.lower()}/M{tokens}/{rank}"
        out[key] = {k: dict(n=len(v), median=round(statistics.median(v), 2), min=round(min(v), 2), max=round(max(v), 2)) for k, v in d.items()}
        print(key, " ".join(f"{k.replace('_ms','')}={statistics.median(v):.1f}" for k, v in sorted(d.items()) if k.endswith("_ms")))
    if a.out: json.dump(out, open(a.out, "w"), indent=1)

if __name__ == "__main__":
    main()
