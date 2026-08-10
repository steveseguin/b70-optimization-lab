#!/usr/bin/env python3
"""Offline-only hard gates for four independent embedded-MTP services."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
import sys
import tempfile
from pathlib import Path
from typing import Any


MODEL_SHA256 = "9408dcb356cc061a05c139e5647cbde0698ff980c6a69f7fc214e9989f86cfa8"
RUNTIME_SHA256 = "1a093f09122ceb2851157042c2bbc6281ddb9d4e2de50137502890f9b52fa7d7"
MODEL_PATH = "/mnt/usb-models/models/qwen36-27b-mtp-q8-gguf/Qwen3.6-27B-Q8_0.gguf"
RUNTIME_PATH = "/mnt/fast-ai/runtime/llama.cpp-15586e2d-qwen27-vdr2-hybrid/llama-server"
SUITE_SHA256 = "df03f49d36c36d2b8ac4cd117b7cb2e42c74878af1f6926690ebb89eeccd47ac"
ISOLATED_CANDIDATE_SHA256 = "0ce2399561568c4d80d112f42457fc31acedbddac576f1900e64ba88ee1352e7"
MATCHED_CONTROL_FORENSIC_SHA256 = "8af30d579a30aedf3cadaa8f0728d883acc7d0da188bd2b30125b472f37a2ad2"
SEALED_MTP3_GATE_SHA256 = "95dad265e308c2a1787d81c7a874eb2a2a2cab7ce513a7d6e9ec02fa448987d6"
SUPPLEMENT_COMPARISON_SHA256 = "41d754812311ad657f7f59b7f51794e7b394a82096587123280fdf76dc510ae3"
SUPPLEMENT_COMPLETION_SHA256 = "3eaf8d2c72bc64e2440e42486ca69b3605d357cc6e782aae79fd21c059e03c7f"
SUPPLEMENT_IDENTITY_SHA256 = "d966b5d2996cee86faba0ef95b68afdabfcd95fb25d97078319680b8b922ae49"
CAPTURE_SCHEMA = "qwen36-embedded-mtp-four-service-realistic-capture-v1"
CONFIG_SCHEMA = "qwen36-embedded-mtp-four-service-config-v1"
PROMPT_IDS = (
    "incident-retrospective",
    "code-review",
    "customer-email",
    "sql-debugging",
    "release-plan",
    "benchmark-analysis",
    "architecture-tradeoff",
    "bug-report-synthesis",
    "technical-guide",
    "risk-register",
    "performance-hypotheses",
    "decision-memo",
)
SERVICE_COUNT = 4
WAVE_COUNT = 3
AGGREGATE_RETENTION_FLOOR = 0.95
SERVICE_RETENTION_FLOOR = 0.90
SERVICE_FAIRNESS_FLOOR = 0.90
PROMPT_D99_RETENTION_FLOOR = 0.80
MIN_WAVE_OVERLAP_S = 1.0
MIN_LOADED_DELTA_MIB = 29000
MAX_LOADED_MIB = 31500
MAX_IDLE_MIB = 256
PRIOR_TARGET_ONLY_FOUR_SERVICE_RETENTION = 0.997617


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"JSON root is not an object: {path}")
    return value


def atomic_write(path: Path, value: Any) -> None:
    if path.exists():
        raise ValueError(f"refusing to overwrite gate output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False) as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")
        temporary = Path(stream.name)
    temporary.replace(path)


def finite_positive(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value > 0
    )


def nonnegative_int_at_most(value: Any, maximum: int) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and 0 <= value <= maximum
    )


def argv_values(argv: list[str], option: str) -> list[str]:
    return [
        argv[index + 1]
        for index in range(len(argv) - 1)
        if argv[index] == option
    ]


def row_rates(row: dict[str, Any]) -> tuple[float, float]:
    positions = row.get("stream_complete_positions")
    offsets = row.get("token_id_offsets_s")
    completion = row.get("completion_tokens")
    if (
        not isinstance(completion, int)
        or isinstance(completion, bool)
        or completion < 100
        or not isinstance(positions, list)
        or not isinstance(offsets, list)
        or len(positions) != len(offsets)
    ):
        raise ValueError("row cannot support D99/full interval accounting")
    by_position = dict(zip(positions, offsets))
    if 0 not in by_position or 99 not in by_position or completion - 1 not in by_position:
        raise ValueError("row is missing required interval endpoints")
    d99_duration = by_position[99] - by_position[0]
    full_duration = by_position[completion - 1] - by_position[0]
    if not finite_positive(d99_duration) or not finite_positive(full_duration):
        raise ValueError("row interval duration is not positive and finite")
    return 99 / d99_duration, (completion - 1) / full_duration


def median(values: list[float]) -> float:
    if not values or not all(finite_positive(value) for value in values):
        raise ValueError("cannot calculate a positive median")
    return float(statistics.median(values))


def load_suite(path: Path) -> tuple[list[str], list[str]]:
    if sha256_file(path) != SUITE_SHA256:
        raise ValueError("fixed realistic suite SHA-256 mismatch")
    suite = read_object(path)
    prompts = suite.get("prompts")
    if not isinstance(prompts, list) or len(prompts) != len(PROMPT_IDS):
        raise ValueError("fixed realistic suite schema mismatch")
    ids: list[str] = []
    hashes: list[str] = []
    for item in prompts:
        if not isinstance(item, dict) or not isinstance(item.get("prompt"), str):
            raise ValueError("fixed realistic suite prompt is malformed")
        ids.append(item.get("id"))
        hashes.append(sha256_text(item["prompt"]))
    if tuple(ids) != PROMPT_IDS:
        raise ValueError("fixed realistic prompt order mismatch")
    return ids, hashes


def validate_reference(
    args: argparse.Namespace,
) -> tuple[
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, dict[str, float]],
    dict[str, Any],
]:
    expected_hashes = {
        args.isolated_candidate: ISOLATED_CANDIDATE_SHA256,
        args.matched_control_forensic: MATCHED_CONTROL_FORENSIC_SHA256,
        args.sealed_mtp3_gate: SEALED_MTP3_GATE_SHA256,
        args.supplement_comparison: SUPPLEMENT_COMPARISON_SHA256,
        args.supplement_completion: SUPPLEMENT_COMPLETION_SHA256,
        args.supplement_identity: SUPPLEMENT_IDENTITY_SHA256,
    }
    observed_hashes = {str(path.resolve()): sha256_file(path) for path in expected_hashes}
    if any(sha256_file(path) != expected for path, expected in expected_hashes.items()):
        raise ValueError("sealed matched-control reference SHA-256 mismatch")
    isolated = read_object(args.isolated_candidate)
    control = read_object(args.matched_control_forensic)
    sealed_gate = read_object(args.sealed_mtp3_gate)
    comparison = read_object(args.supplement_comparison)
    completion = read_object(args.supplement_completion)
    identity = read_object(args.supplement_identity)
    reference_checks = {
        "isolated_suite": (isolated.get("run_identity") or {}).get("suite_sha256")
        == SUITE_SHA256,
        "isolated_once_only": (isolated.get("run_identity") or {}).get(
            "generation_requests_per_prompt"
        )
        == 1
        and (isolated.get("run_identity") or {}).get("replay_requests") == 0,
        "isolated_gate": (isolated.get("realistic_final_gate") or {}).get("passed")
        is True,
        "sealed_gate_passed": sealed_gate.get("passed") is True
        and sealed_gate.get("mode") == "mtp3",
        "sealed_gate_core_identity": sealed_gate.get("model_sha256")
        == MODEL_SHA256
        and sealed_gate.get("runtime_sha256") == RUNTIME_SHA256
        and sealed_gate.get("suite_sha256") == SUITE_SHA256
        and all(
            (sealed_gate.get("checks") or {}).get(key) is True
            for key in (
                "scored_gate_identity_log_binding",
                "scored_gate_passed",
                "server_identity_mode",
                "server_model_sha256",
                "server_runtime_sha256",
                "fresh_once",
                "one_scored_request_per_prompt",
            )
        ),
        "sealed_gate_candidate_bound": sealed_gate.get("input_sha256")
        == ISOLATED_CANDIDATE_SHA256,
        "sealed_gate_control_bound": (
            sealed_gate.get("control_checks") or {}
        ).get("observed_control_forensic_sha256")
        == MATCHED_CONTROL_FORENSIC_SHA256,
        "sealed_gate_full_exact": all(
            (sealed_gate.get("control_checks") or {}).get(key) is True
            for key in (
                "full_candidate_control_token_ids_exact",
                "full_candidate_control_content_exact",
                "full_candidate_control_exact",
            )
        ),
        "supplement_pass": comparison.get("classification")
        == "PASS_REALISTIC_MTP_WIN"
        and comparison.get("quality_reference") == "matched_fresh_control_v1"
        and comparison.get("evidence_passed") is True
        and comparison.get("performance_passed") is True
        and comparison.get("realistic_policy_passed") is True,
        "supplement_completion": completion.get("status")
        == "PASS_REALISTIC_MTP_WIN"
        and completion.get("evidence_valid") is True
        and completion.get("comparison_sha256") == SUPPLEMENT_COMPARISON_SHA256
        and completion.get("supplemental_identity_sha256")
        == SUPPLEMENT_IDENTITY_SHA256,
        "supplement_identity": identity.get("source_run_manifest_verified") is True
        and identity.get("source_run_unchanged") is True
        and identity.get("candidate_control_full_token_content_exact") is True
        and identity.get("quality_reference") == "matched_fresh_control_v1",
    }
    if not all(reference_checks.values()):
        raise ValueError(f"sealed matched-control reference invalid: {reference_checks}")

    isolated_rows = isolated.get("rows")
    control_rows = control.get("rows")
    if not isinstance(isolated_rows, list) or not isinstance(control_rows, list):
        raise ValueError("sealed reference rows are missing")
    isolated_by_id = {row.get("prompt_id"): row for row in isolated_rows if isinstance(row, dict)}
    control_by_id = {row.get("prompt_id"): row for row in control_rows if isinstance(row, dict)}
    if tuple(isolated_by_id) != PROMPT_IDS or tuple(control_by_id) != PROMPT_IDS:
        raise ValueError("sealed reference prompt order mismatch")
    rates: dict[str, dict[str, float]] = {}
    for prompt_id in PROMPT_IDS:
        retained = isolated_by_id[prompt_id]
        d99, full = row_rates(retained)
        rates[prompt_id] = {"d99": d99, "full": full}
        oracle = control_by_id[prompt_id]
        retained_positions = retained.get("stream_complete_positions")
        retained_tokens = retained.get("token_ids")
        retained_usage = retained.get("usage") or {}
        retained_timings = retained.get("timings") or {}
        oracle_usage = oracle.get("usage") or {}
        oracle_timings = oracle.get("timings") or {}
        if (
            not isinstance(oracle.get("token_ids"), list)
            or not isinstance(oracle.get("token_count"), int)
            or isinstance(oracle.get("token_count"), bool)
            or not 100 <= oracle["token_count"] <= 512
            or oracle.get("token_count") != len(oracle["token_ids"])
            or not all(
                isinstance(token, int)
                and not isinstance(token, bool)
                and token >= 0
                for token in oracle["token_ids"]
            )
            or not isinstance(oracle.get("content"), str)
            or sha256_text(oracle["content"]) != oracle.get("content_sha256")
            or not isinstance(retained_positions, list)
            or not isinstance(retained_tokens, list)
            or len(retained_positions) != len(retained_tokens)
            or retained_positions != sorted(set(retained_positions))
            or not all(
                isinstance(position, int)
                and not isinstance(position, bool)
                and 0 <= position < oracle["token_count"]
                for position in retained_positions
            )
            or retained.get("completion_tokens") != oracle["token_count"]
            or retained.get("rendered_prompt_sha256")
            != oracle.get("rendered_prompt_sha256")
            or not isinstance(retained.get("rendered_prompt_sha256"), str)
            or retained.get("prompt_tokens")
            != retained_usage.get("prompt_tokens")
            or retained.get("prompt_tokens")
            != retained_timings.get("prompt_n")
            or retained.get("prompt_tokens") != oracle_usage.get("prompt_tokens")
            or retained.get("prompt_tokens") != oracle_timings.get("prompt_n")
            or not isinstance(retained.get("prompt_tokens"), int)
            or isinstance(retained.get("prompt_tokens"), bool)
            or retained["prompt_tokens"] <= 0
            or retained_tokens
            != [oracle["token_ids"][position] for position in retained_positions]
            or retained.get("content") != oracle["content"]
            or retained.get("sha256") != oracle["content_sha256"]
        ):
            raise ValueError(
                f"sealed isolated/matched-control row is malformed: {prompt_id}"
            )
    return control_by_id, isolated_by_id, rates, {
        "checks": reference_checks,
        "hashes": observed_hashes,
    }


def load_journal(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text().splitlines():
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError("capture journal entry is not an object")
        rows.append(value)
    return rows


def load_cleanup(path: Path) -> dict[str, Any]:
    value = read_object(path)
    if value.get("schema") != "qwen36-four-service-cleanup-v1":
        raise ValueError("cleanup schema mismatch")
    return value


def validate_hash_manifest(path: Path) -> bool:
    entries = 0
    for line in path.read_text().splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if match is None:
            return False
        expected, raw_path = match.groups()
        item = Path(raw_path)
        if not item.is_file() or sha256_file(item) != expected:
            return False
        entries += 1
    return entries >= 10


def validate(args: argparse.Namespace) -> int:
    run = args.run_dir.resolve()
    capture_path = run / "capture.json"
    config_path = run / "service-config.json"
    prepared_path = run / "prepared.json"
    journal_path = run / "capture-journal.jsonl"
    prompt_ids, prompt_hashes = load_suite(args.suite)
    (
        control_by_id,
        retained_by_id,
        reference_rates,
        reference_evidence,
    ) = validate_reference(args)
    capture = read_object(capture_path)
    config = read_object(config_path)
    prepared = read_object(prepared_path)
    identity = capture.get("run_identity") or {}
    fresh = capture.get("fresh_response_validity") or {}
    accounting = capture.get("metric_accounting") or {}
    rows = capture.get("rows")
    waves = capture.get("waves")
    services = config.get("services")
    prepared_rows = prepared.get("rows")
    checks: dict[str, bool] = {
        "capture_schema": capture.get("schema") == CAPTURE_SCHEMA,
        "config_schema": config.get("schema") == CONFIG_SCHEMA,
        "capture_config_bound": identity.get("config_sha256")
        == sha256_file(config_path),
        "prepared_capture_bound": identity.get("prepared_path")
        == str(prepared_path.resolve())
        and identity.get("prepared_sha256") == sha256_file(prepared_path),
        "prepared_exact": prepared.get("schema") == f"{CAPTURE_SCHEMA}-prepared"
        and prepared.get("suite_path") == str(args.suite.resolve())
        and prepared.get("suite_sha256") == SUITE_SHA256
        and prepared.get("config_path") == str(config_path.resolve())
        and prepared.get("config_sha256") == sha256_file(config_path)
        and prepared.get("service_count") == 4
        and prepared.get("wave_count") == 3
        and prepared.get("generation_requests") == 0
        and isinstance(prepared_rows, list)
        and len(prepared_rows) == 12,
        "suite_bound": identity.get("suite_sha256") == SUITE_SHA256,
        "once_only_identity": identity.get("prompt_count") == 12
        and identity.get("service_count") == 4
        and identity.get("wave_count") == 3
        and identity.get("requests_per_wave") == 4
        and identity.get("generation_requests_per_prompt") == 1
        and identity.get("generation_requests_total") == 12
        and identity.get("replay_requests") == 0,
        "request_policy": identity.get("max_tokens") == 512
        and identity.get("seed") == 1
        and identity.get("temperature") == 0
        and identity.get("top_p") == 1
        and identity.get("ignore_eos") is False
        and identity.get("request_extra")
        == {
            "cache_prompt": False,
            "id_slot": 0,
            "ignore_eos": False,
            "return_tokens": True,
            "verbose": True,
        },
        "fresh_policy": fresh.get("valid") is True
        and fresh.get("each_prompt_run_once") is True
        and fresh.get("cached_tokens_all_zero") is True
        and all(
            fresh.get(key) is False
            for key in (
                "history_acceleration",
                "ngram_history_acceleration",
                "response_reuse",
                "context_checkpoints_or_prefix_reuse",
            )
        ),
        "metric_accounting": accounting
        == {
            "schema": "realistic-window-accounting-v2-oracle-aligned",
            "timestamped_events": 100,
            "inter_token_intervals": 99,
            "timing_source": "llamacpp_oai_completion_verbose_token_ids",
        },
        "four_services": isinstance(services, list) and len(services) == 4,
        "twelve_rows": isinstance(rows, list) and len(rows) == 12,
        "three_waves": isinstance(waves, list) and len(waves) == 3,
        "harness_inputs_unchanged": validate_hash_manifest(run / "harness-inputs.sha256"),
        "device_error_scan_empty": (run / "device-error-scan.txt").read_text() == "",
        "server_error_scan_empty": (run / "server-error-scan.txt").read_text() == "",
    }
    model_integrity = read_object(run / "model-integrity.json")
    runtime_initial = read_object(run / "runtime-bundle.json")
    runtime_final = read_object(run / "runtime-bundle-final.json")
    checks["model_identity_stable"] = (
        model_integrity.get("schema") == "qwen36-four-service-model-integrity-v1"
        and model_integrity.get("expected_sha256") == MODEL_SHA256
        and model_integrity.get("stat_unchanged") is True
        and model_integrity.get("sha256_verified") is True
        and model_integrity.get("passed") is True
    )
    checks["runtime_bundle_stable"] = (
        runtime_initial.get("passed") is True
        and runtime_final.get("passed") is True
        and runtime_final.get("reference_match") is True
        and runtime_final.get("reference_report")
        == str((run / "runtime-bundle.json").resolve())
        and (runtime_initial.get("binary") or {}).get("sha256") == RUNTIME_SHA256
        and (runtime_final.get("binary") or {}).get("sha256") == RUNTIME_SHA256
        and (runtime_initial.get("binary") or {}).get("resolved_path")
        == RUNTIME_PATH
        and (runtime_final.get("binary") or {}).get("resolved_path")
        == RUNTIME_PATH
    )
    if (
        not isinstance(services, list)
        or not isinstance(rows, list)
        or not isinstance(waves, list)
        or not isinstance(prepared_rows, list)
    ):
        raise ValueError("capture/config arrays are missing")

    service_config_checks: list[dict[str, Any]] = []
    for service_index, service in enumerate(services):
        expected_port = args.port_base + service_index
        expected_model = f"qwen36-27b-mtp-q8-vdr2-realistic-scale-gpu{service_index}"
        item_checks = {
            "service_index": isinstance(service, dict)
            and service.get("service_index") == service_index,
            "gpu_index": isinstance(service, dict)
            and service.get("gpu_index") == service_index,
            "base_url": isinstance(service, dict)
            and service.get("base_url") == f"http://127.0.0.1:{expected_port}",
            "model": isinstance(service, dict) and service.get("model") == expected_model,
        }
        service_config_checks.append(
            {"service_index": service_index, "checks": item_checks, "passed": all(item_checks.values())}
        )
    checks["service_config_exact"] = all(item["passed"] for item in service_config_checks)
    discovery = read_object(run / "xpu-smi-discovery.json")
    physical_b70s = [
        device
        for device in discovery.get("device_list", [])
        if isinstance(device, dict)
        and device.get("device_function_type") == "physical"
        and "Arc(TM) Pro B70" in str(device.get("device_name", ""))
    ]
    checks["four_distinct_physical_b70s"] = (
        len(physical_b70s) == 4
        and sorted(device.get("device_id") for device in physical_b70s)
        == [0, 1, 2, 3]
        and len({device.get("pci_bdf_address") for device in physical_b70s}) == 4
        and len({device.get("uuid") for device in physical_b70s}) == 4
        and all(device.get("pci_bdf_address") for device in physical_b70s)
        and all(device.get("uuid") for device in physical_b70s)
    )
    row_results: list[dict[str, Any]] = []
    observed_rates: dict[str, dict[str, float]] = {}
    request_ids: list[str] = []
    service_response_counters = {
        index: {"draft_tokens": 0, "accepted_tokens": 0} for index in range(4)
    }
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError("capture row is not an object")
        prompt_id = row.get("prompt_id")
        service_index = index % 4
        wave_index = index // 4
        completion = row.get("completion_tokens")
        positions = row.get("stream_complete_positions")
        token_ids = row.get("token_ids")
        offsets = row.get("token_id_offsets_s")
        oracle = control_by_id.get(prompt_id, {})
        retained = retained_by_id.get(prompt_id, {})
        timings = row.get("timings") or {}
        usage = row.get("usage") or {}
        payload = row.get("request_payload") or {}
        prepared_row = prepared_rows[index] if index < len(prepared_rows) else {}
        verbose = row.get("final_verbose") or {}
        try:
            d99, full = row_rates(row)
        except ValueError:
            d99 = full = 0.0
        expected_model = f"qwen36-27b-mtp-q8-vdr2-realistic-scale-gpu{service_index}"
        row_checks = {
            "prompt_identity": prompt_id == prompt_ids[index]
            and row.get("prompt_index") == index
            and row.get("prompt_sha256") == prompt_hashes[index],
            "prepared_prompt_bound": isinstance(prepared_row, dict)
            and prepared_row.get("prompt_index") == index
            and prepared_row.get("prompt_id") == prompt_ids[index]
            and prepared_row.get("prompt_sha256") == prompt_hashes[index]
            and prepared_row.get("wave_index") == wave_index
            and prepared_row.get("service_index") == service_index
            and prepared_row.get("gpu_index") == service_index
            and prepared_row.get("base_url")
            == f"http://127.0.0.1:{args.port_base + service_index}"
            and prepared_row.get("model") == expected_model
            and isinstance(prepared_row.get("rendered_prompt"), str)
            and sha256_text(prepared_row["rendered_prompt"])
            == prepared_row.get("rendered_prompt_sha256")
            == row.get("rendered_prompt_sha256"),
            "partition": row.get("wave_index") == wave_index
            and row.get("service_index") == service_index
            and row.get("gpu_index") == service_index,
            "service_identity": row.get("base_url")
            == f"http://127.0.0.1:{args.port_base + service_index}"
            and row.get("model") == expected_model,
            "request_exact": payload.get("model") == expected_model
            and payload.get("max_tokens") == 512
            and payload.get("temperature") == 0
            and payload.get("top_p") == 1
            and payload.get("seed") == 1
            and payload.get("stream") is True
            and payload.get("stream_options") == {"include_usage": True}
            and payload.get("cache_prompt") is False
            and payload.get("verbose") is True
            and payload.get("return_tokens") is True
            and payload.get("ignore_eos") is False
            and payload.get("id_slot") == 0,
            "prompt_hash_bound": isinstance(payload.get("prompt"), str)
            and sha256_text(payload["prompt"]) == row.get("rendered_prompt_sha256"),
            "rendered_prompt_equal_sealed_reference": row.get(
                "rendered_prompt_sha256"
            )
            == retained.get("rendered_prompt_sha256")
            == oracle.get("rendered_prompt_sha256"),
            "prompt_token_count_equal_sealed_reference": isinstance(
                row.get("prompt_tokens"), int
            )
            and not isinstance(row.get("prompt_tokens"), bool)
            and row.get("prompt_tokens") > 0
            and row.get("prompt_tokens") == usage.get("prompt_tokens")
            and row.get("prompt_tokens") == timings.get("prompt_n")
            and row.get("prompt_tokens") == retained.get("prompt_tokens")
            and row.get("prompt_tokens")
            == (oracle.get("usage") or {}).get("prompt_tokens"),
            "cache_zero": row.get("cached_tokens") == 0
            and (usage.get("prompt_tokens_details") or {}).get("cached_tokens") == 0
            and timings.get("cache_n") == 0,
            "completion_bound": isinstance(completion, int)
            and not isinstance(completion, bool)
            and 100 <= completion <= 512
            and usage.get("completion_tokens") == completion
            and timings.get("predicted_n") == completion,
            "stream_position_arrays_valid": isinstance(completion, int)
            and isinstance(positions, list)
            and positions == sorted(set(positions))
            and bool(positions)
            and positions[0] >= 0
            and positions[-1] < completion
            and isinstance(token_ids, list)
            and isinstance(offsets, list)
            and len(token_ids) == len(offsets) == len(positions)
            and row.get("stream_token_id_count") == len(token_ids),
            "token_ids_valid": isinstance(token_ids, list)
            and all(
                isinstance(token, int)
                and not isinstance(token, bool)
                and token >= 0
                for token in token_ids
            ),
            "offsets_finite_monotone": isinstance(offsets, list)
            and all(
                isinstance(offset, (int, float))
                and not isinstance(offset, bool)
                and math.isfinite(offset)
                and offset >= 0
                for offset in offsets
            )
            and all(
                offsets[position] <= offsets[position + 1]
                for position in range(len(offsets) - 1)
            ),
            "stream_token_ids_match_control_positions": isinstance(token_ids, list)
            and isinstance(positions, list)
            and isinstance(oracle.get("token_ids"), list)
            and all(0 <= position < len(oracle["token_ids"]) for position in positions)
            and all(
                oracle["token_ids"][position] == token
                for position, token in zip(positions, token_ids)
            ),
            "observed_position_pattern_equal_retained_isolated": positions
            == retained.get("stream_complete_positions"),
            "observed_token_ids_equal_retained_isolated": token_ids
            == retained.get("token_ids"),
            "completion_count_equal_sealed_reference": completion
            == retained.get("completion_tokens")
            == oracle.get("token_count"),
            "token_identity_bound_via_sealed_position_policy": positions
            == retained.get("stream_complete_positions")
            and token_ids == retained.get("token_ids")
            and completion
            == retained.get("completion_tokens")
            == oracle.get("token_count"),
            "full_content_equal_control": isinstance(row.get("content"), str)
            and row.get("content") == oracle.get("content")
            and row.get("sha256") == oracle.get("content_sha256")
            and sha256_text(row["content"]) == row.get("sha256"),
            "d99_and_full_valid": finite_positive(d99) and finite_positive(full),
            "request_counters_valid": isinstance(timings.get("draft_n"), int)
            and not isinstance(timings.get("draft_n"), bool)
            and timings.get("draft_n") > 0
            and isinstance(timings.get("draft_n_accepted"), int)
            and not isinstance(timings.get("draft_n_accepted"), bool)
            and 0 <= timings.get("draft_n_accepted") <= timings.get("draft_n"),
            "protocol_complete": row.get("final_event_count") == 1
            and row.get("done_count") == 1
            and row.get("usage_event_count") == 1
            and row.get("final_timings_event_count") == 1
            and row.get("final_verbose_tokens") == []
            and row.get("final_verbose_content") == ""
            and verbose.get("stop") is True
            and verbose.get("id_slot") == 0
            and verbose.get("truncated") is False
            and verbose.get("tokens_predicted") == completion
            and verbose.get("stop_type") in {"limit", "eos", "word"}
            and row.get("finish_reasons")
            == ["length" if verbose.get("stop_type") == "limit" else "stop"]
            and isinstance(row.get("response_ids"), list)
            and len(row["response_ids"]) > 0
            and len(set(row["response_ids"])) == 1,
        }
        if row_checks["request_counters_valid"]:
            service_response_counters[service_index]["draft_tokens"] += timings["draft_n"]
            service_response_counters[service_index]["accepted_tokens"] += timings[
                "draft_n_accepted"
            ]
        if finite_positive(d99) and finite_positive(full) and isinstance(prompt_id, str):
            observed_rates[prompt_id] = {"d99": d99, "full": full}
        if isinstance(row.get("request_id"), str):
            request_ids.append(row["request_id"])
        row_results.append(
            {
                "prompt_id": prompt_id,
                "prompt_index": index,
                "wave_index": wave_index,
                "service_index": service_index,
                "d99_interval_tok_s": d99,
                "full_interval_tok_s": full,
                "reference_d99_interval_tok_s": reference_rates.get(prompt_id, {}).get("d99"),
                "d99_retention": (
                    d99 / reference_rates[prompt_id]["d99"]
                    if prompt_id in reference_rates and finite_positive(d99)
                    else None
                ),
                "stream_missing_positions": (
                    sorted(set(range(completion)) - set(positions))
                    if isinstance(completion, int) and isinstance(positions, list)
                    else None
                ),
                "checks": row_checks,
                "passed": all(row_checks.values()),
            }
        )
    checks["all_rows_pass"] = len(row_results) == 12 and all(
        row["passed"] for row in row_results
    )
    checks["request_ids_unique"] = len(request_ids) == len(set(request_ids)) == 12
    checks["prompt_order"] = [row.get("prompt_id") for row in rows] == list(PROMPT_IDS)

    journal = load_journal(journal_path)
    started = [entry for entry in journal if entry.get("event") == "request_started"]
    completed = [entry for entry in journal if entry.get("event") == "request_completed"]
    failed = [entry for entry in journal if entry.get("event") == "request_failed"]
    checks["journal_once_only"] = len(journal) == 24 and len(started) == 12 and len(completed) == 12 and not failed
    checks["journal_request_join"] = sorted(entry.get("request_id") for entry in started) == sorted(request_ids) == sorted(
        entry.get("request_id") for entry in completed
    )
    expected_journal_projection = sorted(
        (
            row["request_id"],
            row["wave_index"],
            row["service_index"],
            row["prompt_index"],
            row["prompt_id"],
        )
        for row in rows
    )
    checks["journal_identity_join"] = all(
        sorted(
            (
                entry.get("request_id"),
                entry.get("wave_index"),
                entry.get("service_index"),
                entry.get("prompt_index"),
                entry.get("prompt_id"),
            )
            for entry in entries
        )
        == expected_journal_projection
        for entries in (started, completed)
    )

    wave_results: list[dict[str, Any]] = []
    for wave_index, wave in enumerate(waves):
        captured_wave_rows = rows[wave_index * 4 : wave_index * 4 + 4]
        row_lifetimes_valid = all(
            finite_positive(row.get("request_started_epoch_s"))
            and finite_positive(row.get("request_ended_epoch_s"))
            and finite_positive(row.get("elapsed_s"))
            and row["request_ended_epoch_s"] > row["request_started_epoch_s"]
            for row in captured_wave_rows
        )
        row_end_arithmetic = row_lifetimes_valid and all(
            math.isclose(
                row["request_ended_epoch_s"],
                row["request_started_epoch_s"] + row["elapsed_s"],
                rel_tol=0,
                abs_tol=1e-6,
            )
            for row in captured_wave_rows
        )
        recomputed_latest_start = (
            max(row["request_started_epoch_s"] for row in captured_wave_rows)
            if row_lifetimes_valid
            else None
        )
        recomputed_earliest_end = (
            min(row["request_ended_epoch_s"] for row in captured_wave_rows)
            if row_lifetimes_valid
            else None
        )
        recomputed_overlap = (
            recomputed_earliest_end - recomputed_latest_start
            if row_lifetimes_valid
            else None
        )
        wave_checks = {
            "identity": isinstance(wave, dict) and wave.get("wave_index") == wave_index,
            "partition": isinstance(wave, dict)
            and wave.get("prompt_indices") == list(range(wave_index * 4, wave_index * 4 + 4))
            and wave.get("service_indices") == [0, 1, 2, 3],
            "four_requests": isinstance(wave, dict)
            and isinstance(wave.get("request_ids"), list)
            and len(wave["request_ids"]) == len(set(wave["request_ids"])) == 4,
            "request_id_join": isinstance(wave, dict)
            and wave.get("request_ids")
            == [row.get("request_id") for row in captured_wave_rows],
            "row_lifetimes_valid": row_lifetimes_valid,
            "row_end_arithmetic": row_end_arithmetic,
            "summary_extrema_match_rows": isinstance(wave, dict)
            and row_lifetimes_valid
            and math.isclose(
                wave.get("latest_request_start_epoch_s", math.nan),
                recomputed_latest_start,
                rel_tol=0,
                abs_tol=1e-9,
            )
            and math.isclose(
                wave.get("earliest_request_end_epoch_s", math.nan),
                recomputed_earliest_end,
                rel_tol=0,
                abs_tol=1e-9,
            ),
            "genuine_overlap": finite_positive(recomputed_overlap)
            and recomputed_overlap >= MIN_WAVE_OVERLAP_S,
            "overlap_arithmetic": isinstance(wave, dict)
            and finite_positive(wave.get("four_way_overlap_s"))
            and finite_positive(recomputed_overlap)
            and math.isclose(
                wave["four_way_overlap_s"],
                recomputed_overlap,
                rel_tol=0,
                abs_tol=1e-9,
            ),
        }
        listener_text = (run / f"listeners-wave{wave_index}.txt").read_text()
        wave_checks["four_live_listeners"] = all(
            re.search(
                rf"127\.0\.0\.1:{args.port_base + service}\b.*\bpid={int((run / f'gpu{service}' / 'server.pid').read_text().strip())}\b",
                listener_text,
            )
            is not None
            for service in range(4)
        )
        wave_results.append(
            {
                "wave_index": wave_index,
                "recomputed_latest_request_start_epoch_s": recomputed_latest_start,
                "recomputed_earliest_request_end_epoch_s": recomputed_earliest_end,
                "recomputed_four_way_overlap_s": recomputed_overlap,
                "checks": wave_checks,
                "passed": all(wave_checks.values()),
            }
        )
    checks["all_waves_overlap"] = all(wave["passed"] for wave in wave_results)

    service_results: list[dict[str, Any]] = []
    observed_service_d99: list[float] = []
    observed_service_full: list[float] = []
    reference_service_d99: list[float] = []
    reference_service_full: list[float] = []
    server_pids: list[int] = []
    for service_index in range(4):
        directory = run / f"gpu{service_index}"
        server_identity = read_object(directory / "server-identity.json")
        pre_gate = read_object(directory / "server-gate-pre.json")
        post_gate = read_object(directory / "server-gate-post.json")
        metrics = read_object(directory / "metrics-gate.json")
        residency = read_object(directory / "residency.json")
        cleanup = load_cleanup(directory / "cleanup.json")
        argv = server_identity.get("argv")
        response = service_response_counters[service_index]
        assigned = [PROMPT_IDS[index] for index in range(service_index, 12, 4)]
        observed_d99 = median([observed_rates[prompt]["d99"] for prompt in assigned])
        observed_full = median([observed_rates[prompt]["full"] for prompt in assigned])
        reference_d99 = median([reference_rates[prompt]["d99"] for prompt in assigned])
        reference_full = median([reference_rates[prompt]["full"] for prompt in assigned])
        observed_service_d99.append(observed_d99)
        observed_service_full.append(observed_full)
        reference_service_d99.append(reference_d99)
        reference_service_full.append(reference_full)
        expected_port = args.port_base + service_index
        expected_alias = f"qwen36-27b-mtp-q8-vdr2-realistic-scale-gpu{service_index}"
        expected_identity_path = str((directory / "server-identity.json").resolve())
        expected_log_path = str((directory / "server.stdout.log").resolve())
        server_pid = int((directory / "server.pid").read_text().strip())
        server_pids.append(server_pid)
        service_checks = {
            "identity": server_identity.get("mode") == "mtp3"
            and server_identity.get("gpu_index") == service_index
            and server_identity.get("ze_affinity_mask") == str(service_index)
            and server_identity.get("model") == MODEL_PATH
            and server_identity.get("model_sha256") == MODEL_SHA256
            and server_identity.get("runtime_sha256") == RUNTIME_SHA256,
            "argv": isinstance(argv, list)
            and bool(argv)
            and all(isinstance(value, str) for value in argv)
            and argv[0] == RUNTIME_PATH
            and argv_values(argv, "--port") == [str(expected_port)]
            and argv_values(argv, "--alias") == [expected_alias]
            and argv_values(argv, "-c") == ["32768"]
            and argv_values(argv, "-np") == ["1"]
            and argv_values(argv, "-b") == ["1024"]
            and argv_values(argv, "-ub") == ["1024"]
            and argv_values(argv, "--spec-type") == ["draft-mtp"]
            and argv_values(argv, "-lv") == ["4"]
            and "--verbose" not in argv,
            "pre_server_gate": pre_gate.get("passed") is True
            and pre_gate.get("mode") == "mtp3"
            and all((pre_gate.get("checks") or {}).values())
            and pre_gate.get("identity") == expected_identity_path
            and pre_gate.get("log") == expected_log_path,
            "post_server_gate": post_gate.get("passed") is True
            and post_gate.get("mode") == "mtp3"
            and all((post_gate.get("checks") or {}).values())
            and post_gate.get("identity") == expected_identity_path
            and post_gate.get("log") == expected_log_path,
            "full_offload_66": (pre_gate.get("checks") or {}).get("full_offload_66")
            is True
            and (post_gate.get("checks") or {}).get("full_offload_66") is True,
            "fit_no_changes": (pre_gate.get("checks") or {}).get("fit_no_changes_exact")
            is True
            and (post_gate.get("checks") or {}).get("fit_no_changes_exact") is True
            and all(pair[1] >= 1024 and pair[0] >= pair[1] for pair in pre_gate.get("fit_headroom_pairs_mib", []))
            and len(pre_gate.get("fit_headroom_pairs_mib", [])) == 1,
            "metrics_gate": metrics.get("mode") == "mtp3"
            and metrics.get("passed") is True
            and all((metrics.get("checks") or {}).values()),
            "metrics_response_join": (metrics.get("counters") or {}).get("draft_tokens")
            == response["draft_tokens"]
            and (metrics.get("counters") or {}).get("accepted_tokens")
            == response["accepted_tokens"],
            "positive_counters": all(
                isinstance((metrics.get("counters") or {}).get(key), int)
                and not isinstance((metrics.get("counters") or {}).get(key), bool)
                and (metrics.get("counters") or {})[key] > 0
                for key in ("draft_tokens", "accepted_tokens", "drafts")
            ),
            "residency": residency.get("gpu_index") == service_index
            and nonnegative_int_at_most(residency.get("pre_mib"), MAX_IDLE_MIB)
            and nonnegative_int_at_most(
                residency.get("loaded_mib"), MAX_LOADED_MIB
            )
            and residency.get("loaded_delta_mib")
            == residency["loaded_mib"] - residency["pre_mib"]
            and residency["loaded_delta_mib"] >= MIN_LOADED_DELTA_MIB,
            "cleanup": cleanup.get("gpu_index") == service_index
            and cleanup.get("pid") == server_pid
            and server_pid > 0
            and cleanup.get("pre_mib") == residency.get("pre_mib")
            and cleanup.get("forced_kill") is False
            and cleanup.get("survivor") is False
            and cleanup.get("port_closed") is True
            and cleanup.get("pid_dead") is True
            and nonnegative_int_at_most(cleanup.get("post_mib"), MAX_IDLE_MIB),
        }
        service_performance_checks = {
            "d99_retention_at_least_090": observed_d99 / reference_d99
            >= SERVICE_RETENTION_FLOOR,
            "full_retention_at_least_090": observed_full / reference_full
            >= SERVICE_RETENTION_FLOOR,
        }
        service_results.append(
            {
                "service_index": service_index,
                "gpu_index": service_index,
                "prompt_ids": assigned,
                "observed": {"d99_median": observed_d99, "full_median": observed_full},
                "isolated_reference": {
                    "d99_median": reference_d99,
                    "full_median": reference_full,
                },
                "retention": {
                    "d99": observed_d99 / reference_d99,
                    "full": observed_full / reference_full,
                },
                "response_counters": response,
                "metrics_counters": metrics.get("counters"),
                "checks": service_checks,
                "evidence_passed": all(service_checks.values()),
                "performance_checks": service_performance_checks,
                "performance_passed": all(service_performance_checks.values()),
            }
        )
    checks["all_services_pass"] = all(
        service["evidence_passed"] for service in service_results
    )
    checks["four_distinct_service_pids"] = (
        len(server_pids) == len(set(server_pids)) == SERVICE_COUNT
        and all(pid > 0 for pid in server_pids)
    )

    aggregate_observed_d99 = sum(observed_service_d99)
    aggregate_observed_full = sum(observed_service_full)
    aggregate_reference_d99 = sum(reference_service_d99)
    aggregate_reference_full = sum(reference_service_full)
    aggregate_d99_retention = aggregate_observed_d99 / aggregate_reference_d99
    aggregate_full_retention = aggregate_observed_full / aggregate_reference_full
    d99_fairness = min(observed_service_d99) / max(observed_service_d99)
    full_fairness = min(observed_service_full) / max(observed_service_full)
    prompt_d99_retentions = {
        prompt: observed_rates[prompt]["d99"] / reference_rates[prompt]["d99"]
        for prompt in PROMPT_IDS
    }
    performance_checks = {
        "aggregate_d99_retention_at_least_095": aggregate_d99_retention
        >= AGGREGATE_RETENTION_FLOOR,
        "aggregate_full_retention_at_least_095": aggregate_full_retention
        >= AGGREGATE_RETENTION_FLOOR,
        "each_service_d99_retention_at_least_090": all(
            service["performance_checks"]["d99_retention_at_least_090"]
            for service in service_results
        ),
        "each_service_full_retention_at_least_090": all(
            service["performance_checks"]["full_retention_at_least_090"]
            for service in service_results
        ),
        "d99_service_fairness_at_least_090": d99_fairness
        >= SERVICE_FAIRNESS_FLOOR,
        "full_service_fairness_at_least_090": full_fairness
        >= SERVICE_FAIRNESS_FLOOR,
        "each_prompt_d99_retention_at_least_080": all(
            value >= PROMPT_D99_RETENTION_FLOOR
            for value in prompt_d99_retentions.values()
        ),
    }
    evidence_checks = dict(checks)
    evidence_valid = all(evidence_checks.values())
    performance_passed = all(performance_checks.values())
    passed = evidence_valid and performance_passed
    classification = (
        "PASS_REALISTIC_MTP_FOUR_SERVICE_SCALE"
        if passed
        else "VALID_REALISTIC_MTP_FOUR_SERVICE_SCALE_RETENTION_FAIL"
        if evidence_valid
        else "INVALID_REALISTIC_MTP_FOUR_SERVICE_EVIDENCE"
    )
    result = {
        "schema": "qwen36-embedded-mtp-four-service-realistic-gate-v1",
        "classification": classification,
        "passed": passed,
        "evidence_valid": evidence_valid,
        "performance_passed": performance_passed,
        "evidence_class": "official-four-service-realistic-scaling-gate",
        "performance_promotable": False,
        "localmaxxing_submission_ready": False,
        "scope": {
            "gpu_count": 4,
            "independent_services": 4,
            "slots_per_service": 1,
            "ctx_size": 32768,
            "fixed_prompts": 12,
            "waves": 3,
            "requests_per_wave": 4,
            "ordinary_eos": True,
            "requests_per_prompt": 1,
            "replay_requests": 0,
            "quality_reference": "sealed_matched_fresh_control_v1",
        },
        "token_identity_policy": {
            "mode": "sealed_retained_isolated_position_binding",
            "current_stream_ids_direct_at_reported_positions": True,
            "current_missing_position_ids_directly_observed": False,
            "requires_exact_current_vs_retained_position_pattern": True,
            "requires_exact_current_vs_retained_observed_ids": True,
            "requires_exact_current_vs_control_full_content": True,
            "retained_isolated_full_token_content_equality_is_sealed": True,
            "replay_requests": 0,
            "note": "This is a transitive binding to pinned scored/forensic evidence, not a claim that UTF-8-buffered IDs absent from the current SSE were directly observed.",
        },
        "thresholds": {
            "aggregate_retention": AGGREGATE_RETENTION_FLOOR,
            "service_retention": SERVICE_RETENTION_FLOOR,
            "service_fairness": SERVICE_FAIRNESS_FLOOR,
            "prompt_d99_retention": PROMPT_D99_RETENTION_FLOOR,
            "minimum_four_way_overlap_s": MIN_WAVE_OVERLAP_S,
            "minimum_loaded_delta_mib": MIN_LOADED_DELTA_MIB,
            "maximum_loaded_mib": MAX_LOADED_MIB,
            "maximum_pre_post_idle_mib": MAX_IDLE_MIB,
        },
        "evidence_checks": evidence_checks,
        "performance_checks": performance_checks,
        "reference_evidence": reference_evidence,
        "services": service_results,
        "waves": wave_results,
        "rows": row_results,
        "performance": {
            "prompt_balanced_isolated_reference": {
                "aggregate_d99": aggregate_reference_d99,
                "aggregate_full": aggregate_reference_full,
                "service_d99_medians": reference_service_d99,
                "service_full_medians": reference_service_full,
            },
            "observed": {
                "aggregate_d99": aggregate_observed_d99,
                "aggregate_full": aggregate_observed_full,
                "service_d99_medians": observed_service_d99,
                "service_full_medians": observed_service_full,
            },
            "retention": {
                "aggregate_d99": aggregate_d99_retention,
                "aggregate_full": aggregate_full_retention,
                "d99_service_fairness": d99_fairness,
                "full_service_fairness": full_fairness,
                "per_prompt_d99": prompt_d99_retentions,
            },
            "context": {
                "ideal_four_service_retention": 1.0,
                "isolated_global_d99_median_x4": 4
                * median([reference_rates[prompt]["d99"] for prompt in PROMPT_IDS]),
                "isolated_global_full_median_x4": 4
                * median([reference_rates[prompt]["full"] for prompt in PROMPT_IDS]),
                "prior_target_only_four_service_retention_expectation": PRIOR_TARGET_ONLY_FOUR_SERVICE_RETENTION,
                "preregistered_aggregate_retention_gate": AGGREGATE_RETENTION_FLOOR,
                "note": "Ideal retention is 100% and the prior target-only expectation is 99.76%, but the hard gate is 95%. The denominator is the sum of four prompt-balanced isolated lane medians; global-median x4 is context only.",
            },
            "checks": performance_checks,
        },
    }
    atomic_write(args.output, result)
    return 0 if evidence_valid else 1


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    root.add_argument("--run-dir", type=Path, required=True)
    root.add_argument("--suite", type=Path, required=True)
    root.add_argument("--isolated-candidate", type=Path, required=True)
    root.add_argument("--matched-control-forensic", type=Path, required=True)
    root.add_argument("--sealed-mtp3-gate", type=Path, required=True)
    root.add_argument("--supplement-comparison", type=Path, required=True)
    root.add_argument("--supplement-completion", type=Path, required=True)
    root.add_argument("--supplement-identity", type=Path, required=True)
    root.add_argument("--port-base", type=int, required=True)
    root.add_argument("--output", type=Path, required=True)
    return root


def main() -> int:
    try:
        args = parser().parse_args()
        if not 1024 <= args.port_base <= 65532:
            raise ValueError("port base must leave four valid unprivileged ports")
        return validate(args)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"four-service realistic gate failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
