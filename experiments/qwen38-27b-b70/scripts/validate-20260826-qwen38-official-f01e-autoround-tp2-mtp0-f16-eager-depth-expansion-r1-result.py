#!/usr/bin/env python3
"""Read-only validator for the current-f01e TP2/MTP0 depth result."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import socket

REPO = Path(__file__).resolve().parents[3]
ROOT = Path("/mnt/fast-ai/bench-results/qwen38-official-f01e-autoround-tp2-mtp0-f16-eager-depth-expansion-20260826-r1")
RESULT = REPO / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp2-mtp0-f16-eager-depth-expansion-r1-result.json"
DEPTHS = [2048, 4096, 8192, 16384, 24576, 32768]
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
    need(result["status"] == "passed-quality-clean-depth-expansion", "result status changed")
    need(result["published_decode_field"] == "conventional_99_interval_tok_s", "site metric changed")
    for binding in result["tracked_inputs"].values():
        path = REPO / binding["path"]
        need(path.is_file() and digest(path) == binding["sha256"], f"tracked input changed: {path}")

    terminal = load(ROOT / "terminal-receipt.json")
    arm = load(ROOT / "arm-result.json")
    quality = load(ROOT / "quality.json")
    for name, key in (("terminal-receipt.json", "terminal_receipt_sha256"), ("arm-result.json", "arm_result_sha256"), ("quality.json", "quality_sha256"), ("model-verification.json", "model_verification_sha256"), ("rank-cache-isolation.txt", "rank_cache_isolation_sha256")):
        need(digest(ROOT / name) == result["cleanup"][key], f"{name} changed")
    need((ROOT / "rank-cache-isolation.txt").read_text() == "graph-off: no compile artifacts\n", "rank cache receipt changed")
    need(terminal["terminal"] and terminal["runner_return_code"] == 0, "campaign not terminal-passed")
    need(arm["state"] == "passed-quality-clean-depth-expansion", "arm state changed")
    need(arm["passed_depth_count"] == 6 and arm["frozen_same_topology_oracle_depths"] == DEPTHS, "depth authority changed")
    need(arm["objective_quality_passed"] and arm["cleanup_passed"], "native gates changed")
    need(arm["tp2_worker_topology_passed"] and arm["rank_cache_isolation_passed"], "topology/cache changed")
    need(arm["passed_cross_topology_comparison_count"] == 6 and arm["tp4_quality_comparison_passed"], "comparison gate changed")
    server_args = (ROOT / "server-args.shell.txt").read_text()
    need("--tensor-parallel-size 2" in server_args and "--enforce-eager" in server_args, "TP2 eager args changed")
    need("--speculative-config" not in server_args and "--kv-cache-dtype" not in server_args, "target-only F16 args changed")
    startup = (ROOT / "server-startup.log").read_text()
    for marker in ("speculative_config=None", "tensor_parallel_size=2", "quantization=inc", "enforce_eager=True", "kv_cache_dtype=auto", "cudagraph_mode': <CUDAGraphMode.NONE: 0>"):
        need(marker in startup, f"startup identity missing: {marker}")

    need(quality["pass_all"] and quality["baseline_match_all"], "quality failed")
    usages = [case["usage"] for case in quality["exact_cases"]] + [run["usage"] for run in quality["repeat_case"]["runs"]] + [quality["long_context_case"]["usage"]]
    need(len(quality["exact_cases"]) == 7 and quality["repeat_case"]["repeats"] == 8 and len(usages) == 16, "quality cardinality changed")
    need(all(usage.get("prompt_tokens_details", {}).get("cached_tokens") == 0 for usage in usages), "quality cache reuse appeared")
    verification = load(ROOT / "model-verification.json")
    need(verification["status"] == "verified" and len(verification["files"]) == 19, "model verification weakened")
    need(all(item["ok"] and item["paths_coherent"] and item["direct_mode"] == "odirect" for item in verification["files"]), "model verification path weakened")

    points = []
    for depth in DEPTHS:
        path = ROOT / "exact-depth" / f"depth-{depth}.json"
        raw = load(path)
        need(raw == load(ROOT / "exact-depth" / f"depth-{depth}.stdout.json"), f"stdout differs: {depth}")
        need(raw["gate"]["passed"] and all(raw["gate"]["checks"].values()), f"depth failed: {depth}")
        usage = raw["response"]["usage"]
        need(usage["prompt_tokens"] == depth and usage["completion_tokens"] == 128 and usage["prompt_tokens_details"].get("cached_tokens") == 0, f"usage changed: {depth}")
        points.append((depth, raw["metric_window"]["conventional_99_interval_tok_s"], raw["response"]["output_token_ids_sha256"], digest(path)))
    expected = [(p["x"], p["decode_tok_s"], p["output_token_ids_sha256"], p["raw_sha256"]) for p in result["points"]]
    need(points == expected, "compact points differ from raw")

    comparisons = {item["depth"]: item["verification"]["cross_topology_comparison"] for item in arm["depth_receipts"]}
    need(all(comparisons[d]["passed"] and comparisons[d]["first_divergence"] is None for d in DEPTHS), "cross-topology parity changed")
    authority = result["authority"]
    need(authority["new_site_cells"] == 6 and authority["retained_existing_site_cells"] == 0 and authority["zero_context_cells"] == 0, "site authority widened")
    need(not authority["headline_or_protected_replacement"] and not authority["older_tp2_series_replacement"], "replacement enabled")
    need(authority["protected_decode_values_unchanged"] == PROTECTED, "protected values changed")
    need(port_closed(19492), "campaign port is open")
    return {"status": "pass", "raw_cells": 6, "new_site_cells": 6, "cross_topology_parity": "6/6", "quality_cache_zero": "16/16", "x0": "missing"}


if __name__ == "__main__":
    print(json.dumps(validate(), indent=2, sort_keys=True))
