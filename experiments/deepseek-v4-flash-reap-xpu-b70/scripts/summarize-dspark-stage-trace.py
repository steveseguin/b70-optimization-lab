#!/usr/bin/env python3
"""Summarize DSpark profiler scopes and their submitted XPU kernels."""

from __future__ import annotations

import argparse
from bisect import bisect_right
from collections import Counter
import json
from pathlib import Path
import statistics

import ijson


SCOPES = (
    "gpu_model_runner: forward",
    "gpu_model_runner: sample",
    "gpu_model_runner: draft",
    "dspark: combine_and_copy_hidden",
    "dspark: prepare_inputs",
    "dspark: context_kv",
    "dspark: dispatch_and_metadata",
    "dspark: generate_draft",
    "dspark: backbone",
    "dspark: markov_sample",
    "dspark: markov_sample_graph",
    "xpu_v2: target_forward",
    "xpu_v2: target_sample",
    "xpu_v2: dspark_propose",
)


def iter_events(path: Path):
    with path.open("rb") as handle:
        yield from ijson.items(handle, "traceEvents.item")


def scope_intervals(path: Path) -> dict[str, list[tuple[float, float]]]:
    result = {name: [] for name in SCOPES}
    for event in iter_events(path):
        name = event.get("name")
        if event.get("ph") != "X" or name not in result:
            continue
        start = float(event["ts"])
        result[name].append((start, start + float(event["dur"])))
    for intervals in result.values():
        intervals.sort()
    return result


def containing_index(
    starts: list[float], intervals: list[tuple[float, float]], timestamp: float
) -> int | None:
    index = bisect_right(starts, timestamp) - 1
    if index >= 0 and timestamp <= intervals[index][1]:
        return index
    return None


def summarize_rank(path: Path, drop_first: int) -> dict:
    all_intervals = scope_intervals(path)
    retained = {
        name: intervals[drop_first:] for name, intervals in all_intervals.items()
    }
    starts = {name: [start for start, _ in intervals] for name, intervals in retained.items()}
    kernel_us = {name: [0.0] * len(intervals) for name, intervals in retained.items()}
    kernel_counts = {name: [0] * len(intervals) for name, intervals in retained.items()}
    oneccl_us = {name: [0.0] * len(intervals) for name, intervals in retained.items()}
    kernel_names = {name: Counter() for name in SCOPES}

    for event in iter_events(path):
        if event.get("ph") != "X" or event.get("cat") != "kernel":
            continue
        args = event.get("args") or {}
        anchor = args.get("submitted") or args.get("appended") or args.get(
            "sycl_enqk_begin"
        )
        try:
            timestamp = float(anchor)
        except (TypeError, ValueError):
            continue
        event_name = str(event.get("name", "<unnamed>"))
        duration = float(event.get("dur", 0.0))
        for scope_name, intervals in retained.items():
            index = containing_index(starts[scope_name], intervals, timestamp)
            if index is None:
                continue
            kernel_counts[scope_name][index] += 1
            kernel_names[scope_name][event_name] += duration
            if event_name.startswith("oneccl_"):
                oneccl_us[scope_name][index] += duration
            else:
                kernel_us[scope_name][index] += duration

    scopes = {}
    for name, intervals in retained.items():
        if not intervals:
            continue
        host_ms = [(end - start) / 1000.0 for start, end in intervals]
        noncollective_ms = [value / 1000.0 for value in kernel_us[name]]
        scopes[name] = {
            "calls": len(intervals),
            "host_ms": {
                "mean": statistics.fmean(host_ms),
                "median": statistics.median(host_ms),
                "samples": host_ms,
            },
            "noncollective_kernel_ms": {
                "mean": statistics.fmean(noncollective_ms),
                "median": statistics.median(noncollective_ms),
                "samples": noncollective_ms,
            },
            "kernel_count_mean": statistics.fmean(kernel_counts[name]),
            "oneccl_trace_duration_ms_mean_excluded": statistics.fmean(
                oneccl_us[name]
            )
            / 1000.0,
            "top_kernels": [
                {
                    "name": kernel_name,
                    "mean_ms_per_call": duration / len(intervals) / 1000.0,
                }
                for kernel_name, duration in kernel_names[name].most_common(15)
            ],
        }

    draft = retained["xpu_v2: dspark_propose"] or retained[
        "gpu_model_runner: draft"
    ]
    child_names = (
        "dspark: combine_and_copy_hidden",
        "dspark: prepare_inputs",
        "dspark: context_kv",
        "dspark: dispatch_and_metadata",
        "dspark: generate_draft",
    )
    unannotated_ms = []
    for draft_start, draft_end in draft:
        child_us = 0.0
        for child_name in child_names:
            child_us += sum(
                end - start
                for start, end in retained[child_name]
                if draft_start <= start and end <= draft_end
            )
        unannotated_ms.append(((draft_end - draft_start) - child_us) / 1000.0)
    return {
        "trace": str(path),
        "dropped_initial_calls_per_scope": drop_first,
        "scopes": scopes,
        "draft_unannotated_host_ms": {
            "mean": statistics.fmean(unannotated_ms) if unannotated_ms else None,
            "median": statistics.median(unannotated_ms) if unannotated_ms else None,
            "samples": unannotated_ms,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace_dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--drop-first", type=int, default=1)
    args = parser.parse_args()

    traces = sorted(args.trace_dir.glob("*rank*.pt.trace.json"))
    if not traces:
        raise SystemExit(f"no rank traces found under {args.trace_dir}")
    ranks = [summarize_rank(path, args.drop_first) for path in traces]
    result = {
        "schema_version": 1,
        "classification": "deepseek_v4_dspark_exact_m7_stage_trace",
        "trace_count": len(ranks),
        "timestamp_method": (
            "associate kernels with host profiler scopes using submitted/appended/"
            "sycl_enqk_begin; retain device duration"
        ),
        "oneccl_warning": (
            "oneCCL device durations are timeline-distorted and excluded from "
            "noncollective totals"
        ),
        "ranks": ranks,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
