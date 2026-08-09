#!/usr/bin/env python3
"""Capture a compact diagnostic-only c2 token matrix.

This is deliberately separate from the formal c2 promotion gate.  A complete,
well-attested token mismatch is valid diagnostic evidence and therefore does
not make this program fail.  Malformed or incomplete evidence does.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import time
from types import ModuleType
from typing import Any
from urllib.parse import urlparse


TOKEN_COUNT = 128
REQUEST_SKEW_LIMIT_S = 0.025
OCCUPANCY_MINIMUM = 1.5
SCENARIO_CASE_INDEXES = {
    "swap": (1, 0),
    "duplicate-b": (1, 1),
    "forward": (0, 1),
    "duplicate-a": (0, 0),
}
PAYLOAD_FIELDS = {
    "n_predict": TOKEN_COUNT,
    "temperature": 0,
    "top_p": 1,
    "seed": 1,
    "cache_prompt": False,
    "return_tokens": True,
    "ignore_eos": True,
}
FORBIDDEN_PAYLOAD_FIELDS = {
    "backend_sampling",
    "min_p",
    "top_k",
    "typical_p",
}
EXPECTED_PAYLOAD_FIELDS = {
    "prompt",
    "id_slot",
    *PAYLOAD_FIELDS,
}
REQUIRED_ATTESTATION_IDENTITY_FIELDS = {
    "GGML_SYCL_ENABLE_DNN",
    "GGML_SYCL_ENABLE_FLASH_ATTN",
    "GGML_SYCL_ENABLE_GRAPH",
    "GGML_SYCL_ENABLE_MKL_FA",
    "GGML_SYCL_ENABLE_OPT",
    "GGML_SYCL_ENABLE_VMM",
    "GGML_SYCL_FA_ONEDNN",
    "GGML_SYCL_FA_ONEDNN_MAX_KV",
    "ONEAPI_DEVICE_SELECTOR",
    "batch_size",
    "cache_type_k",
    "cache_type_v",
    "cont_batching",
    "ctx_size",
    "ctx_size_per_slot",
    "flash_attn",
    "http_threads",
    "kv_unified",
    "llama_server_sha256",
    "log_verbosity",
    "model_alias",
    "model_bytes",
    "n_gpu_layers",
    "parallel_slots",
    "pinned_model_fd_contract",
    "reasoning",
    "speculation",
    "threads",
    "ubatch_size",
    "vision_projector",
}
REQUIRED_ATTESTATION_ARGV_FIELDS = {
    "--cache-ram 0",
    "--cont-batching",
    "--ctx-checkpoints 0",
    "--jinja",
    "--metrics",
    "--no-cache-idle-slots",
    "--no-context-shift",
    "--no-kv-unified",
    "--reasoning off",
    "--slots",
    "--spec-type none",
    "--threads-http 6",
    "-b 1024",
    "-c 65536",
    "-ctk f16",
    "-ctv f16",
    "-fa on",
    "-ngl 99",
    "-np 2",
    "-ub 128",
}
REQUIRED_ATTESTATION_RUNTIME_FIELDS = {
    "context_checkpoints_disabled",
    "f16_kv_4096_mib",
    "flash_attn_enabled",
    "full_offload_65_of_65",
    "kv_unified_false",
    "n_batch_1024",
    "n_ctx_65536",
    "n_ctx_seq_32768",
    "n_seq_max_2",
    "n_ubatch_128",
    "post_fit_free_at_least_minimum",
    "prompt_cache_disabled",
    "speculation_disabled",
    "two_slot_recurrent_state",
    "two_slot_runtime",
}
REQUIRED_ATTESTATION_OBSERVED_FIELDS = {
    "fit_free_mib",
    "kv_config",
    "minimum_fit_free_mib",
    "offload_pairs",
    "recurrent_config",
    "slot_config",
}
_FAILURE_OUTPUT: Path | None = None


def is_json_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def integer_equals(value: Any, expected: int) -> bool:
    return is_json_integer(value) and value == expected


def is_finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def is_token_id_list(value: Any, expected_length: int | None = None) -> bool:
    return (
        isinstance(value, list)
        and (expected_length is None or len(value) == expected_length)
        and all(is_json_integer(token) and token >= 0 for token in value)
    )


def is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode())


def load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def snapshot_inputs(paths: dict[str, Path]) -> dict[str, dict[str, str]]:
    return {
        label: {
            "path": str(path),
            "sha256": sha256_bytes(path.read_bytes()),
        }
        for label, path in paths.items()
    }


def compare_input_snapshots(
    before: dict[str, dict[str, str]],
    after: dict[str, dict[str, str]],
) -> dict[str, Any]:
    labels_exact = {
        label: after.get(label) == value for label, value in before.items()
    }
    return {
        "before": before,
        "after": after,
        "labels_exact": labels_exact,
        "passed": set(before) == set(after) and all(labels_exact.values()),
    }


def load_short_cases(suite: dict[str, Any]) -> list[dict[str, Any]]:
    pairs = suite.get("pairs") if isinstance(suite, dict) else None
    matches = (
        [pair for pair in pairs if isinstance(pair, dict) and pair.get("band") == "short"]
        if isinstance(pairs, list)
        else []
    )
    cases = matches[0].get("cases") if len(matches) == 1 else None
    if not isinstance(cases, list) or len(cases) != 2:
        raise SystemExit("suite must contain exactly one two-case short pair")
    if any(not isinstance(case, dict) for case in cases):
        raise SystemExit("short-pair cases must be objects")
    case_ids = [case.get("id") for case in cases]
    if (
        any(not isinstance(case_id, str) or not case_id for case_id in case_ids)
        or len(set(case_ids)) != 2
        or any(
            not is_json_integer(case.get("calibrated_prompt_tokens"))
            or case["calibrated_prompt_tokens"] <= 0
            for case in cases
        )
    ):
        raise SystemExit("short-pair case identity/calibration is malformed")
    return copy.deepcopy(cases)


def payload_value_exact(key: str, value: Any, expected: Any) -> bool:
    if isinstance(expected, bool):
        return value is expected
    if key in ("n_predict", "seed"):
        return integer_equals(value, expected)
    return is_finite_number(value) and value == expected


def attest_server(
    attestation: dict[str, Any],
    oracle_identity: dict[str, Any],
    runtime_sha256: str,
) -> dict[str, bool]:
    expected_identity = attestation.get("expected_identity")
    identity_fields = attestation.get("identity_fields")
    argv_fields = attestation.get("argv_fields")
    runtime_fields = attestation.get("runtime_fields")
    observed = attestation.get("observed")
    identity_fields = identity_fields if isinstance(identity_fields, dict) else {}
    argv_fields = argv_fields if isinstance(argv_fields, dict) else {}
    runtime_fields = runtime_fields if isinstance(runtime_fields, dict) else {}
    observed = observed if isinstance(observed, dict) else {}
    fields = {
        "attestation_passed": attestation.get("passed") is True,
        "identity_fields_complete": REQUIRED_ATTESTATION_IDENTITY_FIELDS.issubset(
            identity_fields
        )
        and all(identity_fields[key] is True for key in REQUIRED_ATTESTATION_IDENTITY_FIELDS),
        "argv_fields_complete": REQUIRED_ATTESTATION_ARGV_FIELDS.issubset(argv_fields)
        and all(argv_fields[key] is True for key in REQUIRED_ATTESTATION_ARGV_FIELDS),
        "runtime_fields_complete": REQUIRED_ATTESTATION_RUNTIME_FIELDS.issubset(
            runtime_fields
        )
        and all(runtime_fields[key] is True for key in REQUIRED_ATTESTATION_RUNTIME_FIELDS),
        "observed_fields_complete": REQUIRED_ATTESTATION_OBSERVED_FIELDS.issubset(
            observed
        ),
        "observed_fit_valid": is_json_integer(observed.get("fit_free_mib"))
        and is_json_integer(observed.get("minimum_fit_free_mib"))
        and observed["fit_free_mib"] >= observed["minimum_fit_free_mib"],
        "expected_identity_present": isinstance(expected_identity, dict)
        and bool(expected_identity),
        "runtime_exact": isinstance(expected_identity, dict)
        and expected_identity.get("llama_server_sha256") == runtime_sha256,
        "oracle_server_identity_exact": isinstance(expected_identity, dict)
        and expected_identity == oracle_identity.get("server_benchmark_identity"),
        "f16_kv": isinstance(expected_identity, dict)
        and expected_identity.get("cache_type_k") == "f16"
        and expected_identity.get("cache_type_v") == "f16",
        "two_32k_slots": isinstance(expected_identity, dict)
        and expected_identity.get("ctx_size") == "65536"
        and expected_identity.get("ctx_size_per_slot") == "32768"
        and expected_identity.get("parallel_slots") == "2"
        and expected_identity.get("cont_batching") == "1"
        and expected_identity.get("kv_unified") == "0",
        "target_only": isinstance(expected_identity, dict)
        and expected_identity.get("speculation") == "none"
        and expected_identity.get("vision_projector") == "none",
    }
    return fields


def process_start_ticks(pid: int) -> int:
    raw = Path(f"/proc/{pid}/stat").read_text()
    close = raw.rfind(")")
    if close < 0:
        raise RuntimeError("server /proc stat has no command terminator")
    fields_after_command = raw[close + 2 :].split()
    if len(fields_after_command) < 20:
        raise RuntimeError("server /proc stat is incomplete")
    value = int(fields_after_command[19])
    if value <= 0:
        raise RuntimeError("server /proc start time is invalid")
    return value


def process_start_epoch_s(start_ticks: int) -> float:
    boot_time: int | None = None
    for line in Path("/proc/stat").read_text().splitlines():
        if line.startswith("btime "):
            boot_time = int(line.split()[1])
            break
    if boot_time is None:
        raise RuntimeError("kernel boot time is absent from /proc/stat")
    ticks_per_second = os.sysconf("SC_CLK_TCK")
    if not isinstance(ticks_per_second, int) or ticks_per_second <= 0:
        raise RuntimeError("system clock tick frequency is invalid")
    return boot_time + start_ticks / ticks_per_second


def command_has_option(argv: list[str], option: str, expected: str) -> bool:
    for index, value in enumerate(argv):
        if value == option and index + 1 < len(argv) and argv[index + 1] == expected:
            return True
        if value == f"{option}={expected}":
            return True
    return False


def listener_inodes(port: int) -> set[str]:
    inodes: set[str] = set()
    for path in (Path("/proc/net/tcp"), Path("/proc/net/tcp6")):
        try:
            lines = path.read_text().splitlines()[1:]
        except OSError:
            continue
        for line in lines:
            fields = line.split()
            if len(fields) < 10 or fields[3] != "0A":
                continue
            local = fields[1]
            try:
                local_port = int(local.rsplit(":", 1)[1], 16)
            except (IndexError, ValueError):
                continue
            if local_port == port:
                inodes.add(fields[9])
    return inodes


def process_socket_inodes(pid: int) -> set[str]:
    inodes: set[str] = set()
    for path in Path(f"/proc/{pid}/fd").iterdir():
        try:
            target = os.readlink(path)
        except OSError:
            continue
        if target.startswith("socket:[") and target.endswith("]"):
            inodes.add(target[8:-1])
    return inodes


def capture_live_server_binding(
    pid: int,
    port: int,
    runtime_sha256: str,
) -> dict[str, Any]:
    if not is_json_integer(pid) or pid <= 1:
        raise RuntimeError("server PID must be an integer greater than one")
    proc_root = Path(f"/proc/{pid}")
    if not proc_root.is_dir():
        raise RuntimeError("attested server PID is not live")
    exe_path = Path(f"/proc/{pid}/exe")
    executable_sha256 = sha256_bytes(exe_path.read_bytes())
    argv = [
        value.decode("utf-8", errors="strict")
        for value in Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
        if value
    ]
    live_listener_inodes = listener_inodes(port)
    owned_socket_inodes = process_socket_inodes(pid)
    fields = {
        "executable_runtime_exact": executable_sha256 == runtime_sha256,
        "port_argument_exact": command_has_option(argv, "--port", str(port)),
        "ctx_argument_exact": command_has_option(argv, "-c", "65536"),
        "parallel_argument_exact": command_has_option(argv, "-np", "2"),
        "ubatch_argument_exact": command_has_option(argv, "-ub", "128"),
        "listener_present": bool(live_listener_inodes),
        "listener_owned_by_pid": bool(live_listener_inodes & owned_socket_inodes),
    }
    start_ticks = process_start_ticks(pid)
    return {
        "pid": pid,
        "process_start_ticks": start_ticks,
        "process_start_epoch_s": process_start_epoch_s(start_ticks),
        "executable_path": os.readlink(exe_path),
        "executable_sha256": executable_sha256,
        "argv": argv,
        "argv_sha256": sha256_bytes(b"\0".join(value.encode() for value in argv)),
        "listener_inodes": sorted(live_listener_inodes),
        "owned_socket_inodes": sorted(owned_socket_inodes),
        "fields": fields,
        "passed": all(fields.values()),
    }


def bind_attestation_to_process(
    attestation_path: Path, live_binding: dict[str, Any]
) -> dict[str, Any]:
    stat = attestation_path.stat()
    modified_epoch_s = stat.st_mtime_ns / 1_000_000_000
    process_epoch_s = live_binding.get("process_start_epoch_s")
    now_epoch_s = time.time()
    fields = {
        "regular_file": attestation_path.is_file(),
        "live_binding_passed": live_binding.get("passed") is True,
        "attestation_created_after_process_start": is_finite_number(process_epoch_s)
        and modified_epoch_s >= process_epoch_s,
        "attestation_not_future_dated": modified_epoch_s <= now_epoch_s + 1,
    }
    return {
        "attestation_path": str(attestation_path),
        "attestation_modified_epoch_s": modified_epoch_s,
        "process_start_epoch_s": process_epoch_s,
        "fields": fields,
        "passed": all(fields.values()),
    }


def compare_live_server_bindings(
    before: dict[str, Any], after: dict[str, Any]
) -> dict[str, Any]:
    continuity_fields = {
        "pid_exact": before.get("pid") == after.get("pid"),
        "process_start_exact": before.get("process_start_ticks")
        == after.get("process_start_ticks"),
        "executable_exact": before.get("executable_sha256")
        == after.get("executable_sha256"),
        "argv_exact": before.get("argv_sha256") == after.get("argv_sha256"),
        "before_passed": before.get("passed") is True,
        "after_passed": after.get("passed") is True,
    }
    return {
        "before": before,
        "after": after,
        "continuity_fields": continuity_fields,
        "passed": all(continuity_fields.values()),
    }


def validate_oracle(
    oracle: dict[str, Any],
    suite_sha256: str,
    cases: list[dict[str, Any]],
    model_sha256: str,
    runtime_sha256: str,
) -> tuple[dict[str, bool], dict[str, dict[str, Any]]]:
    identity = oracle.get("run_identity")
    rows = oracle.get("rows")
    intrinsic = oracle.get("intrinsic_gate")
    comparison = oracle.get("oracle_comparison")
    identity = identity if isinstance(identity, dict) else {}
    rows = rows if isinstance(rows, list) else []
    case_ids = [case["id"] for case in cases]
    oracle_case_ids = [
        row.get("case_id") for row in rows if isinstance(row, dict)
    ]
    oracle_slot_ids = [
        row.get("slot_id") for row in rows if isinstance(row, dict)
    ]
    row_structure = (
        len(rows) == 2
        and all(
            isinstance(row, dict)
            and row.get("passed") is True
            and isinstance(row.get("case_id"), str)
            and is_json_integer(row.get("slot_id"))
            and is_token_id_list(row.get("token_ids"), 512)
            and integer_equals(row.get("token_count"), 512)
            and row.get("token_ids_sha256")
            == sha256_bytes(
                json.dumps(
                    row.get("token_ids"), separators=(",", ":")
                ).encode()
            )
            and is_sha256(row.get("prompt_sha256"))
            and is_sha256(row.get("rendered_prompt_sha256"))
            and is_sha256(row.get("content_sha256"))
            for row in rows
        )
    )
    fields = {
        "mode_sequential_oracle": identity.get("mode") == "sequential-oracle",
        "baseline_ready": isinstance(intrinsic, dict)
        and intrinsic.get("passed") is True
        and isinstance(comparison, dict)
        and comparison.get("status") == "BASELINE_CAPTURE_READY",
        "suite_exact": identity.get("suite_sha256") == suite_sha256,
        "band_short": identity.get("band") == "short",
        "model_exact": identity.get("model_sha256") == model_sha256,
        "runtime_exact": identity.get("runtime_sha256") == runtime_sha256,
        "f16_kv": identity.get("cache_type_k") == "f16"
        and identity.get("cache_type_v") == "f16",
        "two_32k_slots": integer_equals(identity.get("ctx_size_total"), 65536)
        and integer_equals(identity.get("ctx_size_per_slot"), 32768)
        and integer_equals(identity.get("parallel_slots"), 2),
        "forced_payload_identity": integer_equals(identity.get("max_tokens"), 512)
        and identity.get("ignore_eos") is True
        and integer_equals(identity.get("seed"), 1)
        and identity.get("cache_prompt") is False,
        "row_structure": row_structure,
        "case_ids_exact": len(oracle_case_ids) == 2
        and len(set(oracle_case_ids)) == 2
        and set(oracle_case_ids) == set(case_ids),
        "slot_ids_exact": len(oracle_slot_ids) == 2
        and all(is_json_integer(slot_id) for slot_id in oracle_slot_ids)
        and set(oracle_slot_ids) == {0, 1},
        "slot_topology_passed": isinstance(oracle.get("slot_topology"), dict)
        and oracle["slot_topology"].get("passed") is True,
    }
    oracle_by_case = {
        row["case_id"]: row
        for row in rows
        if isinstance(row, dict) and isinstance(row.get("case_id"), str)
    }
    return fields, oracle_by_case


def validate_payload(item: dict[str, Any]) -> dict[str, bool]:
    payload = item.get("payload")
    payload = payload if isinstance(payload, dict) else {}
    return {
        "prompt_present": isinstance(payload.get("prompt"), str)
        and bool(payload["prompt"]),
        "prompt_exact": isinstance(item.get("rendered"), str)
        and payload.get("prompt") == item["rendered"],
        "slot_exact": integer_equals(payload.get("id_slot"), item.get("slot_id")),
        "key_set_exact": set(payload) == EXPECTED_PAYLOAD_FIELDS,
        "formal_fields_exact": all(
            payload_value_exact(key, payload.get(key), expected)
            for key, expected in PAYLOAD_FIELDS.items()
        ),
        "backend_sampling_unchanged": not any(
            field in payload for field in FORBIDDEN_PAYLOAD_FIELDS
        ),
    }


def validate_base_prepared(
    prepared: Any, cases: list[dict[str, Any]]
) -> dict[str, Any]:
    rows = prepared if isinstance(prepared, list) else []
    row_fields: list[dict[str, Any]] = []
    for index, item in enumerate(rows):
        item = item if isinstance(item, dict) else {}
        expected_case = cases[index] if index < len(cases) else None
        payload_fields = validate_payload(item)
        fields = {
            "case_exact": isinstance(expected_case, dict)
            and item.get("case") == expected_case,
            "slot_exact": integer_equals(item.get("slot_id"), index),
            "prompt_string": isinstance(item.get("prompt"), str)
            and bool(item["prompt"]),
            "rendered_string": isinstance(item.get("rendered"), str)
            and bool(item["rendered"]),
            "payload_valid": all(payload_fields.values()),
        }
        row_fields.append(
            {
                "index": index,
                "case_id": (item.get("case") or {}).get("id")
                if isinstance(item.get("case"), dict)
                else None,
                "fields": fields,
                "payload_fields": payload_fields,
                "passed": all(fields.values()),
            }
        )
    case_ids = [row["case_id"] for row in row_fields]
    return {
        "rows": row_fields,
        "case_ids": case_ids,
        "passed": len(row_fields) == len(cases) == 2
        and case_ids == [case["id"] for case in cases]
        and len(set(case_ids)) == 2
        and all(row["passed"] for row in row_fields),
    }


def assign_slot(item: dict[str, Any], slot_id: int) -> dict[str, Any]:
    assigned = copy.deepcopy(item)
    assigned["slot_id"] = slot_id
    assigned["payload"]["id_slot"] = slot_id
    return assigned


def validate_prompt_identity(
    prepared_by_case: dict[str, dict[str, Any]],
    oracle_by_case: dict[str, dict[str, Any]],
) -> dict[str, dict[str, bool]]:
    return {
        case_id: {
            "oracle_row_present": case_id in oracle_by_case,
            "prompt_exact": case_id in oracle_by_case
            and sha256_text(item["prompt"])
            == oracle_by_case[case_id].get("prompt_sha256"),
            "rendered_prompt_exact": case_id in oracle_by_case
            and sha256_text(item["rendered"])
            == oracle_by_case[case_id].get("rendered_prompt_sha256"),
        }
        for case_id, item in prepared_by_case.items()
    }


def validate_stream(item: dict[str, Any], stream: dict[str, Any]) -> dict[str, bool]:
    tokens = stream.get("token_ids")
    offsets = stream.get("token_offsets_s")
    final = stream.get("final")
    final = final if isinstance(final, dict) else {}
    timings = final.get("timings")
    timings = timings if isinstance(timings, dict) else {}
    expected_prompt_n = item["case"]["calibrated_prompt_tokens"]
    started = stream.get("request_started_perf_s")
    ended = stream.get("request_ended_perf_s")
    return {
        "token_ids_128": is_token_id_list(tokens, TOKEN_COUNT),
        "token_offsets_128": isinstance(offsets, list)
        and len(offsets) == TOKEN_COUNT
        and all(is_finite_number(value) and value >= 0 for value in offsets),
        "content_string": isinstance(stream.get("content"), str),
        "final_present": bool(final),
        "slot_exact": integer_equals(final.get("id_slot"), item["slot_id"]),
        "cache_zero": integer_equals(timings.get("cache_n"), 0),
        "predicted_128": integer_equals(timings.get("predicted_n"), TOKEN_COUNT),
        "prompt_count_exact": integer_equals(timings.get("prompt_n"), expected_prompt_n),
        "limit_stop": final.get("stop_type") == "limit",
        "not_truncated": final.get("truncated") is False,
        "timing_order": is_finite_number(started)
        and is_finite_number(ended)
        and ended >= started,
    }


def compare_prefix(observed: Any, expected: Any) -> dict[str, Any]:
    if not is_token_id_list(observed) or not is_token_id_list(expected, TOKEN_COUNT):
        return {
            "comparable": False,
            "expected_token_ids": expected if isinstance(expected, list) else None,
            "observed_token_ids": observed if isinstance(observed, list) else None,
            "lcp_tokens": None,
            "first_mismatch": None,
            "exact_to_c1": False,
        }
    limit = min(len(observed), len(expected))
    lcp = 0
    while lcp < limit and observed[lcp] == expected[lcp]:
        lcp += 1
    mismatch = None
    if lcp < len(observed) or lcp < len(expected):
        mismatch = {
            "index": lcp,
            "observed_token_id": observed[lcp] if lcp < len(observed) else None,
            "expected_token_id": expected[lcp] if lcp < len(expected) else None,
        }
    return {
        "comparable": True,
        "expected_token_ids": expected,
        "observed_token_ids": observed,
        "lcp_tokens": lcp,
        "first_mismatch": mismatch,
        "exact_to_c1": len(observed) == TOKEN_COUNT and lcp == TOKEN_COUNT,
    }


def classify_occupancy(
    metrics_before: dict[str, Any],
    metrics_after: dict[str, Any],
) -> dict[str, Any]:
    keys = (
        "tokens_predicted_total",
        "n_decode_total",
        "n_busy_slots_per_decode",
    )
    numeric_snapshots_valid = all(
        isinstance(snapshot, dict)
        and all(
            is_finite_number(snapshot.get(key)) and snapshot[key] >= 0
            for key in keys
        )
        for snapshot in (metrics_before, metrics_after)
    )
    integral_counters_valid = numeric_snapshots_valid and all(
        float(snapshot[key]).is_integer()
        for snapshot in (metrics_before, metrics_after)
        for key in ("tokens_predicted_total", "n_decode_total")
    )
    busy_bounds_valid = numeric_snapshots_valid and all(
        0 <= snapshot["n_busy_slots_per_decode"] <= 2
        for snapshot in (metrics_before, metrics_after)
    )
    snapshots_valid = integral_counters_valid and busy_bounds_valid
    if snapshots_valid:
        predicted_delta = (
            metrics_after["tokens_predicted_total"]
            - metrics_before["tokens_predicted_total"]
        )
        decode_delta = (
            metrics_after["n_decode_total"] - metrics_before["n_decode_total"]
        )
        ratio = predicted_delta / decode_delta if decode_delta > 0 else None
        busy_after = metrics_after["n_busy_slots_per_decode"]
    else:
        predicted_delta = None
        decode_delta = None
        ratio = None
        busy_after = None
    fields = {
        "numeric_snapshots_valid": numeric_snapshots_valid,
        "integral_counters_valid": integral_counters_valid,
        "busy_bounds_valid": busy_bounds_valid,
        "fresh_server_counters_zero": snapshots_valid
        and metrics_before["tokens_predicted_total"] == 0
        and metrics_before["n_decode_total"] == 0
        and metrics_before["n_busy_slots_per_decode"] == 0,
        "counter_monotonic": snapshots_valid
        and predicted_delta is not None
        and decode_delta is not None
        and predicted_delta >= 0
        and decode_delta >= 0,
        "predicted_delta_256": snapshots_valid and predicted_delta == 2 * TOKEN_COUNT,
        "decode_delta_positive": snapshots_valid
        and decode_delta is not None
        and decode_delta >= TOKEN_COUNT,
        "ratio_proves_m2": is_finite_number(ratio)
        and OCCUPANCY_MINIMUM <= ratio <= 2,
        "busy_metric_proves_m2": is_finite_number(busy_after)
        and busy_after >= OCCUPANCY_MINIMUM,
    }
    return {
        "metrics_before": metrics_before,
        "metrics_after": metrics_after,
        "tokens_predicted_delta": predicted_delta,
        "llama_decode_calls_delta": decode_delta,
        "predicted_tokens_per_llama_decode": ratio,
        "n_busy_slots_per_decode_after": busy_after,
        "concurrent_minimum": OCCUPANCY_MINIMUM,
        "fields": fields,
        "passed": all(fields.values()),
    }


def validate_post_slots(slots: Any) -> dict[str, Any]:
    rows = slots if isinstance(slots, list) else []
    row_fields: list[dict[str, Any]] = []
    for slot in rows:
        slot = slot if isinstance(slot, dict) else {}
        params = slot.get("params")
        params = params if isinstance(params, dict) else {}
        fields = {
            "slot_id_valid": is_json_integer(slot.get("id"))
            and slot.get("id") in (0, 1),
            "idle": slot.get("is_processing") is False,
            "ctx_32768": integer_equals(slot.get("n_ctx"), 32768),
            "cache_zero": integer_equals(slot.get("n_prompt_tokens_cache"), 0),
            "backend_sampling_false": params.get("backend_sampling") is False,
            "temperature_zero": is_finite_number(params.get("temperature"))
            and params.get("temperature") == 0,
            "top_p_one": is_finite_number(params.get("top_p"))
            and params.get("top_p") == 1,
            "seed_one": integer_equals(params.get("seed"), 1),
            "ignore_eos_true": params.get("ignore_eos") is True,
            "stream_true": params.get("stream") is True,
            "n_predict_128": integer_equals(params.get("n_predict"), TOKEN_COUNT),
        }
        row_fields.append(
            {"slot_id": slot.get("id"), "fields": fields, "passed": all(fields.values())}
        )
    return {
        "rows": row_fields,
        "passed": len(row_fields) == 2
        and {row["slot_id"] for row in row_fields} == {0, 1}
        and all(row["passed"] for row in row_fields),
    }


def retain_stream(item: dict[str, Any], stream: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": item["case"]["id"],
        "slot_id": item["slot_id"],
        "prompt_sha256": sha256_text(item["prompt"]),
        "rendered_prompt_sha256": sha256_text(item["rendered"]),
        "token_ids": stream.get("token_ids"),
        "token_offsets_s": stream.get("token_offsets_s"),
        "content": stream.get("content"),
        "content_sha256": (
            sha256_text(stream["content"])
            if isinstance(stream.get("content"), str)
            else None
        ),
        "final": stream.get("final"),
        "connected_perf_s": stream.get("connected_perf_s"),
        "request_started_perf_s": stream.get("request_started_perf_s"),
        "request_ended_perf_s": stream.get("request_ended_perf_s"),
        "elapsed_s": stream.get("elapsed_s"),
    }


def duplicate_equality(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if len(rows) != 2:
        return {"applicable": True, "passed": False}
    left, right = rows
    left_final = left.get("final") if isinstance(left.get("final"), dict) else {}
    right_final = right.get("final") if isinstance(right.get("final"), dict) else {}
    left_timings = (
        left_final.get("timings") if isinstance(left_final.get("timings"), dict) else {}
    )
    right_timings = (
        right_final.get("timings")
        if isinstance(right_final.get("timings"), dict)
        else {}
    )
    token_ids_equal = (
        is_token_id_list(left.get("token_ids"), TOKEN_COUNT)
        and is_token_id_list(right.get("token_ids"), TOKEN_COUNT)
        and left["token_ids"] == right["token_ids"]
    )
    content_equal = (
        isinstance(left.get("content"), str)
        and isinstance(right.get("content"), str)
        and left["content"] == right["content"]
    )
    final_semantics_equal = all(
        left_value == right_value
        for left_value, right_value in (
            (left_final.get("stop_type"), right_final.get("stop_type")),
            (left_final.get("truncated"), right_final.get("truncated")),
            (left_timings.get("cache_n"), right_timings.get("cache_n")),
            (left_timings.get("predicted_n"), right_timings.get("predicted_n")),
            (left_timings.get("prompt_n"), right_timings.get("prompt_n")),
        )
    )
    return {
        "applicable": True,
        "token_ids_equal": token_ids_equal,
        "content_equal": content_equal,
        "final_semantics_equal_excluding_slot_and_rates": final_semantics_equal,
        "passed": token_ids_equal and content_equal and final_semantics_equal,
    }


def classify_scenario(
    scenario: str,
    prepared: list[dict[str, Any]],
    streams: list[dict[str, Any]],
    oracle_by_case: dict[str, dict[str, Any]],
    metrics_before: dict[str, Any],
    metrics_after: dict[str, Any],
    barrier_release_perf_s: Any,
    slots_before: list[dict[str, Any]],
    slots_after: list[dict[str, Any]],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for item, stream in zip(prepared, streams):
        row = retain_stream(item, stream)
        evidence_fields = validate_stream(item, stream)
        oracle_row = oracle_by_case.get(item["case"]["id"], {})
        oracle_tokens = oracle_row.get("token_ids")
        expected_prefix = oracle_tokens[:TOKEN_COUNT] if isinstance(oracle_tokens, list) else None
        comparison = compare_prefix(row["token_ids"], expected_prefix)
        row.update(
            {
                "evidence_fields": evidence_fields,
                "evidence_valid": all(evidence_fields.values()),
                "oracle_prefix_comparison": comparison,
                "exact_to_c1": comparison["exact_to_c1"],
            }
        )
        rows.append(row)
    starts = [row.get("request_started_perf_s") for row in rows]
    skew_valid = (
        len(starts) == 2
        and all(is_finite_number(value) for value in starts)
        and is_finite_number(barrier_release_perf_s)
        and all(value >= barrier_release_perf_s for value in starts)
    )
    request_skew_s = max(starts) - min(starts) if skew_valid else None
    synchronization = {
        "barrier_release_perf_s": barrier_release_perf_s,
        "request_skew_s": request_skew_s,
        "request_skew_limit_s": REQUEST_SKEW_LIMIT_S,
        "starts_after_barrier": skew_valid,
        "passed": skew_valid and request_skew_s <= REQUEST_SKEW_LIMIT_S,
    }
    occupancy = classify_occupancy(metrics_before, metrics_after)
    post_slots = validate_post_slots(slots_after)
    payload_fields = [validate_payload(item) for item in prepared]
    evidence_valid = (
        len(rows) == 2
        and all(row["evidence_valid"] for row in rows)
        and all(all(fields.values()) for fields in payload_fields)
        and synchronization["passed"]
        and occupancy["passed"]
        and post_slots["passed"]
    )
    exact_to_c1 = evidence_valid and all(row["exact_to_c1"] for row in rows)
    duplicate = (
        duplicate_equality(rows)
        if scenario in ("duplicate-a", "duplicate-b")
        else {"applicable": False, "passed": None}
    )
    return {
        "scenario": scenario,
        "case_assignment": [
            {"slot_id": item["slot_id"], "case_id": item["case"]["id"]}
            for item in prepared
        ],
        "payload_contract_fields": payload_fields,
        "slots_before": slots_before,
        "slots_after": slots_after,
        "post_slot_sampling_attestation": post_slots,
        "synchronization": synchronization,
        "metrics": {"before": metrics_before, "after": metrics_after},
        "occupancy_proof": occupancy,
        "rows": rows,
        "duplicate_equality": duplicate,
        "evidence_valid": evidence_valid,
        "exact_to_c1": exact_to_c1,
        "classification": (
            "VALID_EXACT_TO_C1"
            if exact_to_c1
            else "VALID_DIVERGENCE_FROM_C1"
            if evidence_valid
            else "INVALID_EVIDENCE"
        ),
    }


def main() -> int:
    global _FAILURE_OUTPUT
    _FAILURE_OUTPUT = None
    script_path = Path(__file__).resolve()
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenario", choices=tuple(SCENARIO_CASE_INDEXES), required=True
    )
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--prompt-builder", type=Path, required=True)
    parser.add_argument("--common-script", type=Path, required=True)
    parser.add_argument(
        "--capture-script",
        type=Path,
        default=script_path.with_name("capture-simultaneous-c2.py"),
    )
    parser.add_argument("--server-attestation", type=Path, required=True)
    parser.add_argument("--server-attestation-sha256", required=True)
    parser.add_argument("--oracle-json", type=Path, required=True)
    parser.add_argument("--oracle-sha256", required=True)
    parser.add_argument("--model-sha256", required=True)
    parser.add_argument("--runtime-sha256", required=True)
    parser.add_argument("--server-pid", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args()

    input_paths = {
        "matrix_script": script_path,
        "suite": args.suite,
        "prompt_builder": args.prompt_builder,
        "common_script": args.common_script,
        "capture_script": args.capture_script,
        "server_attestation": args.server_attestation,
        "sequential_oracle": args.oracle_json,
    }
    if args.out.exists():
        raise SystemExit(f"refusing to overwrite existing output: {args.out}")
    out_resolved = args.out.resolve()
    if any(out_resolved == path.resolve() for path in input_paths.values()):
        raise SystemExit("output path must not overwrite a protected input")
    for label, path in input_paths.items():
        if not path.is_file():
            raise SystemExit(f"required {label} input is not a file: {path}")
    _FAILURE_OUTPUT = args.out
    if args.timeout <= 0:
        raise SystemExit("--timeout must be positive")
    if args.server_pid <= 1:
        raise SystemExit("--server-pid must be greater than one")
    parsed = urlparse(args.base_url)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in ("127.0.0.1", "localhost")
        or parsed.port is None
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        raise SystemExit("--base-url must be a loopback HTTP origin with an explicit port")
    for label, value in (
        ("model", args.model_sha256),
        ("runtime", args.runtime_sha256),
        ("oracle", args.oracle_sha256),
        ("server-attestation", args.server_attestation_sha256),
    ):
        if not is_sha256(value):
            raise SystemExit(f"--{label}-sha256 must be a lowercase SHA-256 digest")

    input_before = snapshot_inputs(input_paths)
    if input_before["sequential_oracle"]["sha256"] != args.oracle_sha256:
        raise SystemExit("sequential c2 oracle SHA-256 mismatch")
    if (
        input_before["server_attestation"]["sha256"]
        != args.server_attestation_sha256
    ):
        raise SystemExit("server attestation SHA-256 mismatch")

    suite = json.loads(args.suite.read_text())
    oracle = json.loads(args.oracle_json.read_text())
    attestation = json.loads(args.server_attestation.read_text())
    if not all(isinstance(value, dict) for value in (suite, oracle, attestation)):
        raise SystemExit("suite, oracle, and attestation must be JSON objects")
    cases = load_short_cases(suite)
    suite_sha256 = input_before["suite"]["sha256"]
    oracle_fields, oracle_by_case = validate_oracle(
        oracle, suite_sha256, cases, args.model_sha256, args.runtime_sha256
    )
    server_fields = attest_server(
        attestation, oracle.get("run_identity") or {}, args.runtime_sha256
    )
    if not all(oracle_fields.values()):
        raise SystemExit("sealed sequential c2 oracle identity is invalid")
    if not all(server_fields.values()):
        raise SystemExit("server attestation does not match the sealed c2 identity")
    live_server_before = capture_live_server_binding(
        args.server_pid, parsed.port, args.runtime_sha256
    )
    if not live_server_before["passed"]:
        raise SystemExit("live server process does not own the attested endpoint")
    attestation_process_binding = bind_attestation_to_process(
        args.server_attestation, live_server_before
    )
    if not attestation_process_binding["passed"]:
        raise SystemExit(
            "server attestation was not generated during the owning live process"
        )

    common = load_module(args.common_script, "c2_token_matrix_common")
    prompt_builder = load_module(args.prompt_builder, "c2_token_matrix_prompt_builder")
    capture = load_module(args.capture_script, "c2_token_matrix_capture")
    base_url = args.base_url.rstrip("/")
    base_prepared = capture.prepare_cases(
        base_url, cases, prompt_builder.make_prompt, common, args.timeout, TOKEN_COUNT
    )
    prepared_gate = validate_base_prepared(base_prepared, cases)
    if not prepared_gate["passed"]:
        raise SystemExit("prepared short-pair identity or payload contract is invalid")
    prepared_by_case = {item["case"]["id"]: item for item in base_prepared}
    prompt_identity = validate_prompt_identity(prepared_by_case, oracle_by_case)
    if set(prompt_identity) != {case["id"] for case in cases} or not all(
        all(fields.values()) for fields in prompt_identity.values()
    ):
        raise SystemExit("live prompt/rendering identity drifted from the sealed oracle")

    indexes = SCENARIO_CASE_INDEXES[args.scenario]
    prepared = [
        assign_slot(base_prepared[index], slot) for slot, index in enumerate(indexes)
    ]
    slots_before = capture.capture_idle_slots(base_url, args.timeout)
    metrics_before = capture.capture_metrics(base_url, args.timeout)
    streams, release = capture.capture_streams(
        "concurrent", base_url, prepared, common, args.timeout
    )
    metrics_after = capture.capture_metrics(base_url, args.timeout)
    slots_after = capture.capture_idle_slots(base_url, args.timeout)
    scenario_result = classify_scenario(
        args.scenario,
        prepared,
        streams,
        oracle_by_case,
        metrics_before,
        metrics_after,
        release,
        slots_before,
        slots_after,
    )

    live_server_after = capture_live_server_binding(
        args.server_pid, parsed.port, args.runtime_sha256
    )
    live_server_binding = compare_live_server_bindings(
        live_server_before, live_server_after
    )
    if not live_server_binding["passed"]:
        scenario_result["evidence_valid"] = False
        scenario_result["exact_to_c1"] = False
        scenario_result["classification"] = "INVALID_EVIDENCE"

    input_after = snapshot_inputs(input_paths)
    input_integrity = compare_input_snapshots(input_before, input_after)
    evidence_valid = (
        input_integrity["passed"]
        and live_server_binding["passed"]
        and attestation_process_binding["passed"]
        and scenario_result["evidence_valid"]
    )
    exact_to_c1 = evidence_valid and scenario_result["exact_to_c1"]
    result = {
        "diagnostic_identity": {
            "diagnostic_only": True,
            "formal_c2_gate_modified": False,
            "performance_claim_eligible": False,
            "base_url": base_url,
            "model_sha256": args.model_sha256,
            "runtime_sha256": args.runtime_sha256,
            "suite_sha256": suite_sha256,
            "oracle_path": str(args.oracle_json),
            "oracle_sha256": args.oracle_sha256,
            "server_attestation_path": str(args.server_attestation),
            "server_attestation_sha256": args.server_attestation_sha256,
            "band": "short",
            "scenario": args.scenario,
            "max_tokens": TOKEN_COUNT,
            "temperature": 0,
            "top_p": 1,
            "seed": 1,
            "cache_prompt": False,
            "return_tokens": True,
            "ignore_eos": True,
            "backend_sampling_override": None,
            "c1_reference_definition": (
                "first 128 token IDs of the supplied sealed sequential-c2 oracle, "
                "matched by case ID rather than historical slot"
            ),
        },
        "identity_gate": {
            "oracle_fields": oracle_fields,
            "server_fields": server_fields,
            "prompt_fields": prompt_identity,
            "prepared_fields": prepared_gate,
            "passed": True,
        },
        "live_server_binding": live_server_binding,
        "attestation_process_binding": attestation_process_binding,
        "input_integrity": input_integrity,
        "scenario": scenario_result,
        "evidence_valid": evidence_valid,
        "exact_to_c1": exact_to_c1,
        "classification": (
            "VALID_EXACT_TO_C1"
            if exact_to_c1
            else "VALID_DIVERGENCE_FROM_C1"
            if evidence_valid
            else "INVALID_EVIDENCE"
        ),
        "exit_policy": (
            "Exit zero means evidence_valid=true. Token divergence is retained as "
            "valid diagnostic evidence and does not cause a nonzero exit."
        ),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "out": str(args.out),
                "evidence_valid": evidence_valid,
                "exact_to_c1": exact_to_c1,
                "classification": result["classification"],
            },
            sort_keys=True,
        )
    )
    return 0 if evidence_valid else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BaseException as exc:
        if _FAILURE_OUTPUT is not None and not _FAILURE_OUTPUT.exists():
            try:
                _FAILURE_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
                _FAILURE_OUTPUT.write_text(
                    json.dumps(
                        {
                            "evidence_valid": False,
                            "exact_to_c1": False,
                            "classification": "INVALID_EVIDENCE",
                            "error_type": type(exc).__name__,
                            "error": str(exc),
                        },
                        indent=2,
                        sort_keys=True,
                    )
                    + "\n"
                )
            except OSError:
                pass
        raise
