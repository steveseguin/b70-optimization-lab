#!/usr/bin/env python3
"""Read-only validation of the Q4_K_XL/F16 cache20 R2 sentinel result."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen38-27b-b70"
CAMPAIGN_ID = "qwen38-q4kxl-f16kv-tp1-target-sycl-graph-cache20-8k-sentinel-20260826-r2"
DEFAULT_ROOT = Path("/mnt/fast-ai/bench-results") / CAMPAIGN_ID
DEFAULT_RECEIPT = LANE / "data/2026-08-26-qwen38-q4kxl-f16kv-tp1-target-sycl-graph-cache20-8k-sentinel-r2-result.json"
ARMS = ("control-graph-off-cache0", "candidate-graph-on-cache20")
EXPECTED_CLEANUP = {
    "forced_kill": False,
    "port_closed": True,
    "render_node_idle": True,
    "server_survivor": False,
}
PROTECTED_VALUES = [
    71.45427094575045,
    30.329809361830037,
    49.05894025767351,
    71.9001988117144,
]
EXPECTED_AUTHORITY = {
    "failure_stops_same_design_full_curve": False,
    "full_curve_preregistration": True,
    "full_graph_curve": False,
    "localmaxxing_submission": False,
    "mtp_or_speculative_cells": 0,
    "prefill_cells": 0,
    "protected_or_headline_replacement": False,
    "selectors": {
        "active_context_tokens": 8192,
        "fit": "off",
        "graph_mode": "matched-control sentinel",
        "mtp": 0,
        "revision": "qwen3.8-27b-current-weights",
        "target_kv": "f16",
        "target_quantization": "UD-Q4_K_XL",
        "tp": 1,
        "transport": "HTTP /v1/completions",
    },
    "site_cells": 0,
    "tp2_or_tp4_cells": 0,
}
COUNTER_KEYS = (
    "device", "requested", "compatibility_rejected", "device_unsupported",
    "cache_entries", "cache_limit", "cache_hit", "cache_miss", "cache_full",
    "direct_replay", "recorded", "created", "updated", "recreated", "replayed",
)
SUMMARY_RE = re.compile(
    r"\[SYCL-GRAPH\] summary device=(?P<device>\d+) requested=(?P<requested>\d+) "
    r"compatibility_rejected=(?P<compatibility_rejected>\d+) "
    r"device_unsupported=(?P<device_unsupported>\d+) cache_entries=(?P<cache_entries>\d+) "
    r"cache_limit=(?P<cache_limit>\d+) cache_hit=(?P<cache_hit>\d+) "
    r"cache_miss=(?P<cache_miss>\d+) cache_full=(?P<cache_full>\d+) "
    r"direct_replay=(?P<direct_replay>\d+) recorded=(?P<recorded>\d+) "
    r"created=(?P<created>\d+) updated=(?P<updated>\d+) recreated=(?P<recreated>\d+) "
    r"replayed=(?P<replayed>\d+)"
)


class ValidationError(RuntimeError):
    """The sealed result evidence no longer satisfies its frozen contract."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValidationError(f"JSON root must be an object: {path}")
    return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def parse_graph_summary(path: Path) -> dict[str, int]:
    text = path.read_text(encoding="utf-8", errors="replace")
    rows = [
        {key: int(value) for key, value in match.groupdict().items()}
        for match in SUMMARY_RE.finditer(text)
    ]
    require(len(rows) == 1, f"expected exactly one graph summary in {path}, got {len(rows)}")
    return rows[0]


def validate(root: Path, receipt_path: Path) -> dict[str, Any]:
    receipt = load_json(receipt_path)
    require(
        receipt.get("schema") == "neural.download.qwen38-q4kxl-f16kv-target-sycl-graph-cache20-8k-sentinel-result.v1",
        "result schema changed",
    )
    require(receipt.get("campaign_id") == CAMPAIGN_ID, "campaign identity changed")
    require(receipt.get("raw_root") == str(DEFAULT_ROOT), "recorded raw root changed")
    require(
        receipt.get("classification") == "completed-valid-mechanism-sentinel-adverse-single-speed-observation",
        "result classification changed",
    )

    tracked = receipt.get("tracked_inputs") or {}
    expected_tracked = {
        "preregistration": (
            "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-q4kxl-f16kv-tp1-target-sycl-graph-cache20-8k-sentinel-r2-prereg.json",
            "00033550919b53f113d95ee374cbf9595d67d01fab45dea86faa971cb5332b87",
        ),
        "runner": (
            "experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-q4kxl-f16kv-tp1-target-sycl-graph-cache20-8k-sentinel-r2.py",
            "12b506083429294241cd24a98912369f9d7511ecc695d888880fbec5a7e3a8d0",
        ),
        "historical_validator": (
            "experiments/qwen38-27b-b70/scripts/validate-20260826-qwen38-q4kxl-f16kv-tp1-target-sycl-graph-cache20-8k-sentinel-r2.py",
            "bf95d2063b1c20763b2b9d12dd1246d9810a4d6e4e3e6e701f38a9ca25e156e9",
        ),
        "historical_tests": (
            "experiments/qwen38-27b-b70/scripts/test_qwen38_q4kxl_f16kv_tp1_target_sycl_graph_cache20_8k_sentinel_r2.py",
            "dff366ff347a1a542ae3696cfeefd2196a75a8e32ceaa5d7efe4f51ec972ed15",
        ),
    }
    require(set(tracked) == set(expected_tracked), "tracked-input inventory changed")
    for name, (relative, expected_sha) in expected_tracked.items():
        require(tracked[name] == {"path": relative, "sha256": expected_sha}, f"tracked binding changed: {name}")
        path = REPO / relative
        require(path.is_file() and sha256_file(path) == expected_sha, f"tracked input changed: {path}")
    prereg = load_json(REPO / expected_tracked["preregistration"][0])
    frozen = prereg.get("frozen_interpretation") or {}
    require(frozen.get("speed_floor") is None, "sentinel unexpectedly had a speed floor")
    require(frozen.get("protected_decode_values") == PROTECTED_VALUES, "preregistered protected values changed")

    expected_files = {
        row["path"]: {"bytes": row["bytes"], "sha256": row["sha256"]}
        for row in receipt.get("raw_files", [])
    }
    require(len(expected_files) == 16, "result must bind exactly 16 raw files")
    require(not any(path.is_symlink() for path in root.rglob("*")), "raw root contains a symlink")
    actual_paths = sorted(path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file())
    require(actual_paths == sorted(expected_files), "raw-file inventory changed")
    for relative, binding in expected_files.items():
        path = root / relative
        require(path.stat().st_size == binding["bytes"], f"raw size changed: {relative}")
        require(sha256_file(path) == binding["sha256"], f"raw hash changed: {relative}")

    identity = load_json(root / "identity.json")
    require(identity.get("campaign_id") == CAMPAIGN_ID, "raw campaign identity mismatch")
    require(
        identity.get("git_head") == identity.get("origin_main") == "d289862088af4b2141e746238a5e746f888ee3fa",
        "launch Git identity mismatch",
    )
    require(identity.get("model") == receipt.get("identity", {}).get("model"), "model identity mismatch")
    require(identity.get("graph_runtime") == receipt.get("identity", {}).get("graph_runtime"), "graph runtime identity mismatch")
    argv_by_arm = identity.get("server_argv") or {}
    require(set(argv_by_arm) == set(ARMS) and argv_by_arm[ARMS[0]] == argv_by_arm[ARMS[1]], "server argv differed between arms")
    argv = argv_by_arm[ARMS[0]]
    require(argv[argv.index("--spec-type") + 1] == "none" and "--spec-draft-model" not in argv, "run was not target-only")
    require(argv[argv.index("-ctk") + 1] == argv[argv.index("-ctv") + 1] == "f16", "run was not F16 KV")
    require(identity.get("runtime_environment") == {
        ARMS[0]: {"GGML_SYCL_ENABLE_GRAPH": "0", "GGML_SYCL_GRAPH_CACHE_SIZE": "0", "ONEAPI_DEVICE_SELECTOR": "level_zero:0"},
        ARMS[1]: {"GGML_SYCL_ENABLE_GRAPH": "1", "GGML_SYCL_GRAPH_CACHE_SIZE": "20", "ONEAPI_DEVICE_SELECTOR": "level_zero:0"},
    }, "runtime environment was not the frozen graph-only arm delta")

    for arm in ARMS:
        models = load_json(root / arm / "models.json")
        model_rows = models.get("data") or []
        require(len(model_rows) == 1, f"unexpected model inventory: {arm}")
        require(model_rows[0].get("id") == "qwen38-q4kxl-f16kv-tp1-graph-8k-r1", f"served alias mismatch: {arm}")
        require(model_rows[0].get("meta", {}).get("ftype") == "Q4_K - Medium", f"served quant mismatch: {arm}")
        require(model_rows[0].get("meta", {}).get("n_ctx") == 32768, f"served context capacity mismatch: {arm}")
        cleanup = load_json(root / arm / "cleanup.json")
        require(cleanup == EXPECTED_CLEANUP, f"cleanup failed: {arm}")
        arm_result = load_json(root / arm / "arm-result.json")
        require(arm_result == {"cleanup": EXPECTED_CLEANUP, "error": None, "status": "completed-awaiting-validation"}, f"arm result changed: {arm}")

    depths: dict[str, dict[str, Any]] = {}
    for arm in ARMS:
        exact = load_json(root / arm / "depth-8192/exact-depth.json")
        require(exact == load_json(root / arm / "depth-8192/exact-depth.stdout.json"), f"exact-depth/stdout mismatch: {arm}")
        require(exact.get("schema") == "openai-token-depth-benchmark-v1" and exact.get("status") == "passed", f"depth receipt failed: {arm}")
        gate = exact.get("gate") or {}
        require(gate.get("passed") is True and all((gate.get("checks") or {}).values()), f"depth gate failed: {arm}")
        run_identity = exact.get("run_identity") or {}
        require(run_identity.get("depth") == run_identity.get("active_context_tokens") == 8192, f"active depth failed: {arm}")
        require(run_identity.get("configured_context_capacity") == 32768 and run_identity.get("max_tokens") == 128, f"depth capacity/window mismatch: {arm}")
        response = exact.get("response") or {}
        require(response.get("usage") == {
            "completion_tokens": 128,
            "prompt_tokens": 8192,
            "prompt_tokens_details": {"cached_tokens": 0},
            "total_tokens": 8320,
        }, f"usage/cache-zero mismatch: {arm}")
        require(len(response.get("token_ids") or []) == 128, f"returned token count mismatch: {arm}")
        depths[arm] = exact

    left = depths[ARMS[0]]["response"]
    right = depths[ARMS[1]]["response"]
    parity_keys = ("output_token_ids_sha256", "text_sha256", "token_ids", "usage", "returned_prompt_token_ids_sha256")
    require(all(left.get(key) == right.get(key) for key in parity_keys), "graph-on/off output or usage parity failed")

    control_graph = parse_graph_summary(root / ARMS[0] / "server.log")
    candidate_graph = parse_graph_summary(root / ARMS[1] / "server.log")
    expected_control = {key: 0 for key in COUNTER_KEYS}
    expected_candidate = {
        "device": 0, "requested": 146, "compatibility_rejected": 0,
        "device_unsupported": 0, "cache_entries": 20, "cache_limit": 20,
        "cache_hit": 126, "cache_miss": 20, "cache_full": 0,
        "direct_replay": 126, "recorded": 20, "created": 20,
        "updated": 0, "recreated": 0, "replayed": 146,
    }
    require(control_graph == expected_control, "graph-off counters were not exactly zero")
    require(candidate_graph == expected_candidate, "cache20 graph counters changed")
    require(candidate_graph["requested"] == candidate_graph["cache_hit"] + candidate_graph["cache_miss"], "requested hit/miss conservation failed")
    require(candidate_graph["requested"] == candidate_graph["replayed"], "requested/replayed conservation failed")
    require(candidate_graph["cache_hit"] == candidate_graph["direct_replay"] >= 120, "direct replay floor failed")
    require(candidate_graph["cache_miss"] == candidate_graph["recorded"] == candidate_graph["created"] == candidate_graph["cache_entries"] == 20, "cache creation conservation failed")
    graph_evidence = load_json(root / ARMS[1] / "graph-evidence.json")
    require(graph_evidence == {**candidate_graph, "summary_count": 1}, "graph-evidence file changed")

    terminal = load_json(root / "terminal-receipt.json")
    validator_stdout = load_json(root / "validator.stdout.json")
    require(terminal == validator_stdout, "terminal and validator stdout differ")
    require(terminal.get("schema") == "neural.download.qwen38-q4kxl-f16kv-target-sycl-graph-cache20-8k-sentinel-terminal.v2", "terminal schema changed")
    require(terminal.get("status") == "completed-valid-target-only-q4kxl-graph-8k-sentinel", "terminal status changed")
    require(terminal.get("authority") == receipt.get("terminal_authority") == EXPECTED_AUTHORITY, "terminal authority widened or changed")
    require(terminal.get("graph_evidence") == graph_evidence, "terminal graph evidence mismatch")
    require(terminal.get("checks", {}).get("protected_values_immutable") is True, "terminal protected-value gate failed")

    measurements = {
        ARMS[0]: {
            "active_context_tokens": 8192,
            "serving_decode_tok_s_99_interval": depths[ARMS[0]]["metric_window"]["conventional_99_interval_tok_s"],
            "output_token_ids_sha256": left["output_token_ids_sha256"],
            "text_sha256": left["text_sha256"],
            "returned_prompt_token_ids_sha256": left.get("returned_prompt_token_ids_sha256"),
            "cached_tokens": left["usage"]["prompt_tokens_details"]["cached_tokens"],
        },
        ARMS[1]: {
            "active_context_tokens": 8192,
            "serving_decode_tok_s_99_interval": depths[ARMS[1]]["metric_window"]["conventional_99_interval_tok_s"],
            "output_token_ids_sha256": right["output_token_ids_sha256"],
            "text_sha256": right["text_sha256"],
            "returned_prompt_token_ids_sha256": right.get("returned_prompt_token_ids_sha256"),
            "cached_tokens": right["usage"]["prompt_tokens_details"]["cached_tokens"],
        },
    }
    require(receipt.get("measurements") == measurements, "compact measurements do not match raw receipts")
    require(receipt.get("graph_counters") == {ARMS[0]: control_graph, ARMS[1]: candidate_graph}, "compact graph counters do not match logs")
    terminal_measurements = {row["arm"]: row for row in terminal.get("measurements", [])}
    require(set(terminal_measurements) == set(ARMS), "terminal measurement arms changed")
    for arm in ARMS:
        compact = measurements[arm]
        raw_terminal = terminal_measurements[arm]
        for key in ("serving_decode_tok_s_99_interval", "output_token_ids_sha256", "text_sha256", "returned_prompt_token_ids_sha256", "cached_tokens"):
            require(raw_terminal.get(key) == compact[key], f"terminal measurement mismatch: {arm}/{key}")

    observation = receipt.get("single_sentinel_performance_observation") or {}
    control_speed = measurements[ARMS[0]]["serving_decode_tok_s_99_interval"]
    candidate_speed = measurements[ARMS[1]]["serving_decode_tok_s_99_interval"]
    relative = (candidate_speed / control_speed - 1.0) * 100.0
    require(observation.get("classification") == "adverse-non-authoritative-no-speed-floor", "speed observation classification changed")
    require(observation.get("graph_off_tok_s") == control_speed and observation.get("graph_on_tok_s") == candidate_speed, "speed observation values changed")
    require(math.isclose(observation.get("graph_on_relative_percent"), relative, rel_tol=0.0, abs_tol=1e-15), "relative speed observation changed")
    require(relative < 0 and observation.get("speed_authority") is False, "adverse observation gained speed authority")

    require(receipt.get("protected_decode_values") == PROTECTED_VALUES, "protected values changed")
    require(receipt.get("checks") == {
        "all_16_raw_files_hash_bound": True,
        "terminal_and_validator_stdout_exactly_equal": True,
        "launch_identity_clean_pushed_main": True,
        "model_and_runtime_identity_bound": True,
        "target_only_f16_kv_tp1": True,
        "only_graph_environment_differs": True,
        "both_exact_depth_gates_pass": True,
        "cached_tokens_zero_both_arms": True,
        "exact_token_text_usage_and_prompt_parity": True,
        "control_graph_counters_zero": True,
        "candidate_cache20_counter_conservation_pass": True,
        "cleanup_pass_both_arms": True,
        "terminal_authority_exactly_bound": True,
        "protected_values_immutable": True,
    }, "compact checks changed")

    return {
        "status": "pass",
        "campaign_id": CAMPAIGN_ID,
        "classification": receipt["classification"],
        "raw_files_verified": len(expected_files),
        "graph_on_relative_percent": relative,
        "candidate_graph_counters": candidate_graph,
        "terminal_authority": EXPECTED_AUTHORITY,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    args = parser.parse_args()
    try:
        result = validate(args.root, args.receipt)
    except (ValidationError, KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
