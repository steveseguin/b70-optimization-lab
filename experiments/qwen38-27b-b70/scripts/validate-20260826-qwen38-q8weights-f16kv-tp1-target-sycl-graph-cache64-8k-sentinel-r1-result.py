#!/usr/bin/env python3
"""Read-only validation of the sealed Q8_0/F16 cache64 graph sentinel."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen38-27b-b70"
CAMPAIGN = "qwen38-q8weights-f16kv-tp1-target-sycl-graph-cache64-8k-sentinel-20260826-r1"
DEFAULT_ROOT = Path("/mnt/fast-ai/bench-results") / CAMPAIGN
DEFAULT_RESULT = LANE / "data/2026-08-26-qwen38-q8weights-f16kv-tp1-target-sycl-graph-cache64-8k-sentinel-r1-result.json"
ARMS = ("control-graph-off-cache0", "candidate-graph-on-cache64")
CLEANUP = {
    "forced_kill": False,
    "port_closed": True,
    "render_node_idle": True,
    "server_survivor": False,
}
AUTHORITY = {
    "site_cells": 0,
    "full_graph_curve": False,
    "seven_depth_full_curve_preregistration": True,
    "other_cells": 0,
    "protected_or_headline_replacement": False,
    "localmaxxing_submission": False,
}
PROTECTED = [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144]


class ValidationError(RuntimeError):
    """The sealed evidence no longer matches its frozen result."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON root must be an object: {path}")
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def quality_summary(raw: dict[str, Any]) -> dict[str, Any]:
    exact = raw.get("exact_cases") or []
    repeat = raw.get("repeat_case") or {}
    long_context = raw.get("long_context_case") or {}
    requests = exact + (repeat.get("runs") or []) + [long_context]
    return {
        "pass_all": raw.get("pass_all"),
        "exact_passes": sum(row.get("pass") is True for row in exact),
        "exact_hashes": [row.get("sha256") for row in exact],
        "repeat_pass": repeat.get("pass"),
        "repeat_runs": repeat.get("repeats"),
        "repeat_unique_hashes": repeat.get("unique_hashes"),
        "long_context_pass": long_context.get("pass"),
        "long_context_actual_prompt_tokens": long_context.get("actual_prompt_tokens"),
        "long_context_api_prompt_tokens": (long_context.get("usage") or {}).get("prompt_tokens"),
        "long_context_sha256": long_context.get("sha256"),
        "cache_zero": all(
            ((row.get("usage") or {}).get("prompt_tokens_details") or {}).get("cached_tokens") == 0
            for row in requests
        ),
        "cache_zero_count": len(requests),
    }


def validate(root: Path, result_path: Path) -> dict[str, Any]:
    result = load(result_path)
    require(result.get("schema") == "neural.download.qwen38-q8weights-f16kv-target-sycl-graph-cache64-8k-sentinel-result.v1", "result schema changed")
    require(result.get("campaign_id") == CAMPAIGN, "campaign changed")
    require(result.get("classification") == "completed-valid-diagnostic-mechanism-and-quality-sentinel", "classification changed")
    require(result.get("raw_root") == str(DEFAULT_ROOT), "raw root changed")

    tracked = result.get("tracked_inputs") or {}
    require(set(tracked) == {"preregistration", "runner", "terminal_validator", "runner_tests"}, "tracked-input inventory changed")
    for name, binding in tracked.items():
        path = REPO / binding["path"]
        require(path.is_file(), f"tracked input missing: {name}")
        require(sha256(path) == binding["sha256"], f"tracked input changed: {name}")

    prereg = load(REPO / tracked["preregistration"]["path"])
    frozen = prereg.get("frozen_interpretation") or {}
    require(frozen.get("site_cells_authorized") == 0, "prereg site authority widened")
    require(frozen.get("full_graph_curve_authorized") is False, "prereg full-curve authority widened")
    require(frozen.get("sentinel_pass_authorizes_separate_seven_depth_full_curve_preregistration") is True, "prereg next-door authority changed")
    require(frozen.get("speed_floor") is None, "sentinel unexpectedly gained a speed floor")
    require(frozen.get("protected_decode_values") == PROTECTED, "preregistered protected values changed")

    bindings = {row["path"]: row for row in result.get("raw_files", [])}
    require(len(bindings) == 22, "result must bind exactly 22 raw files")
    require(not any(path.is_symlink() for path in root.rglob("*")), "raw root contains a symlink")
    actual = sorted(path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file())
    require(actual == sorted(bindings), "raw-file inventory changed")
    for relative, binding in bindings.items():
        path = root / relative
        require(path.stat().st_size == binding["bytes"], f"raw byte size changed: {relative}")
        require(sha256(path) == binding["sha256"], f"raw hash changed: {relative}")

    identity = load(root / "identity.json")
    require(identity.get("campaign_id") == CAMPAIGN, "raw campaign changed")
    require(identity.get("git_head") == identity.get("origin_main") == result["identity"]["git_head_and_origin_main"], "launch Git identity changed")
    model = identity.get("model") or {}
    compact_model = result["identity"]["model"]
    for key in ("path", "repository", "revision", "quantization", "size_bytes", "sha256"):
        require(model.get(key) == compact_model.get(key), f"model identity changed: {key}")
    runtime = identity.get("graph_runtime") or {}
    compact_runtime = result["identity"]["runtime"]
    for key in ("source_base_head", "binary_sha256", "graph_backend_sha256", "effective_dso_canonical_sha256"):
        require(runtime.get(key) == compact_runtime.get(key), f"runtime identity changed: {key}")
    argv = identity.get("server_argv") or {}
    require(set(argv) == set(ARMS) and argv[ARMS[0]] == argv[ARMS[1]], "server argv differed")
    require("--spec-draft-model" not in argv[ARMS[0]], "draft model unexpectedly present")
    require(argv[ARMS[0]][argv[ARMS[0]].index("--spec-type") + 1] == "none", "run was not target-only")
    require(argv[ARMS[0]][argv[ARMS[0]].index("-ctk") + 1] == argv[ARMS[0]][argv[ARMS[0]].index("-ctv") + 1] == "f16", "run was not F16 KV")
    environments = identity.get("runtime_environment") or {}
    for arm in ARMS:
        expected = {**result["identity"]["arm_delta"][arm], "ONEAPI_DEVICE_SELECTOR": "level_zero:0"}
        require(environments.get(arm) == expected, f"runtime environment changed: {arm}")

    depths: dict[str, dict[str, Any]] = {}
    qualities: dict[str, dict[str, Any]] = {}
    for arm in ARMS:
        require(load(root / arm / "cleanup.json") == CLEANUP, f"cleanup failed: {arm}")
        require(load(root / arm / "arm-result.json") == {"cleanup": CLEANUP, "error": None, "status": "completed-awaiting-validation"}, f"arm result changed: {arm}")
        depth = load(root / arm / "depth-8192/exact-depth.json")
        require(depth == load(root / arm / "depth-8192/exact-depth.stdout.json"), f"depth/stdout differ: {arm}")
        require(depth.get("status") == "passed" and (depth.get("gate") or {}).get("passed") is True, f"depth gate failed: {arm}")
        require(all(((depth.get("gate") or {}).get("checks") or {}).values()), f"depth subcheck failed: {arm}")
        run_identity = depth.get("run_identity") or {}
        require(run_identity.get("active_context_tokens") == run_identity.get("depth") == 8192, f"depth changed: {arm}")
        response = depth.get("response") or {}
        require(response.get("usage") == {"completion_tokens": 128, "prompt_tokens": 8192, "prompt_tokens_details": {"cached_tokens": 0}, "total_tokens": 8320}, f"usage changed: {arm}")
        require(len(response.get("token_ids") or []) == 128, f"token count changed: {arm}")
        depths[arm] = depth
        quality = load(root / arm / "quality.json")
        quality_stdout = load(root / arm / "quality.stdout.json")
        require(quality_stdout.get("pass_all") is True, f"quality stdout failed: {arm}")
        require(quality_stdout.get("repeat_pass") is True and quality_stdout.get("long_context_pass") is True, f"quality stdout summary failed: {arm}")
        require(all((quality_stdout.get("exact") or {}).values()) and len(quality_stdout.get("exact") or {}) == 7, f"quality stdout exact summary failed: {arm}")
        qualities[arm] = quality_summary(quality)

    left = depths[ARMS[0]]["response"]
    right = depths[ARMS[1]]["response"]
    for key in ("token_ids", "output_token_ids_sha256", "text_sha256", "usage", "returned_prompt_token_ids_sha256"):
        require(left.get(key) == right.get(key), f"graph-off/on exact-depth parity failed: {key}")
    expected_quality = {
        "pass_all": True,
        "exact_passes": 7,
        "repeat_pass": True,
        "repeat_runs": 2,
        "repeat_unique_hashes": [result["quality"]["repeat_sha256"]],
        "long_context_pass": True,
        "long_context_actual_prompt_tokens": 25200,
        "long_context_api_prompt_tokens": 25212,
        "long_context_sha256": result["quality"]["long_context_sha256"],
        "cache_zero": True,
        "cache_zero_count": 10,
    }
    for arm, summary in qualities.items():
        require(summary["exact_hashes"] == result["quality"]["exact_case_hashes"], f"exact quality hashes changed: {arm}")
        require({key: summary[key] for key in expected_quality} == expected_quality, f"quality battery changed: {arm}")
    require(qualities[ARMS[0]] == qualities[ARMS[1]], "full quality output parity failed")

    compact_measurements = result.get("measurements") or {}
    for arm in ARMS:
        depth = depths[arm]
        response = depth["response"]
        expected = {
            "serving_decode_tok_s_99_interval": depth["metric_window"]["conventional_99_interval_tok_s"],
            "time_to_first_token_s": depth["metric_window"]["time_to_first_token_s"],
            "completion_tokens": response["usage"]["completion_tokens"],
            "prompt_tokens": response["usage"]["prompt_tokens"],
            "cached_tokens": response["usage"]["prompt_tokens_details"]["cached_tokens"],
            "output_token_ids_sha256": response["output_token_ids_sha256"],
            "text_sha256": response["text_sha256"],
        }
        require(compact_measurements.get(arm) == expected, f"compact measurement changed: {arm}")
    relative = (compact_measurements[ARMS[1]]["serving_decode_tok_s_99_interval"] / compact_measurements[ARMS[0]]["serving_decode_tok_s_99_interval"] - 1.0) * 100.0
    observation = result.get("single_sentinel_performance_observation") or {}
    require(math.isclose(observation.get("graph_on_relative_percent"), relative, rel_tol=0.0, abs_tol=1e-15), "relative observation changed")
    require(relative < 0 and observation.get("speed_authority") is False, "diagnostic observation gained speed authority")

    graph = load(root / ARMS[1] / "graph-evidence.json")
    compact_graph = result.get("graph_mechanism") or {}
    for key in ("requested", "replayed", "direct_replay", "cache_entries", "cache_limit", "cache_hit", "cache_miss", "cache_full", "created", "recorded", "compatibility_rejected", "device_unsupported", "updated", "recreated"):
        require(graph.get(key) == compact_graph.get(key), f"graph telemetry changed: {key}")
    require(graph["requested"] == graph["cache_hit"] + graph["cache_miss"] == graph["replayed"], "graph request conservation failed")
    require(graph["cache_hit"] == graph["direct_replay"] >= compact_graph["minimum_direct_replays"], "direct replay floor failed")
    require(graph["cache_miss"] == graph["created"] == graph["recorded"] == graph["cache_entries"], "graph creation conservation failed")

    terminal = load(root / "terminal-receipt.json")
    require(terminal == load(root / "validator.stdout.json"), "terminal and validator stdout differ")
    require(terminal.get("status") == result["validation"]["terminal_status"], "terminal status changed")
    checks = terminal.get("checks") or {}
    require(len(checks) == 18 and all(checks.values()), "terminal is not 18/18")
    require(terminal.get("authority") == AUTHORITY == result.get("authority"), "authority widened or changed")
    require(terminal.get("graph_evidence") == graph, "terminal graph evidence changed")
    terminal_measurements = {row["arm"]: row for row in terminal.get("measurements", [])}
    require(set(terminal_measurements) == set(ARMS), "terminal arms changed")
    for arm in ARMS:
        for compact_key, terminal_key in (("serving_decode_tok_s_99_interval", "speed"), ("cached_tokens", "cached_tokens"), ("output_token_ids_sha256", "output_token_ids_sha256"), ("text_sha256", "text_sha256")):
            require(compact_measurements[arm][compact_key] == terminal_measurements[arm][terminal_key], f"terminal measurement changed: {arm}/{terminal_key}")
    require(result.get("protected_decode_values") == PROTECTED, "protected values changed")

    return {
        "status": "pass",
        "campaign_id": CAMPAIGN,
        "raw_files_verified": len(bindings),
        "terminal_checks": len(checks),
        "dual_full_quality_pass": True,
        "direct_replay": graph["direct_replay"],
        "requested": graph["requested"],
        "site_cells_authorized": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    args = parser.parse_args()
    try:
        report = validate(args.root, args.result)
    except (ValidationError, KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
