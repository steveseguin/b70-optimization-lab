#!/usr/bin/env python3
"""Summarise a Laguna breakable-graph event profile by segment kind.

Answers the question the roofline cannot: of one verifier forward, how much
time is spent inside captured graph segments (weight streaming + compute)
versus stalled at the 97 collective and 48 attention eager boundaries.
"""
import json, sys, statistics as st
from pathlib import Path

root = Path(sys.argv[1])
ranks = sorted(root.glob("rank*.json"))
if not ranks:
    raise SystemExit(f"no rank payloads under {root}")
for path in ranks:
    d = json.loads(path.read_text())
    iv = d["intervals"]
    by = {}
    for row in iv:
        by.setdefault(row["kind"], []).append(row["duration_ns"])
    total = d["total_duration_ns"]
    print(f"\n{path.name}  total={total/1e6:.3f} ms  intervals={len(iv)}")
    print(f"  {'kind':<12}{'n':>5}{'sum_ms':>10}{'share':>8}{'med_us':>10}{'max_us':>10}")
    for kind, vals in sorted(by.items(), key=lambda kv: -sum(kv[1])):
        s = sum(vals)
        print(f"  {kind:<12}{len(vals):>5}{s/1e6:>10.3f}{s/total*100:>7.1f}%"
              f"{st.median(vals)/1e3:>10.2f}{max(vals)/1e3:>10.2f}")
