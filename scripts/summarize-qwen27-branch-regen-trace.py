#!/usr/bin/env python3
"""Summarize Qwen27 branch/regenerate opportunity trace records.

Input is a COW worker trace JSONL containing records emitted by
`VLLM_XPU_BRANCH_REGEN_TRACE=1` from gpu_model_runner.py.  The trace is
diagnostic only: it measures the legal accepted-draft-prefix surface on fresh
endpoint runs, but it does not prove a speedup or quality result.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any


def load_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{line_no}: invalid JSON: {exc}") from exc
            if rec.get("stage") != "branch_regen_candidates":
                continue
            for row in (rec.get("extra") or {}).get("rows") or []:
                if row.get("scheduled_spec_len", 0) > 0:
                    rows.append(row)
    return rows


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    partial = [r for r in rows if r.get("partial_reject")]
    full = [r for r in rows if r.get("full_accept")]
    raw_counts = [int(r.get("raw_visible_count", 0)) for r in rows]
    prefix_counts = [int(r.get("draft_prefix_count", 0)) for r in rows]
    first_reject = [
        int(r["first_reject_index"])
        for r in partial
        if r.get("first_reject_index") is not None
    ]
    scheduled_lens = [int(r.get("scheduled_spec_len", 0)) for r in rows]
    hist_raw = Counter(raw_counts)
    hist_prefix = Counter(prefix_counts)
    hist_first_reject = Counter(first_reject)
    hist_sched = Counter(scheduled_lens)
    branchable_after_first_reject = sum(
        max(0, int(r.get("scheduled_spec_len", 0))
            - int(r.get("draft_prefix_count", 0)))
        for r in partial
    )
    return {
        "classification": "qwen27_branch_regen_trace_summary",
        "diagnostic_only": True,
        "scheduled_rows": total,
        "partial_reject_rows": len(partial),
        "full_accept_rows": len(full),
        "partial_reject_rate": (len(partial) / total if total else None),
        "full_accept_rate": (len(full) / total if total else None),
        "mean_raw_visible_tokens": (mean(raw_counts) if raw_counts else None),
        "mean_accepted_draft_prefix": (
            mean(prefix_counts) if prefix_counts else None),
        "mean_scheduled_spec_len": (
            mean(scheduled_lens) if scheduled_lens else None),
        "branchable_remaining_draft_rows": branchable_after_first_reject,
        "hist_raw_visible_count": dict(sorted(hist_raw.items())),
        "hist_draft_prefix_count": dict(sorted(hist_prefix.items())),
        "hist_first_reject_index": dict(sorted(hist_first_reject.items())),
        "hist_scheduled_spec_len": dict(sorted(hist_sched.items())),
    }


def write_md(summary: dict[str, Any], path: Path, trace_path: Path) -> None:
    def fmt(value: Any) -> str:
        if isinstance(value, float):
            return f"{value:.6f}"
        return str(value)

    lines = [
        "# Qwen27 Branch/Regenerate Trace Summary",
        "",
        "Classification: diagnostic only, no endpoint mutation, no headline result.",
        "",
        f"Trace: `{trace_path}`",
        "",
        "| metric | value |",
        "| --- | ---: |",
    ]
    for key in [
        "scheduled_rows",
        "partial_reject_rows",
        "partial_reject_rate",
        "full_accept_rows",
        "full_accept_rate",
        "mean_raw_visible_tokens",
        "mean_accepted_draft_prefix",
        "mean_scheduled_spec_len",
        "branchable_remaining_draft_rows",
    ]:
        lines.append(f"| `{key}` | {fmt(summary.get(key))} |")
    lines.extend([
        "",
        "Histograms:",
        "",
        "```json",
        json.dumps({
            "hist_raw_visible_count": summary.get("hist_raw_visible_count"),
            "hist_draft_prefix_count": summary.get("hist_draft_prefix_count"),
            "hist_first_reject_index": summary.get("hist_first_reject_index"),
            "hist_scheduled_spec_len": summary.get("hist_scheduled_spec_len"),
        }, indent=2, sort_keys=True),
        "```",
        "",
        "Interpretation: normal MTP verifier rows expose accepted draft prefix as "
        "`max(raw_visible_count - 1, 0)` clamped to scheduled spec length; the "
        "target-owned replacement/bonus tail is deliberately excluded.",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", required=True, type=Path)
    parser.add_argument("--out-json", required=True, type=Path)
    parser.add_argument("--out-md", required=True, type=Path)
    args = parser.parse_args()

    rows = load_rows(args.trace)
    summary = summarize(rows)
    summary["trace"] = str(args.trace)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_md(summary, args.out_md, args.trace)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
