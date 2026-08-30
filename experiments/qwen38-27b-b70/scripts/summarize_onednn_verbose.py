#!/usr/bin/env python3
"""Aggregate oneDNN verbose execution records after a server-log marker."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
from collections import defaultdict
from pathlib import Path


def percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def summarize(
    log: Path, after_pattern: str, top: int, source_label: str | None = None
) -> dict[str, object]:
    groups: dict[tuple[str, str, str, str], list[float]] = defaultdict(list)
    device_totals: dict[str, float] = defaultdict(float)
    device_counts: dict[str, int] = defaultdict(int)
    marker_seen = False
    malformed = 0

    with log.open(errors="replace") as handle:
        for line in handle:
            if after_pattern in line:
                marker_seen = True
            if not marker_seen or not line.startswith("onednn_verbose"):
                continue
            if ",primitive,exec," not in line:
                continue
            row = next(csv.reader([line]))
            if len(row) < 13:
                malformed += 1
                continue
            try:
                duration_ms = float(row[-1])
            except ValueError:
                malformed += 1
                continue
            device, primitive, implementation, problem = row[4], row[5], row[6], row[11]
            groups[(device, primitive, implementation, problem)].append(duration_ms)
            device_totals[device] += duration_ms
            device_counts[device] += 1

    devices: dict[str, object] = {}
    for device in sorted(device_totals):
        rows = []
        for (row_device, primitive, implementation, problem), durations in groups.items():
            if row_device != device:
                continue
            total_ms = sum(durations)
            rows.append(
                {
                    "primitive": primitive,
                    "implementation": implementation,
                    "problem": problem,
                    "calls": len(durations),
                    "total_ms": total_ms,
                    "share_percent": 100.0 * total_ms / device_totals[device],
                    "median_ms": statistics.median(durations),
                    "p95_ms": percentile(durations, 0.95),
                    "max_ms": max(durations),
                }
            )
        rows.sort(key=lambda row: (-row["total_ms"], row["problem"]))
        devices[device] = {
            "exec_records": device_counts[device],
            "summed_primitive_duration_ms": device_totals[device],
            "top_groups": rows[:top],
        }

    return {
        "schema": "neural.download.onednn-verbose-summary.v1",
        "source_log": source_label or str(log),
        "source_log_sha256": hashlib.sha256(log.read_bytes()).hexdigest(),
        "after_pattern": after_pattern,
        "marker_seen": marker_seen,
        "malformed_exec_records": malformed,
        "exec_records": sum(device_counts.values()),
        "devices": devices,
        "interpretation_boundary": (
            "Primitive durations are summed independently per GPU after the first marker. "
            "They may overlap with non-oneDNN kernels and host work; shares rank oneDNN work, "
            "not complete endpoint wall time. Verbose logging perturbs performance."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--after-pattern", default="processing task")
    parser.add_argument("--top", type=int, default=25)
    parser.add_argument(
        "--source-label",
        help="Portable evidence label to record instead of the local input path.",
    )
    args = parser.parse_args()
    if args.top <= 0:
        parser.error("--top must be positive")
    result = summarize(args.log, args.after_pattern, args.top, args.source_label)
    if not result["marker_seen"] or result["exec_records"] == 0:
        raise SystemExit("no post-marker oneDNN primitive exec records found")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "exec_records": result["exec_records"],
        "devices": {
            device: {
                "summed_primitive_duration_ms": summary["summed_primitive_duration_ms"],
                "top_group": summary["top_groups"][0],
            }
            for device, summary in result["devices"].items()
        },
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
