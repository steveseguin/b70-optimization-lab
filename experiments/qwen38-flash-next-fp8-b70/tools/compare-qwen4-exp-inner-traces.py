#!/usr/bin/env python3
"""Compare two ordered Qwen4Exp inner traces without hiding schema drift."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def load_trace(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        trace = json.load(handle)
    if not isinstance(trace, dict):
        raise ValueError(f"{path}: root must be an object")
    if not isinstance(trace.get("records"), list):
        raise ValueError(f"{path}: records must be a list")
    return trace


def flatten(trace: dict[str, Any], path: Path) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    for record_index, record in enumerate(trace["records"]):
        if not isinstance(record, dict):
            raise ValueError(f"{path}: record {record_index} must be an object")
        label = record.get("label")
        tensors = record.get("tensors")
        if not isinstance(label, str) or not isinstance(tensors, dict):
            raise ValueError(f"{path}: malformed record {record_index}")
        for tensor_name in sorted(tensors):
            tensor = tensors[tensor_name]
            if not isinstance(tensor, dict):
                raise ValueError(
                    f"{path}: tensor {record_index}/{tensor_name} must be an object"
                )
            required = {"dtype", "shape", "numel", "sha256"}
            missing = sorted(required.difference(tensor))
            if missing:
                raise ValueError(
                    f"{path}: tensor {record_index}/{tensor_name} missing {missing}"
                )
            flattened.append(
                {
                    "record_index": record_index,
                    "label": label,
                    "tensor_name": tensor_name,
                    "dtype": tensor["dtype"],
                    "shape": tensor["shape"],
                    "numel": tensor["numel"],
                    "sha256": tensor["sha256"],
                }
            )
    return flattened


def compare(left_path: Path, right_path: Path) -> dict[str, Any]:
    left = load_trace(left_path)
    right = load_trace(right_path)
    left_flat = flatten(left, left_path)
    right_flat = flatten(right, right_path)
    header_fields = (
        "schema_version",
        "rank",
        "min_position_gate",
        "position_min",
        "position_max",
    )
    header_mismatches = {
        field: {"left": left.get(field), "right": right.get(field)}
        for field in header_fields
        if left.get(field) != right.get(field)
    }
    result: dict[str, Any] = {
        "schema_version": 1,
        "left": str(left_path),
        "right": str(right_path),
        "left_trace": {
            "rank": left.get("rank"),
            "position_min": left.get("position_min"),
            "position_max": left.get("position_max"),
            "record_count": len(left["records"]),
            "tensor_count": len(left_flat),
        },
        "right_trace": {
            "rank": right.get("rank"),
            "position_min": right.get("position_min"),
            "position_max": right.get("position_max"),
            "record_count": len(right["records"]),
            "tensor_count": len(right_flat),
        },
        "header_mismatches": header_mismatches,
    }
    if header_mismatches:
        result.update(status="schema_mismatch", matching_tensor_prefix=0)
        return result
    if len(left["records"]) != len(right["records"]):
        result.update(
            status="schema_mismatch",
            matching_tensor_prefix=0,
            reason="record_count",
        )
        return result
    if len(left_flat) != len(right_flat):
        result.update(
            status="schema_mismatch",
            matching_tensor_prefix=0,
            reason="tensor_count",
        )
        return result

    schema_fields = ("record_index", "label", "tensor_name", "dtype", "shape", "numel")
    for index, (left_item, right_item) in enumerate(zip(left_flat, right_flat)):
        schema_diff = {
            field: {"left": left_item[field], "right": right_item[field]}
            for field in schema_fields
            if left_item[field] != right_item[field]
        }
        if schema_diff:
            result.update(
                status="schema_mismatch",
                matching_tensor_prefix=index,
                first_mismatch={"schema": schema_diff},
            )
            return result
        if left_item["sha256"] != right_item["sha256"]:
            result.update(
                status="digest_mismatch",
                matching_tensor_prefix=index,
                first_mismatch={
                    "record_index": left_item["record_index"],
                    "label": left_item["label"],
                    "tensor_name": left_item["tensor_name"],
                    "dtype": left_item["dtype"],
                    "shape": left_item["shape"],
                    "numel": left_item["numel"],
                    "left_sha256": left_item["sha256"],
                    "right_sha256": right_item["sha256"],
                },
            )
            return result

    result.update(status="identical", matching_tensor_prefix=len(left_flat))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("left", type=Path)
    parser.add_argument("right", type=Path)
    parser.add_argument("--require-records", type=int)
    parser.add_argument("--require-tensors", type=int)
    args = parser.parse_args()

    try:
        result = compare(args.left, args.right)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(
            json.dumps({"schema_version": 1, "status": "invalid", "error": str(error)})
        )
        return 2

    requirements = {}
    for side in ("left_trace", "right_trace"):
        if (
            args.require_records is not None
            and result[side]["record_count"] != args.require_records
        ):
            requirements[f"{side}.record_count"] = result[side]["record_count"]
        if (
            args.require_tensors is not None
            and result[side]["tensor_count"] != args.require_tensors
        ):
            requirements[f"{side}.tensor_count"] = result[side]["tensor_count"]
    if requirements:
        result["status"] = "requirement_mismatch"
        result["requirement_mismatches"] = requirements

    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if result["status"] == "identical" else 1


if __name__ == "__main__":
    raise SystemExit(main())
