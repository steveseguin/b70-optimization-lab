#!/usr/bin/env python3
"""Fail-closed analysis of the rank-2 rescue rate.

Refuses to produce a number unless the run it reads is a benchmark-matched
diagnostic. The rate this computes decides whether the speculative tree is worth
implementing, and a rate measured on a different workload, or aggregated over
ranks that disagree, is worse than no rate at all: it looks like evidence.

Reports per-prompt numerator and denominator and a Wilson interval, because the
decision threshold sits inside the sampling noise and a point estimate alone
cannot close it.
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import sys
from pathlib import Path

# A cycle that rejected every draft token rejected at position 0, which is the
# only position the recorder captures a second candidate for.
def _wilson(successes: int, trials: int, z: float = 1.96) -> tuple[float, float]:
    if trials == 0:
        return (0.0, 0.0)
    p = successes / trials
    den = 1 + z * z / trials
    centre = p + z * z / (2 * trials)
    margin = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials))
    return ((centre - margin) / den, (centre + margin) / den)


def _rank_files(root: Path) -> list[Path]:
    files = sorted(Path(p) for p in glob.glob(str(root / "attribution" / "*.json")))
    if len(files) != 4:
        raise SystemExit(
            f"expected four rank payloads, found {len(files)}; a partial "
            "attribution set cannot be aggregated"
        )
    return files


def rescue_rate(root: Path, depth: int) -> dict:
    """Rescue statistics, or raise if the evidence is not trustworthy."""
    per_rank = []
    for path in _rank_files(root):
        rows = json.loads(path.read_text()).get("topk_probe") or []
        rows.sort(key=lambda r: r["cycle"])
        rejected = rescued = 0
        for a, b in zip(rows, rows[1:]):
            if b["cycle"] != a["cycle"] + 1:
                continue  # request boundary; the join would be meaningless
            if b["entry_num_rejected"] != depth:
                continue  # accepted at position 0, nothing to rescue
            rejected += 1
            if a["top2"] == b["entry_next_token_id"]:
                rescued += 1
        per_rank.append((rescued, rejected, len(rows)))

    counts = {(r, n) for r, n, _ in per_rank}
    if len(counts) != 1:
        raise SystemExit(
            f"ranks disagree on the rescue counts {sorted(counts)}; the probe "
            "is not observing one deterministic generation"
        )
    rescued, rejected, cycles = per_rank[0]
    if rejected == 0:
        raise SystemExit("no position-0 rejections observed; nothing to measure")
    low, high = _wilson(rescued, rejected)
    return {
        "cycles": cycles,
        "position0_rejected": rejected,
        "rescued": rescued,
        "rate": rescued / rejected,
        "wilson95": (low, high),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-root", type=Path, required=True)
    ap.add_argument("--benchmark", type=Path, required=True)
    ap.add_argument("--probe-rows", type=Path, required=True)
    ap.add_argument("--depth", type=int, required=True)
    ap.add_argument("--required-rate", type=float, required=True)
    args = ap.parse_args()

    sys.path.insert(0, str(Path(__file__).parent))
    from audit_probe_identity import audit

    failures = audit(args.benchmark, args.probe_rows)
    if failures:
        print("VERDICT=INVALID (workload mismatch)")
        for reason in failures:
            print(f"  - {reason}")
        return 1

    stats = rescue_rate(args.run_root, args.depth)
    low, high = stats["wilson95"]
    print(f"cycles={stats['cycles']} position0_rejected={stats['position0_rejected']}")
    print(f"rescued={stats['rescued']}  rate={stats['rate'] * 100:.2f}%")
    print(f"wilson95=[{low * 100:.2f}%, {high * 100:.2f}%]")
    print(f"required={args.required_rate * 100:.2f}%")

    if low >= args.required_rate:
        print("VERDICT=GO (interval clears the requirement)")
        return 0
    if high < args.required_rate:
        print("VERDICT=NO-GO (interval excludes the requirement)")
        return 2
    print("VERDICT=UNDECIDED (interval straddles the requirement)")
    print("  More cycles are needed, or the route is not worth pursuing.")
    return 3


if __name__ == "__main__":
    sys.exit(main())
