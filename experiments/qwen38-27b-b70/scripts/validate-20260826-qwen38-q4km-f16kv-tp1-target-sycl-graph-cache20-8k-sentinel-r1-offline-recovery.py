#!/usr/bin/env python3
"""Read-only validation of the Q4_K_M/F16 cache-20 R1 offline recovery."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen38-27b-b70"
CAMPAIGN_ID = "qwen38-q4km-f16kv-tp1-target-sycl-graph-8k-sentinel-20260826-r1"
DEFAULT_ROOT = Path("/mnt/fast-ai/bench-results") / CAMPAIGN_ID
DEFAULT_RECEIPT = LANE / "data/2026-08-26-qwen38-q4km-f16kv-tp1-target-sycl-graph-cache20-8k-sentinel-r1-offline-recovery.json"
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
    """The sealed recovery evidence no longer satisfies its frozen contract."""


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
    require(receipt.get("schema") == "neural.download.qwen38-q4km-f16kv-target-sycl-graph-cache20-8k-offline-recovery.v1", "recovery schema changed")
    require(receipt.get("campaign_id") == CAMPAIGN_ID, "campaign identity changed")
    require(receipt.get("raw_root") == str(DEFAULT_ROOT), "recorded raw root changed")
    require(receipt.get("classification") == "recovered-valid-mechanism-sentinel-original-procedural-failure-preserved", "recovery classification changed")
    require(receipt.get("original_closeout") == {
        "control_status": "completed-awaiting-validation",
        "candidate_status": "failed-preserve",
        "candidate_error": "GateError: server graph mechanism evidence failed",
        "terminal_receipt_written": False,
        "graph_evidence_written": False,
        "cause": "The historical Q4_K_M runner delegates execution to the Q5 base runner, which calls GRAPH.IMPL.F16.graph_evidence after generation and cleanup. That inherited helper requires cache_limit == 8. The raw candidate correctly reported cache_limit == 20, so the report parser rejected a passing cache20 mechanism result before a terminal receipt could be written.",
        "performance_or_quality_failure": False,
        "gpu_rerun_required": False,
        "original_status_and_runner_preserved": True,
    }, "original procedural closeout changed")

    tracked = receipt.get("tracked_inputs") or {}
    expected_tracked = {
        "preregistration": ("experiments/qwen38-27b-b70/data/2026-08-26-qwen38-q4km-f16kv-tp1-target-sycl-graph-8k-sentinel-r1-prereg.json", "65dfd2916c47f1988d1634e3c0ee77b6b31a11805b7858fa3a9a50bfe5311310"),
        "historical_runner": ("experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-q4km-f16kv-tp1-target-sycl-graph-8k-sentinel-r1.py", "b9e150dc2c69890a905b16ae2ac2b984b9d848ca2f9e532cf0df0ff4d9926de4"),
        "inherited_base_runner": ("experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-q5ks-f16kv-tp1-target-sycl-graph-8k-sentinel-r1.py", "c20e16c4e88f1bc0884c3ad82796fc0d415333af50e0aa638cccb6bfe1eeb40d"),
        "historical_validator": ("experiments/qwen38-27b-b70/scripts/validate-20260826-qwen38-q4km-f16kv-tp1-target-sycl-graph-8k-sentinel-r1.py", "5a15e2411599f5a5596e1defbda1a7a8eaa51dff8d9ed65f0973d0108bff4b8f"),
        "inherited_graph_parser": ("experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/run-20260825-qwen36-q8-f16-tp1-sycl-graph-quality-r1.py", "501d3f37e79791aa8f97c740fbbe90fdc4b75483880441df14147e21289a0cfc"),
    }
    require(set(tracked) == set(expected_tracked), "tracked-input inventory changed")
    for name, (relative, expected_sha) in expected_tracked.items():
        require(tracked[name] == {"path": relative, "sha256": expected_sha}, f"tracked binding changed: {name}")
        path = REPO / relative
        require(path.is_file() and sha256_file(path) == expected_sha, f"tracked input changed: {path}")
    runner_text = (REPO / expected_tracked["historical_runner"][0]).read_text(encoding="utf-8")
    base_runner_text = (REPO / expected_tracked["inherited_base_runner"][0]).read_text(encoding="utf-8")
    parser_text = (REPO / expected_tracked["inherited_graph_parser"][0]).read_text(encoding="utf-8")
    manifest = load_json(REPO / expected_tracked["preregistration"][0])
    require("def main() -> int: return BASE.main()" in runner_text, "historical Q4_K_M delegation changed")
    require("GRAPH.IMPL.F16.graph_evidence" in base_runner_text, "inherited base runner no longer shows parser call")
    require('"cache_limit": 8' in parser_text and 'row["cache_limit"] == 8' in parser_text, "inherited cache-8 hardcode not found")

    expected_files = {
        row["path"]: {"bytes": row["bytes"], "sha256": row["sha256"]}
        for row in receipt.get("raw_files", [])
    }
    require(len(expected_files) == 13, "recovery must bind exactly the 13 original raw files")
    actual_paths = sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    )
    require(not any(path.is_symlink() for path in root.rglob("*")), "raw root contains a symlink")
    require(actual_paths == sorted(expected_files), "raw-file inventory changed; terminal or other artifact may have been added")
    for relative, binding in expected_files.items():
        path = root / relative
        require(path.stat().st_size == binding["bytes"], f"raw size changed: {relative}")
        require(sha256_file(path) == binding["sha256"], f"raw hash changed: {relative}")

    identity = load_json(root / "identity.json")
    require(identity.get("campaign_id") == CAMPAIGN_ID, "raw campaign identity mismatch")
    require(identity.get("git_head") == identity.get("origin_main") == "3538d51b8f4517b3ccfbee1fba8e5a0252c38c55", "launch Git identity mismatch")
    require(identity.get("model") == receipt.get("identity", {}).get("model"), "model identity mismatch")
    require(identity.get("graph_runtime") == receipt.get("identity", {}).get("graph_runtime"), "graph runtime identity mismatch")
    require(identity.get("model") == manifest.get("model"), "raw model identity differs from preregistration")
    require(identity.get("graph_runtime") == manifest.get("graph_runtime"), "raw graph runtime differs from preregistration")
    argv_by_arm = identity.get("server_argv") or {}
    require(set(argv_by_arm) == set(ARMS) and argv_by_arm[ARMS[0]] == argv_by_arm[ARMS[1]], "server argv differed between arms")
    argv = argv_by_arm[ARMS[0]]
    server_contract = manifest.get("server_contract") or {}
    require(argv[argv.index("-m") + 1] == manifest["model"]["path"], "served model path changed")
    require(argv[argv.index("--alias") + 1] == server_contract.get("model_alias"), "served alias argv changed")
    require(argv[argv.index("--port") + 1] == str(server_contract.get("port")), "served port changed")
    require(argv[argv.index("-c") + 1] == str(server_contract.get("context_capacity")), "served context capacity changed")
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
        require(model_rows[0].get("id") == "qwen38-q4km-f16kv-tp1-graph-8k-r1", f"served alias mismatch: {arm}")
        require(model_rows[0].get("meta", {}).get("ftype") == "Q4_K - Medium", f"served quant mismatch: {arm}")
        require(model_rows[0].get("meta", {}).get("n_ctx") == 32768, f"served context capacity mismatch: {arm}")
        cleanup = load_json(root / arm / "cleanup.json")
        require(cleanup == EXPECTED_CLEANUP, f"cleanup failed: {arm}")
        arm_result = load_json(root / arm / "arm-result.json")
        require(arm_result.get("cleanup") == EXPECTED_CLEANUP, f"arm-result cleanup mismatch: {arm}")

    control_result = load_json(root / ARMS[0] / "arm-result.json")
    candidate_result = load_json(root / ARMS[1] / "arm-result.json")
    require(control_result == {"cleanup": EXPECTED_CLEANUP, "error": None, "status": "completed-awaiting-validation"}, "original control status changed")
    require(candidate_result == {"cleanup": EXPECTED_CLEANUP, "error": "GateError: server graph mechanism evidence failed", "status": "failed-preserve"}, "original candidate failure changed")
    for forbidden in ("terminal-receipt.json", "validator.stdout.json", "candidate-graph-on-cache20/graph-evidence.json"):
        require(not (root / forbidden).exists(), f"original no-terminal failure no longer preserved: {forbidden}")

    depths: dict[str, dict[str, Any]] = {}
    for arm in ARMS:
        exact_path = root / arm / "depth-8192/exact-depth.json"
        stdout_path = root / arm / "depth-8192/exact-depth.stdout.json"
        exact = load_json(exact_path)
        require(exact == load_json(stdout_path), f"exact-depth/stdout duplicate mismatch: {arm}")
        require(exact.get("schema") == "openai-token-depth-benchmark-v1" and exact.get("status") == "passed", f"depth receipt status failed: {arm}")
        gate = exact.get("gate") or {}
        require(gate.get("passed") is True and all((gate.get("checks") or {}).values()), f"exact-depth gate failed: {arm}")
        run_identity = exact.get("run_identity") or {}
        require(run_identity.get("depth") == run_identity.get("active_context_tokens") == 8192, f"active-depth identity failed: {arm}")
        require(run_identity.get("configured_context_capacity") == 32768 and run_identity.get("max_tokens") == 128, f"depth capacity/window mismatch: {arm}")
        require(run_identity.get("model") == server_contract.get("model_alias") and run_identity.get("endpoint") == "/v1/completions", f"depth served identity mismatch: {arm}")
        response = exact.get("response") or {}
        usage = response.get("usage") or {}
        require(usage == {"completion_tokens": 128, "prompt_tokens": 8192, "prompt_tokens_details": {"cached_tokens": 0}, "total_tokens": 8320}, f"usage/cache-zero mismatch: {arm}")
        require(len(response.get("token_ids") or []) == 128, f"returned token count mismatch: {arm}")
        depths[arm] = exact

    parity_keys = ("output_token_ids_sha256", "text_sha256", "token_ids", "usage", "returned_prompt_token_ids_sha256")
    left = depths[ARMS[0]]["response"]
    right = depths[ARMS[1]]["response"]
    require(all(left.get(key) == right.get(key) for key in parity_keys), "graph-on/off token, text, prompt or usage parity failed")

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

    measurements = {
        ARMS[0]: {
            "active_context_tokens": 8192,
            "serving_decode_tok_s_99_interval": depths[ARMS[0]]["metric_window"]["conventional_99_interval_tok_s"],
            "output_token_ids_sha256": left["output_token_ids_sha256"],
            "text_sha256": left["text_sha256"],
            "cached_tokens": left["usage"]["prompt_tokens_details"]["cached_tokens"],
        },
        ARMS[1]: {
            "active_context_tokens": 8192,
            "serving_decode_tok_s_99_interval": depths[ARMS[1]]["metric_window"]["conventional_99_interval_tok_s"],
            "output_token_ids_sha256": right["output_token_ids_sha256"],
            "text_sha256": right["text_sha256"],
            "cached_tokens": right["usage"]["prompt_tokens_details"]["cached_tokens"],
        },
    }
    require(receipt.get("measurements") == measurements, "compact measurements do not match raw receipts")
    control_rate = measurements[ARMS[0]]["serving_decode_tok_s_99_interval"]
    candidate_rate = measurements[ARMS[1]]["serving_decode_tok_s_99_interval"]
    require(receipt.get("observed_speed_direction") == {
        "classification": "single-sentinel-observation-not-a-speed-claim",
        "control_tok_s": control_rate,
        "candidate_tok_s": candidate_rate,
        "candidate_vs_control_percent": (candidate_rate / control_rate - 1) * 100,
        "direction": "graph-on was slower in this one 8K sentinel",
    }, "observed speed direction changed")
    require(receipt.get("graph_counters") == {ARMS[0]: control_graph, ARMS[1]: candidate_graph}, "compact graph counters do not match logs")
    require(receipt.get("checks") == {
        "all_13_raw_files_hash_bound": True,
        "launch_identity_clean_pushed_main": True,
        "model_and_runtime_identity_bound": True,
        "target_only_f16_kv_tp1": True,
        "only_graph_environment_differs": True,
        "both_exact_depth_gates_pass": True,
        "cached_tokens_zero_both_arms": True,
        "exact_token_text_usage_and_prompt_parity": True,
        "control_graph_counters_zero": True,
        "candidate_cache20_counter_gate_pass": True,
        "cleanup_pass_both_arms": True,
        "original_failed_status_preserved": True,
        "original_terminal_receipt_absent": True,
    }, "compact recovery checks changed")
    require(receipt.get("authority") == {
        "site_cells": 0,
        "full_graph_curve": False,
        "full_curve_preregistration": True,
        "quality_battery": False,
        "mtp_or_speculative_cells": 0,
        "tp2_or_tp4_cells": 0,
        "prefill_cells": 0,
        "protected_or_headline_replacement": False,
        "localmaxxing_submission": False,
    }, "recovery authority widened")
    require(receipt.get("protected_decode_values") == PROTECTED_VALUES, "protected values changed")

    return {
        "status": "pass",
        "campaign_id": CAMPAIGN_ID,
        "classification": receipt["classification"],
        "raw_files_verified": len(expected_files),
        "candidate_graph_counters": candidate_graph,
        "authority": receipt["authority"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    args = parser.parse_args()
    try:
        result = validate(args.root, args.receipt)
    except (ValidationError, KeyError, OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
