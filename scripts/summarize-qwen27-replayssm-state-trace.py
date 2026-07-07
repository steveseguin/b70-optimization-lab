#!/usr/bin/env python3
"""Summarize Qwen27 ReplaySSM state trace records.

Input is a GDN row trace JSONL emitted with
`VLLM_XPU_GDN_ROW_TRACE_REPLAYSSM_STATE=1`.  The trace is diagnostic only: it
captures ReplaySSM ring cursor / pending metadata and small state digests around
stage/commit/spec-decode boundaries, but it does not prove a speedup or quality
result by itself.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


REPLAYSSM_STAGES = {
    "replayssm_commit_pending_before",
    "replayssm_commit_pending_after",
    "replayssm_after_stage_conv",
    "replayssm_after_spec_decode",
}


def load_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{line_no}: invalid JSON: {exc}") from exc
            if rec.get("stage") in REPLAYSSM_STAGES:
                records.append(rec)
    return records


def flatten_ints(value: Any) -> list[int]:
    if not isinstance(value, list):
        return []
    out: list[int] = []
    for item in value:
        try:
            out.append(int(item))
        except (TypeError, ValueError):
            continue
    return out


def digest_presence(records: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for rec in records:
        state = rec.get("replayssm_state")
        if not isinstance(state, dict):
            continue
        for key, value in state.items():
            if value is not None:
                counts[key] += 1
    return dict(sorted(counts.items()))


def summarize(records: list[dict[str, Any]], trace_path: Path) -> dict[str, Any]:
    stage_counts = Counter(str(rec.get("stage")) for rec in records)
    layer_counts = Counter(str(rec.get("layer")) for rec in records)
    slot_counts: Counter[int] = Counter()
    pending_counts: Counter[int] = Counter()
    pending_len_counts: Counter[int] = Counter()
    write_pos_counts: Counter[int] = Counter()
    cache_base_counts: Counter[int] = Counter()
    accepted_counts: Counter[int] = Counter()

    for rec in records:
        slot_counts.update(flatten_ints(rec.get("slots_sample")))
        pending_counts.update(flatten_ints(rec.get("pending")))
        pending_len_counts.update(flatten_ints(rec.get("pending_len")))
        write_pos_counts.update(flatten_ints(rec.get("write_pos")))
        cache_base_counts.update(flatten_ints(rec.get("cache_base")))
        accepted_counts.update(flatten_ints(rec.get("num_accepted_tokens")))

    samples = []
    for rec in records[:8]:
        sample = {
            "stage": rec.get("stage"),
            "layer": rec.get("layer"),
            "layer_idx": rec.get("layer_idx"),
            "slots_sample": rec.get("slots_sample"),
            "num_accepted_tokens": rec.get("num_accepted_tokens"),
            "write_pos": rec.get("write_pos"),
            "cache_base": rec.get("cache_base"),
            "pending": rec.get("pending"),
            "pending_len": rec.get("pending_len"),
            "has_state_digest": isinstance(rec.get("replayssm_state"), dict),
        }
        samples.append(sample)

    return {
        "classification": "qwen27_replayssm_state_trace_summary",
        "diagnostic_only": True,
        "trace": str(trace_path),
        "record_count": len(records),
        "stage_counts": dict(sorted(stage_counts.items())),
        "layer_counts": dict(sorted(layer_counts.items())),
        "slot_counts": dict(sorted(slot_counts.items())),
        "accepted_token_value_counts": dict(sorted(accepted_counts.items())),
        "pending_value_counts": dict(sorted(pending_counts.items())),
        "pending_len_value_counts": dict(sorted(pending_len_counts.items())),
        "write_pos_value_counts": dict(sorted(write_pos_counts.items())),
        "cache_base_value_counts": dict(sorted(cache_base_counts.items())),
        "state_digest_record_counts": digest_presence(records),
        "samples": samples,
        "interpretation": (
            "Diagnostic trace only. Stage/cursor coverage can show whether the "
            "ReplaySSM transaction points were observed; correctness still "
            "requires the existing GDN unit contracts and endpoint quality gate."
        ),
    }


def write_md(summary: dict[str, Any], path: Path) -> None:
    lines = [
        "# Qwen27 ReplaySSM State Trace Summary",
        "",
        "Classification: diagnostic only, no endpoint mutation, no headline result.",
        "",
        f"Trace: `{summary['trace']}`",
        "",
        "| metric | value |",
        "| --- | ---: |",
        f"| `record_count` | {summary['record_count']} |",
        "",
        "Stage counts:",
        "",
        "```json",
        json.dumps(summary["stage_counts"], indent=2, sort_keys=True),
        "```",
        "",
        "Cursor and pending histograms:",
        "",
        "```json",
        json.dumps({
            "accepted_token_value_counts": summary["accepted_token_value_counts"],
            "pending_value_counts": summary["pending_value_counts"],
            "pending_len_value_counts": summary["pending_len_value_counts"],
            "write_pos_value_counts": summary["write_pos_value_counts"],
            "cache_base_value_counts": summary["cache_base_value_counts"],
            "state_digest_record_counts": summary["state_digest_record_counts"],
        }, indent=2, sort_keys=True),
        "```",
        "",
        "First records:",
        "",
        "```json",
        json.dumps(summary["samples"], indent=2, sort_keys=True),
        "```",
        "",
        summary["interpretation"],
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", required=True, type=Path)
    parser.add_argument("--out-json", required=True, type=Path)
    parser.add_argument("--out-md", required=True, type=Path)
    args = parser.parse_args()

    records = load_records(args.trace)
    summary = summarize(records, args.trace)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_md(summary, args.out_md)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
