#!/usr/bin/env python3
"""Read-only validator for the published current-f01e TP4/MTP1 sentinel."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ROOT = Path(
    "/mnt/fast-ai/bench-results/"
    "qwen38-official-f01e-autoround-tp4-mtp1-f16-eager-8k-sentinel-20260826-r1"
)
RESULT = REPO / (
    "experiments/qwen38-27b-b70/data/"
    "2026-08-26-qwen38-official-f01e-autoround-tp4-mtp1-f16-eager-8k-sentinel-r1-result.json"
)


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 << 20), b""):
            value.update(chunk)
    return value.hexdigest()


def need(value, message):
    if not value:
        raise RuntimeError(message)


def arg_value(args, name):
    return args[args.index(name) + 1]


def validate(root: Path, result_path: Path):
    result = load(result_path)
    need(result["status"] == "passed-quality-clean-tp4-mtp1-sentinel", "result is not passed")
    for binding in result["tracked_inputs"].values():
        path = REPO / binding["path"]
        need(path.is_file() and digest(path) == binding["sha256"], f"tracked input changed: {path}")

    identity = result["identity"]
    for name, expected in identity["raw_sha256"].items():
        need(digest(root / name) == expected, f"raw identity changed: {name}")
    need((root / "image-id.txt").read_text().strip() == identity["image"].split("@", 1)[1], "image changed")
    need((root / "vllm-source-commit.txt").read_text().strip() == identity["vllm_source"], "vLLM source changed")
    need((root / "stack-versions.txt").read_text().splitlines() == [identity["vllm_version"], identity["xpu_kernels_version"]], "stack changed")

    inspect = load(root / "container-inspect.json")
    need(len(inspect) == 1, "container identity count changed")
    container = inspect[0]
    args = container["Config"]["Cmd"]
    env = container["Config"]["Env"]
    config = result["config"]
    need(container["Image"] == identity["image"].split("@", 1)[1], "container image changed")
    need(arg_value(args, "--tensor-parallel-size") == "4", "TP4 identity changed")
    need(arg_value(args, "--pipeline-parallel-size") == "1" and arg_value(args, "--data-parallel-size") == "1", "parallel topology changed")
    need(arg_value(args, "--gpu-memory-utilization") == "0.60", "memory identity changed")
    need("--enforce-eager" in args and "--kv-cache-dtype" not in args, "eager/F16 identity changed")
    need("--compilation-config" not in args, "graph compilation appeared")
    spec = json.loads(arg_value(args, "--speculative-config"))
    need(spec == {"method": config["speculative_method_requested"], "num_speculative_tokens": 1}, "MTP1 identity changed")
    need("ZE_AFFINITY_MASK=0,1,2,3" in env, "four-GPU affinity changed")
    need(not any(item.startswith("ONEAPI_DEVICE_SELECTOR=") for item in env), "selector x mask trap appeared")
    need("VLLM_XPU_ENABLE_XPU_GRAPH=0" in env and "VLLM_XPU_GRAPH=0" in env, "graph-off environment changed")
    need("PYTHONHASHSEED=0" in env, "hash seed changed")

    cleanup = result["cleanup"]
    terminal = load(root / "terminal-receipt.json")
    need(digest(root / "terminal-receipt.json") == cleanup["terminal_receipt_sha256"], "terminal receipt changed")
    need(terminal["terminal"] and terminal["runner_return_code"] == 0, "terminal was not rc0")
    need(terminal["state"] == result["status"] and terminal["launch_git_head"] == cleanup["launch_git_head"], "terminal classification changed")
    need(terminal["protected_profiles_untouched"] and not terminal["historical_replacement_allowed"], "protected authority widened")
    need(not terminal["automatic_descendant_expansion"], "automatic descendants appeared")

    arm = load(root / "arm-result.json")
    need(digest(root / "arm-result.json") == cleanup["arm_result_sha256"], "arm receipt changed")
    required = (
        "acceptance_passed", "cleanup_passed", "mtp1_evidence_usable", "objective_quality_passed",
        "parent_baseline_comparison_passed", "rank_cache_isolation_passed",
        "same_topology_target_verification_passed", "startup_identity_passed", "tp4_worker_topology_passed",
    )
    need(arm["state"] == result["status"] and arm["runner_return_code"] == 0, "arm was not passed rc0")
    need(all(arm[key] for key in required), "a sentinel arm gate failed")
    need(arm["exact_8k_return_code"] == 0 and arm["quality_return_code"] == 0, "depth or quality rc changed")
    need(not arm["historical_replacement_allowed"] and not arm["descendant_execution_authorized"], "arm authority widened")

    raw_path = root / "exact-depth/depth-8192.json"
    raw = load(raw_path)
    need(raw == load(root / "exact-depth/depth-8192.stdout.json"), "stdout mirror changed")
    need(raw["gate"]["passed"] and all(raw["gate"]["checks"].values()), "exact 8K gate failed")
    usage = raw["response"]["usage"]
    need(usage["prompt_tokens"] == 8192 and usage["completion_tokens"] == 128, "exact usage changed")
    need(usage["prompt_tokens_details"]["cached_tokens"] == 0, "exact request cache reuse appeared")
    metric = raw["metric_window"]
    ttft_s = metric["time_to_first_token_s"]
    point = {
        "x": 8192,
        "decode_tok_s": metric["conventional_99_interval_tok_s"],
        "historical_100_event_decode_tok_s": metric["historical_100_event_tok_s"],
        "published_decode_field": "conventional_99_interval_tok_s",
        "ttft_s": ttft_s,
        "ttft_ms": ttft_s * 1000,
        "effective_prompt_throughput_proxy_tok_s": 8192 / ttft_s,
        "cached_tokens": 0,
        "completion_tokens": 128,
        "output_token_ids_sha256": raw["response"]["output_token_ids_sha256"],
        "raw_sha256": digest(raw_path),
    }
    need(point == result["point"], "compact point differs from raw")

    gates = load(root / "verification-gates.json")
    mechanism = result["mechanism"]
    need(digest(root / "verification-gates.json") == mechanism["raw_sha256"], "verification gates changed")
    acceptance = gates["acceptance"]
    need(acceptance["passed"] and acceptance["drafted_tokens"] == mechanism["drafted_tokens"], "draft count changed")
    need(acceptance["accepted_tokens"] == mechanism["accepted_tokens"] and acceptance["acceptance_rate"] == mechanism["acceptance_rate"], "acceptance changed")
    oracle = result["same_topology_oracle"]
    target_gate = gates["same_topology_target_verification"]
    need(target_gate["passed"] and target_gate["first_divergence"] is None, "same-topology parity failed")
    need(target_gate["candidate_ids_sha256"] == oracle["candidate_token_ids_sha256"], "candidate hash changed")
    need(target_gate["target_ids_sha256"] == oracle["target_token_ids_sha256"] and target_gate["target_token_count"] == 128, "target hash changed")
    target_path = Path(oracle["target_path"])
    need(digest(target_path) == oracle["target_raw_sha256"], "frozen TP4/MTP0 oracle changed")
    need(digest(Path(oracle["target_terminal_path"])) == oracle["target_terminal_sha256"], "parent terminal changed")
    need(load(Path(oracle["target_terminal_path"]))["state"] == "passed-quality-clean-tp4-oracle-sentinel", "parent oracle no longer passed")
    need(raw["response"]["token_ids"] == load(target_path)["response"]["token_ids"], "token parity changed")

    quality = load(root / "quality.json")
    expected_quality = result["quality"]
    need(digest(root / "quality.json") == expected_quality["raw_sha256"], "quality receipt changed")
    need(quality["pass_all"] and quality["baseline_match_all"], "objective or MTP0 baseline quality failed")
    need(len(quality["exact_cases"]) == 7 and all(case["pass"] for case in quality["exact_cases"]), "exact quality changed")
    repeat = quality["repeat_case"]
    need(repeat["pass"] and repeat["repeats"] == 8 and len(repeat["unique_hashes"]) == 1, "repeat quality changed")
    need(quality["long_context_case"]["pass"], "long-context quality failed")
    need(len(quality["baseline_comparisons"]) == 24 and all(quality["baseline_comparisons"].values()), "baseline comparisons changed")
    usages = [case["usage"] for case in quality["exact_cases"]]
    usages.extend(run["usage"] for run in repeat["runs"])
    usages.append(quality["long_context_case"]["usage"])
    need(len(usages) == 16 and all(item["prompt_tokens_details"]["cached_tokens"] == 0 for item in usages), "quality cache reuse appeared")

    topology = result["topology_and_cache"]
    need(digest(root / "rank-cache-isolation.txt") == topology["rank_cache_raw_sha256"], "rank-cache receipt changed")
    need((root / "rank-cache-isolation.txt").read_text().strip() == topology["rank_cache_status"], "rank-cache status changed")
    verification = load(root / "model-verification.json")
    expected_verification = result["model_verification"]
    need(digest(root / "model-verification.json") == expected_verification["raw_sha256"], "model verification changed")
    need(verification["status"] == "verified" and len(verification["files"]) == 19, "model verification weakened")
    need(all(item["direct_mode"] == "odirect" and item["ok"] and item["paths_coherent"] for item in verification["files"]), "model read paths weakened")

    authority = result["authority"]
    need(authority["site_cells"] == 1 and authority["site_or_family_publication_authorized"], "one-cell authority missing")
    need(authority["quality_grade"] == "C" and authority["additive_profile_specific_evidence"], "grade/additive authority changed")
    need(not authority["historical_or_protected_replacement"] and not authority["headline_graph_or_frontier_replacement"], "replacement authority appeared")
    need(authority["protected_decode_values_unchanged"] == [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144], "protected values changed")
    need(not authority["other_depths_tp_mtp_graph_or_kv_inferred"] and authority["x0_remains_missing"], "scope widened")
    return {"status": "pass", "cells_published": 1, "exact_context": 8192, "tp": 4, "mtp": 1, "grade": "C", "accepted": 61, "drafted": 66, "target_parity": True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--result", type=Path, default=RESULT)
    args = parser.parse_args()
    try:
        report = validate(args.root, args.result)
    except (KeyError, OSError, TypeError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
