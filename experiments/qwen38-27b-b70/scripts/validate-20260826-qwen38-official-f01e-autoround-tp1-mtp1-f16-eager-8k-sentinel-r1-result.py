#!/usr/bin/env python3
"""Validate the quarantined eager/F16 native-MTP1 sentinel."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ROOT = Path("/mnt/fast-ai/bench-results/qwen38-official-f01e-autoround-tp1-mtp1-f16-eager-8k-sentinel-20260826-r1")
RESULT = REPO / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp1-mtp1-f16-eager-8k-sentinel-r1-result.json"


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
    need(result["status"] == "quarantined-target-verification-failed", "classification changed")
    for binding in result["tracked_inputs"].values():
        path = REPO / binding["path"]
        need(path.is_file() and digest(path) == binding["sha256"], f"tracked input changed: {path}")
    identity = result["identity"]
    for name, expected in identity["raw_sha256"].items():
        need(digest(root / name) == expected, f"raw identity changed: {name}")
    inspect = load(root / "container-inspect.json")[0]
    args, env = inspect["Config"]["Cmd"], inspect["Config"]["Env"]
    need(inspect["Image"] == identity["image"].split("@", 1)[1], "image changed")
    need("--enforce-eager" in args and "--kv-cache-dtype" not in args, "eager/F16 identity changed")
    need("--compilation-config" not in args and "VLLM_XPU_ENABLE_XPU_GRAPH=1" not in env, "graph identity appeared")
    spec = json.loads(args[args.index("--speculative-config") + 1])
    need(spec == {"method": "qwen3_next_mtp", "num_speculative_tokens": 1}, "MTP1 identity changed")
    terminal, arm = load(root / "terminal-receipt.json"), load(root / "arm-result.json")
    cleanup = result["cleanup"]
    need(digest(root / "terminal-receipt.json") == cleanup["terminal_receipt_sha256"], "terminal changed")
    need(digest(root / "arm-result.json") == cleanup["arm_result_sha256"], "arm changed")
    need(terminal["terminal"] and terminal["state"] == result["status"] and terminal["runner_return_code"] == 39, "terminal quarantine changed")
    need(terminal["launch_git_head"] == cleanup["launch_git_head"], "launch head changed")
    need(terminal["protected_profiles_untouched"] and not terminal["historical_replacement_allowed"] and not terminal["automatic_descendant_expansion"], "authority widened")
    need(arm["exact_8k_return_code"] == 0 and arm["quality_return_code"] == 0 and arm["acceptance_passed"] and not arm["target_verification_passed"], "gate split changed")
    need(arm["cleanup_passed"] and arm["startup_identity_passed"] and not arm["descendant_expansion_authorized"] and not arm["descendant_execution_authorized"], "cleanup/authority changed")
    gates = load(root / "verification-gates.json")
    mechanism, oracle = result["mechanism"], result["target_oracle"]
    need(digest(root / "verification-gates.json") == mechanism["raw_sha256"], "verification gates changed")
    acceptance, target = gates["acceptance"], gates["target_verification"]
    need(acceptance["passed"] and acceptance["drafted_tokens"] == mechanism["drafted_tokens"] and acceptance["accepted_tokens"] == mechanism["accepted_tokens"] and acceptance["acceptance_rate"] == mechanism["acceptance_rate"], "acceptance changed")
    need(not target["passed"] and target["first_divergence"] == oracle["first_divergence"], "divergence changed")
    need(target["candidate_ids_sha256"] == oracle["candidate_token_ids_sha256"] and target["target_ids_sha256"] == oracle["target_token_ids_sha256"], "oracle hashes changed")
    mtp2 = load(REPO / oracle["mtp2_result"])
    need(oracle["same_alternate_as_current_mtp2_8k"] and mtp2["diagnostic_point"]["output_token_ids_sha256"] == oracle["candidate_token_ids_sha256"], "MTP2 alternate relationship changed")
    raw_path = root / "exact-depth/depth-8192.json"
    raw = load(raw_path)
    need(raw == load(root / "exact-depth/depth-8192.stdout.json"), "stdout mirror changed")
    need(raw["gate"]["passed"] and all(raw["gate"]["checks"].values()), "exact-depth gate failed")
    point = result["diagnostic_point"]
    need(digest(raw_path) == point["raw_sha256"], "raw point changed")
    need(raw["metric_window"]["conventional_99_interval_tok_s"] == point["conventional_99_interval_tok_s"], "conventional speed changed")
    need(raw["metric_window"]["historical_100_event_tok_s"] == point["historical_100_event_tok_s"], "historical speed changed")
    need(raw["metric_window"]["time_to_first_token_s"] == point["ttft_s"], "TTFT changed")
    need(raw["response"]["usage"]["prompt_tokens_details"]["cached_tokens"] == 0 and not point["publishable_as_strong_or_site_coverage"], "cache or publication authority changed")
    quality = load(root / "quality.json")
    expected = result["quality"]
    need(digest(root / "quality.json") == expected["raw_sha256"], "quality changed")
    need(quality["pass_all"] and quality["baseline_match_all"] and len(quality["exact_cases"]) == 7 and quality["repeat_case"]["pass"] and len(quality["repeat_case"]["unique_hashes"]) == 1 and quality["long_context_case"]["pass"] and len(quality["baseline_comparisons"]) == 24, "quality weakened")
    verification = load(root / "model-verification.json")
    need(digest(root / "model-verification.json") == result["model_verification"]["raw_sha256"], "model verification changed")
    need(verification["status"] == "verified" and len(verification["files"]) == 19, "model verification weakened")
    authority = result["authority"]
    need(authority["site_cells"] == 0 and not authority["site_or_family_publication_authorized"] and not authority["strong_measured_coverage_authorized"] and not authority["descendant_expansion_authorized"], "publication authority appeared")
    need(not authority["historical_or_protected_replacement"] and not authority["headline_graph_or_frontier_replacement"], "replacement authority appeared")
    return {"status": "pass", "classification": result["status"], "site_cells": 0, "mtp": 1, "quality": True, "target_parity": False, "first_divergence_one_based": 99}


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
