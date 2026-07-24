#!/usr/bin/env python3
"""CPU-only, fail-closed parser for Laguna gate+up unitrace evidence.

This module intentionally has no profiler, XPU, subprocess, or artifact-writing
path.  A future runner can import these validators only after its separately
authorized capture has been sealed.
"""

from __future__ import annotations

import csv
import hashlib
import math
import re
from pathlib import Path
from statistics import fmean
from typing import Any


RAW_PAIR_COUNT = 13
DISCARDED_PAIR_INDEXES = (0, 1)
ANALYZED_PAIR_COUNT = RAW_PAIR_COUNT - len(DISCARDED_PAIR_INDEXES)
RAW_GEMM_SAMPLE_COUNT = RAW_PAIR_COUNT * 2
ANALYZED_GEMM_SAMPLE_COUNT = ANALYZED_PAIR_COUNT * 2
TIME_PERCENT_ABSOLUTE_TOLERANCE = 0.000005
KERNEL_PATTERN = re.compile(
    r"^gemm_kernel\[SIMD16 "
    r"\{[1-9][0-9]*; [1-9][0-9]*; [1-9][0-9]*\} "
    r"\{[1-9][0-9]*; [1-9][0-9]*; [1-9][0-9]*\}\]$"
)

TIMING_FIELDS = (
    "Kernel",
    "Calls",
    "Time (ns)",
    "Time (%)",
    "Average (ns)",
    "Min (ns)",
    "Max (ns)",
)
PROPERTY_FIELDS = (
    "Kernel",
    "Compiled",
    "SIMD",
    "Number of Arguments",
    "SLM Per Work Group",
    "Private Memory Per Thread",
    "Spill Memory Per Thread",
    "Register File Size Per Thread",
)
# The timing summary is not filtered as narrowly as metric-query by unitrace.
AUXILIARY_TIMING_CALLS = {
    "zeCommandListAppendMemoryCopy(D2M)[1572864]": 2,
    "zeCommandListAppendMemoryCopy(M2D)[1572864]": 2,
    "zeCommandListAppendMemoryCopy(D2M)[49152]": 1,
    "zeCommandListAppendMemoryCopy(D2M)[4096]": 26,
    "zeCommandListAppendMemoryCopy(M2D)[49152]": 1,
}

MEAN_FIELDS = (
    "GpuTime[ns]",
    "XVE_ACTIVE[%]",
    "XVE_STALL[%]",
    "XVE_THREADS_OCCUPANCY_ALL[%]",
    "GPU_MEMORY_BYTE_READ[bytes]",
    "GPU_MEMORY_BYTE_WRITE[bytes]",
    "GPU_MEMORY_BYTE_READ_RATE[GBpS]",
    "GPU_MEMORY_BYTE_WRITE_RATE[GBpS]",
    "LOAD_STORE_CACHE_BYTE_READ[bytes]",
    "LOAD_STORE_CACHE_BYTE_WRITE[bytes]",
    "LOAD_STORE_CACHE_PARTIAL_WRITE_COUNT[events]",
    "SLM_BANK_CONFLICT_COUNT[events]",
    "SLM_BYTE_READ[bytes]",
    "SLM_BYTE_WRITE[bytes]",
    "ASYNC_GPGPU_THREADGROUP_COUNT[events]",
    "ASYNC_GPGPU_THREAD_EXIT_COUNT[messages]",
)
POSITIVE_FIELDS = (
    "GpuTime[ns]",
    "GPU_MEMORY_BYTE_READ[bytes]",
    "LOAD_STORE_CACHE_BYTE_READ[bytes]",
    "ASYNC_GPGPU_THREADGROUP_COUNT[events]",
    "ASYNC_GPGPU_THREAD_EXIT_COUNT[messages]",
)
PERCENT_FIELDS = ("XVE_ACTIVE[%]", "XVE_STALL[%]", "XVE_THREADS_OCCUPANCY_ALL[%]")
ZERO_VALIDITY_FIELDS = (
    "ResultUncertainty[%]",
    "QuerySplitOccurred",
    "OverrunOccured",
    "MidQueryTimer",
    "MidQueryProgramming",
    "MidQueryMarker",
    "MidQueryCtxSwitch",
    "MidQueryC6",
    "MidQueryFreqChange",
    "MidQueryMmioTrigger",
    "ReportError",
    "ReportLost",
    "ReportInconsistent",
    "ReportCtxSwitchLost",
    "ReportWithoutWorkload",
    "ReportContextMismatch",
    "ReportQueryModeMismatch",
)
ZERO_TRAFFIC_FIELDS = (
    "LOAD_STORE_CACHE_BYTE_WRITE[bytes]",
    "LOAD_STORE_CACHE_PARTIAL_WRITE_COUNT[events]",
    "SLM_BANK_CONFLICT_COUNT[events]",
    "SLM_BYTE_READ[bytes]",
    "SLM_BYTE_WRITE[bytes]",
)
# Exact ComputeBasic emitter header from the sealed shared-down capture.  Do
# not reduce this to fields consumed by the guardrails: header drift itself is
# evidence drift.
METRIC_FIELDS = (
    "Kernel",
    "GlobalInstanceId",
    "SubDeviceId",
    "GpuTime[ns]",
    "GpuCoreClocks[cycles]",
    "AvgGpuCoreFrequencyMHz[MHz]",
    "ResultUncertainty[%]",
    "GPU_BUSY[%]",
    "IA_VERTEX[events]",
    "GPGPU_THREADGROUP_COUNT[events]",
    "ASYNC_GPGPU_THREADGROUP_COUNT[events]",
    "RASTERIZER_SAMPLE_OUTPUT[events]",
    "ICACHE_HIT[events]",
    "ICACHE_MISS[events]",
    "XVE_ACTIVE[%]",
    "XVE_INST_EXECUTED_ALU0_ALL[events]",
    "XVE_INST_EXECUTED_ALU1_ALL[events]",
    "XVE_INST_EXECUTED_SEND_ALL[events]",
    "XVE_INST_ISSUED_ALL[events]",
    "XVE_SHARED_FUNCTION_ACCESS_HOLD[%]",
    "XVE_STALL[%]",
    "XVE_THREADS_OCCUPANCY_ALL[%]",
    "XVE_INST_EXECUTED_ALU2_ALL[events]",
    "XVE_MULTIPLE_PIPE_ACTIVE[%]",
    "LOAD_STORE_CACHE_PARTIAL_WRITE_COUNT[events]",
    "SLM_BANK_CONFLICT_COUNT[events]",
    "SLM_BYTE_READ[bytes]",
    "SLM_BYTE_WRITE[bytes]",
    "LOAD_STORE_CACHE_BYTE_READ[bytes]",
    "LOAD_STORE_CACHE_BYTE_WRITE[bytes]",
    "LOAD_STORE_CACHE_ACCESS[events]",
    "LOAD_STORE_CACHE_HIT[events]",
    "L3_ATOMIC_ACCESS[events]",
    "L3_HIT[events]",
    "L3_MISS[events]",
    "L3_READ[events]",
    "L3_WRITE[events]",
    "L3_STALL[%]",
    "COMPRESSOR_INPUT[events]",
    "COMPRESSOR_OUTPUT[events]",
    "GPU_MEMORY_BYTE_READ[bytes]",
    "GPU_MEMORY_BYTE_WRITE[bytes]",
    "GPU_MEMORY_BYTE_READ_RATE[GBpS]",
    "GPU_MEMORY_BYTE_WRITE_RATE[GBpS]",
    "GPU_MEMORY_L3_READ[events]",
    "GPU_MEMORY_L3_WRITE[events]",
    "GPU_MEMORY_REQUEST_QUEUE_FULL[%]",
    "TLB_MISS[events]",
    "ASYNC_GPGPU_THREAD_EXIT_COUNT[messages]",
    "GPGPU_DISPATCH[%]",
    "COMMAND_PARSER_COMPUTE_ENGINE_BUSY[%]",
    "COMMAND_PARSER_COMPUTE_ENGINE_DISPATCH_KERNEL_COUNT[events]",
    "COMMAND_PARSER_COPY_ENGINE_BUSY[%]",
    "COMMAND_PARSER_FLUSH_COUNT[events]",
    "COMMAND_PARSER_RENDER_ENGINE_BUSY[%]",
    "COMMAND_PARSER_RENDER_ENGINE_DISPATCH_KERNEL_COUNT[events]",
    "XVE_PIPE_ALU0_AND_ALU1_ACTIVE[%]",
    "XVE_PIPE_ALU0_AND_ALU2_ACTIVE[%]",
    "XVE_INST_EXECUTED_ALU0_ALL_UTILIZATION[%]",
    "XVE_INST_EXECUTED_ALU1_ALL_UTILIZATION[%]",
    "XVE_INST_EXECUTED_ALU2_ALL_UTILIZATION[%]",
    "HOST_TO_GPUMEM_TRANSACTION_READ[events]",
    "HOST_TO_GPUMEM_TRANSACTION_WRITE[events]",
    "SYSMEM_TRANSACTION_READ[events]",
    "SYSMEM_TRANSACTION_WRITE[events]",
    "QueryBeginTime[ns]",
    "CoreFrequencyMHz[MHz]",
    "CoreFrequencyChanged",
    "QuerySplitOccurred",
    "ReportId",
    "ReportsCount",
    "OverrunOccured",
    "MidQueryTimer",
    "MidQueryProgramming",
    "MidQueryMarker",
    "MidQueryCtxSwitch",
    "MidQueryC6",
    "MidQueryFreqChange",
    "MidQueryMmioTrigger",
    "ReportError",
    "ReportLost",
    "ReportInconsistent",
    "ReportCtxSwitchLost",
    "ReportWithoutWorkload",
    "ReportContextMismatch",
    "ReportQueryModeMismatch",
)
METRIC_HEADER_SHA256 = (
    "2f1add0fd583d68e3f9dfe9cd34577f25de4aff28e0a2c203ccaab1c567ce438"
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def integer(row: dict[str, str], field: str, path: Path) -> int:
    value = row.get(field)
    require(
        isinstance(value, str) and re.fullmatch(r"[0-9]+", value.strip()) is not None,
        f"{path}: {field} is not an emitter-form decimal integer",
    )
    return int(value)


def numeric(row: dict[str, str], field: str, path: Path) -> float:
    value = row.get(field)
    require(value is not None and value != "", f"{path}: missing {field}")
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise RuntimeError(f"{path}: nonnumeric {field}={value!r}") from error
    require(math.isfinite(number), f"{path}: nonfinite {field}")
    return number


def csv_rows(
    lines: list[str], path: Path, label: str, expected_fields: tuple[str, ...]
) -> list[dict[str, str]]:
    stripped = [line.strip() for line in lines if line.strip()]
    headers = [
        index for index, line in enumerate(stripped) if line.startswith("Kernel,")
    ]
    require(len(headers) == 1, f"{path}: {label} requires one CSV header")
    reader = csv.DictReader(stripped[headers[0] :], skipinitialspace=True)
    require(
        reader.fieldnames is not None and tuple(reader.fieldnames) == expected_fields,
        f"{path}: {label} CSV header/schema drift",
    )
    rows = list(reader)
    require(
        bool(rows)
        and all(
            row
            and None not in row
            and isinstance(row.get("Kernel"), str)
            and bool(row["Kernel"].strip())
            for row in rows
        ),
        f"{path}: {label} contains empty-kernel or surplus CSV records",
    )
    return rows


def parse_csv_section(
    text: str,
    *,
    path: Path,
    start: str,
    end: str | None,
    label: str,
    expected_fields: tuple[str, ...],
) -> list[dict[str, str]]:
    require(text.count(start) == 1, f"{path}: require one {start}")
    section = text.split(start, maxsplit=1)[1]
    if end is not None:
        require(section.count(end) == 1, f"{path}: require one {end} after {start}")
        section = section.split(end, maxsplit=1)[0]
    return csv_rows(section.splitlines(), path, label, expected_fields)


def _parse_timing_row(
    row: dict[str, str], *, path: Path, expected_calls: int
) -> dict[str, Any]:
    calls = integer(row, "Calls", path)
    time_ns = integer(row, "Time (ns)", path)
    average_ns = integer(row, "Average (ns)", path)
    minimum_ns = integer(row, "Min (ns)", path)
    maximum_ns = integer(row, "Max (ns)", path)
    percent = numeric(row, "Time (%)", path)
    require(calls == expected_calls, f"{path}: timing Calls drift for {row['Kernel']}")
    require(
        time_ns > 0
        and percent > 0
        and average_ns > 0
        and minimum_ns > 0
        and maximum_ns > 0
        and minimum_ns <= average_ns <= maximum_ns,
        f"{path}: invalid timing scalar/range for {row['Kernel']}",
    )
    require(
        average_ns == time_ns // calls
        and calls * minimum_ns <= time_ns <= calls * maximum_ns,
        f"{path}: timing aggregate inconsistent for {row['Kernel']}",
    )
    return {
        "kernel_name": row["Kernel"],
        "calls": calls,
        "time_ns": time_ns,
        "time_percent": percent,
        "average_ns": average_ns,
        "minimum_ns": minimum_ns,
        "maximum_ns": maximum_ns,
    }


def parse_timing_properties(path: Path, *, expected_kernel_name: str) -> dict[str, Any]:
    """Validate the exact six-row timing schema and one frozen GEMM property row."""
    text = path.read_text()
    timing_rows = parse_csv_section(
        text,
        path=path,
        start="=== Device Timing Summary ===",
        end="=== Kernel Properties ===",
        label="device timing",
        expected_fields=TIMING_FIELDS,
    )
    property_rows = parse_csv_section(
        text,
        path=path,
        start="=== Kernel Properties ===",
        end=None,
        label="kernel properties",
        expected_fields=PROPERTY_FIELDS,
    )
    by_name = {row["Kernel"]: row for row in timing_rows}
    expected_names = {expected_kernel_name, *AUXILIARY_TIMING_CALLS}
    require(
        len(timing_rows) == len(by_name) == 6 and set(by_name) == expected_names,
        f"{path}: timing rows are not the exact selected-GEMM plus copy set",
    )
    parsed = {
        name: _parse_timing_row(
            row,
            path=path,
            expected_calls=(
                RAW_GEMM_SAMPLE_COUNT
                if name == expected_kernel_name
                else AUXILIARY_TIMING_CALLS[name]
            ),
        )
        for name, row in by_name.items()
    }
    totals = re.findall(
        r"(?m)^\s*Total Device Time for L0 backend \(ns\):\s*([0-9]+)\s*$", text
    )
    require(len(totals) == 1, f"{path}: require one decimal L0 total-device-time field")
    total = int(totals[0])
    require(
        total == sum(row["time_ns"] for row in parsed.values()),
        f"{path}: timing row sum differs from reported L0 device time",
    )
    for row in parsed.values():
        require(
            math.isclose(
                row["time_percent"],
                row["time_ns"] * 100.0 / total,
                rel_tol=0.0,
                abs_tol=TIME_PERCENT_ABSOLUTE_TOLERANCE,
            ),
            f"{path}: timing percentage inconsistent for {row['kernel_name']}",
        )
    require(
        math.isclose(
            sum(row["time_percent"] for row in parsed.values()),
            100.0,
            rel_tol=0.0,
            abs_tol=TIME_PERCENT_ABSOLUTE_TOLERANCE,
        ),
        f"{path}: timing percentages do not sum to 100",
    )
    require(
        len(property_rows) == 1
        and property_rows[0].get("Kernel") == expected_kernel_name,
        f"{path}: properties must contain only the selected exact kernel",
    )
    properties = property_rows[0]
    require(
        properties.get("Compiled") == "AOT"
        and integer(properties, "SIMD", path) == 16
        and integer(properties, "Number of Arguments", path) == 15
        and integer(properties, "SLM Per Work Group", path) == 0
        and integer(properties, "Private Memory Per Thread", path) == 0
        and integer(properties, "Spill Memory Per Thread", path) == 0
        and integer(properties, "Register File Size Per Thread", path) == 256,
        f"{path}: selected GEMM property identity drift",
    )
    return {
        "path": str(path),
        "sha256": sha256_file(path),
        "kernel_name": expected_kernel_name,
        "calls": RAW_GEMM_SAMPLE_COUNT,
        "selected": parsed[expected_kernel_name],
        "reported_total_device_time_ns": total,
        "timing_row_order": [r["Kernel"] for r in timing_rows],
        "auxiliary_timing_rows": {
            name: parsed[name] for name in AUXILIARY_TIMING_CALLS
        },
    }


def parse_metrics(
    path: Path, *, expected_kernel_name: str | None = None
) -> dict[str, Any]:
    """Validate metric-query rows and retain ordered gate/up pairs 2..12 only."""
    require(
        hashlib.sha256(",".join(METRIC_FIELDS).encode()).hexdigest()
        == METRIC_HEADER_SHA256,
        f"{path}: frozen ComputeBasic metric header hash drift",
    )
    rows = csv_rows(path.read_text().splitlines(), path, "metric query", METRIC_FIELDS)
    require(
        len(rows) == RAW_GEMM_SAMPLE_COUNT,
        f"{path}: expected exactly {RAW_GEMM_SAMPLE_COUNT} selected metric rows",
    )
    kernel_names = {row["Kernel"] for row in rows}
    require(
        len(kernel_names) == 1,
        f"{path}: selected metric rows have multiple kernel identities",
    )
    observed_kernel_name = next(iter(kernel_names))
    require(
        KERNEL_PATTERN.fullmatch(observed_kernel_name) is not None,
        f"{path}: selected metric kernel is not verbose SIMD16 gemm_kernel",
    )
    if expected_kernel_name is not None:
        require(
            observed_kernel_name == expected_kernel_name,
            f"{path}: selected metric rows have kernel identity drift",
        )
    ids = [integer(row, "GlobalInstanceId", path) for row in rows]
    require(
        ids == sorted(ids) and len(set(ids)) == RAW_GEMM_SAMPLE_COUNT,
        f"{path}: GlobalInstanceId values are not strictly ordered and unique",
    )
    for row in rows:
        require(
            integer(row, "SubDeviceId", path) == 0,
            f"{path}: metric SubDeviceId must be zero",
        )
        require(
            integer(row, "ReportsCount", path) == 1,
            f"{path}: ReportsCount must equal one",
        )
        for field in ZERO_VALIDITY_FIELDS + ZERO_TRAFFIC_FIELDS:
            require(
                numeric(row, field, path) == 0.0,
                f"{path}: nonzero invalidity/traffic proxy {field}",
            )
        for field in MEAN_FIELDS:
            require(
                numeric(row, field, path) >= 0.0, f"{path}: negative metric {field}"
            )
        for field in POSITIVE_FIELDS:
            require(
                numeric(row, field, path) > 0.0, f"{path}: {field} must be positive"
            )
        for field in PERCENT_FIELDS:
            require(
                0.0 <= numeric(row, field, path) <= 100.0,
                f"{path}: percentage metric out of range",
            )
    pairs = [
        {
            "pair_index": index,
            "gate": rows[index * 2],
            "up": rows[index * 2 + 1],
            "gate_global_instance_id": ids[index * 2],
            "up_global_instance_id": ids[index * 2 + 1],
        }
        for index in range(RAW_PAIR_COUNT)
    ]
    require(
        all(
            pair["up_global_instance_id"] == pair["gate_global_instance_id"] + 1
            for pair in pairs
        ),
        f"{path}: gate/up queries are not consecutive within each selected pair",
    )
    require(
        all(
            pairs[index + 1]["gate_global_instance_id"]
            == pairs[index]["up_global_instance_id"] + 2
            for index in range(RAW_PAIR_COUNT - 1)
        ),
        f"{path}: selected pair query IDs do not contain exactly one eviction gap",
    )
    retained = pairs[len(DISCARDED_PAIR_INDEXES) :]
    require(
        len(retained) == ANALYZED_PAIR_COUNT
        and 2 * len(retained) == ANALYZED_GEMM_SAMPLE_COUNT,
        f"{path}: pair-aware retained metric sample count drift",
    )
    return {
        "path": str(path),
        "sha256": sha256_file(path),
        "kernel_name": observed_kernel_name,
        "global_instance_ids": ids,
        "raw_pairs": RAW_PAIR_COUNT,
        "discarded_pair_indexes": list(DISCARDED_PAIR_INDEXES),
        "analyzed_pairs": ANALYZED_PAIR_COUNT,
        "analyzed_gemm_samples": ANALYZED_GEMM_SAMPLE_COUNT,
        "pair_order": "row 2*i=gate, row 2*i+1=up",
        "retained_pairs": retained,
        "mean": {
            field: fmean(
                numeric(sample, field, path)
                for pair in retained
                for sample in (pair["gate"], pair["up"])
            )
            for field in MEAN_FIELDS
        },
    }
