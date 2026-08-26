#!/usr/bin/env python3
"""Read-only validator for the current-f01e TP2/MTP3 depth result."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import socket

REPO = Path(__file__).resolve().parents[3]
ROOT = Path("/mnt/fast-ai/bench-results/qwen38-official-f01e-autoround-tp2-mtp3-f16-eager-depth-expansion-20260826-r1")
TARGET_ROOT = Path("/mnt/fast-ai/bench-results/qwen38-official-f01e-autoround-tp2-mtp0-f16-eager-depth-expansion-20260826-r1")
RESULT = REPO / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp2-mtp3-f16-eager-depth-expansion-r1-result.json"
PARENT_RESULT = REPO / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp2-mtp2-f16-eager-depth-expansion-r1-result.json"
DEPTHS = [4096, 8192, 16384, 24576, 32768]
PROTECTED = [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144]


def load(path: Path):
    return json.loads(path.read_text())


def digest(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def need(value, message):
    if not value:
        raise RuntimeError(message)


def port_closed(port: int) -> bool:
    with socket.socket() as sock:
        sock.settimeout(0.2)
        return sock.connect_ex(("127.0.0.1", port)) != 0


def validate():
    result = load(RESULT)
    need(result["status"] == "passed-quality-clean-depth-expansion-grade-c", "result status changed")
    need(result["published_decode_field"] == "conventional_99_interval_tok_s", "site metric changed")
    for binding in result["tracked_inputs"].values():
        path = REPO / binding["path"]
        need(path.is_file() and digest(path) == binding["sha256"], f"tracked input changed: {path}")

    terminal = load(ROOT / "terminal-receipt.json")
    arm = load(ROOT / "arm-result.json")
    quality = load(ROOT / "quality.json")
    for name, key in (
        ("terminal-receipt.json", "terminal_receipt_sha256"),
        ("arm-result.json", "arm_result_sha256"),
        ("quality.json", "quality_sha256"),
        ("model-verification.json", "model_verification_sha256"),
        ("rank-cache-isolation.txt", "rank_cache_isolation_sha256"),
    ):
        need(digest(ROOT / name) == result["cleanup"][key], f"{name} changed")
    need((ROOT / "rank-cache-isolation.txt").read_text() == "graph-off: no compile artifacts\n", "rank cache receipt changed")
    need(terminal["terminal"] and terminal["runner_return_code"] == 0, "terminal receipt changed")
    need(terminal["state"] == "passed-quality-clean-depth-expansion", "terminal state changed")
    need(arm["state"] == "passed-quality-clean-depth-expansion" and arm["runner_return_code"] == 0, "arm state changed")
    need(arm["passed_depth_count"] == 5 and arm["passed_acceptance_count"] == 5, "depth/acceptance authority changed")
    need(arm["passed_same_topology_target_count"] == 5 and arm["frozen_same_topology_oracle_depths"] == DEPTHS, "target parity authority changed")
    need(arm["failed_or_quarantined_depths"] == [], "raw arm acquired an unexpected quarantine")
    need(arm["objective_quality_passed"] and arm["same_topology_baseline_passed"] and arm["cleanup_passed"], "quality/cleanup changed")
    need(arm["tp2_worker_topology_passed"] and arm["rank_cache_isolation_passed"], "topology/cache changed")
    need(arm["complete_descendant_expansion_authorized"] and not arm["descendant_execution_authorized"], "descendant authority changed")

    server_args = (ROOT / "server-args.shell.txt").read_text()
    need("--tensor-parallel-size 2" in server_args and "--enforce-eager" in server_args, "TP2 eager args changed")
    need(r'--speculative-config \{\"method\":\"qwen3_next_mtp\"\,\"num_speculative_tokens\":3\}' in server_args, "MTP3 args changed")
    need("--kv-cache-dtype" not in server_args, "F16/auto KV args changed")
    startup = (ROOT / "server-startup.log").read_text()
    for marker in (
        "SpeculativeConfig(method='mtp'",
        "num_spec_tokens=3",
        "tensor_parallel_size=2",
        "quantization=inc",
        "enforce_eager=True",
        "kv_cache_dtype=auto",
        "cudagraph_mode': <CUDAGraphMode.NONE: 0>",
        "world_size=2, local_world_size=2",
    ):
        need(marker in startup, f"startup identity missing: {marker}")

    need(quality["pass_all"] and quality["baseline_match_all"], "quality failed")
    usages = [case["usage"] for case in quality["exact_cases"]] + [run["usage"] for run in quality["repeat_case"]["runs"]] + [quality["long_context_case"]["usage"]]
    need(len(quality["exact_cases"]) == 7 and quality["repeat_case"]["repeats"] == 8 and len(usages) == 16, "quality cardinality changed")
    need(len(quality["repeat_case"]["unique_hashes"]) == 1 and quality["long_context_case"]["pass"], "quality objective weakened")
    need(len(quality["baseline_comparisons"]) == 24, "baseline comparison count changed")
    need(all(usage.get("prompt_tokens_details", {}).get("cached_tokens") == 0 for usage in usages), "quality cache reuse appeared")
    verification = load(ROOT / "model-verification.json")
    need(verification["status"] == "verified" and len(verification["files"]) == 19, "model verification weakened")
    need(all(item["ok"] and item["paths_coherent"] and item["direct_mode"] == "odirect" for item in verification["files"]), "model verification path weakened")

    receipts = {item["depth"]: item for item in arm["depth_receipts"]}
    valid = []
    for depth in DEPTHS:
        path = ROOT / "exact-depth" / f"depth-{depth}.json"
        raw = load(path)
        verify = load(ROOT / "verification" / f"depth-{depth}.json")
        need(raw == load(ROOT / "exact-depth" / f"depth-{depth}.stdout.json"), f"stdout differs: {depth}")
        need(raw["gate"]["passed"] and all(raw["gate"]["checks"].values()), f"exact depth failed: {depth}")
        usage = raw["response"]["usage"]
        need(usage["prompt_tokens"] == depth and usage["completion_tokens"] == 128 and usage["prompt_tokens_details"].get("cached_tokens") == 0, f"usage changed: {depth}")
        acceptance = verify["acceptance"]
        need(acceptance["passed"] and acceptance["drafted_tokens"] > 0 and 0 < acceptance["accepted_tokens"] <= acceptance["drafted_tokens"], f"acceptance failed: {depth}")
        target = verify["same_topology_target_verification"]
        target_raw = load(TARGET_ROOT / "exact-depth" / f"depth-{depth}.json")
        need(target["passed"] and target["first_divergence"] is None, f"target parity failed: {depth}")
        need(raw["response"]["token_ids"] == target_raw["response"]["token_ids"], f"direct target IDs differ: {depth}")
        need(receipts[depth]["per_depth_valid"] and receipts[depth]["target_parity_passed"], f"arm valid receipt failed: {depth}")
        valid.append((depth, raw["metric_window"]["conventional_99_interval_tok_s"], raw["response"]["output_token_ids_sha256"], digest(path), int(acceptance["drafted_tokens"]), int(acceptance["accepted_tokens"]), acceptance["acceptance_rate"]))

    expected_valid = [(p["x"], p["decode_tok_s"], p["output_token_ids_sha256"], p["raw_sha256"], p["drafted_tokens"], p["accepted_tokens"], p["draft_acceptance_rate"]) for p in result["valid_points"]]
    need(valid == expected_valid, "valid points differ from raw")
    need(not (ROOT / "exact-depth/depth-2048.json").exists() and not (ROOT / "verification/depth-2048.json").exists(), "excluded 2K unexpectedly has a raw observation")
    excluded = result["structurally_excluded_points"]
    need(len(excluded) == 1 and excluded[0]["x"] == 2048 and not excluded[0]["speed_observed"] and excluded[0]["site_action"] == "quarantine-no-speed", "2K exclusion disclosure weakened")
    parent = load(PARENT_RESULT)
    parent_2k = parent["quarantined_points"][0]
    need(parent_2k["x"] == 2048 and parent_2k["first_divergence_one_based"] == 90 and parent_2k["site_action"] == "quarantine-no-speed", "parent 2K quarantine changed")

    authority = result["authority"]
    need(authority["qualified_raw_cells"] == 5 and authority["new_site_measured_cells"] == 5 and authority["new_site_quarantined_cells"] == 0, "site authority widened")
    need(authority["retained_parent_quarantined_cells"] == 1 and authority["zero_context_cells"] == 0, "site scope changed")
    need(not authority["headline_or_protected_replacement"] and not authority["target_only_profile_replacement"] and not authority["mtp1_profile_replacement"] and not authority["mtp2_profile_replacement"] and not authority["older_tp2_graph_series_replacement"], "replacement enabled")
    need(authority["protected_decode_values_unchanged"] == PROTECTED, "protected values changed")
    need(result["adjudication"]["valid_depths"] == DEPTHS and result["adjudication"]["structurally_excluded_depths"] == [2048], "publication scope changed")
    need(result["adjudication"]["excluded_depths_were_not_run"] and not result["adjudication"]["automatic_publication_authority"], "publication authority widened")
    need(port_closed(19495), "campaign port is open")
    return {"status": "pass", "raw_exact": "5/5", "acceptance": "5/5", "target_parity": "5/5", "new_site_measured": 5, "structurally_excluded": [2048], "quality_cache_zero": "16/16", "x0": "missing"}


if __name__ == "__main__":
    print(json.dumps(validate(), indent=2, sort_keys=True))
