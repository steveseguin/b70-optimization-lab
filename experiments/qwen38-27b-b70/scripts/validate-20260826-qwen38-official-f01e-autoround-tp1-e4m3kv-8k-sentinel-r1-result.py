#!/usr/bin/env python3
"""Read-only validator for the current-image AutoRound E4M3-KV 8K sentinel."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ROOT = Path("/mnt/fast-ai/bench-results/qwen38-official-f01e-autoround-tp1-e4m3kv-8k-sentinel-20260826-r1")
RESULT = REPO / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp1-e4m3kv-8k-sentinel-r1-result.json"


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

    terminal = load(root / "terminal-receipt.json")
    need(digest(root / "terminal-receipt.json") == result["cleanup"]["terminal_receipt_sha256"], "terminal receipt changed")
    need(terminal["terminal"] and terminal["state"] == "passed-quality-clean-sentinel", "terminal classification changed")
    need(terminal["protected_profiles_untouched"] and not terminal["historical_replacement_allowed"], "protected authority widened")
    need(not terminal["automatic_descendant_expansion"], "automatic descendants were enabled")

    arm = load(root / "arm-result.json")
    need(digest(root / "arm-result.json") == result["cleanup"]["arm_result_sha256"], "arm receipt changed")
    need(arm["state"] == "passed-quality-clean-sentinel" and arm["exact_8k_return_code"] == 0, "8K arm did not pass")
    need(arm["quality_return_code"] == 0 and arm["cleanup_passed"] and arm["startup_identity_passed"], "arm identity, quality, or cleanup failed")
    need(not arm["descendant_execution_authorized"], "descendant execution was authorized")

    raw_path = root / "exact-depth/depth-8192.json"
    raw = load(raw_path)
    need(raw == load(root / "exact-depth/depth-8192.stdout.json"), "stdout mirror changed")
    need(raw["gate"]["passed"] and all(raw["gate"]["checks"].values()), "8K depth gate failed")
    usage = raw["response"]["usage"]
    need(usage["prompt_tokens"] == 8192 and usage["completion_tokens"] == 128, "8K usage changed")
    need(usage["prompt_tokens_details"]["cached_tokens"] == 0, "cache reuse appeared")
    point = {
        "x": 8192,
        "decode_tok_s": raw["metric_window"]["conventional_99_interval_tok_s"],
        "ttft_ms": raw["metric_window"]["time_to_first_token_s"] * 1000,
        "effective_prompt_throughput_proxy_tok_s": 8192 / raw["metric_window"]["time_to_first_token_s"],
        "cached_tokens": 0,
        "completion_tokens": 128,
        "output_token_ids_sha256": raw["response"]["output_token_ids_sha256"],
        "raw_sha256": digest(raw_path),
    }
    need(point == result["point"], "compact point differs from raw receipt")

    quality = load(root / "quality.json")
    need(digest(root / "quality.json") == result["quality"]["raw_sha256"], "quality receipt changed")
    need(quality["pass_all"] and quality["baseline_match_all"], "quality did not pass")
    need(len(quality["exact_cases"]) == 7 and all(case["pass"] for case in quality["exact_cases"]), "exact quality changed")
    need(quality["repeat_case"]["pass"] and quality["repeat_case"]["repeats"] == 8 and len(quality["repeat_case"]["unique_hashes"]) == 1, "repeat determinism changed")
    need(quality["long_context_case"]["pass"] and len(quality["baseline_comparisons"]) == 24, "needle or baseline gate changed")

    verification = load(root / "model-verification.json")
    need(digest(root / "model-verification.json") == result["model_verification"]["raw_sha256"], "model verification changed")
    need(verification["status"] == "verified" and len(verification["files"]) == 19, "model verification weakened")
    need(all(item["direct_mode"] == "odirect" and item["ok"] and item["paths_coherent"] for item in verification["files"]), "model read paths weakened")
    authority = result["authority"]
    need(authority["site_cells"] == 1 and authority["active_context_tokens"] == [8192], "site authority widened")
    need(authority["zero_context_cells"] == 0 and authority["f16_cells"] == 0 and authority["graph_or_descendant_cells"] == 0, "selector authority widened")
    need(not authority["headline_or_protected_replacement"], "protected replacement was authorized")
    need(authority["protected_decode_values_unchanged"] == [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144], "protected values changed")
    return {"status": "pass", "cells_verified": 1, "exact_context": 8192, "kv": "fp8_e4m3", "descendants": "not-authorized"}


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
