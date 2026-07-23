#!/usr/bin/env python3
"""Offline-only parser repair for one sealed Laguna counter campaign.

The original counter analyzer correctly failed closed because it assumed the
device-timing CSV contained only the selected GEMM.  The pinned unitrace emits
five fixture-related memory-copy summary rows alongside that GEMM.  This tool
leaves the execution packet, campaign, metric parser, evidence validator,
comparison logic, and thresholds unchanged.  It replaces only the
timing/property parser under a separately committed repair authorization and
writes to a new sibling NVMe result root.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any


MAIN_REPO = Path("/home/steve/llm-optimizations")
TOOLS_DIR = MAIN_REPO / "experiments/laguna-s-2.1-xpu-b70/tools"
ORIGINAL_RUNNER = TOOLS_DIR / "run_laguna_shared_down_mm_counters.py"
ORIGINAL_ANALYZER = TOOLS_DIR / "analyze_laguna_shared_down_mm_counters.py"
REPAIR_ANALYZER = TOOLS_DIR / "analyze_laguna_shared_down_mm_counters_repair.py"
REPAIR_TEST = TOOLS_DIR / "test_analyze_laguna_shared_down_mm_counters_repair.py"
EXECUTION_AUTHORIZATION = (
    MAIN_REPO / "data/laguna-s-2.1-shared-down-m8-counter-authorization-20260723.json"
)
REPAIR_AUTHORIZATION_RELATIVE = Path(
    "data/laguna-s-2.1-shared-down-m8-counter-analysis-repair-"
    "authorization-20260723.json"
)
REPAIR_AUTHORIZATION = MAIN_REPO / REPAIR_AUTHORIZATION_RELATIVE
RUNS_ROOT = Path("/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs")
CAMPAIGN_ROOT = RUNS_ROOT / "shared-down-m8-counters-20260723T173812Z"
CAMPAIGN_OPEN = CAMPAIGN_ROOT / "campaign.open.json"
CAMPAIGN_COMPLETE = CAMPAIGN_ROOT / "campaign.complete.json"
EXPECTED_EXECUTION_AUTHORIZATION_SHA256 = (
    "3b8aa2cf10f27e50ccae778071b8d0b96480dd7c03a852b7199cb0de40928b1a"
)
EXPECTED_ORIGINAL_RUNNER_SHA256 = (
    "2c551194c55886138dab88854782ce9d008532fe358f8cf4bb1f1d502de3f0ab"
)
EXPECTED_ORIGINAL_ANALYZER_SHA256 = (
    "d3b8472556b558d92a2e73617ed7d968e03920126af71cba67719dae8f73fa24"
)
EXPECTED_CAMPAIGN_OPEN_SHA256 = (
    "c2ae3b524d010e118df0be0fed17e5c81718dc5376f38db8ca3d3c9ac3ccbb46"
)
EXPECTED_CAMPAIGN_COMPLETE_SHA256 = (
    "164d124d7d88b9ec4dd3a7f1280feb7ec274538fb9ccc842f62671e951562c12"
)
RAW_QUERY_COUNT = 13
TIME_PERCENT_ABSOLUTE_TOLERANCE = 0.000005
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
AUXILIARY_TIMING_CALLS = {
    "zeCommandListAppendMemoryCopy(D2M)[1572864]": 2,
    "zeCommandListAppendMemoryCopy(M2D)[1572864]": 1,
    "zeCommandListAppendMemoryCopy(D2M)[49152]": 13,
    "zeCommandListAppendMemoryCopy(D2M)[4096]": 2,
    "zeCommandListAppendMemoryCopy(M2D)[4096]": 1,
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_argument(value: str) -> str:
    normalized = value.lower()
    if re.fullmatch(r"[0-9a-f]{64}", normalized) is None:
        raise argparse.ArgumentTypeError("expected a 64-digit SHA-256")
    return normalized


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


def csv_rows(
    lines: list[str],
    path: Path,
    label: str,
    expected_fields: tuple[str, ...],
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
        all(
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


def expected_parser_contract() -> dict[str, Any]:
    return {
        "repair_scope": "device-timing and kernel-property parser only",
        "metric_parser": "unchanged original analyzer",
        "campaign_evidence_validator": "unchanged original analyzer",
        "comparison_and_thresholds": "unchanged original analyzer",
        "timing_rows": {
            "exact_row_count": 6,
            "order": (
                "order-insensitive exact identity set; unitrace orders rows by "
                "measured time"
            ),
            "selected_kernel": {
                "identity": "exact metric-query verbose SIMD16 kernel name",
                "calls": RAW_QUERY_COUNT,
            },
            "auxiliary_name_to_calls": AUXILIARY_TIMING_CALLS,
            "no_other_rows": True,
        },
        "timing_arithmetic": {
            "decimal_integer_fields": [
                "Calls",
                "Time (ns)",
                "Average (ns)",
                "Min (ns)",
                "Max (ns)",
            ],
            "average": "Time (ns) // Calls",
            "range": "Calls * Min <= Time <= Calls * Max",
            "row_time_sum_equals_reported_l0_device_time": True,
            "time_percent_matches_row_fraction": True,
            "time_percent_sum": 100.0,
            "absolute_tolerance": TIME_PERCENT_ABSOLUTE_TOLERANCE,
        },
        "selected_kernel_property": {
            "exact_row_count": 1,
            "compiled": "AOT",
            "simd": 16,
            "number_of_arguments": 15,
            "slm_per_work_group": 0,
            "private_memory_per_thread": 0,
            "spill_memory_per_thread": 0,
            "register_file_size_per_thread": 256,
        },
    }


def parse_timing_row(
    row: dict[str, str],
    *,
    path: Path,
    expected_calls: int,
) -> dict[str, Any]:
    calls = integer(row, "Calls", path)
    time_ns = integer(row, "Time (ns)", path)
    time_percent = numeric(row, "Time (%)", path)
    average_ns = integer(row, "Average (ns)", path)
    minimum_ns = integer(row, "Min (ns)", path)
    maximum_ns = integer(row, "Max (ns)", path)
    require(calls == expected_calls, f"{path}: timing Calls drift for {row['Kernel']}")
    require(
        time_ns > 0
        and time_percent > 0.0
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
        "time_percent": time_percent,
        "average_ns": average_ns,
        "minimum_ns": minimum_ns,
        "maximum_ns": maximum_ns,
    }


def parse_timing_properties_repair(
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
    timing_by_name = {row["Kernel"]: row for row in timing_rows}
    expected_names = {expected_kernel_name, *AUXILIARY_TIMING_CALLS}
    require(
        len(timing_rows) == len(timing_by_name) == 6
        and set(timing_by_name) == expected_names,
        f"{path}: timing rows are not the exact selected-GEMM plus copy set",
    )
    parsed_by_name = {
        name: parse_timing_row(
            row,
            path=path,
            expected_calls=(
                RAW_QUERY_COUNT
                if name == expected_kernel_name
                else AUXILIARY_TIMING_CALLS[name]
            ),
        )
        for name, row in timing_by_name.items()
    }
    total_matches = re.findall(
        r"(?m)^\s*Total Device Time for L0 backend \(ns\):\s*([0-9]+)\s*$",
        text,
    )
    require(
        len(total_matches) == 1,
        f"{path}: require one decimal L0 total-device-time field",
    )
    total_device_time_ns = int(total_matches[0])
    require(
        total_device_time_ns == sum(row["time_ns"] for row in parsed_by_name.values()),
        f"{path}: timing row sum differs from reported L0 device time",
    )
    for row in parsed_by_name.values():
        expected_percent = row["time_ns"] * 100.0 / total_device_time_ns
        require(
            math.isclose(
                row["time_percent"],
                expected_percent,
                rel_tol=0.0,
                abs_tol=TIME_PERCENT_ABSOLUTE_TOLERANCE,
            ),
            f"{path}: timing percentage inconsistent for {row['kernel_name']}",
        )
    require(
        math.isclose(
            sum(row["time_percent"] for row in parsed_by_name.values()),
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
    compiled = properties.get("Compiled")
    simd = integer(properties, "SIMD", path)
    argument_count = integer(properties, "Number of Arguments", path)
    slm = integer(properties, "SLM Per Work Group", path)
    private_memory = integer(properties, "Private Memory Per Thread", path)
    spill = integer(properties, "Spill Memory Per Thread", path)
    register_file = integer(properties, "Register File Size Per Thread", path)
    require(
        compiled == "AOT"
        and simd == 16
        and argument_count == 15
        and slm == 0
        and private_memory == 0
        and spill == 0
        and register_file == 256,
        f"{path}: selected GEMM property identity drift",
    )
    selected = parsed_by_name[expected_kernel_name]
    return {
        "path": str(path),
        "sha256": sha256_file(path),
        "kernel_name": expected_kernel_name,
        "calls": selected["calls"],
        "time_ns": selected["time_ns"],
        "time_percent": selected["time_percent"],
        "average_ns": selected["average_ns"],
        "minimum_ns": selected["minimum_ns"],
        "maximum_ns": selected["maximum_ns"],
        "compiled": compiled,
        "simd": simd,
        "number_of_arguments": argument_count,
        "private_memory_per_thread": private_memory,
        "spill_memory_per_thread": spill,
        "slm_per_work_group": slm,
        "register_file_size_per_thread": register_file,
        "reported_total_device_time_ns": total_device_time_ns,
        "timing_row_order": [row["Kernel"] for row in timing_rows],
        "auxiliary_timing_rows": {
            name: parsed_by_name[name] for name in AUXILIARY_TIMING_CALLS
        },
        "analysis_repair": "exact six-row unitrace device-timing schema",
    }


def committed_bytes(relative_path: Path) -> bytes:
    return subprocess.run(
        ["git", "-C", str(MAIN_REPO), "show", f"HEAD:{relative_path}"],
        check=True,
        capture_output=True,
    ).stdout


def validate_repair_authorization(
    path: Path,
    expected_sha256: str,
) -> tuple[dict[str, Any], str]:
    require(
        path.is_absolute()
        and not path.is_symlink()
        and path.resolve(strict=True) == REPAIR_AUTHORIZATION,
        "repair authorization path drift",
    )
    packet_sha256 = sha256_file(path)
    require(packet_sha256 == expected_sha256, "repair authorization SHA drift")
    status = subprocess.run(
        [
            "git",
            "-C",
            str(MAIN_REPO),
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    require(not status.strip(), "main repository is dirty")
    tracked = subprocess.run(
        [
            "git",
            "-C",
            str(MAIN_REPO),
            "ls-files",
            "--error-unmatch",
            str(REPAIR_AUTHORIZATION_RELATIVE),
        ],
        check=False,
        capture_output=True,
    )
    require(tracked.returncode == 0, "repair authorization is not tracked")
    require(
        committed_bytes(REPAIR_AUTHORIZATION_RELATIVE) == path.read_bytes(),
        "repair authorization differs from committed HEAD bytes",
    )
    packet = json.loads(path.read_text())
    require(
        set(packet)
        == {
            "format",
            "created_utc",
            "reason",
            "execution_evidence",
            "tools",
            "parser_contract",
            "output",
            "authorization",
        },
        "repair authorization top-level schema drift",
    )
    require(
        packet.get("format")
        == "laguna-shared-down-m8-counter-analysis-repair-authorization-v1"
        and packet.get("reason")
        == (
            "post-capture parser repair: pinned unitrace device timing includes "
            "five fixture memory-copy rows alongside the selected GEMM"
        )
        and packet.get("execution_evidence")
        == {
            "execution_authorization": {
                "path": str(EXECUTION_AUTHORIZATION),
                "sha256": EXPECTED_EXECUTION_AUTHORIZATION_SHA256,
            },
            "campaign_root": str(CAMPAIGN_ROOT),
            "campaign_open": {
                "path": str(CAMPAIGN_OPEN),
                "sha256": EXPECTED_CAMPAIGN_OPEN_SHA256,
            },
            "campaign_complete": {
                "path": str(CAMPAIGN_COMPLETE),
                "sha256": EXPECTED_CAMPAIGN_COMPLETE_SHA256,
            },
            "original_runner": {
                "path": str(ORIGINAL_RUNNER),
                "sha256": EXPECTED_ORIGINAL_RUNNER_SHA256,
            },
            "original_analyzer": {
                "path": str(ORIGINAL_ANALYZER),
                "sha256": EXPECTED_ORIGINAL_ANALYZER_SHA256,
            },
        }
        and packet.get("parser_contract") == expected_parser_contract()
        and packet.get("authorization")
        == {
            "sealed_counter_capture_reuse_authorized": True,
            "counter_reexecution_authorized": False,
            "analysis_repair_authorized": True,
            "counter_gate_evaluated": False,
            "counter_gate_passed": False,
            "endpoint_preregistration_construction_authorized": False,
            "endpoint_execution_authorized": False,
            "model_generation_authorized": False,
            "model_generation_performed": False,
            "payload_created": False,
            "localmaxxing_submission_authorized": False,
            "localmaxxing_submission_made": False,
        },
        "repair authorization frozen contract drift",
    )
    expected_tools = {
        "repair_analyzer": REPAIR_ANALYZER,
        "repair_test": REPAIR_TEST,
    }
    tools = packet.get("tools")
    require(
        isinstance(tools, dict) and set(tools) == set(expected_tools),
        "repair tool set drift",
    )
    for name, tool_path in expected_tools.items():
        entry = tools[name]
        require(
            entry
            == {
                "path": str(tool_path),
                "sha256": entry.get("sha256"),
            }
            and isinstance(entry.get("sha256"), str)
            and re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]) is not None
            and tool_path.is_file()
            and sha256_file(tool_path) == entry["sha256"],
            f"repair tool identity drift: {name}",
        )
    output = packet.get("output")
    require(
        isinstance(output, dict)
        and set(output)
        == {
            "root",
            "analysis",
            "exclusive_create",
            "original_campaign_remains_immutable",
        },
        "repair output schema drift",
    )
    output_root = Path(output["root"])
    require(
        output_root.is_absolute()
        and output_root.parent == RUNS_ROOT
        and re.fullmatch(
            r"shared-down-m8-counters-20260723T173812Z-analysis-repair-"
            r"[0-9]{8}T[0-9]{6}Z",
            output_root.name,
        )
        is not None
        and output["analysis"] == str(output_root / "analysis.json")
        and output["exclusive_create"] is True
        and output["original_campaign_remains_immutable"] is True,
        "repair output contract drift",
    )
    require(
        sha256_file(EXECUTION_AUTHORIZATION) == EXPECTED_EXECUTION_AUTHORIZATION_SHA256
        and sha256_file(ORIGINAL_RUNNER) == EXPECTED_ORIGINAL_RUNNER_SHA256
        and sha256_file(ORIGINAL_ANALYZER) == EXPECTED_ORIGINAL_ANALYZER_SHA256
        and sha256_file(CAMPAIGN_OPEN) == EXPECTED_CAMPAIGN_OPEN_SHA256
        and sha256_file(CAMPAIGN_COMPLETE) == EXPECTED_CAMPAIGN_COMPLETE_SHA256,
        "sealed execution evidence drift",
    )
    return packet, packet_sha256


def load_frozen_modules() -> tuple[ModuleType, ModuleType]:
    sys.path.insert(0, str(TOOLS_DIR))
    names_paths_hashes = (
        (
            "run_laguna_shared_down_mm_counters",
            ORIGINAL_RUNNER,
            EXPECTED_ORIGINAL_RUNNER_SHA256,
        ),
        (
            "analyze_laguna_shared_down_mm_counters",
            ORIGINAL_ANALYZER,
            EXPECTED_ORIGINAL_ANALYZER_SHA256,
        ),
    )
    loaded: list[ModuleType] = []
    try:
        for name, path, expected_sha256 in names_paths_hashes:
            require(name not in sys.modules, f"refuse preloaded local module: {name}")
            source_bytes = path.read_bytes()
            require(
                hashlib.sha256(source_bytes).hexdigest() == expected_sha256,
                f"refuse to execute drifted source bytes: {name}",
            )
            module = ModuleType(name)
            module.__file__ = str(path)
            module.__package__ = ""
            module.__loader__ = None
            module.__spec__ = None
            sys.modules[name] = module
            code = compile(
                source_bytes,
                str(path),
                "exec",
                dont_inherit=True,
                optimize=0,
            )
            exec(code, module.__dict__)
            require(
                Path(module.__file__).resolve() == path,
                f"frozen module path drift after load: {name}",
            )
            loaded.append(module)
    except Exception:
        for name, _path, _expected_sha256 in reversed(names_paths_hashes):
            sys.modules.pop(name, None)
        raise
    contract, legacy = loaded
    require(
        getattr(legacy, "contract", None) is contract,
        "legacy analyzer did not bind the exact loaded runner module",
    )
    return contract, legacy


def main() -> int:
    require(
        sys.dont_write_bytecode,
        "offline repair requires -B or PYTHONDONTWRITEBYTECODE=1",
    )
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign-root", type=Path, required=True)
    parser.add_argument(
        "--execution-authorization-json",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--expected-execution-authorization-sha256",
        type=sha256_argument,
        required=True,
    )
    parser.add_argument(
        "--repair-authorization-json",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--expected-repair-authorization-sha256",
        type=sha256_argument,
        required=True,
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    repair_packet, repair_packet_sha256 = validate_repair_authorization(
        args.repair_authorization_json,
        args.expected_repair_authorization_sha256,
    )
    require(
        args.campaign_root == CAMPAIGN_ROOT
        and args.execution_authorization_json == EXECUTION_AUTHORIZATION
        and args.expected_execution_authorization_sha256
        == EXPECTED_EXECUTION_AUTHORIZATION_SHA256,
        "repair CLI execution-evidence identity drift",
    )
    output_root = Path(repair_packet["output"]["root"])
    out = Path(repair_packet["output"]["analysis"])
    require(
        args.out == out
        and not output_root.exists()
        and not output_root.is_symlink()
        and output_root.resolve(strict=False) == output_root
        and output_root.parent == RUNS_ROOT,
        "repair output must be a new exact sibling NVMe root",
    )

    contract, legacy = load_frozen_modules()
    execution_packet, execution_packet_sha256 = contract.validate_authorization(
        args.execution_authorization_json,
        args.expected_execution_authorization_sha256,
    )
    contract.validate_packet_command_template(execution_packet)
    contract.local_nvme_mount_identity()
    require(
        sha256_file(Path(__file__).resolve())
        == repair_packet["tools"]["repair_analyzer"]["sha256"],
        "repair analyzer source differs from authorization packet",
    )
    legacy.parse_timing_properties = parse_timing_properties_repair
    complete, profiles = legacy.validate_campaign(
        CAMPAIGN_ROOT.resolve(strict=True),
        packet=execution_packet,
        packet_sha256=execution_packet_sha256,
    )
    analysis = legacy.analyze_profiles(profiles)
    require(
        sha256_file(CAMPAIGN_OPEN) == EXPECTED_CAMPAIGN_OPEN_SHA256
        and sha256_file(CAMPAIGN_COMPLETE) == EXPECTED_CAMPAIGN_COMPLETE_SHA256,
        "sealed campaign drifted during offline analysis",
    )
    passed = analysis["passed"]
    result: dict[str, Any] = {
        "format": "laguna-shared-down-mm-counter-analysis-repair-v1",
        "status": (
            "counter-analysis-repair-passed-independent-audit-next"
            if passed
            else "counter-failed-stop-before-endpoint"
        ),
        "passed": passed,
        "created_utc": contract.utc_now(),
        "original_campaign": {
            "root": str(CAMPAIGN_ROOT),
            "campaign_open": {
                "path": str(CAMPAIGN_OPEN),
                "sha256": EXPECTED_CAMPAIGN_OPEN_SHA256,
            },
            "campaign_complete": {
                "path": str(CAMPAIGN_COMPLETE),
                "sha256": EXPECTED_CAMPAIGN_COMPLETE_SHA256,
            },
            "remained_immutable": True,
        },
        "execution_authorization": {
            "path": str(EXECUTION_AUTHORIZATION),
            "sha256": execution_packet_sha256,
        },
        "analysis_repair_authorization": {
            "path": str(REPAIR_AUTHORIZATION),
            "sha256": repair_packet_sha256,
        },
        "parser_contract": repair_packet["parser_contract"],
        "protocol": execution_packet["protocol"],
        "protocol_sha256": contract.canonical_sha256(execution_packet["protocol"]),
        "acceptance": execution_packet["acceptance"],
        "execution_tools": execution_packet["tools"],
        "repair_tools": repair_packet["tools"],
        "component_evidence": execution_packet["component_evidence"],
        "campaign_closure": complete,
        "analysis": analysis,
        "authorization": {
            "analysis_repair_evaluated": True,
            "counter_gate_evaluated": True,
            "counter_gate_passed": passed,
            "endpoint_preregistration_construction_authorized": False,
            "endpoint_execution_authorized": False,
            "model_generation_authorized": False,
            "model_generation_performed": False,
            "payload_created": False,
            "localmaxxing_submission_authorized": False,
            "localmaxxing_submission_made": False,
        },
    }
    output_root.mkdir(mode=0o755)
    legacy.atomic_exclusive_json(out, result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "passed": passed,
                "analysis": str(out),
                "analysis_sha256": sha256_file(out),
            },
            sort_keys=True,
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
