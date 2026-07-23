#!/usr/bin/env python3
"""Fail-closed offline analyzer for Laguna shared-down cold counters."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
from pathlib import Path
from statistics import fmean
from typing import Any

import run_laguna_shared_down_mm_counters as contract


RAW_QUERY_COUNT = 13
DISCARDED_QUERY_COUNT = 2
ANALYZED_QUERY_COUNT = RAW_QUERY_COUNT - DISCARDED_QUERY_COUNT
KERNEL_PATTERN = re.compile(
    r"^gemm_kernel\[SIMD16 "
    r"\{[1-9][0-9]*; [1-9][0-9]*; [1-9][0-9]*\} "
    r"\{[1-9][0-9]*; [1-9][0-9]*; [1-9][0-9]*\}\]$"
)
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
PERCENT_FIELDS = (
    "XVE_ACTIVE[%]",
    "XVE_STALL[%]",
    "XVE_THREADS_OCCUPANCY_ALL[%]",
)
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


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def numeric(row: dict[str, str], field: str, path: Path) -> float:
    value = row.get(field)
    require(value is not None and value != "", f"{path}: missing {field}")
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise RuntimeError(f"{path}: nonnumeric {field}={value!r}") from error
    require(math.isfinite(number), f"{path}: nonfinite {field}")
    return number


def integer(row: dict[str, str], field: str, path: Path) -> int:
    value = row.get(field)
    require(
        isinstance(value, str) and re.fullmatch(r"[0-9]+", value.strip()) is not None,
        f"{path}: {field} is not an emitter-form decimal integer",
    )
    return int(value)


def csv_rows(lines: list[str], path: Path, label: str) -> list[dict[str, str]]:
    stripped = [line.strip() for line in lines if line.strip()]
    headers = [
        index for index, line in enumerate(stripped) if line.startswith("Kernel,")
    ]
    require(len(headers) == 1, f"{path}: {label} requires one CSV header")
    reader = csv.DictReader(stripped[headers[0] :], skipinitialspace=True)
    rows = [row for row in reader if row and row.get("Kernel")]
    require(
        reader.fieldnames is not None
        and len(reader.fieldnames) == len(set(reader.fieldnames)),
        f"{path}: {label} has invalid/duplicate CSV fields",
    )
    require(
        all(None not in row for row in rows),
        f"{path}: {label} contains surplus CSV columns",
    )
    return rows


def metric_rows(path: Path) -> list[dict[str, str]]:
    rows = csv_rows(path.read_text().splitlines(), path, "metric query")
    require(
        len(rows) == RAW_QUERY_COUNT,
        f"{path}: expected exactly {RAW_QUERY_COUNT} selected metric rows",
    )
    names = {row["Kernel"] for row in rows}
    require(
        len(names) == 1 and KERNEL_PATTERN.fullmatch(next(iter(names))) is not None,
        f"{path}: selected kernel is not one exact verbose SIMD16 gemm_kernel",
    )
    return rows


def parse_metrics(path: Path) -> dict[str, Any]:
    rows = metric_rows(path)
    ids = [integer(row, "GlobalInstanceId", path) for row in rows]
    require(ids == sorted(ids), f"{path}: GlobalInstanceId values are not ordered")
    require(len(set(ids)) == RAW_QUERY_COUNT, f"{path}: duplicate query IDs")
    for row in rows:
        require(
            integer(row, "SubDeviceId", path) == 0,
            f"{path}: metric-query SubDeviceId must be zero",
        )
        require(
            integer(row, "ReportsCount", path) == 1,
            f"{path}: ReportsCount must equal one",
        )
        for field in ZERO_VALIDITY_FIELDS:
            require(
                numeric(row, field, path) == 0.0,
                f"{path}: nonzero validity proxy {field}",
            )
        for field in ZERO_TRAFFIC_FIELDS:
            require(
                numeric(row, field, path) == 0.0,
                f"{path}: nonzero spill/SLM/write proxy {field}",
            )
        for field in MEAN_FIELDS:
            value = numeric(row, field, path)
            require(value >= 0.0, f"{path}: negative metric {field}")
        for field in POSITIVE_FIELDS:
            require(
                numeric(row, field, path) > 0.0,
                f"{path}: {field} must be positive",
            )
        for field in PERCENT_FIELDS:
            value = numeric(row, field, path)
            require(
                0.0 <= value <= 100.0,
                f"{path}: percentage metric out of range: {field}",
            )
    analyzed = rows[DISCARDED_QUERY_COUNT:]
    require(
        len(analyzed) == ANALYZED_QUERY_COUNT,
        f"{path}: analyzed query count drift",
    )
    return {
        "path": str(path),
        "sha256": sha256_file(path),
        "kernel_name": rows[0]["Kernel"],
        "global_instance_ids": ids,
        "raw_selected_queries": RAW_QUERY_COUNT,
        "discarded_query_indexes": [0, 1],
        "analyzed_queries": ANALYZED_QUERY_COUNT,
        "reduction": "arithmetic mean of selected metric rows[2:]",
        "all_query_reports_valid": True,
        "zero_lsc_writes": True,
        "zero_partial_writes": True,
        "zero_slm_traffic_and_conflicts": True,
        "mean": {
            field: fmean(numeric(row, field, path) for row in analyzed)
            for field in MEAN_FIELDS
        },
    }


def parse_csv_section(
    text: str,
    *,
    path: Path,
    start: str,
    end: str | None,
    label: str,
) -> list[dict[str, str]]:
    require(text.count(start) == 1, f"{path}: require one {start}")
    section = text.split(start, maxsplit=1)[1]
    if end is not None:
        require(section.count(end) == 1, f"{path}: require one {end} after {start}")
        section = section.split(end, maxsplit=1)[0]
    return csv_rows(section.splitlines(), path, label)


def parse_timing_properties(
    path: Path,
    *,
    expected_kernel_name: str,
) -> dict[str, Any]:
    text = path.read_text()
    timing_rows = parse_csv_section(
        text,
        path=path,
        start="=== Device Timing Summary ===",
        end="=== Kernel Properties ===",
        label="device timing",
    )
    property_rows = parse_csv_section(
        text,
        path=path,
        start="=== Kernel Properties ===",
        end=None,
        label="kernel properties",
    )
    require(
        len(timing_rows) == 1 and timing_rows[0].get("Kernel") == expected_kernel_name,
        f"{path}: timing must contain only the selected exact kernel",
    )
    calls = integer(timing_rows[0], "Calls", path)
    require(
        calls == RAW_QUERY_COUNT,
        f"{path}: timing Calls must equal {RAW_QUERY_COUNT}",
    )
    time_ns = integer(timing_rows[0], "Time (ns)", path)
    time_percent = numeric(timing_rows[0], "Time (%)", path)
    average_ns = integer(timing_rows[0], "Average (ns)", path)
    minimum_ns = integer(timing_rows[0], "Min (ns)", path)
    maximum_ns = integer(timing_rows[0], "Max (ns)", path)
    require(
        time_ns > 0
        and time_percent == 100.0
        and average_ns > 0
        and minimum_ns > 0
        and maximum_ns > 0
        and minimum_ns <= average_ns <= maximum_ns,
        f"{path}: invalid timing scalar/range",
    )
    require(
        average_ns == time_ns // calls
        and calls * minimum_ns <= time_ns <= calls * maximum_ns,
        f"{path}: timing aggregate is inconsistent with calls/min/average/max",
    )
    require(
        len(property_rows) == 1
        and property_rows[0].get("Kernel") == expected_kernel_name,
        f"{path}: properties must contain only the selected exact kernel",
    )
    spill = integer(property_rows[0], "Spill Memory Per Thread", path)
    slm = integer(property_rows[0], "SLM Per Work Group", path)
    compiled = property_rows[0].get("Compiled")
    simd = integer(property_rows[0], "SIMD", path)
    argument_count = integer(property_rows[0], "Number of Arguments", path)
    private_memory = integer(
        property_rows[0],
        "Private Memory Per Thread",
        path,
    )
    register_file = integer(
        property_rows[0],
        "Register File Size Per Thread",
        path,
    )
    require(compiled in {"AOT", "JIT"}, f"{path}: invalid compilation mode")
    require(simd == 16, f"{path}: selected GEMM property SIMD is not 16")
    require(argument_count > 0, f"{path}: selected GEMM has no arguments")
    require(
        private_memory >= 0 and register_file > 0,
        f"{path}: invalid private/register property",
    )
    require(spill == 0, f"{path}: selected GEMM has spill memory")
    require(slm == 0, f"{path}: selected GEMM has SLM allocation")
    return {
        "path": str(path),
        "sha256": sha256_file(path),
        "kernel_name": expected_kernel_name,
        "calls": RAW_QUERY_COUNT,
        "time_ns": time_ns,
        "time_percent": time_percent,
        "average_ns": average_ns,
        "minimum_ns": minimum_ns,
        "maximum_ns": maximum_ns,
        "compiled": compiled,
        "simd": simd,
        "number_of_arguments": argument_count,
        "private_memory_per_thread": private_memory,
        "spill_memory_per_thread": spill,
        "slm_per_work_group": slm,
        "register_file_size_per_thread": register_file,
    }


def parse_idle_text(text: str, path: Path) -> None:
    lines = [line.split() for line in text.splitlines() if line.strip()]
    require(
        bool(lines) and lines[0][:5] == ["PID", "Command", "DeviceID", "SHR", "MEM"],
        f"{path}: invalid idle header",
    )
    rows = lines[1:]
    require(len(rows) == 4, f"{path}: idle proof does not have four rows")
    seen: dict[int, int] = {}
    for row in rows:
        require(
            len(row) >= 5 and row[1] == "xpu-smi",
            f"{path}: non-idle XPU client",
        )
        require(
            re.fullmatch(r"[0-3]", row[2]) is not None,
            f"{path}: bad idle device ID",
        )
        device = int(row[2])
        seen[device] = seen.get(device, 0) + 1
    require(
        seen == {0: 1, 1: 1, 2: 1, 3: 1},
        f"{path}: idle physical-device coverage drift",
    )


def validate_preflight(
    preflight: dict[str, Any],
    *,
    path: Path,
    rank: int,
    arm: str,
    treatment: str,
    packet: dict[str, Any],
    packet_sha256: str,
    protocol_sha256: str,
) -> dict[str, Any]:
    require(
        set(preflight)
        == {
            "format",
            "status",
            "captured_utc",
            "rank",
            "arm",
            "treatment",
            "authorization_path",
            "authorization_sha256",
            "protocol_sha256",
            "source",
            "physical_device",
            "idle",
            "mount",
            "sudo_password_file",
        },
        f"{path}: preflight schema drift",
    )
    require(
        preflight.get("format") == "laguna-shared-down-mm-counter-arm-preflight-v1"
        and preflight.get("status") == "passed"
        and preflight.get("rank") == rank
        and preflight.get("arm") == arm
        and preflight.get("treatment") == treatment
        and preflight.get("authorization_path") == str(contract.AUTHORIZATION_PATH)
        and preflight.get("authorization_sha256") == packet_sha256
        and preflight.get("protocol_sha256") == protocol_sha256,
        f"{path}: preflight identity drift",
    )
    source = preflight.get("source")
    require(isinstance(source, dict), f"{path}: missing source preflight")
    repositories = source.get("repositories")
    require(
        isinstance(repositories, dict)
        and repositories.get("main", {}).get("clean") is True
        and repositories.get("vllm", {}).get("clean") is True
        and repositories.get("kernels", {}).get("clean") is True
        and repositories.get("unitrace_source", {}).get("clean") is True
        and repositories["vllm"].get("commit") == contract.EXPECTED_VLLM_COMMIT
        and repositories["kernels"].get("commit") == contract.EXPECTED_KERNEL_COMMIT
        and repositories["unitrace_source"].get("commit")
        == contract.EXPECTED_UNITRACE_COMMIT
        and source.get("tools") == packet["tools"]
        and source.get("python") == packet["identities"]["python"]
        and source.get("torch") == packet["identities"]["torch"]
        and source.get("host_tools") == packet["identities"]["host_tools"]
        and source.get("boot_id") == contract.EXPECTED_BOOT_ID
        and source.get("kernel_taint") == "0",
        f"{path}: source identity drift",
    )
    physical = preflight.get("physical_device")
    require(
        isinstance(physical, dict)
        and physical.get("rank") == rank
        and physical.get("expected") == contract.EXPECTED_PHYSICAL_DEVICES[rank]
        and physical.get("uuid_bdf_binding_exact") is True,
        f"{path}: physical-device preflight drift",
    )
    filtered_devices = physical.get("filtered", {}).get("device_list")
    unfiltered_devices = physical.get("unfiltered", {}).get("device_list")
    expected_device = contract.EXPECTED_PHYSICAL_DEVICES[rank]
    require(
        isinstance(filtered_devices, list)
        and len(filtered_devices) == 1
        and filtered_devices[0].get("device_id") == 0
        and all(
            filtered_devices[0].get(field) == expected
            for field, expected in {
                **expected_device,
                "device_id": 0,
                "device_name": contract.EXPECTED_DEVICE_NAME,
            }.items()
        )
        and isinstance(unfiltered_devices, list)
        and len(unfiltered_devices) == 4,
        f"{path}: filtered/unfiltered discovery drift",
    )
    unfiltered_by_rank = {
        device.get("device_id"): device
        for device in unfiltered_devices
        if isinstance(device, dict)
    }
    require(
        set(unfiltered_by_rank) == set(contract.RANKS)
        and all(
            all(
                unfiltered_by_rank[physical_rank].get(field) == expected
                for field, expected in {
                    **contract.EXPECTED_PHYSICAL_DEVICES[physical_rank],
                    "device_name": contract.EXPECTED_DEVICE_NAME,
                }.items()
            )
            for physical_rank in contract.RANKS
        )
        and all(
            isinstance(physical.get(name), str)
            and re.fullmatch(r"[0-9a-f]{64}", physical[name]) is not None
            for name in ("filtered_sha256", "unfiltered_sha256")
        ),
        f"{path}: unfiltered four-card mapping drift",
    )
    idle = preflight.get("idle")
    require(
        isinstance(idle, dict)
        and idle.get("passed") is True
        and idle.get("only_xpu_smi_self_rows") is True
        and idle.get("rows") == 4
        and isinstance(idle.get("text"), str)
        and idle.get("sha256") == sha256_bytes(idle["text"].encode()),
        f"{path}: idle proof linkage drift",
    )
    parse_idle_text(idle["text"], path)
    require(
        preflight.get("mount")
        == {
            "target": "/mnt/fast-ai",
            "mount_point": "/",
            "source": contract.NVME_SOURCE,
            "filesystem": contract.NVME_FSTYPE,
        }
        and preflight.get("sudo_password_file", {}).get("mode") == "0600"
        and preflight.get("sudo_password_file", {}).get("content_not_recorded") is True,
        f"{path}: mount/sudo metadata drift",
    )
    return {
        "main_commit": repositories["main"]["commit"],
        "vllm_commit": repositories["vllm"]["commit"],
        "kernel_commit": repositories["kernels"]["commit"],
        "boot_id": source["boot_id"],
        "physical_uuid": filtered_devices[0]["uuid"],
        "physical_bdf": filtered_devices[0]["pci_bdf_address"],
        "idle_sha256": idle["sha256"],
    }


def expected_fixture_argv(
    *,
    command: list[str],
) -> list[str]:
    fixture_index = command.index(str(contract.FIXTURE))
    return command[fixture_index:]


def validate_fixture(
    fixture: dict[str, Any],
    *,
    path: Path,
    base: Path,
    rank: int,
    treatment: str,
    command: list[str],
    packet: dict[str, Any],
) -> dict[str, Any]:
    require(
        set(fixture)
        == {
            "format",
            "status",
            "created_utc",
            "identity",
            "rank",
            "arm",
            "epoch",
            "geometry",
            "calls",
            "selected_gemm_calls",
            "completion_boundary_before_each_call",
            "completion_boundary_after_each_call",
            "eviction_bytes_before_each_call",
            "input_sha256",
            "fixture_sha256",
            "output_sha256",
            "all_output_sha256",
            "counter_execution_performed",
            "counter_gate_evaluated",
            "endpoint_preregistration_construction_authorized",
            "endpoint_authorized",
            "model_generation_performed",
            "payload_created",
            "submission_performed",
        },
        f"{path}: fixture schema drift",
    )
    require(
        fixture.get("format") == "laguna-shared-down-mm-cold-counter-fixture-v1"
        and fixture.get("status") == "fixture-complete"
        and fixture.get("rank") == rank
        and fixture.get("arm") == treatment
        and fixture.get("epoch") == 30_000
        and fixture.get("geometry")
        == {
            "rows": 8,
            "k": 256,
            "n": 3072,
            "dtype": "torch.bfloat16",
            "rows_contiguous": True,
            "weight_contiguous": True,
        }
        and fixture.get("calls") == RAW_QUERY_COUNT
        and fixture.get("selected_gemm_calls") == RAW_QUERY_COUNT
        and fixture.get("completion_boundary_before_each_call") is True
        and fixture.get("completion_boundary_after_each_call") is True
        and fixture.get("eviction_bytes_before_each_call") == 134_217_728,
        f"{path}: fixture protocol drift",
    )
    identity = fixture.get("identity")
    require(isinstance(identity, dict), f"{path}: fixture identity missing")
    require(
        identity.get("fixture")
        == {
            "path": str(contract.FIXTURE),
            "sha256": packet["tools"]["fixture"]["sha256"],
        }
        and identity.get("gate")
        == {
            "path": str(contract.GATE),
            "sha256": packet["tools"]["gate"]["sha256"],
        }
        and identity.get("model_config") == packet["identities"]["model_config"]
        and identity.get("binaries") == packet["identities"]["runtime_binaries"]
        and identity.get("torch_identity") == packet["identities"]["torch"]
        and identity.get("declared_physical_rank") == rank
        and identity.get("expected_physical_device")
        == contract.EXPECTED_PHYSICAL_DEVICES[rank]
        and identity.get("subprocesses_started") == 0,
        f"{path}: fixture source/binary identity drift",
    )
    environment = identity.get("environment")
    require(isinstance(environment, dict), f"{path}: fixture environment missing")
    expected_runtime_paths = contract.arm_runtime_paths(base)
    for name, expected in contract.RECORD_ENVIRONMENT.items():
        require(
            environment.get(name) == expected,
            f"{path}: fixture environment {name} drift",
        )
    require(
        environment.get("ZE_AFFINITY_MASK") == str(rank)
        and environment.get("ONEAPI_DEVICE_SELECTOR") == "level_zero:0"
        and environment.get("PYTHONPATH")
        == f"{contract.VLLM_REPO}:{contract.KERNEL_REPO}"
        and environment.get("PYTHONHASHSEED") == "0"
        and environment.get("PYTHONNOUSERSITE") == "1"
        and environment.get("PYTHONDONTWRITEBYTECODE") == "1"
        and environment.get("PATH")
        == "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
        and environment.get("LANG") == "C.UTF-8"
        and environment.get("LC_ALL") == "C.UTF-8"
        and environment.get("HOME") == str(expected_runtime_paths["HOME"])
        and environment.get("OMP_NUM_THREADS") == "1"
        and environment.get("MKL_NUM_THREADS") == "1",
        f"{path}: fixture selector/determinism environment drift",
    )
    for name, expected_path in expected_runtime_paths.items():
        require(
            environment.get(name) == str(expected_path),
            f"{path}: runtime path {name} drift",
        )
    runtime = identity.get("runtime")
    require(
        isinstance(runtime, dict)
        and runtime.get("boot_id") == contract.EXPECTED_BOOT_ID
        and runtime.get("kernel_taint") == "0"
        and runtime.get("visible_torch_xpu_count") == 1
        and runtime.get("visible_torch_xpu_name") == contract.EXPECTED_DEVICE_NAME
        and runtime.get("python_executable") == str(contract.PYTHON)
        and runtime.get("python_sha256") == packet["identities"]["python"]["sha256"]
        and runtime.get("torch") == packet["identities"]["torch"]["version"]
        and runtime.get("torch_path")
        == packet["identities"]["torch"]["files"]["__init__"]["path"]
        and identity.get("uid") == 0
        and isinstance(identity.get("pid"), int)
        and identity["pid"] > 0
        and identity.get("argv") == expected_fixture_argv(command=command),
        f"{path}: fixture direct runtime identity drift",
    )
    require(
        identity.get("mount")
        == {
            "target": "/mnt/fast-ai",
            "mount_point": "/",
            "source": contract.NVME_SOURCE,
            "filesystem": contract.NVME_FSTYPE,
        },
        f"{path}: fixture mount identity drift",
    )
    input_hashes = fixture.get("input_sha256")
    output_hashes = fixture.get("all_output_sha256")
    require(
        isinstance(input_hashes, dict)
        and set(input_hashes) == {"rows", "weight", "combined"}
        and all(
            isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None
            for value in input_hashes.values()
        )
        and fixture.get("fixture_sha256") == input_hashes["combined"]
        and isinstance(output_hashes, list)
        and len(output_hashes) == RAW_QUERY_COUNT
        and len(set(output_hashes)) == 1
        and fixture.get("output_sha256") == output_hashes[0]
        and re.fullmatch(r"[0-9a-f]{64}", output_hashes[0]) is not None,
        f"{path}: fixture/output raw-hash contract drift",
    )
    require(
        fixture.get("counter_execution_performed") is True
        and fixture.get("counter_gate_evaluated") is False
        and fixture.get("endpoint_preregistration_construction_authorized") is False
        and fixture.get("endpoint_authorized") is False
        and fixture.get("model_generation_performed") is False
        and fixture.get("payload_created") is False
        and fixture.get("submission_performed") is False,
        f"{path}: fixture authorization boundary drift",
    )
    return {
        "fixture_sha256": fixture["fixture_sha256"],
        "input_sha256": input_hashes,
        "output_sha256": fixture["output_sha256"],
        "all_output_sha256": output_hashes,
        "fixture_pid": identity["pid"],
        "torch": runtime["torch"],
        "torch_path": runtime["torch_path"],
    }


def validate_runtime_subtree(
    base: Path,
    declared: dict[str, Any],
) -> dict[str, Any]:
    runtime = base / "runtime"
    cache = runtime / "cache"
    temporary = runtime / "tmp"
    home = runtime / "home"
    expected_paths = contract.arm_runtime_paths(base)
    require(
        declared
        == {
            "path": str(runtime),
            "evidence_file_hashing_excluded": True,
            "reason": "fresh per-arm compiler/cache/temp contents are non-counter evidence",
            "required_directories": {
                name: str(path) for name, path in expected_paths.items()
            },
        },
        f"{base}: runtime-subtree declaration drift",
    )
    require(
        runtime.is_dir()
        and not runtime.is_symlink()
        and runtime.resolve().is_relative_to(base)
        and {child.name for child in runtime.iterdir()} == {"cache", "tmp", "home"}
        and cache.is_dir()
        and temporary.is_dir()
        and home.is_dir()
        and not cache.is_symlink()
        and not temporary.is_symlink()
        and not home.is_symlink(),
        f"{base}: runtime direct layout drift",
    )
    expected_cache_leaves = {
        path.name for path in set(expected_paths.values()) if path.parent == cache
    }
    require(
        {child.name for child in cache.iterdir()} == expected_cache_leaves
        and all(
            child.is_dir()
            and not child.is_symlink()
            and child.resolve().is_relative_to(base)
            for child in cache.iterdir()
        ),
        f"{base}: runtime cache-leaf layout drift",
    )
    entries = 0
    for walk_root, directories, files in os.walk(runtime, followlinks=False):
        for name in (*directories, *files):
            child = Path(walk_root) / name
            require(
                not child.is_symlink() and child.resolve().is_relative_to(base),
                f"{base}: runtime descendant escaped through a symlink",
            )
            entries += 1
    return {
        "path": str(runtime),
        "layout_passed": True,
        "symlinks": 0,
        "descendant_entries": entries,
        "evidence_file_hashing_excluded": True,
    }


def validate_arm(
    path: Path,
    *,
    expected_manifest_sha256: str,
    rank: int,
    arm: str,
    packet: dict[str, Any],
    packet_sha256: str,
    protocol_sha256: str,
) -> dict[str, Any]:
    base = path.parent
    treatment = "control" if arm.startswith("A") else "candidate"
    require(
        path == base / "manifest.json"
        and path.is_file()
        and not path.is_symlink()
        and sha256_file(path) == expected_manifest_sha256,
        f"{path}: arm-manifest path/SHA drift",
    )
    manifest = json.loads(path.read_text())
    require(
        set(manifest)
        == {
            "format",
            "status",
            "completed_utc",
            "rank",
            "arm",
            "treatment",
            "authorization_path",
            "authorization_sha256",
            "protocol_sha256",
            "command",
            "cwd",
            "returncode",
            "unitrace_output_pid_suffix",
            "runtime_subtree",
            "files",
            "fixture",
            "counter_execution_performed",
            "counter_gate_evaluated",
            "endpoint_preregistration_construction_authorized",
            "endpoint_authorized",
            "model_generation_performed",
            "payload_created",
            "localmaxxing_submission_made",
        },
        f"{path}: arm-manifest schema drift",
    )
    require(
        manifest.get("format") == "laguna-shared-down-mm-counter-arm-manifest-v1"
        and manifest.get("status") == "complete"
        and manifest.get("rank") == rank
        and manifest.get("arm") == arm
        and manifest.get("treatment") == treatment
        and manifest.get("authorization_path") == str(contract.AUTHORIZATION_PATH)
        and manifest.get("authorization_sha256") == packet_sha256
        and manifest.get("protocol_sha256") == protocol_sha256
        and manifest.get("cwd") == str(base)
        and manifest.get("returncode") == 0,
        f"{path}: arm-manifest identity drift",
    )
    command = contract.build_unitrace_command(
        rank=rank,
        arm=arm,
        arm_dir=base,
        fixture_sha256=packet["tools"]["fixture"]["sha256"],
    )
    require(
        manifest.get("command") == command and "--follow-child-process" not in command,
        f"{path}: profiler command drift",
    )
    suffix = manifest.get("unitrace_output_pid_suffix")
    require(
        isinstance(suffix, str) and re.fullmatch(r"[0-9]+", suffix) is not None,
        f"{path}: invalid unitrace PID suffix",
    )
    expected_names = {
        "preflight.json",
        "stdout.log",
        "stderr.log",
        "fixture.json",
        f"unitrace.{suffix}",
        f"unitrace.metrics.{suffix}",
    }
    files = manifest.get("files")
    require(
        isinstance(files, dict) and set(files) == expected_names,
        f"{path}: arm evidence file set drift",
    )
    for name, entry in files.items():
        file_path = base / name
        require(
            isinstance(entry, dict)
            and set(entry) == {"path", "sha256", "bytes"}
            and entry.get("path") == str(file_path)
            and file_path.is_file()
            and not file_path.is_symlink()
            and sha256_file(file_path) == entry.get("sha256")
            and file_path.stat().st_size == entry.get("bytes"),
            f"{path}: arm evidence identity drift: {name}",
        )
    require(
        {child.name for child in base.iterdir()}
        == expected_names | {"manifest.json", "runtime"}
        and (base / "runtime").resolve().is_relative_to(base),
        f"{path}: unexpected arm files/directories",
    )
    runtime_report = validate_runtime_subtree(
        base,
        manifest.get("runtime_subtree"),
    )
    preflight_path = base / "preflight.json"
    preflight = json.loads(preflight_path.read_text())
    preflight_report = validate_preflight(
        preflight,
        path=preflight_path,
        rank=rank,
        arm=arm,
        treatment=treatment,
        packet=packet,
        packet_sha256=packet_sha256,
        protocol_sha256=protocol_sha256,
    )
    fixture_path = base / "fixture.json"
    fixture = json.loads(fixture_path.read_text())
    require(
        manifest.get("fixture") == fixture,
        f"{path}: embedded fixture differs from fixture.json",
    )
    fixture_report = validate_fixture(
        fixture,
        path=fixture_path,
        base=base,
        rank=rank,
        treatment=treatment,
        command=command,
        packet=packet,
    )
    require(
        str(fixture_report["fixture_pid"]) == suffix,
        f"{path}: unitrace PID suffix does not equal fixture PID",
    )
    metrics_path = base / f"unitrace.metrics.{suffix}"
    timing_path = base / f"unitrace.{suffix}"
    metrics = parse_metrics(metrics_path)
    timing = parse_timing_properties(
        timing_path,
        expected_kernel_name=metrics["kernel_name"],
    )
    require(
        manifest.get("counter_execution_performed") is True
        and manifest.get("counter_gate_evaluated") is False
        and manifest.get("endpoint_preregistration_construction_authorized") is False
        and manifest.get("endpoint_authorized") is False
        and manifest.get("model_generation_performed") is False
        and manifest.get("payload_created") is False
        and manifest.get("localmaxxing_submission_made") is False,
        f"{path}: arm authorization boundary drift",
    )
    return {
        "rank": rank,
        "arm": arm,
        "treatment": treatment,
        "manifest": {
            "path": str(path),
            "sha256": expected_manifest_sha256,
        },
        "preflight": preflight_report,
        "fixture": fixture_report,
        "metrics": metrics,
        "timing_properties": timing,
        "runtime_subtree": runtime_report,
        "unitrace_output_pid_suffix": suffix,
    }


def average_profile(profiles: list[dict[str, Any]]) -> dict[str, float]:
    require(bool(profiles), "cannot average an empty profile set")
    return {
        field: fmean(profile["metrics"]["mean"][field] for profile in profiles)
        for field in MEAN_FIELDS
    }


def compare_means(
    candidate: dict[str, float],
    control: dict[str, float],
    *,
    full_metric_guardrails: bool,
) -> dict[str, Any]:
    for field in (
        "GpuTime[ns]",
        "GPU_MEMORY_BYTE_READ[bytes]",
        "LOAD_STORE_CACHE_BYTE_READ[bytes]",
    ):
        require(control[field] > 0.0, f"zero control denominator for {field}")
    checks = {
        "candidate_gpu_time_lower": (candidate["GpuTime[ns]"] < control["GpuTime[ns]"])
    }
    if full_metric_guardrails:
        checks.update(
            {
                "gpu_memory_read_regression_within_2pct": (
                    candidate["GPU_MEMORY_BYTE_READ[bytes]"]
                    <= control["GPU_MEMORY_BYTE_READ[bytes]"] * 1.02
                ),
                "lsc_read_regression_within_2pct": (
                    candidate["LOAD_STORE_CACHE_BYTE_READ[bytes]"]
                    <= control["LOAD_STORE_CACHE_BYTE_READ[bytes]"] * 1.02
                ),
                "xve_stall_increase_within_0_5pp": (
                    candidate["XVE_STALL[%]"] <= control["XVE_STALL[%]"] + 0.5
                ),
                "xve_active_decrease_within_0_5pp": (
                    candidate["XVE_ACTIVE[%]"] >= control["XVE_ACTIVE[%]"] - 0.5
                ),
                "thread_occupancy_decrease_within_0_5pp": (
                    candidate["XVE_THREADS_OCCUPANCY_ALL[%]"]
                    >= control["XVE_THREADS_OCCUPANCY_ALL[%]"] - 0.5
                ),
            }
        )
    return {
        "control_mean": control,
        "candidate_mean": candidate,
        "delta": {field: candidate[field] - control[field] for field in MEAN_FIELDS},
        "ratio": {
            "gpu_time": candidate["GpuTime[ns]"] / control["GpuTime[ns]"],
            "gpu_memory_read": candidate["GPU_MEMORY_BYTE_READ[bytes]"]
            / control["GPU_MEMORY_BYTE_READ[bytes]"],
            "lsc_read": candidate["LOAD_STORE_CACHE_BYTE_READ[bytes]"]
            / control["LOAD_STORE_CACHE_BYTE_READ[bytes]"],
        },
        "checks": checks,
        "guardrail_scope": (
            "gpu-time-plus-full-metric-guardrails"
            if full_metric_guardrails
            else "gpu-time-only"
        ),
        "passed": all(checks.values()),
    }


def validate_campaign(
    root: Path,
    *,
    packet: dict[str, Any],
    packet_sha256: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    require(
        root.is_absolute()
        and root.resolve(strict=True) == root
        and root.parent == contract.RUNS_ROOT
        and re.fullmatch(
            r"shared-down-m8-counters-[0-9]{8}T[0-9]{6}Z",
            root.name,
        )
        is not None,
        "campaign root identity drift",
    )
    require(
        not (root / "campaign.error.json").exists()
        and not (root / "analysis.json").exists(),
        "campaign has an error or preexisting analysis artifact",
    )
    open_path = root / "campaign.open.json"
    complete_path = root / "campaign.complete.json"
    require(
        open_path.is_file()
        and complete_path.is_file()
        and not open_path.is_symlink()
        and not complete_path.is_symlink(),
        "campaign open/complete closure is missing or symlinked",
    )
    opened = json.loads(open_path.read_text())
    complete = json.loads(complete_path.read_text())
    protocol_sha256 = contract.canonical_sha256(packet["protocol"])
    require(
        set(opened)
        == {
            "format",
            "status",
            "created_utc",
            "campaign_root",
            "authorization_path",
            "authorization_sha256",
            "authorization",
            "protocol",
            "protocol_sha256",
            "acceptance",
            "tools",
            "component_evidence",
            "source",
            "mount",
            "planned_cards",
            "planned_arms_per_card",
            "counter_execution_performed",
            "counter_gate_evaluated",
            "endpoint_preregistration_construction_authorized",
            "endpoint_authorized",
            "model_generation_performed",
            "payload_created",
            "localmaxxing_submission_made",
        },
        "campaign-open schema drift",
    )
    require(
        opened.get("format") == "laguna-shared-down-mm-counter-campaign-open-v1"
        and opened.get("status") == "open"
        and opened.get("campaign_root") == str(root)
        and opened.get("authorization_path") == str(contract.AUTHORIZATION_PATH)
        and opened.get("authorization_sha256") == packet_sha256
        and opened.get("authorization") == packet["authorization"]
        and opened.get("protocol") == packet["protocol"]
        and opened.get("protocol_sha256") == protocol_sha256
        and opened.get("acceptance") == packet["acceptance"]
        and opened.get("tools") == packet["tools"]
        and opened.get("component_evidence") == packet["component_evidence"]
        and opened.get("planned_cards") == list(contract.RANKS)
        and opened.get("planned_arms_per_card") == list(contract.ARMS),
        "campaign-open contract drift",
    )
    open_source = opened.get("source")
    open_repositories = (
        open_source.get("repositories") if isinstance(open_source, dict) else None
    )
    require(
        isinstance(open_repositories, dict)
        and all(
            open_repositories.get(name, {}).get("clean") is True
            for name in ("main", "vllm", "kernels", "unitrace_source")
        )
        and open_repositories["vllm"].get("commit") == contract.EXPECTED_VLLM_COMMIT
        and open_repositories["kernels"].get("commit")
        == contract.EXPECTED_KERNEL_COMMIT
        and open_repositories["unitrace_source"].get("commit")
        == contract.EXPECTED_UNITRACE_COMMIT
        and open_source.get("tools") == packet["tools"]
        and open_source.get("python") == packet["identities"]["python"]
        and open_source.get("torch") == packet["identities"]["torch"]
        and open_source.get("host_tools") == packet["identities"]["host_tools"]
        and open_source.get("boot_id") == contract.EXPECTED_BOOT_ID
        and open_source.get("kernel_taint") == "0"
        and opened.get("mount")
        == {
            "target": "/mnt/fast-ai",
            "mount_point": "/",
            "source": contract.NVME_SOURCE,
            "filesystem": contract.NVME_FSTYPE,
        }
        and opened.get("counter_execution_performed") is False
        and opened.get("counter_gate_evaluated") is False
        and opened.get("endpoint_preregistration_construction_authorized") is False
        and opened.get("endpoint_authorized") is False
        and opened.get("model_generation_performed") is False
        and opened.get("payload_created") is False
        and opened.get("localmaxxing_submission_made") is False,
        "campaign-open source/mount/authorization drift",
    )
    require(
        set(complete)
        == {
            "format",
            "status",
            "completed_utc",
            "campaign_root",
            "authorization_path",
            "authorization_sha256",
            "protocol_sha256",
            "campaign_open",
            "cards",
            "arms",
            "counter_execution_performed",
            "counter_gate_evaluated",
            "endpoint_preregistration_construction_authorized",
            "endpoint_authorized",
            "model_generation_performed",
            "payload_created",
            "localmaxxing_submission_made",
        },
        "campaign-complete schema drift",
    )
    require(
        complete.get("format") == "laguna-shared-down-mm-counter-campaign-complete-v1"
        and complete.get("status") == "complete"
        and complete.get("campaign_root") == str(root)
        and complete.get("authorization_path") == str(contract.AUTHORIZATION_PATH)
        and complete.get("authorization_sha256") == packet_sha256
        and complete.get("protocol_sha256") == protocol_sha256
        and complete.get("campaign_open")
        == {"path": str(open_path), "sha256": sha256_file(open_path)}
        and complete.get("counter_execution_performed") is True
        and complete.get("counter_gate_evaluated") is False
        and complete.get("endpoint_preregistration_construction_authorized") is False
        and complete.get("endpoint_authorized") is False
        and complete.get("model_generation_performed") is False
        and complete.get("payload_created") is False
        and complete.get("localmaxxing_submission_made") is False,
        "campaign-complete contract drift",
    )
    arm_entries = complete.get("arms")
    card_entries = complete.get("cards")
    require(
        isinstance(arm_entries, list)
        and len(arm_entries) == 16
        and isinstance(card_entries, list)
        and len(card_entries) == 4,
        "campaign closure must bind 16 arms and four cards",
    )
    expected_pairs = [(rank, arm) for rank in contract.RANKS for arm in contract.ARMS]
    require(
        [(entry.get("rank"), entry.get("arm")) for entry in arm_entries]
        == expected_pairs,
        "campaign arm order/coverage drift",
    )
    profiles: list[dict[str, Any]] = []
    for entry in arm_entries:
        rank = entry["rank"]
        arm = entry["arm"]
        treatment = "control" if arm.startswith("A") else "candidate"
        expected_path = root / f"card{rank}" / arm / "manifest.json"
        require(
            entry
            == {
                "rank": rank,
                "arm": arm,
                "treatment": treatment,
                "path": str(expected_path),
                "sha256": entry.get("sha256"),
            }
            and isinstance(entry.get("sha256"), str)
            and re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]) is not None,
            "campaign arm closure entry drift",
        )
        profiles.append(
            validate_arm(
                expected_path,
                expected_manifest_sha256=entry["sha256"],
                rank=rank,
                arm=arm,
                packet=packet,
                packet_sha256=packet_sha256,
                protocol_sha256=protocol_sha256,
            )
        )
    for rank, entry in zip(contract.RANKS, card_entries, strict=True):
        card_path = root / f"card{rank}" / "card.manifest.json"
        require(
            entry
            == {
                "rank": rank,
                "path": str(card_path),
                "sha256": entry.get("sha256"),
            }
            and card_path.is_file()
            and not card_path.is_symlink()
            and sha256_file(card_path) == entry["sha256"],
            f"card {rank} closure SHA drift",
        )
        card = json.loads(card_path.read_text())
        expected_arms = [
            arm_entry for arm_entry in arm_entries if arm_entry["rank"] == rank
        ]
        require(
            set(card)
            == {
                "format",
                "status",
                "completed_utc",
                "rank",
                "authorization_sha256",
                "protocol_sha256",
                "arms",
                "counter_execution_performed",
                "counter_gate_evaluated",
                "endpoint_preregistration_construction_authorized",
                "endpoint_authorized",
                "model_generation_performed",
                "payload_created",
                "localmaxxing_submission_made",
            }
            and card.get("format") == "laguna-shared-down-mm-counter-card-manifest-v1"
            and card.get("status") == "complete"
            and card.get("rank") == rank
            and card.get("authorization_sha256") == packet_sha256
            and card.get("protocol_sha256") == protocol_sha256
            and card.get("arms") == expected_arms
            and card.get("counter_execution_performed") is True
            and card.get("counter_gate_evaluated") is False
            and card.get("endpoint_preregistration_construction_authorized") is False
            and card.get("endpoint_authorized") is False
            and card.get("model_generation_performed") is False
            and card.get("payload_created") is False
            and card.get("localmaxxing_submission_made") is False,
            f"card {rank} manifest contract drift",
        )
        card_dir = root / f"card{rank}"
        require(
            {child.name for child in card_dir.iterdir()}
            == {"A1", "B1", "B2", "A2", "card.manifest.json"}
            and all(
                (card_dir / arm).is_dir()
                and not (card_dir / arm).is_symlink()
                and (card_dir / arm).resolve().is_relative_to(card_dir)
                for arm in contract.ARMS
            ),
            f"card {rank} directory closure drift",
        )
    require(
        {child.name for child in root.iterdir()}
        == {
            "campaign.open.json",
            "campaign.complete.json",
            "card0",
            "card1",
            "card2",
            "card3",
        },
        "unexpected campaign-root entries",
    )
    return complete, profiles


def analyze_profiles(profiles: list[dict[str, Any]]) -> dict[str, Any]:
    by = {(profile["rank"], profile["arm"]): profile for profile in profiles}
    require(
        len(by) == 16
        and set(by)
        == {(rank, arm) for rank in contract.RANKS for arm in contract.ARMS},
        "profile rank/arm coverage drift",
    )
    fixtures = {profile["fixture"]["fixture_sha256"] for profile in profiles}
    inputs = {
        json.dumps(profile["fixture"]["input_sha256"], sort_keys=True)
        for profile in profiles
    }
    outputs = {profile["fixture"]["output_sha256"] for profile in profiles}
    output_lists = {
        tuple(profile["fixture"]["all_output_sha256"]) for profile in profiles
    }
    require(
        len(fixtures) == len(inputs) == len(outputs) == len(output_lists) == 1,
        "control/candidate/card fixture or raw output hashes differ",
    )
    require(
        len({profile["preflight"]["physical_uuid"] for profile in profiles}) == 4
        and len({profile["preflight"]["physical_bdf"] for profile in profiles}) == 4
        and all(
            profile["preflight"]["physical_uuid"]
            == contract.EXPECTED_PHYSICAL_DEVICES[profile["rank"]]["uuid"]
            and profile["preflight"]["physical_bdf"]
            == contract.EXPECTED_PHYSICAL_DEVICES[profile["rank"]]["pci_bdf_address"]
            for profile in profiles
        )
        and len({profile["preflight"]["main_commit"] for profile in profiles}) == 1
        and len({profile["preflight"]["vllm_commit"] for profile in profiles}) == 1
        and len({profile["preflight"]["kernel_commit"] for profile in profiles}) == 1
        and len({profile["preflight"]["boot_id"] for profile in profiles}) == 1
        and {profile["fixture"]["torch"] for profile in profiles}
        == {contract.EXPECTED_TORCH_VERSION}
        and {profile["fixture"]["torch_path"] for profile in profiles}
        == {
            contract.EXPECTED_TORCH_FILES["__init__"]["path"],
        },
        "cross-card physical/source/runtime identity drift",
    )
    control_kernel_names = {
        profile["metrics"]["kernel_name"]
        for profile in profiles
        if profile["treatment"] == "control"
    }
    candidate_kernel_names = {
        profile["metrics"]["kernel_name"]
        for profile in profiles
        if profile["treatment"] == "candidate"
    }
    require(
        len(control_kernel_names) == len(candidate_kernel_names) == 1,
        "kernel identity differs within a treatment",
    )

    cards: dict[str, Any] = {}
    comparison_passes: list[bool] = []
    for rank in contract.RANKS:
        first = compare_means(
            by[rank, "B1"]["metrics"]["mean"],
            by[rank, "A1"]["metrics"]["mean"],
            full_metric_guardrails=False,
        )
        second = compare_means(
            by[rank, "B2"]["metrics"]["mean"],
            by[rank, "A2"]["metrics"]["mean"],
            full_metric_guardrails=False,
        )
        aggregate = compare_means(
            average_profile([by[rank, "B1"], by[rank, "B2"]]),
            average_profile([by[rank, "A1"], by[rank, "A2"]]),
            full_metric_guardrails=True,
        )
        cards[str(rank)] = {
            "physical_uuid": by[rank, "A1"]["preflight"]["physical_uuid"],
            "physical_bdf": by[rank, "A1"]["preflight"]["physical_bdf"],
            "B1_vs_A1": first,
            "B2_vs_A2": second,
            "candidate_vs_control_aggregate": aggregate,
            "passed": first["passed"] and second["passed"] and aggregate["passed"],
        }
        comparison_passes.extend(
            (first["passed"], second["passed"], aggregate["passed"])
        )
    global_comparison = compare_means(
        average_profile(
            [profile for profile in profiles if profile["treatment"] == "candidate"]
        ),
        average_profile(
            [profile for profile in profiles if profile["treatment"] == "control"]
        ),
        full_metric_guardrails=False,
    )
    comparison_passes.append(global_comparison["passed"])
    passed = all(comparison_passes)
    return {
        "passed": passed,
        "fixture_sha256": next(iter(fixtures)),
        "input_sha256": json.loads(next(iter(inputs))),
        "output_sha256": next(iter(outputs)),
        "all_output_sha256": list(next(iter(output_lists))),
        "all_control_candidate_outputs_raw_exact": True,
        "control_kernel_name": next(iter(control_kernel_names)),
        "candidate_kernel_name": next(iter(candidate_kernel_names)),
        "cards": cards,
        "global_four_card_candidate_vs_control": global_comparison,
        "profiles": profiles,
    }


def atomic_exclusive_json(path: Path, value: dict[str, Any]) -> None:
    encoded = (
        json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n"
    ).encode()
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o644,
    )
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign-root", type=Path, required=True)
    parser.add_argument("--authorization-json", type=Path, required=True)
    parser.add_argument(
        "--expected-authorization-sha256",
        type=contract.sha256_argument,
        required=True,
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    packet, packet_sha256 = contract.validate_authorization(
        args.authorization_json,
        args.expected_authorization_sha256,
    )
    require(
        sha256_file(Path(__file__).resolve()) == packet["tools"]["analyzer"]["sha256"],
        "analyzer source differs from authorization packet",
    )
    contract.validate_packet_command_template(packet)
    contract.local_nvme_mount_identity()
    root = args.campaign_root.resolve(strict=True)
    out = args.out
    require(
        out.is_absolute()
        and out == root / "analysis.json"
        and not out.exists()
        and not out.is_symlink(),
        "analysis output must be new campaign-root/analysis.json",
    )
    complete, profiles = validate_campaign(
        root,
        packet=packet,
        packet_sha256=packet_sha256,
    )
    analysis = analyze_profiles(profiles)
    passed = analysis["passed"]
    result: dict[str, Any] = {
        "format": "laguna-shared-down-mm-counter-analysis-v1",
        "status": (
            "counter-passed-endpoint-preregistration-construction-next"
            if passed
            else "counter-failed-stop-before-endpoint"
        ),
        "passed": passed,
        "created_utc": contract.utc_now(),
        "campaign_root": str(root),
        "campaign_complete": {
            "path": str(root / "campaign.complete.json"),
            "sha256": sha256_file(root / "campaign.complete.json"),
        },
        "authorization_path": str(contract.AUTHORIZATION_PATH),
        "authorization_sha256": packet_sha256,
        "protocol": packet["protocol"],
        "protocol_sha256": contract.canonical_sha256(packet["protocol"]),
        "acceptance": packet["acceptance"],
        "tools": packet["tools"],
        "component_evidence": packet["component_evidence"],
        "campaign_closure": complete,
        "analysis": analysis,
        "authorization": {
            "counter_gate_evaluated": True,
            "counter_gate_passed": passed,
            "endpoint_preregistration_construction_authorized": passed,
            "endpoint_execution_authorized": False,
            "model_generation_authorized": False,
            "model_generation_performed": False,
            "payload_created": False,
            "localmaxxing_submission_authorized": False,
            "localmaxxing_submission_made": False,
        },
    }
    atomic_exclusive_json(out, result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "passed": passed,
                "analysis_sha256": sha256_file(out),
            },
            sort_keys=True,
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
