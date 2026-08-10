#!/usr/bin/env python3
"""Offline validation for the four-card canonical-Q8 sequential-oracle wave.

The companion shell runner owns all live processes.  This module only parses
retained files, validates the fixed mapping and identity, and constructs the
selector-matched oracle handoff.  It deliberately makes no performance claim.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import re
import sys
import time
from pathlib import Path
from types import ModuleType
from typing import Any


SCHEMA_VERSION = 1
CONTROL = "GGML_SYCL_Q8_0_C2_CANONICAL_MMVQ"
MARKER = "SYCL_Q8_0_C2_CANONICAL_MMVQ"
PROCESS_BINDING = "QWEN36_SERVER_PROCESS_BINDING"
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
PID_RE = re.compile(r"^[1-9][0-9]*$")
PROCESS_RE = re.compile(r"^QWEN36_SERVER_PROCESS_BINDING pid=([1-9][0-9]*)$")
SUMMARY_RE = re.compile(
    rf"^{MARKER} summary: "
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
DIMENSION_PATTERN = r"(-?[0-9]+),(-?[0-9]+),(-?[0-9]+),(-?[0-9]+)"
FIRST_HIT_RE = re.compile(
    rf"^{re.escape(MARKER)} first-hit: "
    rf"layout=(flat|recurrent) "
    rf"path=reordered_single_col_mmvq reorder_ready=1 calls_per_dispatch=2 "
    rf"src0=(\S+) src0_ne=\[{DIMENSION_PATTERN}\] "
    rf"src1_ne=\[{DIMENSION_PATTERN}\] dst_ne=\[{DIMENSION_PATTERN}\]$"
)
RUNTIME_SIGNATURE_FIELDS = (
    "runtime_bundle_schema_version",
    "runtime_manifest_sha256",
    "binary",
    "loader_policy",
    "dependency_count",
    "origin_shared_object_count",
    "origin_shared_object_sonames",
    "dependencies",
)
C1_MAPPING = (
    {"gpu_index": 0, "selector": 0},
    {"gpu_index": 1, "selector": 0},
    {"gpu_index": 2, "selector": 1},
    {"gpu_index": 3, "selector": 1},
)
EXPECTED_CASES = ("q27-q8-lc-04k-middle", "q27-q8-c2-04k-b")
CANDIDATE_MANIFEST_SHA256 = (
    "1b6c305b7e3fad027e7397168bda23526b72b8a4b59e8c6b2b3788fc7347b4d9"
)
CANDIDATE_SYCL_DSO_SHA256 = (
    "f0a9e736dde321f72fceb14db6fb1410a9ad090380a3cf8ed7c591e949c94305"
)
CANONICAL_ATTESTER_SHA256 = (
    "73ce1562ae5cee236f5761f36e9250409c90460593c1aa08bcd4c963d1de45da"
)
MATRIX_CLIENT_SHA256 = (
    "aac9348d09340bfdc2b21725512ff4784f1fe42be533f69f7cf8a96277a872a7"
)
MODEL_SHA256 = "f93f517f38e696d35a1a7df2c0e3155a64f4c4dcd662107a146ae263f7fb14ce"
RUNTIME_SHA256 = "1a093f09122ceb2851157042c2bbc6281ddb9d4e2de50137502890f9b52fa7d7"
SUITE_SHA256 = "053523440e4a23d7f772dec5025fe4831ba33c0a8eaba76795e4ee76718860af"
OLD_BASELINE_ORACLE_SHA256 = (
    "7a884c14ecd1705981aea63c22e8fd96b9b6646aeca98a53850d5cc54836e534"
)
OFFICIAL_C1_RESULT_SHA256 = (
    "fe03bfdd5adb826a3c9b5a68f9922c543b3767f3afce7ca388139dd6613356c4"
)
OFFICIAL_C1_MANIFEST_SHA256 = (
    "d1203c993a50c1d1ced03f20e85f96c61ee23c6c349b27326310fe8b6c4ce65c"
)
OFFICIAL_C1_MARKER_SHA256 = (
    "5cbb5809398fa6edb6ea08d96edb54e7f166328d23a4dbe0412016858c796a56"
)
EXPECTED_SHORT_CANARY_HASHES = (
    (
        "ddba4a3c5ef44f1119cfc1cac74d6088d2022f2b609d424f6bc27383d80fe97b",
        "b68f079c76adb820399ef43a2d22774eb21604ab1d0540ffa3e28ff7e40caba2",
        "7a1faf881b655dfde16b20620ca9af4c120dd98c2c71b0b017f06c4ef62d4a8c",
    ),
    (
        "8649a7bb06cd6fcd62d9def8f5711d1ec4e5fe35b2a5c8632541cc42fb9dd030",
        "29c16b970f082463d534aaa97d9d50524167c20a4d3f53e3df6dd739ef9b7a67",
        "e039c938458ad2ffa0c8e0e30033adc84c6fe973e98fa82364990e34a68ad04d",
    ),
)
EXPECTED_EXTERNAL_CANARY_HASHES = (
    "e6480d7ef60af9764f6dacb1ff1a37bacdf6dffe8b34c33d1790aed9e46fe769",
    "c972beb79fbdb3613d15baa098bf53c332dad64dbd23251d573ab885824db2ca",
    "b6c5ea9e2495278fbe9314b60c34cb3eb51421c6489478812e598f7b3cc83538",
    "4f1f6d3d02833192d6b2d16ad263e789129ea9bc101d5841c12c8958a5ccee8b",
)
EXPECTED_SERVER_BENCHMARK_IDENTITY = {
    "GGML_SYCL_ENABLE_DNN": "0",
    "GGML_SYCL_ENABLE_FLASH_ATTN": "1",
    "GGML_SYCL_ENABLE_GRAPH": "0",
    "GGML_SYCL_ENABLE_MKL_FA": "1",
    "GGML_SYCL_ENABLE_OPT": "1",
    "GGML_SYCL_ENABLE_VMM": "1",
    "GGML_SYCL_FA_ONEDNN": "1",
    "GGML_SYCL_FA_ONEDNN_MAX_KV": "0",
    "ONEAPI_DEVICE_SELECTOR": "level_zero:*",
    "batch_size": "1024",
    "cache_type_k": "f16",
    "cache_type_v": "f16",
    "cont_batching": "1",
    "ctx_size": "65536",
    "ctx_size_per_slot": "32768",
    "flash_attn": "on",
    "http_threads": "6",
    "kv_unified": "0",
    "llama_server_sha256": (
        "1a093f09122ceb2851157042c2bbc6281ddb9d4e2de50137502890f9b52fa7d7"
    ),
    "log_verbosity": "4",
    "model_alias": "qwen36-27b-q8_0-target-only",
    "model_bytes": "28595763424",
    "n_gpu_layers": "99",
    "parallel_slots": "2",
    "reasoning": "off",
    "speculation": "none",
    "threads": "8",
    "ubatch_size": "128",
    "vision_projector": "none",
}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def write_json_new(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise ValueError(f"refusing to overwrite output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    if temporary.exists():
        raise ValueError(f"temporary output already exists: {temporary}")
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


def copy_file_new(source: Path, destination: Path) -> None:
    if destination.exists():
        raise ValueError(f"refusing to overwrite output: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
    try:
        with (
            source.open("rb") as input_stream,
            os.fdopen(descriptor, "wb", closefd=True) as output_stream,
        ):
            for block in iter(lambda: input_stream.read(8 * 1024 * 1024), b""):
                output_stream.write(block)
            output_stream.flush()
            os.fsync(output_stream.fileno())
        os.link(temporary, destination)
        directory_fd = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


def load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def normalize_runtime_line(line: str) -> str:
    common = re.match(
        r"^[0-9]+\.[0-9]{2}\.[0-9]{3}\.[0-9]{3} [IWE] (?P<message>.*)$",
        line,
    )
    return common.group("message") if common else line


def exact_header_fields(
    identity_bytes: bytes,
    expected: dict[str, str],
) -> tuple[dict[str, bool], list[str]]:
    lines = identity_bytes.decode("utf-8", errors="replace").splitlines()
    delimiters = [index for index, line in enumerate(lines) if line == "--- server ---"]
    header = lines[: delimiters[0]] if delimiters else lines
    fields: dict[str, bool] = {"identity_delimiter_exactly_once": len(delimiters) == 1}
    for name, value in expected.items():
        candidates = [line for line in header if line.startswith(f"{name}=")]
        fields[f"identity_{name}_exactly_once"] = candidates == [f"{name}={value}"]
    return fields, header


def validate_runtime_reports(
    manifest_path: Path,
    manifest_sha256: str,
    reference_path: Path,
    reference_sha256: str,
    final_path: Path,
    final_sha256: str,
    canonical_attester_path: Path,
    canonical_attester_sha256: str,
) -> tuple[dict[str, bool], dict[str, Any]]:
    manifest = load_json(manifest_path, "runtime manifest")
    reference = load_json(reference_path, "runtime reference report")
    final = load_json(final_path, "runtime final report")
    if sha256_file(canonical_attester_path) != canonical_attester_sha256:
        raise ValueError("canonical attester SHA-256 mismatch")
    validator = load_module(canonical_attester_path, "canonical_dispatch_attester")
    contract, contract_errors = validator.manifest_runtime_contract(manifest)
    reference_checks, reference_errors = validator.validate_runtime_report(
        reference,
        contract,
        str(manifest_path),
        manifest_sha256,
    )
    final_checks, final_errors = validator.validate_runtime_report(
        final,
        contract,
        str(manifest_path),
        manifest_sha256,
    )
    expected_sonames = (
        sorted(contract["expected_origin"]) if contract is not None else []
    )
    fields = {
        "manifest_expected_hash_well_formed": SHA_RE.fullmatch(manifest_sha256)
        is not None,
        "reference_expected_hash_well_formed": SHA_RE.fullmatch(reference_sha256)
        is not None,
        "final_expected_hash_well_formed": SHA_RE.fullmatch(final_sha256) is not None,
        "manifest_hash_exact": sha256_file(manifest_path) == manifest_sha256
        and manifest_sha256 == CANDIDATE_MANIFEST_SHA256,
        "canonical_attester_hash_exact": canonical_attester_sha256
        == CANONICAL_ATTESTER_SHA256,
        "reference_hash_exact": sha256_file(reference_path) == reference_sha256,
        "final_hash_exact": sha256_file(final_path) == final_sha256,
        "manifest_candidate_control_supported": (
            manifest.get("experimental_controls", {}).get(CONTROL, {}).get("supported")
            is True
        ),
        "manifest_origin_first": manifest.get("runtime_loader_policy")
        == {"mode": "origin-first", "variable": "LD_LIBRARY_PATH"},
        "manifest_eight_origin_objects": len(expected_sonames) == 8,
        "manifest_contract_valid": contract is not None and not contract_errors,
        "candidate_sycl_dso_exact": contract is not None
        and contract.get("expected_origin", {})
        .get("libggml-sycl.so.0", {})
        .get("sha256")
        == CANDIDATE_SYCL_DSO_SHA256,
        "reference_report_exact": all(reference_checks.values()),
        "final_report_exact": all(final_checks.values()),
        "runtime_signature_exact": all(
            reference.get(field) == final.get(field)
            for field in RUNTIME_SIGNATURE_FIELDS
        ),
        "final_reference_path_exact": final.get("reference_report")
        == str(reference_path),
        "final_reference_match_true": final.get("reference_match") is True,
    }
    observed = {
        "expected_origin_sonames": expected_sonames,
        "manifest_contract_errors": contract_errors,
        "reference_validation_errors": reference_errors,
        "final_validation_errors": final_errors,
        "reference_checks": reference_checks,
        "final_checks": final_checks,
    }
    return fields, observed


def validate_prefix_snapshot(prefix_path: Path, full_log: bytes) -> dict[str, Any]:
    prefix = prefix_path.read_bytes()
    fields = {
        "prefix_regular_file": prefix_path.is_file() and not prefix_path.is_symlink(),
        "prefix_nonempty": bool(prefix),
        "prefix_ends_at_line_boundary": prefix.endswith(b"\n"),
        "full_log_begins_with_prefix": full_log.startswith(prefix),
    }
    normalized = [
        normalize_runtime_line(line)
        for line in prefix.decode("utf-8", errors="replace").splitlines()
    ]
    return {
        "path": str(prefix_path),
        "size_bytes": len(prefix),
        "line_count": len(normalized),
        "sha256": sha256_bytes(prefix),
        "canonical_marker_lines": [
            line
            for line in normalized
            if line.startswith(
                (
                    f"{MARKER} first-hit:",
                    f"{MARKER} summary:",
                    f"{MARKER} violation:",
                )
            )
        ],
        "fields": fields,
        "passed": all(fields.values()),
    }


def parse_selector_markers(
    full_log: bytes,
    prerelease_prefix: dict[str, Any],
    postcapture_prefix: dict[str, Any],
    selector: int,
    server_pid: str,
) -> tuple[dict[str, bool], dict[str, Any]]:
    raw_lines = full_log.decode("utf-8", errors="replace").splitlines()
    normalized = [normalize_runtime_line(line) for line in raw_lines]
    process_candidates = [line for line in raw_lines if PROCESS_BINDING in line]
    process_matches = [PROCESS_RE.fullmatch(line) for line in process_candidates]
    process_matches = [match for match in process_matches if match is not None]
    first_candidates = [
        line for line in normalized if line.startswith(f"{MARKER} first-hit:")
    ]
    first_matches = [FIRST_HIT_RE.fullmatch(line) for line in first_candidates]
    first_matches = [match for match in first_matches if match is not None]
    layouts = [match.group(1) for match in first_matches]
    first_shape_fields: list[dict[str, bool]] = []
    for match in first_matches:
        src0_ne = [int(value) for value in match.groups()[2:6]]
        src1_ne = [int(value) for value in match.groups()[6:10]]
        dst_ne = [int(value) for value in match.groups()[10:14]]
        expected_batch = [2, 1, 1] if match.group(1) == "flat" else [1, 2, 1]
        first_shape_fields.append(
            {
                "positive_matrix_dimensions": src0_ne[0] > 0 and src0_ne[1] > 0,
                "src0_is_matrix": src0_ne[2:] == [1, 1],
                "src1_layout_exact": src1_ne[1:] == expected_batch,
                "dst_layout_exact": dst_ne[1:] == expected_batch,
                "inner_dimension_exact": src1_ne[0] == src0_ne[0],
                "output_dimension_exact": dst_ne[0] == src0_ne[1],
            }
        )
    summary_candidates = [
        line for line in normalized if line.startswith(f"{MARKER} summary:")
    ]
    summary_matches = [SUMMARY_RE.fullmatch(line) for line in summary_candidates]
    summary_matches = [match for match in summary_matches if match is not None]
    summaries = [
        dict(zip(SUMMARY_FIELDS, (int(value) for value in match.groups())))
        for match in summary_matches
    ]
    violations = [
        line for line in normalized if line.startswith(f"{MARKER} violation:")
    ]
    startup_candidates = [
        line for line in normalized if line.strip().startswith(f"{CONTROL}:")
    ]
    expected_startup = f"  {CONTROL}: {selector}"
    startup_valid = startup_candidates in ([], [expected_startup])
    prerelease_markers = prerelease_prefix.get("canonical_marker_lines", [])
    postcapture_markers = postcapture_prefix.get("canonical_marker_lines", [])
    process_line_numbers = [
        index
        for index, line in enumerate(raw_lines, 1)
        if PROCESS_RE.fullmatch(line) is not None
    ]
    route_line_numbers = [
        index
        for index, line in enumerate(normalized, 1)
        if line.startswith(
            (
                f"{MARKER} first-hit:",
                f"{MARKER} summary:",
                f"{MARKER} violation:",
            )
        )
    ]
    startup_line_numbers = [
        index
        for index, line in enumerate(normalized, 1)
        if line.strip().startswith(f"{CONTROL}:")
    ]
    summary_line_numbers = [
        index
        for index, line in enumerate(normalized, 1)
        if line.startswith(f"{MARKER} summary:")
    ]
    postcapture_line_count = int(postcapture_prefix.get("line_count", -1))
    summary = summaries[0] if len(summaries) == 1 else None
    dispatch_sum = (
        summary["flat_dispatches"] + summary["recurrent_dispatches"]
        if summary is not None
        else None
    )
    summary_internal_consistency = summary is None or (
        summary["flat_multicol_suppressed"] == summary["flat_dispatches"]
        and summary["recurrent_dmmv_suppressed"] == summary["recurrent_dispatches"]
        and summary["reorder_ready_dispatches"] == dispatch_sum
        and summary["single_col_mmvq_calls"] == 2 * dispatch_sum
        and summary["violations"] == 0
    )
    fields = {
        "process_binding_exactly_once": len(process_candidates) == 1
        and len(process_matches) == 1,
        "process_binding_pid_exact": len(process_matches) == 1
        and process_matches[0].group(1) == server_pid,
        "process_binding_precedes_route_markers": len(process_line_numbers) == 1
        and (
            not route_line_numbers or process_line_numbers[0] < min(route_line_numbers)
        ),
        "startup_marker_optional_but_exact": startup_valid,
        "startup_order_valid_if_present": not startup_line_numbers
        or (
            len(startup_line_numbers) == 1
            and len(process_line_numbers) == 1
            and process_line_numbers[0] < startup_line_numbers[0]
            and (
                not route_line_numbers
                or startup_line_numbers[0] < min(route_line_numbers)
            )
        ),
        "no_violation_markers": not violations,
        "summary_optional_but_well_formed": len(summary_candidates)
        == len(summary_matches)
        and len(summary_candidates) <= 1,
        "summary_internal_consistency_if_present": summary_internal_consistency,
        "summary_after_postcapture_if_present": not summary_candidates
        or (
            len(summary_line_numbers) == 1
            and postcapture_line_count > 0
            and summary_line_numbers[0] > postcapture_line_count
        ),
    }
    if selector == 0:
        fields.update(
            {
                "selector_off_zero_first_hits": not first_candidates,
                "selector_off_zero_canonical_route_markers": not any(
                    line.startswith(
                        (
                            f"{MARKER} first-hit:",
                            f"{MARKER} summary:",
                            f"{MARKER} violation:",
                        )
                    )
                    for line in normalized
                ),
                "selector_off_summary_absent": not summary_candidates,
            }
        )
    else:
        fields.update(
            {
                "selector_on_first_hits_well_formed": len(first_candidates)
                == len(first_matches),
                "selector_on_first_hit_shapes_exact": bool(first_shape_fields)
                and all(all(item.values()) for item in first_shape_fields),
                "selector_on_flat_first_hit_exactly_once": layouts == ["flat"],
                "selector_on_recurrent_first_hit_absent": "recurrent" not in layouts,
                "selector_on_summary_route_consistent_if_present": summary is None
                or (
                    summary["flat_dispatches"] > 0
                    and summary["recurrent_dispatches"] == 0
                ),
                "selector_on_prerelease_exact_flat_hit": bool(prerelease_markers)
                and len(prerelease_markers) == 1
                and f"{MARKER} first-hit: layout=flat " in prerelease_markers[0],
                "selector_on_prerelease_no_recurrent_summary_or_violation": not any(
                    any(
                        term in line
                        for term in ("layout=recurrent", " summary:", " violation:")
                    )
                    for line in prerelease_markers
                ),
                "selector_on_postcapture_exact_flat_marker_only": len(
                    postcapture_markers
                )
                == 1
                and f"{MARKER} first-hit: layout=flat " in postcapture_markers[0],
            }
        )
    observed = {
        "process_binding_candidates": process_candidates,
        "first_hit_layouts": layouts,
        "first_hit_shape_fields": first_shape_fields,
        "summary": summary,
        "violation_lines": violations,
        "startup_candidates": startup_candidates,
        "prerelease_canonical_marker_lines": prerelease_markers,
        "postcapture_canonical_marker_lines": postcapture_markers,
        "summary_present": summary is not None,
        "summary_well_formed": len(summary_candidates) == len(summary_matches),
        "summary_internal_consistency": summary_internal_consistency,
        "summary_line_numbers": summary_line_numbers,
        "postcapture_line_count": postcapture_line_count,
        "flat_first_hit_present_before_release": any(
            f"{MARKER} first-hit: layout=flat " in line for line in prerelease_markers
        ),
        "recurrent_first_hit_present_before_release": any(
            f"{MARKER} first-hit: layout=recurrent " in line
            for line in prerelease_markers
        ),
        "attribution_guard": (
            "Phase 1 uses only first-hit route evidence. Any retained summary is "
            "optional and checked only for internal consistency; its totals are not "
            "used or claimed, and this phase makes no request-time dispatch claim."
        ),
    }
    return fields, observed


def validate_oracle(
    oracle: dict[str, Any],
    model_sha256: str,
    runtime_sha256: str,
    suite_sha256: str,
) -> tuple[dict[str, bool], dict[str, dict[str, Any]]]:
    identity = oracle.get("run_identity")
    identity = identity if isinstance(identity, dict) else {}
    rows = oracle.get("rows")
    rows = rows if isinstance(rows, list) else []
    semantic = oracle.get("semantic_retrieval")
    semantic = semantic if isinstance(semantic, list) else []
    canaries = oracle.get("canaries")
    canaries = canaries if isinstance(canaries, list) else []
    external_canaries = oracle.get("external_baseline_canaries")
    external_canaries = external_canaries if isinstance(external_canaries, list) else []
    row_fields: list[bool] = []
    by_case: dict[str, dict[str, Any]] = {}
    for row in rows:
        valid = isinstance(row, dict)
        if not valid:
            row_fields.append(False)
            continue
        tokens = row.get("token_ids")
        valid = (
            isinstance(tokens, list)
            and len(tokens) == 512
            and all(
                isinstance(token, int) and not isinstance(token, bool) and token >= 0
                for token in tokens
            )
            and row.get("token_count") == 512
            and row.get("token_ids_sha256")
            == sha256_bytes(json.dumps(tokens, separators=(",", ":")).encode())
            and row.get("passed") is True
            and row.get("case_id") in EXPECTED_CASES
            and type(row.get("slot_id")) is int
            and row.get("slot_id") in (0, 1)
            and row.get("stream_id_slot") == row.get("slot_id")
            and type(row.get("stream_id_slot")) is int
            and row.get("replay_id_slot") == row.get("slot_id")
            and type(row.get("replay_id_slot")) is int
            and row.get("stream_predicted_n") == 512
            and row.get("replay_predicted_n") == 512
            and row.get("stream_stop_type") == "limit"
            and row.get("replay_stop_type") == "limit"
            and row.get("stream_truncated") is False
            and row.get("replay_truncated") is False
            and row.get("stream_cache_n") == 0
            and type(row.get("stream_cache_n")) is int
            and row.get("replay_cache_n") == 0
            and type(row.get("replay_cache_n")) is int
            and row.get("stream_alignment_unique") is True
            and row.get("stream_token_ids") == tokens
            and row.get("stream_to_complete_positions") == list(range(512))
            and isinstance(row.get("content_sha256"), str)
            and SHA_RE.fullmatch(row["content_sha256"]) is not None
            and isinstance(row.get("prompt_sha256"), str)
            and SHA_RE.fullmatch(row["prompt_sha256"]) is not None
            and isinstance(row.get("rendered_prompt_sha256"), str)
            and SHA_RE.fullmatch(row["rendered_prompt_sha256"]) is not None
        )
        row_fields.append(valid)
        if valid:
            by_case[row["case_id"]] = row
    semantic_by_case: dict[str, dict[str, Any]] = {}
    semantic_fields: list[bool] = []
    for item in semantic:
        valid = isinstance(item, dict)
        if not valid:
            semantic_fields.append(False)
            continue
        case_id = item.get("case_id")
        content = item.get("content")
        expected_slot = (
            EXPECTED_CASES.index(case_id) if case_id in EXPECTED_CASES else -1
        )
        valid = (
            case_id in EXPECTED_CASES
            and isinstance(content, str)
            and item.get("content_sha256") == sha256_bytes(content.encode())
            and item.get("passed") is True
            and type(item.get("slot_id")) is int
            and item.get("slot_id") == expected_slot
            and type(item.get("observed_slot_id")) is int
            and item.get("observed_slot_id") == expected_slot
            and item.get("forced_512_content_prefix_exact") is True
            and item.get("forced_512_pre_eos_token_prefix_exact") is True
            and isinstance(item.get("token_ids"), list)
            and bool(item["token_ids"])
            and item.get("token_count") == len(item["token_ids"])
            and item.get("predicted_n") == len(item["token_ids"])
            and all(type(token) is int and token >= 0 for token in item["token_ids"])
            and item.get("token_ids_sha256")
            == sha256_bytes(
                json.dumps(item["token_ids"], separators=(",", ":")).encode()
            )
            and item.get("forced_512_token_ids_sha256")
            == by_case.get(case_id, {}).get("token_ids_sha256")
            and item.get("cache_n") == 0
            and type(item.get("cache_n")) is int
            and item.get("stop_type") == "eos"
            and item.get("truncated") is False
            and isinstance(item.get("validation"), dict)
            and item["validation"].get("pass") is True
        )
        semantic_fields.append(valid)
        if valid:
            semantic_by_case[case_id] = item
    canary_fields: list[bool] = []
    for index, item in enumerate(canaries):
        tokens = item.get("token_ids") if isinstance(item, dict) else None
        expected_case = EXPECTED_CASES[index] if index < len(EXPECTED_CASES) else None
        expected_hashes = (
            EXPECTED_SHORT_CANARY_HASHES[index]
            if index < len(EXPECTED_SHORT_CANARY_HASHES)
            else None
        )
        canary_fields.append(
            isinstance(item, dict)
            and item.get("passed") is True
            and item.get("case_id") == expected_case
            and item.get("slot_id") == index
            and type(item.get("slot_id")) is int
            and item.get("observed_slot_id") == index
            and type(item.get("observed_slot_id")) is int
            and isinstance(tokens, list)
            and len(tokens) == 128
            and all(type(token) is int and token >= 0 for token in tokens)
            and item.get("token_ids_sha256")
            == sha256_bytes(json.dumps(tokens, separators=(",", ":")).encode())
            and isinstance(item.get("content_sha256"), str)
            and SHA_RE.fullmatch(item["content_sha256"]) is not None
            and item.get("cache_n") == 0
            and type(item.get("cache_n")) is int
            and item.get("predicted_n") == 128
            and item.get("stop_type") == "limit"
            and item.get("truncated") is False
            and (
                item.get("token_ids_sha256"),
                item.get("content_sha256"),
                item.get("rendered_prompt_sha256"),
            )
            == expected_hashes
        )
    external_fields: list[bool] = []
    for index, item in enumerate(external_canaries):
        tokens = item.get("token_ids") if isinstance(item, dict) else None
        content = item.get("content") if isinstance(item, dict) else None
        external_fields.append(
            isinstance(item, dict)
            and item.get("passed") is True
            and item.get("prompt_id") == "incident-retrospective"
            and item.get("slot_id_requested") == index
            and type(item.get("slot_id_requested")) is int
            and item.get("slot_id_observed") == index
            and type(item.get("slot_id_observed")) is int
            and item.get("oracle_sha256")
            == "e4477808823cdf9bb182d5abc4788cee216011a0195cf49bf03a7bda35f5dbcc"
            and item.get("suite_sha256")
            == "df03f49d36c36d2b8ac4cd117b7cb2e42c74878af1f6926690ebb89eeccd47ac"
            and isinstance(tokens, list)
            and len(tokens) == 128
            and all(type(token) is int and token >= 0 for token in tokens)
            and item.get("token_ids_sha256")
            == sha256_bytes(json.dumps(tokens, separators=(",", ":")).encode())
            and isinstance(content, str)
            and item.get("content_sha256") == sha256_bytes(content.encode())
            and item.get("cache_n") == 0
            and type(item.get("cache_n")) is int
            and item.get("predicted_n") == 128
            and item.get("stop_type") == "limit"
            and item.get("truncated") is False
            and isinstance(item.get("checks"), dict)
            and bool(item["checks"])
            and all(value is True for value in item["checks"].values())
            and (
                item.get("token_ids_sha256"),
                item.get("content_sha256"),
                item.get("prompt_sha256"),
                item.get("rendered_prompt_sha256"),
            )
            == EXPECTED_EXTERNAL_CANARY_HASHES
        )
    intrinsic = oracle.get("intrinsic_gate")
    intrinsic = intrinsic if isinstance(intrinsic, dict) else {}
    occupancy = oracle.get("decode_occupancy")
    occupancy = occupancy if isinstance(occupancy, dict) else {}
    metrics_before = occupancy.get("metrics_before")
    metrics_before = metrics_before if isinstance(metrics_before, dict) else {}
    metrics_after = occupancy.get("metrics_after_streaming_rows")
    metrics_after = metrics_after if isinstance(metrics_after, dict) else {}
    slot_topology = oracle.get("slot_topology")
    slot_topology = slot_topology if isinstance(slot_topology, dict) else {}
    slots_before = slot_topology.get("before")
    slots_after = slot_topology.get("after")
    slots_before = slots_before if isinstance(slots_before, list) else []
    slots_after = slots_after if isinstance(slots_after, list) else []
    fields = {
        "mode_sequential_oracle": identity.get("mode") == "sequential-oracle",
        "forward_order": identity.get("case_order") == "forward",
        "model_exact": identity.get("model_sha256") == model_sha256,
        "runtime_exact": identity.get("runtime_sha256") == runtime_sha256,
        "suite_exact": identity.get("suite_sha256") == suite_sha256,
        "short_band": identity.get("band") == "short",
        "exact_c2_topology": identity.get("ctx_size_total") == 65536
        and identity.get("ctx_size_per_slot") == 32768
        and identity.get("parallel_slots") == 2,
        "f16_kv": identity.get("cache_type_k") == "f16"
        and identity.get("cache_type_v") == "f16",
        "forced_512": identity.get("max_tokens") == 512
        and identity.get("ignore_eos") is True
        and identity.get("cache_prompt") is False
        and type(identity.get("seed")) is int
        and identity.get("seed") == 1
        and identity.get("slot_ids") == [0, 1]
        and all(type(value) is int for value in identity.get("slot_ids", []))
        and identity.get("baseline_canary_slot_ids") == [0, 1]
        and all(
            type(value) is int for value in identity.get("baseline_canary_slot_ids", [])
        ),
        "rows_exact": len(rows) == 2
        and all(row_fields)
        and set(by_case) == set(EXPECTED_CASES),
        "semantic_retrieval_exact": len(semantic) == 2
        and all(semantic_fields)
        and set(semantic_by_case) == set(EXPECTED_CASES),
        "slot_assignment_exact": len(rows) == 2
        and [row.get("slot_id") for row in rows if isinstance(row, dict)] == [0, 1]
        and [row.get("case_id") for row in rows if isinstance(row, dict)]
        == list(EXPECTED_CASES),
        "intrinsic_gate_passed": set(intrinsic)
        == {
            "canaries_passed",
            "external_baseline_canary_passed",
            "overlap_passed",
            "passed",
            "rows_passed",
            "semantic_retrieval_passed",
            "timing_endpoints_present",
        }
        and all(value is True for value in intrinsic.values()),
        "canaries_exact": len(canaries) == 2 and all(canary_fields),
        "external_canaries_exact": len(external_canaries) == 2
        and all(external_fields)
        and identity.get("baseline_canary_oracle_sha256")
        == "e4477808823cdf9bb182d5abc4788cee216011a0195cf49bf03a7bda35f5dbcc"
        and identity.get("baseline_canary_suite_sha256")
        == "df03f49d36c36d2b8ac4cd117b7cb2e42c74878af1f6926690ebb89eeccd47ac"
        and identity.get("baseline_canary_prompt_id") == "incident-retrospective",
        "baseline_capture_ready": isinstance(oracle.get("oracle_comparison"), dict)
        and oracle["oracle_comparison"].get("status") == "BASELINE_CAPTURE_READY",
        "slot_topology_passed": slot_topology.get("passed") is True
        and slot_topology.get("official_timing_polled_slots") is False
        and len(slots_before) == 2
        and len(slots_after) == 2
        and [slot.get("id") for slot in slots_before if isinstance(slot, dict)]
        == [0, 1]
        and [slot.get("id") for slot in slots_after if isinstance(slot, dict)] == [0, 1]
        and all(
            isinstance(slot, dict)
            and type(slot.get("id")) is int
            and slot.get("is_processing") is False
            and slot.get("n_ctx") == 32768
            and slot.get("speculative") is False
            for slot in slots_before + slots_after
        ),
        "decode_occupancy_passed": occupancy.get("passed") is True
        and occupancy.get("tokens_predicted_delta") == 1024.0
        and type(occupancy.get("tokens_predicted_delta")) in (int, float)
        and occupancy.get("llama_decode_calls_delta") == 1032.0
        and type(occupancy.get("llama_decode_calls_delta")) in (int, float)
        and metrics_before.get("n_decode_total") == 0.0
        and type(metrics_before.get("n_decode_total")) in (int, float)
        and metrics_before.get("tokens_predicted_total") == 0.0
        and type(metrics_before.get("tokens_predicted_total")) in (int, float)
        and metrics_before.get("n_busy_slots_per_decode") == 0.0
        and type(metrics_before.get("n_busy_slots_per_decode")) in (int, float)
        and metrics_after.get("n_decode_total") == 1032.0
        and type(metrics_after.get("n_decode_total")) in (int, float)
        and metrics_after.get("tokens_predicted_total") == 1024.0
        and type(metrics_after.get("tokens_predicted_total")) in (int, float)
        and metrics_after.get("n_busy_slots_per_decode") == 1.0
        and type(metrics_after.get("n_busy_slots_per_decode")) in (int, float)
        and occupancy.get("llama_decode_calls_delta")
        == (
            metrics_after.get("n_decode_total", 0)
            - metrics_before.get("n_decode_total", 0)
        )
        and occupancy.get("tokens_predicted_delta")
        == (
            metrics_after.get("tokens_predicted_total", 0)
            - metrics_before.get("tokens_predicted_total", 0)
        )
        and isinstance(occupancy.get("predicted_tokens_per_llama_decode"), (int, float))
        and not isinstance(occupancy.get("predicted_tokens_per_llama_decode"), bool)
        and math.isfinite(occupancy["predicted_tokens_per_llama_decode"])
        and math.isclose(
            occupancy["predicted_tokens_per_llama_decode"],
            occupancy["tokens_predicted_delta"] / occupancy["llama_decode_calls_delta"],
            rel_tol=1e-12,
            abs_tol=1e-12,
        ),
        "server_benchmark_identity_exact": identity.get("server_benchmark_identity")
        == EXPECTED_SERVER_BENCHMARK_IDENTITY,
    }
    comparison_rows = {
        case_id: {
            **row,
            "_semantic_content": semantic_by_case.get(case_id, {}).get("content"),
            "_semantic_content_sha256": semantic_by_case.get(case_id, {}).get(
                "content_sha256"
            ),
            "_semantic_token_ids": semantic_by_case.get(case_id, {}).get("token_ids"),
            "_semantic_token_ids_sha256": semantic_by_case.get(case_id, {}).get(
                "token_ids_sha256"
            ),
            "_canary_token_ids": (
                canaries[EXPECTED_CASES.index(case_id)].get("token_ids")
                if len(canaries) == 2
                and isinstance(canaries[EXPECTED_CASES.index(case_id)], dict)
                else None
            ),
            "_canary_token_ids_sha256": (
                canaries[EXPECTED_CASES.index(case_id)].get("token_ids_sha256")
                if len(canaries) == 2
                and isinstance(canaries[EXPECTED_CASES.index(case_id)], dict)
                else None
            ),
            "_canary_content_sha256": (
                canaries[EXPECTED_CASES.index(case_id)].get("content_sha256")
                if len(canaries) == 2
                and isinstance(canaries[EXPECTED_CASES.index(case_id)], dict)
                else None
            ),
            "_external_token_ids": (
                external_canaries[EXPECTED_CASES.index(case_id)].get("token_ids")
                if len(external_canaries) == 2
                and isinstance(external_canaries[EXPECTED_CASES.index(case_id)], dict)
                else None
            ),
            "_external_token_ids_sha256": (
                external_canaries[EXPECTED_CASES.index(case_id)].get("token_ids_sha256")
                if len(external_canaries) == 2
                and isinstance(external_canaries[EXPECTED_CASES.index(case_id)], dict)
                else None
            ),
            "_external_content": (
                external_canaries[EXPECTED_CASES.index(case_id)].get("content")
                if len(external_canaries) == 2
                and isinstance(external_canaries[EXPECTED_CASES.index(case_id)], dict)
                else None
            ),
            "_external_content_sha256": (
                external_canaries[EXPECTED_CASES.index(case_id)].get("content_sha256")
                if len(external_canaries) == 2
                and isinstance(external_canaries[EXPECTED_CASES.index(case_id)], dict)
                else None
            ),
        }
        for case_id, row in by_case.items()
    }
    return fields, comparison_rows


def validate_live_attestation(
    oracle: dict[str, Any],
    server_attestation_path: Path,
    server_attestation_sha256: str,
    binding_before_path: Path,
    binding_after_path: Path,
    matrix_client_path: Path,
    matrix_client_sha256: str,
    runtime_sha256: str,
    server_pid: str,
    port: int,
    oracle_path: Path,
    prerelease_prefix_path: Path,
    postcapture_prefix_path: Path,
) -> tuple[dict[str, bool], dict[str, Any]]:
    if (
        matrix_client_sha256 != MATRIX_CLIENT_SHA256
        or sha256_file(matrix_client_path) != MATRIX_CLIENT_SHA256
    ):
        raise ValueError("matrix client SHA-256 mismatch")
    matrix = load_module(matrix_client_path, "canonical_c1_matrix_binding")
    attestation = load_json(server_attestation_path, "live c2 server attestation")
    before = load_json(binding_before_path, "live binding before capture")
    after = load_json(binding_after_path, "live binding after capture")
    server_fields = matrix.attest_server(
        attestation, oracle.get("run_identity") or {}, runtime_sha256
    )
    continuity = matrix.compare_live_server_bindings(before, after)
    attestation_binding = matrix.bind_attestation_to_process(
        server_attestation_path, before
    )
    identity = oracle.get("run_identity") or {}
    before_capture_ns = before.get("captured_at_epoch_ns")
    after_capture_ns = after.get("captured_at_epoch_ns")
    oracle_mtime_ns = oracle_path.stat().st_mtime_ns
    prerelease_mtime_ns = prerelease_prefix_path.stat().st_mtime_ns
    postcapture_mtime_ns = postcapture_prefix_path.stat().st_mtime_ns
    argv = before.get("argv")
    argv = argv if isinstance(argv, list) else []
    fields = {
        "server_attestation_expected_hash_well_formed": SHA_RE.fullmatch(
            server_attestation_sha256
        )
        is not None,
        "server_attestation_hash_exact": sha256_file(server_attestation_path)
        == server_attestation_sha256,
        "server_attestation_contract_exact": all(server_fields.values()),
        "oracle_server_attestation_hash_exact": identity.get(
            "server_attestation_sha256"
        )
        == server_attestation_sha256,
        "oracle_server_attestation_path_exact": os.path.realpath(
            str(identity.get("server_attestation_path", ""))
        )
        == os.path.realpath(server_attestation_path),
        "oracle_base_url_exact": identity.get("base_url") == f"http://127.0.0.1:{port}",
        "binding_before_passed": before.get("passed") is True,
        "binding_after_passed": after.get("passed") is True,
        "binding_continuity_passed": continuity.get("passed") is True,
        "attestation_process_binding_passed": attestation_binding.get("passed") is True,
        "binding_pid_exact": before.get("pid") == int(server_pid)
        and after.get("pid") == int(server_pid),
        "binding_port_exact": (before.get("fields") or {}).get("port_argument_exact")
        is True
        and (after.get("fields") or {}).get("port_argument_exact") is True,
        "binding_runtime_exact": before.get("executable_sha256") == runtime_sha256
        and after.get("executable_sha256") == runtime_sha256,
        "binding_argv_exact_across_capture": before.get("argv") == after.get("argv"),
        "sleep_idle_argv_absent": "--sleep-idle-seconds" not in argv,
        "binding_capture_times_exact": type(before_capture_ns) is int
        and type(after_capture_ns) is int
        and before_capture_ns > 0
        and prerelease_mtime_ns <= before_capture_ns
        and before_capture_ns <= oracle_mtime_ns
        and oracle_mtime_ns <= after_capture_ns
        and after_capture_ns <= postcapture_mtime_ns,
    }
    return fields, {
        "server_fields": server_fields,
        "binding_before": before,
        "binding_after": after,
        "continuity": continuity,
        "attestation_process_binding": attestation_binding,
        "capture_time_order": {
            "before_capture_epoch_ns": before_capture_ns,
            "prerelease_prefix_mtime_epoch_ns": prerelease_mtime_ns,
            "oracle_mtime_epoch_ns": oracle_mtime_ns,
            "after_capture_epoch_ns": after_capture_ns,
            "postcapture_prefix_mtime_epoch_ns": postcapture_mtime_ns,
        },
    }


def capture_live_binding(args: argparse.Namespace) -> int:
    if (
        args.matrix_client_sha256 != MATRIX_CLIENT_SHA256
        or sha256_file(args.matrix_client) != MATRIX_CLIENT_SHA256
    ):
        raise ValueError("matrix client SHA-256 mismatch")
    if PID_RE.fullmatch(args.server_pid) is None:
        raise ValueError("server PID must be a positive decimal")
    matrix = load_module(args.matrix_client, "canonical_c1_live_binding")
    binding = matrix.capture_live_server_binding(
        int(args.server_pid), args.port, args.runtime_sha256
    )
    binding["captured_at_epoch_ns"] = time.time_ns()
    write_json_new(args.out, binding)
    return 0 if binding.get("passed") is True else 1


def attest_lane(args: argparse.Namespace) -> int:
    for path in (
        args.oracle,
        args.server_log,
        args.identity_log,
        args.prerelease_prefix,
        args.postcapture_prefix,
        args.runtime_manifest,
        args.runtime_reference_report,
        args.runtime_final_report,
        args.canonical_attester,
        args.server_attestation,
        args.binding_before,
        args.binding_after,
        args.matrix_client,
    ):
        if not path.is_file():
            raise ValueError(f"required input is not a file: {path}")
    if args.selector not in (0, 1):
        raise ValueError("selector must be 0 or 1")
    if PID_RE.fullmatch(args.server_pid) is None:
        raise ValueError("server PID must be a positive decimal")
    oracle = load_json(args.oracle, "sequential oracle")
    oracle_fields, _ = validate_oracle(
        oracle, args.model_sha256, args.runtime_sha256, args.suite_sha256
    )
    full_log = args.server_log.read_bytes()
    identity_bytes = args.identity_log.read_bytes()
    prerelease_prefix = validate_prefix_snapshot(args.prerelease_prefix, full_log)
    postcapture_prefix = validate_prefix_snapshot(args.postcapture_prefix, full_log)
    prefix_order_fields = {
        "prerelease_is_postcapture_prefix": args.postcapture_prefix.read_bytes().startswith(
            args.prerelease_prefix.read_bytes()
        ),
    }
    runtime_fields, runtime_observed = validate_runtime_reports(
        args.runtime_manifest.resolve(),
        args.runtime_manifest_sha256,
        args.runtime_reference_report.resolve(),
        args.runtime_reference_report_sha256,
        args.runtime_final_report.resolve(),
        args.runtime_final_report_sha256,
        args.canonical_attester.resolve(),
        args.canonical_attester_sha256,
    )
    live_fields, live_observed = validate_live_attestation(
        oracle,
        args.server_attestation.resolve(),
        args.server_attestation_sha256,
        args.binding_before.resolve(),
        args.binding_after.resolve(),
        args.matrix_client.resolve(),
        args.matrix_client_sha256,
        args.runtime_sha256,
        args.server_pid,
        args.port,
        args.oracle,
        args.prerelease_prefix,
        args.postcapture_prefix,
    )
    manifest = load_json(args.runtime_manifest, "runtime manifest")
    expected_header = {
        "gpu_index": str(args.gpu_index),
        "host": "127.0.0.1",
        "port": str(args.port),
        "ZE_AFFINITY_MASK": str(args.gpu_index),
        "gpu_lease_path": (
            f"/run/user/{os.getuid()}/qwen36-b70-gpu-leases/gpu{args.gpu_index}.lock"
        ),
        "port_lease_path": (
            f"/run/user/{os.getuid()}/qwen36-b70-port-leases/port{args.port}.lock"
        ),
        CONTROL: str(args.selector),
        "GGML_SYCL_ENABLE_OPT": "1",
        "GGML_SYCL_ENABLE_GRAPH": "0",
        "GGML_SYCL_PRIORITIZE_DMMV": "0",
        "runtime_bundle_verified": "1",
        "runtime_manifest": str(args.runtime_manifest.resolve()),
        "runtime_manifest_sha256": args.runtime_manifest_sha256,
        "llama_server": manifest["llama_server_path"],
        "llama_server_sha256": manifest["llama_server_sha256"],
        "runtime_loader_policy": "origin-first",
        "runtime_loader_origin": str(Path(manifest["llama_server_path"]).parent),
        "runtime_loader_origin_precedence": "1",
        "server_pid": args.server_pid,
        "server_output_log": str(args.server_log.resolve()),
        "ctx_size": "65536",
        "parallel_slots": "2",
        "ctx_size_per_slot": "32768",
        "kv_unified": "0",
        "sleep_idle_seconds": "-1",
    }
    identity_fields, _ = exact_header_fields(identity_bytes, expected_header)
    marker_fields, marker_observed = parse_selector_markers(
        full_log,
        prerelease_prefix,
        postcapture_prefix,
        args.selector,
        args.server_pid,
    )
    fields = {
        "oracle": all(oracle_fields.values()),
        "identity": all(identity_fields.values()),
        "runtime": all(runtime_fields.values()),
        "prefix_boundaries": all(
            prefix["passed"]
            for prefix in (
                prerelease_prefix,
                postcapture_prefix,
            )
        )
        and all(prefix_order_fields.values()),
        "selector_markers": all(marker_fields.values()),
        "live_server_binding": all(live_fields.values()),
    }
    result = {
        "schema_version": SCHEMA_VERSION,
        "status": "PASS" if all(fields.values()) else "FAIL",
        "passed": all(fields.values()),
        "evidence_class": "diagnostic-only",
        "performance_promotable": False,
        "phase": "sequential-c1-oracle-on-c2-topology",
        "gpu_index": args.gpu_index,
        "selector": args.selector,
        "server_pid": args.server_pid,
        "fields": fields,
        "oracle_fields": oracle_fields,
        "identity_fields": identity_fields,
        "runtime_fields": runtime_fields,
        "marker_fields": marker_fields,
        "live_server_fields": live_fields,
        "observed": {
            "runtime": runtime_observed,
            "markers": marker_observed,
            "prefixes": {
                "prerelease": prerelease_prefix,
                "postcapture": postcapture_prefix,
                "ordering_fields": prefix_order_fields,
            },
            "live_server": live_observed,
        },
        "inputs": {
            name: {
                "path": str(path.resolve()),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for name, path in (
                ("oracle", args.oracle),
                ("server_log", args.server_log),
                ("identity_log", args.identity_log),
                ("prerelease_prefix", args.prerelease_prefix),
                ("postcapture_prefix", args.postcapture_prefix),
                ("runtime_manifest", args.runtime_manifest),
                ("runtime_reference_report", args.runtime_reference_report),
                ("runtime_final_report", args.runtime_final_report),
                ("canonical_attester", args.canonical_attester),
                ("server_attestation", args.server_attestation),
                ("binding_before", args.binding_before),
                ("binding_after", args.binding_after),
                ("matrix_client", args.matrix_client),
                ("study_analyzer", Path(__file__).resolve()),
            )
        },
    }
    write_json_new(args.out, result)
    return 0 if result["passed"] else 1


def parse_manifest(
    directory: Path,
    manifest_name: str,
    marker_name: str = "diagnostic-completion-status.json",
) -> tuple[bool, str]:
    manifest = directory / manifest_name
    if not manifest.is_file():
        return False, ""
    lines = manifest.read_text().splitlines()
    if not lines:
        return False, ""
    seen: set[str] = set()
    relative_paths: list[str] = []
    for raw in lines:
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", raw)
        if match is None:
            return False, ""
        expected, relative = match.groups()
        relative = relative[2:] if relative.startswith("./") else relative
        candidate = Path(relative)
        if (
            not relative
            or candidate.is_absolute()
            or ".." in candidate.parts
            or relative in seen
        ):
            return False, ""
        seen.add(relative)
        relative_paths.append(relative)
        path = directory / relative
        try:
            if (
                not path.is_file()
                or path.is_symlink()
                or path.resolve().parent != directory.resolve()
                and directory.resolve() not in path.resolve().parents
                or sha256_file(path) != expected
            ):
                return False, ""
        except OSError:
            return False, ""
    if relative_paths != sorted(relative_paths):
        return False, ""
    if any(path.is_symlink() for path in directory.rglob("*")):
        return False, ""
    excluded = {manifest_name, marker_name}
    actual = {
        str(path.relative_to(directory))
        for path in directory.rglob("*")
        if path.is_file()
        and not path.is_symlink()
        and str(path.relative_to(directory)) not in excluded
        and not str(path.relative_to(directory)).startswith(f".{manifest_name}.")
    }
    if seen != actual:
        return False, ""
    return True, sha256_file(manifest)


def validate_official_c1_packet(
    directory: Path,
    expected_result_sha256: str,
    expected_manifest_sha256: str,
    expected_marker_sha256: str,
    old_rows: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    result_path = directory / "exact-tokens.json"
    manifest_path = directory / "artifacts.sha256"
    marker_path = directory / "completion-status.json"
    for path in (result_path, manifest_path, marker_path):
        if not path.is_file():
            raise ValueError(f"official c1 packet input missing: {path}")
    manifest_valid, observed_manifest_sha = parse_manifest(
        directory, "artifacts.sha256", "completion-status.json"
    )
    result = load_json(result_path, "official c1 exact result")
    marker = load_json(marker_path, "official c1 completion marker")
    rows = result.get("rows")
    rows = rows if isinstance(rows, list) else []
    by_case: dict[str, dict[str, Any]] = {}
    row_fields: list[bool] = []
    for row in rows:
        valid = isinstance(row, dict)
        if not valid:
            row_fields.append(False)
            continue
        tokens = row.get("token_ids")
        case_id = row.get("prompt_id")
        content = row.get("content")
        valid = (
            case_id in EXPECTED_CASES
            and isinstance(tokens, list)
            and len(tokens) == 512
            and all(type(token) is int and token >= 0 for token in tokens)
            and row.get("token_ids_sha256")
            == sha256_bytes(json.dumps(tokens, separators=(",", ":")).encode())
            and isinstance(content, str)
            and row.get("content_sha256") == sha256_bytes(content.encode())
            and row.get("final_predicted_n") == 512
            and row.get("id_slot") == 0
            and type(row.get("id_slot")) is int
            and isinstance(row.get("prompt_sha256"), str)
            and SHA_RE.fullmatch(row["prompt_sha256"]) is not None
            and isinstance(row.get("rendered_prompt_sha256"), str)
            and SHA_RE.fullmatch(row["rendered_prompt_sha256"]) is not None
        )
        row_fields.append(valid)
        if valid:
            by_case[case_id] = row
    comparisons: list[dict[str, Any]] = []
    for case_id in EXPECTED_CASES:
        official = by_case.get(case_id, {})
        sequential = old_rows.get(case_id, {})
        fields = {
            "token_ids_exact": official.get("token_ids") == sequential.get("token_ids"),
            "token_ids_sha256_exact": official.get("token_ids_sha256")
            == sequential.get("token_ids_sha256"),
            "content_sha256_exact": official.get("content_sha256")
            == sequential.get("content_sha256"),
            "prompt_sha256_exact": official.get("prompt_sha256")
            == sequential.get("prompt_sha256"),
            "rendered_prompt_sha256_exact": official.get("rendered_prompt_sha256")
            == sequential.get("rendered_prompt_sha256"),
        }
        comparisons.append(
            {"case_id": case_id, "fields": fields, "passed": all(fields.values())}
        )
    fields = {
        "result_hash_exact": expected_result_sha256 == OFFICIAL_C1_RESULT_SHA256
        and sha256_file(result_path) == OFFICIAL_C1_RESULT_SHA256,
        "manifest_hash_exact": expected_manifest_sha256 == OFFICIAL_C1_MANIFEST_SHA256
        and observed_manifest_sha == OFFICIAL_C1_MANIFEST_SHA256,
        "manifest_valid": manifest_valid,
        "marker_hash_exact": expected_marker_sha256 == OFFICIAL_C1_MARKER_SHA256
        and sha256_file(marker_path) == OFFICIAL_C1_MARKER_SHA256,
        "marker_exact": marker.get("status") == "PASS"
        and marker.get("evidence_valid") is True
        and marker.get("evidence_class") == "official-isolated"
        and marker.get("run_scope") == "promotion512"
        and marker.get("full512_band") == "short"
        and marker.get("gpu_index") == 0
        and marker.get("result_sha256") == OFFICIAL_C1_RESULT_SHA256
        and marker.get("artifacts_manifest_sha256") == OFFICIAL_C1_MANIFEST_SHA256,
        "rows_exact": len(rows) == 2
        and all(row_fields)
        and set(by_case) == set(EXPECTED_CASES),
        "old_schema_adapter_rows_exact": len(comparisons) == 2
        and all(item["passed"] for item in comparisons),
    }
    return {
        "directory": str(directory.resolve()),
        "fields": fields,
        "row_comparisons": comparisons,
        "passed": all(fields.values()),
    }


def parse_xpu_stats_file(path: Path) -> tuple[int, int] | None:
    try:
        lines = path.read_text().splitlines()
    except (OSError, UnicodeDecodeError):
        return None
    device_values: list[str] = []
    memory_values: list[str] = []
    for line in lines:
        parts = line.split("|")
        if len(parts) < 4:
            continue
        label = parts[1].strip()
        value = parts[2].strip()
        if label == "Device ID":
            device_values.append(value)
        elif label == "GPU Memory Used (MiB)":
            memory_values.append(value)
    if len(device_values) != 1 or len(memory_values) != 1:
        return None
    if re.fullmatch(r"[0-9]+", device_values[0]) is None:
        return None
    memory_match = re.fullmatch(r"([0-9]+)(?:\.([0-9]+))?", memory_values[0])
    if memory_match is None:
        return None
    fraction = memory_match.group(2)
    if fraction is not None and any(character != "0" for character in fraction):
        return None
    return int(device_values[0]), int(memory_match.group(1))


def validate_global_health_evidence(
    wave_dir: Path, global_health: dict[str, Any]
) -> tuple[dict[str, bool], dict[str, Any]]:
    manifest_path = wave_dir / "global-health-evidence.sha256"
    expected: set[str] = {"postwave-group-members-before-reap.txt"}
    for prefix in ("preprobe", "postprobe"):
        expected.update(
            {
                f"{prefix}-group-members.txt",
                f"{prefix}-lane-listeners.txt",
                f"{prefix}-lane-listeners.stderr",
                f"{prefix}-processes.txt",
                f"{prefix}-processes.stderr",
                f"{prefix}-log-error-scan.txt",
                f"{prefix}-log-error-scan.stderr",
                f"{prefix}-kernel-journal.txt",
                f"{prefix}-kernel-journal.stderr",
                f"{prefix}-device-error-scan.txt",
                f"{prefix}-device-error-scan.stderr",
                f"{prefix}-passive-status.env",
            }
        )
    expected.update(
        {f"xpu-smi-final-gpu{gpu}.txt" for gpu in range(4)}
        | {"xpu-final-used.tsv", "global-cleanup-status.env"}
    )
    parsed: dict[str, str] = {}
    lines: list[str] = []
    if manifest_path.is_file():
        lines = manifest_path.read_text().splitlines()
    shape_valid = bool(lines)
    relative_paths: list[str] = []
    for line in lines:
        match = re.fullmatch(r"([0-9a-f]{64})  \./(.+)", line)
        if match is None:
            shape_valid = False
            continue
        digest, relative = match.groups()
        candidate = Path(relative)
        if (
            not relative
            or candidate.is_absolute()
            or ".." in candidate.parts
            or relative in parsed
            or candidate.parent != Path(".")
        ):
            shape_valid = False
            continue
        parsed[relative] = digest
        relative_paths.append(relative)
    files_exact = (
        shape_valid
        and set(parsed) == expected
        and relative_paths == sorted(relative_paths)
    )
    hashes_exact = files_exact
    if hashes_exact:
        for relative, digest in parsed.items():
            path = wave_dir / relative
            if not path.is_file() or path.is_symlink() or sha256_file(path) != digest:
                hashes_exact = False
                break
    empty_names = {"postwave-group-members-before-reap.txt"}
    for prefix in ("preprobe", "postprobe"):
        empty_names.update(
            {
                f"{prefix}-group-members.txt",
                f"{prefix}-lane-listeners.txt",
                f"{prefix}-processes.txt",
                f"{prefix}-log-error-scan.txt",
                f"{prefix}-device-error-scan.txt",
            }
        )
    empties_exact = hashes_exact and all(
        (wave_dir / name).stat().st_size == 0 for name in empty_names
    )
    status_exact = hashes_exact and all(
        (wave_dir / f"{prefix}-passive-status.env").read_text()
        == "passive_fault_detected=0\n"
        for prefix in ("preprobe", "postprobe")
    )
    used_rows: list[tuple[int, int]] = []
    used_lines: list[str] = []
    if hashes_exact:
        used_lines = (wave_dir / "xpu-final-used.tsv").read_text().splitlines()
        for line in used_lines:
            match = re.fullmatch(r"gpu=([0-3])\tused_mib=([0-9]+)", line)
            if match is not None:
                used_rows.append((int(match.group(1)), int(match.group(2))))
    xpu_exact = (
        hashes_exact
        and len(used_lines) == 4
        and len(used_rows) == 4
        and [gpu for gpu, _ in used_rows] == [0, 1, 2, 3]
    )
    xpu_exact = xpu_exact and all(value <= 256 for _, value in used_rows)
    raw_xpu_rows = [
        parse_xpu_stats_file(wave_dir / f"xpu-smi-final-gpu{gpu}.txt")
        for gpu in range(4)
    ]
    xpu_exact = xpu_exact and raw_xpu_rows == used_rows
    fields = {
        "manifest_path_exact": global_health.get("evidence_manifest_path")
        == str(manifest_path.resolve()),
        "manifest_hash_exact": manifest_path.is_file()
        and not manifest_path.is_symlink()
        and global_health.get("evidence_manifest_sha256") == sha256_file(manifest_path),
        "manifest_inventory_exact": files_exact,
        "evidence_hashes_exact": hashes_exact,
        "negative_evidence_empty": empties_exact,
        "passive_status_exact": status_exact,
        "xpu_evidence_exact": xpu_exact,
    }
    return fields, {
        "expected_paths": sorted(expected),
        "used_rows": used_rows,
        "raw_xpu_rows": raw_xpu_rows,
    }


def validate_lane_packet(
    lane: Path,
    expected_gpu: int,
    expected_selector: int,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    lane = lane.resolve()
    marker_path = lane / "diagnostic-completion-status.json"
    attestation_path = lane / "lane-attestation.json"
    oracle_path = lane / "oracle.json"
    marker = load_json(marker_path, "lane completion marker")
    attestation = load_json(attestation_path, "lane attestation")
    oracle = load_json(oracle_path, "lane oracle")
    manifest_ok, manifest_sha = parse_manifest(lane, "artifacts.sha256")
    cleanup_path = lane / "cleanup-status.env"
    cleanup_bytes = cleanup_path.read_bytes()
    server_pid_path = lane / "server.pid"
    server_pid_value = server_pid_path.read_text().strip()
    lifecycle = marker.get("lifecycle")
    lifecycle = lifecycle if isinstance(lifecycle, dict) else {}
    global_health_path_value = lifecycle.get("global_health_path")
    global_health_path = (
        Path(global_health_path_value)
        if isinstance(global_health_path_value, str)
        and os.path.isabs(global_health_path_value)
        else None
    )
    global_health = (
        load_json(global_health_path, "phase-global health")
        if global_health_path is not None and global_health_path.is_file()
        else {}
    )
    global_cleanup_path_value = lifecycle.get("global_cleanup_path")
    global_cleanup_path = (
        Path(global_cleanup_path_value)
        if isinstance(global_cleanup_path_value, str)
        and os.path.isabs(global_cleanup_path_value)
        else None
    )
    global_cleanup_bytes = (
        global_cleanup_path.read_bytes()
        if global_cleanup_path is not None and global_cleanup_path.is_file()
        else b""
    )
    health_evidence_fields, _ = validate_global_health_evidence(
        lane.parent, global_health
    )
    expected_cleanup = (
        "status=PASS\n"
        f"gpu_index={expected_gpu}\n"
        f"selector={expected_selector}\n"
        "graceful_server_teardown=1\n"
        "forced_kill=0\n"
        "cleanup_survivor=0\n"
        "port_closed=1\n"
    ).encode()
    attestation_maps = (
        "fields",
        "oracle_fields",
        "identity_fields",
        "runtime_fields",
        "marker_fields",
        "live_server_fields",
    )
    attestation_inputs = attestation.get("inputs")
    attestation_inputs = (
        attestation_inputs if isinstance(attestation_inputs, dict) else {}
    )
    expected_attestation_inputs = {
        "oracle",
        "server_log",
        "identity_log",
        "prerelease_prefix",
        "postcapture_prefix",
        "runtime_manifest",
        "runtime_reference_report",
        "runtime_final_report",
        "canonical_attester",
        "server_attestation",
        "binding_before",
        "binding_after",
        "matrix_client",
        "study_analyzer",
    }
    input_rows_exact = set(attestation_inputs) == expected_attestation_inputs
    script_dir = Path(__file__).resolve().parent
    expected_input_paths = {
        "oracle": lane / "oracle.json",
        "server_log": lane / "server.stdout.log",
        "identity_log": lane / "server.identity.log",
        "prerelease_prefix": lane / "prerelease-prefix.log",
        "postcapture_prefix": lane / "postcapture-prefix.log",
        "runtime_manifest": script_dir.parent / "runtime-manifest-canonical-q8-c2.json",
        "runtime_reference_report": lane / "runtime-reference.json",
        "runtime_final_report": lane / "runtime-final.json",
        "canonical_attester": script_dir / "attest-canonical-q8-dispatch.py",
        "server_attestation": lane / "server-attestation.json",
        "binding_before": lane / "live-binding-before.json",
        "binding_after": lane / "live-binding-after.json",
        "matrix_client": script_dir / "capture-c2-token-matrix.py",
        "study_analyzer": Path(__file__).resolve(),
    }
    input_paths_exact = input_rows_exact
    if input_rows_exact:
        for name, row in attestation_inputs.items():
            if not isinstance(row, dict):
                input_rows_exact = False
                input_paths_exact = False
                break
            path_value = row.get("path")
            path = Path(path_value) if isinstance(path_value, str) else None
            if (
                path is None
                or not path.is_absolute()
                or not path.is_file()
                or path.is_symlink()
                or row.get("size_bytes") != path.stat().st_size
                or row.get("sha256") != sha256_file(path)
            ):
                input_rows_exact = False
            expected_path = expected_input_paths.get(name)
            if expected_path is None or path is None or path != expected_path.resolve():
                input_paths_exact = False
    fields = {
        "manifest_valid": manifest_ok,
        "marker_schema_phase_exact": type(marker.get("schema_version")) is int
        and marker.get("schema_version") == SCHEMA_VERSION
        and marker.get("phase") == "four-gpu-sequential-c1-oracle-on-c2-topology",
        "marker_literal_paths_exact": marker.get("artifact_manifest")
        == "artifacts.sha256"
        and marker.get("oracle") == "oracle.json"
        and marker.get("attestation") == "lane-attestation.json",
        "marker_status": marker.get("status") == "EVIDENCE_VALID",
        "marker_evidence_valid": marker.get("evidence_valid") is True,
        "marker_diagnostic_only": marker.get("evidence_class") == "diagnostic-only"
        and marker.get("performance_promotable") is False,
        "gpu_exact": type(marker.get("gpu_index")) is int
        and marker.get("gpu_index") == expected_gpu
        and type(attestation.get("gpu_index")) is int
        and attestation.get("gpu_index") == expected_gpu,
        "selector_exact": type(marker.get("selector")) is int
        and marker.get("selector") == expected_selector
        and type(attestation.get("selector")) is int
        and attestation.get("selector") == expected_selector,
        "server_pid_exact": PID_RE.fullmatch(server_pid_value) is not None
        and marker.get("server_pid") == server_pid_value
        and attestation.get("server_pid") == server_pid_value,
        "manifest_hash_bound": marker.get("artifact_manifest_sha256") == manifest_sha,
        "attestation_hash_bound": marker.get("attestation_sha256")
        == sha256_file(attestation_path),
        "oracle_hash_bound": marker.get("oracle_sha256") == sha256_file(oracle_path),
        "attestation_passed": attestation.get("passed") is True,
        "attestation_schema_phase_exact": type(attestation.get("schema_version")) is int
        and attestation.get("schema_version") == SCHEMA_VERSION
        and attestation.get("status") == "PASS"
        and attestation.get("phase") == "sequential-c1-oracle-on-c2-topology"
        and attestation.get("evidence_class") == "diagnostic-only"
        and attestation.get("performance_promotable") is False,
        "attestation_subfields_all_true": all(
            isinstance(attestation.get(name), dict)
            and bool(attestation[name])
            and all(value is True for value in attestation[name].values())
            for name in attestation_maps
        ),
        "attestation_inputs_exact": input_rows_exact,
        "attestation_input_paths_exact": input_paths_exact,
        "cleanup_hash_and_content_exact": cleanup_bytes == expected_cleanup
        and marker.get("cleanup_status_sha256") == sha256_bytes(cleanup_bytes),
        "lifecycle_exact": lifecycle.get("graceful_server_teardown") is True
        and lifecycle.get("forced_kill") is False
        and lifecycle.get("cleanup_survivor") is False
        and lifecycle.get("port_closed") is True
        and lifecycle.get("global_passive_health_passed") is True,
        "global_health_exact": bool(global_health)
        and global_health_path is not None
        and global_health_path
        == Path(os.path.abspath(lane.parent / "global-health.json"))
        and not global_health_path.is_symlink()
        and lifecycle.get("global_health_sha256") == sha256_file(global_health_path)  # type: ignore[arg-type]
        and type(global_health.get("schema_version")) is int
        and global_health.get("schema_version") == SCHEMA_VERSION
        and global_health.get("phase") == "four-gpu-sequential-c1-oracle-on-c2-topology"
        and global_health.get("passed") is True
        and global_health.get("all_groups_stopped") is True
        and global_health.get("all_listeners_closed") is True
        and global_health.get("passive_fault_detected") is False
        and global_health.get("final_xpu_probes_performed") is True
        and global_health.get("all_cards_idle") is True
        and global_health.get("forced_kill") is False
        and global_health.get("cleanup_survivor") is False,
        "global_health_evidence_exact": all(health_evidence_fields.values()),
        "global_cleanup_exact": global_cleanup_path is not None
        and global_cleanup_path
        == Path(os.path.abspath(lane.parent / "global-cleanup-status.env"))
        and not global_cleanup_path.is_symlink()
        and global_cleanup_bytes
        == (
            "status=PASS\n"
            "all_groups_stopped=1\n"
            "all_listeners_closed=1\n"
            "passive_fault_detected=0\n"
            "final_xpu_probes_performed=1\n"
            "all_cards_idle=1\n"
            "forced_kill=0\n"
            "cleanup_survivor=0\n"
        ).encode()
        and lifecycle.get("global_cleanup_sha256")
        == sha256_bytes(global_cleanup_bytes),
    }
    if not all(fields.values()):
        failed = [name for name, passed in fields.items() if not passed]
        raise ValueError(f"lane {expected_gpu} packet failed: {failed}")
    return marker, attestation, oracle


def compare_oracle_rows(
    left: dict[str, dict[str, Any]], right: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for case_id in EXPECTED_CASES:
        left_row = left.get(case_id, {})
        right_row = right.get(case_id, {})
        tokens_exact = left_row.get("token_ids") == right_row.get("token_ids")
        content_exact = left_row.get("content_sha256") == right_row.get(
            "content_sha256"
        )
        semantic_content_exact = left_row.get("_semantic_content") == right_row.get(
            "_semantic_content"
        ) and left_row.get("_semantic_content_sha256") == right_row.get(
            "_semantic_content_sha256"
        )
        semantic_tokens_exact = left_row.get("_semantic_token_ids") == right_row.get(
            "_semantic_token_ids"
        ) and left_row.get("_semantic_token_ids_sha256") == right_row.get(
            "_semantic_token_ids_sha256"
        )
        canary_exact = (
            left_row.get("_canary_token_ids") == right_row.get("_canary_token_ids")
            and left_row.get("_canary_token_ids_sha256")
            == right_row.get("_canary_token_ids_sha256")
            and left_row.get("_canary_content_sha256")
            == right_row.get("_canary_content_sha256")
        )
        external_canary_exact = (
            left_row.get("_external_token_ids") == right_row.get("_external_token_ids")
            and left_row.get("_external_token_ids_sha256")
            == right_row.get("_external_token_ids_sha256")
            and left_row.get("_external_content") == right_row.get("_external_content")
            and left_row.get("_external_content_sha256")
            == right_row.get("_external_content_sha256")
        )
        prompt_exact = left_row.get("prompt_sha256") == right_row.get("prompt_sha256")
        rendered_exact = left_row.get("rendered_prompt_sha256") == right_row.get(
            "rendered_prompt_sha256"
        )
        rows.append(
            {
                "case_id": case_id,
                "token_ids_exact": tokens_exact,
                "content_exact": content_exact,
                "semantic_content_exact": semantic_content_exact,
                "semantic_tokens_exact": semantic_tokens_exact,
                "canary_exact": canary_exact,
                "external_canary_exact": external_canary_exact,
                "prompt_exact": prompt_exact,
                "rendered_prompt_exact": rendered_exact,
                "passed": tokens_exact
                and content_exact
                and semantic_content_exact
                and semantic_tokens_exact
                and canary_exact
                and external_canary_exact
                and prompt_exact
                and rendered_exact,
            }
        )
    return {"rows": rows, "passed": all(row["passed"] for row in rows)}


def aggregate(args: argparse.Namespace) -> int:
    if len(args.lane) != 4:
        raise ValueError("exactly four --lane paths are required")
    if (args.model_sha256, args.runtime_sha256, args.suite_sha256) != (
        MODEL_SHA256,
        RUNTIME_SHA256,
        SUITE_SHA256,
    ):
        raise ValueError("aggregate identity differs from the canonical control")
    if (
        args.old_baseline_oracle_sha256 != OLD_BASELINE_ORACLE_SHA256
        or sha256_file(args.old_baseline_oracle) != OLD_BASELINE_ORACLE_SHA256
    ):
        raise ValueError("old baseline oracle hash mismatch")
    old = load_json(args.old_baseline_oracle, "old baseline oracle")
    old_fields, old_rows = validate_oracle(
        old, args.model_sha256, args.runtime_sha256, args.suite_sha256
    )
    if not all(old_fields.values()):
        raise ValueError("old baseline oracle identity is invalid")
    official_c1 = validate_official_c1_packet(
        args.official_c1_dir,
        args.official_c1_result_sha256,
        args.official_c1_manifest_sha256,
        args.official_c1_marker_sha256,
        old_rows,
    )
    if not official_c1["passed"]:
        raise ValueError("official c1 PASS packet does not bind the schema adapter")
    lanes: list[dict[str, Any]] = []
    lane_rows: dict[int, dict[str, dict[str, Any]]] = {}
    lane_oracles: dict[int, dict[str, Any]] = {}
    for mapping, lane_path in zip(C1_MAPPING, args.lane):
        marker, attestation, oracle = validate_lane_packet(
            lane_path, mapping["gpu_index"], mapping["selector"]
        )
        fields, rows = validate_oracle(
            oracle, args.model_sha256, args.runtime_sha256, args.suite_sha256
        )
        if not all(fields.values()):
            raise ValueError(f"lane {mapping['gpu_index']} oracle identity failed")
        baseline_comparison = compare_oracle_rows(rows, old_rows)
        if not baseline_comparison["passed"]:
            raise ValueError(f"lane {mapping['gpu_index']} differs from old baseline")
        lane_rows[mapping["gpu_index"]] = rows
        lane_oracles[mapping["gpu_index"]] = oracle
        lanes.append(
            {
                **mapping,
                "run_dir": str(lane_path.resolve()),
                "completion_marker_sha256": sha256_file(
                    lane_path / "diagnostic-completion-status.json"
                ),
                "artifact_manifest_sha256": marker["artifact_manifest_sha256"],
                "oracle_sha256": marker["oracle_sha256"],
                "attestation_sha256": marker["attestation_sha256"],
                "oracle_fields": fields,
                "old_baseline_comparison": baseline_comparison,
                "route_observation": attestation.get("observed", {}).get("markers"),
            }
        )
    comparisons = {
        "off_cross_card": compare_oracle_rows(lane_rows[0], lane_rows[1]),
        "on_cross_card": compare_oracle_rows(lane_rows[2], lane_rows[3]),
        "off_on_cross_selector": compare_oracle_rows(lane_rows[0], lane_rows[2]),
        "all_lanes_old_baseline": {
            "passed": all(lane["old_baseline_comparison"]["passed"] for lane in lanes)
        },
    }
    passed = all(item["passed"] for item in comparisons.values())
    if not passed:
        raise ValueError("four-lane c1 oracle consensus failed")
    # Preserve the capture-generated sequential-oracle schema byte-for-byte in
    # the handoff files.  The aggregate binds both same-selector replicates.
    if args.selector0_oracle.exists() or args.selector1_oracle.exists():
        raise ValueError("selector oracle output already exists")
    copy_file_new(args.lane[0] / "oracle.json", args.selector0_oracle)
    copy_file_new(args.lane[2] / "oracle.json", args.selector1_oracle)
    selector_oracles = {
        "0": {
            "path": str(args.selector0_oracle.resolve()),
            "sha256": sha256_file(args.selector0_oracle),
            "source_gpus": [0, 1],
            "source_oracle_sha256": [
                lanes[0]["oracle_sha256"],
                lanes[1]["oracle_sha256"],
            ],
            "cross_card_correctness_rows_exact": True,
            "server_benchmark_identity": EXPECTED_SERVER_BENCHMARK_IDENTITY,
        },
        "1": {
            "path": str(args.selector1_oracle.resolve()),
            "sha256": sha256_file(args.selector1_oracle),
            "source_gpus": [2, 3],
            "source_oracle_sha256": [
                lanes[2]["oracle_sha256"],
                lanes[3]["oracle_sha256"],
            ],
            "cross_card_correctness_rows_exact": True,
            "server_benchmark_identity": EXPECTED_SERVER_BENCHMARK_IDENTITY,
        },
    }
    result = {
        "schema_version": SCHEMA_VERSION,
        "status": "PASS",
        "passed": True,
        "evidence_class": "diagnostic-only",
        "performance_promotable": False,
        "phase": "four-gpu-sequential-c1-oracle-on-c2-topology",
        "mapping": list(C1_MAPPING),
        "topology": {
            "ctx_size_total": 65536,
            "parallel_slots": 2,
            "ctx_size_per_slot": 32768,
            "kv_unified": False,
            "request_mode": "sequential-oracle",
            "case_order": "A-slot0-then-B-slot1",
            "forced_tokens": 512,
        },
        "model_sha256": args.model_sha256,
        "runtime_sha256": args.runtime_sha256,
        "suite_sha256": args.suite_sha256,
        "runtime_bundle": {
            "runtime_manifest_sha256": CANDIDATE_MANIFEST_SHA256,
            "canonical_sycl_dso_sha256": CANDIDATE_SYCL_DSO_SHA256,
            "canonical_attester_sha256": CANONICAL_ATTESTER_SHA256,
            "study_analyzer_sha256": sha256_file(Path(__file__).resolve()),
        },
        "old_baseline_oracle": {
            "path": str(args.old_baseline_oracle.resolve()),
            "sha256": args.old_baseline_oracle_sha256,
            "provenance_role": "fixed-hash sequential-c2 schema adapter",
        },
        "official_c1_pass_packet": official_c1,
        "lanes": lanes,
        "comparisons": comparisons,
        "selector_oracles": selector_oracles,
        "phase2_handoff_contract": {
            "server_benchmark_identity_exact_match_required": True,
            "sleep_idle_server_argument_forbidden": True,
            "selector_matched_oracle_required": True,
            "fresh_phase1_cohort_required": True,
        },
        "interpretation_guard": {
            "performance_claim": False,
            "c2_correctness_claim": False,
            "request_time_dispatch_claim": False,
            "process_total_counter_claim": False,
            "summary_presence_required": False,
            "summary_totals_used": False,
            "selector_on_route_claim": "one exact flat first-hit before release",
            "selector_off_route_claim": "zero canonical route markers",
            "next_gate": "two-wave heterogeneous c2 same-card selector crossover",
        },
    }
    write_json_new(args.out, result)
    return 0


def print_plan(args: argparse.Namespace) -> int:
    if args.port_base < 1024 or args.port_base > 65532:
        raise ValueError("port base must leave four valid ports")
    for row in C1_MAPPING:
        print(
            f"gpu={row['gpu_index']}\tselector={row['selector']}\t"
            f"port={args.port_base + row['gpu_index']}\t"
            "topology=c65536-np2-no-kv-unified\tmode=sequential-oracle\t"
            "server_sleep=disabled"
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    plan = subparsers.add_parser("print-plan")
    plan.add_argument("--port-base", type=int, default=19620)
    plan.set_defaults(function=print_plan)

    binding = subparsers.add_parser("capture-live-binding")
    binding.add_argument("--matrix-client", type=Path, required=True)
    binding.add_argument("--matrix-client-sha256", required=True)
    binding.add_argument("--server-pid", required=True)
    binding.add_argument("--port", type=int, required=True)
    binding.add_argument("--runtime-sha256", required=True)
    binding.add_argument("--out", type=Path, required=True)
    binding.set_defaults(function=capture_live_binding)

    lane = subparsers.add_parser("attest-lane")
    lane.add_argument("--oracle", type=Path, required=True)
    lane.add_argument("--server-log", type=Path, required=True)
    lane.add_argument("--identity-log", type=Path, required=True)
    lane.add_argument("--prerelease-prefix", type=Path, required=True)
    lane.add_argument("--postcapture-prefix", type=Path, required=True)
    lane.add_argument("--runtime-manifest", type=Path, required=True)
    lane.add_argument("--runtime-manifest-sha256", required=True)
    lane.add_argument("--runtime-reference-report", type=Path, required=True)
    lane.add_argument("--runtime-reference-report-sha256", required=True)
    lane.add_argument("--runtime-final-report", type=Path, required=True)
    lane.add_argument("--runtime-final-report-sha256", required=True)
    lane.add_argument("--canonical-attester", type=Path, required=True)
    lane.add_argument("--canonical-attester-sha256", required=True)
    lane.add_argument("--server-attestation", type=Path, required=True)
    lane.add_argument("--server-attestation-sha256", required=True)
    lane.add_argument("--binding-before", type=Path, required=True)
    lane.add_argument("--binding-after", type=Path, required=True)
    lane.add_argument("--matrix-client", type=Path, required=True)
    lane.add_argument("--matrix-client-sha256", required=True)
    lane.add_argument("--model-sha256", required=True)
    lane.add_argument("--runtime-sha256", required=True)
    lane.add_argument("--suite-sha256", required=True)
    lane.add_argument("--gpu-index", type=int, required=True)
    lane.add_argument("--selector", type=int, required=True)
    lane.add_argument("--server-pid", required=True)
    lane.add_argument("--port", type=int, required=True)
    lane.add_argument("--out", type=Path, required=True)
    lane.set_defaults(function=attest_lane)

    aggregate_parser = subparsers.add_parser("aggregate")
    aggregate_parser.add_argument("--lane", action="append", type=Path, required=True)
    aggregate_parser.add_argument("--old-baseline-oracle", type=Path, required=True)
    aggregate_parser.add_argument("--old-baseline-oracle-sha256", required=True)
    aggregate_parser.add_argument("--official-c1-dir", type=Path, required=True)
    aggregate_parser.add_argument("--official-c1-result-sha256", required=True)
    aggregate_parser.add_argument("--official-c1-manifest-sha256", required=True)
    aggregate_parser.add_argument("--official-c1-marker-sha256", required=True)
    aggregate_parser.add_argument("--model-sha256", required=True)
    aggregate_parser.add_argument("--runtime-sha256", required=True)
    aggregate_parser.add_argument("--suite-sha256", required=True)
    aggregate_parser.add_argument("--selector0-oracle", type=Path, required=True)
    aggregate_parser.add_argument("--selector1-oracle", type=Path, required=True)
    aggregate_parser.add_argument("--out", type=Path, required=True)
    aggregate_parser.set_defaults(function=aggregate)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    for name in (
        "model_sha256",
        "runtime_sha256",
        "suite_sha256",
        "runtime_manifest_sha256",
        "runtime_reference_report_sha256",
        "runtime_final_report_sha256",
        "canonical_attester_sha256",
        "server_attestation_sha256",
        "matrix_client_sha256",
        "old_baseline_oracle_sha256",
        "official_c1_result_sha256",
        "official_c1_manifest_sha256",
        "official_c1_marker_sha256",
    ):
        value = getattr(args, name, None)
        if value is not None and SHA_RE.fullmatch(value) is None:
            parser.error(f"--{name.replace('_', '-')} must be a lowercase SHA-256")
    return args.function(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
