#!/usr/bin/env python3
"""Validate the mixed Grade D current-image eager MTP1 depth result."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ROOT = Path("/mnt/fast-ai/bench-results/qwen38-official-f01e-autoround-tp1-mtp1-f16-eager-depth-expansion-20260826-r1")
RESULT = REPO / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp1-mtp1-f16-eager-depth-expansion-r1-result.json"
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
    need(result["publication_state"] == "mixed-partial-grade-d-human-adjudicated", "adjudication changed")
    need(result["metric_definition"]["published_decode_field"] == "conventional_99_interval_tok_s", "metric mislabeled")
    for binding in result["tracked_inputs"].values():
        path = REPO / binding["path"]
        need(path.is_file() and digest(path) == binding["sha256"], f"tracked input changed: {path}")
    for name, expected in result["identity"]["raw_sha256"].items():
        need(digest(root / name) == expected, f"identity changed: {name}")
    terminal, arm = load(root / "terminal-receipt.json"), load(root / "arm-result.json")
    need(digest(root / "terminal-receipt.json") == result["cleanup"]["terminal_receipt_sha256"], "terminal changed")
    need(digest(root / "arm-result.json") == result["cleanup"]["arm_result_sha256"], "arm changed")
    need(terminal["terminal"] and terminal["state"] == "quarantined-target-verification-failed" and terminal["runner_return_code"] == 39, "fail-closed terminal changed")
    need(terminal["protected_profiles_untouched"] and not terminal["historical_replacement_allowed"] and not terminal["automatic_descendant_expansion"], "terminal authority widened")
    need(arm["passed_depth_count"] == arm["passed_acceptance_count"] == 6 and arm["passed_target_verification_count"] == 4, "arm counts changed")
    need(not arm["publication_authorized"] and not arm["diagnostic_coverage_authorized"], "automatic publication appeared")
    need(arm["quality_return_code"] == 0 and arm["cleanup_passed"] and arm["startup_identity_passed"], "whole-arm receipt changed")
    points = []
    for depth in DEPTHS:
        raw_path = root / "exact-depth" / f"depth-{depth}.json"
        verify_path = root / "verification" / f"depth-{depth}.json"
        raw, verification = load(raw_path), load(verify_path)
        need(raw == load(root / "exact-depth" / f"depth-{depth}.stdout.json"), f"stdout mirror changed: {depth}")
        need(raw["gate"]["passed"] and all(raw["gate"]["checks"].values()), f"exact gate failed: {depth}")
        need(verification["acceptance"]["passed"], f"acceptance failed: {depth}")
        usage, target = raw["response"]["usage"], verification["target_verification"]
        points.append({"x": depth, "decode_tok_s": raw["metric_window"]["conventional_99_interval_tok_s"], "historical_100_event_tok_s": raw["metric_window"]["historical_100_event_tok_s"], "ttft_ms": raw["metric_window"]["time_to_first_token_s"] * 1000, "cached_tokens": usage["prompt_tokens_details"]["cached_tokens"], "completion_tokens": usage["completion_tokens"], "acceptance_rate": verification["acceptance"]["acceptance_rate"], "accepted_tokens": verification["acceptance"]["accepted_tokens"], "drafted_tokens": verification["acceptance"]["drafted_tokens"], "output_token_ids_sha256": raw["response"]["output_token_ids_sha256"], "target_output_token_ids_sha256": target["target_ids_sha256"], "target_parity": target["passed"], "first_divergence": target["first_divergence"], "publication_state": "lab-measured" if target["passed"] else "quarantined", "evidence_grade": "D", "raw_sha256": digest(raw_path), "verification_sha256": digest(verify_path)})
    need(points == result["points"], "compact points differ from raw receipts")
    need([p["x"] for p in points if p["target_parity"]] == [4096, 16384, 24576, 32768], "parity set changed")
    need([p["first_divergence"]["one_based"] for p in points if not p["target_parity"]] == [90, 99], "divergence set changed")
    quality = load(root / "quality.json")
    need(digest(root / "quality.json") == result["quality"]["raw_sha256"], "quality changed")
    need(quality["pass_all"] and quality["baseline_match_all"] and len(quality["exact_cases"]) == 7 and quality["repeat_case"]["pass"] and quality["long_context_case"]["pass"] and len(quality["baseline_comparisons"]) == 24, "quality weakened")
    verification = load(root / "model-verification.json")
    need(digest(root / "model-verification.json") == result["model_verification"]["raw_sha256"], "model verification changed")
    need(verification["status"] == "verified" and len(verification["files"]) == 19 and all(item["ok"] and item["paths_coherent"] for item in verification["files"]), "model verification weakened")
    adjudication = result["adjudication"]
    need(adjudication["whole_arm_fail_closed_receipt_preserved"] and not adjudication["automatic_publication_authority"], "adjudication overclaims")
    need(adjudication["measured_depths"] == [4096, 16384, 24576, 32768] and adjudication["quarantined_depths"] == [2048, 8192] and adjudication["missing_depths"] == [0], "site scope changed")
    authority = result["authority"]
    need(authority["site_measured_cells"] == 4 and authority["site_quarantined_cells"] == 2 and not authority["headline_or_protected_replacement"], "authority widened")
    need(authority["protected_decode_values_unchanged"] == [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144], "protected values changed")
    return {"status": "pass", "measured_cells": 4, "quarantined_cells": 2, "x0": "missing", "grade": "D", "metric": "conventional-99-interval"}


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
