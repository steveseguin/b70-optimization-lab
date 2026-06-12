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
