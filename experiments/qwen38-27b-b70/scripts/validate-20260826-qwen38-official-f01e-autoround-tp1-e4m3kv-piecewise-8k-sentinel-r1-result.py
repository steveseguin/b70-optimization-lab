#!/usr/bin/env python3
"""Read-only validator for the current-image PIECEWISE E4M3-KV 8K sentinel."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ROOT = Path(
    "/mnt/fast-ai/bench-results/"
    "qwen38-official-f01e-autoround-tp1-e4m3kv-piecewise-8k-sentinel-20260826-r1"
)
RESULT = REPO / (
    "experiments/qwen38-27b-b70/data/"
    "2026-08-26-qwen38-official-f01e-autoround-tp1-e4m3kv-piecewise-8k-sentinel-r1-result.json"
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
    versions = (root / "stack-versions.txt").read_text().splitlines()
    need(versions == [identity["vllm_version"], identity["xpu_kernels_version"]], "stack versions changed")

    inspect = load(root / "container-inspect.json")
    need(len(inspect) == 1, "container identity count changed")
    container = inspect[0]
    args = container["Config"]["Cmd"]
    env = container["Config"]["Env"]
    config = result["config"]
    need(container["Image"] == identity["image"].split("@", 1)[1], "container image changed")
    need("--kv-cache-dtype" in args and args[args.index("--kv-cache-dtype") + 1] == "fp8_e4m3", "KV identity changed")
    need("VLLM_XPU_ENABLE_XPU_GRAPH=1" in env and "PYTHONHASHSEED=0" in env, "graph or seed identity changed")
    compilation = json.loads(args[args.index("--compilation-config") + 1])
    need(compilation["cudagraph_mode"] == config["graph_mode"], "graph mode changed")
    need(compilation["cudagraph_capture_sizes"] == config["cudagraph_capture_sizes"], "capture sizes changed")
    need(compilation["max_cudagraph_capture_size"] == config["max_cudagraph_capture_size"], "maximum capture size changed")

    terminal = load(root / "terminal-receipt.json")
    cleanup = result["cleanup"]
    need(digest(root / "terminal-receipt.json") == cleanup["terminal_receipt_sha256"], "terminal receipt changed")
    need(terminal["terminal"] and terminal["state"] == "passed-quality-clean-sentinel", "terminal classification changed")
    need(terminal["launch_git_head"] == cleanup["launch_git_head"], "launch Git identity changed")
    need(terminal["protected_profiles_untouched"] and not terminal["historical_replacement_allowed"], "replacement authority widened")
    need(not terminal["automatic_descendant_expansion"], "automatic descendants were enabled")

    arm = load(root / "arm-result.json")
    need(digest(root / "arm-result.json") == cleanup["arm_result_sha256"], "arm receipt changed")
    need(arm["state"] == "passed-quality-clean-sentinel" and arm["exact_8k_return_code"] == 0, "8K arm did not pass")
    need(arm["quality_return_code"] == 0 and arm["cleanup_passed"] and arm["startup_identity_passed"], "arm identity, quality, or cleanup failed")
    need(arm["descendant_expansion_authorized"], "separate expansion authorization disappeared")
    need(not arm["descendant_execution_authorized"], "descendant execution was authorized by the sentinel")

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
    need(authority["additive_profile_specific_evidence"], "additive scope changed")
    need(not authority["headline_or_protected_replacement"] and not authority["historical_replacement"], "replacement authority appeared")
    need(not authority["prior_e4m3_value_replacement"] and not authority["other_depths_tp_mtp_graph_or_kv_inferred"], "selector authority widened")
    need(not authority["automatic_descendant_expansion"] and not authority["descendant_execution_authorized_by_this_result"], "automatic execution appeared")
    need(authority["separately_preregistered_graph_depth_expansion_authorized"], "separate expansion authorization changed")
    need(authority["x0_remains_missing"], "x0 scope changed")
    return {
        "status": "pass",
        "cells_published": 0,
        "diagnostic_points_verified": 1,
        "exact_context": 8192,
        "graph": "PIECEWISE",
        "kv": "fp8_e4m3",
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
