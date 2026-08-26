#!/usr/bin/env python3
"""Fail-closed validator for the Q8-KV exact-2K R3 retry."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
from pathlib import Path
import sys
from typing import Any

HERE = Path(__file__).resolve().parent
RUNNER_PATH = HERE / "run-20260825-qwen36-mtpq8-q8kv-tp1-mtp01234-exact2k-classification-r3.py"
R2_VALIDATOR_PATH = HERE / "validate-20260825-qwen36-mtpq8-q8kv-tp1-mtp01234-exact2k-classification-r2.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


RUNNER = load_module(RUNNER_PATH, "qwen36_q8kv_exact2k_r3_validator_runner")
R2V = load_module(R2_VALIDATOR_PATH, "qwen36_q8kv_exact2k_r2_validator_for_r3")
GateError = RUNNER.GateError

EXPECTED_CLEANUP = {"forced_kill": False, "port_closed": True, "render_node_idle": True, "server_survivor": False}
EXPECTED_UNSET = ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"]
ENV_KEYS = (
    "ONEAPI_DEVICE_SELECTOR", "ZE_AFFINITY_MASK", "ZES_ENABLE_SYSMAN",
    "UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS", "GGML_SYCL_ENABLE_VMM",
    "GGML_SYCL_ENABLE_GRAPH", "GGML_SYCL_GRAPH_CACHE_SIZE", "GGML_SYCL_ENABLE_DNN",
    "GGML_SYCL_ENABLE_OPT", "GGML_SYCL_FA_ONEDNN", "GGML_SYCL_FA_ONEDNN_MAX_KV",
    "GGML_SYCL_ENABLE_MKL_FA", "GGML_SYCL_ENABLE_FLASH_ATTN", "NO_PROXY", "no_proxy",
)


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def strict_receipt(receipt: dict[str, Any], runtime: dict[str, Any]) -> bool:
    identity, fixture = receipt.get("run_identity") or {}, receipt.get("fixture") or {}
    request, response = receipt.get("request") or {}, receipt.get("response") or {}
    usage = response.get("usage") or {}
    details = usage.get("prompt_tokens_details") or {}
    metric = receipt.get("metric_window") or {}
    checks = (receipt.get("gate") or {}).get("checks") or {}
    required_gate_names = {
        "cached_tokens_zero", "completion_tokens_exact", "context_capacity_covers_prompt_and_output",
        "done_seen", "endpoint_is_v1_completions", "finish_reason_length", "llama_cache_zero_if_reported",
        "llama_prompt_not_truncated", "llama_stop_is_limit", "metric_events_exact",
        "metric_intervals_exact", "metric_span_positive", "no_context_shift_reported",
        "request_disables_prompt_cache", "request_disables_prompt_truncation",
        "request_disables_special_tokens", "request_ignores_eos", "request_prompt_depth_exact",
        "request_prompt_hash_exact", "request_prompt_is_flat_integer_array", "request_returns_token_ids",
        "returned_prompt_ids_exact_if_reported", "stream_token_ids_exact", "usage_prompt_tokens_exact",
        "usage_total_tokens_exact",
    }
    token_ids = response.get("token_ids") if isinstance(response.get("token_ids"), list) else []
    return bool(
        receipt.get("schema") == "openai-token-depth-benchmark-v1"
        and receipt.get("status") == "passed" and (receipt.get("gate") or {}).get("passed") is True
        and set(checks) == required_gate_names and all(checks.values())
        and identity.get("model") == runtime["server_contract"]["model_alias"]
        and identity.get("depth") == identity.get("active_context_tokens") == RUNNER.DEPTH
        and identity.get("case_id") == RUNNER.CASE_ID
        and identity.get("configured_context_capacity") == runtime["server_contract"]["context_capacity"]
        and identity.get("max_tokens") == 128 and identity.get("metric_events") == 100
        and identity.get("metric_intervals") == 99 and identity.get("endpoint") == "/v1/completions"
        and fixture.get("fixture_id") == runtime["fixture"]["fixture_id"]
        and fixture.get("fixture_sha256") == runtime["fixture"]["sha256"]
        and fixture.get("selected_case_sha256") == "d4fc9f41aecece5ca9cdcdcc21ef602c26f709235448badb0c258627bd7410f8"
        and fixture.get("prompt_token_ids_sha256") == runtime["fixture"]["prompt_token_ids_sha256"][1]
        and request.get("model") == runtime["server_contract"]["model_alias"]
        and request.get("prompt_token_count") == RUNNER.DEPTH
        and request.get("prompt_token_ids_sha256") == runtime["fixture"]["prompt_token_ids_sha256"][1]
        and request.get("max_tokens") == 128 and request.get("seed") == 1
        and request.get("temperature") == 0 and request.get("top_p") == 1
        and request.get("cache_prompt") is False and request.get("add_special_tokens") is False
        and request.get("ignore_eos") is True and request.get("truncate_prompt_tokens") is None
        and request.get("return_token_ids") is True and request.get("return_tokens") is True
        and request.get("stream") is True and request.get("stream_options") == {"include_usage": True}
        and usage.get("prompt_tokens") == RUNNER.DEPTH and usage.get("completion_tokens") == 128
        and usage.get("total_tokens") == RUNNER.DEPTH + 128 and details.get("cached_tokens") == 0
        and response.get("llama_cache_n") == 0 and len(token_ids) == 128
        and all(type(token) is int and token >= 0 for token in token_ids)
        and response.get("output_token_ids_sha256") == R2V.token_ids_sha256(token_ids)
        and metric.get("timestamped_events") == 100 and metric.get("inter_token_intervals") == 99
        and isinstance(metric.get("conventional_99_interval_tok_s"), (int, float))
        and math.isfinite(metric["conventional_99_interval_tok_s"])
        and metric["conventional_99_interval_tok_s"] > 0
    )


def strict_audit(root: Path, manifest: dict[str, Any]) -> dict[str, bool]:
    runtime = RUNNER.runtime_manifest(manifest)
    execution = RUNNER.R1.Execution(runtime)
    identity = load_json(root / "identity.json")
    expected_env = RUNNER.CORE.oneapi_environment(Path(runtime["runtime"]["binary"]).parent)
    runtime_identity = identity.get("runtime") or {}
    checks: dict[str, bool] = {
        "complete_primary_identity": bool(
            identity.get("campaign_id") == RUNNER.CAMPAIGN_ID
            and isinstance(identity.get("git_head"), str) and len(identity["git_head"]) == 40
            and identity.get("git_head") == identity.get("origin_main")
            and identity.get("model") == {k: runtime["model"][k] for k in ("path", "size_bytes", "sha256", "repository", "revision")}
            and all(runtime_identity.get(k) == runtime["runtime"][k] for k in ("binary", "binary_sha256", "manifest", "manifest_sha256", "source_commit"))
            and runtime_identity.get("local_dsos") == runtime["runtime"]["effective_local_shared_libraries"]
            and runtime["runtime"]["reported_version"] in str(runtime_identity.get("version", "")).splitlines()
            and isinstance(runtime_identity.get("ldd"), list) and len(runtime_identity["ldd"]) >= len(runtime["runtime"]["effective_local_shared_libraries"])
            and identity.get("fixture_sha256") == runtime["fixture"]["sha256"]
            and identity.get("explicitly_unset_environment") == EXPECTED_UNSET
            and identity.get("runtime_environment") == {key: expected_env[key] for key in ENV_KEYS}
            and identity.get("failed_r1_parent_hashes") == {
                "terminal": manifest["failed_r1_parent"]["raw"]["terminal-receipt.json"],
                "identity": manifest["failed_r1_parent"]["raw"]["identity.json"],
            }
            and identity.get("failed_r2_parent_hashes") == {
                "terminal": manifest["failed_r2_parent"]["terminal_sha256"],
                "identity": manifest["failed_r2_parent"]["identity_sha256"],
            }
        ),
        "exact_server_argv": identity.get("server_argv") == {
            arm: execution.server_argv_for_mtp(route) for arm, route in RUNNER.ARM_PLAN
        },
    }
    try:
        RUNNER.verify_ldd_closure("\n".join(runtime_identity.get("ldd", [])), runtime["runtime"])
        checks["runtime_ldd_closure"] = True
    except (GateError, TypeError):
        checks["runtime_ldd_closure"] = False

    for arm, route in RUNNER.ARM_PLAN:
        arm_dir = root / arm
        expected_names = {"arm-result.json", "cleanup.json", "models.json", "server.log", *(f"repeat-{r}" for r in RUNNER.REPEATS)}
        checks[f"{arm}_exact_inventory"] = arm_dir.is_dir() and {p.name for p in arm_dir.iterdir()} == expected_names
        arm_result, cleanup = load_json(arm_dir / "arm-result.json"), load_json(arm_dir / "cleanup.json")
        checks[f"{arm}_successful_lifetime"] = bool(
            arm_result.get("status") == "completed-awaiting-classification" and arm_result.get("error") is None
            and arm_result.get("cleanup") == cleanup == EXPECTED_CLEANUP
            and (arm_dir / "server.log").is_file() and (arm_dir / "server.log").stat().st_size > 0
        )
        parsed = RUNNER.CORE.acceptance_rows(arm_dir / "server.log") if (arm_dir / "server.log").is_file() else []
        for repeat in RUNNER.REPEATS:
            repeat_dir = arm_dir / f"repeat-{repeat}"
            expected_repeat = {"exact-depth.json", "exact-depth.stdout.json"}
            if route > 0:
                expected_repeat.add("draft-counters.json")
            checks[f"{arm}_repeat{repeat}_inventory"] = repeat_dir.is_dir() and {p.name for p in repeat_dir.iterdir()} == expected_repeat
            checks[f"{arm}_repeat{repeat}_receipt"] = strict_receipt(load_json(repeat_dir / "exact-depth.json"), runtime)
            if route > 0:
                counter = load_json(repeat_dir / "draft-counters.json")
                rows = counter.get("new_rows") if isinstance(counter.get("new_rows"), list) else []
                checks[f"{arm}_repeat{repeat}_counter"] = bool(
                    counter.get("active_context_tokens") == RUNNER.DEPTH and counter.get("repeat") == repeat
                    and counter.get("rows_before") == repeat - 1 and counter.get("rows_after") == repeat
                    and len(rows) == 1 and len(parsed) == 3 and rows[0] == parsed[repeat - 1]
                    and 0 < rows[0].get("accepted", 0) <= rows[0].get("generated", 0)
                    and abs(rows[0].get("ratio", -1) - round(rows[0]["accepted"] / rows[0]["generated"], 5)) <= 0.00001
                )
            else:
                checks[f"{arm}_no_counters"] = len(parsed) == 0 and not (repeat_dir / "draft-counters.json").exists()
    return checks


def validate(root: Path, manifest_path: Path) -> dict[str, Any]:
    manifest = RUNNER.load_manifest()
    strict = strict_audit(root, manifest)
    RUNNER._configure_base()
    R2V.RUNNER = RUNNER
    original_load = R2V.load_json

    def merged_load(path: Path) -> dict[str, Any]:
        return manifest if Path(path) == Path(manifest_path) else original_load(path)

    R2V.load_json = merged_load
    try:
        terminal = R2V.validate(root, manifest_path)
    finally:
        R2V.load_json = original_load
    terminal["strict_r3_checks"] = strict
    terminal["failed_r2_parent"] = {
        "terminal_sha256": manifest["failed_r2_parent"]["terminal_sha256"],
        "identity_sha256": manifest["failed_r2_parent"]["identity_sha256"],
        "contained_classification_evidence": False,
    }
    if not all(strict.values()):
        terminal["status"] = "failed-evidence-preserve"
        terminal["overall_classification"] = "invalid-evidence"
        terminal["packet_grade"] = "D"
        terminal["route_comparisons"] = [
            {"arm": f"candidate-mtp{route}", "classification": "invalid-evidence", "comparison_to_bracketing_mtp0": None}
            for route in (1, 2, 3, 4)
        ]
    return terminal


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate(args.root, args.manifest)
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        if args.output.exists():
            parser.error(f"create-only output exists: {args.output}")
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if result["status"] == "completed-classification-only" else 2


if __name__ == "__main__":
    raise SystemExit(main())
