#!/usr/bin/env python3
"""Summarize the bounded c1 reordered-Q8 unitrace window."""

import argparse
import csv
import json
import re
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace-dir", type=Path, required=True)
    parser.add_argument("--kernel", required=True)
    parser.add_argument("--expected-decode-cycles", type=int, required=True)
    parser.add_argument("--baseline-token-ns", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    timing_files = sorted(args.trace_dir.rglob("device_timing.txt"))
    submission_files = sorted(args.trace_dir.rglob("device_submission.txt"))
    rows = []
    properties = []
    submission_rows = []
    total_device_ns = 0
    ncols_seen = False
    for path in timing_files:
        text = path.read_text(errors="replace")
        ncols_seen |= "_ncols" in text
        totals = re.findall(r"Total Device Time for L0 backend \(ns\):\s*(\d+)", text)
        total_device_ns += sum(map(int, totals))
        for line in text.splitlines():
            if args.kernel not in line:
                continue
            fields = next(csv.reader([line], skipinitialspace=True))
            fields = [field.strip() for field in fields]
            if len(fields) == 7 and fields[1].isdigit() and fields[2].isdigit():
                rows.append(
                    {
                        "file": str(path),
                        "kernel": fields[0],
                        "calls": int(fields[1]),
                        "device_time_ns": int(fields[2]),
                        "time_percent": float(fields[3]),
                        "average_ns": int(fields[4]),
                        "min_ns": int(fields[5]),
                        "max_ns": int(fields[6]),
                    }
                )
            elif len(fields) == 8 and fields[2].isdigit():
                register_size = None if fields[7] == "unknown" else int(fields[7])
                properties.append(
                    {
                        "file": str(path),
                        "kernel": fields[0],
                        "compiled": fields[1],
                        "simd": int(fields[2]),
                        "argument_count": int(fields[3]),
                        "slm_per_work_group": int(fields[4]),
                        "private_memory_per_thread": int(fields[5]),
                        "spill_memory_per_thread": int(fields[6]),
                        "register_file_size_per_thread": register_size,
                    }
                )
    for path in submission_files:
        text = path.read_text(errors="replace")
        ncols_seen |= "_ncols" in text
        for line in text.splitlines():
            if args.kernel not in line:
                continue
            fields = [
                field.strip()
                for field in next(csv.reader([line], skipinitialspace=True))
            ]
            if (
                len(fields) == 8
                and fields[1].isdigit()
                and fields[2].isdigit()
                and fields[4].isdigit()
                and fields[6].isdigit()
            ):
                submission_rows.append(
                    {
                        "file": str(path),
                        "kernel": fields[0],
                        "calls": int(fields[1]),
                        "append_ns": int(fields[2]),
                        "append_percent": float(fields[3]),
                        "submit_ns": int(fields[4]),
                        "submit_percent": float(fields[5]),
                        "execute_ns": int(fields[6]),
                        "execute_percent": float(fields[7]),
                    }
                )
    calls = sum(row["calls"] for row in rows)
    kernel_device_ns = sum(row["device_time_ns"] for row in rows)
    submission_lines = sum(
        len(path.read_text(errors="replace").splitlines()) for path in submission_files
    )
    nominal_window_ns = args.expected_decode_cycles * args.baseline_token_ns
    nominal_hotspot_share = (
        kernel_device_ns / nominal_window_ns if nominal_window_ns else 0
    )
    submission_append_ns = sum(row["append_ns"] for row in submission_rows)
    submission_submit_ns = sum(row["submit_ns"] for row in submission_rows)
    submission_execute_ns = sum(row["execute_ns"] for row in submission_rows)
    zero_spill = bool(properties) and all(
        row["spill_memory_per_thread"] == 0 for row in properties
    )
    checks = {
        "device_timing_present": bool(timing_files),
        "kernel_submission_present": bool(submission_files),
        "kernel_submission_nonempty": submission_lines > 0 and bool(submission_rows),
        "exact_c1_kernel_present": bool(rows) and calls > 0,
        "verbose_kernel_properties_present": bool(properties),
        "ncols_variant_absent": not ncols_seen,
        "device_time_positive": kernel_device_ns > 0,
        "kernel_time_within_filtered_total": 0 < kernel_device_ns <= total_device_ns,
    }
    result = {
        "evidence_class": "profiler-only",
        "performance_promotable": False,
        "kernel": args.kernel,
        "device_timing_files": [str(path) for path in timing_files],
        "kernel_submission_files": [str(path) for path in submission_files],
        "kernel_submission_line_count": submission_lines,
        "kernel_submission_rows": submission_rows,
        "submission_append_ns": submission_append_ns,
        "submission_submit_ns": submission_submit_ns,
        "submission_execute_ns": submission_execute_ns,
        "kernel_rows": rows,
        "kernel_properties": properties,
        "kernel_calls": calls,
        "kernel_device_time_ns": kernel_device_ns,
        "total_filtered_device_time_ns": total_device_ns,
        "expected_decode_cycles": args.expected_decode_cycles,
        "baseline_token_ns": args.baseline_token_ns,
        "nominal_window_ns": nominal_window_ns,
        "nominal_hotspot_share": nominal_hotspot_share,
        "calls_per_nominal_decode_cycle": calls / args.expected_decode_cycles,
        "zero_spill": zero_spill,
        "capture_window_note": "resume at task-0 decoded 100; pause+stop at 150; nominally 50 cycles",
        "checks": checks,
        "passed": all(checks.values()),
    }
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
