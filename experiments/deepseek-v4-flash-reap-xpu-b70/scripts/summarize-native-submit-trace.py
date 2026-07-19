#!/usr/bin/env python3
"""Count per-decode Level Zero boundaries in paired XPU profiler traces."""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path
from typing import Any


SUBMIT_APIS = (
    "zeCommandListImmediateAppendCommandListsExp",
    "zeCommandQueueExecuteCommandLists",
)
IMMEDIATE_APIS = (
    "zeCommandListAppendLaunchKernel",
    "zeCommandListAppendMemoryCopy",
    "zeCommandListAppendSignalEvent",
    "zeCommandListAppendWaitOnEvents",
)
SYNC_APIS = (
    "zeCommandListHostSynchronize",
    "zeEventHostSynchronize",
    "zeFenceHostSynchronize",
)
POLL_APIS = ("zeEventQueryStatus",)
ACTIVE_LZ_APIS = SUBMIT_APIS + IMMEDIATE_APIS + (
    "zeCommandListHostSynchronize",
    "zeFenceHostSynchronize",
) + POLL_APIS


def median(values: list[float]) -> float:
    return float(statistics.median(values))


def summarize_trace(path: Path, tokens_per_turn: int) -> dict[str, Any]:
    events = json.loads(path.read_text())["traceEvents"]
    scopes = [
        event
        for event in events
        if event.get("name", "").startswith("execute_context")
    ]
    if len(scopes) < 5:
        raise ValueError(f"{path}: expected at least five execute_context scopes")
    scopes = scopes[-5:]
    rows: list[dict[str, Any]] = []
    for scope in scopes:
        start = scope["ts"]
        end = start + scope["dur"]
        inside = [
            event
            for event in events
            if event.get("pid") == scope.get("pid")
            and event.get("tid") == scope.get("tid")
            and start <= event.get("ts", -1) <= end
        ]
        counts = Counter(event.get("name") for event in inside)
        durations = {
            name: sum(
                event.get("dur", 0.0)
                for event in inside
                if event.get("name") == name
            )
            / 1000.0
            for name in set(ACTIVE_LZ_APIS) | {"vllm::all_gather"}
        }
        argmax = next(
            (event for event in inside if event.get("name") == "vllm::all_gather"),
            None,
        )
        lz_in_argmax_ms = 0.0
        if argmax is not None:
            argmax_end = argmax["ts"] + argmax["dur"]
            lz_in_argmax_ms = sum(
                event.get("dur", 0.0)
                for event in inside
                if event.get("name") in ACTIVE_LZ_APIS
                and argmax["ts"] <= event.get("ts", -1) <= argmax_end
            ) / 1000.0

        device_bookkeeping_ms = sum(
            event.get("dur", 0.0)
            for event in events
            if event.get("cat") in ("kernel", "gpu_memcpy")
            and start <= event.get("ts", -1) <= end
            and "gemm_kernel" not in event.get("name", "")
            and "ArgMaxOps" not in event.get("name", "")
            and "oneccl_allgatherv" not in event.get("name", "")
        ) / 1000.0
        rows.append(
            {
                "scope_ms": scope["dur"] / 1000.0,
                "counts": dict(counts),
                "durations_ms": durations,
                "lz_in_argmax_ms": lz_in_argmax_ms,
                "device_bookkeeping_ms": device_bookkeeping_ms,
            }
        )

    def med_count(name: str) -> float:
        return median([float(row["counts"].get(name, 0)) for row in rows])

    def med_duration(name: str) -> float:
        return median([row["durations_ms"].get(name, 0.0) for row in rows])

    literal = sum(med_count(name) for name in SUBMIT_APIS)
    immediate = sum(med_count(name) for name in IMMEDIATE_APIS)
    syncs = sum(med_count(name) for name in SYNC_APIS)
    polls = sum(med_count(name) for name in POLL_APIS)
    active_lz = sum(med_duration(name) for name in ACTIVE_LZ_APIS)
    lz_in_argmax = median([row["lz_in_argmax_ms"] for row in rows])
    return {
        "trace": str(path),
        "tokens_per_worker_turn": tokens_per_turn,
        "stable_scope_count": len(rows),
        "execute_context_ms_per_turn_profile_distorted": median(
            [row["scope_ms"] for row in rows]
        ),
        "per_turn": {
            "literal_command_list_submit_calls": literal,
            "direct_immediate_append_calls": immediate,
            "effective_submission_boundaries": literal + immediate,
            "host_sync_calls": syncs,
            "event_query_polls": polls,
        },
        "per_token": {
            "literal_command_list_submit_calls": literal / tokens_per_turn,
            "direct_immediate_append_calls": immediate / tokens_per_turn,
            "effective_submission_boundaries": (literal + immediate)
            / tokens_per_turn,
            "host_sync_calls": syncs / tokens_per_turn,
            "event_query_polls": polls / tokens_per_turn,
        },
        "host_api_active_ms_per_turn": {
            "lz_excluding_long_event_wait": active_lz,
            "lz_inside_argmax_scope": lz_in_argmax,
            "lz_excluding_argmax_scope": active_lz - lz_in_argmax,
            "argmax_gather_inclusive": med_duration("vllm::all_gather"),
        },
        "device_event_bookkeeping_ms_per_turn_lower_bound": median(
            [row["device_bookkeeping_ms"] for row in rows]
        ),
    }


def summarize_dir(path: Path, tokens_per_turn: int) -> list[dict[str, Any]]:
    traces = sorted(path.glob("*rank*.pt.trace.json"))
    if not traces:
        raise ValueError(f"no rank traces in {path}")
    return [summarize_trace(trace, tokens_per_turn) for trace in traces]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-trace-dir", type=Path, required=True)
    parser.add_argument("--candidate-trace-dir", type=Path, required=True)
    parser.add_argument("--candidate-k", type=int, default=2)
    parser.add_argument("--residual-ms", type=float, default=3.435)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    baseline = summarize_dir(args.baseline_trace_dir, 1)
    candidate = summarize_dir(args.candidate_trace_dir, args.candidate_k)
    # The slowest baseline rank is the cycle authority. The four-way split is
    # intentionally bounded: device events give a metadata/bookkeeping lower
    # bound, while the residual bucket is an upper bound that also absorbs
    # profiler-invisible host metadata and scheduler work.
    authority = max(
        baseline, key=lambda row: row["execute_context_ms_per_turn_profile_distorted"]
    )
    lz_ms = authority["host_api_active_ms_per_turn"]["lz_excluding_argmax_scope"]
    argmax_ms = authority["host_api_active_ms_per_turn"]["argmax_gather_inclusive"]
    metadata_ms = authority["device_event_bookkeeping_ms_per_turn_lower_bound"]
    iteration_ms = args.residual_ms - lz_ms - argmax_ms - metadata_ms
    output = {
        "method": {
            "stable_scopes": "last five execute_context scopes per rank",
            "throughput_warning": "Profiler-distorted scope time is diagnostic only.",
            "literal_submit_definition": "zeCommandListImmediateAppendCommandListsExp + zeCommandQueueExecuteCommandLists",
            "effective_boundary_definition": "literal submits plus direct immediate launch/copy/signal/wait appends",
            "sync_definition": "command-list + event + fence host synchronizations",
        },
        "baseline": baseline,
        "candidate": candidate,
        "residual_split_ms_per_token": {
            "worker_segment_iteration_and_unresolved_host_metadata_upper_bound": iteration_ms,
            "level_zero_submit_and_sync_active_time_excluding_argmax": lz_ms,
            "attention_kv_metadata_and_device_bookkeeping_event_lower_bound": metadata_ms,
            "host_scheduled_argmax_gather_inclusive": argmax_ms,
            "total": args.residual_ms,
        },
    }
    rendered = json.dumps(output, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.write_text(rendered)
    print(rendered, end="")


if __name__ == "__main__":
    main()
