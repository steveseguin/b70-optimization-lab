#!/usr/bin/env python3
"""Summarize vLLM XPU decode timing log lines."""

from __future__ import annotations

import argparse
import json
import re
import statistics
from pathlib import Path


SAMPLE_RE = re.compile(
    r"\[vllm-xpu-timing\]\s+rank=(?P<rank>\d+)\s+"
    r"label=(?P<label>.+?)\s+count=(?P<count>\d+)\s+last_ms=(?P<last_ms>[0-9.]+)"
)
SUMMARY_RE = re.compile(
    r"\[vllm-xpu-timing-summary\]\s+rank=(?P<rank>\d+)\s+"
    r"label=(?P<label>.+?)\s+count=(?P<count>\d+)\s+"
    r"total_ms=(?P<total_ms>[0-9.]+)\s+avg_ms=(?P<avg_ms>[0-9.]+)\s+"
    r"max_ms=(?P<max_ms>[0-9.]+)"
)
STEP_RE = re.compile(r"\[vllm-xpu-timing-step\]\s+(?P<payload>\{.*\})")
POST_RE = re.compile(r'POST\s+/v1/(?:completions|chat/completions)\s+HTTP/\d(?:\.\d)?"\s+200')


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * pct
    lower = int(pos)
    upper = min(lower + 1, len(ordered) - 1)
    frac = pos - lower
    return ordered[lower] * (1.0 - frac) + ordered[upper] * frac


def summarize_samples(samples: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for sample in samples:
        grouped.setdefault(sample["label"], []).append(sample)

    rows = []
    for label, items in grouped.items():
        values = [float(item["last_ms"]) for item in items]
        counts = [int(item["count"]) for item in items]
        rows.append(
            {
                "label": label,
                "sample_count": len(items),
                "first_count": min(counts),
                "last_count": max(counts),
                "mean_last_ms": statistics.fmean(values),
                "median_last_ms": statistics.median(values),
                "p90_last_ms": percentile(values, 0.90),
                "p99_last_ms": percentile(values, 0.99),
                "min_last_ms": min(values),
                "max_last_ms": max(values),
            }
        )
    rows.sort(key=lambda row: row["mean_last_ms"], reverse=True)
    return rows


def summarize_steps(steps: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for step in steps:
        for row in step.get("summary_by_total_ms", []):
            grouped.setdefault(row["label"], []).append(row)

    rows = []
    for label, items in grouped.items():
        totals = [float(item["total_ms"]) for item in items]
        counts = [int(item["count"]) for item in items]
        avg_per_call = [float(item["avg_ms"]) for item in items]
        maxes = [float(item["max_ms"]) for item in items]
        rows.append(
            {
                "label": label,
                "step_count": len(items),
                "call_count": sum(counts),
                "mean_total_ms_per_step": statistics.fmean(totals),
                "median_total_ms_per_step": statistics.median(totals),
                "p90_total_ms_per_step": percentile(totals, 0.90),
                "max_total_ms_per_step": max(totals),
                "mean_avg_ms_per_call": statistics.fmean(avg_per_call),
                "max_ms": max(maxes),
            }
        )
    rows.sort(key=lambda row: row["mean_total_ms_per_step"], reverse=True)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", required=True, help="vLLM worker log file")
    parser.add_argument("--out", required=True, help="JSON summary output path")
    parser.add_argument(
        "--all-lines",
        action="store_true",
        help="include every timing sample and aggregate summary in the log",
    )
    parser.add_argument(
        "--include-raw",
        action="store_true",
        help="include raw matched sample and summary rows",
    )
    args = parser.parse_args()

    log_path = Path(args.log)
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()

    post_lines = [idx + 1 for idx, line in enumerate(lines) if POST_RE.search(line)]
    sample_start_line = 1
    sample_end_line = len(lines)
    summary_start_line = 1
    if post_lines and not args.all_lines:
        sample_start_line = post_lines[-2] + 1 if len(post_lines) >= 2 else 1
        sample_end_line = post_lines[-1]
        summary_start_line = post_lines[-1] + 1

    samples = []
    summaries = []
    steps = []
    for idx, line in enumerate(lines, start=1):
        if sample_start_line <= idx <= sample_end_line:
            match = SAMPLE_RE.search(line)
            if match:
                samples.append(
                    {
                        "line": idx,
                        "rank": int(match.group("rank")),
                        "label": match.group("label"),
                        "count": int(match.group("count")),
                        "last_ms": float(match.group("last_ms")),
                    }
                )
                continue
        if idx >= summary_start_line:
            match = SUMMARY_RE.search(line)
        else:
            match = None
        if match:
            summaries.append(
                {
                    "line": idx,
                    "rank": int(match.group("rank")),
                    "label": match.group("label"),
                    "count": int(match.group("count")),
                    "total_ms": float(match.group("total_ms")),
                    "avg_ms": float(match.group("avg_ms")),
                    "max_ms": float(match.group("max_ms")),
                }
            )
        match = STEP_RE.search(line)
        if match and (args.all_lines or idx >= sample_start_line):
            try:
                payload = json.loads(match.group("payload"))
            except json.JSONDecodeError:
                continue
            payload["line"] = idx
            steps.append(payload)

    summary_rows = summarize_samples(samples)
    timing_summary = sorted(summaries, key=lambda row: row["total_ms"], reverse=True)
    step_summary = summarize_steps(steps)
    payload = {
        "source_log": str(log_path),
        "line_count": len(lines),
        "post_lines": post_lines,
        "sample_start_line": sample_start_line,
        "sample_end_line": sample_end_line,
        "summary_start_line": summary_start_line,
        "sample_line_count": len(samples),
        "summary_line_count": len(timing_summary),
        "step_line_count": len(steps),
        "samples_by_last_ms": summary_rows,
        "summary_by_total_ms": timing_summary,
        "step_summary_by_mean_total_ms": step_summary,
    }
    if args.include_raw:
        payload["raw_samples"] = samples
        payload["raw_summaries"] = summaries
        payload["raw_steps"] = steps

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
