#!/usr/bin/env python3
"""Stream large Kineto traces into per-cycle XPU kernel summaries.

GPU event timestamps can be offset from the host timeline on this stack. Use
the event's host-side submission timestamp to associate it with an
execute_context annotation, while retaining the GPU event duration for timing.
"""

from __future__ import annotations

import argparse
from bisect import bisect_right
from collections import Counter
import json
from pathlib import Path
import statistics

import ijson


DEFAULT_CONTEXT = "execute_context_0(0)_generation_1(2)"


def classify(name: str) -> str:
    if name.startswith("oneccl_"):
        return "oneccl_distorted_timeline"
    if name == "gemm_kernel":
        return "dense_gemm"
    if "MoE::GemmCuteName" in name:
        return "mxfp4_routed_moe"
    if "MhcPreM1Fused" in name:
        return "mhc_post_pre"
    if name == "_fp8_sparse_qk_lse_kernel":
        return "attention_qk_lse"
    if name == "_fp8_sparse_pv_kernel":
        return "attention_pv"
    if "SegmentedGroupRadixSelectPairsFunctor" in name:
        return "router_radix_select"
    if "SegmentedGroupRadixSortPairsFunctor" in name:
        return "router_radix_sort"
    return "other_noncollective"


def iter_events(path: Path):
    with path.open("rb") as handle:
        yield from ijson.items(handle, "traceEvents.item")


def context_intervals(path: Path, name: str, drop_first: int):
    intervals = []
    for event in iter_events(path):
        if event.get("ph") == "X" and event.get("name") == name:
            start = float(event["ts"])
            intervals.append((start, start + float(event["dur"])))
    intervals.sort()
    return intervals[drop_first:]


def interval_index(starts: list[float], intervals, timestamp: float):
    index = bisect_right(starts, timestamp) - 1
    if index >= 0 and timestamp <= intervals[index][1]:
        return index
    return None


def summarize_trace(path: Path, context_name: str, drop_first: int):
    intervals = context_intervals(path, context_name, drop_first)
    if not intervals:
        raise RuntimeError(f"no retained {context_name!r} intervals in {path}")
    starts = [item[0] for item in intervals]
    per_cycle_buckets = [Counter() for _ in intervals]
    per_cycle_names = [Counter() for _ in intervals]
    topk_shapes = Counter()
    topk_contracts = Counter()

    for event in iter_events(path):
        category = event.get("cat")
        if event.get("ph") != "X":
            continue
        if category == "kernel":
            args = event.get("args") or {}
            anchor = (
                args.get("submitted")
                or args.get("appended")
                or args.get("sycl_enqk_begin")
            )
            try:
                timestamp = float(anchor)
            except (TypeError, ValueError):
                continue
            index = interval_index(starts, intervals, timestamp)
            if index is None:
                continue
            name = str(event.get("name", "<unnamed>"))
            duration_us = float(event.get("dur", 0.0))
            per_cycle_buckets[index][classify(name)] += duration_us
            per_cycle_names[index][name] += duration_us
        elif category == "cpu_op" and event.get("name") == "aten::topk":
            timestamp = float(event.get("ts", -1))
            if interval_index(starts, intervals, timestamp) is None:
                continue
            args = event.get("args") or {}
            dims = args.get("Input Dims") or []
            concrete = args.get("Concrete Inputs") or []
            shape = dims[0] if dims else []
            topk_shapes[str(shape)] += 1
            topk_contracts[
                json.dumps(
                    {
                        "shape": shape,
                        "k": concrete[1] if len(concrete) > 1 else None,
                        "dim": concrete[2] if len(concrete) > 2 else None,
                        "largest": concrete[3] if len(concrete) > 3 else None,
                        "sorted": concrete[4] if len(concrete) > 4 else None,
                    },
                    sort_keys=True,
                )
            ] += 1

    bucket_names = sorted(set().union(*(row.keys() for row in per_cycle_buckets)))
    bucket_ms = {
        bucket: [row[bucket] / 1000.0 for row in per_cycle_buckets]
        for bucket in bucket_names
    }
    noncollective_ms = [
        sum(value for key, value in row.items() if not key.startswith("oneccl_"))
        / 1000.0
        for row in per_cycle_buckets
    ]
    aggregate_names = sum(per_cycle_names, Counter())
    return {
        "trace": str(path),
        "retained_contexts": len(intervals),
        "context_host_duration_ms": [
            (end - start) / 1000.0 for start, end in intervals
        ],
        "bucket_ms_per_cycle": {
            key: {
                "mean": statistics.fmean(values),
                "median": statistics.median(values),
                "samples": values,
            }
            for key, values in bucket_ms.items()
        },
        "noncollective_kernel_ms_per_cycle": {
            "mean": statistics.fmean(noncollective_ms),
            "median": statistics.median(noncollective_ms),
            "samples": noncollective_ms,
        },
        "top_kernel_names_by_duration": [
            {
                "name": name,
                "mean_ms_per_cycle": duration / len(intervals) / 1000.0,
            }
            for name, duration in aggregate_names.most_common(30)
        ],
        "cpu_topk_shapes": dict(topk_shapes),
        "cpu_topk_contracts": {
            key: count for key, count in topk_contracts.items()
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace_dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--context-name", default=DEFAULT_CONTEXT)
    parser.add_argument("--drop-first", type=int, default=1)
    args = parser.parse_args()

    traces = sorted(args.trace_dir.glob("*rank*.pt.trace.json"))
    if not traces:
        raise SystemExit(f"no rank traces found under {args.trace_dir}")
    ranks = [
        summarize_trace(path, args.context_name, args.drop_first)
        for path in traces
    ]
    bucket_names = sorted(
        set().union(*(rank["bucket_ms_per_cycle"].keys() for rank in ranks))
    )
    cross_rank = {}
    for bucket in bucket_names:
        values = [
            rank["bucket_ms_per_cycle"].get(bucket, {}).get("mean", 0.0)
            for rank in ranks
        ]
        cross_rank[bucket] = {
            "mean_ms_per_cycle": statistics.fmean(values),
            "min_rank_mean_ms": min(values),
            "max_rank_mean_ms": max(values),
        }
    result = {
        "schema_version": 1,
        "classification": "deepseek_v4_eager_mtp1_cycle_trace_summary",
        "context_name": args.context_name,
        "dropped_initial_contexts_per_rank": args.drop_first,
        "trace_count": len(traces),
        "timestamp_method": (
            "associate GPU kernels with host execute_context by args.submitted "
            "(falling back to appended/sycl_enqk_begin); use GPU event dur"
        ),
        "oneccl_warning": (
            "oneCCL GPU event durations are timeline-distorted in this trace; "
            "exclude them from noncollective totals and use normal-run evidence"
        ),
        "cross_rank_bucket_means": cross_rank,
        "ranks": ranks,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
