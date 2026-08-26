#!/usr/bin/env python3
"""Read-only validator for the current-image eager/F16 native-MTP4 sentinel."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ROOT = Path(
    "/mnt/fast-ai/bench-results/"
    "qwen38-official-f01e-autoround-tp1-mtp4-f16-eager-8k-sentinel-20260826-r1"
)
RESULT = REPO / (
    "experiments/qwen38-27b-b70/data/"
    "2026-08-26-qwen38-official-f01e-autoround-tp1-mtp4-f16-eager-8k-sentinel-r1-result.json"
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


def validate(root: Path, result_path: Path):
    result = load(result_path)
    need(result["status"] == "passed-quality-clean-sentinel", "compact result is not passed")
    for binding in result["tracked_inputs"].values():
        path = REPO / binding["path"]
        need(path.is_file() and digest(path) == binding["sha256"], f"tracked input changed: {path}")

    identity = result["identity"]
    for name, expected in identity["raw_sha256"].items():
        need(digest(root / name) == expected, f"raw identity changed: {name}")
    need((root / "image-id.txt").read_text().strip() == identity["image"].split("@", 1)[1], "image identity changed")
    need((root / "vllm-source-commit.txt").read_text().strip() == identity["vllm_source"], "vLLM source changed")
    need((root / "stack-versions.txt").read_text().splitlines() == [identity["vllm_version"], identity["xpu_kernels_version"]], "stack versions changed")

    inspect = load(root / "container-inspect.json")
    need(len(inspect) == 1, "container identity count changed")
    container = inspect[0]
    args = container["Config"]["Cmd"]
    env = container["Config"]["Env"]
    config = result["config"]
    need(container["Image"] == identity["image"].split("@", 1)[1], "container image changed")
    need("--enforce-eager" in args and "--kv-cache-dtype" not in args, "eager/F16 identity changed")
    need("--compilation-config" not in args and "VLLM_XPU_ENABLE_XPU_GRAPH=1" not in env, "graph identity appeared")
    spec = json.loads(args[args.index("--speculative-config") + 1])
    need(spec == {"method": config["speculative_method_requested"], "num_speculative_tokens": 4}, "MTP4 identity changed")
    need("PYTHONHASHSEED=0" in env and "ONEAPI_DEVICE_SELECTOR=level_zero:0" in env, "seed or device identity changed")

    cleanup = result["cleanup"]
    terminal = load(root / "terminal-receipt.json")
    need(digest(root / "terminal-receipt.json") == cleanup["terminal_receipt_sha256"], "terminal receipt changed")
    need(terminal["terminal"] and terminal["state"] == "passed-quality-clean-sentinel", "terminal classification changed")
    need(terminal["launch_git_head"] == cleanup["launch_git_head"], "launch Git identity changed")
    need(terminal["protected_profiles_untouched"] and not terminal["historical_replacement_allowed"], "protected authority widened")
    need(not terminal["automatic_descendant_expansion"], "automatic descendants were enabled")

    arm = load(root / "arm-result.json")
    need(digest(root / "arm-result.json") == cleanup["arm_result_sha256"], "arm receipt changed")
    need(arm["state"] == "passed-quality-clean-sentinel" and arm["exact_8k_return_code"] == 0, "8K arm did not pass")
    need(arm["quality_return_code"] == 0 and arm["cleanup_passed"] and arm["startup_identity_passed"], "identity, quality, or cleanup failed")
    need(arm["acceptance_passed"] and arm["target_verification_passed"], "mechanism or target gate failed")
    need(arm["descendant_expansion_authorized"] and not arm["descendant_execution_authorized"], "expansion authority changed")

    gates = load(root / "verification-gates.json")
    mechanism = result["mechanism"]
    need(digest(root / "verification-gates.json") == mechanism["raw_sha256"], "verification gates changed")
    acceptance = gates["acceptance"]
    need(acceptance["passed"] and acceptance["drafted_tokens"] == mechanism["drafted_tokens"], "draft count changed")
    need(acceptance["accepted_tokens"] == mechanism["accepted_tokens"] and acceptance["acceptance_rate"] == mechanism["acceptance_rate"], "acceptance changed")
    target_gate = gates["target_verification"]
    oracle = result["target_oracle"]
    need(target_gate["passed"] and target_gate["first_divergence"] is None, "target parity failed")
    need(target_gate["candidate_ids_sha256"] == oracle["candidate_token_ids_sha256"], "candidate target hash changed")
    need(target_gate["target_ids_sha256"] == oracle["target_token_ids_sha256"], "oracle target hash changed")

    raw_path = root / "exact-depth/depth-8192.json"
    raw = load(raw_path)
    need(raw == load(root / "exact-depth/depth-8192.stdout.json"), "stdout mirror changed")
    need(raw["gate"]["passed"] and all(raw["gate"]["checks"].values()), "8K depth gate failed")
    usage = raw["response"]["usage"]
    need(usage["prompt_tokens"] == 8192 and usage["completion_tokens"] == 128, "8K usage changed")
    need(usage["prompt_tokens_details"]["cached_tokens"] == 0, "cache reuse appeared")
    ttft_s = raw["metric_window"]["time_to_first_token_s"]
    point = {
        "x": 8192,
        "decode_tok_s": raw["metric_window"]["conventional_99_interval_tok_s"],
        "ttft_s": ttft_s,
        "ttft_ms": ttft_s * 1000,
        "effective_prompt_throughput_proxy_tok_s": 8192 / ttft_s,
        "cached_tokens": 0,
        "completion_tokens": 128,
        "output_token_ids_sha256": raw["response"]["output_token_ids_sha256"],
        "raw_sha256": digest(raw_path),
    }
    need(point == result["point"], "compact point differs from raw receipt")
    target_path = Path(oracle["path"])
    need(digest(target_path) == oracle["raw_sha256"], "frozen target receipt changed")
    target = load(target_path)
    need(raw["response"]["token_ids"] == target["response"]["token_ids"], "candidate no longer matches target tokens")
    need(raw["response"]["output_token_ids_sha256"] == oracle["target_token_ids_sha256"], "target hash parity changed")

    quality = load(root / "quality.json")
    expected_quality = result["quality"]
    need(digest(root / "quality.json") == expected_quality["raw_sha256"], "quality receipt changed")
    need(quality["pass_all"] and quality["baseline_match_all"], "full quality or baseline gate failed")
    need(len(quality["exact_cases"]) == 7 and all(case["pass"] for case in quality["exact_cases"]), "exact quality changed")
    repeat = quality["repeat_case"]
    need(repeat["pass"] and repeat["repeats"] == 8 and len(repeat["unique_hashes"]) == 1, "repeat determinism changed")
    need(quality["long_context_case"]["pass"], "8K needle failed")
    need(len(quality["baseline_comparisons"]) == 24 and all(quality["baseline_comparisons"].values()), "baseline comparisons changed")
    usages = [case["usage"] for case in quality["exact_cases"]]
    usages.extend(run["usage"] for run in repeat["runs"])
    usages.append(quality["long_context_case"]["usage"])
    need(all(item["prompt_tokens_details"]["cached_tokens"] == 0 for item in usages), "quality cache reuse appeared")

    verification = load(root / "model-verification.json")
    expected_verification = result["model_verification"]
    need(digest(root / "model-verification.json") == expected_verification["raw_sha256"], "model verification changed")
    need(verification["status"] == "verified" and len(verification["files"]) == 19, "model verification weakened")
    need(all(item["direct_mode"] == "odirect" and item["ok"] and item["paths_coherent"] for item in verification["files"]), "model read paths weakened")

    authority = result["authority"]
    need(authority["site_cells"] == 0 and not authority["site_or_family_publication_authorized"], "publication authority appeared")
    need(authority["additive_profile_specific_evidence"] and not authority["historical_or_protected_replacement"], "replacement authority appeared")
    need(not authority["headline_graph_or_frontier_replacement"], "graph/frontier authority appeared")
    need(not authority["automatic_descendant_expansion"] and not authority["descendant_execution_authorized_by_this_result"], "automatic execution appeared")
    need(authority["separately_preregistered_expansion_authorized"] and authority["x0_remains_missing"], "parent scope changed")
    return {
        "status": "pass",
        "cells_published": 0,
        "diagnostic_points_verified": 1,
        "exact_context": 8192,
        "mtp": 4,
        "accepted": 92,
        "drafted": 140,
        "target_parity": True,
        "expansion": "separately-authorized-not-automatic",
    }


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
