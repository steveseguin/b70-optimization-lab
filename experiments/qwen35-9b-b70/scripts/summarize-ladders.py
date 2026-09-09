#!/usr/bin/env python3
"""Tabulate concurrency-identity ladders: aggregate rate and exactness at every rung.

One row per (arm, lane, concurrency). The exact column is the one that decides whether a rung is
publishable: aggregate throughput is scoped capacity evidence and never a single-user headline, so a
rung that is fast but not byte-exact against the sequential oracle is a measurement, not a result.

usage: summarize-ladders.py ROOT [ROOT ...]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def rows_for(root: Path):
    for ladder in sorted(root.glob("*/ladder.json")):
        try:
            d = json.loads(ladder.read_text())
        except Exception as exc:                      # a killed arm leaves a truncated file
            yield (root.name, ladder.parent.name, None, None, None, f"unreadable: {exc}")
            continue
        lane = ladder.parent.name
        qualified = d.get("output_identity_qualified")
        by_rung: dict[int, list] = {}
        for b in d.get("batches", []):
            by_rung.setdefault(b.get("concurrency"), []).append(b)
        for conc in sorted(k for k in by_rung if k is not None):
            passes = by_rung[conc]
            rate = "/".join(
                f"{p.get('aggregate_tok_s_wall'):.1f}" if isinstance(p.get("aggregate_tok_s_wall"), (int, float)) else "?"
                for p in passes
            )
            exact = "/".join(
                f"{p.get('oracle_exact_count')}:{p.get('oracle_exact_total')}" for p in passes
            )
            allx = all(bool(p.get("oracle_exact_all")) for p in passes)
            cz = all(bool(p.get("cached_tokens_all_zero")) for p in passes)
            note = "" if allx else "  <-- NOT EXACT"
            if not cz:
                note += "  <-- CACHE NOT ZERO"
            yield (root.name, lane, conc, rate, exact, ("qualified" if qualified else "unqualified") + note)


def main() -> int:
    roots = [Path(a) for a in sys.argv[1:]]
    if not roots:
        print(__doc__)
        return 2
    print(f"{'campaign':<52} {'lane':<14} {'users':>5}  {'aggregate tok/s (passes)':<26} {'exact/total':<16} status")
    any_row = False
    for root in roots:
        for campaign, lane, conc, rate, exact, status in rows_for(root):
            any_row = True
            print(f"{campaign:<52} {lane:<14} {str(conc):>5}  {str(rate):<26} {str(exact):<16} {status}")
    if not any_row:
        print("(no ladder.json found under the given roots)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
