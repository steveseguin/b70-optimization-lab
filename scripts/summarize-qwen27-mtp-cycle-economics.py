#!/usr/bin/env python3
"""Summarize opt-in llama-server MTP cycle diagnostic rows."""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path


TASK_RE = re.compile(r"task (\d+) \| processing task")
TS_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)\.(\d+)")
KV_RE = re.compile(r"([a-z_]+)=([0-9]+)")


def stats(values: list[float]) -> dict:
    if not values:
        return {"n": 0, "min": None, "median": None, "mean": None, "p90": None, "max": None}
    ordered = sorted(values)
    return {
        "n": len(values),
        "min": ordered[0],
        "median": statistics.median(ordered),
        "mean": statistics.fmean(ordered),
        "p90": ordered[min(len(ordered) - 1, math.ceil(0.9 * len(ordered)) - 1)],
        "max": ordered[-1],
    }


def timestamp_us(line: str) -> int | None:
    match = TS_RE.match(line)
    if not match:
        return None
    hour, minute, ms, us = map(int, match.groups())
    return ((hour * 60 + minute) * 1_000_000) + ms * 1000 + us


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-log", type=Path, required=True)
    parser.add_argument("--result", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    prompt_ids: list[str] = []
    if args.result:
        result = json.loads(args.result.read_text())
        prompt_ids = [str(row.get("prompt_id", row.get("prompt_index"))) for row in result.get("rows", [])]

    current_task: int | None = None
    current_request_index = -1
    pending_draft: dict | None = None
    pending_target: dict | None = None
    cycles: list[dict] = []
    previous_accept_ts: dict[int, int] = {}

    for line in args.server_log.read_text(errors="replace").splitlines():
        task_match = TASK_RE.search(line)
        if task_match:
            current_task = int(task_match.group(1))
            current_request_index += 1
            pending_draft = None
            pending_target = None
            continue
        if "[MTP-CYCLE]" not in line:
            continue
        fields = {key: int(value) for key, value in KV_RE.findall(line)}
        ts_us = timestamp_us(line)
        if "phase=draft_prepare" in line:
            pending_draft = {**fields, "timestamp_us": ts_us, "task": current_task, "request_index": current_request_index}
        elif "phase=target_decode" in line:
            if fields.get("width", 0) <= 4:
                pending_target = {**fields, "timestamp_us": ts_us, "task": current_task, "request_index": current_request_index}
        elif "phase=accept_commit" in line and pending_draft and pending_target:
            if pending_draft["task"] != current_task or pending_target["task"] != current_task:
                continue
            cycle = {
                "task": current_task,
                "request_index": current_request_index,
                "prompt_id": prompt_ids[current_request_index] if current_request_index < len(prompt_ids) else None,
                "verifier_width": fields["verifier_width"],
                "drafted": fields["drafted"],
                "accepted": fields["accepted"],
                "emitted": fields["emitted"],
                "draft_prepare_us": pending_draft["host_us"],
                "target_decode_us": pending_target["target_us"],
                "spec_process_us": pending_target["spec_process_us"],
                "accept_us": fields["accept_us"],
                "commit_us": fields["commit_us"],
            }
            cycle["accounted_us"] = sum(cycle[key] for key in (
                "draft_prepare_us", "target_decode_us", "spec_process_us", "accept_us", "commit_us"
            ))
            if current_task is not None and current_task in previous_accept_ts and ts_us is not None:
                cycle["observed_cycle_us"] = ts_us - previous_accept_ts[current_task]
                cycle["unaccounted_us"] = cycle["observed_cycle_us"] - cycle["accounted_us"]
            if current_task is not None and ts_us is not None:
                previous_accept_ts[current_task] = ts_us
            cycles.append(cycle)
            pending_draft = None
            pending_target = None

    phases = ("draft_prepare_us", "target_decode_us", "spec_process_us", "accept_us", "commit_us", "accounted_us", "observed_cycle_us", "unaccounted_us")
    by_task: dict[int, list[dict]] = defaultdict(list)
    for cycle in cycles:
        by_task[cycle["request_index"]].append(cycle)

    prompt_summary = []
    for request_index, rows in sorted(by_task.items()):
        drafted = sum(row["drafted"] for row in rows)
        accepted = sum(row["accepted"] for row in rows)
        emitted = sum(row["emitted"] for row in rows)
        prompt_summary.append({
            "request_index": request_index,
            "task": rows[0]["task"],
            "prompt_id": rows[0]["prompt_id"],
            "cycles": len(rows),
            "drafted": drafted,
            "accepted": accepted,
            "emitted": emitted,
            "acceptance": accepted / drafted if drafted else None,
            "emitted_per_cycle": emitted / len(rows),
            "accepted_histogram": dict(sorted(Counter(row["accepted"] for row in rows).items())),
            "verifier_width_histogram": dict(sorted(Counter(row["verifier_width"] for row in rows).items())),
            "observed_cycle_us": stats([row["observed_cycle_us"] for row in rows if "observed_cycle_us" in row]),
        })

    drafted = sum(row["drafted"] for row in cycles)
    accepted = sum(row["accepted"] for row in cycles)
    emitted = sum(row["emitted"] for row in cycles)
    doc = {
        "schema_version": 1,
        "server_log": str(args.server_log),
        "result": str(args.result) if args.result else None,
        "cycles": len(cycles),
        "verifier_width_histogram": dict(sorted(Counter(row["verifier_width"] for row in cycles).items())),
        "accepted_histogram": dict(sorted(Counter(row["accepted"] for row in cycles).items())),
        "totals": {
            "drafted": drafted,
            "accepted": accepted,
            "emitted": emitted,
            "acceptance": accepted / drafted if drafted else None,
            "emitted_per_cycle": emitted / len(cycles) if cycles else None,
        },
        "phase_us": {phase: stats([row[phase] for row in cycles if phase in row]) for phase in phases},
        "by_prompt": prompt_summary,
        "budget": {
            "cycle_ms_for_68_tok_s_at_measured_emitted_per_cycle": (emitted / len(cycles)) / 68 * 1000 if cycles else None,
            "cycle_ms_for_100_tok_s_at_measured_emitted_per_cycle": (emitted / len(cycles)) / 100 * 1000 if cycles else None,
        },
        "limitations": [
            "Diagnostic rows add logging but no kernel instrumentation; target_decode and draft_prepare are blocking host wall intervals that include their device work.",
            "The final width-1 decode after each request is not a speculative verifier cycle and is excluded.",
            "Observed cycle time is accept-log to accept-log and therefore includes the next cycle's draft preparation plus logging/scheduling gaps.",
        ],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2) + "\n")


if __name__ == "__main__":
    main()
