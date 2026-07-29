#!/usr/bin/env python3
"""Summarize an interleaved A/B endpoint campaign.

Standing rules this enforces, not merely reports:

* A leg that failed exactness contributes no rate. It is counted as a failure
  and its number is never shown, because a rate from a non-exact run is not a
  measurement of anything.
* The median is the headline, and the mean is always printed beside it. A
  single leg is never the result.
* Legs are listed in the order they ran so interleaving is auditable.
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

RUN_ROOT = Path("/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs")
TARGET = 102.0


def leg_rate(run_dir: Path) -> tuple[float | None, str]:
    """Return (conventional tok/s, verdict). Rate is None unless fully exact."""
    status = (run_dir / "status.txt")
    if not status.is_file() or "PASS" not in status.read_text():
        return None, "leg did not reach PASS"

    exact_path = run_dir / "exactness-vs-q1.json"
    if not exact_path.is_file():
        return None, "no exactness artifact"
    exact = json.loads(exact_path.read_text())
    comparison = exact.get("candidates", [{}])[0].get("comparison", {})
    if not exact.get("all_exact"):
        return None, "all_exact false"
    if comparison.get("exact_count") != 13 or comparison.get("total") != 13:
        return None, f"exact {comparison.get('exact_count')}/{comparison.get('total')}"
    if not comparison.get("all_cached_zero"):
        return None, "cached_tokens not all zero"
    if not comparison.get("all_text_sha256_equal"):
        return None, "output text sha256 mismatch"

    metric = run_dir / "metric-accounting.stdout"
    if not metric.is_file():
        return None, "no metric accounting"
    rate = None
    for line in metric.read_text().splitlines():
        if line.startswith("conventional_interval_tok_s="):
            rate = float(line.split("=", 1)[1])
    if rate is None:
        return None, "no conventional interval field"
    return rate, "13/13 exact, cached_tokens=0"


def main(tag: str) -> int:
    runs = sorted(RUN_ROOT.glob(f"{tag}-*"), key=lambda p: p.name.split("-")[-1])
    if not runs:
        print(f"no runs found for tag {tag!r} under {RUN_ROOT}")
        return 1

    arms: dict[str, list[float]] = {}
    failures: dict[str, list[tuple[str, str]]] = {}

    print(f"campaign {tag}: {len(runs)} legs, in execution order\n")
    for run in runs:
        # <tag>-<label>-r<round>-<stamp>
        rest = run.name[len(tag) + 1:]
        label = rest.rsplit("-r", 1)[0]
        rate, verdict = leg_rate(run)
        arms.setdefault(label, [])
        failures.setdefault(label, [])
        if rate is None:
            failures[label].append((run.name, verdict))
            print(f"  {label:>12}  {'FAILED':>12}   {verdict}  [{run.name}]")
        else:
            arms[label].append(rate)
            print(f"  {label:>12}  {rate:12.6f}   {verdict}")

    print()
    header = f"{'arm':>12} {'n':>3} {'median':>12} {'mean':>12} {'min':>12} {'max':>12} {'>=102':>6} {'failed':>7}"
    print(header)
    print("-" * len(header))
    for label, rates in arms.items():
        nfail = len(failures[label])
        if not rates:
            print(f"{label:>12} {0:>3} {'--':>12} {'--':>12} {'--':>12} {'--':>12} {'--':>6} {nfail:>7}")
            continue
        print(
            f"{label:>12} {len(rates):>3} {statistics.median(rates):12.6f} "
            f"{statistics.fmean(rates):12.6f} {min(rates):12.6f} {max(rates):12.6f} "
            f"{sum(r >= TARGET for r in rates):>6} {nfail:>7}"
        )

    labels = [k for k, v in arms.items() if v]
    if len(labels) == 2:
        a, b = labels
        ma, mb = statistics.median(arms[a]), statistics.median(arms[b])
        delta = (mb - ma) / ma * 100.0
        print(f"\nmedian {b} vs {a}: {mb - ma:+.6f} tok/s ({delta:+.3f}%)")
        print("host endpoint noise floor is 1.63%; anything under ~1.5% is not resolvable.")
        if min(len(arms[a]), len(arms[b])) < 5:
            print("WARNING: fewer than 5 legs in an arm. Not decision-grade.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        print("usage: laguna_ab_summarize.py TAG")
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
