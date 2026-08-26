#!/usr/bin/env python3
"""Read-only validator for the TP4/MTP4 depth diagnostic quarantine."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
ROOT = Path("/mnt/fast-ai/bench-results/qwen38-official-f01e-autoround-tp4-mtp4-f16-eager-depth-expansion-20260826-r1")
RESULT = REPO / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp4-mtp4-f16-eager-depth-expansion-r1-result.json"
DEPTHS = [2048, 4096, 8192, 16384, 24576, 32768]
PROTECTED = [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144]


def load(path: Path):
    return json.loads(path.read_text())


def digest(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def need(value, message):
    if not value:
        raise RuntimeError(message)


def validate(root: Path, result_path: Path):
    result = load(result_path)
    need(result["status"] == "quarantined-quality-failed-after-32k-engine-fatal", "result state changed")
    for binding in result["tracked_inputs"].values():
        path = REPO / binding["path"]
        need(path.is_file() and digest(path) == binding["sha256"], f"tracked input changed: {path}")
    for name, expected in result["identity"]["raw_sha256"].items():
        need(digest(root / name) == expected, f"identity changed: {name}")

    inspect = load(root / "container-inspect.json")[0]
    args, env = inspect["Config"]["Cmd"], inspect["Config"]["Env"]
    arg = lambda name: args[args.index(name) + 1]
    need(arg("--tensor-parallel-size") == "4" and arg("--gpu-memory-utilization") == "0.60", "TP4 changed")
    need("--enforce-eager" in args and "--kv-cache-dtype" not in args and "--compilation-config" not in args, "eager/F16 changed")
    need(json.loads(arg("--speculative-config")) == {"method": "qwen3_next_mtp", "num_speculative_tokens": 4}, "MTP4 changed")
    need("ZE_AFFINITY_MASK=0,1,2,3" in env and not any(item.startswith("ONEAPI_DEVICE_SELECTOR=") for item in env), "GPU selection changed")

    terminal = load(root / "terminal-receipt.json")
    arm = load(root / "arm-result.json")
    cleanup = result["cleanup"]
    need(digest(root / "terminal-receipt.json") == cleanup["terminal_receipt_sha256"], "terminal changed")
    need(digest(root / "arm-result.json") == cleanup["arm_result_sha256"], "arm changed")
    need(digest(root / "input-sha256sums.txt") == cleanup["input_sha256sums_sha256"], "input provenance changed")
    need(terminal["terminal"] and terminal["state"] == "quarantined-quality-failed" and terminal["runner_return_code"] == 40, "terminal classification changed")
    need(terminal["protected_profiles_untouched"] and not terminal["historical_replacement_allowed"] and not terminal["automatic_descendant_expansion"], "terminal authority widened")
    need(arm["state"] == "quarantined-quality-failed" and arm["quality_return_code"] == 1, "quality failure changed")
    need(not arm["objective_quality_passed"] and not arm["same_topology_baseline_passed"], "quality unexpectedly authorized")
    need(arm["frozen_same_topology_oracle_depths"] == [] and not arm["per_depth_descendant_oracle_authority"], "depth authority appeared")
    need(arm["startup_identity_passed"] and arm["tp4_worker_topology_passed"] and arm["parent_8k_match_passed"] and arm["rank_cache_isolation_passed"] and arm["cleanup_passed"], "non-quality global gate failed")
    need(not arm["automatic_publication_allowed"] and not arm["complete_descendant_expansion_authorized"] and not arm["descendant_execution_authorized"], "raw authority widened")

    compact = {point["x"]: point for point in result["local_diagnostic_points"]}
    need(sorted(compact) == DEPTHS, "diagnostic depth set changed")
    for depth in DEPTHS:
        raw_path = root / "exact-depth" / f"depth-{depth}.json"
        verify_path = root / "verification" / f"depth-{depth}.json"
        raw, verification, point = load(raw_path), load(verify_path), compact[depth]
        need(raw == load(root / "exact-depth" / f"depth-{depth}.stdout.json"), f"stdout differs: {depth}")
        need(digest(raw_path) == point["raw_sha256"] and digest(verify_path) == point["verification_sha256"], f"raw receipt changed: {depth}")
        metric = raw["metric_window"]
        need(point["decode_tok_s_diagnostic_only"] == metric["conventional_99_interval_tok_s"], f"decode changed: {depth}")
        need(point["historical_100_event_decode_tok_s_diagnostic_only"] == metric["historical_100_event_tok_s"], f"historical decode changed: {depth}")
        need(point["ttft_ms"] == metric["time_to_first_token_s"] * 1000, f"TTFT changed: {depth}")
        acceptance = verification["acceptance"]
        need(acceptance["passed"] and all(math.isfinite(acceptance[key]) for key in ("drafted_tokens", "accepted_tokens", "acceptance_rate")), f"acceptance failed: {depth}")
        need((point["drafted_tokens"], point["accepted_tokens"], point["draft_acceptance_rate"]) == (acceptance["drafted_tokens"], acceptance["accepted_tokens"], acceptance["acceptance_rate"]), f"acceptance changed: {depth}")

    for depth in (4096, 16384, 24576):
        raw = load(root / "exact-depth" / f"depth-{depth}.json")
        verification = load(root / "verification" / f"depth-{depth}.json")
        usage = raw["response"]["usage"]
        need(raw["gate"]["passed"] and all(raw["gate"]["checks"].values()), f"local exact gate failed: {depth}")
        need(usage["prompt_tokens"] == depth and usage["completion_tokens"] == 128 and usage["prompt_tokens_details"]["cached_tokens"] == 0, f"usage changed: {depth}")
        need(verification["same_topology_target_verification"]["passed"], f"local parity failed: {depth}")
        need("diagnostic-only-global-quality-failed" in compact[depth]["local_state"], f"diagnostic classification changed: {depth}")

    two_k = load(root / "verification/depth-2048.json")
    need(not two_k["same_topology_target_verification"]["passed"] and two_k["same_topology_target_verification"]["first_divergence"]["one_based"] == 90, "2K quarantine changed")
    eight_k = load(root / "verification/depth-8192.json")
    need(eight_k["parent_8k_match"]["passed"] and not eight_k["same_topology_target_verification"]["passed"], "8K parent quarantine changed")
    need(eight_k["candidate_ids_sha256"] == "dd31856f45269d222efe0f6f5f1ac9342b6c9ae55e5ce9129fc02b27abdb7e8e", "8K parent output changed")
    need(eight_k["same_topology_target_verification"]["first_divergence"]["one_based"] == 99, "8K divergence changed")

    thirty_two = load(root / "exact-depth/depth-32768.json")
    need(thirty_two["status"] == "failed" and not thirty_two["gate"]["passed"], "32K exact failure changed")
    need(len(thirty_two["response"]["token_ids"]) == 126 and thirty_two["response"]["usage"] == {}, "32K partial response changed")
    need((root / "exact-depth/depth-32768.rc").read_text().strip() == "2", "32K return code changed")

    failure = result["fatal_and_quality_failure"]
    need(not (root / "quality.json").exists() and failure["quality_json_present"] is False, "quality output appeared")
    need(digest(root / "server.log") == failure["server_log_sha256"], "fatal log changed")
    need(digest(root / "quality.stdout.log") == failure["quality_stdout_log_sha256"], "quality traceback changed")
    server_text = (root / "server.log").read_text(errors="replace")
    quality_text = (root / "quality.stdout.log").read_text(errors="replace")
    need(failure["engine_error"] in server_text and "EngineCore encountered a fatal error" in server_text, "engine fatal signature missing")
    need("HTTP Error 500" in quality_text, "quality HTTP 500 missing")

    need(digest(root / "rank-cache-isolation.txt") == result["topology_and_cache"]["rank_cache_raw_sha256"], "rank cache changed")
    model = load(root / "model-verification.json")
    need(digest(root / "model-verification.json") == result["model_verification"]["raw_sha256"], "model verification changed")
    need(model["status"] == "verified" and len(model["files"]) == 19 and all(item["ok"] and item["paths_coherent"] for item in model["files"]), "model verification failed")

    authority = result["authority"]
    need(not authority["raw_publication_authorized"] and authority["site_structural_cells"] == 0 and authority["site_measured_speed_cells"] == 0, "site authority appeared")
    need(authority["locally_parity_passing_but_not_frozen_depths"] == [4096, 16384, 24576] and authority["exact_fatal_depths"] == [32768], "diagnostic classification changed")
    need(not authority["historical_or_protected_replacement"] and authority["protected_decode_values_unchanged"] == PROTECTED and authority["existing_site_cells_unchanged"], "protected/site authority changed")
    return {"status": "pass", "site_cells": 0, "frozen_depths": [], "diagnostic_local_parity_depths": [4096, 16384, 24576], "exact_fatal_depth": 32768, "runner_rc": 40}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--result", type=Path, default=RESULT)
    args = parser.parse_args()
    try:
        report = validate(args.root, args.result)
    except (KeyError, OSError, TypeError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        parser.error(str(error))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
