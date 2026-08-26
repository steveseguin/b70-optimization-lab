#!/usr/bin/env python3
"""Read-only validator for the mixed eager/F16 native-MTP4 depth expansion."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ROOT = Path("/mnt/fast-ai/bench-results/qwen38-official-f01e-autoround-tp1-mtp4-f16-eager-depth-expansion-20260826-r1")
RESULT = REPO / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp1-mtp4-f16-eager-depth-expansion-r1-result.json"


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
    need(result["status"] == "incomplete-mixed-depth-expansion", "result classification changed")
    for binding in result["tracked_inputs"].values():
        path = REPO / binding["path"]
        need(path.is_file() and digest(path) == binding["sha256"], f"tracked input changed: {path}")
    for name, expected in result["identity"]["raw_sha256"].items():
        need(digest(root / name) == expected, f"identity input changed: {name}")

    terminal = load(root / "terminal-receipt.json")
    arm = load(root / "arm-result.json")
    cleanup = result["cleanup"]
    need(digest(root / "terminal-receipt.json") == cleanup["terminal_receipt_sha256"], "terminal receipt changed")
    need(digest(root / "arm-result.json") == cleanup["arm_result_sha256"], "arm receipt changed")
    need(terminal["terminal"] and terminal["state"] == "incomplete-depth-expansion", "terminal state changed")
    need(terminal["launch_git_head"] == cleanup["launch_git_head"], "launch Git head changed")
    need(terminal["protected_profiles_untouched"] and not terminal["historical_replacement_allowed"], "protected authority widened")
    need(arm["state"] == "incomplete-depth-expansion" and arm["runner_return_code"] == 37, "arm state changed")
    need(arm["passed_acceptance_count"] == 6 and arm["passed_depth_count"] == 5, "gate counts changed")
    need(arm["passed_target_verification_count"] == 3 and arm["required_depth_count"] == 6, "parity counts changed")
    need(arm["quality_return_code"] == 1 and arm["cleanup_passed"] and arm["startup_identity_passed"], "quality, cleanup, or identity changed")
    need(not arm["publication_authorized"], "publication authority appeared")

    exact_pattern = [True, True, True, True, True, False]
    parity_pattern = [False, True, False, True, True, False]
    for point, exact_ok, parity_ok in zip(result["depths"], exact_pattern, parity_pattern):
        depth = point["x"]
        raw_path = root / f"exact-depth/depth-{depth}.json"
        verify_path = root / f"verification/depth-{depth}.json"
        raw = load(raw_path)
        verification = load(verify_path)
        need(digest(raw_path) == point["raw_sha256"], f"raw depth changed: {depth}")
        need(digest(verify_path) == point["verification_sha256"], f"verification changed: {depth}")
        need(raw["gate"]["passed"] is exact_ok and point["exact_depth_gate_passed"] is exact_ok, f"exact gate changed: {depth}")
        need(verification["acceptance"]["passed"] and point["acceptance_gate_passed"], f"acceptance failed: {depth}")
        need(verification["target_verification"]["passed"] is parity_ok and point["target_parity_passed"] is parity_ok, f"parity changed: {depth}")
        need(verification["acceptance"]["accepted_tokens"] == point["accepted_tokens"], f"accepted count changed: {depth}")
        need(verification["acceptance"]["drafted_tokens"] == point["drafted_tokens"], f"drafted count changed: {depth}")
        need(verification["acceptance"]["acceptance_rate"] == point["acceptance_rate"], f"acceptance rate changed: {depth}")
        need(raw["response"]["output_token_ids_sha256"] == point["candidate_token_ids_sha256"], f"candidate hash changed: {depth}")
        need(verification["target_verification"]["target_ids_sha256"] == point["target_token_ids_sha256"], f"target hash changed: {depth}")
        need(verification["target_verification"]["first_divergence"] == point["first_divergence"], f"divergence changed: {depth}")
        if exact_ok:
            usage = raw["response"]["usage"]
            need(usage["prompt_tokens"] == depth and usage["completion_tokens"] == 128, f"usage changed: {depth}")
            need(usage["prompt_tokens_details"]["cached_tokens"] == 0, f"cache reuse appeared: {depth}")
            need(raw["metric_window"]["conventional_99_interval_tok_s"] == point["decode_tok_s"], f"speed changed: {depth}")
            need(raw["metric_window"]["time_to_first_token_s"] == point["ttft_s"], f"TTFT changed: {depth}")
        else:
            need(depth == 32768 and raw["status"] == "failed", "unexpected failed depth")
            need(len(raw["response"]["token_ids"]) == 121 and raw["response"]["usage"] == {}, "32K partial response changed")
            need(raw["metric_window"]["conventional_99_interval_tok_s"] == point["partial_timing_observation_tok_s"], "32K partial timing changed")
            need(not point["partial_timing_is_publishable_speed"], "32K partial timing became publishable")

    failure = result["failure"]
    need(digest(root / "server.log") == failure["server_log_sha256"], "server log changed")
    need(failure["error"] in (root / "server.log").read_text(encoding="utf-8"), "engine fatal missing")
    quality = result["quality"]
    need(not (root / "quality.json").exists() and quality["status"] == "not-run-engine-dead", "quality classification changed")
    need(digest(root / "quality.stdout.log") == quality["quality_stdout_sha256"], "quality failure log changed")

    parent_binding = result["parent_8k"]
    parent_path = REPO / parent_binding["result_path"]
    need(digest(parent_path) == parent_binding["result_sha256"], "passed parent result changed")
    parent = load(parent_path)
    need(parent["status"] == parent_binding["status"] and parent["point"]["decode_tok_s"] == parent_binding["decode_tok_s"], "passed parent weakened")
    need(parent["point"]["output_token_ids_sha256"] == parent_binding["target_token_ids_sha256"], "parent target parity changed")

    authority = result["authority"]
    need(authority["site_cells"] == 0 and not authority["site_or_family_publication_authorized"], "site authority appeared")
    need(not authority["full_curve_publication_authorized"] and not authority["historical_or_protected_replacement"], "curve or protected authority appeared")
    need(not authority["parent_8k_replacement"] and not authority["headline_graph_or_frontier_replacement"], "replacement authority appeared")
    need(authority["lower_grade_diagnostic_cells_may_be_separately_classified_later"] and authority["x0_remains_missing"], "diagnostic scope changed")
    return {"status": "pass", "site_cells": 0, "acceptance_gates": "6/6", "exact_depth_gates": "5/6", "target_parity_gates": "3/6", "engine_fatal_depth": 32768}


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
