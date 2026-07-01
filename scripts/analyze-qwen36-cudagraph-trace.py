#!/usr/bin/env python3
"""Summarize Qwen3.6 XPU CUDAGraph replay traces around canary failures."""

from __future__ import annotations

import argparse
import glob
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def load_jsonl(paths: list[str]) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    malformed = 0
    for pattern in paths:
        for raw_path in sorted(glob.glob(pattern)):
            path = Path(raw_path)
            with path.open("r", encoding="utf-8") as f:
                for line_no, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        malformed += 1
                        continue
                    row["_trace_path"] = str(path)
                    row["_line_no"] = line_no
                    rows.append(row)
    return rows, malformed


def request_index(req_id: str | None) -> int | None:
    if not req_id:
        return None
    match = re.search(r"(?:^|[-_])(?:json|color|req)-(\d{3,})(?:[-_]|$)", req_id)
    if match:
        return int(match.group(1))
    match = re.search(r"(\d+)$", req_id)
    if not match:
        return None
    return int(match.group(1))


def first_req(row: dict[str, Any]) -> str | None:
    ids = row.get("matched_req_ids") or row.get("req_ids") or []
    if ids:
        return str(ids[0])
    return None


def stage(row: dict[str, Any]) -> str:
    extra = row.get("forward_extra") or {}
    prompts = extra.get("xpu_num_prompt_tokens") or []
    computed = extra.get("xpu_num_computed_tokens") or []
    try:
        prompt = int(prompts[0])
        comp = int(computed[0])
    except Exception:
        return "unknown"
    if comp < prompt:
        return "prefill"
    if comp == prompt:
        return "first_decode"
    return "decode"


def digest_sig(obj: Any) -> Any:
    if isinstance(obj, dict):
        digest = obj.get("digest")
        if isinstance(digest, dict):
            return {
                "shape": obj.get("shape"),
                "dtype": obj.get("dtype"),
                "data_ptr": obj.get("data_ptr"),
                "storage_data_ptr": obj.get("storage_data_ptr"),
                "storage_offset": obj.get("storage_offset"),
                "sum": digest.get("sum"),
                "l2": digest.get("l2"),
                "head": digest.get("head"),
            }
        for key in ("$", "0", "1"):
            if key in obj:
                sig = digest_sig(obj[key])
                if sig is not None:
                    return sig
        for value in obj.values():
            sig = digest_sig(value)
            if sig is not None:
                return sig
    if isinstance(obj, list):
        for value in obj:
            sig = digest_sig(value)
            if sig is not None:
                return sig
    return None


def tensor_arg_sigs(row: dict[str, Any], limit: int = 4) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in row.get("tensor_args") or []:
        if len(out) >= limit:
            break
        digest = item.get("digest") or {}
        out.append(
            {
                "arg_index": item.get("arg_index"),
                "shape": item.get("shape"),
                "dtype": item.get("dtype"),
                "data_ptr": item.get("data_ptr"),
                "storage_data_ptr": item.get("storage_data_ptr"),
                "storage_offset": item.get("storage_offset"),
                "sum": digest.get("sum"),
                "l2": digest.get("l2"),
                "head": digest.get("head"),
            }
        )
    return out


def summarize_request_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for row in rows:
        summary.append(
            {
                "line": row.get("_line_no"),
                "rank": row.get("tp_rank"),
                "event": row.get("event"),
                "stage": stage(row),
                "label": row.get("label"),
                "batch_descriptor": row.get("batch_descriptor"),
                "entry": row.get("entry"),
                "input_address_check": row.get("input_address_check"),
                "arg_sigs": tensor_arg_sigs(row),
                "output_sig": digest_sig(row.get("output")),
                "reason": row.get("reason"),
            }
        )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", action="append", required=True)
    parser.add_argument("--canary-json", type=Path, required=True)
    parser.add_argument("--out-json", type=Path, required=True)
    parser.add_argument("--out-md", type=Path)
    parser.add_argument("--window", type=int, default=3)
    parser.add_argument("--max-request-rows", type=int, default=80)
    args = parser.parse_args()

    trace_rows, malformed = load_jsonl(args.trace)
    canary = load_json(args.canary_json)
    mismatches = canary.get("mismatches") or []
    first_mismatch = mismatches[0] if mismatches else None
    bad_req_id = (first_mismatch or {}).get("request_id")
    bad_index = (first_mismatch or {}).get("index")
    if bad_req_id is None and isinstance(bad_index, int):
        prefix = canary.get("request_id_prefix")
        if prefix:
            bad_req_id = f"{prefix}-{bad_index:06d}"

    bad_req_index = request_index(bad_req_id) if bad_req_id else bad_index
    rows_by_req: dict[str, list[dict[str, Any]]] = defaultdict(list)
    no_req_rows = 0
    for row in trace_rows:
        rid = first_req(row)
        if rid is None:
            no_req_rows += 1
            continue
        rows_by_req[rid].append(row)

    event_counts = Counter(str(row.get("event")) for row in trace_rows)
    label_counts = Counter(str(row.get("label")) for row in trace_rows)
    stage_counts = Counter(stage(row) for row in trace_rows)

    request_counts = {
        rid: len(items) for rid, items in sorted(rows_by_req.items())
    }
    nearby: dict[str, Any] = {}
    if bad_req_index is not None:
        for rid, items in rows_by_req.items():
            idx = request_index(rid)
            if idx is None:
                continue
            if abs(idx - int(bad_req_index)) <= args.window:
                nearby[rid] = summarize_request_rows(items[: args.max_request_rows])

    baseline_req_id = None
    if bad_req_index is not None:
        candidates = [
            rid
            for rid in rows_by_req
            if (request_index(rid) is not None and request_index(rid) < bad_req_index)
        ]
        if candidates:
            baseline_req_id = sorted(candidates, key=lambda rid: request_index(rid) or -1)[
                -1
            ]

    out = {
        "trace_patterns": args.trace,
        "trace_rows": len(trace_rows),
        "malformed_trace_rows": malformed,
        "canary_json": str(args.canary_json),
        "canary_case": canary.get("case"),
        "canary_pass_all": canary.get("pass_all"),
        "canary_repeats_completed": canary.get("repeats_completed"),
        "mismatch_count": canary.get("mismatch_count"),
        "first_mismatch": first_mismatch,
        "bad_req_id": bad_req_id,
        "bad_req_index": bad_req_index,
        "event_counts": dict(event_counts),
        "stage_counts": dict(stage_counts),
        "top_labels": label_counts.most_common(20),
        "traced_request_count": len(rows_by_req),
        "no_req_rows": no_req_rows,
        "request_counts_sample": dict(list(request_counts.items())[:20]),
        "baseline_req_id": baseline_req_id,
        "nearby_requests": nearby,
    }

    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(out, indent=2, default=str) + "\n")
    if args.out_md:
        lines = [
            "# Qwen3.6 CUDAGraph Trace Summary",
            "",
            f"- trace rows: `{len(trace_rows)}`",
            f"- malformed trace rows: `{malformed}`",
            f"- canary: `{args.canary_json}`",
            f"- pass_all: `{canary.get('pass_all')}`",
            f"- first mismatch: `{bad_req_id}` index `{bad_req_index}`",
            "",
            "## Counts",
            "",
            f"- events: `{dict(event_counts)}`",
            f"- stages: `{dict(stage_counts)}`",
            f"- traced requests: `{len(rows_by_req)}`",
            "",
            "## Top Labels",
            "",
        ]
        for label, count in label_counts.most_common(10):
            lines.append(f"- `{count}` `{label}`")
        lines.extend(["", "## Nearby Requests", ""])
        for rid, items in nearby.items():
            lines.append(f"### `{rid}`")
            lines.append("")
            for item in items[:12]:
                lines.append(
                    "- "
                    f"{item.get('event')} {item.get('stage')} "
                    f"entry={item.get('entry')} "
                    f"addr={item.get('input_address_check')}"
                )
            lines.append("")
        args.out_md.write_text("\n".join(lines) + "\n")

    print(
        json.dumps(
            {
                "out_json": str(args.out_json),
                "out_md": str(args.out_md) if args.out_md else None,
                "trace_rows": len(trace_rows),
                "bad_req_id": bad_req_id,
                "bad_req_index": bad_req_index,
                "mismatch_count": canary.get("mismatch_count"),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
