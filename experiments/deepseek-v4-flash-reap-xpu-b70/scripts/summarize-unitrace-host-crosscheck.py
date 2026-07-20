#!/usr/bin/env python3
"""Summarize a bounded host-only PTI unitrace DeepSeek decode capture."""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path


def interval_union_us(events: list[dict[str, object]]) -> float:
    intervals = sorted(
        (float(event["ts"]), float(event["ts"]) + float(event["dur"]))
        for event in events
    )
    if not intervals:
        return 0.0
    total = 0.0
    left, right = intervals[0]
    for next_left, next_right in intervals[1:]:
        if next_left <= right:
            right = max(right, next_right)
        else:
            total += right - left
            left, right = next_left, next_right
    return total + right - left


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--unitrace-dir", type=Path, required=True)
    parser.add_argument("--profile-request", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    request = json.loads(args.profile_request.read_text())
    token_intervals = int(request["trace_window"]["captured_intervals"])
    rows: list[dict[str, object]] = []
    for path in sorted(args.unitrace_dir.glob("python.*/chrome_trace.json")):
        if path.stat().st_size == 0:
            continue
        process_id = int(path.parent.name.rsplit(".", 1)[1])
        events = [
            event
            for event in json.loads(path.read_text()).get("traceEvents", [])
            if event.get("ph") == "X"
        ]
        main_events = [event for event in events if event.get("tid") == process_id]
        counts = Counter(str(event["name"]) for event in main_events)
        if counts["zeCommandListImmediateAppendCommandListsExp"] == 0:
            continue
        start_us = min(float(event["ts"]) for event in main_events)
        end_us = max(
            float(event["ts"]) + float(event["dur"]) for event in main_events
        )
        active_union_us = interval_union_us(main_events)
        long_memory_copy = [
            event
            for event in main_events
            if event["name"] == "zeCommandListAppendMemoryCopy"
            and float(event["dur"]) > 1000.0
        ]
        nonblocking_api_sum_us = sum(
            float(event["dur"])
            for event in main_events
            if event not in long_memory_copy
        )
        effective_boundaries = sum(
            counts[name]
            for name in (
                "zeCommandListImmediateAppendCommandListsExp",
                "zeCommandListAppendLaunchKernel",
                "zeCommandListAppendMemoryCopy",
                "zeCommandListAppendSignalEvent",
            )
        )
        all_counts = Counter(str(event["name"]) for event in events)
        rows.append(
            {
                "process_id": process_id,
                "trace": str(path),
                "span_ms": (end_us - start_us) / 1000.0,
                "api_union_ms": active_union_us / 1000.0,
                "cpu_no_level_zero_gap_ms_per_token": (
                    (end_us - start_us - active_union_us) / 1000.0 / token_intervals
                ),
                "nonblocking_level_zero_api_sum_ms_per_token": (
                    nonblocking_api_sum_us / 1000.0 / token_intervals
                ),
                "collective_wait_inclusive_upper_ms_per_observed_wait": (
                    sum(float(event["dur"]) for event in long_memory_copy)
                    / 1000.0
                    / len(long_memory_copy)
                ),
                "long_blocking_memory_copy_calls": len(long_memory_copy),
                "effective_submission_boundaries": effective_boundaries,
                "effective_submission_boundaries_per_token": (
                    effective_boundaries / token_intervals
                ),
                "literal_immediate_graph_submits": counts[
                    "zeCommandListImmediateAppendCommandListsExp"
                ],
                "literal_immediate_graph_submits_per_token": (
                    counts["zeCommandListImmediateAppendCommandListsExp"]
                    / token_intervals
                ),
                "kernel_appends": counts["zeCommandListAppendLaunchKernel"],
                "memory_copy_appends": counts["zeCommandListAppendMemoryCopy"],
                "signal_appends": counts["zeCommandListAppendSignalEvent"],
                "command_list_host_syncs": counts["zeCommandListHostSynchronize"],
                "command_list_host_syncs_per_token": (
                    counts["zeCommandListHostSynchronize"] / token_intervals
                ),
                "event_host_syncs_all_threads": all_counts["zeEventHostSynchronize"],
                "event_host_syncs_all_threads_per_token": (
                    all_counts["zeEventHostSynchronize"] / token_intervals
                ),
            }
        )

    if len(rows) != 4:
        raise RuntimeError(f"expected four worker traces, found {len(rows)}")

    median_keys = (
        "cpu_no_level_zero_gap_ms_per_token",
        "nonblocking_level_zero_api_sum_ms_per_token",
        "collective_wait_inclusive_upper_ms_per_observed_wait",
        "effective_submission_boundaries_per_token",
        "literal_immediate_graph_submits_per_token",
        "command_list_host_syncs_per_token",
        "event_host_syncs_all_threads_per_token",
    )
    medians = {
        key: statistics.median(float(row[key]) for row in rows)
        for key in median_keys
    }
    host_outer_gap_authority_ms = 3.435
    medians["reconciled_cpu_scheduler_gap_ms_per_token"] = (
        host_outer_gap_authority_ms
        - medians["nonblocking_level_zero_api_sum_ms_per_token"]
    )
    medians["profiler_invisible_scheduler_edge_ms_per_token"] = (
        medians["reconciled_cpu_scheduler_gap_ms_per_token"]
        - medians["cpu_no_level_zero_gap_ms_per_token"]
    )

    output = {
        "classification": "diagnostic_profiler_crosscheck",
        "tracer": {
            "name": "Intel PTI GPU unitrace",
            "version": "2.4.0",
            "commit": "a5bab309f4ffdd78bd127035c46f5f75371160f8",
            "mode": "host-only temporal Level Zero capture",
        },
        "one_active_generation": request["one_active_generation"],
        "token_intervals": token_intervals,
        "profile_request": str(args.profile_request),
        "per_rank": rows,
        "medians": medians,
        "bounds": {
            "collective_wait_note": (
                "Inclusive long zeCommandListAppendMemoryCopy / paired "
                "zeEventHostSynchronize duration. It encloses downstream device "
                "progress and is a non-additive upper bound."
            ),
            "kernel_timing_note": (
                "Full PTI device timestamp mode destabilized oneCCL and produced "
                "no valid kernel trace; use the same-identity device-event "
                "kernel buckets from the 2026-07-19 roofline profile."
            ),
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
