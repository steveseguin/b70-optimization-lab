#!/usr/bin/env python3
"""Attest activation of the default-off canonical Q8 c2 SYCL control.

The launcher identity is authoritative for the requested selector and its
required compatibility settings.  The candidate backend emits one first-hit
line for each selected two-vector layout and one summary during orderly backend
teardown.  Incomplete, malformed, duplicated, reordered, or inconsistent
evidence produces a retained failed attestation.  The evidence is also bound to
an explicitly hashed candidate manifest and matching reference/final runtime
bundle reports so dispatch markers cannot be transplanted to another runtime.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any


CONTROL = "GGML_SYCL_Q8_0_C2_CANONICAL_MMVQ"
MARKER = "SYCL_Q8_0_C2_CANONICAL_MMVQ"
STARTUP_LINE = f"  {CONTROL}: 1"
FIRST_HIT_PREFIX = f"{MARKER} first-hit:"
SUMMARY_PREFIX = f"{MARKER} summary:"
VIOLATION_PREFIX = f"{MARKER} violation:"
PROCESS_BINDING_PREFIX = "QWEN36_SERVER_PROCESS_BINDING"
PROCESS_BINDING_RE = re.compile(
    rf"^{re.escape(PROCESS_BINDING_PREFIX)} pid=([1-9][0-9]*)$"
)
POSITIVE_DECIMAL_RE = re.compile(r"^[1-9][0-9]*$")
IDENTITY_LINES = {
    CONTROL: "1",
    "GGML_SYCL_ENABLE_OPT": "1",
    "GGML_SYCL_ENABLE_GRAPH": "0",
    "GGML_SYCL_PRIORITIZE_DMMV": "0",
}
RUNTIME_REPORT_SIGNATURE_FIELDS = (
    "runtime_bundle_schema_version",
    "runtime_manifest_sha256",
    "binary",
    "loader_policy",
    "dependency_count",
    "origin_shared_object_count",
    "origin_shared_object_sonames",
    "dependencies",
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

COMMON_LOG_PREFIX_RE = re.compile(
    r"^(?P<elapsed>[0-9]+\.[0-9]{2}\.[0-9]{3}\.[0-9]{3}) "
    r"(?P<level>[IWE]) (?P<message>.*)$"
)
DIMENSION_PATTERN = r"(-?[0-9]+),(-?[0-9]+),(-?[0-9]+),(-?[0-9]+)"
FIRST_HIT_RE = re.compile(
    rf"^{re.escape(FIRST_HIT_PREFIX)} "
    rf"layout=(flat|recurrent) "
    rf"path=reordered_single_col_mmvq reorder_ready=1 calls_per_dispatch=2 "
    rf"src0=(\S+) src0_ne=\[{DIMENSION_PATTERN}\] "
    rf"src1_ne=\[{DIMENSION_PATTERN}\] dst_ne=\[{DIMENSION_PATTERN}\]$"
)
SUMMARY_RE = re.compile(
    rf"^{re.escape(SUMMARY_PREFIX)} "
    r"flat_dispatches=([0-9]+) "
    r"recurrent_dispatches=([0-9]+) "
    r"flat_multicol_suppressed=([0-9]+) "
    r"recurrent_dmmv_suppressed=([0-9]+) "
    r"reorder_ready_dispatches=([0-9]+) "
    r"single_col_mmvq_calls=([0-9]+) "
    r"violations=([0-9]+)$"
)
SUMMARY_FIELDS = (
    "flat_dispatches",
    "recurrent_dispatches",
    "flat_multicol_suppressed",
    "recurrent_dmmv_suppressed",
    "reorder_ready_dispatches",
    "single_col_mmvq_calls",
    "violations",
)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def safe_realpath(value: Any) -> str | None:
    if (
        not isinstance(value, str)
        or not os.path.isabs(value)
        or "\n" in value
        or "\x00" in value
    ):
        return None
    try:
        return os.path.realpath(value)
    except (OSError, ValueError):
        return None


def parse_json_object(
    value: bytes, label: str
) -> tuple[dict[str, Any] | None, str | None]:
    try:
        parsed = json.loads(value)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"cannot parse {label}: {exc}"
    if not isinstance(parsed, dict):
        return None, f"{label} must contain a JSON object"
    return parsed, None


def expand_origin_path(value: Any, origin: str) -> str | None:
    if not isinstance(value, str) or not value.startswith("$ORIGIN/"):
        return None
    relative = value[len("$ORIGIN/") :]
    parts = Path(relative).parts
    if not relative or os.path.isabs(relative) or ".." in parts:
        return None
    return os.path.normpath(os.path.join(origin, relative))


def manifest_runtime_contract(
    manifest: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    if manifest is None:
        return None, ["runtime manifest is not a JSON object"]

    server_path = manifest.get("llama_server_path")
    server_sha256 = manifest.get("llama_server_sha256")
    if (
        not isinstance(server_path, str)
        or not os.path.isabs(server_path)
        or "\n" in server_path
        or "\x00" in server_path
    ):
        errors.append("llama_server_path must be an absolute newline-free path")
    if not isinstance(server_sha256, str) or SHA256_RE.fullmatch(server_sha256) is None:
        errors.append("llama_server_sha256 is malformed")
    if type(manifest.get("runtime_bundle_schema_version")) is not int or (
        manifest["runtime_bundle_schema_version"] != 1
    ):
        errors.append("runtime_bundle_schema_version must be 1")
    if manifest.get("runtime_loader_policy") != {
        "mode": "origin-first",
        "variable": "LD_LIBRARY_PATH",
    }:
        errors.append("runtime_loader_policy is not the exact origin-first policy")
    controls = manifest.get("experimental_controls")
    control = controls.get(CONTROL) if isinstance(controls, dict) else None
    if not isinstance(control, dict) or not (
        control.get("supported") is True
        and control.get("default") == "0"
        and control.get("values") == ["0", "1"]
    ):
        errors.append("runtime manifest does not declare the candidate control")

    if not isinstance(server_path, str) or not os.path.isabs(server_path):
        return None, errors
    server_resolved_path = safe_realpath(server_path)
    if server_resolved_path is None:
        errors.append("llama_server_path cannot be resolved safely")
    origin = os.path.dirname(server_path)
    objects = manifest.get("origin_shared_objects")
    expected_origin: dict[str, dict[str, Any]] = {}
    if not isinstance(objects, list) or not objects:
        errors.append("origin_shared_objects must be a nonempty array")
        objects = []
    for index, item in enumerate(objects):
        if not isinstance(item, dict):
            errors.append(f"origin_shared_objects[{index}] is not an object")
            continue
        soname = item.get("soname")
        loader_path = expand_origin_path(item.get("loader_path"), origin)
        resolved_path = expand_origin_path(item.get("resolved_path"), origin)
        size_bytes = item.get("size_bytes")
        sha256 = item.get("sha256")
        if not isinstance(soname, str) or not soname or "/" in soname:
            errors.append(f"origin_shared_objects[{index}] has an invalid soname")
            continue
        if soname in expected_origin:
            errors.append(f"duplicate origin soname: {soname}")
            continue
        if loader_path is None or resolved_path is None:
            errors.append(f"{soname} has an invalid $ORIGIN path")
            continue
        if (
            isinstance(size_bytes, bool)
            or not isinstance(size_bytes, int)
            or size_bytes <= 0
        ):
            errors.append(f"{soname} has an invalid size_bytes")
            continue
        if not isinstance(sha256, str) or SHA256_RE.fullmatch(sha256) is None:
            errors.append(f"{soname} has a malformed SHA-256")
            continue
        expected_origin[soname] = {
            "soname": soname,
            "loader_path": loader_path,
            "resolved_path": resolved_path,
            "size_bytes": size_bytes,
            "sha256": sha256,
        }
    if len(expected_origin) != len(objects):
        errors.append("not every manifest origin object has a valid unique identity")
    if errors:
        return None, errors
    return {
        "server_path": server_path,
        "server_resolved_path": server_resolved_path,
        "server_sha256": server_sha256,
        "origin": origin,
        "expected_origin": expected_origin,
        "schema_version": 1,
        "loader_policy": {
            "mode": "origin-first",
            "variable": "LD_LIBRARY_PATH",
            "binary_origin": origin,
            "ld_library_path_first": origin,
            "origin_precedence_attested": True,
        },
    }, []


def validate_runtime_report(
    report: dict[str, Any] | None,
    contract: dict[str, Any] | None,
    runtime_manifest_path: str,
    runtime_manifest_sha256: str,
) -> tuple[dict[str, bool], list[str]]:
    checks: dict[str, bool] = {
        "is_object": report is not None,
        "passed": False,
        "schema_version": False,
        "manifest_path": False,
        "manifest_sha256": False,
        "binary": False,
        "loader_policy": False,
        "dependency_count": False,
        "origin_object_set": False,
    }
    errors: list[str] = []
    if report is None or contract is None:
        return checks, errors

    checks["passed"] = report.get("passed") is True
    checks["schema_version"] = (
        type(report.get("runtime_bundle_schema_version")) is int
        and report["runtime_bundle_schema_version"] == contract["schema_version"]
    )
    checks["manifest_path"] = report.get("runtime_manifest") == runtime_manifest_path
    checks["manifest_sha256"] = (
        report.get("runtime_manifest_sha256") == runtime_manifest_sha256
    )

    binary = report.get("binary")
    checks["binary"] = isinstance(binary, dict) and (
        binary.get("loader_path") == contract["server_path"]
        and binary.get("resolved_path") == contract["server_resolved_path"]
        and isinstance(binary.get("size_bytes"), int)
        and not isinstance(binary.get("size_bytes"), bool)
        and binary["size_bytes"] > 0
        and binary.get("sha256") == contract["server_sha256"]
    )
    checks["loader_policy"] = report.get("loader_policy") == contract["loader_policy"]

    dependencies = report.get("dependencies")
    dependency_count = report.get("dependency_count")
    checks["dependency_count"] = (
        isinstance(dependencies, list)
        and isinstance(dependency_count, int)
        and not isinstance(dependency_count, bool)
        and dependency_count == len(dependencies)
        and dependency_count > 0
    )
    expected_origin = contract["expected_origin"]
    expected_sonames = set(expected_origin)
    origin_dependencies: dict[str, dict[str, Any]] = {}
    dependency_sonames: set[str] = set()
    dependency_shape_valid = isinstance(dependencies, list)
    for dependency in dependencies if isinstance(dependencies, list) else []:
        if not isinstance(dependency, dict):
            dependency_shape_valid = False
            continue
        soname = dependency.get("soname")
        loader_path = dependency.get("loader_path")
        resolved_path = dependency.get("resolved_path")
        if (
            not isinstance(soname, str)
            or soname in dependency_sonames
            or not isinstance(loader_path, str)
            or not os.path.isabs(loader_path)
            or not isinstance(resolved_path, str)
            or not os.path.isabs(resolved_path)
            or type(dependency.get("size_bytes")) is not int
            or dependency["size_bytes"] <= 0
            or not isinstance(dependency.get("sha256"), str)
            or SHA256_RE.fullmatch(dependency["sha256"]) is None
        ):
            dependency_shape_valid = False
            continue
        dependency_sonames.add(soname)
        try:
            is_origin = (
                os.path.commonpath((contract["origin"], loader_path))
                == contract["origin"]
            )
        except ValueError:
            is_origin = False
        if is_origin:
            origin_dependencies[soname] = dependency

    projected_origin = {
        soname: {
            field: dependency.get(field)
            for field in (
                "soname",
                "loader_path",
                "resolved_path",
                "size_bytes",
                "sha256",
            )
        }
        for soname, dependency in origin_dependencies.items()
    }
    checks["origin_object_set"] = (
        dependency_shape_valid
        and set(origin_dependencies) == expected_sonames
        and projected_origin == expected_origin
        and type(report.get("origin_shared_object_count")) is int
        and report["origin_shared_object_count"] == len(expected_origin)
        and report.get("origin_shared_object_sonames") == sorted(expected_origin)
    )
    return checks, errors


def parse_dimensions(values: tuple[str, ...]) -> list[int]:
    return [int(value) for value in values]


def normalize_runtime_line(line: str) -> tuple[str, str | None]:
    """Strip only llama.cpp's exact common-log prefix when it is present."""

    match = COMMON_LOG_PREFIX_RE.fullmatch(line)
    if match is None:
        return line, None
    return match.group("message"), match.group("level")


def parse_first_hit(match: re.Match[str], line_number: int) -> dict[str, Any]:
    layout = match.group(1)
    src0_name = match.group(2)
    src0_ne = parse_dimensions(match.groups()[2:6])
    src1_ne = parse_dimensions(match.groups()[6:10])
    dst_ne = parse_dimensions(match.groups()[10:14])
    expected_batch = [2, 1, 1] if layout == "flat" else [1, 2, 1]
    shape_fields = {
        "positive_matrix_dimensions": src0_ne[0] > 0 and src0_ne[1] > 0,
        "src0_is_matrix": src0_ne[2:] == [1, 1],
        "src1_layout_exact": src1_ne[1:] == expected_batch,
        "dst_layout_exact": dst_ne[1:] == expected_batch,
        "inner_dimension_exact": src1_ne[0] == src0_ne[0],
        "output_dimension_exact": dst_ne[0] == src0_ne[1],
    }
    return {
        "line_number": line_number,
        "layout": layout,
        "path": "reordered_single_col_mmvq",
        "reorder_ready": 1,
        "calls_per_dispatch": 2,
        "src0": src0_name,
        "src0_ne": src0_ne,
        "src1_ne": src1_ne,
        "dst_ne": dst_ne,
        "shape_fields": shape_fields,
        "shape_passed": all(shape_fields.values()),
    }


def build_attestation(
    log_bytes: bytes,
    identity_bytes: bytes,
    server_pid: str,
    runtime_manifest_bytes: bytes,
    runtime_manifest_sha256: str,
    runtime_reference_report_bytes: bytes,
    runtime_reference_report_sha256: str,
    runtime_final_report_bytes: bytes,
    runtime_final_report_sha256: str,
    *,
    log_path: str,
    identity_path: str,
    runtime_manifest_path: str,
    runtime_reference_report_path: str,
    runtime_final_report_path: str,
) -> dict[str, Any]:
    """Build an attestation from identity and complete post-teardown logs."""

    text = log_bytes.decode("utf-8", errors="replace")
    lines = text.splitlines()
    normalized = [normalize_runtime_line(line) for line in lines]

    manifest, manifest_parse_error = parse_json_object(
        runtime_manifest_bytes, "runtime manifest"
    )
    reference_report, reference_parse_error = parse_json_object(
        runtime_reference_report_bytes, "runtime reference report"
    )
    final_report, final_parse_error = parse_json_object(
        runtime_final_report_bytes, "runtime final report"
    )
    manifest_contract, manifest_contract_errors = manifest_runtime_contract(manifest)
    manifest_actual_sha256 = sha256_bytes(runtime_manifest_bytes)
    reference_actual_sha256 = sha256_bytes(runtime_reference_report_bytes)
    final_actual_sha256 = sha256_bytes(runtime_final_report_bytes)
    expected_sha256_well_formed = {
        "manifest": SHA256_RE.fullmatch(runtime_manifest_sha256) is not None,
        "reference_report": (
            SHA256_RE.fullmatch(runtime_reference_report_sha256) is not None
        ),
        "final_report": SHA256_RE.fullmatch(runtime_final_report_sha256) is not None,
    }
    input_paths_absolute = all(
        os.path.isabs(path)
        for path in (
            runtime_manifest_path,
            runtime_reference_report_path,
            runtime_final_report_path,
        )
    )
    input_paths_distinct = (
        len(
            {
                os.path.normpath(runtime_manifest_path),
                os.path.normpath(runtime_reference_report_path),
                os.path.normpath(runtime_final_report_path),
            }
        )
        == 3
    )

    reference_checks, reference_validation_errors = validate_runtime_report(
        reference_report,
        manifest_contract,
        runtime_manifest_path,
        runtime_manifest_sha256,
    )
    final_checks, final_validation_errors = validate_runtime_report(
        final_report,
        manifest_contract,
        runtime_manifest_path,
        runtime_manifest_sha256,
    )
    report_signature_exact = (
        reference_report is not None
        and final_report is not None
        and all(
            reference_report.get(field) == final_report.get(field)
            for field in RUNTIME_REPORT_SIGNATURE_FIELDS
        )
    )
    final_reference_path_exact = (
        final_report is not None
        and final_report.get("reference_report") == runtime_reference_report_path
    )
    final_reference_match_true = (
        final_report is not None and final_report.get("reference_match") is True
    )
    server_pid_valid = (
        isinstance(server_pid, str)
        and POSITIVE_DECIMAL_RE.fullmatch(server_pid) is not None
    )

    identity_text = identity_bytes.decode("utf-8", errors="replace")
    identity_all_lines = identity_text.splitlines()
    identity_delimiter_indexes = [
        index
        for index, line in enumerate(identity_all_lines)
        if line == "--- server ---"
    ]
    identity_header = (
        identity_all_lines[: identity_delimiter_indexes[0]]
        if identity_delimiter_indexes
        else identity_all_lines
    )
    identity_expected = dict(IDENTITY_LINES)
    identity_expected["server_pid"] = server_pid if server_pid_valid else None
    if manifest_contract is not None:
        identity_expected.update(
            {
                "runtime_bundle_verified": "1",
                "runtime_manifest": runtime_manifest_path,
                "runtime_manifest_sha256": runtime_manifest_sha256,
                "llama_server": manifest_contract["server_path"],
                "llama_server_sha256": manifest_contract["server_sha256"],
                "runtime_loader_policy": "origin-first",
                "runtime_loader_origin": manifest_contract["origin"],
                "runtime_loader_origin_precedence": "1",
            }
        )
    else:
        for name in (
            "runtime_bundle_verified",
            "runtime_manifest",
            "runtime_manifest_sha256",
            "llama_server",
            "llama_server_sha256",
            "runtime_loader_policy",
            "runtime_loader_origin",
            "runtime_loader_origin_precedence",
        ):
            identity_expected[name] = None
    identity_candidates = {
        name: [line for line in identity_header if line.startswith(f"{name}=")]
        for name in identity_expected
    }
    identity_exact = {
        name: [
            line
            for line in identity_candidates[name]
            if value is not None and line == f"{name}={value}"
        ]
        for name, value in identity_expected.items()
    }
    server_output_log_candidates = [
        line for line in identity_header if line.startswith("server_output_log=")
    ]
    server_output_log_values = [
        line.split("=", 1)[1]
        for line in server_output_log_candidates
        if line != "server_output_log="
    ]
    expected_server_output_realpath = safe_realpath(log_path)
    observed_server_output_realpath = (
        safe_realpath(server_output_log_values[0])
        if len(server_output_log_values) == 1
        else None
    )
    server_output_log_valid = (
        len(server_output_log_candidates) == 1
        and len(server_output_log_values) == 1
        and expected_server_output_realpath is not None
        and observed_server_output_realpath == expected_server_output_realpath
    )

    process_binding_candidates = [
        (line_number, line)
        for line_number, line in enumerate(lines, 1)
        if PROCESS_BINDING_PREFIX in line
    ]
    process_binding_matches = [
        (line_number, match)
        for line_number, line in process_binding_candidates
        if (match := PROCESS_BINDING_RE.fullmatch(line)) is not None
    ]
    process_binding_pids = [match.group(1) for _, match in process_binding_matches]
    process_binding_line_number = (
        process_binding_matches[0][0] if len(process_binding_matches) == 1 else None
    )
    identity_pid_values = [
        match.group(1)
        for line in identity_candidates["server_pid"]
        if (match := re.fullmatch(r"server_pid=([1-9][0-9]*)", line)) is not None
    ]

    startup_candidates = [
        (line_number, message, level)
        for line_number, (message, level) in enumerate(normalized, 1)
        if f"{CONTROL}:" in message
    ]
    startup_exact = [
        row
        for row in startup_candidates
        if row[1] == STARTUP_LINE and row[2] in (None, "I")
    ]

    first_hit_candidates = [
        (line_number, message, level)
        for line_number, (message, level) in enumerate(normalized, 1)
        if FIRST_HIT_PREFIX in message
    ]
    first_hit_matches = [
        (line_number, FIRST_HIT_RE.fullmatch(message))
        for line_number, message, level in first_hit_candidates
        if level in (None, "I")
    ]
    parsed_first_hits = [
        parse_first_hit(match, line_number)
        for line_number, match in first_hit_matches
        if match is not None
    ]
    flat_hits = [row for row in parsed_first_hits if row["layout"] == "flat"]
    recurrent_hits = [row for row in parsed_first_hits if row["layout"] == "recurrent"]

    summary_candidates = [
        (line_number, message, level)
        for line_number, (message, level) in enumerate(normalized, 1)
        if SUMMARY_PREFIX in message
    ]
    summary_matches = [
        (line_number, SUMMARY_RE.fullmatch(message))
        for line_number, message, level in summary_candidates
        if level in (None, "I")
    ]
    parsed_summaries = [
        {
            "line_number": line_number,
            **dict(zip(SUMMARY_FIELDS, (int(value) for value in match.groups()))),
        }
        for line_number, match in summary_matches
        if match is not None
    ]
    summary = parsed_summaries[0] if len(parsed_summaries) == 1 else None

    violation_lines = [
        {"line_number": line_number, "line": line}
        for line_number, line in enumerate(lines, 1)
        if VIOLATION_PREFIX in normalize_runtime_line(line)[0]
    ]
    flat_dispatches = summary.get("flat_dispatches") if summary else None
    recurrent_dispatches = summary.get("recurrent_dispatches") if summary else None
    dispatch_sum = (
        flat_dispatches + recurrent_dispatches
        if isinstance(flat_dispatches, int) and isinstance(recurrent_dispatches, int)
        else None
    )
    first_hit_line_numbers = [row["line_number"] for row in parsed_first_hits]
    summary_line_number = summary.get("line_number") if summary else None
    process_binding_order_valid = (
        isinstance(process_binding_line_number, int)
        and len(first_hit_line_numbers) == 2
        and process_binding_line_number < min(first_hit_line_numbers)
        and (not startup_exact or process_binding_line_number < startup_exact[0][0])
    )
    marker_order_valid = (
        process_binding_order_valid
        and isinstance(summary_line_number, int)
        and max(first_hit_line_numbers) < summary_line_number
        and (not startup_exact or startup_exact[0][0] < min(first_hit_line_numbers))
    )

    identity_once = {
        name: len(identity_exact[name]) == 1 and len(identity_candidates[name]) == 1
        for name in identity_expected
    }

    fields = {
        "identity_delimiter_exactly_once": len(identity_delimiter_indexes) == 1,
        "server_pid_argument_positive_decimal": server_pid_valid,
        "server_pid_identity_exactly_once": identity_once["server_pid"],
        "server_output_log_identity_exactly_once_and_resolved": (
            server_output_log_valid
        ),
        "server_process_binding_sentinel_exactly_once": (
            len(process_binding_candidates) == 1 and len(process_binding_matches) == 1
        ),
        "server_process_binding_all_pids_equal": (
            server_pid_valid
            and len(identity_pid_values) == 1
            and len(process_binding_pids) == 1
            and identity_pid_values[0] == server_pid
            and process_binding_pids[0] == server_pid
        ),
        "server_process_binding_order_valid": process_binding_order_valid,
        "selector_identity_exactly_once": identity_once[CONTROL],
        "opt_identity_exactly_once": identity_once["GGML_SYCL_ENABLE_OPT"],
        "graph_identity_exactly_once": identity_once["GGML_SYCL_ENABLE_GRAPH"],
        "prioritize_dmmv_identity_exactly_once": identity_once[
            "GGML_SYCL_PRIORITIZE_DMMV"
        ],
        "runtime_bundle_verified_identity_exactly_once": identity_once[
            "runtime_bundle_verified"
        ],
        "runtime_manifest_identity_exactly_once": identity_once["runtime_manifest"],
        "runtime_manifest_sha256_identity_exactly_once": identity_once[
            "runtime_manifest_sha256"
        ],
        "llama_server_identity_exactly_once": identity_once["llama_server"],
        "llama_server_sha256_identity_exactly_once": identity_once[
            "llama_server_sha256"
        ],
        "runtime_loader_policy_identity_exactly_once": identity_once[
            "runtime_loader_policy"
        ],
        "runtime_loader_origin_identity_exactly_once": identity_once[
            "runtime_loader_origin"
        ],
        "runtime_loader_origin_precedence_identity_exactly_once": identity_once[
            "runtime_loader_origin_precedence"
        ],
        "runtime_input_paths_absolute": input_paths_absolute,
        "runtime_input_paths_distinct": input_paths_distinct,
        "runtime_manifest_expected_sha256_well_formed": expected_sha256_well_formed[
            "manifest"
        ],
        "runtime_reference_report_expected_sha256_well_formed": (
            expected_sha256_well_formed["reference_report"]
        ),
        "runtime_final_report_expected_sha256_well_formed": (
            expected_sha256_well_formed["final_report"]
        ),
        "runtime_manifest_sha256_matches_expected": (
            expected_sha256_well_formed["manifest"]
            and manifest_actual_sha256 == runtime_manifest_sha256
        ),
        "runtime_reference_report_sha256_matches_expected": (
            expected_sha256_well_formed["reference_report"]
            and reference_actual_sha256 == runtime_reference_report_sha256
        ),
        "runtime_final_report_sha256_matches_expected": (
            expected_sha256_well_formed["final_report"]
            and final_actual_sha256 == runtime_final_report_sha256
        ),
        "runtime_manifest_contract_valid": (
            manifest_parse_error is None
            and manifest_contract is not None
            and not manifest_contract_errors
        ),
        "runtime_reference_report_valid": all(reference_checks.values()),
        "runtime_final_report_valid": all(final_checks.values()),
        "runtime_report_signature_exact": report_signature_exact,
        "runtime_final_reference_path_exact": final_reference_path_exact,
        "runtime_final_reference_match_true": final_reference_match_true,
        "runtime_startup_marker_if_present_well_formed": len(startup_candidates)
        == len(startup_exact)
        and len(startup_candidates) <= 1,
        "first_hit_markers_well_formed": len(first_hit_candidates) == 2
        and len(parsed_first_hits) == 2,
        "flat_first_hit_exactly_once": len(flat_hits) == 1,
        "recurrent_first_hit_exactly_once": len(recurrent_hits) == 1,
        "flat_first_hit_shape_valid": len(flat_hits) == 1
        and flat_hits[0]["shape_passed"] is True,
        "recurrent_first_hit_shape_valid": len(recurrent_hits) == 1
        and recurrent_hits[0]["shape_passed"] is True,
        "summary_marker_exactly_once": len(summary_candidates) == 1,
        "summary_marker_well_formed": len(summary_candidates) == 1
        and len(parsed_summaries) == 1,
        "runtime_marker_order_valid": marker_order_valid,
        "flat_dispatches_positive": isinstance(flat_dispatches, int)
        and flat_dispatches > 0,
        "recurrent_dispatches_positive": isinstance(recurrent_dispatches, int)
        and recurrent_dispatches > 0,
        "flat_multicol_suppressed_exact": summary is not None
        and summary["flat_multicol_suppressed"] == flat_dispatches,
        "recurrent_dmmv_suppressed_exact": summary is not None
        and summary["recurrent_dmmv_suppressed"] == recurrent_dispatches,
        "reorder_ready_dispatches_exact": summary is not None
        and summary["reorder_ready_dispatches"] == dispatch_sum,
        "single_col_mmvq_calls_exact": summary is not None
        and summary["single_col_mmvq_calls"] == 2 * dispatch_sum,
        "summary_violations_zero": summary is not None and summary["violations"] == 0,
        "no_violation_markers": len(violation_lines) == 0,
    }
    return {
        "schema_version": 2,
        "status": "PASS" if all(fields.values()) else "FAIL",
        "passed": all(fields.values()),
        "control": CONTROL,
        "expected_selector": "1",
        "expected_server_pid": server_pid,
        "input": {
            "server_log": {
                "path": log_path,
                "size_bytes": len(log_bytes),
                "sha256": sha256_bytes(log_bytes),
            },
            "identity_log": {
                "path": identity_path,
                "size_bytes": len(identity_bytes),
                "sha256": sha256_bytes(identity_bytes),
            },
            "runtime_manifest": {
                "path": runtime_manifest_path,
                "size_bytes": len(runtime_manifest_bytes),
                "expected_sha256": runtime_manifest_sha256,
                "sha256": manifest_actual_sha256,
            },
            "runtime_reference_report": {
                "path": runtime_reference_report_path,
                "size_bytes": len(runtime_reference_report_bytes),
                "expected_sha256": runtime_reference_report_sha256,
                "sha256": reference_actual_sha256,
            },
            "runtime_final_report": {
                "path": runtime_final_report_path,
                "size_bytes": len(runtime_final_report_bytes),
                "expected_sha256": runtime_final_report_sha256,
                "sha256": final_actual_sha256,
            },
        },
        "fields": fields,
        "observed": {
            "identity_candidate_counts": {
                name: len(rows) for name, rows in identity_candidates.items()
            },
            "identity_exact_counts": {
                name: len(rows) for name, rows in identity_exact.items()
            },
            "identity_delimiter_count": len(identity_delimiter_indexes),
            "server_process_binding": {
                "expected_pid": server_pid,
                "expected_pid_positive_decimal": server_pid_valid,
                "identity_pid_candidate_count": len(identity_candidates["server_pid"]),
                "identity_pid_exact_count": len(identity_exact["server_pid"]),
                "identity_pids": identity_pid_values,
                "server_output_log_candidate_count": len(server_output_log_candidates),
                "server_output_log_values": server_output_log_values,
                "server_output_log_expected_resolved": (
                    expected_server_output_realpath
                ),
                "server_output_log_observed_resolved": (
                    observed_server_output_realpath
                ),
                "stdout_sentinel_candidate_count": len(process_binding_candidates),
                "stdout_sentinel_candidates": [
                    {"line_number": line_number, "line": line}
                    for line_number, line in process_binding_candidates
                ],
                "stdout_sentinel_exact_count": len(process_binding_matches),
                "stdout_sentinel_pids": process_binding_pids,
                "stdout_sentinel_line_numbers": [
                    line_number for line_number, _ in process_binding_matches
                ],
                "optional_startup_line_numbers": [
                    line_number for line_number, _, _ in startup_exact
                ],
                "first_hit_line_numbers": first_hit_line_numbers,
                "summary_line_number": summary_line_number,
                "order_valid": process_binding_order_valid and marker_order_valid,
            },
            "runtime_binding": {
                "manifest_parse_error": manifest_parse_error,
                "manifest_contract_errors": manifest_contract_errors,
                "reference_report_parse_error": reference_parse_error,
                "reference_report_validation_errors": reference_validation_errors,
                "reference_report_checks": reference_checks,
                "final_report_parse_error": final_parse_error,
                "final_report_validation_errors": final_validation_errors,
                "final_report_checks": final_checks,
                "report_signature_fields": list(RUNTIME_REPORT_SIGNATURE_FIELDS),
                "report_signature_exact": report_signature_exact,
                "final_reference_report": (
                    final_report.get("reference_report")
                    if final_report is not None
                    else None
                ),
                "final_reference_match": (
                    final_report.get("reference_match")
                    if final_report is not None
                    else None
                ),
                "manifest_origin_sonames": (
                    sorted(manifest_contract["expected_origin"])
                    if manifest_contract is not None
                    else []
                ),
            },
            "runtime_startup_candidate_count": len(startup_candidates),
            "runtime_startup_exact_count": len(startup_exact),
            "first_hit_candidate_count": len(first_hit_candidates),
            "first_hit_parsed_count": len(parsed_first_hits),
            "first_hits": parsed_first_hits,
            "summary_candidate_count": len(summary_candidates),
            "summary_parsed_count": len(parsed_summaries),
            "summary": summary,
            "violation_marker_count": len(violation_lines),
            "violation_lines": violation_lines,
        },
    }


def write_json_exclusive(path: Path, value: dict[str, Any]) -> None:
    if not path.parent.is_dir():
        raise SystemExit(f"output parent is not a directory: {path.parent}")
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    try:
        with temporary.open("x") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            raise SystemExit(f"refusing to overwrite existing output: {path}")
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-log", type=Path, required=True)
    parser.add_argument("--identity-log", type=Path, required=True)
    parser.add_argument("--server-pid", required=True)
    parser.add_argument("--runtime-manifest", type=Path, required=True)
    parser.add_argument("--runtime-manifest-sha256", required=True)
    parser.add_argument("--runtime-reference-report", type=Path, required=True)
    parser.add_argument("--runtime-reference-report-sha256", required=True)
    parser.add_argument("--runtime-final-report", type=Path, required=True)
    parser.add_argument("--runtime-final-report-sha256", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    if POSITIVE_DECIMAL_RE.fullmatch(args.server_pid) is None:
        parser.error("--server-pid must be a positive decimal")

    for label, path in (
        ("server log", args.server_log),
        ("identity log", args.identity_log),
        ("runtime manifest", args.runtime_manifest),
        ("runtime reference report", args.runtime_reference_report),
        ("runtime final report", args.runtime_final_report),
    ):
        if not path.is_file():
            parser.error(f"{label} is not a file: {path}")
    for label, path in (
        ("runtime manifest", args.runtime_manifest),
        ("runtime reference report", args.runtime_reference_report),
        ("runtime final report", args.runtime_final_report),
    ):
        if not path.is_absolute():
            parser.error(f"{label} path must be absolute: {path}")
    input_paths = {
        path.resolve()
        for path in (
            args.server_log,
            args.identity_log,
            args.runtime_manifest,
            args.runtime_reference_report,
            args.runtime_final_report,
        )
    }
    if len(input_paths) != 5:
        parser.error("attestation inputs must be five distinct files")
    if args.out.resolve() in input_paths:
        parser.error("output must not overwrite an input")

    result = build_attestation(
        args.server_log.read_bytes(),
        args.identity_log.read_bytes(),
        args.server_pid,
        args.runtime_manifest.read_bytes(),
        args.runtime_manifest_sha256,
        args.runtime_reference_report.read_bytes(),
        args.runtime_reference_report_sha256,
        args.runtime_final_report.read_bytes(),
        args.runtime_final_report_sha256,
        log_path=str(args.server_log.resolve()),
        identity_path=str(args.identity_log.resolve()),
        runtime_manifest_path=str(args.runtime_manifest),
        runtime_reference_report_path=str(args.runtime_reference_report),
        runtime_final_report_path=str(args.runtime_final_report),
    )
    write_json_exclusive(args.out, result)
    print(
        json.dumps({"out": str(args.out), "passed": result["passed"]}, sort_keys=True)
    )
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
