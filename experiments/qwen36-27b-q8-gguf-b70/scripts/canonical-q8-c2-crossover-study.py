#!/usr/bin/env python3
"""Capture and validate the canonical-Q8 two-wave c2 crossover.

The live shell runner owns processes, leases, and cleanup.  This module owns
the scientific contract: a full forced-512 heterogeneous pair, exact binding
to a fresh selector-matched Phase-1 oracle, first-hit timing evidence, and a
balanced two-wave outcome.  Timing values are retained only to prove request
synchronization and decode overlap; this study makes no performance claim.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import re
import shlex
import sys
import time
from pathlib import Path
from types import ModuleType
from typing import Any
from urllib.parse import urlparse


SCHEMA_VERSION = 1
CONTROL = "GGML_SYCL_Q8_0_C2_CANONICAL_MMVQ"
MARKER = "SYCL_Q8_0_C2_CANONICAL_MMVQ"
PROCESS_BINDING = "QWEN36_SERVER_PROCESS_BINDING"
MODEL_SHA256 = "f93f517f38e696d35a1a7df2c0e3155a64f4c4dcd662107a146ae263f7fb14ce"
RUNTIME_SHA256 = "1a093f09122ceb2851157042c2bbc6281ddb9d4e2de50137502890f9b52fa7d7"
MANIFEST_SHA256 = "1b6c305b7e3fad027e7397168bda23526b72b8a4b59e8c6b2b3788fc7347b4d9"
SYCL_DSO_SHA256 = "f0a9e736dde321f72fceb14db6fb1410a9ad090380a3cf8ed7c591e949c94305"
SUITE_SHA256 = "053523440e4a23d7f772dec5025fe4831ba33c0a8eaba76795e4ee76718860af"
EXPECTED_CASES = ("q27-q8-lc-04k-middle", "q27-q8-c2-04k-b")
EXPECTED_PROMPT_TOKENS = {
    "q27-q8-lc-04k-middle": 4369,
    "q27-q8-c2-04k-b": 4317,
}
TOKEN_COUNT = 512
REQUEST_SKEW_LIMIT_S = 0.025
OCCUPANCY_MINIMUM = 1.5
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
PROCESS_RE = re.compile(r"^QWEN36_SERVER_PROCESS_BINDING pid=([1-9][0-9]*)$")
DIMENSION_PATTERN = r"(-?[0-9]+),(-?[0-9]+),(-?[0-9]+),(-?[0-9]+)"
FIRST_HIT_RE = re.compile(
    rf"^{MARKER} first-hit: layout=(flat|recurrent) "
    rf"path=reordered_single_col_mmvq reorder_ready=1 calls_per_dispatch=2 "
    rf"src0=(\S+) src0_ne=\[{DIMENSION_PATTERN}\] "
    rf"src1_ne=\[{DIMENSION_PATTERN}\] dst_ne=\[{DIMENSION_PATTERN}\]$"
)
SUMMARY_RE = re.compile(
    rf"^{MARKER} summary: flat_dispatches=([0-9]+) "
    r"recurrent_dispatches=([0-9]+) flat_multicol_suppressed=([0-9]+) "
    r"recurrent_dmmv_suppressed=([0-9]+) reorder_ready_dispatches=([0-9]+) "
    r"single_col_mmvq_calls=([0-9]+) violations=([0-9]+)$"
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
PASSIVE_LOG_ERROR_RE = re.compile(
    r"UR_RESULT_ERROR_DEVICE_LOST|ZE_RESULT_ERROR_DEVICE_LOST|out of memory|"
    r"segmentation fault|core dumped|Aborted|Timedout job",
    re.IGNORECASE,
)
PASSIVE_DEVICE_ERROR_RE = re.compile(
    r"xe.*(reset|wedg|fault|hang|timedout|device lost)|GuC.*reset|"
    r"Fault response|VM.*fault|PCIe.*AER|UR_RESULT_ERROR_DEVICE_LOST|"
    r"ZE_RESULT_ERROR_DEVICE_LOST",
    re.IGNORECASE,
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
SERVER_IDENTITY = {
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
    "llama_server_sha256": RUNTIME_SHA256,
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
PLAN = (
    {"wave": 1, "gpu_index": 0, "scenario": "forward", "selector": 0},
    {"wave": 1, "gpu_index": 1, "scenario": "forward", "selector": 1},
    {"wave": 1, "gpu_index": 2, "scenario": "reverse", "selector": 0},
    {"wave": 1, "gpu_index": 3, "scenario": "reverse", "selector": 1},
    {"wave": 2, "gpu_index": 0, "scenario": "forward", "selector": 1},
    {"wave": 2, "gpu_index": 1, "scenario": "forward", "selector": 0},
    {"wave": 2, "gpu_index": 2, "scenario": "reverse", "selector": 1},
    {"wave": 2, "gpu_index": 3, "scenario": "reverse", "selector": 0},
)
PAYLOAD_FIELDS = {
    "n_predict": TOKEN_COUNT,
    "temperature": 0,
    "top_p": 1,
    "seed": 1,
    "cache_prompt": False,
    "return_tokens": True,
    "ignore_eos": True,
}
FORBIDDEN_PAYLOAD_FIELDS = {"backend_sampling", "min_p", "top_k", "typical_p"}
_FAILURE_OUTPUT: Path | None = None


def is_json_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def json_exact(value: Any, expected: Any) -> bool:
    if is_json_integer(expected):
        return is_json_integer(value) and value == expected
    return type(value) is type(expected) and value == expected


def is_finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def is_sha256(value: Any) -> bool:
    return isinstance(value, str) and SHA_RE.fullmatch(value) is not None


def is_token_list(value: Any, length: int | None = None) -> bool:
    return (
        isinstance(value, list)
        and (length is None or len(value) == length)
        and all(is_json_integer(token) and token >= 0 for token in value)
    )


def argv_option_absent(argv: Any, option: str) -> bool:
    return isinstance(argv, list) and all(
        isinstance(value, str)
        and value != option
        and not value.startswith(f"{option}=")
        for value in argv
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def token_sha256(tokens: list[int]) -> str:
    return sha256_bytes(json.dumps(tokens, separators=(",", ":")).encode())


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
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            stream.write((json.dumps(value, indent=2, sort_keys=True) + "\n").encode())
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


def load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def snapshot_inputs(paths: dict[str, Path]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for label, path in paths.items():
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"input {label} is not a regular non-symlink file: {path}")
        result[label] = {
            "path": str(path.resolve()),
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    return result


def normalize_runtime_line(line: str) -> str:
    match = re.match(r"^[0-9]+\.[0-9]{2}\.[0-9]{3}\.[0-9]{3} [IWE] (.*)$", line)
    return match.group(1) if match else line


def parse_manifest(
    directory: Path, name: str, excluded_marker: str
) -> tuple[bool, str]:
    directory = directory.resolve()
    manifest = directory / name
    if not manifest.is_file() or manifest.is_symlink():
        return False, ""
    lines = manifest.read_text().splitlines()
    parsed: dict[str, str] = {}
    ordered: list[str] = []
    for line in lines:
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if match is None:
            return False, ""
        digest, relative = match.groups()
        relative = relative[2:] if relative.startswith("./") else relative
        candidate = Path(relative)
        if (
            not relative
            or candidate.is_absolute()
            or ".." in candidate.parts
            or relative in parsed
        ):
            return False, ""
        path = directory / candidate
        try:
            resolved = path.resolve(strict=True)
        except OSError:
            return False, ""
        if (
            not path.is_file()
            or path.is_symlink()
            or directory not in resolved.parents
            or sha256_file(path) != digest
        ):
            return False, ""
        parsed[relative] = digest
        ordered.append(relative)
    if not parsed or ordered != sorted(ordered):
        return False, ""
    if any(path.is_symlink() for path in directory.rglob("*")):
        return False, ""
    excluded = {name, excluded_marker}
    actual = {
        str(path.relative_to(directory))
        for path in directory.rglob("*")
        if path.is_file()
        and not path.is_symlink()
        and str(path.relative_to(directory)) not in excluded
        and not str(path.relative_to(directory)).startswith(f".{name}.")
    }
    return set(parsed) == actual, sha256_file(manifest)


def expected_plan_row(wave: int, gpu_index: int) -> dict[str, Any]:
    matches = [
        row for row in PLAN if row["wave"] == wave and row["gpu_index"] == gpu_index
    ]
    if len(matches) != 1:
        raise ValueError("wave/GPU pair is outside the frozen crossover plan")
    return dict(matches[0])


def extract_phase1_flat_marker(
    summary: dict[str, Any],
) -> tuple[dict[str, bool], str | None]:
    lanes = summary.get("lanes")
    lanes = lanes if isinstance(lanes, list) else []
    observed: list[str] = []
    per_lane_exact = True
    for lane in lanes:
        if not isinstance(lane, dict) or not json_exact(lane.get("selector"), 1):
            continue
        route = lane.get("route_observation")
        route = route if isinstance(route, dict) else {}
        markers = route.get("prerelease_canonical_marker_lines")
        if (
            not isinstance(markers, list)
            or len(markers) != 1
            or not isinstance(markers[0], str)
            or FIRST_HIT_RE.fullmatch(markers[0]) is None
            or "layout=flat " not in markers[0]
        ):
            per_lane_exact = False
        else:
            observed.append(markers[0])
    fields = {
        "two_selector_on_phase1_lanes": len(observed) == 2,
        "phase1_flat_marker_well_formed": per_lane_exact,
        "phase1_flat_marker_cross_card_exact": len(set(observed)) == 1,
    }
    return fields, observed[0] if all(fields.values()) else None


def validate_phase1_lanes(
    directory: Path, summary: dict[str, Any]
) -> tuple[bool, list[dict[str, Any]]]:
    lanes = summary.get("lanes")
    lanes = lanes if isinstance(lanes, list) else []
    expected = (
        {"gpu_index": 0, "selector": 0},
        {"gpu_index": 1, "selector": 0},
        {"gpu_index": 2, "selector": 1},
        {"gpu_index": 3, "selector": 1},
    )
    results: list[dict[str, Any]] = []
    for mapping, lane in zip(expected, lanes):
        lane = lane if isinstance(lane, dict) else {}
        run_dir_value = lane.get("run_dir")
        run_dir = Path(run_dir_value) if isinstance(run_dir_value, str) else None
        path_bound = (
            run_dir is not None
            and run_dir.is_absolute()
            and run_dir.is_dir()
            and not run_dir.is_symlink()
            and directory in run_dir.resolve().parents
        )
        marker: dict[str, Any] = {}
        attestation: dict[str, Any] = {}
        marker_path = (
            run_dir / "diagnostic-completion-status.json" if path_bound else None
        )
        attestation_path = run_dir / "lane-attestation.json" if path_bound else None
        if (
            marker_path is not None
            and attestation_path is not None
            and marker_path.is_file()
            and attestation_path.is_file()
            and not marker_path.is_symlink()
            and not attestation_path.is_symlink()
        ):
            marker = load_json(marker_path, "Phase-1 lane marker")
            attestation = load_json(attestation_path, "Phase-1 lane attestation")
        identity_fields = attestation.get("identity_fields")
        live_fields = attestation.get("live_server_fields")
        attestation_groups = attestation.get("fields")
        identity_fields = identity_fields if isinstance(identity_fields, dict) else {}
        live_fields = live_fields if isinstance(live_fields, dict) else {}
        attestation_groups = (
            attestation_groups if isinstance(attestation_groups, dict) else {}
        )
        fields = {
            "summary_mapping_exact": all(
                json_exact(lane.get(key), value) for key, value in mapping.items()
            ),
            "run_dir_bound": path_bound,
            "summary_marker_hash_exact": marker_path is not None
            and marker_path.is_file()
            and lane.get("completion_marker_sha256") == sha256_file(marker_path),
            "summary_attestation_hash_exact": attestation_path is not None
            and attestation_path.is_file()
            and lane.get("attestation_sha256") == sha256_file(attestation_path),
            "marker_passed": marker.get("status") == "EVIDENCE_VALID"
            and marker.get("evidence_valid") is True
            and marker.get("performance_promotable") is False
            and all(
                json_exact(marker.get(key), value) for key, value in mapping.items()
            ),
            "attestation_passed": attestation.get("passed") is True
            and attestation.get("status") == "PASS"
            and all(
                json_exact(attestation.get(key), value)
                for key, value in mapping.items()
            )
            and bool(attestation_groups)
            and all(value is True for value in attestation_groups.values()),
            "no_sleep_identity": identity_fields.get(
                "identity_sleep_idle_seconds_exactly_once"
            )
            is True,
            "no_sleep_live_argv": live_fields.get("sleep_idle_argv_absent") is True,
        }
        results.append(
            {
                **mapping,
                "run_dir": str(run_dir) if run_dir is not None else None,
                "fields": fields,
                "passed": all(fields.values()),
            }
        )
    return len(lanes) == 4 and len(results) == 4 and all(
        row["passed"] for row in results
    ), results


def validate_phase1_packet(
    directory: Path,
    manifest_sha256: str,
    summary_sha256: str,
    marker_sha256: str,
    selector: int,
    oracle_path: Path,
    oracle_sha256: str,
) -> tuple[dict[str, bool], dict[str, Any], dict[str, Any]]:
    directory = directory.resolve()
    manifest_path = directory / "wave-artifacts.sha256"
    summary_path = directory / "phase-summary.json"
    marker_path = directory / "wave-diagnostic-completion-status.json"
    for path in (manifest_path, summary_path, marker_path, oracle_path):
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"Phase-1 handoff input is not a regular file: {path}")
    manifest_valid, observed_manifest_sha = parse_manifest(
        directory, "wave-artifacts.sha256", "wave-diagnostic-completion-status.json"
    )
    summary = load_json(summary_path, "Phase-1 summary")
    marker = load_json(marker_path, "Phase-1 completion marker")
    selector_oracles = summary.get("selector_oracles")
    selector_oracles = selector_oracles if isinstance(selector_oracles, dict) else {}
    selected = selector_oracles.get(str(selector))
    selected = selected if isinstance(selected, dict) else {}
    comparisons = summary.get("comparisons")
    comparisons = comparisons if isinstance(comparisons, dict) else {}
    handoff = summary.get("phase2_handoff_contract")
    handoff = handoff if isinstance(handoff, dict) else {}
    runtime = summary.get("runtime_bundle")
    runtime = runtime if isinstance(runtime, dict) else {}
    marker_fields, phase1_flat_marker = extract_phase1_flat_marker(summary)
    phase1_lanes_valid, phase1_lane_observed = validate_phase1_lanes(directory, summary)
    selected_path_value = selected.get("path")
    selected_path = (
        Path(selected_path_value) if isinstance(selected_path_value, str) else None
    )
    fields = {
        "expected_hashes_well_formed": all(
            is_sha256(value)
            for value in (manifest_sha256, summary_sha256, marker_sha256, oracle_sha256)
        ),
        "manifest_valid": manifest_valid,
        "manifest_hash_exact": observed_manifest_sha == manifest_sha256,
        "summary_hash_exact": sha256_file(summary_path) == summary_sha256,
        "marker_hash_exact": sha256_file(marker_path) == marker_sha256,
        "marker_evidence_valid": marker.get("status") == "EVIDENCE_VALID"
        and marker.get("phase") == "four-gpu-sequential-c1-oracle-on-c2-topology"
        and marker.get("evidence_valid") is True
        and marker.get("evidence_class") == "diagnostic-only"
        and marker.get("performance_promotable") is False
        and marker.get("summary_sha256") == summary_sha256
        and marker.get("artifact_manifest_sha256") == manifest_sha256,
        "summary_passed": summary.get("status") == "PASS"
        and summary.get("passed") is True
        and summary.get("phase") == "four-gpu-sequential-c1-oracle-on-c2-topology"
        and summary.get("evidence_class") == "diagnostic-only"
        and summary.get("performance_promotable") is False,
        "identity_exact": summary.get("model_sha256") == MODEL_SHA256
        and summary.get("runtime_sha256") == RUNTIME_SHA256
        and summary.get("suite_sha256") == SUITE_SHA256
        and runtime.get("runtime_manifest_sha256") == MANIFEST_SHA256
        and runtime.get("canonical_sycl_dso_sha256") == SYCL_DSO_SHA256,
        "mapping_exact": isinstance(summary.get("mapping"), list)
        and len(summary["mapping"]) == 4
        and all(
            isinstance(observed_row, dict)
            and set(observed_row) == set(expected_row)
            and all(
                json_exact(observed_row.get(key), value)
                for key, value in expected_row.items()
            )
            for observed_row, expected_row in zip(
                summary["mapping"],
                (
                    {"gpu_index": 0, "selector": 0},
                    {"gpu_index": 1, "selector": 0},
                    {"gpu_index": 2, "selector": 1},
                    {"gpu_index": 3, "selector": 1},
                ),
            )
        ),
        "phase1_lane_packets_exact": phase1_lanes_valid,
        "consensus_exact": all(
            isinstance(value, dict) and value.get("passed") is True
            for value in comparisons.values()
        )
        and set(comparisons)
        == {
            "off_cross_card",
            "on_cross_card",
            "off_on_cross_selector",
            "all_lanes_old_baseline",
        },
        "no_sleep_handoff_exact": handoff.get(
            "server_benchmark_identity_exact_match_required"
        )
        is True
        and handoff.get("sleep_idle_server_argument_forbidden") is True
        and handoff.get("selector_matched_oracle_required") is True
        and handoff.get("fresh_phase1_cohort_required") is True,
        "selected_oracle_path_exact": selected_path is not None
        and selected_path.resolve() == oracle_path.resolve()
        and directory in oracle_path.resolve().parents,
        "selected_oracle_hash_exact": selected.get("sha256") == oracle_sha256
        and sha256_file(oracle_path) == oracle_sha256,
        "selected_oracle_selector_exact": set(selector_oracles) == {"0", "1"},
        **marker_fields,
    }
    observed = {
        "directory": str(directory),
        "manifest_sha256": observed_manifest_sha,
        "summary_sha256": sha256_file(summary_path),
        "marker_sha256": sha256_file(marker_path),
        "selected_oracle": selected,
        "phase1_flat_marker": phase1_flat_marker,
        "phase1_lanes": phase1_lane_observed,
    }
    return fields, observed, summary


def load_short_cases(suite: dict[str, Any], scenario: str) -> list[dict[str, Any]]:
    pairs = suite.get("pairs") if isinstance(suite, dict) else None
    matches = (
        [
            pair
            for pair in pairs
            if isinstance(pair, dict) and pair.get("band") == "short"
        ]
        if isinstance(pairs, list)
        else []
    )
    cases = matches[0].get("cases") if len(matches) == 1 else None
    if (
        not isinstance(cases, list)
        or len(cases) != 2
        or any(not isinstance(case, dict) for case in cases)
    ):
        raise ValueError("suite must contain exactly one two-case short pair")
    if [case.get("id") for case in cases] != list(EXPECTED_CASES):
        raise ValueError("short-pair case order differs from the frozen A/B identity")
    if scenario == "reverse":
        cases = list(reversed(cases))
    return [dict(case) for case in cases]


def validate_oracle(
    oracle: dict[str, Any], suite_sha256: str, oracle_sha256: str, selector: int
) -> tuple[dict[str, bool], dict[str, dict[str, Any]]]:
    identity = oracle.get("run_identity")
    identity = identity if isinstance(identity, dict) else {}
    rows = oracle.get("rows")
    rows = rows if isinstance(rows, list) else []
    by_case: dict[str, dict[str, Any]] = {}
    row_validity: list[bool] = []
    for row in rows:
        valid = isinstance(row, dict)
        if not valid:
            row_validity.append(False)
            continue
        tokens = row.get("token_ids")
        valid = (
            row.get("case_id") in EXPECTED_CASES
            and is_json_integer(row.get("slot_id"))
            and row.get("slot_id") in (0, 1)
            and is_token_list(tokens, TOKEN_COUNT)
            and json_exact(row.get("token_count"), TOKEN_COUNT)
            and row.get("token_ids_sha256") == token_sha256(tokens)
            and json_exact(
                row.get("calibrated_prompt_tokens"),
                EXPECTED_PROMPT_TOKENS.get(row.get("case_id")),
            )
            and is_sha256(row.get("prompt_sha256"))
            and is_sha256(row.get("rendered_prompt_sha256"))
            and is_sha256(row.get("content_sha256"))
            and row.get("passed") is True
        )
        row_validity.append(valid)
        if valid:
            by_case[row["case_id"]] = row
    intrinsic = oracle.get("intrinsic_gate")
    comparison = oracle.get("oracle_comparison")
    fields = {
        "oracle_hash_well_formed": is_sha256(oracle_sha256),
        "mode_exact": identity.get("mode") == "sequential-oracle",
        "identity_exact": identity.get("suite_sha256") == suite_sha256 == SUITE_SHA256
        and identity.get("model_sha256") == MODEL_SHA256
        and identity.get("runtime_sha256") == RUNTIME_SHA256
        and identity.get("band") == "short",
        "topology_exact": json_exact(identity.get("ctx_size_total"), 65536)
        and json_exact(identity.get("ctx_size_per_slot"), 32768)
        and json_exact(identity.get("parallel_slots"), 2)
        and identity.get("cache_type_k") == "f16"
        and identity.get("cache_type_v") == "f16",
        "payload_exact": json_exact(identity.get("max_tokens"), TOKEN_COUNT)
        and identity.get("ignore_eos") is True
        and json_exact(identity.get("seed"), 1)
        and identity.get("cache_prompt") is False,
        "server_identity_exact": identity.get("server_benchmark_identity")
        == SERVER_IDENTITY,
        "intrinsic_passed": isinstance(intrinsic, dict)
        and intrinsic.get("passed") is True,
        "baseline_ready": isinstance(comparison, dict)
        and comparison.get("status") == "BASELINE_CAPTURE_READY",
        "rows_exact": len(rows) == 2
        and all(row_validity)
        and set(by_case) == set(EXPECTED_CASES),
        "oracle_case_slot_mapping_exact": len(rows) == 2
        and by_case.get(EXPECTED_CASES[0], {}).get("slot_id") == 0
        and by_case.get(EXPECTED_CASES[1], {}).get("slot_id") == 1,
        "selector_valid": is_json_integer(selector) and selector in (0, 1),
    }
    return fields, by_case


def compare_tokens(observed: Any, expected: Any) -> dict[str, Any]:
    if not is_token_list(observed, TOKEN_COUNT) or not is_token_list(
        expected, TOKEN_COUNT
    ):
        return {
            "comparable": False,
            "exact": False,
            "lcp_tokens": None,
            "first_mismatch": None,
        }
    lcp = 0
    while lcp < TOKEN_COUNT and observed[lcp] == expected[lcp]:
        lcp += 1
    mismatch = None
    if lcp < TOKEN_COUNT:
        mismatch = {
            "index_zero_based": lcp,
            "ordinal_one_based": lcp + 1,
            "observed_token_id": observed[lcp],
            "oracle_token_id": expected[lcp],
        }
    return {
        "comparable": True,
        "exact": lcp == TOKEN_COUNT,
        "lcp_tokens": lcp,
        "first_mismatch": mismatch,
    }


def payload_fields(item: dict[str, Any]) -> dict[str, bool]:
    payload = item.get("payload")
    payload = payload if isinstance(payload, dict) else {}
    expected_keys = {"prompt", "id_slot", *PAYLOAD_FIELDS}
    return {
        "keys_exact": set(payload) == expected_keys,
        "prompt_exact": isinstance(item.get("rendered"), str)
        and payload.get("prompt") == item.get("rendered"),
        "slot_exact": payload.get("id_slot") == item.get("slot_id")
        and is_json_integer(payload.get("id_slot")),
        "values_exact": all(
            json_exact(payload.get(name), expected)
            for name, expected in PAYLOAD_FIELDS.items()
        ),
        "sampling_overrides_absent": not (set(payload) & FORBIDDEN_PAYLOAD_FIELDS),
    }


def recompute_stored_row_contract(
    row: dict[str, Any], oracle_row: dict[str, Any]
) -> dict[str, Any]:
    tokens = row.get("token_ids")
    offsets = row.get("token_offsets_s")
    content = row.get("content")
    final = row.get("final")
    final = final if isinstance(final, dict) else {}
    timings = final.get("timings")
    timings = timings if isinstance(timings, dict) else {}
    start = row.get("request_started_perf_s")
    end = row.get("request_ended_perf_s")
    offsets_complete = (
        isinstance(offsets, list)
        and len(offsets) == TOKEN_COUNT
        and all(is_finite_number(value) and value >= 0 for value in offsets)
    )
    evidence_fields = {
        "tokens_512": is_token_list(tokens, TOKEN_COUNT),
        "offsets_512": offsets_complete,
        "offsets_monotonic": offsets_complete
        and all(
            offsets[index] <= offsets[index + 1] for index in range(TOKEN_COUNT - 1)
        ),
        "content_string": isinstance(content, str),
        "slot_exact": is_json_integer(row.get("slot_id"))
        and is_json_integer(final.get("id_slot"))
        and final.get("id_slot") == row.get("slot_id"),
        "cache_zero": is_json_integer(timings.get("cache_n"))
        and timings.get("cache_n") == 0,
        "predicted_512": is_json_integer(timings.get("predicted_n"))
        and timings.get("predicted_n") == TOKEN_COUNT,
        "prompt_count_exact": is_json_integer(timings.get("prompt_n"))
        and timings.get("prompt_n")
        == oracle_row.get("calibrated_prompt_tokens")
        == EXPECTED_PROMPT_TOKENS.get(row.get("case_id")),
        "limit_stop": final.get("stop_type") == "limit",
        "not_truncated": final.get("truncated") is False,
        "request_time_order": is_finite_number(start)
        and is_finite_number(end)
        and end >= start,
    }
    payload = row.get("payload")
    payload = payload if isinstance(payload, dict) else {}
    expected_payload_keys = {"prompt", "id_slot", *PAYLOAD_FIELDS}
    payload_prompt = payload.get("prompt")
    payload_fields_recomputed = {
        "keys_exact": set(payload) == expected_payload_keys,
        "prompt_exact": isinstance(payload_prompt, str)
        and sha256_bytes(payload_prompt.encode())
        == row.get("rendered_prompt_sha256")
        == oracle_row.get("rendered_prompt_sha256"),
        "slot_exact": payload.get("id_slot") == row.get("slot_id")
        and is_json_integer(payload.get("id_slot")),
        "values_exact": all(
            json_exact(payload.get(name), expected)
            for name, expected in PAYLOAD_FIELDS.items()
        ),
        "sampling_overrides_absent": not (set(payload) & FORBIDDEN_PAYLOAD_FIELDS),
    }
    t100 = start + offsets[99] if offsets_complete and is_finite_number(start) else None
    t512 = (
        start + offsets[511] if offsets_complete and is_finite_number(start) else None
    )
    evidence_fields["request_time_order"] = (
        evidence_fields["request_time_order"]
        and is_finite_number(t100)
        and is_finite_number(t512)
        and start <= t100 <= t512 <= end
    )
    return {
        "evidence_fields": evidence_fields,
        "payload_fields": payload_fields_recomputed,
        "t100_perf_s": t100,
        "t512_perf_s": t512,
    }


def validate_stored_row_contract(
    row: dict[str, Any], oracle_row: dict[str, Any]
) -> tuple[dict[str, bool], dict[str, Any]]:
    recomputed = recompute_stored_row_contract(row, oracle_row)
    evidence_fields = recomputed["evidence_fields"]
    stored_payload_fields = recomputed["payload_fields"]
    fields = {
        "evidence_map_recomputed_exact": row.get("evidence_fields") == evidence_fields
        and all(evidence_fields.values()),
        "evidence_valid_recomputed_exact": row.get("evidence_valid")
        is all(evidence_fields.values()),
        "payload_map_recomputed_exact": row.get("payload_fields")
        == stored_payload_fields
        and all(stored_payload_fields.values()),
        "t100_recomputed_exact": json_exact(
            row.get("t100_perf_s"), recomputed["t100_perf_s"]
        ),
        "t512_recomputed_exact": json_exact(
            row.get("t512_perf_s"), recomputed["t512_perf_s"]
        ),
    }
    return fields, recomputed


def validate_slots(value: Any, require_cache_zero: bool) -> dict[str, Any]:
    slots = value if isinstance(value, list) else []
    rows: list[dict[str, Any]] = []
    for slot in slots:
        slot = slot if isinstance(slot, dict) else {}
        fields = {
            "id_valid": is_json_integer(slot.get("id")) and slot.get("id") in (0, 1),
            "idle": slot.get("is_processing") is False,
            "ctx_exact": is_json_integer(slot.get("n_ctx"))
            and slot.get("n_ctx") == 32768,
            "cache_exact": not require_cache_zero
            or (
                is_json_integer(slot.get("n_prompt_tokens_cache"))
                and slot.get("n_prompt_tokens_cache") == 0
            ),
        }
        rows.append(
            {
                "slot_id": slot.get("id"),
                "fields": fields,
                "passed": all(fields.values()),
            }
        )
    return {
        "snapshot": slots,
        "rows": rows,
        "passed": len(rows) == 2
        and {row["slot_id"] for row in rows} == {0, 1}
        and all(row["passed"] for row in rows),
    }


def classify_occupancy(
    metrics_before: dict[str, Any], metrics_after: dict[str, Any]
) -> dict[str, Any]:
    keys = ("tokens_predicted_total", "n_decode_total", "n_busy_slots_per_decode")
    numeric = all(
        isinstance(snapshot, dict)
        and all(
            is_finite_number(snapshot.get(key)) and snapshot[key] >= 0 for key in keys
        )
        for snapshot in (metrics_before, metrics_after)
    )
    integral_counters = numeric and all(
        float(snapshot[key]).is_integer()
        for snapshot in (metrics_before, metrics_after)
        for key in ("tokens_predicted_total", "n_decode_total")
    )
    busy_bounds = numeric and all(
        0 <= snapshot["n_busy_slots_per_decode"] <= 2
        for snapshot in (metrics_before, metrics_after)
    )
    snapshots_valid = numeric and integral_counters and busy_bounds
    predicted_delta = (
        metrics_after["tokens_predicted_total"]
        - metrics_before["tokens_predicted_total"]
        if snapshots_valid
        else None
    )
    decode_delta = (
        metrics_after["n_decode_total"] - metrics_before["n_decode_total"]
        if snapshots_valid
        else None
    )
    predicted_per_decode = (
        predicted_delta / decode_delta
        if is_finite_number(predicted_delta)
        and is_finite_number(decode_delta)
        and decode_delta > 0
        else None
    )
    fields = {
        "numeric_snapshots_valid": numeric,
        "integral_counters_valid": integral_counters,
        "busy_metrics_bounded_zero_to_two": busy_bounds,
        "fresh_counters_zero": snapshots_valid
        and all(metrics_before[key] == 0 for key in keys),
        "counters_monotonic": snapshots_valid
        and is_finite_number(predicted_delta)
        and is_finite_number(decode_delta)
        and predicted_delta >= 0
        and decode_delta >= 0,
        "predicted_delta_1024": predicted_delta == 2 * TOKEN_COUNT,
        "decode_delta_full512_floor": is_finite_number(decode_delta)
        and decode_delta >= TOKEN_COUNT,
        "ratio_proves_m2": is_finite_number(predicted_per_decode)
        and OCCUPANCY_MINIMUM <= predicted_per_decode <= 2,
        "busy_metric_proves_m2": snapshots_valid
        and OCCUPANCY_MINIMUM <= metrics_after["n_busy_slots_per_decode"] <= 2,
    }
    return {
        "metrics_before": metrics_before,
        "metrics_after": metrics_after,
        "tokens_predicted_delta": predicted_delta,
        "llama_decode_calls_delta": decode_delta,
        "predicted_tokens_per_llama_decode": predicted_per_decode,
        "minimum": OCCUPANCY_MINIMUM,
        "maximum": 2,
        "fields": fields,
        "passed": all(fields.values()),
    }


def classify_synchronization(
    rows: list[dict[str, Any]], barrier_release: Any
) -> dict[str, Any]:
    starts = [row.get("request_started_perf_s") for row in rows]
    t100 = [row.get("t100_perf_s") for row in rows]
    t512 = [row.get("t512_perf_s") for row in rows]
    exactly_two_rows = len(rows) == 2
    numeric_timestamps = (
        exactly_two_rows
        and is_finite_number(barrier_release)
        and all(is_finite_number(value) for value in starts + t100 + t512)
    )
    request_skew = max(starts) - min(starts) if numeric_timestamps else None
    fields = {
        "exactly_two_rows": exactly_two_rows,
        "numeric_timestamps": numeric_timestamps,
        "per_row_time_order": numeric_timestamps
        and all(
            start <= at_100 <= at_512
            for start, at_100, at_512 in zip(starts, t100, t512)
        ),
        "starts_after_barrier": numeric_timestamps
        and all(value >= barrier_release for value in starts),
        "request_skew_within_limit": is_finite_number(request_skew)
        and request_skew <= REQUEST_SKEW_LIMIT_S,
        "broad_decode_overlap": numeric_timestamps and max(t100) < min(t512),
    }
    return {
        "barrier_release_perf_s": barrier_release,
        "request_skew_s": request_skew,
        "request_skew_limit_s": REQUEST_SKEW_LIMIT_S,
        "starts_after_barrier": fields["starts_after_barrier"],
        "broad_decode_overlap": fields["broad_decode_overlap"],
        "fields": fields,
        "passed": all(fields.values()),
    }


def validate_server_attestation(
    value: dict[str, Any], runtime_sha256: str
) -> dict[str, bool]:
    identity = value.get("expected_identity")
    identity = identity if isinstance(identity, dict) else {}
    identity_fields = value.get("identity_fields")
    argv_fields = value.get("argv_fields")
    runtime_fields = value.get("runtime_fields")
    return {
        "passed": value.get("passed") is True,
        "identity_fields_all_true": isinstance(identity_fields, dict)
        and bool(identity_fields)
        and all(field is True for field in identity_fields.values()),
        "argv_fields_all_true": isinstance(argv_fields, dict)
        and bool(argv_fields)
        and all(field is True for field in argv_fields.values()),
        "runtime_fields_all_true": isinstance(runtime_fields, dict)
        and bool(runtime_fields)
        and all(field is True for field in runtime_fields.values()),
        "identity_exact": identity == SERVER_IDENTITY,
        "runtime_exact": identity.get("llama_server_sha256") == runtime_sha256,
    }


def recompute_server_attestation(
    attestation_path: Path, server_log_path: Path, identity_log_path: Path
) -> tuple[bool, dict[str, Any]]:
    source = Path(__file__).resolve().with_name("attest-c2-server.py")
    module = load_module(source, "canonical_crossover_server_attester")
    recomputed = json.loads(
        json.dumps(
            module.build_attestation(
                server_log_path.read_text(errors="replace"),
                identity_log_path.read_text(errors="replace"),
                28595763424,
                RUNTIME_SHA256,
                1024,
                None,
            )
        )
    )
    stored = load_json(attestation_path, "server attestation")
    return stored == recomputed and recomputed.get("passed") is True, recomputed


def command_option_values(argv: list[str], option: str) -> list[str]:
    values: list[str] = []
    for index, value in enumerate(argv):
        if value == option:
            values.append(argv[index + 1] if index + 1 < len(argv) else "")
        elif value.startswith(f"{option}="):
            values.append(value.split("=", 1)[1])
    return values


def command_has_exact_option(argv: list[str], option: str, expected: str) -> bool:
    return command_option_values(argv, option) == [expected]


def canonical_server_argv(argv: list[str], port: int) -> bool:
    gpu_index = port - 19720
    if (
        gpu_index not in range(4)
        or len(argv) < 3
        or re.fullmatch(r"/proc/self/fd/[1-9][0-9]*", argv[2]) is None
    ):
        return False
    expected = [
        "/mnt/fast-ai/runtime/llama.cpp-15586e2d-q8-c2-canonical-109eee6f-hybrid/llama-server",
        "-m",
        argv[2],
        "--alias",
        "qwen36-27b-q8_0-target-only",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "-dev",
        f"SYCL{gpu_index}",
        "-ngl",
        "99",
        "-c",
        "65536",
        "-np",
        "2",
        "-b",
        "1024",
        "-ub",
        "128",
        "-t",
        "8",
        "--threads-http",
        "6",
        "--poll",
        "50",
        "-lv",
        "4",
        "-ctk",
        "f16",
        "-ctv",
        "f16",
        "-fa",
        "on",
        "--spec-type",
        "none",
        "--reasoning",
        "off",
        "--ctx-checkpoints",
        "0",
        "--cache-ram",
        "0",
        "--no-cache-idle-slots",
        "--no-context-shift",
        "--slots",
        "--metrics",
        "--jinja",
        "--no-kv-unified",
        "--cont-batching",
    ]
    return argv == expected


def process_start_epoch_s(start_ticks: int) -> float | None:
    if not is_json_integer(start_ticks) or start_ticks <= 0:
        return None
    try:
        boot_rows = [
            line for line in Path("/proc/stat").read_text().splitlines()
            if line.startswith("btime ")
        ]
        ticks_per_second = os.sysconf("SC_CLK_TCK")
        if (
            len(boot_rows) != 1
            or len(boot_rows[0].split()) != 2
            or not boot_rows[0].split()[1].isdigit()
            or not is_json_integer(ticks_per_second)
            or ticks_per_second <= 0
        ):
            return None
        return int(boot_rows[0].split()[1]) + start_ticks / ticks_per_second
    except (OSError, ValueError):
        return None


def validate_retained_live_binding(
    value: Any, expected_pid: int, port: int
) -> tuple[dict[str, bool], dict[str, Any]]:
    binding = value if isinstance(value, dict) else {}
    argv = binding.get("argv")
    argv = argv if isinstance(argv, list) else []
    listener_inodes = binding.get("listener_inodes")
    listener_inodes = listener_inodes if isinstance(listener_inodes, list) else []
    owned_inodes = binding.get("owned_socket_inodes")
    owned_inodes = owned_inodes if isinstance(owned_inodes, list) else []
    argv_well_formed = bool(argv) and all(isinstance(item, str) for item in argv)
    inodes_well_formed = all(
        isinstance(item, str) and re.fullmatch(r"[0-9]+", item) is not None
        for item in listener_inodes + owned_inodes
    )
    inode_lists_canonical = (
        inodes_well_formed
        and listener_inodes == sorted(set(listener_inodes), key=int)
        and owned_inodes == sorted(set(owned_inodes), key=int)
    )
    recomputed_binding_fields = {
        "executable_runtime_exact": binding.get("executable_sha256") == RUNTIME_SHA256,
        "port_argument_exact": argv_well_formed
        and command_has_exact_option(argv, "--port", str(port)),
        "ctx_argument_exact": argv_well_formed
        and command_has_exact_option(argv, "-c", "65536"),
        "parallel_argument_exact": argv_well_formed
        and command_has_exact_option(argv, "-np", "2"),
        "ubatch_argument_exact": argv_well_formed
        and command_has_exact_option(argv, "-ub", "128"),
        "listener_present": inode_lists_canonical and bool(listener_inodes),
        "listener_owned_by_pid": inode_lists_canonical
        and bool(listener_inodes)
        and set(listener_inodes) <= set(owned_inodes),
    }
    recomputed_argv_sha = (
        sha256_bytes(b"\0".join(item.encode() for item in argv))
        if argv_well_formed
        else None
    )
    fields = {
        "pid_exact": is_json_integer(binding.get("pid"))
        and binding.get("pid") == expected_pid,
        "start_ticks_valid": is_json_integer(binding.get("process_start_ticks"))
        and binding["process_start_ticks"] > 0,
        "start_epoch_recomputed_exact": is_finite_number(
            binding.get("process_start_epoch_s")
        )
        and binding.get("process_start_epoch_s")
        == process_start_epoch_s(binding.get("process_start_ticks")),
        "executable_path_absolute": isinstance(binding.get("executable_path"), str)
        and Path(binding["executable_path"]).is_absolute(),
        "executable_path_runtime_exact": binding.get("executable_path")
        == "/mnt/fast-ai/runtime/llama.cpp-15586e2d-q8-c2-canonical-109eee6f-hybrid/llama-server",
        "argv_well_formed": argv_well_formed,
        "argv_executable_exact": argv_well_formed
        and argv[0]
        == "/mnt/fast-ai/runtime/llama.cpp-15586e2d-q8-c2-canonical-109eee6f-hybrid/llama-server",
        "canonical_argv_exact": argv_well_formed and canonical_server_argv(argv, port),
        "host_argument_exact_once": argv_well_formed
        and command_has_exact_option(argv, "--host", "127.0.0.1"),
        "argv_sha_recomputed": binding.get("argv_sha256") == recomputed_argv_sha,
        "sleep_argument_absent": argv_option_absent(argv, "--sleep-idle-seconds"),
        "inode_lists_canonical": inode_lists_canonical,
        "binding_fields_recomputed": binding.get("fields") == recomputed_binding_fields
        and all(recomputed_binding_fields.values()),
        "passed_recomputed": binding.get("passed")
        is all(recomputed_binding_fields.values()),
        "capture_epoch_valid": is_json_integer(binding.get("captured_at_epoch_ns"))
        and binding["captured_at_epoch_ns"] > 0,
    }
    return fields, {**binding, "fields": recomputed_binding_fields}


def recompute_binding_continuity(
    before: dict[str, Any], after: dict[str, Any]
) -> dict[str, Any]:
    continuity_fields = {
        "pid_exact": before.get("pid") == after.get("pid"),
        "process_start_exact": before.get("process_start_ticks")
        == after.get("process_start_ticks")
        and before.get("process_start_epoch_s")
        == after.get("process_start_epoch_s")
        == process_start_epoch_s(before.get("process_start_ticks")),
        "executable_exact": before.get("executable_sha256")
        == after.get("executable_sha256"),
        "argv_exact": before.get("argv_sha256") == after.get("argv_sha256"),
        "before_passed": before.get("passed") is True
        and is_json_integer(before.get("captured_at_epoch_ns"))
        and is_json_integer(after.get("captured_at_epoch_ns"))
        and before["captured_at_epoch_ns"] <= after["captured_at_epoch_ns"],
        "after_passed": after.get("passed") is True,
    }
    return {
        "before": before,
        "after": after,
        "continuity_fields": continuity_fields,
        "passed": all(continuity_fields.values()),
    }


def validate_snapshot_exact(value: Any, expected_paths: dict[str, Path]) -> bool:
    if not isinstance(value, dict) or not value or set(value) != set(expected_paths):
        return False
    try:
        expected = snapshot_inputs(expected_paths)
    except ValueError:
        return False
    return value == expected


def validate_retained_attestation_binding(
    value: Any, attestation_path: Path, binding: dict[str, Any]
) -> bool:
    retained = value if isinstance(value, dict) else {}
    modified_epoch_ns = attestation_path.stat().st_mtime_ns
    modified_epoch_s = modified_epoch_ns / 1_000_000_000
    process_epoch_s = binding.get("process_start_epoch_s")
    fields = {
        "regular_file": attestation_path.is_file()
        and not attestation_path.is_symlink(),
        "live_binding_passed": binding.get("passed") is True,
        "attestation_created_after_process_start": is_finite_number(process_epoch_s)
        and modified_epoch_s >= process_epoch_s,
        "attestation_not_future_dated": modified_epoch_s <= time.time() + 1,
    }
    expected = {
        "attestation_path": str(attestation_path.resolve()),
        "attestation_modified_epoch_s": modified_epoch_s,
        "process_start_epoch_s": process_epoch_s,
        "fields": fields,
        "passed": all(fields.values()),
    }
    before_capture_ns = binding.get("captured_at_epoch_ns")
    chronology_exact = (
        is_json_integer(before_capture_ns)
        and is_finite_number(process_epoch_s)
        and process_epoch_s <= modified_epoch_s
        and modified_epoch_ns <= before_capture_ns
    )
    return retained == expected and expected["passed"] is True and chronology_exact


def recompute_capture_provenance(
    result: dict[str, Any],
    plan: dict[str, Any],
    capture_path: Path,
    prerelease_path: Path,
    postcapture_path: Path,
    server_attestation_path: Path,
    server_log_path: Path,
    identity_log_path: Path,
    expected_input_paths: dict[str, Path],
    server_pid: str,
    port: int,
    oracle_sha256: str,
    phase1_manifest_sha256: str,
    phase1_summary_sha256: str,
    phase1_marker_sha256: str,
) -> tuple[dict[str, bool], dict[str, Any]]:
    binding_before = result.get("live_binding_before")
    binding_before = binding_before if isinstance(binding_before, dict) else {}
    binding_after = result.get("live_binding_after")
    binding_after = binding_after if isinstance(binding_after, dict) else {}
    expected_pid = int(server_pid) if re.fullmatch(r"[1-9][0-9]*", server_pid) else -1
    before_fields, _ = validate_retained_live_binding(
        binding_before, expected_pid, port
    )
    after_fields, _ = validate_retained_live_binding(binding_after, expected_pid, port)
    recomputed_continuity = recompute_binding_continuity(binding_before, binding_after)
    before_ns = binding_before.get("captured_at_epoch_ns")
    after_ns = binding_after.get("captured_at_epoch_ns")
    capture_mtime = capture_path.stat().st_mtime_ns
    pre_mtime = prerelease_path.stat().st_mtime_ns
    post_mtime = postcapture_path.stat().st_mtime_ns
    server_attestation = load_json(server_attestation_path, "server attestation")
    server_fields = validate_server_attestation(server_attestation, RUNTIME_SHA256)
    server_raw_exact, server_raw_recomputed = recompute_server_attestation(
        server_attestation_path, server_log_path, identity_log_path
    )
    identity_header = identity_log_path.read_text(errors="replace").split(
        "--- server ---", 1
    )[0]
    identity_argv_values = [
        line.split("=", 1)[1]
        for line in identity_header.splitlines()
        if line.startswith("argv=")
    ]
    try:
        identity_argv = (
            shlex.split(identity_argv_values[0])
            if len(identity_argv_values) == 1
            else []
        )
    except ValueError:
        identity_argv = []
    fields = {
        "capture_evidence_valid": result.get("evidence_valid") is True
        and result.get("status") == "EVIDENCE_VALID",
        "capture_plan_exact": all(
            json_exact(result.get(key), value) for key, value in plan.items()
        ),
        "capture_selector_oracle_exact": result.get("run_identity", {}).get(
            "oracle_sha256"
        )
        == oracle_sha256,
        "capture_phase1_exact": result.get("run_identity", {}).get(
            "phase1_manifest_sha256"
        )
        == phase1_manifest_sha256
        and result.get("run_identity", {}).get("phase1_summary_sha256")
        == phase1_summary_sha256
        and result.get("run_identity", {}).get("phase1_marker_sha256")
        == phase1_marker_sha256,
        "capture_server_pid_exact": result.get("server_pid") == server_pid,
        "capture_port_exact": result.get("port") == port,
        "capture_time_order": is_json_integer(before_ns)
        and is_json_integer(after_ns)
        and pre_mtime <= before_ns <= after_ns <= capture_mtime <= post_mtime,
        "live_binding_before_recomputed": all(before_fields.values()),
        "live_binding_after_recomputed": all(after_fields.values()),
        "live_binding_continuity_recomputed": result.get("live_process_continuity")
        == recomputed_continuity
        and recomputed_continuity["passed"] is True,
        "live_binding_identity_exact": binding_before.get("pid") == expected_pid
        and binding_after.get("pid") == expected_pid
        and binding_before.get("executable_sha256") == RUNTIME_SHA256
        and binding_after.get("executable_sha256") == RUNTIME_SHA256,
        "sleep_argv_absent": argv_option_absent(
            binding_before.get("argv"), "--sleep-idle-seconds"
        )
        and argv_option_absent(binding_after.get("argv"), "--sleep-idle-seconds"),
        "server_attestation_recomputed": all(server_fields.values()),
        "server_attestation_raw_exact": server_raw_exact,
        "identity_argv_matches_live_binding": bool(identity_argv)
        and identity_argv == binding_before.get("argv") == binding_after.get("argv"),
        "capture_inputs_before_exact": validate_snapshot_exact(
            result.get("inputs_before"), expected_input_paths
        ),
        "capture_inputs_after_exact": validate_snapshot_exact(
            result.get("inputs_after"), expected_input_paths
        ),
        "capture_inputs_unchanged": result.get("inputs_before")
        == result.get("inputs_after"),
        "attestation_process_binding_recomputed": validate_retained_attestation_binding(
            result.get("attestation_process_binding"),
            server_attestation_path,
            binding_before,
        ),
    }
    return fields, {
        "before_fields": before_fields,
        "after_fields": after_fields,
        "continuity": recomputed_continuity,
        "server_attestation_fields": server_fields,
        "server_attestation_raw": server_raw_recomputed,
    }


def capture(args: argparse.Namespace) -> int:
    global _FAILURE_OUTPUT
    _FAILURE_OUTPUT = args.out
    plan = expected_plan_row(args.wave, args.gpu_index)
    if plan["scenario"] != args.scenario or plan["selector"] != args.selector:
        raise ValueError("capture arguments differ from the frozen crossover map")
    if (args.model_sha256, args.runtime_sha256, args.suite_sha256) != (
        MODEL_SHA256,
        RUNTIME_SHA256,
        SUITE_SHA256,
    ):
        raise ValueError("capture identity differs from the canonical control")
    parsed = urlparse(args.base_url)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in ("127.0.0.1", "localhost")
        or parsed.port is None
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "base URL must be a loopback HTTP origin with an explicit port"
        )
    if args.timeout <= 0 or args.server_pid <= 1:
        raise ValueError("timeout and server PID must be positive")
    input_paths = {
        "suite": args.suite,
        "prompt_builder": args.prompt_builder,
        "common_script": args.common_script,
        "capture_helper": args.capture_helper,
        "matrix_client": args.matrix_client,
        "server_attestation": args.server_attestation,
        "selector_oracle": args.oracle,
        "phase1_manifest": args.phase1_dir / "wave-artifacts.sha256",
        "phase1_summary": args.phase1_dir / "phase-summary.json",
        "phase1_marker": args.phase1_dir / "wave-diagnostic-completion-status.json",
    }
    before_inputs = snapshot_inputs(input_paths)
    for label, expected in (
        ("suite", args.suite_sha256),
        ("capture_helper", args.capture_helper_sha256),
        ("matrix_client", args.matrix_client_sha256),
        ("server_attestation", args.server_attestation_sha256),
        ("selector_oracle", args.oracle_sha256),
        ("phase1_manifest", args.phase1_manifest_sha256),
        ("phase1_summary", args.phase1_summary_sha256),
        ("phase1_marker", args.phase1_marker_sha256),
    ):
        if before_inputs[label]["sha256"] != expected:
            raise ValueError(f"{label} SHA-256 mismatch")
    phase1_fields, phase1_observed, _ = validate_phase1_packet(
        args.phase1_dir,
        args.phase1_manifest_sha256,
        args.phase1_summary_sha256,
        args.phase1_marker_sha256,
        args.selector,
        args.oracle,
        args.oracle_sha256,
    )
    if not all(phase1_fields.values()):
        raise ValueError(
            "Phase-1 handoff failed: "
            + ", ".join(name for name, passed in phase1_fields.items() if not passed)
        )
    suite = load_json(args.suite, "c2 suite")
    cases = load_short_cases(suite, args.scenario)
    oracle = load_json(args.oracle, "selector oracle")
    oracle_fields, oracle_rows = validate_oracle(
        oracle, args.suite_sha256, args.oracle_sha256, args.selector
    )
    if not all(oracle_fields.values()):
        raise ValueError("selector-matched oracle is invalid")
    attestation = load_json(args.server_attestation, "server attestation")
    server_fields = validate_server_attestation(attestation, args.runtime_sha256)
    if not all(server_fields.values()):
        raise ValueError("live server attestation is invalid")
    matrix = load_module(args.matrix_client, "canonical_crossover_live_binding")
    binding_before = matrix.capture_live_server_binding(
        args.server_pid, parsed.port, args.runtime_sha256
    )
    binding_before["captured_at_epoch_ns"] = time.time_ns()
    argv = binding_before.get("argv")
    if not argv_option_absent(argv, "--sleep-idle-seconds"):
        raise ValueError("live server argv contains the forbidden sleep option")
    bound_attestation = matrix.bind_attestation_to_process(
        args.server_attestation, binding_before
    )
    if (
        binding_before.get("passed") is not True
        or bound_attestation.get("passed") is not True
    ):
        raise ValueError("server endpoint is not bound to the attested live process")

    helper = load_module(args.capture_helper, "canonical_crossover_capture_helper")
    common = load_module(args.common_script, "canonical_crossover_common")
    prompt_builder = load_module(
        args.prompt_builder, "canonical_crossover_prompt_builder"
    )
    base_url = args.base_url.rstrip("/")
    prepared = helper.prepare_cases(
        base_url, cases, prompt_builder.make_prompt, common, args.timeout, TOKEN_COUNT
    )
    if len(prepared) != 2:
        raise ValueError("capture helper did not prepare exactly two requests")
    for slot_id, item in enumerate(prepared):
        if item.get("slot_id") != slot_id or not all(payload_fields(item).values()):
            raise ValueError(
                "prepared payload differs from the frozen forced-512 contract"
            )
        case_id = (
            item.get("case", {}).get("id")
            if isinstance(item.get("case"), dict)
            else None
        )
        expected = oracle_rows.get(case_id or "", {})
        if sha256_bytes(str(item.get("prompt", "")).encode()) != expected.get(
            "prompt_sha256"
        ) or sha256_bytes(str(item.get("rendered", "")).encode()) != expected.get(
            "rendered_prompt_sha256"
        ):
            raise ValueError("live prompt identity differs from the selector oracle")

    slots_before = helper.capture_idle_slots(base_url, args.timeout)
    metrics_before = helper.capture_metrics(base_url, args.timeout)
    streams, barrier_release = helper.capture_streams(
        "concurrent", base_url, prepared, common, args.timeout
    )
    if not isinstance(streams, list) or len(streams) != 2:
        raise ValueError("capture helper did not return exactly two concurrent streams")
    metrics_after = helper.capture_metrics(base_url, args.timeout)
    slots_after = helper.capture_idle_slots(base_url, args.timeout)
    binding_after = matrix.capture_live_server_binding(
        args.server_pid, parsed.port, args.runtime_sha256
    )
    binding_after["captured_at_epoch_ns"] = time.time_ns()
    continuity = matrix.compare_live_server_bindings(binding_before, binding_after)

    rows: list[dict[str, Any]] = []
    for item, stream in zip(prepared, streams):
        case = item["case"]
        case_id = case["id"]
        tokens = stream.get("token_ids")
        offsets = stream.get("token_offsets_s")
        final = stream.get("final")
        final = final if isinstance(final, dict) else {}
        timings = final.get("timings")
        timings = timings if isinstance(timings, dict) else {}
        content = stream.get("content")
        oracle_row = oracle_rows.get(case_id, {})
        evidence_fields = {
            "tokens_512": is_token_list(tokens, TOKEN_COUNT),
            "offsets_512": isinstance(offsets, list)
            and len(offsets) == TOKEN_COUNT
            and all(is_finite_number(value) and value >= 0 for value in offsets),
            "offsets_monotonic": isinstance(offsets, list)
            and len(offsets) == TOKEN_COUNT
            and all(
                offsets[index] <= offsets[index + 1] for index in range(TOKEN_COUNT - 1)
            ),
            "content_string": isinstance(content, str),
            "slot_exact": is_json_integer(final.get("id_slot"))
            and final.get("id_slot") == item["slot_id"],
            "cache_zero": is_json_integer(timings.get("cache_n"))
            and timings.get("cache_n") == 0,
            "predicted_512": is_json_integer(timings.get("predicted_n"))
            and timings.get("predicted_n") == TOKEN_COUNT,
            "prompt_count_exact": is_json_integer(timings.get("prompt_n"))
            and timings.get("prompt_n")
            == case.get("calibrated_prompt_tokens"),
            "limit_stop": final.get("stop_type") == "limit",
            "not_truncated": final.get("truncated") is False,
            "request_time_order": is_finite_number(stream.get("request_started_perf_s"))
            and is_finite_number(stream.get("request_ended_perf_s"))
            and stream["request_ended_perf_s"] >= stream["request_started_perf_s"],
        }
        comparison = compare_tokens(tokens, oracle_row.get("token_ids"))
        content_sha = (
            sha256_bytes(content.encode()) if isinstance(content, str) else None
        )
        rows.append(
            {
                "case_id": case_id,
                "slot_id": item["slot_id"],
                "prompt_sha256": sha256_bytes(item["prompt"].encode()),
                "rendered_prompt_sha256": sha256_bytes(item["rendered"].encode()),
                "payload": item["payload"],
                "payload_fields": payload_fields(item),
                "token_ids": tokens,
                "token_ids_sha256": token_sha256(tokens)
                if is_token_list(tokens)
                else None,
                "token_offsets_s": offsets,
                "content": content,
                "content_sha256": content_sha,
                "oracle_content_sha256": oracle_row.get("content_sha256"),
                "content_exact_to_oracle": content_sha
                == oracle_row.get("content_sha256"),
                "oracle_comparison": comparison,
                "request_started_perf_s": stream.get("request_started_perf_s"),
                "request_ended_perf_s": stream.get("request_ended_perf_s"),
                "t100_perf_s": (
                    stream["request_started_perf_s"] + offsets[99]
                    if evidence_fields["offsets_512"]
                    and is_finite_number(stream.get("request_started_perf_s"))
                    else None
                ),
                "t512_perf_s": (
                    stream["request_started_perf_s"] + offsets[511]
                    if evidence_fields["offsets_512"]
                    and is_finite_number(stream.get("request_started_perf_s"))
                    else None
                ),
                "final": final,
                "evidence_fields": evidence_fields,
                "evidence_valid": all(evidence_fields.values()),
                "exact_to_oracle": comparison["exact"]
                and content_sha == oracle_row.get("content_sha256"),
            }
        )

    synchronization = classify_synchronization(rows, barrier_release)
    occupancy = classify_occupancy(metrics_before, metrics_after)
    before_slot_gate = validate_slots(slots_before, False)
    after_slot_gate = validate_slots(slots_after, True)
    after_inputs = snapshot_inputs(input_paths)
    input_continuity = before_inputs == after_inputs
    phase1_after_fields, phase1_after_observed, _ = validate_phase1_packet(
        args.phase1_dir,
        args.phase1_manifest_sha256,
        args.phase1_summary_sha256,
        args.phase1_marker_sha256,
        args.selector,
        args.oracle,
        args.oracle_sha256,
    )
    evidence_fields = {
        "phase1_handoff": all(phase1_fields.values()),
        "phase1_handoff_unchanged": all(phase1_after_fields.values())
        and phase1_fields == phase1_after_fields,
        "oracle": all(oracle_fields.values()),
        "server_attestation": all(server_fields.values()),
        "input_continuity": input_continuity,
        "rows_complete": len(rows) == 2 and all(row["evidence_valid"] for row in rows),
        "payloads_exact": all(all(row["payload_fields"].values()) for row in rows),
        "synchronization_and_overlap": synchronization["passed"] is True,
        "m2_occupancy": occupancy["passed"] is True,
        "slots_before": before_slot_gate["passed"] is True,
        "slots_after": after_slot_gate["passed"] is True,
        "live_process_continuity": continuity.get("passed") is True,
        "sleep_argument_absent": argv_option_absent(
            binding_before.get("argv"), "--sleep-idle-seconds"
        )
        and argv_option_absent(binding_after.get("argv"), "--sleep-idle-seconds"),
    }
    result = {
        "schema_version": SCHEMA_VERSION,
        "phase": "canonical-q8-c2-crossover-lane-capture",
        "status": "EVIDENCE_VALID"
        if all(evidence_fields.values())
        else "INVALID_EVIDENCE",
        "evidence_valid": all(evidence_fields.values()),
        "evidence_class": "diagnostic-only",
        "performance_promotable": False,
        "interpretation_guard": {
            "performance_claim": False,
            "latency_claim": False,
            "fairness_claim": False,
            "timing_use": "synchronization-and-overlap-only",
        },
        **plan,
        "server_pid": str(args.server_pid),
        "port": parsed.port,
        "run_identity": {
            "model_sha256": args.model_sha256,
            "runtime_sha256": args.runtime_sha256,
            "runtime_manifest_sha256": MANIFEST_SHA256,
            "canonical_sycl_dso_sha256": SYCL_DSO_SHA256,
            "suite_sha256": args.suite_sha256,
            "oracle_sha256": args.oracle_sha256,
            "phase1_manifest_sha256": args.phase1_manifest_sha256,
            "phase1_summary_sha256": args.phase1_summary_sha256,
            "phase1_marker_sha256": args.phase1_marker_sha256,
            "ctx_size_total": 65536,
            "ctx_size_per_slot": 32768,
            "parallel_slots": 2,
            "cache_type_k": "f16",
            "cache_type_v": "f16",
            "kv_unified": False,
            "max_tokens": TOKEN_COUNT,
            "ignore_eos": True,
            "seed": 1,
            "cache_prompt": False,
        },
        "evidence_fields": evidence_fields,
        "phase1_fields": phase1_fields,
        "phase1_observed": phase1_observed,
        "phase1_after_fields": phase1_after_fields,
        "phase1_after_observed": phase1_after_observed,
        "oracle_fields": oracle_fields,
        "server_attestation_fields": server_fields,
        "inputs_before": before_inputs,
        "inputs_after": after_inputs,
        "live_binding_before": binding_before,
        "live_binding_after": binding_after,
        "attestation_process_binding": bound_attestation,
        "live_process_continuity": continuity,
        "synchronization": synchronization,
        "occupancy": occupancy,
        "slot_topology": {"before": before_slot_gate, "after": after_slot_gate},
        "rows": rows,
    }
    write_json_new(args.out, result)
    _FAILURE_OUTPUT = None
    return 0 if result["evidence_valid"] else 1


def exact_header_fields(
    identity_bytes: bytes, expected: dict[str, str]
) -> dict[str, bool]:
    lines = identity_bytes.decode("utf-8", errors="replace").splitlines()
    delimiters = [index for index, line in enumerate(lines) if line == "--- server ---"]
    header = lines[: delimiters[0]] if delimiters else lines
    fields = {"identity_delimiter_exactly_once": len(delimiters) == 1}
    for name, value in expected.items():
        fields[f"identity_{name}_exactly_once"] = [
            line for line in header if line.startswith(f"{name}=")
        ] == [f"{name}={value}"]
    return fields


def first_hit_shape(match: re.Match[str]) -> dict[str, bool]:
    src0 = [int(value) for value in match.groups()[2:6]]
    src1 = [int(value) for value in match.groups()[6:10]]
    dst = [int(value) for value in match.groups()[10:14]]
    layout = match.group(1)
    expected_batch = [2, 1, 1] if layout == "flat" else [1, 2, 1]
    fields = {
        "positive_matrix_dimensions": src0[0] > 0 and src0[1] > 0,
        "src0_matrix": src0[2:] == [1, 1],
        "src1_layout": src1[1:] == expected_batch,
        "dst_layout": dst[1:] == expected_batch,
        "inner_dimension": src1[0] == src0[0],
        "output_dimension": dst[0] == src0[1],
    }
    if layout == "recurrent":
        fields.update(
            {
                "recurrent_weight_name": match.group(2).endswith("ssm_out.weight"),
                "recurrent_src0_exact": src0 == [6144, 5120, 1, 1],
                "recurrent_src1_exact": src1 == [6144, 1, 2, 1],
                "recurrent_dst_exact": dst == [5120, 1, 2, 1],
            }
        )
    return fields


def parse_route_markers(
    full_log: bytes,
    prerelease: bytes,
    postcapture: bytes,
    selector: int,
    server_pid: str,
    phase1_flat_marker: str | None,
) -> tuple[dict[str, bool], dict[str, Any]]:
    full_lines_raw = full_log.decode("utf-8", errors="replace").splitlines()
    full_lines = [normalize_runtime_line(line) for line in full_lines_raw]
    pre_lines = [
        normalize_runtime_line(line)
        for line in prerelease.decode("utf-8", errors="replace").splitlines()
    ]
    post_lines = [
        normalize_runtime_line(line)
        for line in postcapture.decode("utf-8", errors="replace").splitlines()
    ]

    def canonical(lines: list[str]) -> list[str]:
        return [
            line
            for line in lines
            if line.startswith(
                (f"{MARKER} first-hit:", f"{MARKER} summary:", f"{MARKER} violation:")
            )
        ]

    full_markers = canonical(full_lines)
    pre_markers = canonical(pre_lines)
    post_markers = canonical(post_lines)
    first_candidates = [
        line for line in full_markers if line.startswith(f"{MARKER} first-hit:")
    ]
    matches = [FIRST_HIT_RE.fullmatch(line) for line in first_candidates]
    good_matches = [match for match in matches if match is not None]
    layouts = [match.group(1) for match in good_matches]
    shape_fields = [first_hit_shape(match) for match in good_matches]
    summaries = [line for line in full_markers if line.startswith(f"{MARKER} summary:")]
    summary_matches = [SUMMARY_RE.fullmatch(line) for line in summaries]
    summary_matches = [match for match in summary_matches if match is not None]
    violations = [
        line for line in full_markers if line.startswith(f"{MARKER} violation:")
    ]
    process_candidates = [line for line in full_lines_raw if PROCESS_BINDING in line]
    process_matches = [PROCESS_RE.fullmatch(line) for line in process_candidates]
    process_matches = [match for match in process_matches if match is not None]
    startup = [line for line in full_lines if line.strip().startswith(f"{CONTROL}:")]
    expected_startup = f"  {CONTROL}: {selector}"
    process_indexes = [
        index
        for index, line in enumerate(full_lines_raw)
        if PROCESS_RE.fullmatch(line) is not None
    ]
    marker_indexes = [
        index
        for index, line in enumerate(full_lines)
        if line.startswith(
            (f"{MARKER} first-hit:", f"{MARKER} summary:", f"{MARKER} violation:")
        )
    ]
    startup_indexes = [
        index
        for index, line in enumerate(full_lines)
        if line.strip().startswith(f"{CONTROL}:")
    ]
    summary_internal = True
    if len(summary_matches) == 1:
        values = dict(
            zip(SUMMARY_FIELDS, (int(value) for value in summary_matches[0].groups()))
        )
        dispatch = values["flat_dispatches"] + values["recurrent_dispatches"]
        summary_internal = (
            values["flat_dispatches"] > 0
            and values["recurrent_dispatches"] > 0
            and values["flat_multicol_suppressed"] == values["flat_dispatches"]
            and values["recurrent_dmmv_suppressed"] == values["recurrent_dispatches"]
            and values["reorder_ready_dispatches"] == dispatch
            and values["single_col_mmvq_calls"] == 2 * dispatch
            and values["violations"] == 0
        )
    elif summaries:
        summary_internal = False
    fields = {
        "process_binding_exactly_once": len(process_candidates) == 1
        and len(process_matches) == 1,
        "process_binding_pid_exact": len(process_matches) == 1
        and process_matches[0].group(1) == server_pid,
        "process_binding_precedes_routes": len(process_indexes) == 1
        and (not marker_indexes or process_indexes[0] < min(marker_indexes)),
        "startup_optional_but_exact": startup in ([], [expected_startup]),
        "startup_order_exact_if_present": not startup_indexes
        or (
            len(startup_indexes) == 1
            and len(process_indexes) == 1
            and process_indexes[0] < startup_indexes[0]
            and (not marker_indexes or startup_indexes[0] < min(marker_indexes))
        ),
        "no_violation": not violations,
    }
    if selector == 0:
        fields.update(
            {
                "off_prerelease_zero_markers": not pre_markers,
                "off_postcapture_zero_markers": not post_markers,
                "off_full_log_zero_markers": not full_markers,
            }
        )
    else:
        pre_first = [
            line for line in pre_markers if line.startswith(f"{MARKER} first-hit:")
        ]
        post_first = [
            line for line in post_markers if line.startswith(f"{MARKER} first-hit:")
        ]
        recurrent_line = (
            good_matches[1].group(0) if layouts == ["flat", "recurrent"] else None
        )
        after_pre = full_log[len(prerelease) :]
        recurrent_after_boundary = (
            recurrent_line is not None and recurrent_line.encode() in after_pre
        )
        summary_after_hits = True
        if summaries:
            line_indexes = {line: index for index, line in enumerate(full_lines)}
            summary_after_hits = line_indexes.get(summaries[0], -1) > max(
                line_indexes.get(line, 10**9) for line in first_candidates
            )
        fields.update(
            {
                "on_first_hits_well_formed": len(first_candidates)
                == len(good_matches)
                == 2,
                "on_first_hit_order_exact": layouts == ["flat", "recurrent"],
                "on_first_hit_shapes_exact": len(shape_fields) == 2
                and all(all(item.values()) for item in shape_fields),
                "on_prerelease_exact_flat_only": len(pre_markers) == 1
                and len(pre_first) == 1
                and pre_first[0] == phase1_flat_marker,
                "on_postcapture_exact_flat_recurrent_only": len(post_markers) == 2
                and post_first == first_candidates,
                "on_recurrent_after_preclient_boundary": recurrent_after_boundary,
                "on_summary_optional_well_formed": len(summaries)
                == len(summary_matches)
                and len(summaries) <= 1,
                "on_summary_internal_if_present": summary_internal,
                "on_summary_after_hits_if_present": summary_after_hits,
            }
        )
    observed = {
        "first_hit_layouts": layouts,
        "first_hit_lines": first_candidates,
        "first_hit_shape_fields": shape_fields,
        "prerelease_marker_lines": pre_markers,
        "postcapture_marker_lines": post_markers,
        "summary_present": bool(summaries),
        "summary_well_formed": len(summaries) == len(summary_matches),
        "summary_internal_consistency": summary_internal,
        "violation_lines": violations,
        "attribution_guard": (
            "First-hit evidence proves route activation only. Optional teardown totals "
            "are neither retained nor used for dispatch-frequency or request-attribution claims."
        ),
    }
    return fields, observed


def parse_resolved_inventory(path: Path) -> dict[str, str] | None:
    if not path.is_file() or path.is_symlink():
        return None
    rows: dict[str, str] = {}
    for line in path.read_text().splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  (/\S.*)", line)
        if match is None or match.group(2) in rows:
            return None
        rows[match.group(2)] = match.group(1)
    return rows if rows else None


def parse_ldd_inventory(path: Path) -> dict[str, str] | None:
    if not path.is_file() or path.is_symlink():
        return None
    rows: dict[str, str] = {}
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("linux-vdso.so.1 "):
            continue
        matched = re.fullmatch(r"(\S+) => (/\S+) \(0x[0-9a-fA-F]+\)", stripped)
        if matched is not None:
            soname, loader_path = matched.groups()
        else:
            matched = re.fullmatch(r"(/\S+) \(0x[0-9a-fA-F]+\)", stripped)
            if matched is None:
                return None
            loader_path = matched.group(1)
            soname = Path(loader_path).name
        if soname in rows:
            return None
        rows[soname] = loader_path
    return rows if rows else None


def runtime_object_exact(
    row: Any, expected_keys: set[str], raw_hashes: dict[str, str], hash_cache: dict[Path, str]
) -> bool:
    if not isinstance(row, dict) or set(row) != expected_keys:
        return False
    loader_value = row.get("loader_path")
    resolved_value = row.get("resolved_path")
    if not isinstance(loader_value, str) or not isinstance(resolved_value, str):
        return False
    loader_path = Path(loader_value)
    resolved_path = Path(resolved_value)
    if (
        not loader_path.is_absolute()
        or not resolved_path.is_absolute()
        or not resolved_path.is_file()
        or resolved_path.is_symlink()
        or loader_path.resolve() != resolved_path
    ):
        return False
    try:
        size = resolved_path.stat().st_size
        if resolved_path not in hash_cache:
            hash_cache[resolved_path] = sha256_file(resolved_path)
        digest = hash_cache[resolved_path]
    except OSError:
        return False
    return (
        is_json_integer(row.get("size_bytes"))
        and row.get("size_bytes") == size
        and row.get("sha256") == digest
        and raw_hashes.get(str(resolved_path)) == digest
    )


def validate_runtime_report(
    report: dict[str, Any],
    manifest: dict[str, Any],
    manifest_path: Path,
    ldd_path: Path,
    resolved_path: Path,
) -> dict[str, bool]:
    runtime_path = Path(str(manifest.get("llama_server_path", ""))).resolve()
    runtime_origin = runtime_path.parent
    raw_hashes = parse_resolved_inventory(resolved_path)
    ldd_rows = parse_ldd_inventory(ldd_path)
    raw_hashes = raw_hashes if isinstance(raw_hashes, dict) else {}
    ldd_rows = ldd_rows if isinstance(ldd_rows, dict) else {}
    dependencies = report.get("dependencies")
    dependencies = dependencies if isinstance(dependencies, list) else []
    binary = report.get("binary")
    binary = binary if isinstance(binary, dict) else {}
    hash_cache: dict[Path, str] = {}
    binary_exact = runtime_object_exact(
        binary,
        {"loader_path", "resolved_path", "sha256", "size_bytes"},
        raw_hashes,
        hash_cache,
    )
    dependency_keys = {"soname", "loader_path", "resolved_path", "sha256", "size_bytes"}
    dependency_rows_strict = bool(dependencies) and all(
        runtime_object_exact(row, dependency_keys, raw_hashes, hash_cache)
        and isinstance(row.get("soname"), str)
        and bool(row["soname"])
        for row in dependencies
        if isinstance(row, dict)
    ) and all(isinstance(row, dict) for row in dependencies)
    dependency_sonames = [row.get("soname") for row in dependencies]
    dependencies_unique = (
        dependency_rows_strict
        and len(set(dependency_sonames)) == len(dependency_sonames)
        and len({row.get("resolved_path") for row in dependencies}) == len(dependencies)
    )
    report_paths = {
        str(binary.get("resolved_path")),
        *(str(row.get("resolved_path")) for row in dependencies),
    }
    raw_inventory_exact = (
        bool(raw_hashes)
        and report_paths == set(raw_hashes)
        and all(raw_hashes[path] == hash_cache.get(Path(path)) for path in raw_hashes)
    )
    ldd_inventory_exact = (
        bool(ldd_rows)
        and dependencies_unique
        and set(ldd_rows) == set(dependency_sonames)
        and all(
            ldd_rows.get(row["soname"]) == row.get("loader_path")
            for row in dependencies
        )
    )
    manifest_origin = manifest.get("origin_shared_objects")
    manifest_origin = manifest_origin if isinstance(manifest_origin, list) else []
    by_soname = {
        row.get("soname"): row for row in dependencies if isinstance(row, dict)
    }
    origin_contracts: list[bool] = []
    for item in manifest_origin:
        if not isinstance(item, dict) or set(item) != {
            "soname",
            "loader_path",
            "resolved_path",
            "size_bytes",
            "sha256",
        }:
            origin_contracts.append(False)
            continue
        soname = item.get("soname")
        report_row = by_soname.get(soname)
        loader_literal = item.get("loader_path")
        resolved_literal = item.get("resolved_path")
        expected_loader = (
            runtime_origin / loader_literal.removeprefix("$ORIGIN/")
            if isinstance(loader_literal, str) and loader_literal.startswith("$ORIGIN/")
            else Path("")
        )
        expected_resolved_loader = (
            runtime_origin / resolved_literal.removeprefix("$ORIGIN/")
            if isinstance(resolved_literal, str)
            and resolved_literal.startswith("$ORIGIN/")
            else Path("")
        )
        origin_contracts.append(
            isinstance(report_row, dict)
            and report_row.get("loader_path") == str(expected_loader)
            and report_row.get("resolved_path") == str(expected_resolved_loader.resolve())
            and is_json_integer(item.get("size_bytes"))
            and report_row.get("size_bytes") == item.get("size_bytes")
            and report_row.get("sha256") == item.get("sha256")
            and expected_loader.resolve() == expected_resolved_loader.resolve()
        )
    origin_sonames_raw = [
        item.get("soname") for item in manifest_origin if isinstance(item, dict)
    ]
    origin_sonames = sorted(
        item for item in origin_sonames_raw if isinstance(item, str)
    )
    expected_loader_policy = {
        "binary_origin": str(runtime_origin),
        "ld_library_path_first": str(runtime_origin),
        "mode": "origin-first",
        "origin_precedence_attested": True,
        "variable": "LD_LIBRARY_PATH",
    }
    core_fields = {
        "report_schema_exact": json_exact(
            report.get("runtime_bundle_schema_version"), 1
        ),
        "report_manifest_path_exact": report.get("runtime_manifest")
        == str(manifest_path.resolve()),
        "report_manifest_hash_exact": report.get("runtime_manifest_sha256")
        == MANIFEST_SHA256,
        "binary_current_exact": binary_exact
        and binary.get("resolved_path") == str(runtime_path)
        and binary.get("sha256") == RUNTIME_SHA256,
        "dependencies_current_exact": dependency_rows_strict and dependencies_unique,
        "dependency_count_recomputed": is_json_integer(report.get("dependency_count"))
        and report.get("dependency_count") == len(dependencies) == len(ldd_rows),
        "raw_resolved_inventory_exact": raw_inventory_exact,
        "raw_ldd_inventory_exact": ldd_inventory_exact,
        "loader_policy_recomputed": report.get("loader_policy")
        == expected_loader_policy,
        "exact_eight_manifest_origin_objects": len(manifest_origin) == 8
        and len(origin_sonames_raw) == len(origin_sonames)
        and len(set(origin_sonames)) == 8
        and len(origin_contracts) == 8
        and all(origin_contracts),
        "origin_count_recomputed": is_json_integer(
            report.get("origin_shared_object_count")
        )
        and report.get("origin_shared_object_count") == 8,
        "origin_sonames_recomputed": report.get("origin_shared_object_sonames")
        == origin_sonames,
    }
    return {
        **core_fields,
        "passed_recomputed": report.get("passed") is all(core_fields.values()),
    }


def validate_runtime(
    manifest_path: Path,
    reference_path: Path,
    final_path: Path,
    manifest_sha256: str,
) -> tuple[dict[str, bool], dict[str, Any]]:
    manifest = load_json(manifest_path, "candidate runtime manifest")
    reference = load_json(reference_path, "runtime reference")
    final = load_json(final_path, "runtime final")
    origin = manifest.get("origin_shared_objects")
    origin = origin if isinstance(origin, list) else []
    sycl = [
        row
        for row in origin
        if isinstance(row, dict) and row.get("soname") == "libggml-sycl.so.0"
    ]
    reference_raw_fields = validate_runtime_report(
        reference,
        manifest,
        manifest_path,
        reference_path.with_suffix(".ldd.txt"),
        reference_path.with_suffix(".resolved.sha256"),
    )
    final_raw_fields = validate_runtime_report(
        final,
        manifest,
        manifest_path,
        final_path.with_suffix(".ldd.txt"),
        final_path.with_suffix(".resolved.sha256"),
    )
    signature_exact = all(
        reference.get(field) == final.get(field) for field in RUNTIME_SIGNATURE_FIELDS
    )
    fields = {
        "manifest_hash_exact": sha256_file(manifest_path)
        == manifest_sha256
        == MANIFEST_SHA256,
        "manifest_server_exact": manifest.get("llama_server_sha256") == RUNTIME_SHA256,
        "manifest_selector_supported": manifest.get("experimental_controls", {})
        .get(CONTROL, {})
        .get("supported")
        is True,
        "manifest_origin_first": manifest.get("runtime_loader_policy")
        == {"mode": "origin-first", "variable": "LD_LIBRARY_PATH"},
        "manifest_sycl_exact": len(sycl) == 1
        and sycl[0].get("sha256") == SYCL_DSO_SHA256,
        "reference_report_recomputed": all(reference_raw_fields.values()),
        "final_report_recomputed": all(final_raw_fields.values()),
        "reference_match_recomputed": reference.get("reference_match") is True,
        "final_reference_match_recomputed": final.get("reference_match")
        is signature_exact,
        "signature_exact": signature_exact,
        "eight_origin_objects": reference.get("origin_shared_object_count") == 8
        and final.get("origin_shared_object_count") == 8,
    }
    return fields, {
        "reference_sha256": sha256_file(reference_path),
        "final_sha256": sha256_file(final_path),
        "reference_raw_fields": reference_raw_fields,
        "final_raw_fields": final_raw_fields,
    }


def attest_lane(args: argparse.Namespace) -> int:
    plan = expected_plan_row(args.wave, args.gpu_index)
    if plan["scenario"] != args.scenario or plan["selector"] != args.selector:
        raise ValueError("lane arguments differ from the frozen crossover map")
    server_attestation_path = args.capture.parent / "server-attestation.json"
    required = (
        args.capture,
        args.server_log,
        args.identity_log,
        args.prerelease_prefix,
        args.postcapture_prefix,
        args.runtime_manifest,
        args.runtime_reference,
        args.runtime_final,
        args.runtime_reference.with_suffix(".ldd.txt"),
        args.runtime_reference.with_suffix(".resolved.sha256"),
        args.runtime_final.with_suffix(".ldd.txt"),
        args.runtime_final.with_suffix(".resolved.sha256"),
        args.phase1_dir / "wave-artifacts.sha256",
        args.phase1_dir / "phase-summary.json",
        args.phase1_dir / "wave-diagnostic-completion-status.json",
        args.oracle,
        server_attestation_path,
    )
    for path in required:
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"lane attestation input is not a regular file: {path}")
    result = load_json(args.capture, "lane capture")
    phase1_fields, phase1_observed, _ = validate_phase1_packet(
        args.phase1_dir,
        args.phase1_manifest_sha256,
        args.phase1_summary_sha256,
        args.phase1_marker_sha256,
        args.selector,
        args.oracle,
        args.oracle_sha256,
    )
    full_log = args.server_log.read_bytes()
    prerelease = args.prerelease_prefix.read_bytes()
    postcapture = args.postcapture_prefix.read_bytes()
    prefix_fields = {
        "prerelease_nonempty_line_boundary": bool(prerelease)
        and prerelease.endswith(b"\n"),
        "postcapture_nonempty_line_boundary": bool(postcapture)
        and postcapture.endswith(b"\n"),
        "prerelease_is_postcapture_prefix": postcapture.startswith(prerelease),
        "postcapture_is_full_log_prefix": full_log.startswith(postcapture),
    }
    route_fields, route_observed = parse_route_markers(
        full_log,
        prerelease,
        postcapture,
        args.selector,
        args.server_pid,
        phase1_observed.get("phase1_flat_marker"),
    )
    expected_header = {
        **SERVER_IDENTITY,
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
        "runtime_manifest_sha256": MANIFEST_SHA256,
        "llama_server_sha256": RUNTIME_SHA256,
        "llama_server": str(
            Path(
                load_json(args.runtime_manifest, "runtime manifest")[
                    "llama_server_path"
                ]
            ).resolve()
        ),
        "runtime_loader_policy": "origin-first",
        "runtime_loader_origin": str(
            Path(
                load_json(args.runtime_manifest, "runtime manifest")[
                    "llama_server_path"
                ]
            )
            .resolve()
            .parent
        ),
        "runtime_loader_origin_precedence": "1",
        "server_pid": args.server_pid,
        "server_output_log": str(args.server_log.resolve()),
        "ctx_size": "65536",
        "parallel_slots": "2",
        "ctx_size_per_slot": "32768",
        "kv_unified": "0",
        "sleep_idle_seconds": "-1",
    }
    identity_fields = exact_header_fields(
        args.identity_log.read_bytes(), expected_header
    )
    runtime_fields, runtime_observed = validate_runtime(
        args.runtime_manifest,
        args.runtime_reference,
        args.runtime_final,
        args.runtime_manifest_sha256,
    )
    source_dir = Path(__file__).resolve().parent
    repo_root = Path(__file__).resolve().parents[3]
    capture_input_paths = {
        "suite": repo_root
        / "experiments/qwen36-27b-q8-gguf-b70/c2-long-context-suite-v1.json",
        "prompt_builder": repo_root / "scripts/bench-openai-long-context-suite.py",
        "common_script": source_dir / "capture-exact-tokens.py",
        "capture_helper": source_dir / "capture-simultaneous-c2.py",
        "matrix_client": source_dir / "capture-c2-token-matrix.py",
        "server_attestation": server_attestation_path,
        "selector_oracle": args.oracle,
        "phase1_manifest": args.phase1_dir / "wave-artifacts.sha256",
        "phase1_summary": args.phase1_dir / "phase-summary.json",
        "phase1_marker": args.phase1_dir / "wave-diagnostic-completion-status.json",
    }
    capture_fields, _ = recompute_capture_provenance(
        result,
        plan,
        args.capture,
        args.prerelease_prefix,
        args.postcapture_prefix,
        server_attestation_path,
        args.server_log,
        args.identity_log,
        capture_input_paths,
        args.server_pid,
        args.port,
        args.oracle_sha256,
        args.phase1_manifest_sha256,
        args.phase1_summary_sha256,
        args.phase1_marker_sha256,
    )
    attestation_input_paths = {
        "capture": args.capture,
        "server_log": args.server_log,
        "identity_log": args.identity_log,
        "prerelease_prefix": args.prerelease_prefix,
        "postcapture_prefix": args.postcapture_prefix,
        "runtime_manifest": args.runtime_manifest,
        "runtime_reference": args.runtime_reference,
        "runtime_final": args.runtime_final,
        "runtime_reference_ldd": args.runtime_reference.with_suffix(".ldd.txt"),
        "runtime_reference_resolved": args.runtime_reference.with_suffix(
            ".resolved.sha256"
        ),
        "runtime_final_ldd": args.runtime_final.with_suffix(".ldd.txt"),
        "runtime_final_resolved": args.runtime_final.with_suffix(
            ".resolved.sha256"
        ),
        "selector_oracle": args.oracle,
        "study_analyzer": Path(__file__).resolve(),
    }
    attestation_inputs = snapshot_inputs(attestation_input_paths)
    input_fields = {
        "attestation_input_inventory_exact": set(attestation_inputs)
        == set(attestation_input_paths),
        "attestation_inputs_nonempty": bool(attestation_inputs),
        "attestation_inputs_current": validate_snapshot_exact(
            attestation_inputs, attestation_input_paths
        ),
    }
    groups = {
        "phase1": phase1_fields,
        "capture": capture_fields,
        "prefixes": prefix_fields,
        "identity": identity_fields,
        "runtime": runtime_fields,
        "routes": route_fields,
        "inputs": input_fields,
    }
    passed = all(all(fields.values()) for fields in groups.values())
    output = {
        "schema_version": SCHEMA_VERSION,
        "phase": "canonical-q8-c2-crossover-lane-attestation",
        "status": "PASS" if passed else "FAIL",
        "passed": passed,
        "evidence_class": "diagnostic-only",
        "performance_promotable": False,
        **plan,
        "server_pid": args.server_pid,
        "port": args.port,
        "fields": {name: all(fields.values()) for name, fields in groups.items()},
        "phase1_fields": phase1_fields,
        "capture_fields": capture_fields,
        "prefix_fields": prefix_fields,
        "identity_fields": identity_fields,
        "runtime_fields": runtime_fields,
        "route_fields": route_fields,
        "input_fields": input_fields,
        "observed": {
            "phase1": phase1_observed,
            "runtime": runtime_observed,
            "routes": route_observed,
        },
        "inputs": attestation_inputs,
    }
    write_json_new(args.out, output)
    return 0 if passed else 1


def landmark(row: dict[str, Any], scenario: str) -> bool:
    comparison = row.get("oracle_comparison")
    comparison = comparison if isinstance(comparison, dict) else {}
    mismatch = comparison.get("first_mismatch")
    mismatch = mismatch if isinstance(mismatch, dict) else {}
    expected = (
        ("q27-q8-c2-04k-b", 1, 71, 332, 71093)
        if scenario == "forward"
        else ("q27-q8-lc-04k-middle", 1, 96, 90, 71093)
    )
    case_id, slot_id, ordinal, observed, oracle = expected
    rows_complete = is_token_list(row.get("token_ids"), TOKEN_COUNT)
    return (
        rows_complete
        and row.get("case_id") == case_id
        and is_json_integer(row.get("slot_id"))
        and row.get("slot_id") == slot_id
        and comparison.get("lcp_tokens") == ordinal - 1
        and mismatch.get("ordinal_one_based") == ordinal
        and mismatch.get("observed_token_id") == observed
        and mismatch.get("oracle_token_id") == oracle
    )


def quality_regression(rows: list[dict[str, Any]]) -> bool:
    natural_boundaries = {
        "q27-q8-c2-04k-b": 70,
        "q27-q8-lc-04k-middle": 95,
    }
    for row in rows:
        comparison = row.get("oracle_comparison")
        comparison = comparison if isinstance(comparison, dict) else {}
        mismatch = comparison.get("first_mismatch")
        if isinstance(mismatch, dict):
            ordinal = mismatch.get("ordinal_one_based")
            boundary = natural_boundaries.get(row.get("case_id"))
            if (
                is_json_integer(ordinal)
                and boundary is not None
                and ordinal <= boundary
            ):
                return True
    return False


def scenario_landmark_reproduced(rows: list[dict[str, Any]], scenario: str) -> bool:
    target_case = EXPECTED_CASES[1] if scenario == "forward" else EXPECTED_CASES[0]
    other_case = EXPECTED_CASES[0] if scenario == "forward" else EXPECTED_CASES[1]
    target = [row for row in rows if row.get("case_id") == target_case]
    other = [row for row in rows if row.get("case_id") == other_case]
    return (
        len(target) == 1
        and len(other) == 1
        and landmark(target[0], scenario)
        and other[0].get("exact_to_oracle") is True
    )


def classify_outcome(
    lanes: list[dict[str, Any]], evidence_valid: bool
) -> dict[str, Any]:
    if not evidence_valid:
        return {
            "classification": "INVALID_EVIDENCE",
            "quality_regression": None,
            "off_landmarks_all": None,
            "on_exact_all": None,
            "on_landmarks_all": None,
        }
    off = [lane for lane in lanes if lane["plan"]["selector"] == 0]
    on = [lane for lane in lanes if lane["plan"]["selector"] == 1]
    off_landmarks = [lane["landmark_reproduced"] for lane in off]
    on_exact = [lane["full_exact"] for lane in on]
    on_landmarks = [lane["landmark_reproduced"] for lane in on]
    regression = any(lane["quality_regression"] for lane in on)
    if all(on_exact):
        classification = (
            "PASS_CAUSAL_CONTROL"
            if all(off_landmarks)
            else "CANDIDATE_EXACT_CAUSAL_INCONCLUSIVE"
        )
    elif all(on_landmarks):
        classification = "NO_EFFECT"
    else:
        classification = "CANDIDATE_INEXACT"
    return {
        "classification": classification,
        "quality_regression": regression,
        "off_landmarks_all": all(off_landmarks),
        "on_exact_all": all(on_exact),
        "on_landmarks_all": all(on_landmarks),
        "replicate_policy": "all-required-no-majority-vote",
    }


def validate_lane_success_state(lane: Path) -> dict[str, bool]:
    status_path = lane / "run-status.txt"
    return {
        "run_status_regular_exact": status_path.is_file()
        and not status_path.is_symlink()
        and status_path.read_bytes() == b"PRE_SEAL_EVIDENCE_VALID\n",
        "failure_artifacts_absent": all(
            not (lane / name).exists()
            for name in (
                "server-identity-unbound.env",
                "passive-drain-before.env",
                "passive-drain-after.env",
                "failure.json",
            )
        ),
    }


def validate_lane_packet(
    lane: Path,
    plan: dict[str, Any],
    oracle_rows: dict[str, dict[str, Any]],
    handoff: dict[str, Any],
) -> tuple[dict[str, bool], dict[str, Any]]:
    lane = lane.resolve()
    marker_path = lane / "diagnostic-completion-status.json"
    manifest_path = lane / "artifacts.sha256"
    capture_path = lane / "capture.json"
    attestation_path = lane / "lane-attestation.json"
    cleanup_path = lane / "cleanup-status.env"
    run_status_path = lane / "run-status.txt"
    server_log_path = lane / "server.stdout.log"
    identity_log_path = lane / "server.identity.log"
    prerelease_path = lane / "prerelease-prefix.log"
    postcapture_path = lane / "postcapture-prefix.log"
    runtime_reference_path = lane / "runtime-reference.json"
    runtime_final_path = lane / "runtime-final.json"
    runtime_reference_ldd_path = lane / "runtime-reference.ldd.txt"
    runtime_reference_resolved_path = lane / "runtime-reference.resolved.sha256"
    runtime_final_ldd_path = lane / "runtime-final.ldd.txt"
    runtime_final_resolved_path = lane / "runtime-final.resolved.sha256"
    server_attestation_path = lane / "server-attestation.json"
    runtime_manifest_path = (
        Path(__file__).resolve().parents[1] / "runtime-manifest-canonical-q8-c2.json"
    )
    for path in (
        marker_path,
        manifest_path,
        capture_path,
        attestation_path,
        cleanup_path,
        run_status_path,
        server_log_path,
        identity_log_path,
        prerelease_path,
        postcapture_path,
        runtime_reference_path,
        runtime_final_path,
        runtime_reference_ldd_path,
        runtime_reference_resolved_path,
        runtime_final_ldd_path,
        runtime_final_resolved_path,
        server_attestation_path,
        runtime_manifest_path,
    ):
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"lane packet input missing: {path}")
    manifest_valid, manifest_sha = parse_manifest(
        lane, "artifacts.sha256", "diagnostic-completion-status.json"
    )
    marker = load_json(marker_path, "lane completion marker")
    capture_value = load_json(capture_path, "lane capture")
    attestation = load_json(attestation_path, "lane attestation")
    expected_cleanup = (
        "status=PASS\n"
        f"wave={plan['wave']}\n"
        f"gpu_index={plan['gpu_index']}\n"
        f"scenario={plan['scenario']}\n"
        f"selector={plan['selector']}\n"
        "graceful_server_teardown=1\n"
        "forced_kill=0\n"
        "cleanup_survivor=0\n"
        "port_closed=1\n"
    ).encode()
    lane_success_fields = validate_lane_success_state(lane)
    rows = capture_value.get("rows")
    rows = rows if isinstance(rows, list) else []
    expected_case_order = (
        list(EXPECTED_CASES)
        if plan["scenario"] == "forward"
        else list(reversed(EXPECTED_CASES))
    )
    derived_rows: list[dict[str, Any]] = []
    for slot_id, row in enumerate(rows):
        row = row if isinstance(row, dict) else {}
        case_id = row.get("case_id")
        oracle_row = oracle_rows.get(case_id, {}) if isinstance(case_id, str) else {}
        tokens = row.get("token_ids")
        content = row.get("content")
        derived_comparison = compare_tokens(tokens, oracle_row.get("token_ids"))
        content_sha = (
            sha256_bytes(content.encode()) if isinstance(content, str) else None
        )
        content_exact = content_sha == oracle_row.get("content_sha256")
        stored_contract_fields, recomputed_stored = validate_stored_row_contract(
            row, oracle_row
        )
        row_fields = {
            "case_slot_exact": slot_id < len(expected_case_order)
            and case_id == expected_case_order[slot_id]
            and is_json_integer(row.get("slot_id"))
            and row.get("slot_id") == slot_id,
            "prompt_exact": row.get("prompt_sha256") == oracle_row.get("prompt_sha256")
            and row.get("rendered_prompt_sha256")
            == oracle_row.get("rendered_prompt_sha256"),
            "tokens_complete_and_hashed": is_token_list(tokens, TOKEN_COUNT)
            and row.get("token_ids_sha256") == token_sha256(tokens),
            "content_hashed": isinstance(content, str)
            and row.get("content_sha256") == content_sha,
            "comparison_recomputed": row.get("oracle_comparison") == derived_comparison,
            "content_comparison_recomputed": row.get("content_exact_to_oracle")
            is content_exact,
            "exact_flag_recomputed": row.get("exact_to_oracle")
            is (derived_comparison["exact"] and content_exact),
            **stored_contract_fields,
        }
        derived_rows.append(
            {
                "case_id": case_id,
                "slot_id": row.get("slot_id"),
                "token_ids": tokens,
                "oracle_comparison": derived_comparison,
                "content_exact_to_oracle": content_exact,
                "exact_to_oracle": derived_comparison["exact"] and content_exact,
                "request_started_perf_s": row.get("request_started_perf_s"),
                "t100_perf_s": recomputed_stored["t100_perf_s"],
                "t512_perf_s": recomputed_stored["t512_perf_s"],
                "fields": row_fields,
                "valid": all(row_fields.values()),
            }
        )
    capture_evidence_fields = capture_value.get("evidence_fields")
    capture_evidence_fields = (
        capture_evidence_fields if isinstance(capture_evidence_fields, dict) else {}
    )
    attestation_maps = (
        "fields",
        "phase1_fields",
        "capture_fields",
        "prefix_fields",
        "identity_fields",
        "runtime_fields",
        "route_fields",
        "input_fields",
    )
    reported_synchronization = capture_value.get("synchronization")
    reported_synchronization = (
        reported_synchronization if isinstance(reported_synchronization, dict) else {}
    )
    recomputed_synchronization = classify_synchronization(
        derived_rows, reported_synchronization.get("barrier_release_perf_s")
    )
    reported_occupancy = capture_value.get("occupancy")
    reported_occupancy = (
        reported_occupancy if isinstance(reported_occupancy, dict) else {}
    )
    recomputed_occupancy = classify_occupancy(
        reported_occupancy.get("metrics_before", {}),
        reported_occupancy.get("metrics_after", {}),
    )
    reported_topology = capture_value.get("slot_topology")
    reported_topology = reported_topology if isinstance(reported_topology, dict) else {}
    reported_slots_before = reported_topology.get("before")
    reported_slots_before = (
        reported_slots_before if isinstance(reported_slots_before, dict) else {}
    )
    reported_slots_after = reported_topology.get("after")
    reported_slots_after = (
        reported_slots_after if isinstance(reported_slots_after, dict) else {}
    )
    recomputed_slots_before = validate_slots(
        reported_slots_before.get("snapshot"), False
    )
    recomputed_slots_after = validate_slots(reported_slots_after.get("snapshot"), True)
    server_pid = attestation.get("server_pid")
    server_pid = server_pid if isinstance(server_pid, str) else ""
    port = attestation.get("port")
    port = port if is_json_integer(port) else -1
    phase1_fields_raw, phase1_observed_raw, _ = validate_phase1_packet(
        handoff["phase1_dir"],
        handoff["phase1_manifest_sha256"],
        handoff["phase1_summary_sha256"],
        handoff["phase1_marker_sha256"],
        plan["selector"],
        handoff["oracle_path"],
        handoff["oracle_sha256"],
    )
    full_log = server_log_path.read_bytes()
    prerelease = prerelease_path.read_bytes()
    postcapture = postcapture_path.read_bytes()
    prefix_fields_raw = {
        "prerelease_nonempty_line_boundary": bool(prerelease)
        and prerelease.endswith(b"\n"),
        "postcapture_nonempty_line_boundary": bool(postcapture)
        and postcapture.endswith(b"\n"),
        "prerelease_is_postcapture_prefix": postcapture.startswith(prerelease),
        "postcapture_is_full_log_prefix": full_log.startswith(postcapture),
    }
    route_fields_raw, route_observed_raw = parse_route_markers(
        full_log,
        prerelease,
        postcapture,
        plan["selector"],
        server_pid,
        handoff["phase1_flat_marker"],
    )
    runtime_manifest = load_json(runtime_manifest_path, "runtime manifest")
    runtime_server_path = Path(runtime_manifest.get("llama_server_path", ""))
    expected_header = {
        **SERVER_IDENTITY,
        "gpu_index": str(plan["gpu_index"]),
        "host": "127.0.0.1",
        "port": str(port),
        "ZE_AFFINITY_MASK": str(plan["gpu_index"]),
        "gpu_lease_path": (
            f"/run/user/{os.getuid()}/qwen36-b70-gpu-leases/gpu{plan['gpu_index']}.lock"
        ),
        "port_lease_path": (
            f"/run/user/{os.getuid()}/qwen36-b70-port-leases/port{port}.lock"
        ),
        CONTROL: str(plan["selector"]),
        "GGML_SYCL_ENABLE_OPT": "1",
        "GGML_SYCL_ENABLE_GRAPH": "0",
        "GGML_SYCL_PRIORITIZE_DMMV": "0",
        "runtime_bundle_verified": "1",
        "runtime_manifest": str(runtime_manifest_path.resolve()),
        "runtime_manifest_sha256": MANIFEST_SHA256,
        "llama_server_sha256": RUNTIME_SHA256,
        "llama_server": str(runtime_server_path.resolve()),
        "runtime_loader_policy": "origin-first",
        "runtime_loader_origin": str(runtime_server_path.resolve().parent),
        "runtime_loader_origin_precedence": "1",
        "server_pid": server_pid,
        "server_output_log": str(server_log_path.resolve()),
        "ctx_size": "65536",
        "parallel_slots": "2",
        "ctx_size_per_slot": "32768",
        "kv_unified": "0",
        "sleep_idle_seconds": "-1",
    }
    identity_fields_raw = exact_header_fields(
        identity_log_path.read_bytes(), expected_header
    )
    runtime_fields_raw, runtime_observed_raw = validate_runtime(
        runtime_manifest_path,
        runtime_reference_path,
        runtime_final_path,
        MANIFEST_SHA256,
    )
    source_dir = Path(__file__).resolve().parent
    repo_root = Path(__file__).resolve().parents[3]
    capture_input_paths = {
        "suite": repo_root
        / "experiments/qwen36-27b-q8-gguf-b70/c2-long-context-suite-v1.json",
        "prompt_builder": repo_root / "scripts/bench-openai-long-context-suite.py",
        "common_script": source_dir / "capture-exact-tokens.py",
        "capture_helper": source_dir / "capture-simultaneous-c2.py",
        "matrix_client": source_dir / "capture-c2-token-matrix.py",
        "server_attestation": server_attestation_path,
        "selector_oracle": handoff["oracle_path"],
        "phase1_manifest": handoff["phase1_dir"] / "wave-artifacts.sha256",
        "phase1_summary": handoff["phase1_dir"] / "phase-summary.json",
        "phase1_marker": handoff["phase1_dir"]
        / "wave-diagnostic-completion-status.json",
    }
    capture_fields_raw, _ = recompute_capture_provenance(
        capture_value,
        plan,
        capture_path,
        prerelease_path,
        postcapture_path,
        server_attestation_path,
        server_log_path,
        identity_log_path,
        capture_input_paths,
        server_pid,
        port,
        handoff["oracle_sha256"],
        handoff["phase1_manifest_sha256"],
        handoff["phase1_summary_sha256"],
        handoff["phase1_marker_sha256"],
    )
    attestation_input_paths = {
        "capture": capture_path,
        "server_log": server_log_path,
        "identity_log": identity_log_path,
        "prerelease_prefix": prerelease_path,
        "postcapture_prefix": postcapture_path,
        "runtime_manifest": runtime_manifest_path,
        "runtime_reference": runtime_reference_path,
        "runtime_final": runtime_final_path,
        "runtime_reference_ldd": runtime_reference_ldd_path,
        "runtime_reference_resolved": runtime_reference_resolved_path,
        "runtime_final_ldd": runtime_final_ldd_path,
        "runtime_final_resolved": runtime_final_resolved_path,
        "selector_oracle": handoff["oracle_path"],
        "study_analyzer": Path(__file__).resolve(),
    }
    input_fields_raw = {
        "attestation_input_inventory_exact": isinstance(attestation.get("inputs"), dict)
        and set(attestation["inputs"]) == set(attestation_input_paths),
        "attestation_inputs_nonempty": isinstance(attestation.get("inputs"), dict)
        and bool(attestation["inputs"]),
        "attestation_inputs_current": validate_snapshot_exact(
            attestation.get("inputs"), attestation_input_paths
        ),
    }
    raw_groups = {
        "phase1": phase1_fields_raw,
        "capture": capture_fields_raw,
        "prefixes": prefix_fields_raw,
        "identity": identity_fields_raw,
        "runtime": runtime_fields_raw,
        "routes": route_fields_raw,
        "inputs": input_fields_raw,
    }
    reported_groups = {
        "phase1": attestation.get("phase1_fields"),
        "capture": attestation.get("capture_fields"),
        "prefixes": attestation.get("prefix_fields"),
        "identity": attestation.get("identity_fields"),
        "runtime": attestation.get("runtime_fields"),
        "routes": attestation.get("route_fields"),
        "inputs": attestation.get("input_fields"),
    }
    raw_observed = {
        "phase1": phase1_observed_raw,
        "runtime": runtime_observed_raw,
        "routes": route_observed_raw,
    }
    fields = {
        "manifest_valid": manifest_valid,
        "marker_valid": marker.get("status") == "EVIDENCE_VALID"
        and marker.get("evidence_valid") is True
        and marker.get("evidence_class") == "diagnostic-only"
        and marker.get("performance_promotable") is False,
        "plan_exact": all(
            json_exact(marker.get(key), value) for key, value in plan.items()
        )
        and all(
            json_exact(capture_value.get(key), value) for key, value in plan.items()
        )
        and all(
            json_exact(attestation.get(key), value) for key, value in plan.items()
        ),
        "hashes_bound": marker.get("artifact_manifest_sha256") == manifest_sha
        and marker.get("capture_sha256") == sha256_file(capture_path)
        and marker.get("attestation_sha256") == sha256_file(attestation_path)
        and marker.get("cleanup_status_sha256") == sha256_file(cleanup_path),
        "capture_evidence_valid": capture_value.get("evidence_valid") is True
        and capture_value.get("status") == "EVIDENCE_VALID"
        and capture_value.get("evidence_class") == "diagnostic-only"
        and capture_value.get("performance_promotable") is False
        and capture_value.get("interpretation_guard")
        == {
            "performance_claim": False,
            "latency_claim": False,
            "fairness_claim": False,
            "timing_use": "synchronization-and-overlap-only",
        }
        and bool(capture_evidence_fields)
        and all(value is True for value in capture_evidence_fields.values()),
        "capture_identity_exact": capture_value.get("run_identity", {}).get(
            "model_sha256"
        )
        == MODEL_SHA256
        and capture_value.get("run_identity", {}).get("runtime_sha256")
        == RUNTIME_SHA256
        and capture_value.get("run_identity", {}).get("runtime_manifest_sha256")
        == MANIFEST_SHA256
        and capture_value.get("run_identity", {}).get("canonical_sycl_dso_sha256")
        == SYCL_DSO_SHA256
        and capture_value.get("run_identity", {}).get("suite_sha256") == SUITE_SHA256
        and capture_value.get("run_identity", {}).get("max_tokens") == TOKEN_COUNT
        and capture_value.get("run_identity", {}).get("kv_unified") is False,
        "capture_rows_recomputed": len(derived_rows) == 2
        and all(row["valid"] for row in derived_rows),
        "capture_synchronization_recomputed": recomputed_synchronization["passed"]
        is True
        and reported_synchronization == recomputed_synchronization,
        "capture_m2_occupancy_recomputed": recomputed_occupancy["passed"] is True
        and reported_occupancy == recomputed_occupancy,
        "capture_slot_topology_recomputed": recomputed_slots_before["passed"] is True
        and recomputed_slots_after["passed"] is True
        and reported_slots_before == recomputed_slots_before
        and reported_slots_after == recomputed_slots_after,
        "capture_input_continuity": capture_fields_raw.get(
            "capture_inputs_before_exact"
        )
        is True
        and capture_fields_raw.get("capture_inputs_after_exact") is True
        and capture_fields_raw.get("capture_inputs_unchanged") is True,
        "attestation_passed": attestation.get("passed") is True
        and attestation.get("status") == "PASS"
        and attestation.get("evidence_class") == "diagnostic-only"
        and attestation.get("performance_promotable") is False
        and all(
            isinstance(attestation.get(name), dict)
            and bool(attestation[name])
            and all(value is True for value in attestation[name].values())
            for name in attestation_maps
        ),
        "attestation_raw_groups_recomputed": reported_groups == raw_groups
        and all(all(group.values()) for group in raw_groups.values())
        and attestation.get("fields")
        == {name: all(group.values()) for name, group in raw_groups.items()},
        "attestation_raw_observed_recomputed": attestation.get("observed")
        == raw_observed,
        "attestation_server_port_pid_bound": is_json_integer(port)
        and 1024 <= port <= 65535
        and re.fullmatch(r"[1-9][0-9]*", server_pid) is not None
        and capture_value.get("server_pid") == server_pid
        and capture_value.get("port") == port
        and marker.get("server_pid") == server_pid,
        "cleanup_exact": cleanup_path.read_bytes() == expected_cleanup,
        "success_state_recomputed": all(lane_success_fields.values()),
        "lifecycle_exact": marker.get("lifecycle")
        == {
            "graceful_server_teardown": True,
            "forced_kill": False,
            "cleanup_survivor": False,
            "port_closed": True,
            "wave_global_health_passed": True,
        },
    }
    landmark_reproduced = scenario_landmark_reproduced(derived_rows, plan["scenario"])
    classification = {
        "plan": plan,
        "path": str(lane),
        "full_exact": len(derived_rows) == 2
        and all(row.get("exact_to_oracle") is True for row in derived_rows),
        "landmark_reproduced": landmark_reproduced,
        "quality_regression": quality_regression(derived_rows),
        "row_comparisons": [
            {
                "case_id": row.get("case_id"),
                "slot_id": row.get("slot_id"),
                "exact_to_oracle": row.get("exact_to_oracle"),
                "oracle_comparison": row.get("oracle_comparison"),
                "content_exact_to_oracle": row.get("content_exact_to_oracle"),
            }
            for row in derived_rows
        ],
    }
    return fields, classification


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


def validate_xpu_evidence(
    wave_dir: Path, evidence_hashes_valid: bool
) -> tuple[bool, dict[str, Any]]:
    used_lines = (
        (wave_dir / "xpu-final-used.tsv").read_text().splitlines()
        if evidence_hashes_valid
        else []
    )
    used_rows: list[tuple[int, int]] = []
    for line in used_lines:
        match = re.fullmatch(r"gpu=([0-3])\tused_mib=([0-9]+)", line)
        if match is not None:
            used_rows.append((int(match.group(1)), int(match.group(2))))
    raw_rows = [
        parse_xpu_stats_file(wave_dir / f"xpu-smi-final-gpu{gpu}.txt")
        for gpu in range(4)
    ]
    passed = (
        evidence_hashes_valid
        and len(used_lines) == 4
        and len(used_rows) == 4
        and [gpu for gpu, _ in used_rows] == [0, 1, 2, 3]
        and all(used <= 256 for _, used in used_rows)
        and raw_rows == used_rows
    )
    return passed, {"used_rows": used_rows, "raw_rows": raw_rows}


def validate_passive_raw_evidence(wave_dir: Path, prefix: str) -> dict[str, bool]:
    try:
        log_paths = sorted(
            path
            for path in wave_dir.rglob("*")
            if path.is_file()
            and not path.is_symlink()
            and path.name.endswith((".log", ".stderr"))
        )
        log_matches = [
            str(path.relative_to(wave_dir))
            for path in log_paths
            if PASSIVE_LOG_ERROR_RE.search(path.read_text(errors="replace"))
        ]
        journal_path = wave_dir / f"{prefix}-kernel-journal.txt"
        journal = journal_path.read_text(errors="replace")
        retained_log_scan = (wave_dir / f"{prefix}-log-error-scan.txt").read_text(
            errors="replace"
        )
        retained_device_scan = (
            wave_dir / f"{prefix}-device-error-scan.txt"
        ).read_text(errors="replace")
    except OSError:
        return {
            "raw_log_inputs_readable": False,
            "raw_logs_no_frozen_error_match": False,
            "retained_log_scan_exact_empty": False,
            "raw_journal_no_frozen_device_match": False,
            "retained_device_scan_exact_empty": False,
        }
    return {
        "raw_log_inputs_readable": bool(log_paths),
        "raw_logs_no_frozen_error_match": not log_matches,
        "retained_log_scan_exact_empty": retained_log_scan == "",
        "raw_journal_no_frozen_device_match": PASSIVE_DEVICE_ERROR_RE.search(journal)
        is None,
        "retained_device_scan_exact_empty": retained_device_scan == "",
    }


def validate_device_discovery(path: Path) -> tuple[dict[str, bool], list[dict[str, Any]]]:
    regular_file = path.is_file() and not path.is_symlink()
    if not regular_file:
        return {
            "regular_nonsymlink_file": False,
            "exact_four_physical_b70": False,
            "ordinals_strict_integers": False,
            "ordinals_exact": False,
            "uuid_values_unique": False,
            "bdf_values_unique": False,
        }, []
    value = load_json(path, "XPU discovery")
    devices = value.get("device_list")
    devices = devices if isinstance(devices, list) else []
    physical = [
        device
        for device in devices
        if isinstance(device, dict)
        and device.get("device_function_type") == "physical"
        and isinstance(device.get("device_name"), str)
        and "Arc(TM) Pro B70" in device["device_name"]
        and is_json_integer(device.get("device_id"))
    ]
    physical.sort(key=lambda device: device.get("device_id", -1))
    retained = [
        {
            "gpu_index": device.get("device_id"),
            "device_name": device.get("device_name"),
            "uuid": device.get("uuid"),
            "pci_bdf_address": device.get("pci_bdf_address"),
        }
        for device in physical
    ]
    fields = {
        "regular_nonsymlink_file": regular_file,
        "exact_four_physical_b70": len(physical) == 4,
        "ordinals_strict_integers": all(
            is_json_integer(device.get("device_id")) for device in physical
        ),
        "ordinals_exact": [device.get("device_id") for device in physical]
        == [0, 1, 2, 3],
        "uuid_values_unique": len(
            {
                device.get("uuid")
                for device in physical
                if isinstance(device.get("uuid"), str) and device.get("uuid")
            }
        )
        == 4,
        "bdf_values_unique": len(
            {
                device.get("pci_bdf_address")
                for device in physical
                if isinstance(device.get("pci_bdf_address"), str)
                and device.get("pci_bdf_address")
            }
        )
        == 4,
    }
    return fields, retained


def validate_wave_launch_map(
    wave_dir: Path, wave: int
) -> tuple[dict[str, bool], list[dict[str, Any]]]:
    path = wave_dir / "wave-launches.tsv"
    rows: list[dict[str, Any]] = []
    shape_valid = path.is_file() and not path.is_symlink()
    lines = path.read_text().splitlines() if shape_valid else []
    pattern = re.compile(
        r"wave=([12])\tgpu=([0-3])\tscenario=(forward|reverse)\tselector=([01])"
        r"\tport=([0-9]+)\tpid=([1-9][0-9]*)\tparent_pid=([1-9][0-9]*)"
        r"\tparent_start_ticks=([1-9][0-9]*)\tstart_ticks=([1-9][0-9]*)"
        r"\tpgid=([1-9][0-9]*)\tsid=([1-9][0-9]*)"
    )
    for line in lines:
        match = pattern.fullmatch(line)
        if match is None:
            shape_valid = False
            continue
        values = match.groups()
        rows.append(
            {
                "wave": int(values[0]),
                "gpu_index": int(values[1]),
                "scenario": values[2],
                "selector": int(values[3]),
                "port": int(values[4]),
                "pid": int(values[5]),
                "parent_pid": int(values[6]),
                "parent_start_ticks": int(values[7]),
                "start_ticks": int(values[8]),
                "pgid": int(values[9]),
                "sid": int(values[10]),
            }
        )
    expected_plan = [dict(row) for row in PLAN if row["wave"] == wave]
    gates_exact = len(rows) == 4
    lane_identity_exact = len(rows) == 4
    for row in rows:
        gpu = row["gpu_index"]
        gate_path = wave_dir / f"gpu{gpu}-session-gate.json"
        plan = next(
            (item for item in expected_plan if item["gpu_index"] == gpu), None
        )
        lane_path = (
            wave_dir
            / f"gpu{gpu}-{row['scenario']}-selector{row['selector']}"
        )
        if not gate_path.is_file() or gate_path.is_symlink():
            gates_exact = False
        else:
            gate = load_json(gate_path, "session transition gate")
            gates_exact = gates_exact and gate == {
                "passed": True,
                "pid": row["pid"],
                "parent_pid": row["parent_pid"],
                "parent_start_ticks": str(row["parent_start_ticks"]),
                "start_ticks": str(row["start_ticks"]),
                "pgid": row["pgid"],
                "sid": row["sid"],
            }
        attestation_path = lane_path / "lane-attestation.json"
        marker_path = lane_path / "diagnostic-completion-status.json"
        if (
            plan is None
            or not attestation_path.is_file()
            or attestation_path.is_symlink()
            or not marker_path.is_file()
            or marker_path.is_symlink()
        ):
            lane_identity_exact = False
        else:
            lane_attestation = load_json(attestation_path, "lane attestation")
            lane_marker = load_json(marker_path, "lane marker")
            lane_identity_exact = lane_identity_exact and all(
                json_exact(lane_attestation.get(key), value)
                for key, value in plan.items()
            )
            lane_identity_exact = (
                lane_identity_exact
                and lane_attestation.get("port") == row["port"]
                and all(
                    json_exact(lane_marker.get(key), value)
                    for key, value in plan.items()
                )
            )
    fields = {
        "tsv_shape_exact": shape_valid and len(lines) == len(rows) == 4,
        "ordered_plan_exact": [
            {key: row[key] for key in ("wave", "gpu_index", "scenario", "selector")}
            for row in rows
        ]
        == expected_plan,
        "ports_exact": [row["port"] for row in rows]
        == [19720, 19721, 19722, 19723],
        "session_identity_positive_unique": len({row["pid"] for row in rows}) == 4
        and len({row["start_ticks"] for row in rows}) == 4
        and len({row["pgid"] for row in rows}) == 4
        and len({row["sid"] for row in rows}) == 4
        and all(row["pid"] == row["pgid"] == row["sid"] for row in rows),
        "single_outer_identity_within_wave": len(
            {(row["parent_pid"], row["parent_start_ticks"]) for row in rows}
        )
        == 1,
        "session_gates_exact": gates_exact,
        "lane_identities_exact": lane_identity_exact,
    }
    return fields, rows


def validate_outer_runner_continuity(
    path: Path, launches: list[dict[str, Any]]
) -> tuple[dict[str, bool], dict[str, Any]]:
    regular_file = path.is_file() and not path.is_symlink()
    match = (
        re.fullmatch(r"pid=([1-9][0-9]*)\nstart_ticks=([1-9][0-9]*)\n", path.read_text())
        if regular_file
        else None
    )
    root_identity = (
        {"pid": int(match.group(1)), "start_ticks": int(match.group(2))}
        if match is not None
        else {}
    )
    parent_identities = {
        (row.get("parent_pid"), row.get("parent_start_ticks")) for row in launches
    }
    child_identities = {
        (row.get("pid"), row.get("start_ticks")) for row in launches
    }
    fields = {
        "root_identity_regular_exact": regular_file and match is not None,
        "exact_eight_launches": len(launches) == 8,
        "single_outer_identity_across_waves": len(launches) == 8
        and len(parent_identities) == 1,
        "root_identity_matches_all_launches": bool(root_identity)
        and parent_identities
        == {(root_identity.get("pid"), root_identity.get("start_ticks"))},
        "eight_distinct_child_identities": len(launches) == 8
        and len(child_identities) == 8,
    }
    return fields, root_identity


def validate_wave_success_state(wave_dir: Path, wave: int) -> dict[str, bool]:
    state_path = wave_dir / "wave-state.env"
    release_path = wave_dir / "release.json"
    status_path = wave_dir / "wave-status.txt"
    regular_inputs = all(
        path.is_file() and not path.is_symlink()
        for path in (state_path, release_path, status_path)
    )
    release: dict[str, Any] = {}
    if regular_inputs:
        try:
            release = load_json(release_path, f"wave {wave} release")
        except ValueError:
            regular_inputs = False
    release_exact = (
        regular_inputs
        and set(release) == {"released", "phase", "wave", "released_utc"}
        and release.get("released") is True
        and release.get("phase") == "canonical-q8-c2-crossover"
        and json_exact(release.get("wave"), wave)
        and isinstance(release.get("released_utc"), str)
        and re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z",
            release["released_utc"],
        )
        is not None
    )
    contradiction_names = (
        "abort",
        "postrelease-failure.env",
        "child-survivor.env",
        "unbound-session-survivors.env",
    )
    contradiction_globs = ("session-transition-failed-*", "failure-drain-*")
    return {
        "success_inputs_regular": regular_inputs,
        "wave_state_release_exact": regular_inputs
        and state_path.read_bytes() == b"state=RELEASE\n",
        "release_marker_exact": release_exact,
        "wave_status_exact": regular_inputs
        and status_path.read_bytes() == b"PRE_SEAL_EVIDENCE_VALID\n",
        "failure_state_artifacts_absent": all(
            not (wave_dir / name).exists() for name in contradiction_names
        )
        and all(not list(wave_dir.glob(pattern)) for pattern in contradiction_globs),
    }


def validate_wave_marker(wave_dir: Path, wave: int) -> dict[str, bool]:
    marker_path = wave_dir / "wave-diagnostic-completion-status.json"
    manifest_path = wave_dir / "wave-artifacts.sha256"
    health_path = wave_dir / "global-health.json"
    cleanup_path = wave_dir / "global-cleanup-status.env"
    state_path = wave_dir / "wave-state.env"
    release_path = wave_dir / "release.json"
    wave_status_path = wave_dir / "wave-status.txt"
    if not all(
        path.is_file() and not path.is_symlink()
        for path in (
            marker_path,
            manifest_path,
            health_path,
            cleanup_path,
            state_path,
            release_path,
            wave_status_path,
        )
    ):
        return {"required_files": False}
    valid_manifest, manifest_sha = parse_manifest(
        wave_dir, "wave-artifacts.sha256", "wave-diagnostic-completion-status.json"
    )
    marker = load_json(marker_path, f"wave {wave} marker")
    health = load_json(health_path, f"wave {wave} health")
    success_state_fields = validate_wave_success_state(wave_dir, wave)
    health_evidence_path = wave_dir / "global-health-evidence.sha256"
    expected_health_paths = {"postwave-group-members-before-reap.txt"}
    for prefix in ("preprobe", "postprobe"):
        expected_health_paths.update(
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
    expected_health_paths.update(
        {f"xpu-smi-final-gpu{gpu}.txt" for gpu in range(4)}
        | {"xpu-final-used.tsv", "global-cleanup-status.env"}
    )
    health_rows: dict[str, str] = {}
    health_order: list[str] = []
    health_manifest_shape = (
        health_evidence_path.is_file() and not health_evidence_path.is_symlink()
    )
    if health_manifest_shape:
        for line in health_evidence_path.read_text().splitlines():
            match = re.fullmatch(r"([0-9a-f]{64})  \./([^/]+)", line)
            if match is None or match.group(2) in health_rows:
                health_manifest_shape = False
                continue
            health_rows[match.group(2)] = match.group(1)
            health_order.append(match.group(2))
    health_inventory = (
        health_manifest_shape
        and set(health_rows) == expected_health_paths
        and health_order == sorted(health_order)
    )
    health_hashes = health_inventory and all(
        (wave_dir / name).is_file()
        and not (wave_dir / name).is_symlink()
        and sha256_file(wave_dir / name) == digest
        for name, digest in health_rows.items()
    )
    empty_paths = {"postwave-group-members-before-reap.txt"}
    for prefix in ("preprobe", "postprobe"):
        empty_paths.update(
            {
                f"{prefix}-group-members.txt",
                f"{prefix}-lane-listeners.txt",
                f"{prefix}-processes.txt",
                f"{prefix}-log-error-scan.txt",
                f"{prefix}-device-error-scan.txt",
            }
        )
    negative_evidence_empty = health_hashes and all(
        (wave_dir / name).stat().st_size == 0 for name in empty_paths
    )
    passive_status_exact = health_hashes and all(
        (wave_dir / f"{prefix}-passive-status.env").read_text()
        == "passive_fault_detected=0\n"
        for prefix in ("preprobe", "postprobe")
    )
    xpu_exact, _ = validate_xpu_evidence(wave_dir, health_hashes)
    passive_raw = {
        prefix: validate_passive_raw_evidence(wave_dir, prefix)
        for prefix in ("preprobe", "postprobe")
    }
    expected_cleanup = (
        "status=PASS\nall_groups_stopped=1\nall_listeners_closed=1\n"
        "passive_fault_detected=0\nfinal_xpu_probes_performed=1\n"
        "all_cards_idle=1\nforced_kill=0\ncleanup_survivor=0\n"
    ).encode()
    return {
        "required_files": True,
        "manifest_valid": valid_manifest,
        "marker_valid": marker.get("status") == "EVIDENCE_VALID"
        and marker.get("evidence_valid") is True
        and json_exact(marker.get("wave"), wave)
        and marker.get("artifact_manifest_sha256") == manifest_sha,
        "health_valid": health.get("passed") is True
        and json_exact(health.get("wave"), wave)
        and health.get("all_groups_stopped") is True
        and health.get("all_listeners_closed") is True
        and health.get("passive_fault_detected") is False
        and health.get("all_cards_idle") is True
        and health.get("forced_kill") is False
        and health.get("cleanup_survivor") is False,
        "health_evidence_bound": health.get("evidence_manifest")
        == "global-health-evidence.sha256"
        and health_evidence_path.is_file()
        and health.get("evidence_manifest_sha256") == sha256_file(health_evidence_path),
        "health_evidence_inventory": health_inventory,
        "health_evidence_hashes": health_hashes,
        "health_negative_evidence_empty": negative_evidence_empty,
        "health_passive_status_exact": passive_status_exact,
        "health_xpu_idle_exact": xpu_exact,
        "health_raw_passive_evidence_recomputed": all(
            all(fields.values()) for fields in passive_raw.values()
        ),
        "cleanup_exact": cleanup_path.read_bytes() == expected_cleanup,
        "success_state_recomputed": all(success_state_fields.values()),
    }


def aggregate(args: argparse.Namespace) -> int:
    if len(args.lane) != 8:
        raise ValueError("aggregate requires exactly eight --lane paths")
    wave1_dir = args.wave1_dir.resolve()
    wave2_dir = args.wave2_dir.resolve()
    run_root = args.run_root.resolve()
    wave_dirs = {1: wave1_dir, 2: wave2_dir}
    phase1_fields, phase1_observed, _ = validate_phase1_packet(
        args.phase1_dir,
        args.phase1_manifest_sha256,
        args.phase1_summary_sha256,
        args.phase1_marker_sha256,
        0,
        args.selector0_oracle,
        args.selector0_oracle_sha256,
    )
    phase1_on_fields, _, _ = validate_phase1_packet(
        args.phase1_dir,
        args.phase1_manifest_sha256,
        args.phase1_summary_sha256,
        args.phase1_marker_sha256,
        1,
        args.selector1_oracle,
        args.selector1_oracle_sha256,
    )
    selector0_value = load_json(args.selector0_oracle, "selector-0 Phase-1 oracle")
    selector1_value = load_json(args.selector1_oracle, "selector-1 Phase-1 oracle")
    selector0_fields, selector0_rows = validate_oracle(
        selector0_value, SUITE_SHA256, args.selector0_oracle_sha256, 0
    )
    selector1_fields, selector1_rows = validate_oracle(
        selector1_value, SUITE_SHA256, args.selector1_oracle_sha256, 1
    )
    lane_packets: list[dict[str, Any]] = []
    lane_evidence: list[dict[str, bool]] = []
    lane_paths_bound = True
    for plan, lane in zip(PLAN, args.lane):
        expected_name = (
            f"gpu{plan['gpu_index']}-{plan['scenario']}-selector{plan['selector']}"
        )
        resolved_lane = lane.resolve()
        lane_paths_bound = lane_paths_bound and (
            resolved_lane.parent == wave_dirs[plan["wave"]]
            and resolved_lane.name == expected_name
            and resolved_lane.is_dir()
            and not lane.is_symlink()
        )
        oracle_rows = selector0_rows if plan["selector"] == 0 else selector1_rows
        oracle_path = (
            args.selector0_oracle if plan["selector"] == 0 else args.selector1_oracle
        )
        oracle_sha = (
            args.selector0_oracle_sha256
            if plan["selector"] == 0
            else args.selector1_oracle_sha256
        )
        fields, classification = validate_lane_packet(
            resolved_lane,
            dict(plan),
            oracle_rows,
            {
                "phase1_dir": args.phase1_dir,
                "phase1_manifest_sha256": args.phase1_manifest_sha256,
                "phase1_summary_sha256": args.phase1_summary_sha256,
                "phase1_marker_sha256": args.phase1_marker_sha256,
                "phase1_flat_marker": phase1_observed.get("phase1_flat_marker"),
                "oracle_path": oracle_path,
                "oracle_sha256": oracle_sha,
            },
        )
        lane_evidence.append(fields)
        lane_packets.append(classification)
    wave_fields = {
        "wave1": validate_wave_marker(wave1_dir, 1),
        "wave2": validate_wave_marker(wave2_dir, 2),
    }
    mapping_exact = [lane["plan"] for lane in lane_packets] == list(PLAN)
    discovery_fields, device_map = validate_device_discovery(
        run_root / "xpu-smi-discovery.json"
    )
    launch_fields = {}
    launch_maps = {}
    for wave, wave_dir in wave_dirs.items():
        wave_launch_fields, wave_launch_map = validate_wave_launch_map(wave_dir, wave)
        launch_fields[f"wave{wave}"] = wave_launch_fields
        launch_maps[f"wave{wave}"] = wave_launch_map
    observed_by_wave_gpu = {
        (row["wave"], row["gpu_index"]): row
        for rows in launch_maps.values()
        for row in rows
    }
    all_launches = [row for rows in launch_maps.values() for row in rows]
    outer_identity_fields, outer_identity = validate_outer_runner_continuity(
        run_root / "outer-runner-identity.env", all_launches
    )
    same_card_flip = len(observed_by_wave_gpu) == 8 and len(device_map) == 4 and all(
        observed_by_wave_gpu[(1, gpu)]["selector"]
        != observed_by_wave_gpu[(2, gpu)]["selector"]
        and observed_by_wave_gpu[(1, gpu)]["scenario"]
        == observed_by_wave_gpu[(2, gpu)]["scenario"]
        and device_map[gpu]["gpu_index"] == gpu
        for gpu in range(4)
    )
    evidence_fields = {
        "phase1_selector0": all(phase1_fields.values()),
        "phase1_selector1": all(phase1_on_fields.values()),
        "selector0_oracle": all(selector0_fields.values()),
        "selector1_oracle": all(selector1_fields.values()),
        "eight_lanes": len(lane_packets) == 8
        and all(all(fields.values()) for fields in lane_evidence),
        "wave1_global_health": all(wave_fields["wave1"].values()),
        "wave2_global_health": all(wave_fields["wave2"].values()),
        "mapping_exact": mapping_exact,
        "lane_paths_bound_to_matching_waves": lane_paths_bound,
        "wave_paths_sibling_exact": wave1_dir.name == "wave1"
        and wave2_dir.name == "wave2"
        and wave1_dir.parent == wave2_dir.parent == run_root,
        "physical_device_discovery_exact": all(discovery_fields.values()),
        "observed_wave_launch_maps_exact": all(
            all(fields.values()) for fields in launch_fields.values()
        ),
        "outer_runner_continuity_exact": all(outer_identity_fields.values()),
        "same_card_selector_flip": same_card_flip,
    }
    evidence_valid = all(evidence_fields.values())
    outcome = classify_outcome(lane_packets, evidence_valid)
    result = {
        "schema_version": SCHEMA_VERSION,
        "phase": "canonical-q8-c2-two-wave-selector-crossover",
        "status": "EVIDENCE_VALID" if evidence_valid else "INVALID_EVIDENCE",
        "evidence_valid": evidence_valid,
        "evidence_class": "diagnostic-only"
        if evidence_valid
        else "diagnostic-only-failure",
        "performance_promotable": False,
        "scientific_outcome": outcome,
        "interpretation_guard": {
            "performance_claim": False,
            "latency_claim": False,
            "fairness_claim": False,
            "natural_stop_claim": False,
            "isolated_subpath_causality_claim": False,
            "combined_control_scope": "forced-512 heterogeneous c2 only",
        },
        "identity": {
            "model_sha256": MODEL_SHA256,
            "runtime_sha256": RUNTIME_SHA256,
            "runtime_manifest_sha256": MANIFEST_SHA256,
            "canonical_sycl_dso_sha256": SYCL_DSO_SHA256,
            "suite_sha256": SUITE_SHA256,
            "phase1_manifest_sha256": args.phase1_manifest_sha256,
            "phase1_summary_sha256": args.phase1_summary_sha256,
            "phase1_marker_sha256": args.phase1_marker_sha256,
            "selector0_oracle_sha256": args.selector0_oracle_sha256,
            "selector1_oracle_sha256": args.selector1_oracle_sha256,
        },
        "plan": list(PLAN),
        "physical_device_map": device_map,
        "observed_wave_launch_maps": launch_maps,
        "outer_runner_identity": outer_identity,
        "outer_runner_identity_fields": outer_identity_fields,
        "physical_device_fields": discovery_fields,
        "wave_launch_fields": launch_fields,
        "evidence_fields": evidence_fields,
        "phase1_fields": {"selector0": phase1_fields, "selector1": phase1_on_fields},
        "phase1_observed": phase1_observed,
        "wave_fields": wave_fields,
        "lane_evidence_fields": lane_evidence,
        "lanes": lane_packets,
    }
    write_json_new(args.out, result)
    return 0 if evidence_valid else 1


def attest_phase1(args: argparse.Namespace) -> int:
    groups: dict[str, dict[str, bool]] = {}
    observed: dict[str, Any] = {}
    for selector, oracle, oracle_sha256 in (
        (0, args.selector0_oracle, args.selector0_oracle_sha256),
        (1, args.selector1_oracle, args.selector1_oracle_sha256),
    ):
        fields, details, _ = validate_phase1_packet(
            args.phase1_dir,
            args.phase1_manifest_sha256,
            args.phase1_summary_sha256,
            args.phase1_marker_sha256,
            selector,
            oracle,
            oracle_sha256,
        )
        groups[str(selector)] = fields
        observed[str(selector)] = details
    passed = all(all(fields.values()) for fields in groups.values())
    result = {
        "schema_version": SCHEMA_VERSION,
        "phase": "canonical-q8-c2-crossover-phase1-handoff",
        "status": "PASS" if passed else "FAIL",
        "passed": passed,
        "evidence_class": "diagnostic-only",
        "performance_promotable": False,
        "fields": groups,
        "observed": observed,
    }
    write_json_new(args.out, result)
    return 0 if passed else 1


def print_plan(args: argparse.Namespace) -> int:
    if args.port_base < 1024 or args.port_base > 65532:
        raise ValueError("port base must leave four valid ports")
    for row in PLAN:
        print(
            f"wave={row['wave']}\tgpu={row['gpu_index']}\tscenario={row['scenario']}\t"
            f"selector={row['selector']}\tport={args.port_base + row['gpu_index']}\t"
            f"oracle=selector{row['selector']}\tforced_tokens=512\tserver_sleep=disabled"
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("print-plan")
    plan.add_argument("--port-base", type=int, default=19720)
    plan.set_defaults(function=print_plan)

    phase1 = sub.add_parser("attest-phase1")
    phase1.add_argument("--phase1-dir", type=Path, required=True)
    phase1.add_argument("--phase1-manifest-sha256", required=True)
    phase1.add_argument("--phase1-summary-sha256", required=True)
    phase1.add_argument("--phase1-marker-sha256", required=True)
    phase1.add_argument("--selector0-oracle", type=Path, required=True)
    phase1.add_argument("--selector0-oracle-sha256", required=True)
    phase1.add_argument("--selector1-oracle", type=Path, required=True)
    phase1.add_argument("--selector1-oracle-sha256", required=True)
    phase1.add_argument("--out", type=Path, required=True)
    phase1.set_defaults(function=attest_phase1)

    capture_parser = sub.add_parser("capture")
    capture_parser.add_argument("--wave", type=int, required=True)
    capture_parser.add_argument("--gpu-index", type=int, required=True)
    capture_parser.add_argument(
        "--scenario", choices=("forward", "reverse"), required=True
    )
    capture_parser.add_argument("--selector", type=int, choices=(0, 1), required=True)
    capture_parser.add_argument("--base-url", required=True)
    capture_parser.add_argument("--suite", type=Path, required=True)
    capture_parser.add_argument("--suite-sha256", required=True)
    capture_parser.add_argument("--prompt-builder", type=Path, required=True)
    capture_parser.add_argument("--common-script", type=Path, required=True)
    capture_parser.add_argument("--capture-helper", type=Path, required=True)
    capture_parser.add_argument("--capture-helper-sha256", required=True)
    capture_parser.add_argument("--matrix-client", type=Path, required=True)
    capture_parser.add_argument("--matrix-client-sha256", required=True)
    capture_parser.add_argument("--server-attestation", type=Path, required=True)
    capture_parser.add_argument("--server-attestation-sha256", required=True)
    capture_parser.add_argument("--phase1-dir", type=Path, required=True)
    capture_parser.add_argument("--phase1-manifest-sha256", required=True)
    capture_parser.add_argument("--phase1-summary-sha256", required=True)
    capture_parser.add_argument("--phase1-marker-sha256", required=True)
    capture_parser.add_argument("--oracle", type=Path, required=True)
    capture_parser.add_argument("--oracle-sha256", required=True)
    capture_parser.add_argument("--model-sha256", required=True)
    capture_parser.add_argument("--runtime-sha256", required=True)
    capture_parser.add_argument("--server-pid", type=int, required=True)
    capture_parser.add_argument("--timeout", type=int, default=1800)
    capture_parser.add_argument("--out", type=Path, required=True)
    capture_parser.set_defaults(function=capture)

    lane = sub.add_parser("attest-lane")
    lane.add_argument("--wave", type=int, required=True)
    lane.add_argument("--gpu-index", type=int, required=True)
    lane.add_argument("--scenario", choices=("forward", "reverse"), required=True)
    lane.add_argument("--selector", type=int, choices=(0, 1), required=True)
    lane.add_argument("--port", type=int, required=True)
    lane.add_argument("--server-pid", required=True)
    lane.add_argument("--capture", type=Path, required=True)
    lane.add_argument("--server-log", type=Path, required=True)
    lane.add_argument("--identity-log", type=Path, required=True)
    lane.add_argument("--prerelease-prefix", type=Path, required=True)
    lane.add_argument("--postcapture-prefix", type=Path, required=True)
    lane.add_argument("--runtime-manifest", type=Path, required=True)
    lane.add_argument("--runtime-manifest-sha256", required=True)
    lane.add_argument("--runtime-reference", type=Path, required=True)
    lane.add_argument("--runtime-final", type=Path, required=True)
    lane.add_argument("--phase1-dir", type=Path, required=True)
    lane.add_argument("--phase1-manifest-sha256", required=True)
    lane.add_argument("--phase1-summary-sha256", required=True)
    lane.add_argument("--phase1-marker-sha256", required=True)
    lane.add_argument("--oracle", type=Path, required=True)
    lane.add_argument("--oracle-sha256", required=True)
    lane.add_argument("--out", type=Path, required=True)
    lane.set_defaults(function=attest_lane)

    aggregate_parser = sub.add_parser("aggregate")
    aggregate_parser.add_argument("--lane", action="append", type=Path, required=True)
    aggregate_parser.add_argument("--run-root", type=Path, required=True)
    aggregate_parser.add_argument("--wave1-dir", type=Path, required=True)
    aggregate_parser.add_argument("--wave2-dir", type=Path, required=True)
    aggregate_parser.add_argument("--phase1-dir", type=Path, required=True)
    aggregate_parser.add_argument("--phase1-manifest-sha256", required=True)
    aggregate_parser.add_argument("--phase1-summary-sha256", required=True)
    aggregate_parser.add_argument("--phase1-marker-sha256", required=True)
    aggregate_parser.add_argument("--selector0-oracle", type=Path, required=True)
    aggregate_parser.add_argument("--selector0-oracle-sha256", required=True)
    aggregate_parser.add_argument("--selector1-oracle", type=Path, required=True)
    aggregate_parser.add_argument("--selector1-oracle-sha256", required=True)
    aggregate_parser.add_argument("--out", type=Path, required=True)
    aggregate_parser.set_defaults(function=aggregate)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    for name, value in vars(args).items():
        if name.endswith("sha256") and value is not None and not is_sha256(value):
            parser.error(f"--{name.replace('_', '-')} must be a lowercase SHA-256")
    return args.function(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError) as exc:
        if _FAILURE_OUTPUT is not None and not _FAILURE_OUTPUT.exists():
            try:
                write_json_new(
                    _FAILURE_OUTPUT,
                    {
                        "schema_version": SCHEMA_VERSION,
                        "phase": "canonical-q8-c2-crossover-lane-capture",
                        "status": "INVALID_EVIDENCE",
                        "evidence_valid": False,
                        "evidence_class": "diagnostic-only-failure",
                        "performance_promotable": False,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    },
                )
            except (OSError, ValueError):
                pass
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
