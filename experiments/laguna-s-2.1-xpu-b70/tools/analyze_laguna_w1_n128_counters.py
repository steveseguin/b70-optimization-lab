#!/usr/bin/env python3
"""Fail-closed analysis for the Laguna routed-W1 N64/N128 counter gate."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
from pathlib import Path
from statistics import fmean
from typing import Any

EXPECTED_KERNEL_HEAD = "c59aaadbbfd350c2b5f4ad663e247c2811ae3181"
BASELINE_KERNEL_HEAD = "b6076ce1249ffee0e30bee528f4cd15c3bffb234"
EXPECTED_EXTENSION_SHA256 = (
    "f5f672130cc1b1d550646f732a6d576952c49514eba7a10db60fc1c361938fd8"
)
EXPECTED_GROUPED_SHA256 = (
    "fc74a6452b95643768889e2598df77bc4f4aa2b0925257a4c0eff371b1cf6c96"
)
EXPECTED_FIXTURE_SHA256 = (
    "478a23508e635c91fa62ff0a4b737016266bc308e8fe60111e81abad3d47c1f6"
)
EXPECTED_FIXTURE_TENSOR_SHA256 = (
    "2830da5e5e7ee2f4118b8d6c5618be6d36bb9a567c17df230bb87e20890734af"
)
EXPECTED_FIXTURE_SOURCE_SHA256 = (
    "bd1d6ef31f8ee359f04c6af1ccc55e39d79b21fc1592ae2377734e64f2512a47"
)
EXPECTED_UNITRACE_SHA256 = (
    "5aaca1f418a212a1d298cac27afb6c471bf1fcf47a1622e0c20d1a2cf43fc85a"
)
EXPECTED_UNITRACE_COMMIT = "a5bab309f4ffdd78bd127035c46f5f75371160f8"

EXPECTED_ARMS = {
    "A1": 64,
    "B1": 128,
    "B2": 128,
    "A2": 64,
}
RAW_QUERY_COUNT = 13
DISCARDED_QUERY_COUNT = 2
ANALYZED_QUERY_COUNT = RAW_QUERY_COUNT - DISCARDED_QUERY_COUNT
EXPECTED_CALLS = 12
EXPECTED_SUBGROUPS = 5120

# "Material" counter regressions are interpreted conservatively. These are
# guardrails, not performance-selection thresholds.
MAX_READ_BYTES_REGRESSION = 0.05
MAX_STALL_REGRESSION_PP = 2.0
MIN_OCCUPANCY_DELTA_PP = -2.0
MIN_EU_ACTIVE_DELTA_PP = -2.0

NATIVE_PATH = (
    "csrc/xpu/grouped_gemm/xe_2/grouped_gemm_xe2_interface.hpp"
)
PYTHON_PATH = "vllm_xpu_kernels/fused_moe_interface.py"

METRIC_FIELDS = (
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


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def git_output(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def extract_block(text: str, start: str, end: str, label: str) -> str:
    require(text.count(start) == 1, f"{label}: start marker is not unique")
    start_index = text.index(start)
    require(text.count(end, start_index) == 1, f"{label}: end marker is not unique")
    end_index = text.index(end, start_index)
    return text[start_index:end_index]


def source_contract(kernel_root: Path) -> dict[str, Any]:
    head = git_output(kernel_root, "rev-parse", "HEAD").strip()
    require(head == EXPECTED_KERNEL_HEAD, f"wrong kernel HEAD: {head}")
    require(
        not git_output(kernel_root, "status", "--porcelain").strip(),
        "kernel worktree is dirty",
    )

    baseline_native = git_output(
        kernel_root, "show", f"{BASELINE_KERNEL_HEAD}:{NATIVE_PATH}"
    )
    candidate_native = git_output(
        kernel_root, "show", f"{EXPECTED_KERNEL_HEAD}:{NATIVE_PATH}"
    )
    native_start = "    if (w1_only) return;\n"
    native_end = "\n  return output;\n}\n\nat::Tensor cutlass_grouped_gemm_m2"
    baseline_native_block = extract_block(
        baseline_native, native_start, native_end, "baseline native W2"
    )
    candidate_native_block = extract_block(
        candidate_native, native_start, native_end, "candidate native W2"
    )
    require(
        candidate_native_block == baseline_native_block,
        "native W2 launcher block changed from the approved baseline",
    )
    require(
        candidate_native_block.count(
            "M8TopkInt4W2ReduceLauncher<w4a16_policy_m_8, id_type>"
        )
        == 1,
        "native incumbent N64 W2 launcher is not present exactly once",
    )

    baseline_python = git_output(
        kernel_root, "show", f"{BASELINE_KERNEL_HEAD}:{PYTHON_PATH}"
    )
    candidate_python = git_output(
        kernel_root, "show", f"{EXPECTED_KERNEL_HEAD}:{PYTHON_PATH}"
    )
    python_start = (
        "                # Keep only the exact W1+BF16-SiLU launch from the fused\n"
    )
    python_end = "            route_buffer = (\n"
    baseline_python_block = extract_block(
        baseline_python, python_start, python_end, "baseline Python W2/gather"
    )
    candidate_python_block = extract_block(
        candidate_python, python_start, python_end, "candidate Python W2/gather"
    )
    require(
        candidate_python_block == baseline_python_block,
        "Python W2/gather call block changed from the approved baseline",
    )
    for call in (
        "torch.ops._xpu_C.cutlass_grouped_gemm_m8_topk_int4_interface(",
        "torch.ops._moe_C.moe_gather(",
    ):
        require(
            candidate_python_block.count(call) == 1,
            f"{call} is not present exactly once in the unchanged block",
        )

    return {
        "passed": True,
        "baseline_commit": BASELINE_KERNEL_HEAD,
        "candidate_commit": EXPECTED_KERNEL_HEAD,
        "native_w2_block_identical": True,
        "native_w2_block_sha256": sha256_bytes(
            candidate_native_block.encode()
        ),
        "python_w2_gather_block_identical": True,
        "python_w2_gather_block_sha256": sha256_bytes(
            candidate_python_block.encode()
        ),
        "w2_policy": "w4a16_policy_m_8 (N64)",
        "native_w2_launcher_count": 1,
        "python_w2_call_count": 1,
        "python_gather_call_count": 1,
    }


def load_metric_rows(path: Path) -> list[dict[str, str]]:
    lines = path.read_text().splitlines()
    header_indexes = [
        index for index, line in enumerate(lines) if line.startswith("Kernel,")
    ]
    require(len(header_indexes) == 1, f"{path}: expected one CSV header")
    reader = csv.DictReader(lines[header_indexes[0] :])
    rows = [row for row in reader if row.get("Kernel")]
    require(
        len(rows) == RAW_QUERY_COUNT,
        f"{path}: expected {RAW_QUERY_COUNT} selected W1 queries, got {len(rows)}",
    )
    return rows


def numeric(row: dict[str, str], field: str, path: Path) -> float:
    require(field in row and row[field] != "", f"{path}: missing {field}")
    return float(row[field])


def mean_field(
    rows: list[dict[str, str]], field: str, path: Path
) -> float:
    return fmean(numeric(row, field, path) for row in rows)


def parse_csv_section(
    path: Path,
    section_start: str,
    section_end: str | None,
) -> list[dict[str, str]]:
    text = path.read_text()
    require(section_start in text, f"{path}: missing {section_start}")
    section = text.split(section_start, maxsplit=1)[1]
    if section_end is not None:
        require(section_end in section, f"{path}: missing {section_end}")
        section = section.split(section_end, maxsplit=1)[0]
    lines = [line.strip() for line in section.splitlines() if line.strip()]
    header_indexes = [
        index for index, line in enumerate(lines) if line.startswith("Kernel,")
    ]
    require(
        len(header_indexes) == 1,
        f"{path}: expected one CSV header in {section_start}",
    )
    reader = csv.reader(lines[header_indexes[0] :], skipinitialspace=True)
    parsed = list(reader)
    header = [cell.strip() for cell in parsed[0]]
    return [
        dict(zip(header, (cell.strip() for cell in row), strict=True))
        for row in parsed[1:]
        if row and row[0].strip()
    ]


def kernel_properties(path: Path) -> list[dict[str, str]]:
    return parse_csv_section(path, "=== Kernel Properties ===", None)


def device_timing_rows(path: Path) -> list[dict[str, str]]:
    return parse_csv_section(
        path,
        "=== Device Timing Summary ===",
        "=== Kernel Properties ===",
    )


def normalize_kernel_name(name: str) -> str:
    return (
        name.replace("w4a16_policy_m_8_n_128", "w4a16_policy_m_8")
        .replace("{1; 640; 1} {128; 1; 1}", "{1; 1280; 1} {64; 1; 1}")
    )


def profile_metrics(path: Path, tile: int) -> dict[str, Any]:
    raw_rows = load_metric_rows(path)
    rows = raw_rows[DISCARDED_QUERY_COUNT:]
    require(
        len(rows) == ANALYZED_QUERY_COUNT,
        f"{path}: counter reduction produced the wrong query count",
    )
    kernel_names = {row["Kernel"] for row in raw_rows}
    require(len(kernel_names) == 1, f"{path}: selected multiple kernel names")
    kernel_name = next(iter(kernel_names))
    policy = "w4a16_policy_m_8" if tile == 64 else "w4a16_policy_m_8_n_128"
    groups = 1280 if tile == 64 else 640
    require(f"MoE::{policy}," in kernel_name, f"{path}: wrong W1 policy")
    require(
        f"{{1; {groups}; 1}} {{{tile}; 1; 1}}" in kernel_name,
        f"{path}: wrong W1 launch shape",
    )
    require("<int," in kernel_name, f"{path}: not the production int32 kernel")
    require(", true>" in kernel_name, f"{path}: route interleave is not enabled")

    timing_path = path.with_name(path.name.replace(".metrics.", "."))
    require(timing_path.is_file(), f"{path}: missing paired timing/properties file")
    properties = [
        row
        for row in kernel_properties(timing_path)
        if "GemmM8TopkInt4W1SiluCuteName" in row["Kernel"]
    ]
    require(len(properties) == 1, f"{timing_path}: wrong W1 property rows")
    require(
        int(properties[0]["Spill Memory Per Thread"]) == 0,
        f"{timing_path}: W1 has spill memory",
    )
    require(
        int(properties[0]["SLM Per Work Group"]) == 0,
        f"{timing_path}: W1 has SLM allocation",
    )

    expected_ids = sorted(
        int(numeric(row, "GlobalInstanceId", path)) for row in raw_rows
    )
    actual_ids = [int(numeric(row, "GlobalInstanceId", path)) for row in raw_rows]
    require(actual_ids == expected_ids, f"{path}: query IDs are not ordered")
    require(len(set(actual_ids)) == RAW_QUERY_COUNT, f"{path}: duplicate query ID")

    for row in raw_rows:
        for field in ZERO_VALIDITY_FIELDS:
            require(numeric(row, field, path) == 0.0, f"{path}: invalid {field}")
        require(
            numeric(row, "ReportsCount", path) == 1.0,
            f"{path}: expected one report per query",
        )
        require(
            numeric(row, "ASYNC_GPGPU_THREADGROUP_COUNT[events]", path)
            == groups,
            f"{path}: wrong workgroup count",
        )
        require(
            numeric(row, "ASYNC_GPGPU_THREAD_EXIT_COUNT[messages]", path)
            == EXPECTED_SUBGROUPS,
            f"{path}: wrong subgroup/output ownership",
        )
        for field in (
            "LOAD_STORE_CACHE_BYTE_WRITE[bytes]",
            "LOAD_STORE_CACHE_PARTIAL_WRITE_COUNT[events]",
            "SLM_BANK_CONFLICT_COUNT[events]",
            "SLM_BYTE_READ[bytes]",
            "SLM_BYTE_WRITE[bytes]",
        ):
            require(
                numeric(row, field, path) == 0.0,
                f"{path}: nonzero spill/SLM proxy {field}",
            )

    return {
        "path": str(path),
        "sha256": sha256_file(path),
        "timing_properties_path": str(timing_path),
        "timing_properties_sha256": sha256_file(timing_path),
        "raw_selected_queries": RAW_QUERY_COUNT,
        "discarded_queries": DISCARDED_QUERY_COUNT,
        "discard_reason": "explicit warmup plus first settling query",
        "analyzed_queries": ANALYZED_QUERY_COUNT,
        "reduction": "arithmetic mean of selected-kernel rows[2:]",
        "kernel_name": kernel_name,
        "normalized_kernel_name": normalize_kernel_name(kernel_name),
        "tile": tile,
        "workgroups": groups,
        "subgroups_per_workgroup": tile // 16,
        "total_subgroups": groups * (tile // 16),
        "all_query_reports_valid": True,
        "spill_memory_per_thread": 0,
        "slm_per_workgroup": 0,
        "zero_lsc_writes": True,
        "zero_slm_traffic": True,
        "mean": {
            field: mean_field(rows, field, path) for field in METRIC_FIELDS
        },
    }


def find_trace_timing_path(trace_dir: Path, prefix: str) -> Path:
    paths = [
        path
        for path in sorted(trace_dir.glob(f"{prefix}-unitrace.*"))
        if ".metrics." not in path.name
        and "GemmM8TopkInt4W1SiluCuteName" in path.read_text()
        and "GemmM8TopkInt4CuteName" in path.read_text()
        and "MoeGather" in path.read_text()
    ]
    require(
        len(paths) == 1,
        f"{trace_dir}: expected one complete timing trace for {prefix}",
    )
    return paths[0]


def selected_trace_kernels(path: Path) -> dict[str, dict[str, Any]]:
    timing = device_timing_rows(path)
    properties = kernel_properties(path)
    families = {
        "w1": lambda name: "GemmM8TopkInt4W1SiluCuteName" in name,
        "w2": lambda name: (
            "GemmM8TopkInt4CuteName" in name
            and "GemmM8TopkInt4W1SiluCuteName" not in name
        ),
        "gather": lambda name: "MoeGather" in name,
    }
    selected: dict[str, dict[str, Any]] = {}
    for family, matches in families.items():
        timing_rows = [row for row in timing if matches(row["Kernel"])]
        property_rows = [row for row in properties if matches(row["Kernel"])]
        require(len(timing_rows) == 1, f"{path}: wrong {family} timing rows")
        require(len(property_rows) == 1, f"{path}: wrong {family} property rows")
        timing_row = timing_rows[0]
        property_row = property_rows[0]
        require(
            int(timing_row["Calls"]) == RAW_QUERY_COUNT,
            f"{path}: wrong {family} call count",
        )
        selected[family] = {
            "kernel_name": timing_row["Kernel"],
            "calls": int(timing_row["Calls"]),
            "total_time_ns": int(timing_row["Time (ns)"]),
            "average_time_ns": int(timing_row["Average (ns)"]),
            "compiled": property_row["Compiled"],
            "simd": int(property_row["SIMD"]),
            "slm_per_workgroup": int(property_row["SLM Per Work Group"]),
            "private_memory_per_thread": int(
                property_row["Private Memory Per Thread"]
            ),
            "spill_memory_per_thread": int(
                property_row["Spill Memory Per Thread"]
            ),
            "register_file_size_per_thread": int(
                property_row["Register File Size Per Thread"]
            ),
        }
    require(
        selected["w1"]["spill_memory_per_thread"] == 0,
        f"{path}: traced W1 has spill memory",
    )
    return selected


def analyze_trace_card(trace_dir: Path) -> dict[str, Any]:
    harness_paths = sorted(trace_dir.glob("card*-*-n*-full-trace-harness.json"))
    require(len(harness_paths) == 2, f"{trace_dir}: expected two trace harnesses")
    traces: dict[str, dict[str, Any]] = {}
    rank: int | None = None
    physical: dict[str, Any] | None = None
    fixture: dict[str, Any] | None = None
    for harness_path in harness_paths:
        match = re.fullmatch(
            r"card([0-3])-([AB])-n(64|128)-full-trace-harness\.json",
            harness_path.name,
        )
        require(match is not None, f"{harness_path}: unexpected trace filename")
        file_rank = int(match.group(1))
        arm = match.group(2)
        tile = int(match.group(3))
        require(
            (arm, tile) in (("A", 64), ("B", 128)),
            f"{harness_path}: wrong trace treatment",
        )
        rank = file_rank if rank is None else rank
        require(rank == file_rank, f"{trace_dir}: mixed trace ranks")

        harness = json.loads(harness_path.read_text())
        require(harness["passed"] is None, f"{harness_path}: false trace pass")
        require(
            harness["trace_gate_evaluated"] is False,
            f"{harness_path}: harness pre-classified trace",
        )
        trace = harness["trace"]
        require(trace["rank"] == rank, f"{harness_path}: trace rank mismatch")
        require(trace["tile"] == tile, f"{harness_path}: trace tile mismatch")
        require(
            trace["mode"] == f"trace-n{tile}",
            f"{harness_path}: trace mode mismatch",
        )
        require(trace["calls"] == EXPECTED_CALLS, f"{harness_path}: trace calls")
        require(
            trace["completion_boundary_per_complete_path"] is True,
            f"{harness_path}: no full-path completion boundary",
        )
        require(
            trace["expected_selected_kernels_per_call"]
            == {"w1": 1, "w2": 1, "gather": 1},
            f"{harness_path}: wrong selected-kernel contract",
        )

        runtime = harness["runtime"]
        require(
            runtime["extension_sha256"] == EXPECTED_EXTENSION_SHA256,
            f"{harness_path}: extension hash mismatch",
        )
        require(
            runtime["grouped_gemm_sha256"] == EXPECTED_GROUPED_SHA256,
            f"{harness_path}: grouped-GEMM hash mismatch",
        )
        require(
            runtime["ze_affinity_mask"] == str(rank),
            f"{harness_path}: affinity mismatch",
        )
        require(
            runtime["oneapi_device_selector"] == "level_zero:0",
            f"{harness_path}: selector mismatch",
        )
        trace_fixture = trace["real_production_fixture_identity"]
        require(
            trace_fixture["sha256"] == EXPECTED_FIXTURE_SHA256,
            f"{harness_path}: fixture artifact mismatch",
        )
        if physical is None:
            physical = runtime["physical_device"]
            fixture = trace_fixture
        else:
            require(
                runtime["physical_device"] == physical,
                f"{trace_dir}: trace physical identity changed",
            )
            require(
                trace_fixture == fixture,
                f"{trace_dir}: trace fixture identity changed",
            )

        prefix = harness_path.name.removesuffix("-harness.json")
        timing_path = find_trace_timing_path(trace_dir, prefix)
        traces[arm] = {
            "harness_path": str(harness_path),
            "harness_sha256": sha256_file(harness_path),
            "timing_path": str(timing_path),
            "timing_sha256": sha256_file(timing_path),
            "kernels": selected_trace_kernels(timing_path),
        }

    require(set(traces) == {"A", "B"}, f"{trace_dir}: missing trace arm")
    control_kernels = traces["A"]["kernels"]
    candidate_kernels = traces["B"]["kernels"]
    require(
        normalize_kernel_name(control_kernels["w1"]["kernel_name"])
        == normalize_kernel_name(candidate_kernels["w1"]["kernel_name"]),
        f"{trace_dir}: W1 trace differs beyond the policy",
    )
    for family in ("w2", "gather"):
        require(
            control_kernels[family]["kernel_name"]
            == candidate_kernels[family]["kernel_name"],
            f"{trace_dir}: {family} kernel name changed",
        )
        require(
            control_kernels[family]["calls"]
            == candidate_kernels[family]["calls"]
            == RAW_QUERY_COUNT,
            f"{trace_dir}: {family} call count changed",
        )
    return {
        "rank": rank,
        "physical_device": physical,
        "fixture": fixture,
        "traces": traces,
        "w1_differs_only_by_policy": True,
        "w2_kernel_name_and_call_count_identical": True,
        "gather_kernel_name_and_call_count_identical": True,
        "passed": True,
    }


def find_metric_path(card_dir: Path, prefix: str) -> Path:
    paths = sorted(card_dir.glob(f"{prefix}-unitrace.metrics.*"))
    require(len(paths) == 1, f"{card_dir}: expected one metrics file for {prefix}")
    return paths[0]


def analyze_card(card_dir: Path) -> dict[str, Any]:
    harness_paths = sorted(card_dir.glob("card*-*-n*-harness.json"))
    require(len(harness_paths) == 4, f"{card_dir}: expected four harness results")
    profiles: dict[str, dict[str, Any]] = {}
    rank: int | None = None
    physical: dict[str, Any] | None = None
    common_identity: dict[str, Any] | None = None

    for harness_path in harness_paths:
        match = re.fullmatch(
            r"card([0-3])-(A1|B1|B2|A2)-n(64|128)-harness\.json",
            harness_path.name,
        )
        require(match is not None, f"{harness_path}: unexpected filename")
        file_rank = int(match.group(1))
        arm = match.group(2)
        tile = int(match.group(3))
        require(EXPECTED_ARMS[arm] == tile, f"{harness_path}: wrong arm tile")
        rank = file_rank if rank is None else rank
        require(rank == file_rank, f"{card_dir}: mixed declared ranks")

        harness = json.loads(harness_path.read_text())
        require(harness["passed"] is None, f"{harness_path}: false counter pass")
        require(
            harness["counter_gate_evaluated"] is False,
            f"{harness_path}: harness pre-classified counters",
        )
        counter = harness["counter"]
        require(counter["rank"] == rank, f"{harness_path}: rank mismatch")
        require(counter["tile"] == tile, f"{harness_path}: tile mismatch")
        require(
            counter["mode"] == f"counter-n{tile}",
            f"{harness_path}: mode mismatch",
        )
        require(counter["calls"] == EXPECTED_CALLS, f"{harness_path}: call count")
        require(
            counter["completion_boundary_per_call"] is True,
            f"{harness_path}: no completion boundary",
        )

        runtime = harness["runtime"]
        require(
            runtime["extension_sha256"] == EXPECTED_EXTENSION_SHA256,
            f"{harness_path}: extension hash mismatch",
        )
        require(
            runtime["grouped_gemm_sha256"] == EXPECTED_GROUPED_SHA256,
            f"{harness_path}: grouped-GEMM hash mismatch",
        )
        require(
            runtime["ze_affinity_mask"] == str(rank),
            f"{harness_path}: affinity mismatch",
        )
        require(
            runtime["oneapi_device_selector"] == "level_zero:0",
            f"{harness_path}: selector mismatch",
        )
        identity = counter["real_production_fixture_identity"]
        require(
            identity["sha256"] == EXPECTED_FIXTURE_SHA256,
            f"{harness_path}: fixture artifact mismatch",
        )
        require(
            identity["aggregate_tensor_sha256"] == EXPECTED_FIXTURE_TENSOR_SHA256,
            f"{harness_path}: fixture tensor mismatch",
        )
        require(
            identity["production_source_aggregate_sha256"]
            == EXPECTED_FIXTURE_SOURCE_SHA256,
            f"{harness_path}: fixture source mismatch",
        )
        if physical is None:
            physical = runtime["physical_device"]
            common_identity = {
                "extension_sha256": runtime["extension_sha256"],
                "grouped_gemm_sha256": runtime["grouped_gemm_sha256"],
                "fixture": identity,
            }
        else:
            require(
                runtime["physical_device"] == physical,
                f"{card_dir}: physical identity changed within A-B-B-A",
            )
            require(
                identity == common_identity["fixture"],
                f"{card_dir}: fixture identity changed within A-B-B-A",
            )

        prefix = harness_path.name.removesuffix("-harness.json")
        metric_path = find_metric_path(card_dir, prefix)
        profiles[arm] = {
            "harness_path": str(harness_path),
            "harness_sha256": sha256_file(harness_path),
            "metrics": profile_metrics(metric_path, tile),
        }

    require(set(profiles) == set(EXPECTED_ARMS), f"{card_dir}: missing arm")
    normalized_names = {
        profile["metrics"]["normalized_kernel_name"]
        for profile in profiles.values()
    }
    require(
        len(normalized_names) == 1,
        f"{card_dir}: W1 kernels differ by more than policy/launch shape",
    )

    means = {
        arm: profile["metrics"]["mean"] for arm, profile in profiles.items()
    }
    control = {
        field: fmean((means["A1"][field], means["A2"][field]))
        for field in METRIC_FIELDS
    }
    candidate = {
        field: fmean((means["B1"][field], means["B2"][field]))
        for field in METRIC_FIELDS
    }
    deltas = {
        "gpu_time_fraction": (
            control["GpuTime[ns]"] - candidate["GpuTime[ns]"]
        )
        / control["GpuTime[ns]"],
        "eu_active_pp": candidate["XVE_ACTIVE[%]"] - control["XVE_ACTIVE[%]"],
        "stall_pp": candidate["XVE_STALL[%]"] - control["XVE_STALL[%]"],
        "occupancy_pp": (
            candidate["XVE_THREADS_OCCUPANCY_ALL[%]"]
            - control["XVE_THREADS_OCCUPANCY_ALL[%]"]
        ),
        "dram_read_bytes_fraction": (
            candidate["GPU_MEMORY_BYTE_READ[bytes]"]
            / control["GPU_MEMORY_BYTE_READ[bytes]"]
            - 1.0
        ),
        "lsc_read_bytes_fraction": (
            candidate["LOAD_STORE_CACHE_BYTE_READ[bytes]"]
            / control["LOAD_STORE_CACHE_BYTE_READ[bytes]"]
            - 1.0
        ),
    }
    paired_time_wins = {
        "A1_vs_B1": (
            means["B1"]["GpuTime[ns]"] < means["A1"]["GpuTime[ns]"]
        ),
        "A2_vs_B2": (
            means["B2"]["GpuTime[ns]"] < means["A2"]["GpuTime[ns]"]
        ),
    }
    gates = {
        "both_matched_counter_pairs_faster": all(paired_time_wins.values()),
        "aggregate_counter_time_faster": deltas["gpu_time_fraction"] > 0.0,
        "dram_read_bytes_not_materially_higher": (
            deltas["dram_read_bytes_fraction"] <= MAX_READ_BYTES_REGRESSION
        ),
        "lsc_read_bytes_not_materially_higher": (
            deltas["lsc_read_bytes_fraction"] <= MAX_READ_BYTES_REGRESSION
        ),
        "stall_not_materially_higher": (
            deltas["stall_pp"] <= MAX_STALL_REGRESSION_PP
        ),
        "occupancy_not_materially_lower": (
            deltas["occupancy_pp"] >= MIN_OCCUPANCY_DELTA_PP
        ),
        "eu_activity_not_materially_lower": (
            deltas["eu_active_pp"] >= MIN_EU_ACTIVE_DELTA_PP
        ),
        "zero_spill_proxies": all(
            profile["metrics"]["zero_lsc_writes"]
            and profile["metrics"]["zero_slm_traffic"]
            for profile in profiles.values()
        ),
        "same_kernel_except_w1_policy_and_launch_shape": (
            len(normalized_names) == 1
        ),
        "same_total_subgroup_ownership": all(
            profile["metrics"]["total_subgroups"] == EXPECTED_SUBGROUPS
            for profile in profiles.values()
        ),
    }
    return {
        "rank": rank,
        "physical_device": physical,
        "common_identity": common_identity,
        "profiles": profiles,
        "reduced_control_mean": control,
        "reduced_candidate_mean": candidate,
        "paired_time_wins": paired_time_wins,
        "deltas": deltas,
        "gates": gates,
        "passed": all(gates.values()),
    }


def write_markdown(summary: dict[str, Any], path: Path) -> None:
    lines = [
        "# Laguna routed-W1 N128 matched counter summary",
        "",
        f"Overall pass: **{summary['passed']}**",
        "",
        "| Card | Counter time N64 -> N128 (us) | Improvement | "
        "EU active delta | Stall delta | Occupancy delta | "
        "DRAM bytes delta | LSC bytes delta |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for card in summary["cards"]:
        control = card["reduced_control_mean"]
        candidate = card["reduced_candidate_mean"]
        delta = card["deltas"]
        lines.append(
            f"| {card['rank']} | {control['GpuTime[ns]'] / 1000:.6f} -> "
            f"{candidate['GpuTime[ns]'] / 1000:.6f} | "
            f"{100 * delta['gpu_time_fraction']:.3f}% | "
            f"{delta['eu_active_pp']:+.3f} pp | "
            f"{delta['stall_pp']:+.3f} pp | "
            f"{delta['occupancy_pp']:+.3f} pp | "
            f"{100 * delta['dram_read_bytes_fraction']:+.3f}% | "
            f"{100 * delta['lsc_read_bytes_fraction']:+.3f}% |"
        )
    aggregate = summary["aggregate"]
    lines.extend(
        [
            "",
            "Historical reduction: discard the explicit warmup and first "
            "settling query, then arithmetic-mean the remaining 11 selected "
            "W1 queries.",
            "",
            f"Four-card mean counter-time improvement: "
            f"**{100 * aggregate['mean_counter_time_improvement']:.3f}%**.",
            "",
            "Every query retained 5,120 completed subgroups. N64 used "
            "1,280 workgroups × 4 subgroups; N128 used 640 × 8. All query "
            "reports were valid, and every arm had zero LSC writes, zero "
            "partial writes, and zero SLM traffic.",
            "",
            "The approved-baseline and candidate source blocks for native "
            "W2 plus the Python route-parallel W2/gather calls are byte-for-"
            "byte identical.",
            "",
        ]
    )
    path.write_text("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--card-dir",
        type=Path,
        action="append",
        required=True,
        help="Repeat exactly four times, once per physical-card A-B-B-A capture",
    )
    parser.add_argument(
        "--kernel-root",
        type=Path,
        default=Path("/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc"),
    )
    parser.add_argument(
        "--trace-dir",
        type=Path,
        action="append",
        required=True,
        help="Repeat exactly four times, once per physical-card full-path pair",
    )
    parser.add_argument(
        "--unitrace",
        type=Path,
        default=Path("/home/steve/src/pti-gpu/build-unitrace/unitrace"),
    )
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--markdown", type=Path)
    args = parser.parse_args()

    require(len(args.card_dir) == 4, "exactly four --card-dir values are required")
    require(
        len(args.trace_dir) == 4,
        "exactly four --trace-dir values are required",
    )
    require(
        sha256_file(args.unitrace) == EXPECTED_UNITRACE_SHA256,
        "unitrace binary hash mismatch",
    )
    unitrace_commit = git_output(
        args.unitrace.parents[1], "rev-parse", "HEAD"
    ).strip()
    require(
        unitrace_commit == EXPECTED_UNITRACE_COMMIT,
        f"unitrace source commit mismatch: {unitrace_commit}",
    )

    cards = sorted(
        (analyze_card(path.resolve()) for path in args.card_dir),
        key=lambda card: card["rank"],
    )
    require([card["rank"] for card in cards] == [0, 1, 2, 3], "wrong rank set")
    require(all(card["passed"] for card in cards), "one or more cards failed")
    uuids = {card["physical_device"]["uuid"] for card in cards}
    bdfs = {card["physical_device"]["pci_bdf_address"] for card in cards}
    require(len(uuids) == 4, "physical UUIDs are not distinct")
    require(len(bdfs) == 4, "physical PCI BDFs are not distinct")

    traces = sorted(
        (analyze_trace_card(path.resolve()) for path in args.trace_dir),
        key=lambda trace: trace["rank"],
    )
    require(
        [trace["rank"] for trace in traces] == [0, 1, 2, 3],
        "wrong trace rank set",
    )
    require(all(trace["passed"] for trace in traces), "one or more traces failed")
    for card, trace in zip(cards, traces, strict=True):
        require(
            card["physical_device"] == trace["physical_device"],
            f"rank {card['rank']}: counter and trace physical identity differ",
        )
        require(
            card["common_identity"]["fixture"] == trace["fixture"],
            f"rank {card['rank']}: counter and trace fixtures differ",
        )

    static_source = source_contract(args.kernel_root.resolve())
    summary = {
        "format": "laguna-w1-n128-counter-gate-v1",
        "passed": True,
        "endpoint_authorized": False,
        "historical_reduction": {
            "raw_selected_queries": RAW_QUERY_COUNT,
            "discarded_queries": DISCARDED_QUERY_COUNT,
            "analyzed_queries": ANALYZED_QUERY_COUNT,
            "reduction": "arithmetic mean of selected-kernel rows[2:]",
        },
        "thresholds": {
            "max_read_bytes_regression_fraction": MAX_READ_BYTES_REGRESSION,
            "max_stall_regression_pp": MAX_STALL_REGRESSION_PP,
            "min_occupancy_delta_pp": MIN_OCCUPANCY_DELTA_PP,
            "min_eu_active_delta_pp": MIN_EU_ACTIVE_DELTA_PP,
        },
        "unitrace": {
            "path": str(args.unitrace.resolve()),
            "sha256": EXPECTED_UNITRACE_SHA256,
            "source_commit": unitrace_commit,
            "version": "2.4.0",
            "metric_group": "ComputeBasic",
        },
        "static_source_contract": static_source,
        "cards": cards,
        "full_path_traces": traces,
        "aggregate": {
            "all_cards_passed": True,
            "distinct_physical_uuids": len(uuids),
            "distinct_physical_bdfs": len(bdfs),
            "mean_counter_time_improvement": fmean(
                card["deltas"]["gpu_time_fraction"] for card in cards
            ),
            "min_counter_time_improvement": min(
                card["deltas"]["gpu_time_fraction"] for card in cards
            ),
            "max_counter_time_improvement": max(
                card["deltas"]["gpu_time_fraction"] for card in cards
            ),
            "mean_eu_active_delta_pp": fmean(
                card["deltas"]["eu_active_pp"] for card in cards
            ),
            "mean_stall_delta_pp": fmean(
                card["deltas"]["stall_pp"] for card in cards
            ),
            "mean_occupancy_delta_pp": fmean(
                card["deltas"]["occupancy_pp"] for card in cards
            ),
            "max_dram_read_bytes_regression_fraction": max(
                card["deltas"]["dram_read_bytes_fraction"] for card in cards
            ),
            "max_lsc_read_bytes_regression_fraction": max(
                card["deltas"]["lsc_read_bytes_fraction"] for card in cards
            ),
            "all_profiles_zero_spill_proxies": True,
            "all_profiles_total_subgroups": EXPECTED_SUBGROUPS,
            "all_full_path_traces_passed": True,
            "all_w2_names_and_counts_identical": True,
            "all_gather_names_and_counts_identical": True,
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, indent=2) + "\n")
    if args.markdown is not None:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        write_markdown(summary, args.markdown)
    print(json.dumps(summary["aggregate"], sort_keys=True))


if __name__ == "__main__":
    main()
