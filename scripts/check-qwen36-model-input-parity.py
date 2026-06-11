#!/usr/bin/env python3
"""Compare Qwen3.6 verifier model-input traces row by row.

The trace is emitted by the local vLLM `VLLM_XPU_MODEL_INPUT_TRACE_FILE`
instrumentation. This checker intentionally normalizes volatile request IDs and
timestamps, then compares the scheduler-visible and verifier-input-visible
state that can explain accepted/placebo/speculative drift.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


VOLATILE_TOP_LEVEL = {"ts", "pid", "device"}


def load_rows(
    path: Path,
    *,
    max_rows: int | None,
    tp_rank: str | None,
    skip_dummy_or_profile: bool,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{line_no}: invalid JSON: {exc}") from exc
            if not isinstance(row, dict):
                raise SystemExit(f"{path}:{line_no}: expected object row")
            if tp_rank is not None and str(row.get("tp_rank")) != tp_rank:
                continue
            if skip_dummy_or_profile and (row.get("dummy_run") or row.get("is_profile")):
                continue
            rows.append(row)
            if max_rows is not None and len(rows) >= max_rows:
                break
    return rows


def normalize_tensor_record(value: Any) -> Any:
    if value is None:
        return None
    if not isinstance(value, dict):
        return value
    if "error" in value:
        return {"error": value.get("error")}
    out: dict[str, Any] = {}
    for key in ("shape", "dtype", "head"):
        if key in value:
            out[key] = value[key]
    return out


def normalize_group_record(record: Any) -> Any:
    if not isinstance(record, dict):
        return record
    out: dict[str, Any] = {}
    for key, value in record.items():
        if key == "group":
            continue
        if key == "device":
            continue
        if key.endswith("_error") or key == "error":
            out[key] = value
        elif isinstance(value, dict):
            out[key] = normalize_tensor_record(value)
        elif isinstance(value, list):
            out[key] = value
        else:
            out[key] = value
    return out


def normalize_group_records(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, dict):
        # Some runner variants record a single tensor record instead of a list
        # keyed by KV-cache group.
        if any(key in value for key in ("shape", "dtype", "head", "error")):
            return {"0": normalize_tensor_record(value)}
        return {str(key): normalize_group_record(val) for key, val in value.items()}
    if isinstance(value, list):
        grouped: dict[str, Any] = {}
        for index, record in enumerate(value):
            if isinstance(record, dict):
                group = record.get("group", index)
            else:
                group = index
            grouped[str(group)] = normalize_group_record(record)
        return grouped
    return value


def normalize_spec_tokens(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, dict):
        return []
    normalized = []
    for tokens in value.values():
        if isinstance(tokens, dict):
            normalized.append({
                "len": tokens.get("len"),
                "head": tokens.get("head", []),
            })
        elif isinstance(tokens, list):
            normalized.append({"len": len(tokens), "head": tokens[:16]})
    return sorted(normalized, key=lambda item: (item["len"], item["head"]))


def normalize_count_dict(value: Any) -> list[int]:
    if not isinstance(value, dict):
        return []
    return sorted(int(count) for count in value.values())


def pick(container: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: container[key] for key in keys if key in container}


def canonical_row(row: dict[str, Any]) -> dict[str, Any]:
    scheduler = row.get("scheduler") or {}
    input_batch = row.get("input_batch") or {}
    attn = row.get("attn") or {}

    canonical: dict[str, Any] = {
        "top": {
            key: value
            for key, value in row.items()
            if key
            not in VOLATILE_TOP_LEVEL
            and key not in ("scheduler", "input_batch", "attn", "batch_desc")
        },
        "batch_desc": pick(
            row.get("batch_desc") or {},
            ("cg_mode", "num_tokens", "num_reqs", "uniform"),
        ),
        "scheduler": {
            "total_num_scheduled_tokens": scheduler.get(
                "total_num_scheduled_tokens"
            ),
            "num_scheduled_token_counts": normalize_count_dict(
                scheduler.get("num_scheduled_tokens")
            ),
            "scheduled_spec_decode_tokens": normalize_spec_tokens(
                scheduler.get("scheduled_spec_decode_tokens")
            ),
        },
        "input_batch": {
            **pick(
                input_batch,
                (
                    "num_reqs",
                    "num_reqs_after_padding",
                    "num_tokens",
                    "num_tokens_after_padding",
                    "num_tokens_unpadded",
                    "num_tokens_padded",
                    "num_draft_tokens",
                    "use_spec_decode",
                    "skip_compiled",
                ),
            ),
            "spec_token_ids": input_batch.get("spec_token_ids"),
        },
        "attn": {
            "block_tables": normalize_group_records(attn.get("block_tables")),
            "slot_mappings": normalize_group_records(attn.get("slot_mappings")),
        },
    }

    for key in (
        "idx_mapping_np",
        "num_scheduled_tokens",
        "num_scheduled_tokens_np",
        "num_computed_tokens_cpu",
        "query_start_loc_np",
        "seq_lens_cpu_upper_bound",
        "cu_num_logits_np",
        "input_ids",
        "positions",
        "logits_indices",
        "expanded_local_pos",
    ):
        if key in input_batch:
            canonical["input_batch"][key] = normalize_tensor_record(
                input_batch[key]
            )
    return canonical


def first_diff(left: Any, right: Any, path: str = "") -> dict[str, Any] | None:
    if type(left) is not type(right):
        return {"path": path or "$", "left": left, "right": right}
    if isinstance(left, dict):
        left_keys = set(left)
        right_keys = set(right)
        if left_keys != right_keys:
            return {
                "path": path or "$",
                "left_keys": sorted(left_keys),
                "right_keys": sorted(right_keys),
            }
        for key in sorted(left_keys):
            child = first_diff(left[key], right[key], f"{path}.{key}" if path else key)
            if child is not None:
                return child
        return None
    if isinstance(left, list):
        if len(left) != len(right):
            return {
                "path": path or "$",
                "left_len": len(left),
                "right_len": len(right),
                "left": left[:16],
                "right": right[:16],
            }
        for index, (left_item, right_item) in enumerate(zip(left, right)):
            child = first_diff(left_item, right_item, f"{path}[{index}]")
            if child is not None:
                return child
        return None
    if left != right:
        return {"path": path or "$", "left": left, "right": right}
    return None


def compare_rows(
    left_rows: list[dict[str, Any]],
    right_rows: list[dict[str, Any]],
    *,
    max_mismatches: int,
) -> tuple[bool, list[dict[str, Any]]]:
    mismatches: list[dict[str, Any]] = []
    rows_compared = min(len(left_rows), len(right_rows))
    for index in range(rows_compared):
        left = canonical_row(left_rows[index])
        right = canonical_row(right_rows[index])
        diff = first_diff(left, right)
        if diff is not None:
            diff["row"] = index
            mismatches.append(diff)
            if len(mismatches) >= max_mismatches:
                break
    if len(left_rows) != len(right_rows) and len(mismatches) < max_mismatches:
        mismatches.append({
            "row": rows_compared,
            "path": "$row_count",
            "left_rows": len(left_rows),
            "right_rows": len(right_rows),
        })
    return not mismatches, mismatches


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Qwen3.6 Model-Input Parity",
        "",
        f"- left: `{report['left']}`",
        f"- right: `{report['right']}`",
        f"- rows compared: `{report['rows_compared']}`",
        f"- match all: `{str(report['match_all']).lower()}`",
    ]
    if report["mismatches"]:
        first = report["mismatches"][0]
        lines.extend([
            "",
            "## First Mismatch",
            "",
            f"- row: `{first.get('row')}`",
            f"- path: `{first.get('path')}`",
            "",
            "```json",
            json.dumps(first, indent=2, sort_keys=True),
            "```",
        ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--left", required=True, type=Path)
    parser.add_argument("--right", required=True, type=Path)
    parser.add_argument("--left-label", default="left")
    parser.add_argument("--right-label", default="right")
    parser.add_argument("--max-rows", type=int, default=None)
    parser.add_argument("--max-mismatches", type=int, default=20)
    parser.add_argument("--tp-rank", default=None)
    parser.add_argument("--skip-dummy-or-profile", action="store_true")
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    parser.add_argument("--expect-match", action="store_true")
    args = parser.parse_args()

    left_rows = load_rows(
        args.left,
        max_rows=args.max_rows,
        tp_rank=args.tp_rank,
        skip_dummy_or_profile=args.skip_dummy_or_profile,
    )
    right_rows = load_rows(
        args.right,
        max_rows=args.max_rows,
        tp_rank=args.tp_rank,
        skip_dummy_or_profile=args.skip_dummy_or_profile,
    )
    match_all, mismatches = compare_rows(
        left_rows, right_rows, max_mismatches=args.max_mismatches
    )
    report = {
        "left": str(args.left),
        "right": str(args.right),
        "left_label": args.left_label,
        "right_label": args.right_label,
        "left_rows": len(left_rows),
        "right_rows": len(right_rows),
        "rows_compared": min(len(left_rows), len(right_rows)),
        "match_all": match_all,
        "mismatches": mismatches,
    }
    if args.output_json:
        args.output_json.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if args.output_md:
        write_markdown(args.output_md, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.expect_match and not match_all:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
