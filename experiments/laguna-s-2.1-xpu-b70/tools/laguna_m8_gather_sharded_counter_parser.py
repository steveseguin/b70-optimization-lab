#!/usr/bin/env python3
"""Fail-closed, CPU-only reader for paused-session Phase-B evidence."""
from __future__ import annotations

import csv
import hashlib
import math
import os
import re
import stat
from pathlib import Path
from statistics import fmean
from typing import Any

RAW_CYCLES, LAYERS = 13, 47
RAW_ROWS, DISCARDED_CYCLES = RAW_CYCLES * LAYERS, 2
RETAINED_ROWS = (RAW_CYCLES - DISCARDED_CYCLES) * LAYERS
ARMS = {"A1": "control", "B1": "candidate", "B2": "candidate", "A2": "control"}
KERNELS = {
    "control": "vllm::moe::MoeGather<sycl::_V1::ext::oneapi::bfloat16, 10, 8>[SIMD32 {8; 1; 1} {256; 1; 1}]",
    "candidate": "vllm::moe::LagunaM8MoeGatherSharded[SIMD32 {48; 1; 1} {64; 1; 1}]",
}
GEOMETRY = {
    "control": {"workgroups": 8, "simd32_subgroups": 64, "global": 8, "local": 256, "kernel_arguments": 5},
    "candidate": {"workgroups": 48, "simd32_subgroups": 96, "global": 48, "local": 64, "kernel_arguments": 3},
}
TIMING_FIELDS = ("Kernel", "Calls", "Time (ns)", "Time (%)", "Average (ns)", "Min (ns)", "Max (ns)")
PROPERTY_FIELDS = ("Kernel", "Compiled", "SIMD", "Number of Arguments", "SLM Per Work Group", "Private Memory Per Thread", "Spill Memory Per Thread", "Register File Size Per Thread")
METRIC_FIELDS = tuple("""Kernel
GlobalInstanceId
SubDeviceId
GpuTime[ns]
GpuCoreClocks[cycles]
AvgGpuCoreFrequencyMHz[MHz]
ResultUncertainty[%]
GPU_BUSY[%]
IA_VERTEX[events]
GPGPU_THREADGROUP_COUNT[events]
ASYNC_GPGPU_THREADGROUP_COUNT[events]
RASTERIZER_SAMPLE_OUTPUT[events]
ICACHE_HIT[events]
ICACHE_MISS[events]
XVE_ACTIVE[%]
XVE_INST_EXECUTED_ALU0_ALL[events]
XVE_INST_EXECUTED_ALU1_ALL[events]
XVE_INST_EXECUTED_SEND_ALL[events]
XVE_INST_ISSUED_ALL[events]
XVE_SHARED_FUNCTION_ACCESS_HOLD[%]
XVE_STALL[%]
XVE_THREADS_OCCUPANCY_ALL[%]
XVE_INST_EXECUTED_ALU2_ALL[events]
XVE_MULTIPLE_PIPE_ACTIVE[%]
LOAD_STORE_CACHE_PARTIAL_WRITE_COUNT[events]
SLM_BANK_CONFLICT_COUNT[events]
SLM_BYTE_READ[bytes]
SLM_BYTE_WRITE[bytes]
LOAD_STORE_CACHE_BYTE_READ[bytes]
LOAD_STORE_CACHE_BYTE_WRITE[bytes]
LOAD_STORE_CACHE_ACCESS[events]
LOAD_STORE_CACHE_HIT[events]
L3_ATOMIC_ACCESS[events]
L3_HIT[events]
L3_MISS[events]
L3_READ[events]
L3_WRITE[events]
L3_STALL[%]
COMPRESSOR_INPUT[events]
COMPRESSOR_OUTPUT[events]
GPU_MEMORY_BYTE_READ[bytes]
GPU_MEMORY_BYTE_WRITE[bytes]
GPU_MEMORY_BYTE_READ_RATE[GBpS]
GPU_MEMORY_BYTE_WRITE_RATE[GBpS]
GPU_MEMORY_L3_READ[events]
GPU_MEMORY_L3_WRITE[events]
GPU_MEMORY_REQUEST_QUEUE_FULL[%]
TLB_MISS[events]
ASYNC_GPGPU_THREAD_EXIT_COUNT[messages]
GPGPU_DISPATCH[%]
COMMAND_PARSER_COMPUTE_ENGINE_BUSY[%]
COMMAND_PARSER_COMPUTE_ENGINE_DISPATCH_KERNEL_COUNT[events]
COMMAND_PARSER_COPY_ENGINE_BUSY[%]
COMMAND_PARSER_FLUSH_COUNT[events]
COMMAND_PARSER_RENDER_ENGINE_BUSY[%]
COMMAND_PARSER_RENDER_ENGINE_DISPATCH_KERNEL_COUNT[events]
XVE_PIPE_ALU0_AND_ALU1_ACTIVE[%]
XVE_PIPE_ALU0_AND_ALU2_ACTIVE[%]
XVE_INST_EXECUTED_ALU0_ALL_UTILIZATION[%]
XVE_INST_EXECUTED_ALU1_ALL_UTILIZATION[%]
XVE_INST_EXECUTED_ALU2_ALL_UTILIZATION[%]
HOST_TO_GPUMEM_TRANSACTION_READ[events]
HOST_TO_GPUMEM_TRANSACTION_WRITE[events]
SYSMEM_TRANSACTION_READ[events]
SYSMEM_TRANSACTION_WRITE[events]
QueryBeginTime[ns]
CoreFrequencyMHz[MHz]
CoreFrequencyChanged
QuerySplitOccurred
ReportId
ReportsCount
OverrunOccured
MidQueryTimer
MidQueryProgramming
MidQueryMarker
MidQueryCtxSwitch
MidQueryC6
MidQueryFreqChange
MidQueryMmioTrigger
ReportError
ReportLost
ReportInconsistent
ReportCtxSwitchLost
ReportWithoutWorkload
ReportContextMismatch
ReportQueryModeMismatch""".splitlines())
METRIC_HEADER_SHA256 = "2f1add0fd583d68e3f9dfe9cd34577f25de4aff28e0a2c203ccaab1c567ce438"
BYTE_FIELDS = ("GPU_MEMORY_BYTE_READ[bytes]", "GPU_MEMORY_BYTE_WRITE[bytes]", "LOAD_STORE_CACHE_BYTE_READ[bytes]", "LOAD_STORE_CACHE_BYTE_WRITE[bytes]")
PERCENT_FIELDS = ("XVE_ACTIVE[%]", "XVE_THREADS_OCCUPANCY_ALL[%]", "XVE_STALL[%]")
MEAN_FIELDS = BYTE_FIELDS + PERCENT_FIELDS
ZERO_INVALIDITY_FIELDS = ("ResultUncertainty[%]", "QuerySplitOccurred", "OverrunOccured", "MidQueryTimer", "MidQueryProgramming", "MidQueryMarker", "MidQueryCtxSwitch", "MidQueryC6", "MidQueryFreqChange", "MidQueryMmioTrigger", "ReportError", "ReportLost", "ReportInconsistent", "ReportCtxSwitchLost", "ReportWithoutWorkload", "ReportContextMismatch", "ReportQueryModeMismatch")

def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)

def _file_bytes(path: Path, maximum: int = 512 * 1024 * 1024) -> bytes:
    descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        before = os.fstat(descriptor)
        require(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= maximum, f"{path}: unsafe retained profiler file")
        raw = bytearray()
        while len(raw) < before.st_size:
            block = os.read(descriptor, min(1024 * 1024, before.st_size - len(raw)))
            require(bool(block), f"{path}: short retained profiler read")
            raw.extend(block)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_mode) == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_mode), f"{path}: profiler file changed during retained read")
    return bytes(raw)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(_file_bytes(path)).hexdigest()

def _integer(row: dict[str, str], field: str, path: Path) -> int:
    value = row.get(field, "").strip()
    require(re.fullmatch(r"[0-9]+", value) is not None, f"{path}: invalid decimal {field}")
    return int(value)

def _number(row: dict[str, str], field: str, path: Path) -> float:
    try:
        value = float(row[field])
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError(f"{path}: invalid numeric {field}") from exc
    require(math.isfinite(value), f"{path}: nonfinite {field}")
    return value

def _rows(lines: list[str], path: Path, expected: tuple[str, ...], label: str) -> list[dict[str, str]]:
    stripped = [line.strip() for line in lines if line.strip()]
    starts = [i for i, line in enumerate(stripped) if line.startswith("Kernel,")]
    require(len(starts) == 1, f"{path}: {label} must contain one CSV header")
    reader = csv.DictReader(stripped[starts[0]:], skipinitialspace=True)
    require(tuple(reader.fieldnames or ()) == expected, f"{path}: {label} header/schema drift")
    result = list(reader)
    require(bool(result) and all(row and None not in row and row.get("Kernel", "").strip() for row in result), f"{path}: malformed {label} row")
    return result

def _section(text: str, path: Path, start: str, end: str | None, expected: tuple[str, ...], label: str) -> list[dict[str, str]]:
    require(text.count(start) == 1, f"{path}: missing/duplicate {start}")
    part = text.split(start, 1)[1]
    if end is not None:
        require(part.count(end) == 1, f"{path}: missing/duplicate {end}")
        part = part.split(end, 1)[0]
    return _rows(part.splitlines(), path, expected, label)

def parse_timing(path: Path, arm: str) -> dict[str, Any]:
    require(arm in ARMS, "unknown arm")
    treatment, kernel = ARMS[arm], KERNELS[ARMS[arm]]
    raw = _file_bytes(path, 16 * 1024 * 1024)
    text = raw.decode("utf-8", "strict")
    rows = _section(text, path, "=== Device Timing Summary ===", "=== Kernel Properties ===", TIMING_FIELDS, "timing")
    props = _section(text, path, "=== Kernel Properties ===", None, PROPERTY_FIELDS, "properties")
    require(len(rows) == len(props) == 1 and rows[0]["Kernel"].strip() == kernel and props[0]["Kernel"].strip() == kernel, f"{path}: temporal capture requires exactly one gather timing/property row")
    row, prop = rows[0], props[0]
    calls, total = _integer(row, "Calls", path), _integer(row, "Time (ns)", path)
    avg, lo, hi = (_integer(row, field, path) for field in ("Average (ns)", "Min (ns)", "Max (ns)"))
    pct = _number(row, "Time (%)", path)
    device_totals = re.findall(r"Total Device Time for L0 backend \(ns\):\s*([0-9]+)", text)
    require(device_totals == [str(total)], f"{path}: L0 device-time summary does not close to selected row")
    require(calls == RAW_ROWS and total > 0 and lo > 0 and lo <= avg <= hi and avg == total // calls and calls * lo <= total <= calls * hi and pct == 100.0, f"{path}: selected timing arithmetic/calls/percent drift")
    registers = _integer(prop, "Register File Size Per Thread", path)
    require(prop["Compiled"].strip() == "AOT" and _integer(prop, "SIMD", path) == 32 and _integer(prop, "Number of Arguments", path) == GEOMETRY[treatment]["kernel_arguments"] and _integer(prop, "SLM Per Work Group", path) == 0 and _integer(prop, "Private Memory Per Thread", path) == 0 and _integer(prop, "Spill Memory Per Thread", path) == 0 and 32 <= registers <= 1024 and registers % 32 == 0 and registers & (registers - 1) == 0, f"{path}: exact AOT/SIMD32/argument/SLM/private/spill or sane register property drift")
    return {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(), "kernel": kernel, "calls": calls, "time_ns": total, "time_percent": pct, "geometry": GEOMETRY[treatment], "properties": {field: prop[field] for field in PROPERTY_FIELDS}}

def parse_metrics(path: Path, arm: str) -> dict[str, Any]:
    require(arm in ARMS and len(METRIC_FIELDS) == 86 and hashlib.sha256(",".join(METRIC_FIELDS).encode()).hexdigest() == METRIC_HEADER_SHA256, "frozen metric contract drift")
    raw = _file_bytes(path)
    rows = _rows(raw.decode("utf-8", "strict").splitlines(), path, METRIC_FIELDS, "metrics")
    kernel, geometry = KERNELS[ARMS[arm]], GEOMETRY[ARMS[arm]]
    require(len(rows) == RAW_ROWS and all(x["Kernel"].strip() == kernel for x in rows), f"{path}: expected exactly 611 selected gather rows")
    indexed: list[tuple[int, dict[str, str]]] = []
    for row in rows:
        gid = _integer(row, "GlobalInstanceId", path)
        require(_integer(row, "SubDeviceId", path) == 0 and _integer(row, "ReportsCount", path) == 1 and _integer(row, "GpuTime[ns]", path) > 0, f"{path}: device/report/GpuTime drift")
        require(_integer(row, "ASYNC_GPGPU_THREADGROUP_COUNT[events]", path) == geometry["workgroups"] and _integer(row, "ASYNC_GPGPU_THREAD_EXIT_COUNT[messages]", path) == geometry["simd32_subgroups"], f"{path}: async workgroup/SIMD subgroup geometry drift")
        require(_integer(row, "COMMAND_PARSER_COMPUTE_ENGINE_DISPATCH_KERNEL_COUNT[events]", path) == 1 and 0.0 < _number(row, "GPGPU_DISPATCH[%]", path) <= 100.0, f"{path}: exact dispatch count/activity drift")
        for field in ZERO_INVALIDITY_FIELDS:
            require(_number(row, field, path) == 0.0, f"{path}: invalid profiler report {field}")
        for field in MEAN_FIELDS:
            n = _number(row, field, path)
            require(n >= 0.0 and (field not in PERCENT_FIELDS or n <= 100.0), f"{path}: metric range drift {field}")
        indexed.append((gid, row))
    indexed.sort(key=lambda x: x[0])
    gids = [x[0] for x in indexed]
    require(len(set(gids)) == RAW_ROWS, f"{path}: duplicate GlobalInstanceId")
    require(gids == list(range(gids[0], gids[0] + RAW_ROWS)), f"{path}: temporal capture GIDs must be 611 consecutive dispatches")
    chunks = [indexed[i * LAYERS:(i + 1) * LAYERS] for i in range(RAW_CYCLES)]
    retained = [row for chunk in chunks[DISCARDED_CYCLES:] for _gid, row in chunk]
    cycle_sums = [{field: sum(_number(row, field, path) for _gid, row in chunk) for field in BYTE_FIELDS} for chunk in chunks[DISCARDED_CYCLES:]]
    means = {field: fmean(x[field] for x in cycle_sums) for field in BYTE_FIELDS}
    means.update({field: fmean(_number(row, field, path) for row in retained) for field in PERCENT_FIELDS})
    return {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(), "kernel": kernel, "raw_rows": RAW_ROWS, "discarded_cycles": [0, 1], "retained_rows": RETAINED_ROWS, "global_instance_ids_sorted": gids, "cycle_global_instance_ids": [[x[0] for x in chunk] for chunk in chunks], "byte_aggregation": "cycle_sum_then_mean", "percentage_aggregation": "row_mean", "means": means}

def compare(control: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    cm, bm = control["means"], candidate["means"]
    def within(field: str) -> bool:
        return bm[field] == 0.0 if cm[field] == 0.0 else bm[field] <= cm[field] * 1.02
    out = {"gpu_memory_read_within_102pct": within(BYTE_FIELDS[0]), "gpu_memory_write_within_102pct": within(BYTE_FIELDS[1]), "lsc_read_within_102pct": within(BYTE_FIELDS[2]), "lsc_write_within_102pct": within(BYTE_FIELDS[3]), "xve_active_decline_pp": cm[PERCENT_FIELDS[0]] - bm[PERCENT_FIELDS[0]], "thread_occupancy_decline_pp": cm[PERCENT_FIELDS[1]] - bm[PERCENT_FIELDS[1]], "xve_stall_increase_pp": bm[PERCENT_FIELDS[2]] - cm[PERCENT_FIELDS[2]]}
    for name, fields in (("gpu_memory_total", BYTE_FIELDS[:2]), ("lsc_total", BYTE_FIELDS[2:])):
        base, proposed = sum(cm[x] for x in fields), sum(bm[x] for x in fields)
        out[f"{name}_within_102pct"] = proposed == 0.0 if base == 0.0 else proposed <= base * 1.02
    out["xve_active_within_0_5pp"] = out["xve_active_decline_pp"] <= 0.5
    out["thread_occupancy_within_0_5pp"] = out["thread_occupancy_decline_pp"] <= 0.5
    out["xve_stall_within_0_5pp"] = out["xve_stall_increase_pp"] <= 0.5
    out["passed"] = all(value is True for key, value in out.items() if key.endswith("pct") or key.endswith("0_5pp"))
    return out
