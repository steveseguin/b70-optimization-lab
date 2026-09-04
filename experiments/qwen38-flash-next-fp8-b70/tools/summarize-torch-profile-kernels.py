#!/usr/bin/env python3
"""Aggregate device-kernel durations from vLLM torch-profiler traces (XPU).

Reads every trace file under a profiler directory (Chrome trace JSON, gzip
or plain), keeps device-side kernel events, and reports per-kernel-name
totals, counts and mean durations for one rank, plus grand totals. With
--compare, prints the ratio table of two directories (e.g. the two-row MTP1
step against the one-row MTP0 step) by kernel name, ranked by the absolute
time difference, so the kernel that pays for the second row is visible
without trusting absolute profiler overhead.

    summarize-torch-profile-kernels.py --dir <profile dir> [--rank 0] [--top 40] [--out json]
    summarize-torch-profile-kernels.py --dir <a> --compare <b> [--out json]
"""
from __future__ import annotations
import argparse, gzip, json, os, re, sys
from collections import defaultdict


def load_events(path):
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8", errors="replace") as f:
        data = json.load(f)
    return data.get("traceEvents", data if isinstance(data, list) else [])


def rank_files(d, rank):
    files = []
    for root, _, names in os.walk(d):
        for n in names:
            if n.endswith((".json", ".json.gz", ".pt.trace.json", ".pt.trace.json.gz")):
                files.append(os.path.join(root, n))
    # rank-qualified names when present
    ranked = [f for f in files if re.search(rf"rank[_-]?{rank}\b|_{rank}\.pt", os.path.basename(f))]
    return sorted(ranked or files)


def summarize(d, rank):
    totals = defaultdict(lambda: {"count": 0, "us": 0.0})
    n_files = 0
    for f in rank_files(d, rank):
        n_files += 1
        for ev in load_events(f):
            if ev.get("ph") != "X":
                continue
            cat = str(ev.get("cat", "")).lower()
            if not any(k in cat for k in ("kernel", "gpu_memcpy", "gpu_memset", "xpu")):
                continue
            name = ev.get("name", "?")
            totals[name]["count"] += 1
            totals[name]["us"] += float(ev.get("dur", 0.0))
    return n_files, totals


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", required=True); ap.add_argument("--compare"); ap.add_argument("--rank", type=int, default=0)
    ap.add_argument("--top", type=int, default=40); ap.add_argument("--out")
    a = ap.parse_args()
    nf, ta = summarize(a.dir, a.rank)
    grand = sum(v["us"] for v in ta.values())
    print(f"{a.dir}: files={nf} kernels={len(ta)} total_device_ms={grand/1e3:.1f}")
    result = {"dir": a.dir, "rank": a.rank, "files": nf, "total_device_ms": grand / 1e3, "kernels": {k: {"count": v["count"], "ms": v["us"] / 1e3} for k, v in ta.items()}}
    if a.compare:
        nfb, tb = summarize(a.compare, a.rank)
        grand_b = sum(v["us"] for v in tb.values())
        print(f"{a.compare}: files={nfb} kernels={len(tb)} total_device_ms={grand_b/1e3:.1f}")
        names = set(ta) | set(tb)
        rows = []
        for n in names:
            ua = ta[n]["us"] / 1e3 if n in ta else 0.0; ub = tb[n]["us"] / 1e3 if n in tb else 0.0
            rows.append((ua - ub, n, ua, ub, ta[n]["count"] if n in ta else 0, tb[n]["count"] if n in tb else 0))
        rows.sort(key=lambda r: -abs(r[0]))
        print(f"{'delta_ms':>10} {'A_ms':>9} {'B_ms':>9} {'A_n':>6} {'B_n':>6}  kernel")
        for d_, n, ua, ub, ca, cb in rows[: a.top]:
            print(f"{d_:10.1f} {ua:9.1f} {ub:9.1f} {ca:6d} {cb:6d}  {n[:90]}")
        result["compare"] = {"dir": a.compare, "total_device_ms": grand_b / 1e3, "rows": [{"kernel": n, "delta_ms": d_, "a_ms": ua, "b_ms": ub, "a_count": ca, "b_count": cb} for d_, n, ua, ub, ca, cb in rows]}
    else:
        for n, v in sorted(ta.items(), key=lambda kv: -kv[1]["us"])[: a.top]:
            print(f"{v['us']/1e3:9.1f} ms {v['count']:7d}  {n[:100]}")
    if a.out:
        json.dump(result, open(a.out, "w"), indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
