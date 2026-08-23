#!/usr/bin/env python3
"""Fail-closed coverage validator for the Qwen3.8 D1/D2 mechanism traces."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_jsonl(path: Path, errors: list[str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not path.is_file():
        errors.append(f"missing trace: {path}")
        return records
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"{path.name}:{line_number}: malformed JSON: {exc}")
                continue
            if not isinstance(record, dict):
                errors.append(f"{path.name}:{line_number}: record is not an object")
                continue
            records.append(record)
    if not records:
        errors.append(f"empty trace: {path}")
    return records


def head_values(value: Any) -> list[Any]:
    if isinstance(value, dict) and isinstance(value.get("head"), list):
        return value["head"]
    if isinstance(value, list):
        return value
    return []


def request_matches(record_id: Any, benchmark_id: str) -> bool:
    return benchmark_id in str(record_id or "")


def validate_d1(
    records: list[dict[str, Any]],
    bench_rows: list[dict[str, Any]],
    errors: list[str],
) -> dict[str, Any]:
    event_counts = Counter(str(record.get("event")) for record in records)
    collisions: list[dict[str, Any]] = []
    live_by_group: dict[int, dict[int, str]] = defaultdict(dict)

    for record in sorted(records, key=lambda item: float(item.get("ts", 0))):
        event = record.get("event")
        request_id = str(record.get("request_id") or "")
        try:
            group_id = int(record.get("group_id"))
        except (TypeError, ValueError):
            continue
        if event == "allocate_new_blocks":
            for raw_block_id in record.get("new_block_ids") or []:
                block_id = int(raw_block_id)
                owner = live_by_group[group_id].get(block_id)
                if owner is not None and owner != request_id:
                    collisions.append(
                        {
                            "group_id": group_id,
                            "block_id": block_id,
                            "live_owner": owner,
                            "new_owner": request_id,
                            "step": record.get("step"),
                        }
                    )
                live_by_group[group_id][block_id] = request_id
        elif event == "free":
            for raw_block_id in record.get("released_block_ids") or []:
                block_id = int(raw_block_id)
                if live_by_group[group_id].get(block_id) == request_id:
                    del live_by_group[group_id][block_id]

    row_summaries: list[dict[str, Any]] = []
    for row in bench_rows:
        benchmark_id = str(row.get("request_id") or "")
        prompt_tokens = int(row.get("prompt_tokens") or 0)
        lifecycle = [
            record
            for record in records
            if request_matches(record.get("request_id"), benchmark_id)
        ]
        allocations = [
            record
            for record in lifecycle
            if record.get("event") == "allocate_new_blocks"
            and record.get("new_block_ids")
        ]
        frees = [record for record in lifecycle if record.get("event") == "free"]
        allocation_groups = sorted(
            {int(record["group_id"]) for record in allocations}
        )
        free_groups = sorted({int(record["group_id"]) for record in frees})
        if allocation_groups != [0, 1, 2]:
            errors.append(
                f"D1 {benchmark_id}: initial allocation groups {allocation_groups}, expected [0, 1, 2]"
            )
        if free_groups != [0, 1, 2]:
            errors.append(
                f"D1 {benchmark_id}: free groups {free_groups}, expected [0, 1, 2]"
            )

        allocated_slots = {
            int(record["group_id"]): [int(value) for value in record["new_block_ids"]]
            for record in allocations
        }
        if lifecycle:
            start_ts = min(float(record.get("ts", 0)) for record in lifecycle)
            end_ts = max(float(record.get("ts", 0)) for record in lifecycle)
        else:
            start_ts = end_ts = -1.0
        prefill_metadata = [
            record
            for record in records
            if record.get("event") == "metadata_build"
            and int(record.get("num_prefills") or 0) > 0
            and start_ts <= float(record.get("ts", 0)) <= end_ts
        ]
        expected_tail = prompt_tokens - 1024
        prefill_sizes = Counter(
            int(record.get("num_prefill_tokens") or 0)
            for record in prefill_metadata
        )
        expected_prefill_sizes = Counter({1024: 6, expected_tail: 6})
        if prefill_sizes != expected_prefill_sizes:
            errors.append(
                f"D1 {benchmark_id}: prefill metadata sizes {dict(prefill_sizes)}, "
                f"expected {dict(expected_prefill_sizes)}"
            )

        expected_state_slots = {
            slots[0] for slots in allocated_slots.values() if slots
        }
        observed_state_slots = {
            int(head_values(record.get("non_spec_state_indices_tensor"))[0])
            for record in prefill_metadata
            if head_values(record.get("non_spec_state_indices_tensor"))
        }
        if observed_state_slots != expected_state_slots:
            errors.append(
                f"D1 {benchmark_id}: consumed slots {sorted(observed_state_slots)}, "
                f"expected {sorted(expected_state_slots)}"
            )

        row_summaries.append(
            {
                "benchmark_request_id": benchmark_id,
                "prompt_tokens": prompt_tokens,
                "allocation_groups": allocation_groups,
                "free_groups": free_groups,
                "allocated_slots": allocated_slots,
                "prefill_metadata_records": len(prefill_metadata),
                "prefill_sizes": dict(sorted(prefill_sizes.items())),
                "observed_state_slots": sorted(observed_state_slots),
            }
        )

    if collisions:
        errors.append(f"D1 live-slot collisions observed: {len(collisions)}")
    return {
        "record_count": len(records),
        "event_counts": dict(sorted(event_counts.items())),
        "rows": row_summaries,
        "live_slot_collisions": collisions,
        "slots_still_live_after_trace": {
            str(group_id): sorted(blocks)
            for group_id, blocks in live_by_group.items()
            if blocks
        },
    }


def d2_request_view(record: dict[str, Any], benchmark_id: str) -> dict[str, Any] | None:
    extra = record.get("forward_context_extra") or {}
    request_ids = [str(value) for value in extra.get("xpu_req_ids") or []]
    matching_indices = [
        index
        for index, request_id in enumerate(request_ids)
        if request_matches(request_id, benchmark_id)
    ]
    if not matching_indices:
        return None
    index = matching_indices[0]
    prompt_tokens = extra.get("xpu_num_prompt_tokens") or []
    computed_tokens = extra.get("xpu_num_computed_tokens") or []
    if index >= len(prompt_tokens) or index >= len(computed_tokens):
        return {
            "error": "request-indexed prompt/computed token coverage is missing",
            "request_ids": request_ids,
        }
    flags = (record.get("metadata") or {}).get("has_initial_state")
    return {
        "internal_request_id": request_ids[index],
        "prompt_tokens": int(prompt_tokens[index]),
        "computed_tokens": int(computed_tokens[index]),
        "has_initial_state": flags,
        "layer": record.get("layer"),
        "tp_rank": record.get("tp_rank"),
    }


def validate_d2(
    records: list[dict[str, Any]],
    bench_rows: list[dict[str, Any]],
    errors: list[str],
) -> dict[str, Any]:
    callsite_records = [
        record
        for record in records
        if record.get("stage") == "fallback_pre_conv"
        and int(record.get("tp_rank") or 0) == 0
        and re.search(r"layers\.0\.linear_attn$", str(record.get("layer") or ""))
    ]
    row_summaries: list[dict[str, Any]] = []
    for row in bench_rows:
        benchmark_id = str(row.get("request_id") or "")
        expected_prompt_tokens = int(row.get("prompt_tokens") or 0)
        views = [
            view
            for record in callsite_records
            if (view := d2_request_view(record, benchmark_id)) is not None
        ]
        if any("error" in view for view in views):
            errors.append(f"D2 {benchmark_id}: malformed request-indexed coverage")
        views.sort(key=lambda view: int(view.get("computed_tokens", -1)))
        computed = [view.get("computed_tokens") for view in views]
        if computed != [0, 1024]:
            errors.append(
                f"D2 {benchmark_id}: computed-token sequence {computed}, expected [0, 1024]"
            )
        flags = [view.get("has_initial_state") for view in views]
        if flags != [[False], [True]]:
            errors.append(
                f"D2 {benchmark_id}: initial-state sequence {flags}, expected [[false], [true]]"
            )
        prompts = [view.get("prompt_tokens") for view in views]
        if prompts != [expected_prompt_tokens, expected_prompt_tokens]:
            errors.append(
                f"D2 {benchmark_id}: prompt-token sequence {prompts}, "
                f"expected two copies of {expected_prompt_tokens}"
            )
        row_summaries.append(
            {
                "benchmark_request_id": benchmark_id,
                "callsite_records": views,
            }
        )
    return {
        "record_count": len(records),
        "fallback_pre_conv_rank0_layer0_records": len(callsite_records),
        "rows": row_summaries,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm-root", type=Path, required=True)
    parser.add_argument("--expected-dose-rows", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    errors: list[str] = []
    bench_path = args.arm_root / "data" / "bench.json"
    if not bench_path.is_file():
        errors.append(f"missing benchmark evidence: {bench_path}")
        bench_rows: list[dict[str, Any]] = []
    else:
        bench = load_json(bench_path)
        bench_rows = list(bench.get("rows") or [])
    if len(bench_rows) != args.expected_dose_rows:
        errors.append(
            f"benchmark row count {len(bench_rows)}, expected {args.expected_dose_rows}"
        )
    if any(int(row.get("cached_tokens") or 0) != 0 for row in bench_rows):
        errors.append("benchmark contains nonzero cached prompt tokens")

    d1_records = load_jsonl(args.arm_root / "gdn-state-slot-trace.jsonl", errors)
    d2_records = load_jsonl(args.arm_root / "gdn-initstate-audit.jsonl", errors)
    d1 = validate_d1(d1_records, bench_rows, errors)
    d2 = validate_d2(d2_records, bench_rows, errors)

    result = {
        "schema_version": 1,
        "status": "passed" if not errors else "failed",
        "arm_root": str(args.arm_root),
        "expected_dose_rows": args.expected_dose_rows,
        "benchmark_rows": len(bench_rows),
        "errors": errors,
        "d1": d1,
        "d2": d2,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps({"status": result["status"], "errors": errors}))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
