#!/usr/bin/env python3
"""Per-prompt divergence rate across the passes of one ladder.

The identity ladders report n/N exact per pass, which collapses 64 requests into one bit and hides the
structure underneath: divergence is not spread evenly over the suite. A handful of prompts carry all of
it, each with its own rate, and no prompt fails every time. Two passes cannot show that; twenty can.

This reports, per concurrency rung, which prompts ever diverged and in how many passes. The output is
what a fragile-prompt experiment needs to be designed: a site at 95% per pass is a near-certain
detector and worth filling a batch with, while a 5% site needs a different budget.

Distinguishing "concentrated and stochastic" from "deterministic given batch composition" matters for
mechanism too. A site that diverges in every pass would point at a fixed property of the batch shape;
rates strictly between 0 and 1 point at something that varies run to run at fixed shape.

usage: analyze-site-fragility.py ROOT [ROOT ...] [--lane ladder] [--json OUT]
"""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path


def analyse(root: Path, lane: str):
    p = root / lane / "ladder.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text())
    oracle = {r["prompt_id"]: r.get("token_ids") or [] for r in (d.get("oracle") or {}).get("rows", [])}
    per: dict[int, dict[int, set[str]]] = collections.defaultdict(dict)
    for b in d.get("batches", []):
        diverged = set()
        for r in b["rows"]:
            ref = oracle.get(r["prompt_id"])
            got = r.get("token_ids") or []
            if ref and got and ref != got:
                diverged.add(r["prompt_id"])
        per[b["concurrency"]][b["repeat"]] = diverged
    out = {}
    for c, passes in sorted(per.items()):
        n = len(passes)
        counts = collections.Counter()
        for s in passes.values():
            counts.update(s)
        out[c] = {
            "passes": n,
            "requests": c * n,
            "per_pass_divergent": [len(passes[k]) for k in sorted(passes)],
            "clean_passes": sum(1 for s in passes.values() if not s),
            "prompts_ever_divergent": len(counts),
            "always_divergent": sorted(p for p, k in counts.items() if k == n),
            "rates": {p: round(k / n, 3) for p, k in counts.most_common()},
        }
    return out


def main() -> int:
    argv = sys.argv[1:]
    lane = "ladder"
    out_path = None
    roots: list[Path] = []
    i = 0
    while i < len(argv):
        if argv[i] == "--lane":
            lane = argv[i + 1]; i += 2
        elif argv[i] == "--json":
            out_path = Path(argv[i + 1]); i += 2
        else:
            roots.append(Path(argv[i])); i += 1
    if not roots:
        print(__doc__)
        return 2
    report = {}
    for root in roots:
        res = analyse(root, lane)
        if res is None:
            print(f"{root.name}: no {lane}")
            continue
        report[root.name] = res
        print(f"=== {root.name} / {lane} ===")
        for c, r in res.items():
            print(f"  c={c:<4} {r['passes']} passes, {r['requests']} requests; "
                  f"per-pass divergent {r['per_pass_divergent']}")
            print(f"        {r['prompts_ever_divergent']} prompt(s) ever divergent, "
                  f"{len(r['always_divergent'])} in every pass, {r['clean_passes']} fully clean pass(es)")
            if r["rates"]:
                top = list(r["rates"].items())[:8]
                print("        rates: " + ", ".join(f"{p}={v:.0%}" for p, v in top))
    if out_path is not None:
        out_path.write_text(json.dumps(report, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
