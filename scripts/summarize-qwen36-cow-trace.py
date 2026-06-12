#!/usr/bin/env python3
"""Summarize Qwen3.6 COW verifier parent-state trace JSONL.

The trace is produced by the default-off vLLM scheduler patch controlled by
``VLLM_XPU_COW_VERIFIER_TRACE_FILE``. It records parent request state around
scheduling and output commit so a future scratch-row verifier can prove it is
not mutating the parent while candidates are scored.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


DELTA_FIELDS = (
    "num_output_tokens",
    "num_tokens",
    "num_tokens_with_spec",
    "num_computed_tokens",
    "num_output_placeholders",
    "spec_len",
)


def load_jsonl(path: Path) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    malformed = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            malformed += 1
            continue
        if isinstance(value, dict):
            rows.append(value)
        else:
            malformed += 1
    return rows, malformed


def as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def state_delta(
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(before, dict) or not isinstance(after, dict):
        return {}

    delta: dict[str, Any] = {}
    for field in DELTA_FIELDS:
        if field in before or field in after:
            delta[field] = as_int(after.get(field)) - as_int(before.get(field))

    before_blocks = before.get("kv_block_lengths")
    after_blocks = after.get("kv_block_lengths")
    if isinstance(before_blocks, list) or isinstance(after_blocks, list):
        delta["kv_block_lengths_before"] = before_blocks
        delta["kv_block_lengths_after"] = after_blocks
        delta["kv_block_lengths_changed"] = before_blocks != after_blocks

    before_last = before.get("kv_last_block_ids")
    after_last = after.get("kv_last_block_ids")
    if isinstance(before_last, list) or isinstance(after_last, list):
        delta["kv_last_block_ids_changed"] = before_last != after_last
    return delta


def stage_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("stage") or "unknown")].append(row)

    output = []
    for stage, items in sorted(grouped.items()):
        nonzero_delta_counts = {field: 0 for field in DELTA_FIELDS}
        max_abs_delta = {field: 0 for field in DELTA_FIELDS}
        kv_changed = 0
        spec_rows = 0
        examples = []

        for row in items:
            scheduled_spec = row.get("scheduled_spec_token_ids")
            if isinstance(scheduled_spec, list) and scheduled_spec:
                spec_rows += 1
            delta = row.get("delta")
            if not isinstance(delta, dict):
                continue
            for field in DELTA_FIELDS:
                value = as_int(delta.get(field))
                if value:
                    nonzero_delta_counts[field] += 1
                    max_abs_delta[field] = max(max_abs_delta[field], abs(value))
            if delta.get("kv_block_lengths_changed"):
                kv_changed += 1
            if len(examples) < 5 and (
                any(as_int(delta.get(field)) for field in DELTA_FIELDS)
                or delta.get("kv_block_lengths_changed")
            ):
                examples.append(
                    {
                        "req_id": row.get("req_id"),
                        "num_scheduled_tokens": row.get("num_scheduled_tokens"),
                        "scheduled_spec_len": len(scheduled_spec)
                        if isinstance(scheduled_spec, list)
                        else 0,
                        "delta": delta,
                    }
                )

        output.append(
            {
                "stage": stage,
                "rows": len(items),
                "spec_rows": spec_rows,
                "kv_block_lengths_changed_rows": kv_changed,
                "nonzero_delta_counts": nonzero_delta_counts,
                "max_abs_delta": max_abs_delta,
                "examples": examples,
            }
        )
    return output


def schedule_transition_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pending_before: dict[str, list[dict[str, Any]]] = defaultdict(list)
    transitions = []
    unmatched_after = 0

    for row in rows:
        stage = row.get("stage")
        req_id = str(row.get("req_id") or "")
        if not req_id:
            continue
        if stage == "before_update_after_schedule":
            pending_before[req_id].append(row)
        elif stage == "after_update_after_schedule":
            before_row = (
                pending_before[req_id].pop(0)
                if pending_before.get(req_id)
                else None
            )
            if before_row is None:
                unmatched_after += 1
                continue
            scheduled_spec = row.get("scheduled_spec_token_ids")
            delta = state_delta(
                before_row.get("state_after"),
                row.get("state_after"),
            )
            transitions.append(
                {
                    "req_id": req_id,
                    "num_scheduled_tokens": row.get("num_scheduled_tokens"),
                    "scheduled_spec_len": len(scheduled_spec)
                    if isinstance(scheduled_spec, list)
                    else 0,
                    "scheduled_spec_token_ids": scheduled_spec
                    if isinstance(scheduled_spec, list)
                    else [],
                    "delta": delta,
                }
            )

    unmatched_before = sum(len(items) for items in pending_before.values())
    nonzero_delta_counts = {field: 0 for field in DELTA_FIELDS}
    max_abs_delta = {field: 0 for field in DELTA_FIELDS}
    kv_changed = 0
    kv_last_changed = 0
    spec_transitions = 0
    examples = []

    for item in transitions:
        if item.get("scheduled_spec_len"):
            spec_transitions += 1
        delta = item.get("delta")
        if not isinstance(delta, dict):
            continue
        for field in DELTA_FIELDS:
            value = as_int(delta.get(field))
            if value:
                nonzero_delta_counts[field] += 1
                max_abs_delta[field] = max(max_abs_delta[field], abs(value))
        if delta.get("kv_block_lengths_changed"):
            kv_changed += 1
        if delta.get("kv_last_block_ids_changed"):
            kv_last_changed += 1
        if len(examples) < 8 and (
            any(as_int(delta.get(field)) for field in DELTA_FIELDS)
            or delta.get("kv_block_lengths_changed")
            or delta.get("kv_last_block_ids_changed")
        ):
            examples.append(item)

    return {
        "transitions": len(transitions),
        "spec_transitions": spec_transitions,
        "unmatched_before_rows": unmatched_before,
        "unmatched_after_rows": unmatched_after,
        "kv_block_lengths_changed_rows": kv_changed,
        "kv_last_block_ids_changed_rows": kv_last_changed,
        "nonzero_delta_counts": nonzero_delta_counts,
        "max_abs_delta": max_abs_delta,
        "examples": examples,
    }


def write_markdown(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# Qwen3.6 COW Parent-State Trace Summary",
        "",
        f"- Trace: `{summary['trace']}`",
        f"- Rows: `{summary['row_count']}`",
        f"- Malformed rows: `{summary['malformed_rows']}`",
        "",
        "| Stage | Rows | Spec rows | KV changed rows | num_computed delta rows | output delta rows | spec_len delta rows |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for stage in summary["stages"]:
        counts = stage["nonzero_delta_counts"]
        lines.append(
            "| "
            + " | ".join(
                [
                    stage["stage"],
                    str(stage["rows"]),
                    str(stage["spec_rows"]),
                    str(stage["kv_block_lengths_changed_rows"]),
                    str(counts.get("num_computed_tokens", 0)),
                    str(counts.get("num_output_tokens", 0)),
                    str(counts.get("spec_len", 0)),
                ]
            )
            + " |"
        )

    sched = summary.get("schedule_transitions") or {}
    if sched:
        counts = sched.get("nonzero_delta_counts") or {}
        max_delta = sched.get("max_abs_delta") or {}
        lines.extend(
            [
                "",
                "## Schedule Transitions",
                "",
                "Pairwise delta from `before_update_after_schedule` to "
                "`after_update_after_schedule` for the same parent request.",
                "",
                f"- Transitions: `{sched.get('transitions')}`",
                f"- Spec transitions: `{sched.get('spec_transitions')}`",
                f"- Unmatched before rows: `{sched.get('unmatched_before_rows')}`",
                f"- Unmatched after rows: `{sched.get('unmatched_after_rows')}`",
                f"- KV block length changed rows: `{sched.get('kv_block_lengths_changed_rows')}`",
                f"- KV last-block changed rows: `{sched.get('kv_last_block_ids_changed_rows')}`",
                "",
                "| Field | Nonzero rows | Max abs delta |",
                "| --- | ---: | ---: |",
            ]
        )
        for field in DELTA_FIELDS:
            lines.append(
                f"| `{field}` | {counts.get(field, 0)} | "
                f"{max_delta.get(field, 0)} |"
            )

    lines.extend(["", "## Examples", ""])
    for stage in summary["stages"]:
        if not stage["examples"]:
            continue
        lines.append(f"### {stage['stage']}")
        lines.append("")
        for example in stage["examples"]:
            lines.append("```json")
            lines.append(json.dumps(example, indent=2, sort_keys=True))
            lines.append("```")
            lines.append("")

    if sched and sched.get("examples"):
        lines.extend(["## Schedule Transition Examples", ""])
        for example in sched["examples"]:
            lines.append("```json")
            lines.append(json.dumps(example, indent=2, sort_keys=True))
            lines.append("```")
            lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    args = parser.parse_args()

    rows, malformed = load_jsonl(args.trace)
    summary = {
        "trace": str(args.trace),
        "row_count": len(rows),
        "malformed_rows": malformed,
        "stages": stage_summary(rows),
        "schedule_transitions": schedule_transition_summary(rows),
    }

    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        write_markdown(args.output_md, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
