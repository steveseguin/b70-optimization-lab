#!/usr/bin/env python3
"""One-line-per-rung summary of a campaign arm: identity rate, throughput, and site count.

Written during the 2026-09-09 4B campaign, which queues fifteen arms across four chains. Each one
needs the same three numbers per rung and the same site census, and retyping the aggregation for each
is how a transcription error gets into a result file.

Reports, per concurrency rung, the pooled exact/total across passes, the per-request divergence rate,
the median aggregate throughput, and how many distinct sites the divergences resolve to - where a
site is (prompt_id, first differing index, oracle token, run token), the unit the 2026-09-09 work
established is stable across reboots, days and compilation modes.

Pass several roots to compare arms; add --sites to list the sites themselves.

usage: summarize-arm.py ROOT [ROOT ...] [--lane ladder|ladder-mtp0|both] [--sites] [--json OUT]
"""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path


def summarize(root: Path, lane: str):
    p = root / lane / "ladder.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text())
    oracle = {r["prompt_id"]: r.get("token_ids") for r in (d.get("oracle") or {}).get("rows", [])}
    per = collections.defaultdict(lambda: {"exact": 0, "total": 0, "agg": [], "sites": collections.Counter()})
    for b in d.get("batches", []):
        e = per[b["concurrency"]]
        e["exact"] += b["oracle_exact_count"]
        e["total"] += b["oracle_exact_total"]
        e["agg"].append(b["aggregate_tok_s_wall"])
        for r in b.get("rows", []):
            o, t = oracle.get(r["prompt_id"]), r.get("token_ids")
            if not o or not t or o == t:
                continue
            i = next((k for k, (x, y) in enumerate(zip(o, t)) if x != y), 0)
            e["sites"][(r["prompt_id"], i, o[i], t[i])] += 1
    out = {}
    for c, e in sorted(per.items()):
        agg = sorted(e["agg"])
        out[c] = {
            "exact": e["exact"], "total": e["total"],
            "divergent": e["total"] - e["exact"],
            "rate_pct": round(100 * (e["total"] - e["exact"]) / max(e["total"], 1), 3),
            "agg_tok_s_median": round(agg[len(agg) // 2], 1) if agg else None,
            "passes": len(e["agg"]),
            "distinct_sites": len(e["sites"]),
            "sites": {f"{k[0]}@{k[1]} {k[2]}->{k[3]}": n for k, n in e["sites"].most_common()},
        }
    return out


def main() -> int:
    argv = sys.argv[1:]
    lanes, show_sites, out_path, roots = ["ladder", "ladder-mtp0"], False, None, []
    i = 0
    while i < len(argv):
        if argv[i] == "--lane":
            lanes = ["ladder", "ladder-mtp0"] if argv[i + 1] == "both" else [argv[i + 1]]; i += 2
        elif argv[i] == "--sites":
            show_sites = True; i += 1
        elif argv[i] == "--json":
            out_path = Path(argv[i + 1]); i += 2
        else:
            roots.append(Path(argv[i])); i += 1
    if not roots:
        print(__doc__)
        return 2
    report = {}
    print(f"{'arm':<34}{'lane':<13}{'rung':<6}{'exact':<14}{'div%':>7}{'tok/s':>9}{'sites':>7}")
    for root in roots:
        for lane in lanes:
            res = summarize(root, lane)
            if res is None:
                continue
            report.setdefault(root.name, {})[lane] = res
            for c, r in res.items():
                print(f"  {root.name[-30:]:<32}{lane:<13}c{c:<5}"
                      f"{r['exact']}/{r['total']:<9}{r['rate_pct']:>6.2f}%"
                      f"{r['agg_tok_s_median'] or 0:>9.1f}{r['distinct_sites']:>7}")
                if show_sites:
                    for s, n in list(r["sites"].items())[:12]:
                        print(f"        {n:>4}  {s}")
    if out_path is not None:
        out_path.write_text(json.dumps(report, indent=1) + "\n")
        print(f"\nwrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
