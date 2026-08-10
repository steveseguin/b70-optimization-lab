#!/usr/bin/env python3
"""Offline gates for the embedded-MTP middle/near-32K split crossover.

The live wrapper owns device and process lifecycle.  This module only reads
captured artifacts, checks their frozen identities, and classifies matched
same-card control/MTP pairs.  It deliberately does not accept the historical
short oracle: cross-band quality is bound to fresh controls from the same
integrated model artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import re
import statistics
import tempfile
from pathlib import Path
from typing import Any


MODEL_SHA256 = "9408dcb356cc061a05c139e5647cbde0698ff980c6a69f7fc214e9989f86cfa8"
RUNTIME_SHA256 = "1a093f09122ceb2851157042c2bbc6281ddb9d4e2de50137502890f9b52fa7d7"
RUNTIME_PATH = "/mnt/fast-ai/runtime/llama.cpp-15586e2d-qwen27-vdr2-hybrid/llama-server"
RUNTIME_MANIFEST_SHA256 = "4119790a79c55d158e7257d4fa0d95be0ca34639807c1a71ce87b60d6fdc1b49"
RUNTIME_COMMIT = "15586e2d7165570fb3aa7c26e0d442e289ef69de"
MODEL_REPOSITORY = "unsloth/Qwen3.6-27B-MTP-GGUF"
MODEL_REVISION = "5cb35eb3dcbf52dbce5f87dbc64df6aaffadcace"
SUITE_SHA256 = "053523440e4a23d7f772dec5025fe4831ba33c0a8eaba76795e4ee76718860af"
PROMPT_BUILDER_SHA256 = "2286c9fd1ef59136a92a857be2992b31e0ff3bc844c7489239ab8f76f515cf72"
EXPECTED_BANDS = {"middle": 128, "near32k": 1024}
EXPECTED_ASSIGNMENTS = {
    (1, 0): ("middle", "control"),
    (1, 1): ("middle", "mtp3"),
    (1, 2): ("near32k", "control"),
    (1, 3): ("near32k", "mtp3"),
    (2, 0): ("middle", "mtp3"),
    (2, 1): ("middle", "control"),
    (2, 2): ("near32k", "mtp3"),
    (2, 3): ("near32k", "control"),
}
EXPECTED_ASSIGNMENT_OBJECTS = [
    {
        "wave": wave,
        "gpu": gpu,
        "band": band,
        "mode": mode,
        "ubatch": EXPECTED_BANDS[band],
    }
    for (wave, gpu), (band, mode) in EXPECTED_ASSIGNMENTS.items()
]
METRIC_NAMES = {
    "prompt_tokens": "llamacpp:prompt_tokens_total",
    "predicted_tokens": "llamacpp:tokens_predicted_total",
    "requests_processing": "llamacpp:requests_processing",
    "requests_deferred": "llamacpp:requests_deferred",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def atomic_write_json(path: Path, value: Any) -> None:
    if path.exists():
        raise ValueError(f"refusing to overwrite output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
        temporary = Path(stream.name)
    temporary.replace(path)


def read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(), parse_constant=_reject_json_constant)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON object {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON root is not an object: {path}")
    return value


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant: {value}")


def positive_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value > 0
    )


def finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def ratio(numerator: Any, denominator: Any) -> float:
    if not positive_number(numerator) or not positive_number(denominator):
        raise ValueError("ratio operands must be positive finite numbers")
    return float(numerator) / float(denominator)


def stats(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "p10": None, "median": None, "mean": None}
    ordered = sorted(values)
    position = (len(ordered) - 1) * 0.1
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    p10 = ordered[low] * (1 - position + low) + ordered[high] * (position - low)
    return {
        "count": len(values),
        "p10": p10,
        "median": statistics.median(values),
        "mean": statistics.fmean(values),
    }


def has_argv_pair(argv: list[str], option: str, expected: str) -> bool:
    return any(
        argv[index] == option and argv[index + 1] == expected
        for index in range(len(argv) - 1)
    )


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
        if match is None:
            continue
        name, labels_raw, value_raw = match.groups()
        labels = tuple(
            sorted(
                (key, bytes(value, "utf-8").decode("unicode_escape"))
                for key, value in label_re.findall(labels_raw or "")
            )
        )
        key = (name, labels)
        if key in result:
            raise ValueError(f"duplicate Prometheus sample: {name}{labels}")
        value = float(value_raw)
        if not math.isfinite(value):
            raise ValueError(f"non-finite Prometheus sample: {name}")
        result[key] = value
    return result


def unlabelled_metric(
    metrics: dict[tuple[str, tuple[tuple[str, str], ...]], float], name: str
) -> float:
    values = [
        value
        for (metric_name, labels), value in metrics.items()
        if metric_name == name and not labels
    ]
    if len(values) != 1:
        raise ValueError(f"metric {name} must occur once without labels")
    return values[0]


def load_suite(path: Path, prompt_builder: Path) -> tuple[dict[str, list[dict[str, Any]]], Any]:
    if sha256_file(path) != SUITE_SHA256:
        raise ValueError("paired suite SHA-256 mismatch")
    if sha256_file(prompt_builder) != PROMPT_BUILDER_SHA256:
        raise ValueError("prompt builder SHA-256 mismatch")
    suite = read_object(path)
    pairs = suite.get("pairs")
    if not isinstance(pairs, list):
        raise ValueError("paired suite has no pairs")
    by_band: dict[str, list[dict[str, Any]]] = {}
    for pair in pairs:
        if not isinstance(pair, dict) or pair.get("band") not in EXPECTED_BANDS:
            continue
        cases = pair.get("cases")
        if not isinstance(cases, list) or len(cases) != 2:
            raise ValueError(f"band {pair.get('band')} does not contain two cases")
        by_band[str(pair["band"])] = cases
    if set(by_band) != set(EXPECTED_BANDS):
        raise ValueError("paired suite does not contain exactly middle and near32k")
    spec = importlib.util.spec_from_file_location("qwen36_crossband_prompt_builder", prompt_builder)
    if spec is None or spec.loader is None:
        raise ValueError("could not load prompt builder")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    make_prompt = getattr(module, "make_prompt", None)
    if not callable(make_prompt):
        raise ValueError("prompt builder has no callable make_prompt")
    return by_band, make_prompt


def expected_json(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": case["id"],
        "project_code": case["project_code"],
        "answer_phrase": case["answer_phrase"],
        "sort_order": case["sort_order"],
        "arithmetic_result": int(case["arithmetic_result"]),
    }


def first_json_object(text: Any) -> dict[str, Any] | None:
    if not isinstance(text, str):
        return None
    stripped = text.lstrip()
    try:
        value, _ = json.JSONDecoder(parse_constant=_reject_json_constant).raw_decode(stripped)
    except (json.JSONDecodeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def logged_values(text: str, name: str) -> list[int]:
    return [
        int(value)
        for value in re.findall(
            rf"\b{re.escape(name)}\s+=\s+(\d+)\s*$", text, re.MULTILINE
        )
    ]


def gate_server(args: argparse.Namespace) -> int:
    expected_ubatch = EXPECTED_BANDS[args.band]
    if args.ubatch_size != expected_ubatch:
        raise ValueError(f"{args.band} requires ubatch {expected_ubatch}")
    text = args.log.read_text(errors="replace")
    identity = read_object(args.identity)
    argv = identity.get("argv")
    if not isinstance(argv, list) or not all(isinstance(item, str) for item in argv):
        raise ValueError("server argv is not a string array")
    load_path = identity.get("model_load_path")
    model_args = [
        argv[index + 1]
        for index in range(len(argv) - 1)
        if argv[index] == "-m"
    ]
    alias = f"qwen36-27b-mtp-crossband-w{args.wave}-g{args.gpu_index}-{args.band}-{args.mode}"
    port = identity.get("port")
    spec_args = ["--spec-type", "none"]
    if args.mode == "mtp3":
        spec_args = [
            "--spec-type",
            "draft-mtp",
            "--spec-draft-n-max",
            "3",
            "--spec-draft-n-min",
            "0",
            "--spec-draft-p-split",
            "0.10",
            "--spec-draft-p-min",
            "0.00",
            "--spec-draft-backend-sampling",
            "--spec-draft-device",
            "SYCL0",
            "--spec-draft-ngl",
            "all",
            "--spec-draft-type-k",
            "f16",
            "--spec-draft-type-v",
            "f16",
        ]
    expected_argv = [
        RUNTIME_PATH,
        "-m",
        str(load_path),
        "--alias",
        alias,
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "-dev",
        "SYCL0",
        "-ngl",
        "all",
        "-c",
        "32768",
        "-np",
        "1",
        "-b",
        "1024",
        "-ub",
        str(expected_ubatch),
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
        "-fit",
        "on",
        "-fitt",
        "1024",
        *spec_args,
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
    forbidden = {
        "--spec-draft-model",
        "-md",
        "--model-draft",
        "--spec-draft-hf",
        "-hfd",
        "-hfrd",
        "--hf-repo-draft",
    }
    marker = "creating MTP draft context against the target model"
    marker_offset = text.find(marker)
    if args.mode == "mtp3" and marker_offset >= 0:
        target_text = text[:marker_offset]
        draft_text = text[marker_offset + len(marker) :]
    else:
        target_text = text
        draft_text = ""
    target_batch = logged_values(target_text, "n_batch")
    target_ubatch = logged_values(target_text, "n_ubatch")
    draft_batch = logged_values(draft_text, "n_batch")
    draft_ubatch = logged_values(draft_text, "n_ubatch")
    fit_lines = [line.strip() for line in text.splitlines() if "common_params_fit_impl:" in line]
    fit_re = re.compile(
        r".*\bcommon_params_fit_impl:\s+will leave\s+(\d+)\s+>=\s+(\d+) MiB "
        r"of free device memory, no changes needed"
    )
    fit_matches = [match for line in fit_lines if (match := fit_re.fullmatch(line))]
    adjustment_lines = [
        line
        for line in fit_lines
        if re.search(
            r"adjust|reduc|cannot meet|trying to fit|set ngl|moved to system|overflow",
            line,
            re.IGNORECASE,
        )
    ]
    checks: dict[str, bool] = {
        "identity_mode": identity.get("mode") == args.mode,
        "identity_band": identity.get("band") == args.band,
        "identity_ubatch": identity.get("ubatch_size") == expected_ubatch,
        "identity_batch": identity.get("batch_size") == 1024,
        "identity_gpu": identity.get("gpu_index") == args.gpu_index,
        "identity_wave": identity.get("wave") == args.wave,
        "model_identity": identity.get("model_sha256") == MODEL_SHA256,
        "runtime_identity": identity.get("runtime_sha256") == RUNTIME_SHA256,
        "runtime_path": identity.get("runtime_path") == RUNTIME_PATH,
        "port": integer(port) and 1024 <= port <= 65535,
        "alias": identity.get("alias") == alias,
        "model_fd_path": bool(re.fullmatch(r"/proc/self/fd/[0-9]+", str(load_path or ""))),
        "one_exact_model_argument": model_args == [load_path],
        "exact_argv": argv == expected_argv,
        "no_sidecar": not forbidden.intersection(argv),
        "block_count_65": bool(re.search(r"qwen35\.block_count\s+u32\s+= 65\b", text)),
        "trunk_layers_64": bool(re.search(r"n_layer\s+= 64\b", text)),
        "all_layers_65": bool(re.search(r"n_layer_all\s+= 65\b", text)),
        "one_nextn_layer": bool(re.search(r"qwen35\.nextn_predict_layers\s+u32\s+= 1\b", text)),
        "full_offload_66": "offloaded 66/66 layers to GPU" in text,
        "ctx_32768": bool(re.search(r"n_ctx\s+= 32768\b", text)),
        "one_slot": bool(
            re.search(
                r"initializing, n_slots = 1, n_ctx_slot = 32768, kv_unified = 'false'",
                text,
            )
        ),
        "target_batch": bool(target_batch) and all(value == 1024 for value in target_batch),
        "target_ubatch": bool(target_ubatch)
        and all(value == expected_ubatch for value in target_ubatch),
        "fit_no_changes": len(fit_matches) == 1
        and not adjustment_lines
        and int(fit_matches[0].group(1)) >= int(fit_matches[0].group(2)) >= 1024,
        "no_fatal_error": not re.search(
            r"UR_RESULT_ERROR_DEVICE_LOST|ZE_RESULT_ERROR_DEVICE_LOST|out of memory|segmentation fault|core dumped|Aborted|failed to create MTP context",
            text,
            re.IGNORECASE,
        ),
        "no_cpu_fallback": not re.search(
            r"offloaded (?!66/66)\d+/66 layers to GPU|using CPU for layer|failed to offload|using CPU sampler",
            text,
            re.IGNORECASE,
        ),
    }
    if args.mode == "control":
        checks.update(
            {
                "spec_none": has_argv_pair(argv, "--spec-type", "none"),
                "no_spec_options": not any(item.startswith("--spec-draft-") for item in argv),
                "spec_disabled_log": "no implementations specified for speculative decoding" in text,
                "no_mtp_context": marker_offset < 0,
            }
        )
    else:
        required_spec = {
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
                "mtp_pairs": all(has_argv_pair(argv, key, value) for key, value in required_spec.items()),
                "backend_sampling": "--spec-draft-backend-sampling" in argv,
                "embedded_context": marker_offset >= 0,
                "no_separate_draft_load": "loading draft model" not in text,
                "draft_batch": bool(draft_batch) and all(value == 1024 for value in draft_batch),
                "draft_ubatch": bool(draft_ubatch)
                and all(value == expected_ubatch for value in draft_ubatch),
                "mtp_context_on_sycl": marker_offset >= 0
                and bool(re.search(r"SYCL0\s+KV buffer size", text[marker_offset:])),
            }
        )
    result = {
        "mode": args.mode,
        "band": args.band,
        "gpu_index": args.gpu_index,
        "wave": args.wave,
        "port": port,
        "ubatch_size": expected_ubatch,
        "identity_sha256": sha256_file(args.identity),
        "log_sha256": sha256_file(args.log),
        "fit_headroom_pairs_mib": [
            [int(match.group(1)), int(match.group(2))] for match in fit_matches
        ],
        "target_batch_values": target_batch,
        "target_ubatch_values": target_ubatch,
        "draft_batch_values": draft_batch,
        "draft_ubatch_values": draft_ubatch,
        "checks": checks,
        "passed": all(checks.values()),
    }
    atomic_write_json(args.output, result)
    return 0 if result["passed"] else 1


def timing_valid(timing: dict[str, Any], prompt_n: int, mode: str) -> bool:
    predicted_ms = timing.get("predicted_ms")
    predicted_rate = timing.get("predicted_per_second")
    prompt_ms = timing.get("prompt_ms")
    prompt_rate = timing.get("prompt_per_second")
    common = (
        timing.get("predicted_n") == 512
        and timing.get("prompt_n") == prompt_n
        and timing.get("cache_n") == 0
        and positive_number(predicted_ms)
        and positive_number(predicted_rate)
        and positive_number(prompt_ms)
        and positive_number(prompt_rate)
        and math.isclose(float(predicted_rate), 512000.0 / float(predicted_ms), rel_tol=1e-6, abs_tol=1e-6)
        and math.isclose(float(prompt_rate), 1000.0 * prompt_n / float(prompt_ms), rel_tol=1e-6, abs_tol=1e-6)
    )
    if mode == "control":
        return common and "draft_n" not in timing and "draft_n_accepted" not in timing
    return (
        common
        and integer(timing.get("draft_n"))
        and integer(timing.get("draft_n_accepted"))
        and timing["draft_n"] > 0
        and 0 <= timing["draft_n_accepted"] <= timing["draft_n"]
    )


def interval_valid(metric: dict[str, Any], end: int, offsets: list[Any]) -> bool:
    expected_intervals = end
    if (
        metric.get("interval_count") != expected_intervals
        or metric.get("event_count") != expected_intervals + 1
        or metric.get("numerator") != expected_intervals
        or metric.get("start_event_index") != 0
        or metric.get("end_event_index") != end
        or len(offsets) <= end
        or not positive_number(metric.get("duration_s"))
        or not positive_number(metric.get("tok_s"))
        or not positive_number(offsets[end] - offsets[0])
    ):
        return False
    duration = float(offsets[end]) - float(offsets[0])
    return math.isclose(float(metric["duration_s"]), duration, rel_tol=0, abs_tol=1e-12) and math.isclose(
        float(metric["tok_s"]), expected_intervals / duration, rel_tol=1e-12, abs_tol=1e-12
    )


def gate_arm(args: argparse.Namespace) -> int:
    expected_ubatch = EXPECTED_BANDS[args.band]
    if args.ubatch_size != expected_ubatch:
        raise ValueError(f"{args.band} requires ubatch {expected_ubatch}")
    by_band, make_prompt = load_suite(args.suite, args.prompt_builder)
    cases = by_band[args.band]
    expected_ids = [str(case["id"]) for case in cases]
    capture = read_object(args.capture)
    identity = capture.get("run_identity") or {}
    intrinsic = capture.get("intrinsic_gate") or {}
    oracle = capture.get("oracle_comparison") or {}
    rows = capture.get("rows") or []
    server_pre = read_object(args.server_gate)
    server_post = read_object(args.server_post_gate)
    metrics_gate = read_object(args.metrics_gate)
    before = parse_prometheus(args.metrics_before)
    after = parse_prometheus(args.metrics_after)
    expected_prompts = [make_prompt(case) for case in cases]
    expected_prompt_shas = [sha256_text(prompt) for prompt in expected_prompts]
    expected_prompt_tokens = [int(case["calibrated_prompt_tokens"]) for case in cases]
    checks: dict[str, bool] = {
        "suite_sha256": identity.get("suite_sha256") == SUITE_SHA256,
        "prompt_builder_sha256": identity.get("prompt_builder_sha256") == PROMPT_BUILDER_SHA256,
        "band": identity.get("band") == args.band,
        "prompt_ids": identity.get("prompt_ids") == expected_ids,
        "model_sha256": identity.get("model_sha256") == MODEL_SHA256,
        "runtime_sha256": identity.get("runtime_sha256") == RUNTIME_SHA256,
        "ctx_32768": identity.get("ctx_size") == 32768,
        "f16_kv": identity.get("cache_type_k") == identity.get("cache_type_v") == "f16",
        "selectors": identity.get("sycl_dnn_enabled") == 0 and identity.get("sycl_opt_enabled") == 1,
        "max_tokens_512": identity.get("max_tokens") == 512,
        "ignore_eos": identity.get("ignore_eos") is True,
        "exact_count": identity.get("require_exact_token_count") is True,
        "full_metric": identity.get("require_full_512_metric") is True,
        "no_legacy_canary": identity.get("require_post_512_canary") is False,
        "no_legacy_canary_inputs": all(
            identity.get(key) is None
            for key in (
                "post_512_canary_suite_path",
                "post_512_canary_suite_sha256",
                "post_512_canary_oracle_path",
                "post_512_canary_oracle_sha256",
                "post_512_canary_prompt_id",
                "post_512_canary_slot_id",
            )
        ),
        "slot_zero": identity.get("slot_id") == 0,
        "deterministic_sampling": identity.get("seed") == 1
        and identity.get("temperature") == 0
        and identity.get("top_p") == 1,
        "cold_request": identity.get("cache_prompt") is False,
        "token_return": identity.get("return_tokens") is True,
        "stream_capture": identity.get("stream") is True,
        "exact_replay": identity.get("exact_token_replay") is True,
        "replay_order": identity.get("replay_order")
        == "all_streaming_rows_then_all_non_streaming_replays",
        "capture_api": identity.get("api")
        == "llama.cpp /apply-template, streaming timing, deterministic non-streaming token replay",
        "suite_path": identity.get("suite_path") == str(args.suite),
        "prompt_builder_path": identity.get("prompt_builder_path")
        == str(args.prompt_builder),
        "intrinsic": intrinsic.get("passed") is True,
        "fresh_baseline_status": oracle
        == {
            "status": "BASELINE_CAPTURE_READY",
            "passed": None,
            "oracle_json": None,
        },
        "no_prefix_oracle": capture.get("prefix_oracle_comparison") is None,
        "server_pre": server_pre.get("passed") is True,
        "server_post": server_post.get("passed") is True,
        "server_gate_identity": all(
            gate.get(key) == expected
            for gate in (server_pre, server_post)
            for key, expected in {
                "mode": args.mode,
                "band": args.band,
                "gpu_index": args.gpu_index,
                "wave": args.wave,
                "ubatch_size": expected_ubatch,
            }.items()
        ),
        "server_gate_join": server_pre.get("identity_sha256")
        == server_post.get("identity_sha256"),
        "server_port": integer(server_pre.get("port"))
        and server_pre.get("port") == server_post.get("port")
        and identity.get("base_url")
        == f"http://127.0.0.1:{server_pre.get('port')}",
        "metrics_gate": metrics_gate.get("passed") is True and metrics_gate.get("mode") == args.mode,
        "two_rows": isinstance(rows, list) and len(rows) == 2,
    }
    row_results: list[dict[str, Any]] = []
    per_prompt: dict[str, dict[str, float]] = {}
    response_draft = 0
    response_accepted = 0
    for index, case in enumerate(cases):
        row = rows[index] if index < len(rows) and isinstance(rows[index], dict) else {}
        stream_timing = row.get("stream_timings") or {}
        replay_timing = row.get("timings") or {}
        offsets = row.get("token_event_offsets_s") or []
        token_ids = row.get("token_ids")
        first_json = first_json_object(row.get("content"))
        primary = row.get("primary_metric") or {}
        full = row.get("full_512_metric") or {}
        request_started = row.get("request_started_perf_s")
        request_ended = row.get("request_ended_perf_s")
        request_elapsed = row.get("request_elapsed_s")
        row_checks = {
            "prompt_id": row.get("prompt_id") == expected_ids[index],
            "prompt_sha256": row.get("prompt_sha256") == expected_prompt_shas[index],
            "calibrated_prompt_tokens": row.get("calibrated_prompt_tokens") == expected_prompt_tokens[index],
            "rendered_prompt_hash": isinstance(row.get("rendered_prompt_sha256"), str)
            and bool(re.fullmatch(r"[0-9a-f]{64}", row["rendered_prompt_sha256"])),
            "token_count_512": row.get("token_count") == 512,
            "tokens_valid": isinstance(token_ids, list)
            and len(token_ids) == 512
            and all(integer(token) and token >= 0 for token in token_ids),
            "stream_replay_content": row.get("stream_content_matches_replay") is True,
            "stream_alignment": row.get("stream_alignment_unique") is True,
            "stream_final_count": row.get("stream_final_predicted_n") == 512,
            "replay_final_count": row.get("final_predicted_n") == 512,
            "stream_stop_matches": row.get("stop_type_matches_replay") is True,
            "limit_stop": row.get("stop_type") == row.get("stream_stop_type") == "limit",
            "slot_identity": row.get("id_slot_matches_request") is True,
            "stream_timing": timing_valid(stream_timing, expected_prompt_tokens[index], args.mode),
            "replay_timing": timing_valid(replay_timing, expected_prompt_tokens[index], args.mode),
            "offsets": isinstance(offsets, list)
            and len(offsets) == 512
            and all(positive_number(value) for value in offsets)
            and all(offsets[position] <= offsets[position + 1] for position in range(511)),
            "d99": isinstance(offsets, list) and interval_valid(primary, 99, offsets),
            "d511": isinstance(offsets, list) and interval_valid(full, 511, offsets),
            "positive_ttft": positive_number(row.get("ttft_s")),
            "finite_ordered_request_interval": finite_number(request_started)
            and finite_number(request_ended)
            and request_started < request_ended,
            "request_elapsed_arithmetic": positive_number(request_elapsed)
            and finite_number(request_started)
            and finite_number(request_ended)
            and math.isclose(
                float(request_ended) - float(request_started),
                float(request_elapsed),
                rel_tol=0,
                abs_tol=1e-9,
            ),
            "first_json_exact": first_json == expected_json(case),
            "content_hash": isinstance(row.get("content"), str)
            and row.get("content_sha256") == sha256_text(row["content"]),
        }
        if args.mode == "mtp3":
            for timing in (stream_timing, replay_timing):
                if integer(timing.get("draft_n")) and integer(timing.get("draft_n_accepted")):
                    response_draft += timing["draft_n"]
                    response_accepted += timing["draft_n_accepted"]
        if all(row_checks.values()):
            per_prompt[expected_ids[index]] = {
                "d99_interval_tok_s": float(primary["tok_s"]),
                "d511_interval_tok_s": float(full["tok_s"]),
                "native_stream_tok_s": float(stream_timing["predicted_per_second"]),
                "native_replay_tok_s": float(replay_timing["predicted_per_second"]),
                "prompt_tok_s": float(stream_timing["prompt_per_second"]),
                "ttft_s": float(row["ttft_s"]),
            }
        row_results.append(
            {"prompt_id": expected_ids[index], "checks": row_checks, "passed": all(row_checks.values())}
        )
    checks["all_rows"] = len(row_results) == 2 and all(item["passed"] for item in row_results)
    before_values = {key: unlabelled_metric(before, name) for key, name in METRIC_NAMES.items()}
    after_values = {key: unlabelled_metric(after, name) for key, name in METRIC_NAMES.items()}
    expected_prompt_delta = 2 * sum(expected_prompt_tokens)
    checks.update(
        {
            "metrics_begin_zero": before_values == {
                "prompt_tokens": 0,
                "predicted_tokens": 0,
                "requests_processing": 0,
                "requests_deferred": 0,
            },
            "metrics_end_idle": after_values["requests_processing"] == 0
            and after_values["requests_deferred"] == 0,
            "prompt_counter_exact": after_values["prompt_tokens"] - before_values["prompt_tokens"]
            == expected_prompt_delta,
            "predicted_counter_exact": after_values["predicted_tokens"] - before_values["predicted_tokens"]
            == 2048,
        }
    )
    counters = metrics_gate.get("counters") or {}
    if args.mode == "control":
        checks["control_spec_zero"] = counters == {
            "accepted_tokens": 0,
            "draft_tokens": 0,
            "drafts": 0,
        }
        checks["control_response_drafts_absent"] = response_draft == response_accepted == 0
    else:
        checks["response_draft_counter_join"] = counters.get("draft_tokens") == response_draft
        checks["response_accepted_counter_join"] = counters.get("accepted_tokens") == response_accepted
    metric_values = list(per_prompt.values())
    result = {
        "mode": args.mode,
        "band": args.band,
        "gpu_index": args.gpu_index,
        "wave": args.wave,
        "port": server_pre.get("port"),
        "ubatch_size": expected_ubatch,
        "capture_sha256": sha256_file(args.capture),
        "metrics_gate_sha256": sha256_file(args.metrics_gate),
        "server_gate_sha256": sha256_file(args.server_gate),
        "server_post_gate_sha256": sha256_file(args.server_post_gate),
        "checks": checks,
        "rows": row_results,
        "per_prompt": per_prompt,
        "summary": {
            "d99_interval_tok_s": stats([item["d99_interval_tok_s"] for item in metric_values]),
            "d511_interval_tok_s": stats([item["d511_interval_tok_s"] for item in metric_values]),
            "native_stream_tok_s": stats([item["native_stream_tok_s"] for item in metric_values]),
            "native_replay_tok_s": stats([item["native_replay_tok_s"] for item in metric_values]),
            "prompt_tok_s": stats([item["prompt_tok_s"] for item in metric_values]),
            "ttft_s": stats([item["ttft_s"] for item in metric_values]),
            "response_draft_tokens": response_draft,
            "response_accepted_tokens": response_accepted,
            "prometheus": metrics_gate,
        },
        "passed": all(checks.values()),
    }
    atomic_write_json(args.output, result)
    return 0 if result["passed"] else 1


def load_env(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text().splitlines():
        key, separator, value = line.partition("=")
        if not separator or not key or key in result:
            raise ValueError(f"invalid env evidence: {path}")
        result[key] = value
    return result


def verify_artifact_manifest(root: Path, manifest: Path) -> bool:
    try:
        lines = manifest.read_text().splitlines()
        if not lines:
            return False
        for line in lines:
            match = re.fullmatch(r"([0-9a-f]{64})  (\./)?(.+)", line)
            if match is None:
                return False
            relative = Path(match.group(3))
            if relative.is_absolute() or ".." in relative.parts:
                return False
            target = root / relative
            if not target.is_file() or sha256_file(target) != match.group(1):
                return False
        return True
    except OSError:
        return False


def arm_dir(root: Path, wave: int, gpu: int, band: str, mode: str) -> Path:
    return root / f"wave{wave}" / f"gpu{gpu}-{band}-{mode}"


def compare_crossover(args: argparse.Namespace) -> int:
    by_band, _ = load_suite(args.suite, args.prompt_builder)
    run_identity_path = args.root / "run-identity.json"
    run_identity = read_object(run_identity_path)
    port_base = run_identity.get("port_base")
    arms: dict[tuple[int, int], dict[str, Any]] = {}
    evidence_checks: dict[str, bool] = {
        "run_timestamp": isinstance(run_identity.get("date_utc"), str)
        and bool(
            re.fullmatch(
                r"\d{8}T\d{6}\.\d{9}Z",
                run_identity["date_utc"],
            )
        ),
        "run_evidence_class": run_identity.get("evidence_class")
        == "parallel-functional-screen",
        "run_not_promotable": run_identity.get("performance_promotable") is False
        and run_identity.get("localmaxxing_submission_ready") is False,
        "run_model": run_identity.get("model_size") == 29047084160
        and run_identity.get("model_sha256") == MODEL_SHA256
        and run_identity.get("model_repository") == MODEL_REPOSITORY
        and run_identity.get("model_revision") == MODEL_REVISION
        and bool(
            re.fullmatch(
                r"/proc/self/fd/[0-9]+",
                str(run_identity.get("model_load_path") or ""),
            )
        ),
        "run_runtime": run_identity.get("runtime_path") == RUNTIME_PATH
        and run_identity.get("runtime_sha256") == RUNTIME_SHA256
        and run_identity.get("runtime_manifest_sha256") == RUNTIME_MANIFEST_SHA256
        and run_identity.get("runtime_commit") == RUNTIME_COMMIT,
        "run_suite": run_identity.get("suite_sha256") == SUITE_SHA256
        and run_identity.get("prompt_builder_sha256") == PROMPT_BUILDER_SHA256,
        "run_shape": run_identity.get("ctx_size") == 32768
        and run_identity.get("batch_size") == 1024
        and run_identity.get("max_tokens") == 512
        and run_identity.get("ignore_eos") is True
        and run_identity.get("cache_type_k")
        == run_identity.get("cache_type_v")
        == "f16"
        and run_identity.get("sycl_dnn_enabled") == 0
        and run_identity.get("sycl_opt_enabled") == 1,
        "run_port_base": integer(port_base) and 1024 <= port_base <= 65532,
        "run_assignments": run_identity.get("assignments")
        == EXPECTED_ASSIGNMENT_OBJECTS,
    }
    for key, (band, mode) in EXPECTED_ASSIGNMENTS.items():
        wave, gpu = key
        directory = arm_dir(args.root, wave, gpu, band, mode)
        gate = read_object(directory / "arm-gate.json")
        capture = read_object(directory / "exact-tokens.json")
        cleanup = load_env(directory / "cleanup-status.env")
        marker = read_object(directory / "completion-status.json")
        arms[key] = {"gate": gate, "capture": capture, "directory": directory}
        prefix = f"wave{wave}_gpu{gpu}"
        evidence_checks[f"{prefix}_gate"] = (
            gate.get("passed") is True
            and gate.get("band") == band
            and gate.get("mode") == mode
            and gate.get("gpu_index") == gpu
            and gate.get("wave") == wave
            and integer(port_base)
            and gate.get("port") == port_base + gpu
        )
        evidence_checks[f"{prefix}_capture_join"] = gate.get("capture_sha256") == sha256_file(
            directory / "exact-tokens.json"
        )
        evidence_checks[f"{prefix}_cleanup"] = all(
            cleanup.get(name) == value
            for name, value in {
                "forced_kill": "0",
                "cleanup_survivor": "0",
                "port_closed": "1",
                "vram_returned": "1",
            }.items()
        )
        evidence_checks[f"{prefix}_marker"] = (
            marker.get("status") == "PASS"
            and marker.get("evidence_valid") is True
            and marker.get("performance_promotable") is False
            and marker.get("arm_gate_sha256") == sha256_file(directory / "arm-gate.json")
            and marker.get("artifacts_manifest_sha256")
            == sha256_file(directory / "artifacts.sha256")
        )
        evidence_checks[f"{prefix}_sealed_artifacts"] = verify_artifact_manifest(
            directory, directory / "artifacts.sha256"
        )
    wave_intersections: list[dict[str, Any]] = []
    for wave in (1, 2):
        intervals: list[dict[str, Any]] = []
        for gpu in range(4):
            capture_rows = arms[(wave, gpu)]["capture"].get("rows")
            first = (
                capture_rows[0]
                if isinstance(capture_rows, list)
                and capture_rows
                and isinstance(capture_rows[0], dict)
                else {}
            )
            started = first.get("request_started_perf_s")
            ended = first.get("request_ended_perf_s")
            ordered = (
                finite_number(started)
                and finite_number(ended)
                and started < ended
            )
            evidence_checks[f"wave{wave}_gpu{gpu}_first_scored_interval"] = ordered
            intervals.append(
                {
                    "gpu_index": gpu,
                    "prompt_id": first.get("prompt_id"),
                    "request_started_perf_s": started,
                    "request_ended_perf_s": ended,
                    "finite_start_before_end": ordered,
                }
            )
        all_ordered = all(interval["finite_start_before_end"] for interval in intervals)
        latest_start = (
            max(float(interval["request_started_perf_s"]) for interval in intervals)
            if all_ordered
            else None
        )
        earliest_end = (
            min(float(interval["request_ended_perf_s"]) for interval in intervals)
            if all_ordered
            else None
        )
        overlap = (
            earliest_end - latest_start
            if latest_start is not None and earliest_end is not None
            else None
        )
        intersects = positive_number(overlap)
        evidence_checks[f"wave{wave}_first_scored_four_way_intersection"] = intersects
        wave_intersections.append(
            {
                "wave": wave,
                "intervals": intervals,
                "latest_request_start_perf_s": latest_start,
                "earliest_request_end_perf_s": earliest_end,
                "four_way_intersection_s": overlap,
                "passed": intersects,
            }
        )
    pairs: list[dict[str, Any]] = []
    band_metrics: dict[str, dict[str, list[float]]] = {
        band: {
            "control_d99": [],
            "candidate_d99": [],
            "control_d511": [],
            "candidate_d511": [],
            "control_native": [],
            "candidate_native": [],
            "control_pp": [],
            "candidate_pp": [],
            "control_ttft": [],
            "candidate_ttft": [],
            "row_d99_ratios": [],
            "row_d511_ratios": [],
        }
        for band in EXPECTED_BANDS
    }
    candidate_metric_gates: dict[str, list[dict[str, Any]]] = {band: [] for band in EXPECTED_BANDS}
    for band, gpus in (("middle", (0, 1)), ("near32k", (2, 3))):
        expected_ids = [str(case["id"]) for case in by_band[band]]
        for gpu in gpus:
            control_wave = 1 if EXPECTED_ASSIGNMENTS[(1, gpu)][1] == "control" else 2
            candidate_wave = 1 if control_wave == 2 else 2
            control = arms[(control_wave, gpu)]
            candidate = arms[(candidate_wave, gpu)]
            control_rows = {row["prompt_id"]: row for row in control["capture"].get("rows", [])}
            candidate_rows = {row["prompt_id"]: row for row in candidate["capture"].get("rows", [])}
            pair_checks = {
                "prompt_ids": set(control_rows) == set(candidate_rows) == set(expected_ids),
                "rendered_prompts_exact": all(
                    control_rows.get(prompt_id, {}).get("rendered_prompt_sha256")
                    == candidate_rows.get(prompt_id, {}).get("rendered_prompt_sha256")
                    for prompt_id in expected_ids
                ),
                "full_token_ids_exact": all(
                    control_rows.get(prompt_id, {}).get("token_ids")
                    == candidate_rows.get(prompt_id, {}).get("token_ids")
                    for prompt_id in expected_ids
                ),
                "full_content_exact": all(
                    control_rows.get(prompt_id, {}).get("content")
                    == candidate_rows.get(prompt_id, {}).get("content")
                    and control_rows.get(prompt_id, {}).get("content_sha256")
                    == candidate_rows.get(prompt_id, {}).get("content_sha256")
                    for prompt_id in expected_ids
                ),
            }
            evidence_checks[f"{band}_gpu{gpu}_quality"] = all(pair_checks.values())
            row_ratios = []
            for prompt_id in expected_ids:
                control_metric = control["gate"]["per_prompt"][prompt_id]
                candidate_metric = candidate["gate"]["per_prompt"][prompt_id]
                d99_ratio = ratio(candidate_metric["d99_interval_tok_s"], control_metric["d99_interval_tok_s"])
                d511_ratio = ratio(candidate_metric["d511_interval_tok_s"], control_metric["d511_interval_tok_s"])
                row_ratios.append(
                    {"prompt_id": prompt_id, "d99_candidate_over_control": d99_ratio, "d511_candidate_over_control": d511_ratio}
                )
                for stem, key_name in (
                    ("d99", "d99_interval_tok_s"),
                    ("d511", "d511_interval_tok_s"),
                    ("native", "native_stream_tok_s"),
                    ("pp", "prompt_tok_s"),
                    ("ttft", "ttft_s"),
                ):
                    band_metrics[band][f"control_{stem}"].append(float(control_metric[key_name]))
                    band_metrics[band][f"candidate_{stem}"].append(float(candidate_metric[key_name]))
                band_metrics[band]["row_d99_ratios"].append(d99_ratio)
                band_metrics[band]["row_d511_ratios"].append(d511_ratio)
            candidate_metric_gates[band].append(candidate["gate"]["summary"]["prometheus"])
            pairs.append(
                {
                    "band": band,
                    "gpu_index": gpu,
                    "control_wave": control_wave,
                    "candidate_wave": candidate_wave,
                    "checks": pair_checks,
                    "rows": row_ratios,
                    "passed": all(pair_checks.values()),
                }
            )
    evidence_passed = all(evidence_checks.values()) and all(pair["passed"] for pair in pairs)
    band_results: dict[str, Any] = {}
    performance_passed = evidence_passed
    for band, values in band_metrics.items():
        medians = {
            key: statistics.median(value)
            for key, value in values.items()
            if key not in {"row_d99_ratios", "row_d511_ratios"}
        }
        d99_ratio = ratio(medians["candidate_d99"], medians["control_d99"])
        d511_ratio = ratio(medians["candidate_d511"], medians["control_d511"])
        native_ratio = ratio(medians["candidate_native"], medians["control_native"])
        pp_ratio = ratio(medians["candidate_pp"], medians["control_pp"])
        ttft_ratio = ratio(medians["candidate_ttft"], medians["control_ttft"])
        draft_tokens = sum(int(gate["counters"]["draft_tokens"]) for gate in candidate_metric_gates[band])
        accepted_tokens = sum(int(gate["counters"]["accepted_tokens"]) for gate in candidate_metric_gates[band])
        drafts = sum(int(gate["counters"]["drafts"]) for gate in candidate_metric_gates[band])
        acceptance = accepted_tokens / draft_tokens if draft_tokens else None
        accepted_per_verification = accepted_tokens / drafts if drafts else None
        performance_checks = {
            "candidate_d99_at_least_18": medians["candidate_d99"] >= 18,
            "candidate_d511_at_least_18": medians["candidate_d511"] >= 18,
            "candidate_native_at_least_18": medians["candidate_native"] >= 18,
            "d99_gain_at_least_8pct": d99_ratio >= 1.08,
            "d511_gain_at_least_8pct": d511_ratio >= 1.08,
            "native_gain_at_least_8pct": native_ratio >= 1.08,
            "every_row_d99_gain_at_least_5pct": min(values["row_d99_ratios"]) >= 1.05,
            "every_row_d511_gain_at_least_5pct": min(values["row_d511_ratios"]) >= 1.05,
            "prompt_processing_no_regression_over_5pct": pp_ratio >= 0.95,
            "ttft_no_regression_over_10pct": ttft_ratio <= 1.10,
            "acceptance_at_least_045": positive_number(acceptance) and acceptance >= 0.45,
            "accepted_per_verification_at_least_125": positive_number(accepted_per_verification)
            and accepted_per_verification >= 1.25,
            "d511_native_ratio_disagreement_at_most_0035": abs(d511_ratio - native_ratio) <= 0.035,
        }
        if band == "near32k":
            performance_checks["near32k_prompt_processing_at_least_250"] = medians["candidate_pp"] >= 250
            performance_checks["near32k_ttft_at_most_130"] = medians["candidate_ttft"] <= 130
        band_passed = all(performance_checks.values())
        performance_passed = performance_passed and band_passed
        band_results[band] = {
            "rows_per_arm": len(values["control_d99"]),
            "control": {key.removeprefix("control_"): value for key, value in medians.items() if key.startswith("control_")},
            "candidate": {key.removeprefix("candidate_"): value for key, value in medians.items() if key.startswith("candidate_")},
            "ratios": {
                "d99_candidate_over_control": d99_ratio,
                "d511_candidate_over_control": d511_ratio,
                "native_candidate_over_control": native_ratio,
                "prompt_processing_candidate_over_control": pp_ratio,
                "ttft_candidate_over_control": ttft_ratio,
                "d511_native_ratio_disagreement": abs(d511_ratio - native_ratio),
                "minimum_row_d99_candidate_over_control": min(values["row_d99_ratios"]),
                "minimum_row_d511_candidate_over_control": min(values["row_d511_ratios"]),
            },
            "acceptance": {
                "draft_tokens": draft_tokens,
                "accepted_tokens": accepted_tokens,
                "drafts": drafts,
                "accepted_over_drafted": acceptance,
                "accepted_per_verification": accepted_per_verification,
            },
            "performance_checks": performance_checks,
            "performance_passed": band_passed,
        }
    if not evidence_passed:
        classification = "INVALID_CROSSBAND_EVIDENCE"
    elif performance_passed:
        classification = "PASS_CROSSBAND_MTP_RETENTION_WIN"
    else:
        classification = "VALID_CROSSBAND_NO_MTP_WIN"
    result = {
        "classification": classification,
        "evidence_class": "parallel-functional-screen",
        "performance_promotable": False,
        "localmaxxing_submission_ready": False,
        "fresh_quality_reference": "same-card-integrated-model-control-v1",
        "run_identity_sha256": sha256_file(run_identity_path),
        "evidence_checks": evidence_checks,
        "evidence_passed": evidence_passed,
        "performance_passed": performance_passed,
        "pairs": pairs,
        "wave_first_scored_intersections": wave_intersections,
        "bands": band_results,
        "policy": {
            "waves": 2,
            "cards_per_band": 2,
            "prompts_per_arm": 2,
            "max_tokens": 512,
            "ignore_eos": True,
            "same_card_treatment_crossover": True,
            "arm_order_balanced_within_band": True,
            "headline_timing_requests_per_prompt": 1,
            "first_scored_request_four_way_intersection_required": True,
            "unscored_same_lifetime_token_replays_per_prompt": 1,
            "middle_batch_ubatch": [1024, 128],
            "near32k_batch_ubatch": [1024, 1024],
        },
    }
    atomic_write_json(args.output, result)
    return 0 if evidence_passed else 1


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    commands = root.add_subparsers(dest="command", required=True)
    server = commands.add_parser("gate-server")
    server.add_argument("--mode", choices=("control", "mtp3"), required=True)
    server.add_argument("--band", choices=tuple(EXPECTED_BANDS), required=True)
    server.add_argument("--ubatch-size", type=int, required=True)
    server.add_argument("--gpu-index", type=int, choices=range(4), required=True)
    server.add_argument("--wave", type=int, choices=(1, 2), required=True)
    server.add_argument("--log", type=Path, required=True)
    server.add_argument("--identity", type=Path, required=True)
    server.add_argument("--output", type=Path, required=True)
    server.set_defaults(handler=gate_server)
    arm = commands.add_parser("gate-arm")
    arm.add_argument("--mode", choices=("control", "mtp3"), required=True)
    arm.add_argument("--band", choices=tuple(EXPECTED_BANDS), required=True)
    arm.add_argument("--ubatch-size", type=int, required=True)
    arm.add_argument("--gpu-index", type=int, choices=range(4), required=True)
    arm.add_argument("--wave", type=int, choices=(1, 2), required=True)
    arm.add_argument("--capture", type=Path, required=True)
    arm.add_argument("--suite", type=Path, required=True)
    arm.add_argument("--prompt-builder", type=Path, required=True)
    arm.add_argument("--server-gate", type=Path, required=True)
    arm.add_argument("--server-post-gate", type=Path, required=True)
    arm.add_argument("--metrics-before", type=Path, required=True)
    arm.add_argument("--metrics-after", type=Path, required=True)
    arm.add_argument("--metrics-gate", type=Path, required=True)
    arm.add_argument("--output", type=Path, required=True)
    arm.set_defaults(handler=gate_arm)
    compare = commands.add_parser("compare-crossover")
    compare.add_argument("--root", type=Path, required=True)
    compare.add_argument("--suite", type=Path, required=True)
    compare.add_argument("--prompt-builder", type=Path, required=True)
    compare.add_argument("--output", type=Path, required=True)
    compare.set_defaults(handler=compare_crossover)
    return root


def main() -> int:
    try:
        args = parser().parse_args()
        return args.handler(args)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"embedded-MTP cross-band gate failed: {exc}", file=__import__("sys").stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
