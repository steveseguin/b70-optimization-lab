#!/usr/bin/env python3
"""Read-only validator for the official-image AutoRound TP1 graph-mode R3 result."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ROOT = Path("/mnt/fast-ai/bench-results/qwen38-official-f01e-autoround-tp1-f16-graphmodes-depth-20260826-r3")
RESULT = REPO / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp1-f16-graphmodes-depth-r3-result.json"
DEPTHS = [2048, 4096, 8192, 16384, 24576, 32768]


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
    need(result["status"] == "passed-qualified-exact-depth", "compact result is not passed")
    for binding in result["tracked_inputs"].values():
        path = REPO / binding["path"]
        need(path.is_file() and digest(path) == binding["sha256"], f"tracked input changed: {path}")

    terminal = load(root / "terminal-receipt.json")
    need(digest(root / "terminal-receipt.json") == result["cleanup"]["terminal_receipt_sha256"], "terminal receipt changed")
    need(terminal["terminal"] and terminal["state"] == "passed", "campaign is not terminal-passed")
    need(terminal["depth_zero_state"] == "missing", "x=0 authority changed")
    need(not terminal["historical_replacement_allowed"], "historical replacement was enabled")
    need(terminal["protected_full_and_piecewise_profile_untouched"], "protected graph profile was touched")

    expected_arm_config = {
        "eager-f16": ("off", False),
        "piecewise-f16": ("PIECEWISE", True),
    }
    arm_results = {arm["id"]: arm for arm in result["arms"]}
    for arm_id, (graph_mode, graph_enabled) in expected_arm_config.items():
        arm = arm_results[arm_id]
        arm_root = root / arm_id
        raw_arm = load(arm_root / "arm-result.json")
        need(digest(arm_root / "arm-result.json") == arm["arm_result_sha256"], f"arm receipt changed: {arm_id}")
        need(raw_arm["state"] == "passed" and raw_arm["passed_depth_count"] == 6, f"arm did not pass: {arm_id}")
        need(raw_arm["quality_return_code"] == 0 and raw_arm["startup_identity_passed"], f"arm identity or quality failed: {arm_id}")
        need(arm["graph_mode"] == graph_mode and arm["graph"] == ("on" if graph_enabled else "off"), f"graph identity changed: {arm_id}")

        quality = load(arm_root / "quality.json")
        need(digest(arm_root / "quality.json") == arm["quality_sha256"], f"quality receipt changed: {arm_id}")
        need(quality["pass_all"] and quality["baseline_match_all"], f"quality did not pass: {arm_id}")
        need(len(quality["exact_cases"]) == 7 and all(case["pass"] for case in quality["exact_cases"]), f"exact quality changed: {arm_id}")
        need(quality["repeat_case"]["pass"] and quality["repeat_case"]["repeats"] == 8, f"repeat gate changed: {arm_id}")
        need(len(quality["repeat_case"]["unique_hashes"]) == 1, f"repeat determinism changed: {arm_id}")
        need(quality["long_context_case"]["pass"], f"needle failed: {arm_id}")
        need(len(quality["baseline_comparisons"]) == 24, f"baseline comparison count changed: {arm_id}")

        points = []
        for depth in DEPTHS:
            raw_path = arm_root / "exact-depth" / f"depth-{depth}.json"
            raw = load(raw_path)
            need(raw == load(arm_root / "exact-depth" / f"depth-{depth}.stdout.json"), f"stdout mirror changed: {arm_id}/{depth}")
            need(raw["gate"]["passed"] and all(raw["gate"]["checks"].values()), f"depth gate failed: {arm_id}/{depth}")
            usage = raw["response"]["usage"]
            need(usage["prompt_tokens"] == depth and usage["completion_tokens"] == 128, f"usage changed: {arm_id}/{depth}")
            need(usage["prompt_tokens_details"]["cached_tokens"] == 0, f"cache reuse appeared: {arm_id}/{depth}")
            points.append({
                "x": depth,
                "decode_tok_s": raw["metric_window"]["conventional_99_interval_tok_s"],
                "ttft_ms": raw["metric_window"]["time_to_first_token_s"] * 1000,
                "effective_prompt_throughput_proxy_tok_s": depth / raw["metric_window"]["time_to_first_token_s"],
                "cached_tokens": 0,
                "output_token_ids_sha256": raw["response"]["output_token_ids_sha256"],
                "raw_sha256": digest(raw_path),
            })
        need(points == arm["points"], f"compact points differ from raw receipts: {arm_id}")

    verification = load(root / "model-verification.json")
    need(digest(root / "model-verification.json") == result["model_verification"]["raw_sha256"], "model verification changed")
    need(verification["status"] == "verified" and len(verification["files"]) == 19, "model verification weakened")
    need(all(item["direct_mode"] == "odirect" and item["ok"] and item["paths_coherent"] for item in verification["files"]), "model read paths weakened")
    need(result["authority"]["site_cells"] == 12 and result["authority"]["zero_context_cells"] == 0, "authority widened")
    need(not result["authority"]["headline_or_protected_replacement"], "headline replacement was authorized")
    need(result["authority"]["protected_decode_values_unchanged"] == [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144], "protected values changed")
    return {"status": "pass", "arms_verified": 2, "cells_verified": 12, "x0": "missing", "headline_replacement": False}


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
