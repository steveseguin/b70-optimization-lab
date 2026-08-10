#!/usr/bin/env python3
"""Offline gates for the Qwen3.6 27B embedded-MTP VDR2 diagnostic.

This helper intentionally has no device or network code.  The shell lifecycle
runner uses it to derive provenance-preserving oracles and to classify already
captured server, metric, and exact-token artifacts.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import re
import statistics
import sys
import tempfile
from pathlib import Path
from typing import Any


MODEL_SHA_RE = re.compile(r"[0-9a-f]{64}")
METRIC_NAMES = {
    "draft_tokens": "llamacpp:spec_decode_num_draft_tokens_total",
    "accepted_tokens": "llamacpp:spec_decode_num_accepted_tokens_total",
    "drafts": "llamacpp:spec_decode_num_drafts_total",
    "accepted_per_pos": "llamacpp:spec_decode_num_accepted_tokens_per_pos_total",
}


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    return sha256_bytes(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    )


def read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON object {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON root is not an object: {path}")
    return value


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")
        temporary = Path(stream.name)
    temporary.replace(path)


def diff_paths(left: Any, right: Any, prefix: str = "") -> list[str]:
    if type(left) is not type(right):
        return [prefix or "<root>"]
    if isinstance(left, dict):
        result: list[str] = []
        for key in sorted(set(left) | set(right)):
            child = f"{prefix}.{key}" if prefix else key
            if key not in left or key not in right:
                result.append(child)
            else:
                result.extend(diff_paths(left[key], right[key], child))
        return result
    if isinstance(left, list):
        if len(left) != len(right):
            return [prefix or "<root>"]
        result = []
        for index, (lhs, rhs) in enumerate(zip(left, right)):
            child = f"{prefix}[{index}]"
            result.extend(diff_paths(lhs, rhs, child))
        return result
    return [] if left == right else [prefix or "<root>"]


def derive_oracle(args: argparse.Namespace) -> int:
    if not MODEL_SHA_RE.fullmatch(args.model_sha256):
        raise ValueError("new model SHA-256 must be lowercase hexadecimal")
    if not MODEL_SHA_RE.fullmatch(args.expected_old_model_sha256):
        raise ValueError("old model SHA-256 must be lowercase hexadecimal")
    if not MODEL_SHA_RE.fullmatch(args.expected_source_sha256):
        raise ValueError("source SHA-256 must be lowercase hexadecimal")
    observed_source_sha = sha256_file(args.source)
    if observed_source_sha != args.expected_source_sha256:
        raise ValueError(
            "source oracle SHA-256 mismatch: "
            f"expected {args.expected_source_sha256}, got {observed_source_sha}"
        )

    source = read_object(args.source)
    identity = source.get("run_identity")
    if not isinstance(identity, dict):
        raise ValueError("source oracle has no run_identity object")
    if identity.get("model_sha256") != args.expected_old_model_sha256:
        raise ValueError("source oracle model identity is not the sealed trunk SHA-256")
    if (source.get("intrinsic_gate") or {}).get("passed") is not True:
        raise ValueError("source oracle intrinsic gate is not passed")
    if (source.get("oracle_comparison") or {}).get("status") != "BASELINE_CAPTURE_READY":
        raise ValueError("source oracle is not a baseline capture")
    rows = source.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("source oracle has no rows")

    derived = copy.deepcopy(source)
    derived["run_identity"]["model_sha256"] = args.model_sha256
    changed = diff_paths(source, derived)
    if changed != ["run_identity.model_sha256"]:
        raise ValueError(f"unexpected semantic oracle delta: {changed}")

    source_projection = copy.deepcopy(source)
    derived_projection = copy.deepcopy(derived)
    source_projection["run_identity"].pop("model_sha256")
    derived_projection["run_identity"].pop("model_sha256")
    source_projection_sha = canonical_sha256(source_projection)
    derived_projection_sha = canonical_sha256(derived_projection)
    if source_projection_sha != derived_projection_sha:
        raise ValueError("oracle projections differ after removing model identity")

    atomic_write_json(args.output, derived)
    derived_sha = sha256_file(args.output)
    proof = {
        "passed": True,
        "policy": "model-identity-only semantic oracle derivation",
        "source_path": str(args.source.resolve()),
        "source_sha256": observed_source_sha,
        "derived_path": str(args.output.resolve()),
        "derived_sha256": derived_sha,
        "changed_paths": changed,
        "old_model_sha256": args.expected_old_model_sha256,
        "new_model_sha256": args.model_sha256,
        "source_projection_without_model_sha256": source_projection_sha,
        "derived_projection_without_model_sha256": derived_projection_sha,
    }
    atomic_write_json(args.proof, proof)
    return 0


def parse_prometheus(path: Path) -> dict[tuple[str, tuple[tuple[str, str], ...]], float]:
    result: dict[tuple[str, tuple[tuple[str, str], ...]], float] = {}
    line_re = re.compile(
        r'^([^\s{]+)(?:\{([^}]*)\})?\s+([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)$'
    )
    label_re = re.compile(r'([A-Za-z_][A-Za-z0-9_]*)="((?:[^"\\]|\\.)*)"')
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = line_re.fullmatch(line)
        if not match:
            continue
        name, labels_raw, value_raw = match.groups()
        labels: list[tuple[str, str]] = []
        if labels_raw:
            labels = [(key, bytes(value, "utf-8").decode("unicode_escape"))
                      for key, value in label_re.findall(labels_raw)]
        key = (name, tuple(sorted(labels)))
        if key in result:
            raise ValueError(f"duplicate Prometheus sample for {name}")
        result[key] = float(value_raw)
    return result


def metric_value(
    metrics: dict[tuple[str, tuple[tuple[str, str], ...]], float], name: str
) -> float:
    values = [
        (labels, value)
        for (metric, labels), value in metrics.items()
        if metric == name
    ]
    if len(values) != 1 or values[0][0]:
        raise ValueError(f"metric {name} must be present exactly once without labels")
    return values[0][1]


def position_values(
    metrics: dict[tuple[str, tuple[tuple[str, str], ...]], float]
) -> dict[int, float]:
    result: dict[int, float] = {}
    for (name, labels), value in metrics.items():
        if name != METRIC_NAMES["accepted_per_pos"]:
            continue
        label_map = dict(labels)
        if set(label_map) != {"position"} or not label_map["position"].isdigit():
            raise ValueError("accepted-per-position metric has invalid labels")
        position = int(label_map["position"])
        if position in result:
            raise ValueError(f"duplicate accepted position {position}")
        result[position] = value
    return result


def integral_delta(before: float, after: float, name: str) -> int:
    delta = after - before
    if not math.isfinite(delta) or delta < 0 or not delta.is_integer():
        raise ValueError(f"counter {name} has invalid delta {delta}")
    return int(delta)


def gate_metrics(args: argparse.Namespace) -> int:
    before = parse_prometheus(args.before)
    after = parse_prometheus(args.after)
    core = {}
    checks: dict[str, bool] = {}
    for short, full in (
        ("draft_tokens", METRIC_NAMES["draft_tokens"]),
        ("accepted_tokens", METRIC_NAMES["accepted_tokens"]),
        ("drafts", METRIC_NAMES["drafts"]),
    ):
        before_value = metric_value(before, full)
        after_value = metric_value(after, full)
        checks[f"{short}_starts_zero"] = before_value == 0
        core[short] = integral_delta(before_value, after_value, full)

    before_positions = position_values(before)
    after_positions = position_values(after)
    all_positions = sorted(set(before_positions) | set(after_positions))
    positions = {
        position: integral_delta(
            before_positions.get(position, 0.0),
            after_positions.get(position, 0.0),
            f"accepted_per_pos[{position}]",
        )
        for position in all_positions
    }
    checks["positions_start_absent"] = not before_positions

    draft_tokens = core["draft_tokens"]
    accepted = core["accepted_tokens"]
    drafts = core["drafts"]
    if args.mode == "control":
        checks.update(
            {
                "all_spec_counters_zero": draft_tokens == accepted == drafts == 0,
                "accepted_positions_absent": not after_positions,
            }
        )
    else:
        checks.update(
            {
                "drafts_positive": drafts > 0,
                "draft_tokens_positive": draft_tokens > 0,
                "accepted_positive": accepted > 0,
                "accepted_le_draft_tokens": 0 < accepted <= draft_tokens,
                "draft_tokens_ge_drafts": draft_tokens >= drafts,
                "draft_tokens_le_nmax_times_drafts": draft_tokens <= 3 * drafts,
                "positions_exactly_0_1_2": set(after_positions) == {0, 1, 2},
                "positions_monotone": (
                    set(after_positions) == {0, 1, 2}
                    and positions[0] >= positions[1] >= positions[2] >= 0
                ),
                "positions_each_le_drafts": all(value <= drafts for value in positions.values()),
                "positions_sum_to_accepted": sum(positions.values()) == accepted,
            }
        )

    result = {
        "mode": args.mode,
        "before_path": str(args.before.resolve()),
        "after_path": str(args.after.resolve()),
        "counters": core,
        "accepted_per_position": {str(key): value for key, value in positions.items()},
        "acceptance_ratio": accepted / draft_tokens if draft_tokens else None,
        "accepted_per_verification": accepted / drafts if drafts else None,
        "effective_tokens_per_target_verification": 1 + accepted / drafts if drafts else None,
        "checks": checks,
        "passed": all(checks.values()),
    }
    atomic_write_json(args.output, result)
    return 0 if result["passed"] else 1


def positive_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value > 0
    )


def median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def native_timing_valid(timing: dict[str, Any], expected_tokens: int) -> bool:
    predicted_n = timing.get("predicted_n")
    predicted_ms = timing.get("predicted_ms")
    predicted_per_second = timing.get("predicted_per_second")
    return (
        isinstance(predicted_n, int)
        and not isinstance(predicted_n, bool)
        and predicted_n == expected_tokens
        and positive_number(predicted_ms)
        and positive_number(predicted_per_second)
        and math.isclose(
            float(predicted_per_second),
            1000.0 * predicted_n / float(predicted_ms),
            rel_tol=1e-6,
            abs_tol=1e-6,
        )
    )


def gate_exact(args: argparse.Namespace) -> int:
    data = read_object(args.input)
    identity = data.get("run_identity") or {}
    rows = data.get("rows") or []
    intrinsic = data.get("intrinsic_gate") or {}
    oracle = data.get("oracle_comparison") or {}
    canary = data.get("post_512_canary") or {}
    checks: dict[str, bool] = {
        "intrinsic_passed": intrinsic.get("passed") is True,
        "oracle_exact": oracle.get("status") == "PASS_ORACLE_EXACT" and oracle.get("passed") is True,
        "canary_exact": canary.get("passed") is True,
        "two_short_rows": isinstance(rows, list) and len(rows) == 2,
        "model_identity": identity.get("model_sha256") == args.model_sha256,
        "runtime_identity": identity.get("runtime_sha256") == args.runtime_sha256,
        "short_band": identity.get("band") == "short",
        "ctx_32768": identity.get("ctx_size") == 32768,
        "max_tokens_512": identity.get("max_tokens") == 512,
        "cache_prompt_false": identity.get("cache_prompt") is False,
        "exact_count_required": identity.get("require_exact_token_count") is True,
        "full_512_required": identity.get("require_full_512_metric") is True,
        "post_canary_required": identity.get("require_post_512_canary") is True,
        "ignore_eos": identity.get("ignore_eos") is True,
        "slot_zero": identity.get("slot_id") == 0,
        "temperature_zero": identity.get("temperature") == 0,
        "top_p_one": identity.get("top_p") == 1,
        "f16_kv": identity.get("cache_type_k") == identity.get("cache_type_v") == "f16",
        "vdr2_selectors": (
            identity.get("sycl_dnn_enabled") == 0
            and identity.get("sycl_opt_enabled") == 1
        ),
    }
    row_checks = []
    interval_values: list[float] = []
    full_values: list[float] = []
    stream_native_values: list[float] = []
    replay_native_values: list[float] = []
    ttft_values: list[float] = []
    per_prompt: dict[str, dict[str, float]] = {}
    total_request_draft = 0
    total_request_accepted = 0
    for row in rows if isinstance(rows, list) else []:
        timing_pairs = [row.get("stream_timings") or {}, row.get("timings") or {}]
        interval = (row.get("primary_metric") or {}).get("tok_s")
        full = (row.get("full_512_metric") or {}).get("tok_s")
        stream_native = timing_pairs[0].get("predicted_per_second")
        replay_native = timing_pairs[1].get("predicted_per_second")
        ttft = row.get("ttft_s")
        request_draft_fields = []
        for timing in timing_pairs:
            draft_n = timing.get("draft_n")
            accepted_n = timing.get("draft_n_accepted")
            if isinstance(draft_n, int) and isinstance(accepted_n, int):
                total_request_draft += draft_n
                total_request_accepted += accepted_n
                request_draft_fields.append(draft_n > 0 and 0 <= accepted_n <= draft_n)
            else:
                request_draft_fields.append(False)
        row_ok = {
            "token_count_512": row.get("token_count") == 512,
            "cache_zero": row.get("cache_n") == 0 and row.get("stream_cache_n") == 0,
            "primary_99_intervals": (row.get("primary_metric") or {}).get("interval_count") == 99,
            "full_511_intervals": (row.get("full_512_metric") or {}).get("interval_count") == 511,
            "positive_rates": all(positive_number(value) for value in (interval, full, stream_native, replay_native)),
            "positive_ttft": positive_number(ttft),
            "native_timing_arithmetic": all(
                native_timing_valid(timing, 512) for timing in timing_pairs
            ),
            "draft_fields": (
                all(request_draft_fields)
                if args.mode == "mtp3"
                else all(
                    "draft_n" not in timing and "draft_n_accepted" not in timing
                    for timing in timing_pairs
                )
            ),
        }
        row_checks.append({"prompt_id": row.get("prompt_id"), "checks": row_ok, "passed": all(row_ok.values())})
        if all(positive_number(value) for value in (interval, full, stream_native, replay_native, ttft)):
            interval_values.append(float(interval))
            full_values.append(float(full))
            stream_native_values.append(float(stream_native))
            replay_native_values.append(float(replay_native))
            ttft_values.append(float(ttft))
            if isinstance(row.get("prompt_id"), str):
                per_prompt[row["prompt_id"]] = {
                    "interval_tok_s": float(interval),
                    "full_512_tok_s": float(full),
                    "stream_native_tok_s": float(stream_native),
                    "replay_native_tok_s": float(replay_native),
                    "ttft_s": float(ttft),
                }
    checks["all_rows_pass"] = len(row_checks) == 2 and all(item["passed"] for item in row_checks)
    if args.mode == "mtp3":
        checks["request_drafts_positive"] = total_request_draft > 0
        checks["request_acceptance_positive"] = total_request_accepted > 0
        canary_timing = canary.get("timings") or {}
        checks["canary_draft_fields"] = (
            isinstance(canary_timing.get("draft_n"), int)
            and canary_timing["draft_n"] > 0
            and isinstance(canary_timing.get("draft_n_accepted"), int)
            and 0 <= canary_timing["draft_n_accepted"] <= canary_timing["draft_n"]
        )
        canary_draft = canary_timing.get("draft_n", 0)
        canary_accepted = canary_timing.get("draft_n_accepted", 0)
    else:
        checks["request_drafts_absent"] = total_request_draft == 0
        canary_timing = canary.get("timings") or {}
        checks["canary_draft_fields_absent"] = (
            "draft_n" not in canary_timing and "draft_n_accepted" not in canary_timing
        )
        canary_draft = 0
        canary_accepted = 0

    result = {
        "mode": args.mode,
        "input": str(args.input.resolve()),
        "checks": checks,
        "rows": row_checks,
        "per_prompt": per_prompt,
        "summary": {
            "interval_tok_s_median": median(interval_values),
            "full_512_tok_s_median": median(full_values),
            "stream_native_tok_s_median": median(stream_native_values),
            "replay_native_tok_s_median": median(replay_native_values),
            "ttft_s_median": median(ttft_values),
            "request_draft_tokens": total_request_draft,
            "request_accepted_tokens": total_request_accepted,
            "all_request_draft_tokens": total_request_draft + canary_draft,
            "all_request_accepted_tokens": total_request_accepted + canary_accepted,
        },
        "passed": all(checks.values()),
    }
    atomic_write_json(args.output, result)
    return 0 if result["passed"] else 1


def has_argv_pair(argv: list[str], option: str, value: str) -> bool:
    return any(
        argv[index] == option and argv[index + 1] == value
        for index in range(len(argv) - 1)
    )


def gate_server(args: argparse.Namespace) -> int:
    text = args.log.read_text(errors="replace")
    identity = read_object(args.identity)
    argv = identity.get("argv")
    if not isinstance(argv, list) or not all(isinstance(value, str) for value in argv):
        raise ValueError("server identity argv is not a string array")
    forbidden_options = {
        "--spec-draft-model", "-md", "--model-draft", "--spec-draft-hf",
        "-hfd", "-hfrd", "--hf-repo-draft",
    }
    model_load_path = identity.get("model_load_path")
    model_arguments = [
        argv[index + 1]
        for index in range(len(argv) - 1)
        if argv[index] == "-m"
    ]
    common_pairs = {
        "-dev": "SYCL0", "-ngl": "all", "-c": "32768", "-np": "1",
        "-b": "1024", "-ub": "1024", "-t": "8", "--threads-http": "6",
        "--poll": "50", "-lv": "4", "-ctk": "f16", "-ctv": "f16",
        "-fa": "on", "-fit": "on", "-fitt": "1024",
        "--reasoning": "off", "--ctx-checkpoints": "0", "--cache-ram": "0",
    }
    common_flags = {
        "--no-cache-idle-slots", "--no-context-shift", "--slots", "--metrics",
        "--jinja", "--no-kv-unified", "--cont-batching",
    }
    fit_log_lines = [
        line.strip()
        for line in text.splitlines()
        if "common_params_fit_impl:" in line
    ]
    fit_no_change_re = re.compile(
        r".*\bcommon_params_fit_impl:\s+will leave\s+(\d+)\s+>=\s+(\d+) MiB "
        r"of free device memory, no changes needed"
    )
    fit_no_change_matches = [
        match
        for line in fit_log_lines
        if (match := fit_no_change_re.fullmatch(line)) is not None
    ]
    fit_adjustment_lines = [
        line
        for line in fit_log_lines
        if re.search(
            r"adjust|reduc|cannot meet|trying to fit|set ngl|moved to system|overflow",
            line,
            re.IGNORECASE,
        )
    ]
    def logged_batch_values(fragment: str, name: str) -> list[int]:
        return [
            int(value)
            for value in re.findall(
                rf"\b{re.escape(name)}\s+=\s+(\d+)\s*$",
                fragment,
                re.MULTILINE,
            )
        ]

    n_batch_values = logged_batch_values(text, "n_batch")
    n_ubatch_values = logged_batch_values(text, "n_ubatch")
    mtp_context_marker = "creating MTP draft context against the target model"
    mtp_context_offset = text.find(mtp_context_marker)
    if args.mode == "mtp3" and mtp_context_offset >= 0:
        target_context_text = text[:mtp_context_offset]
        draft_context_text = text[mtp_context_offset + len(mtp_context_marker):]
    else:
        target_context_text = text
        draft_context_text = ""
    target_n_batch_values = logged_batch_values(target_context_text, "n_batch")
    target_n_ubatch_values = logged_batch_values(target_context_text, "n_ubatch")
    draft_n_batch_values = logged_batch_values(draft_context_text, "n_batch")
    draft_n_ubatch_values = logged_batch_values(draft_context_text, "n_ubatch")
    checks: dict[str, bool] = {
        "identity_mode": identity.get("mode") == args.mode,
        "model_fd_path": bool(re.fullmatch(r"/proc/self/fd/[0-9]+", str(model_load_path or ""))),
        "one_exact_model_argument": model_arguments == [model_load_path],
        "common_pairs": all(has_argv_pair(argv, key, value) for key, value in common_pairs.items()),
        "common_flags": common_flags.issubset(set(argv)),
        "no_sidecar_or_draft_hf": not forbidden_options.intersection(argv),
        "block_count_65": bool(re.search(r"qwen35\.block_count\s+u32\s+= 65\b", text)),
        "trunk_layers_64": bool(re.search(r"n_layer\s+= 64\b", text)),
        "all_layers_65": bool(re.search(r"n_layer_all\s+= 65\b", text)),
        "one_nextn_layer": bool(re.search(r"n_layer_nextn\s+= 1\b", text)),
        "full_offload_66": "offloaded 66/66 layers to GPU" in text,
        "ctx_32768": bool(re.search(r"n_ctx\s+= 32768\b", text)),
        "runtime_n_batch_1024": bool(n_batch_values) and all(
            value == 1024 for value in n_batch_values
        ),
        "runtime_n_ubatch_1024": bool(n_ubatch_values) and all(
            value == 1024 for value in n_ubatch_values
        ),
        "one_slot": bool(re.search(r"initializing, n_slots = 1, n_ctx_slot = 32768, kv_unified = 'false'", text)),
        "fit_no_changes_exact": (
            len(fit_no_change_matches) == 1
            and not fit_adjustment_lines
            and int(fit_no_change_matches[0].group(2)) >= 1024
            and int(fit_no_change_matches[0].group(1))
            >= int(fit_no_change_matches[0].group(2))
        ),
        "no_fatal_runtime_error": not re.search(
            r"UR_RESULT_ERROR_DEVICE_LOST|ZE_RESULT_ERROR_DEVICE_LOST|out of memory|segmentation fault|core dumped|Aborted|failed to create MTP context",
            text,
            re.IGNORECASE,
        ),
        "no_cpu_runtime_fallback": not re.search(
            r"offloaded (?!66/66)\d+/66 layers to GPU|using CPU for layer|failed to offload|backend offload failed.*CPU sampler|using CPU sampler",
            text,
            re.IGNORECASE,
        ),
    }
    if args.mode == "control":
        checks.update(
            {
                "spec_none_argv": has_argv_pair(argv, "--spec-type", "none"),
                "no_spec_draft_options": not any(value.startswith("--spec-draft-") for value in argv),
                "spec_disabled_log": "no implementations specified for speculative decoding" in text,
                "no_mtp_context": "creating MTP draft context against the target model" not in text,
            }
        )
    else:
        required_spec_pairs = {
            "--spec-type": "draft-mtp",
            "--spec-draft-n-max": "3",
            "--spec-draft-n-min": "0",
            "--spec-draft-p-split": "0.10",
            "--spec-draft-p-min": "0.00",
            "--spec-draft-device": "SYCL0",
            "--spec-draft-ngl": "all",
            "--spec-draft-type-k": "f16",
            "--spec-draft-type-v": "f16",
        }
        checks.update(
            {
                "mtp3_pairs": all(has_argv_pair(argv, key, value) for key, value in required_spec_pairs.items()),
                "backend_sampling_explicit": "--spec-draft-backend-sampling" in argv,
                "embedded_mtp_context": mtp_context_offset >= 0,
                "no_separate_draft_load": "loading draft model" not in text,
                "target_context_n_batch_1024": bool(target_n_batch_values)
                and all(value == 1024 for value in target_n_batch_values),
                "target_context_n_ubatch_1024": bool(target_n_ubatch_values)
                and all(value == 1024 for value in target_n_ubatch_values),
                "draft_context_n_batch_1024": bool(draft_n_batch_values)
                and all(value == 1024 for value in draft_n_batch_values),
                "draft_context_n_ubatch_1024": bool(draft_n_ubatch_values)
                and all(value == 1024 for value in draft_n_ubatch_values),
                "mtp_context_on_sycl": (
                    mtp_context_offset >= 0
                    and bool(re.search(r"SYCL0\s+KV buffer size", text[mtp_context_offset:]))
                ),
            }
        )
    result = {
        "mode": args.mode,
        "log": str(args.log.resolve()),
        "identity": str(args.identity.resolve()),
        "checks": checks,
        "fit_headroom_pairs_mib": [
            [int(match.group(1)), int(match.group(2))]
            for match in fit_no_change_matches
        ],
        "fit_log_lines": fit_log_lines,
        "fit_adjustment_lines": fit_adjustment_lines,
        "logged_n_batch_values": n_batch_values,
        "logged_n_ubatch_values": n_ubatch_values,
        "target_context_n_batch_values": target_n_batch_values,
        "target_context_n_ubatch_values": target_n_ubatch_values,
        "draft_context_n_batch_values": draft_n_batch_values,
        "draft_context_n_ubatch_values": draft_n_ubatch_values,
        "passed": all(checks.values()),
    }
    atomic_write_json(args.output, result)
    return 0 if result["passed"] else 1


def ratio(numerator: float, denominator: float) -> float:
    if not positive_number(numerator) or not positive_number(denominator):
        raise ValueError("cannot calculate ratio from non-positive value")
    return numerator / denominator


def compare_arms(args: argparse.Namespace) -> int:
    control = read_object(args.control_exact_gate)
    candidate = read_object(args.candidate_exact_gate)
    control_metrics = read_object(args.control_metrics_gate)
    candidate_metrics = read_object(args.candidate_metrics_gate)
    evidence_checks = {
        "control_exact": control.get("passed") is True,
        "candidate_exact": candidate.get("passed") is True,
        "control_counters": control_metrics.get("passed") is True,
        "candidate_counters": candidate_metrics.get("passed") is True,
        "control_exact_mode": control.get("mode") == "control",
        "candidate_exact_mode": candidate.get("mode") == "mtp3",
        "control_counter_mode": control_metrics.get("mode") == "control",
        "candidate_counter_mode": candidate_metrics.get("mode") == "mtp3",
    }
    if all(evidence_checks.values()):
        evidence_checks.update(
            {
                "control_draft_counter_matches_responses": (
                    control_metrics.get("counters", {}).get("draft_tokens")
                    == control.get("summary", {}).get("all_request_draft_tokens")
                ),
                "control_accepted_counter_matches_responses": (
                    control_metrics.get("counters", {}).get("accepted_tokens")
                    == control.get("summary", {}).get("all_request_accepted_tokens")
                ),
                "candidate_draft_counter_matches_responses": (
                    candidate_metrics.get("counters", {}).get("draft_tokens")
                    == candidate.get("summary", {}).get("all_request_draft_tokens")
                ),
                "candidate_accepted_counter_matches_responses": (
                    candidate_metrics.get("counters", {}).get("accepted_tokens")
                    == candidate.get("summary", {}).get("all_request_accepted_tokens")
                ),
            }
        )
    if not all(evidence_checks.values()):
        result = {
            "evidence_checks": evidence_checks,
            "evidence_passed": False,
            "classification": "INVALID_EVIDENCE",
            "advance": False,
        }
        atomic_write_json(args.output, result)
        return 1

    csum = control["summary"]
    msum = candidate["summary"]
    interval_ratio = ratio(msum["interval_tok_s_median"], csum["interval_tok_s_median"])
    full_ratio = ratio(msum["full_512_tok_s_median"], csum["full_512_tok_s_median"])
    native_ratio = ratio(msum["stream_native_tok_s_median"], csum["stream_native_tok_s_median"])
    replay_native_ratio = ratio(msum["replay_native_tok_s_median"], csum["replay_native_tok_s_median"])
    official_interval_ratio = msum["interval_tok_s_median"] / args.official_interval_tok_s
    official_native_ratio = msum["stream_native_tok_s_median"] / args.official_native_tok_s
    ttft_ratio = ratio(msum["ttft_s_median"], csum["ttft_s_median"])
    shared_prompts = sorted(set(control["per_prompt"]) & set(candidate["per_prompt"]))
    per_prompt_ratios = {
        prompt: ratio(
            candidate["per_prompt"][prompt]["interval_tok_s"],
            control["per_prompt"][prompt]["interval_tok_s"],
        )
        for prompt in shared_prompts
    }
    acceptance = candidate_metrics.get("acceptance_ratio")
    accepted_per_verify = candidate_metrics.get("accepted_per_verification")
    ratio_disagreement = abs(interval_ratio - native_ratio)

    advance_checks = {
        "candidate_interval_at_least_18": msum["interval_tok_s_median"] >= 18.0,
        "candidate_native_at_least_18": msum["stream_native_tok_s_median"] >= 18.0,
        "interval_gain_at_least_8pct": interval_ratio >= 1.08,
        "full_gain_at_least_8pct": full_ratio >= 1.08,
        "native_gain_at_least_8pct": native_ratio >= 1.08,
        "replay_native_gain_at_least_8pct": replay_native_ratio >= 1.08,
        "official_interval_gain_at_least_8pct": official_interval_ratio >= 1.08,
        "official_native_gain_at_least_8pct": official_native_ratio >= 1.08,
        "each_prompt_at_least_5pct": len(per_prompt_ratios) == 2 and all(value >= 1.05 for value in per_prompt_ratios.values()),
        "ttft_regression_at_most_10pct": ttft_ratio <= 1.10,
        "acceptance_at_least_045": positive_number(acceptance) and acceptance >= 0.45,
        "accepted_per_verify_at_least_125": positive_number(accepted_per_verify) and accepted_per_verify >= 1.25,
        "interval_native_ratio_disagreement_at_most_0035": ratio_disagreement <= 0.035,
    }
    followup_checks = {
        "interval_gain_at_least_5pct": interval_ratio >= 1.05,
        "native_gain_at_least_5pct": native_ratio >= 1.05,
        "each_prompt_at_least_3pct": len(per_prompt_ratios) == 2 and all(value >= 1.03 for value in per_prompt_ratios.values()),
        "ttft_regression_at_most_10pct": ttft_ratio <= 1.10,
        "acceptance_at_least_035": positive_number(acceptance) and acceptance >= 0.35,
        "accepted_per_verify_at_least_100": positive_number(accepted_per_verify) and accepted_per_verify >= 1.0,
    }
    advance = all(advance_checks.values())
    bounded_followup = not advance and all(followup_checks.values())
    classification = (
        "ADVANCE_FULL_VALIDATION"
        if advance
        else "ONE_BOUNDED_NMAX_PMIN_FOLLOWUP"
        if bounded_followup
        else "STOP_NO_MTP_WIN"
    )
    result = {
        "evidence_checks": evidence_checks,
        "evidence_passed": True,
        "classification": classification,
        "advance": advance,
        "bounded_followup": bounded_followup,
        "official_reference": {
            "interval_tok_s": args.official_interval_tok_s,
            "native_tok_s": args.official_native_tok_s,
        },
        "control": csum,
        "candidate": msum,
        "ratios": {
            "interval_candidate_over_control": interval_ratio,
            "full_512_candidate_over_control": full_ratio,
            "stream_native_candidate_over_control": native_ratio,
            "replay_native_candidate_over_control": replay_native_ratio,
            "interval_candidate_over_official": official_interval_ratio,
            "stream_native_candidate_over_official": official_native_ratio,
            "ttft_candidate_over_control": ttft_ratio,
            "interval_native_ratio_disagreement": ratio_disagreement,
            "per_prompt_interval_candidate_over_control": per_prompt_ratios,
        },
        "acceptance": {
            "accepted_over_drafted": acceptance,
            "accepted_per_verification": accepted_per_verify,
            "effective_tokens_per_target_verification": candidate_metrics.get(
                "effective_tokens_per_target_verification"
            ),
        },
        "advance_checks": advance_checks,
        "bounded_followup_checks": followup_checks,
        "measurement_note": (
            "The policy 99-interval metric is retained, but native server timing "
            "is co-gated because accepted speculative tokens are emitted in bursts."
        ),
    }
    atomic_write_json(args.output, result)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    derive = sub.add_parser("derive-oracle")
    derive.add_argument("--source", type=Path, required=True)
    derive.add_argument("--expected-source-sha256", required=True)
    derive.add_argument("--expected-old-model-sha256", required=True)
    derive.add_argument("--model-sha256", required=True)
    derive.add_argument("--output", type=Path, required=True)
    derive.add_argument("--proof", type=Path, required=True)
    derive.set_defaults(handler=derive_oracle)

    metrics = sub.add_parser("gate-metrics")
    metrics.add_argument("--mode", choices=("control", "mtp3"), required=True)
    metrics.add_argument("--before", type=Path, required=True)
    metrics.add_argument("--after", type=Path, required=True)
    metrics.add_argument("--output", type=Path, required=True)
    metrics.set_defaults(handler=gate_metrics)

    exact = sub.add_parser("gate-exact")
    exact.add_argument("--mode", choices=("control", "mtp3"), required=True)
    exact.add_argument("--input", type=Path, required=True)
    exact.add_argument("--model-sha256", required=True)
    exact.add_argument("--runtime-sha256", required=True)
    exact.add_argument("--output", type=Path, required=True)
    exact.set_defaults(handler=gate_exact)

    server = sub.add_parser("gate-server")
    server.add_argument("--mode", choices=("control", "mtp3"), required=True)
    server.add_argument("--log", type=Path, required=True)
    server.add_argument("--identity", type=Path, required=True)
    server.add_argument("--output", type=Path, required=True)
    server.set_defaults(handler=gate_server)

    compare = sub.add_parser("compare-arms")
    compare.add_argument("--control-exact-gate", type=Path, required=True)
    compare.add_argument("--candidate-exact-gate", type=Path, required=True)
    compare.add_argument("--control-metrics-gate", type=Path, required=True)
    compare.add_argument("--candidate-metrics-gate", type=Path, required=True)
    compare.add_argument("--official-interval-tok-s", type=float, default=16.587155022411466)
    compare.add_argument("--official-native-tok-s", type=float, default=16.621315139033597)
    compare.add_argument("--output", type=Path, required=True)
    compare.set_defaults(handler=compare_arms)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.handler(args)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"embedded-MTP gate failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
