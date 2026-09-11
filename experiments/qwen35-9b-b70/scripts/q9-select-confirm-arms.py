#!/usr/bin/env python3
"""Pick the screening arms worth re-running serially, and emit a P3 queue.

A P2 arm runs with three neighbours holding cards, so its rate is a screen, never a verdict. This
selects the arms that (a) passed their identity gates and (b) screened at or above the baseline,
and writes them back out as a queue to be re-run at parallelism 1 on a quiet host.

Selection is deliberately generous on the speed side and strict on identity: a lever that screens
flat can still win once the host is quiet, but a lever that lost exactness is closed regardless of
how fast it screened.

usage: q9-select-confirm-arms.py --baseline-run p0 --out QUEUE [--margin-pct -2.0]
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

BENCH = Path("/mnt/fast-ai/bench-results")
GATE_RE = re.compile(r"(G[123])[^:]*: (\d+)/(\d+)")
PERF_RE = re.compile(r"(\S+): class_balanced_median_tok_s=([0-9.]+)")


def read_campaign(root: Path) -> dict:
    log = root / "campaign.log"
    if not log.is_file():
        return {}
    text = log.read_text(errors="replace")
    gates: dict[str, tuple[int, int]] = {}
    for g, a, b in GATE_RE.findall(text):
        gates.setdefault(g, (int(a), int(b)))
        if int(a) < gates[g][0]:
            gates[g] = (int(a), int(b))
    perf = {label: float(v) for label, v in PERF_RE.findall(text)}
    return {
        "root": root,
        "aborted": (root / "ABORTED").is_file(),
        "abort_reason": (root / "ABORTED").read_text().strip() if (root / "ABORTED").is_file() else "",
        "gates": gates,
        "perf": perf,
        "best": max((v for k, v in perf.items() if not k.startswith("mtp0")), default=None),
        "mtp0": max((v for k, v in perf.items() if k.startswith("mtp0")), default=None),
    }


def arm_of(root: Path) -> str:
    return root.name.rsplit("-", 1)[-1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline-run", default="p0")
    ap.add_argument("--out", required=True)
    ap.add_argument("--margin-pct", type=float, default=-2.0,
                    help="keep an arm whose screen is at least this far from baseline (default -2%%)")
    ap.add_argument("--queue", default="/home/steve/llm-optimizations/experiments/qwen35-9b-b70/data/q9-arm-queue.tsv")
    args = ap.parse_args()

    roots = [p for p in BENCH.glob("qwen35-9b-*-20260909-*")
             if p.is_dir() and "failed" not in p.name and "aborted" not in p.name]
    data = {arm_of(r): read_campaign(r) for r in roots}
    data = {k: v for k, v in data.items() if v}

    base = data.get(args.baseline_run)
    if not base or base.get("best") is None:
        print(f"no usable baseline '{args.baseline_run}'; cannot rank")
        return 2
    baseline = base["best"]
    print(f"baseline {args.baseline_run}: {baseline:.3f} tok/s (mtp0 {base.get('mtp0')})")

    spec = {}
    for line in Path(args.queue).read_text().splitlines():
        line = line.split("#", 1)[0]
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            spec[parts[0].strip()] = parts

    keep, closed = [], []
    for arm, d in sorted(data.items()):
        if arm == args.baseline_run:
            continue
        gates = d["gates"]
        lossless = all(a == b for a, b in gates.values()) and bool(gates)
        best = d.get("best")
        if d["aborted"]:
            closed.append((arm, f"aborted: {d['abort_reason'][:60]}"))
            continue
        if not lossless:
            closed.append((arm, f"identity failed: {gates}"))
            continue
        if best is None:
            closed.append((arm, "no rate recorded"))
            continue
        delta = (best - baseline) / baseline * 100.0
        if delta < args.margin_pct:
            closed.append((arm, f"screened {best:.3f} ({delta:+.2f}%), below margin"))
            continue
        keep.append((delta, arm, best))

    keep.sort(reverse=True)
    out = Path(args.out)
    with out.open("w") as fh:
        fh.write("# P3 confirm queue: arms that passed identity and screened at or above baseline.\n")
        fh.write("# Re-run at parallelism 1; only these rates are verdicts.\n")
        for delta, arm, best in keep:
            parts = spec.get(arm)
            if not parts:
                fh.write(f"# {arm}: screened {best:.3f} ({delta:+.2f}%) but is not in the lever queue\n")
                continue
            parts = list(parts) + [""] * (5 - len(parts))
            fh.write("\t".join([f"{arm}c", parts[1], parts[2], parts[3], parts[4]]).rstrip() + "\n")
            print(f"  keep  {arm:<12} {best:8.3f} tok/s ({delta:+.2f}%)")
    for arm, why in closed:
        print(f"  close {arm:<12} {why}")
    print(f"\nwrote {len(keep)} confirm arms to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
