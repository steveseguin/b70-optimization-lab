#!/usr/bin/env python3
"""Summarize shape-recorded Torch XPU traces without timing inference.

The report joins CPU operator shapes to device kernels through the profiler's
``External id`` field.  Device durations are reported exactly as recorded;
profiling overhead means they are diagnostic attribution, not latency claims.
"""

from __future__ import annotations

import argparse
import gzip
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def load_trace(path: Path) -> dict[str, Any]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def shape_key(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"))


def summarize(path: Path) -> dict[str, Any]:
    trace = load_trace(path)
    events = trace.get("traceEvents", [])
    cpu_by_external: dict[int, dict[str, Any]] = {}
    cpu_counts: dict[str, int] = defaultdict(int)

    for event in events:
        if event.get("ph") != "X" or event.get("cat") != "cpu_op":
            continue
        args = event.get("args", {})
        external_id = args.get("External id")
        name = event.get("name", "")
        cpu_counts[name] += 1
        if isinstance(external_id, int):
            cpu_by_external[external_id] = {
                "name": name,
                "input_dims": args.get("Input Dims", []),
                "input_types": args.get("Input type", []),
            }

    device: dict[tuple[str, str], dict[str, Any]] = {}
    for event in events:
        if event.get("ph") != "X" or event.get("cat") != "kernel":
            continue
        args = event.get("args", {})
        parent = cpu_by_external.get(args.get("External id"))
        if parent is None:
            continue
        parent_name = parent["name"]
        if parent_name not in {
            "_xpu_C::fp8_gemm_w8a16",
            "aten::mm",
            "c10d::allreduce_",
        }:
            continue
        key = (parent_name, shape_key(parent["input_dims"]))
        row = device.setdefault(
            key,
            {
                "operator": parent_name,
                "input_dims": parent["input_dims"],
                "input_types": parent["input_types"],
                "device_kernel_calls": 0,
                "device_duration_us": 0.0,
                "kernel_names": set(),
            },
        )
        row["device_kernel_calls"] += 1
        row["device_duration_us"] += float(event.get("dur", 0.0))
        row["kernel_names"].add(event.get("name", ""))

    rows = []
    for row in device.values():
        calls = row["device_kernel_calls"]
        total = row["device_duration_us"]
        row["device_duration_us"] = round(total, 6)
        row["device_average_us"] = round(total / calls, 6)
        row["kernel_names"] = sorted(row["kernel_names"])
        rows.append(row)
    rows.sort(key=lambda row: (-row["device_duration_us"], row["operator"]))

    return {
        "trace": str(path),
        "record_shapes": trace.get("record_shapes"),
        "vllm_version": trace.get("vllm_version"),
        "device": trace.get("deviceProperties", [{}])[0].get("name"),
        "selected_cpu_operator_counts": {
            name: cpu_counts.get(name, 0)
            for name in (
                "_xpu_C::fp8_gemm_w8a16",
                "vllm::all_reduce",
                "c10d::allreduce_",
                "aten::mm",
            )
        },
        "device_kernel_shape_rows": rows,
        "timing_warning": (
            "Device durations are profiler observations with profiler overhead; "
            "do not publish them as unprofiled latency or throughput."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("traces", nargs="+", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = {
        "schema": "neural.download.torch-xpu-shape-trace-summary.v1",
        "traces": [summarize(path) for path in args.traces],
    }
    rendered = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
