#!/usr/bin/env python3
"""Count fail-closed Level Zero submission boundaries in Phase 0 traces."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any


def load_trace(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text())
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("traceEvents"), list):
        return payload["traceEvents"]
    raise ValueError(f"{path} is not a Chrome trace JSON")


def find_trace(root: Path) -> Path:
    candidates = []
    for path in root.rglob("*.json"):
        try:
            events = load_trace(path)
        except (ValueError, json.JSONDecodeError):
            continue
        if any("zeCommand" in str(event.get("name", "")) for event in events):
            candidates.append(path)
    if len(candidates) != 1:
        raise RuntimeError(
            f"expected exactly one Level Zero Chrome trace under {root}, "
            f"found {len(candidates)}: {candidates}"
        )
    return candidates[0]


def api_name(raw: str) -> str:
    for token in raw.replace("(", " ").split():
        if token.startswith("ze"):
            return token
    return raw


def summarize(root: Path) -> dict[str, Any]:
    trace = find_trace(root)
    events = load_trace(trace)
    names = Counter(
        api_name(str(event.get("name", "")))
        for event in events
        if event.get("ph") == "X" and "ze" in str(event.get("name", ""))
    )
    immediate_exec = sum(
        count
        for name, count in names.items()
        if "zeCommandListImmediateAppendCommandListsExp" in name
    )
    queue_exec = sum(
        count
        for name, count in names.items()
        if "zeCommandQueueExecuteCommandLists" in name
    )
    direct_appends = {
        name: count
        for name, count in names.items()
        if "zeCommandListAppend" in name
        and "zeCommandListImmediateAppendCommandListsExp" not in name
    }
    direct_total = sum(direct_appends.values())
    host_syncs = {
        name: count
        for name, count in names.items()
        if any(
            marker in name
            for marker in (
                "HostSynchronize",
                "zeCommandQueueSynchronize",
                "zeEventQueryStatus",
            )
        )
    }
    return {
        "trace": str(trace),
        "level_zero_api_events": sum(names.values()),
        "immediate_executable_appends": immediate_exec,
        "queue_execute_command_lists": queue_exec,
        "direct_append_total": direct_total,
        "direct_appends": dict(sorted(direct_appends.items())),
        "host_sync_total": sum(host_syncs.values()),
        "host_syncs": dict(sorted(host_syncs.items())),
        "effective_submission_boundaries": immediate_exec
        + queue_exec
        + direct_total,
        "all_level_zero_calls": dict(sorted(names.items())),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--eager-trace-dir", type=Path, required=True)
    parser.add_argument("--graph-trace-dir", type=Path, required=True)
    parser.add_argument("--eager-probe", type=Path, required=True)
    parser.add_argument("--graph-probe", type=Path, required=True)
    parser.add_argument("--nested-trace-dir", type=Path)
    parser.add_argument("--nested-probe", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if (args.nested_trace_dir is None) != (args.nested_probe is None):
        parser.error("--nested-trace-dir and --nested-probe must be paired")

    eager = summarize(args.eager_trace_dir)
    graph = summarize(args.graph_trace_dir)
    eager_probe = json.loads(args.eager_probe.read_text())
    graph_probe = json.loads(args.graph_probe.read_text())
    eager_exact = bool(eager_probe["verdict_inputs"]["bitwise_exact"])
    graph_exact = bool(graph_probe["verdict_inputs"]["bitwise_exact"])
    protected_untouched = bool(
        eager_probe["protected_process"]["untouched"]
        and graph_probe["protected_process"]["untouched"]
    )
    fewer = (
        graph["effective_submission_boundaries"]
        < eager["effective_submission_boundaries"]
    )
    one_boundary = (
        graph["immediate_executable_appends"] == 1
        and graph["queue_execute_command_lists"] == 0
        and graph["direct_append_total"] == 0
    )
    mixed_capture_feasible = (
        eager_exact and graph_exact and protected_untouched and fewer and one_boundary
    )
    graph_no_host_sync = graph["host_sync_total"] == 0
    nested = None
    nested_exact = False
    nested_one_boundary = False
    nested_no_host_sync = False
    nested_protected = False
    if args.nested_trace_dir is not None and args.nested_probe is not None:
        nested = summarize(args.nested_trace_dir)
        nested_probe = json.loads(args.nested_probe.read_text())
        nested_exact = bool(nested_probe["verdict_inputs"]["bitwise_exact"])
        nested_one_boundary = (
            nested["immediate_executable_appends"] == 1
            and nested["queue_execute_command_lists"] == 0
            and nested["direct_append_total"] == 0
        )
        nested_no_host_sync = nested["host_sync_total"] == 0
        nested_protected = bool(nested_probe["protected_process"]["untouched"])
    phase0_passed = (
        mixed_capture_feasible
        and graph_no_host_sync
        and nested_exact
        and nested_one_boundary
        and nested_no_host_sync
        and nested_protected
    )
    reduction = eager["effective_submission_boundaries"] - graph[
        "effective_submission_boundaries"
    ]
    reduction_pct = (
        100.0 * reduction / eager["effective_submission_boundaries"]
        if eager["effective_submission_boundaries"]
        else 0.0
    )
    result = {
        "schema_version": 1,
        "classification": "option4_phase0_level_zero_submission_gate",
        "eager": eager,
        "graph": graph,
        "nested": nested,
        "parity": {
            "eager_trace_case_exact": eager_exact,
            "graph_changed_input_exact": graph_exact,
            "graph_changed_input_cases": graph_probe["parity"][
                "changed_input_cases"
            ],
            "graph_exact_cases": graph_probe["parity"]["exact_cases"],
        },
        "protected_eagle_untouched": protected_untouched,
        "submission_reduction": reduction,
        "submission_reduction_percent": reduction_pct,
        "gate": {
            "one_graph_executable_boundary": one_boundary,
            "materially_fewer_boundaries": fewer,
            "bitwise_exact": eager_exact and graph_exact,
            "mixed_kernel_capture_passed": mixed_capture_feasible,
            "graph_replay_has_no_host_sync": graph_no_host_sync,
            "nested_capture_exact": nested_exact,
            "nested_one_graph_executable_boundary": nested_one_boundary,
            "nested_replay_has_no_host_sync": nested_no_host_sync,
            "phase0_passed": phase0_passed,
            "verdict": "FEASIBLE" if phase0_passed else "PARTIAL",
            "phase1_go": phase0_passed,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if phase0_passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
