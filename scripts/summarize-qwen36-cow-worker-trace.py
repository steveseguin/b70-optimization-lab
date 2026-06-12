#!/usr/bin/env python3
"""Summarize Qwen3.6 worker-side COW/spec trace JSONL."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def load_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{line_no}: invalid JSON: {exc}") from exc
    return rows


def head_values(record: dict[str, Any] | None) -> list[Any]:
    if not isinstance(record, dict):
        return []
    values = record.get("head")
    return values if isinstance(values, list) else []


def request_state(row: dict[str, Any]) -> dict[str, Any]:
    state = row.get("request")
    return state if isinstance(state, dict) else {}


def input_row_state(row: dict[str, Any]) -> dict[str, Any]:
    state = row.get("input_row")
    return state if isinstance(state, dict) else {}


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    stage_counts = Counter(str(row.get("stage", "<missing>")) for row in rows)
    rank_counts = Counter(str(row.get("tp_rank", "<missing>")) for row in rows)
    req_ids = sorted(
        {
            str(row["req_id"])
            for row in rows
            if row.get("req_id") is not None
        }
    )

    stage_by_req: dict[str, list[dict[str, Any]]] = defaultdict(list)
    spec_updates: list[dict[str, Any]] = []
    prepare_events: list[dict[str, Any]] = []

    for row_index, row in enumerate(rows):
        stage = str(row.get("stage", "<missing>"))
        req_id = row.get("req_id")
        req = request_state(row)
        inp = input_row_state(row)
        extra = row.get("extra")
        extra = extra if isinstance(extra, dict) else {}

        if req_id is not None:
            stage_by_req[str(req_id)].append(
                {
                    "row": row_index,
                    "stage": stage,
                    "tp_rank": row.get("tp_rank"),
                    "request_num_computed_tokens": req.get(
                        "num_computed_tokens"
                    ),
                    "request_num_tokens": req.get("num_tokens"),
                    "request_num_output_tokens": req.get(
                        "num_output_tokens"
                    ),
                    "request_prev_num_draft_len": req.get(
                        "prev_num_draft_len"
                    ),
                    "input_num_computed_tokens_cpu": inp.get(
                        "num_computed_tokens_cpu"
                    ),
                    "input_num_tokens_no_spec": inp.get(
                        "num_tokens_no_spec"
                    ),
                    "input_spec_len": len(inp.get("spec_token_ids_head", [])),
                    "scheduled_spec_len": extra.get("scheduled_spec_len"),
                }
            )

        spec_update = extra.get("spec_update")
        if isinstance(spec_update, dict):
            spec_updates.append(
                {
                    "row": row_index,
                    "stage": stage,
                    "tp_rank": row.get("tp_rank"),
                    "req_id": spec_update.get("req_id") or req_id,
                    "scheduled_spec_len": spec_update.get(
                        "scheduled_spec_len"
                    ),
                    "write_start": spec_update.get("write_start"),
                    "write_end": spec_update.get("write_end"),
                    "num_tokens_no_spec": spec_update.get(
                        "num_tokens_no_spec"
                    ),
                    "prev_num_draft_len_before": spec_update.get(
                        "prev_num_draft_len_before"
                    ),
                    "prev_num_draft_len_after": spec_update.get(
                        "prev_num_draft_len_after"
                    ),
                    "scheduled_spec_head": spec_update.get(
                        "scheduled_spec_head"
                    ),
                }
            )

        if stage == "after_prepare_positions":
            prepare_events.append(
                {
                    "row": row_index,
                    "tp_rank": row.get("tp_rank"),
                    "num_reqs": extra.get("num_reqs"),
                    "total_num_scheduled_tokens": extra.get(
                        "total_num_scheduled_tokens"
                    ),
                    "num_scheduled_tokens_head": head_values(
                        extra.get("num_scheduled_tokens_head")
                    ),
                    "num_computed_tokens_gpu_head": head_values(
                        extra.get("num_computed_tokens_gpu_head")
                    ),
                    "positions_head": head_values(extra.get("positions_head")),
                    "seq_lens_head": head_values(extra.get("seq_lens_head")),
                    "prev_num_draft_tokens_head": head_values(
                        extra.get("prev_num_draft_tokens_head")
                    ),
                }
            )

    spec_len_counts = Counter(
        str(update.get("scheduled_spec_len")) for update in spec_updates
    )
    nonzero_spec_updates = [
        update
        for update in spec_updates
        if int(update.get("scheduled_spec_len") or 0) > 0
    ]

    return {
        "row_count": len(rows),
        "stage_counts": dict(stage_counts),
        "rank_counts": dict(rank_counts),
        "request_count": len(req_ids),
        "request_ids": req_ids[:32],
        "spec_update_count": len(spec_updates),
        "spec_update_len_counts": dict(spec_len_counts),
        "nonzero_spec_update_count": len(nonzero_spec_updates),
        "nonzero_spec_updates_head": nonzero_spec_updates[:32],
        "prepare_event_count": len(prepare_events),
        "prepare_events_head": prepare_events[:32],
        "stage_transitions_by_req_head": {
            req_id: events[:32]
            for req_id, events in list(stage_by_req.items())[:16]
        },
    }


def write_markdown(summary: dict[str, Any], output: Path) -> None:
    lines = [
        "# Qwen3.6 COW Worker-State Trace Summary",
        "",
        f"- Rows: `{summary['row_count']}`",
        f"- Requests: `{summary['request_count']}`",
        f"- Spec update rows: `{summary['spec_update_count']}`",
        f"- Nonzero spec updates: `{summary['nonzero_spec_update_count']}`",
        f"- Prepare-position rows: `{summary['prepare_event_count']}`",
        "",
        "## Stage Counts",
        "",
    ]
    for stage, count in summary["stage_counts"].items():
        lines.append(f"- `{stage}`: `{count}`")
    lines.extend(["", "## Nonzero Spec Updates", ""])
    for update in summary["nonzero_spec_updates_head"]:
        lines.append(
            "- "
            f"row `{update['row']}`, rank `{update['tp_rank']}`, "
            f"req `{update['req_id']}`, "
            f"spec `{update['scheduled_spec_len']}`, "
            f"write `{update['write_start']}:{update['write_end']}`, "
            f"num_tokens_no_spec `{update['num_tokens_no_spec']}`, "
            f"prev_draft `{update['prev_num_draft_len_before']}` -> "
            f"`{update['prev_num_draft_len_after']}`"
        )
    if not summary["nonzero_spec_updates_head"]:
        lines.append("- none")
    lines.extend(["", "## Prepare Events", ""])
    for event in summary["prepare_events_head"][:8]:
        lines.append(
            "- "
            f"row `{event['row']}`, rank `{event['tp_rank']}`, "
            f"reqs `{event['num_reqs']}`, "
            f"scheduled `{event['total_num_scheduled_tokens']}`, "
            f"computed_gpu_head `{event['num_computed_tokens_gpu_head'][:8]}`, "
            f"seq_lens_head `{event['seq_lens_head'][:8]}`"
        )
    if not summary["prepare_events_head"]:
        lines.append("- none")
    lines.append("")
    output.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", required=True, type=Path)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    args = parser.parse_args()

    summary = summarize(load_rows(args.trace))
    text = json.dumps(summary, indent=2, sort_keys=True)
    if args.output_json:
        args.output_json.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    if args.output_md:
        write_markdown(summary, args.output_md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
