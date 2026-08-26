#!/usr/bin/env python3
"""Compose and validate the TP4/MTP1 PIECEWISE exact-4K evidence packet."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
DEFAULT_RESULT = REPO / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp4-mtp1-f16-piecewise-4k-sentinel-r1-result.json"


def load(path: Path):
    return json.loads(path.read_text())


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    ap.add_argument("--raw-root", type=Path)
    args = ap.parse_args()
    result = load(args.result)
    root = args.raw_root or Path(result["raw_root"])

    require(result["status"] == "passed-quality-clean-evidence-only", "status widened")
    cfg = result["config"]
    require((cfg["tp"], cfg["cards"], cfg["mtp"], cfg["graph_mode"], cfg["kv"]) == (4, 4, 1, "PIECEWISE", "f16"), "profile identity mismatch")
    require(cfg["graph_capture_sizes"] == [1] and cfg["max_cudagraph_capture_size"] == 1 and not cfg["enforce_eager"], "graph identity mismatch")

    raw_hashes = result["identity"]["raw_sha256"]
    for name, expected in raw_hashes.items():
        require(sha(root / name) == expected, f"raw identity hash mismatch: {name}")
    for key, name in (("raw_sha256", "exact-depth/depth-4096.json"),):
        require(sha(root / name) == result["point"][key], f"point hash mismatch: {name}")
    require(sha(root / "verification-gates.json") == result["mechanism"]["raw_sha256"], "verification hash mismatch")
    require(sha(root / "quality.json") == result["quality"]["raw_sha256"], "quality hash mismatch")
    require(sha(root / "rank-cache-isolation.json") == result["graph_topology_and_cache"]["rank_cache_raw_sha256"], "rank-cache hash mismatch")
    require(sha(root / "model-verification.json") == result["model_verification"]["raw_sha256"], "model verification hash mismatch")
    require(sha(root / "terminal-receipt.json") == result["cleanup"]["terminal_receipt_sha256"], "terminal hash mismatch")
    require(sha(root / "arm-result.json") == result["cleanup"]["arm_result_sha256"], "arm hash mismatch")

    point = load(root / "exact-depth/depth-4096.json")
    window, response, usage = point["metric_window"], point["response"], point["response"]["usage"]
    require(point["status"] == "passed" and point["gate"]["passed"], "exact gate failed")
    require(point["run_identity"]["depth"] == 4096 and usage["prompt_tokens"] == 4096, "not exact 4K")
    require(usage["prompt_tokens_details"]["cached_tokens"] == 0 and usage["completion_tokens"] == 128, "cache/completion gate failed")
    require(window["conventional_99_interval_tok_s"] == result["point"]["decode_tok_s"] == 18.823672180898463, "decode metric mismatch")
    require(window["time_to_first_token_s"] * 1000 == result["point"]["ttft_ms"] == 2349.6064160135575, "TTFT mismatch")
    require(response["output_token_ids_sha256"] == result["point"]["output_token_ids_sha256"], "output hash mismatch")

    verification = load(root / "verification-gates.json")
    acceptance = verification["acceptance"]
    require(acceptance["passed"] and (acceptance["accepted_tokens"], acceptance["drafted_tokens"]) == (56, 71), "acceptance mismatch")
    require(verification["dual_parent_verification"]["passed"], "raw dual-parent verification failed")
    expected_hash = result["point"]["output_token_ids_sha256"]
    for label, parent in result["parent_oracles"].items():
        if not isinstance(parent, dict) or "path" not in parent:
            continue
        path = Path(parent["path"])
        require(sha(path) == parent["raw_sha256"], f"{label} raw hash mismatch")
        pdata = load(path)
        require(pdata["response"]["output_token_ids_sha256"] == parent["output_token_ids_sha256"] == expected_hash, f"{label} token mismatch")
        require(pdata["response"]["token_ids"] == response["token_ids"], f"{label} all-token parity failed")
    require(result["parent_oracles"]["passed"] and result["parent_oracles"]["all_128_tokens_equal"], "parent result gate failed")

    quality = load(root / "quality.json")
    require(quality["pass_all"] and quality["baseline_match_all"], "quality failed")
    require(len(quality["exact_cases"]) == 7 and len(quality["baseline_comparisons"]) == 24, "quality counts mismatch")
    require(len(quality["repeat_case"]["runs"]) == 8, "repeat count mismatch")
    all_usage = [case["usage"] for case in quality["exact_cases"]] + [run["usage"] for run in quality["repeat_case"]["runs"]] + [quality["long_context_case"]["usage"]]
    require(len(all_usage) == 16 and all(u["prompt_tokens_details"]["cached_tokens"] == 0 for u in all_usage), "quality cache-zero failed")

    inspect = load(root / "container-inspect.json")[0]
    cmd = inspect["Config"]["Cmd"]
    env = inspect["Config"]["Env"]
    require("--tensor-parallel-size" in cmd and cmd[cmd.index("--tensor-parallel-size") + 1] == "4", "TP4 command missing")
    require("--enforce-eager" not in cmd and "--kv-cache-dtype" not in cmd, "eager or explicit KV override found")
    require("ZE_AFFINITY_MASK=0,1,2,3" in env and "VLLM_XPU_ENABLE_XPU_GRAPH=1" in env, "affinity/graph env mismatch")
    startup = (root / "server-startup.log").read_text(errors="replace")
    require("world_size=4, local_world_size=4" in startup, "local world size missing")
    for rank in range(4):
        require(f"world_size=4 rank={rank} local_rank={rank}" in startup, f"worker rank {rank} missing")
    require("TP rank 0" in startup, "rank-zero TP assignment missing")
    require("Capturing CUDA graphs (mixed prefill-decode, PIECEWISE)" in startup and "Graph capturing finished" in startup, "PIECEWISE capture missing")

    cache = load(root / "rank-cache-isolation.json")
    namespaces = [f"rank_{i}_0" for i in range(4)]
    require(cache["passed"] and cache["expected_rank_namespaces"] == namespaces and cache["observed_rank_namespaces"] == namespaces, "rank cache isolation failed")
    model = load(root / "model-verification.json")
    require(model["status"] == "verified" and len(model["files"]) == 19, "model verification failed")
    require(all(item["ok"] and item["paths_coherent"] for item in model["files"]), "model path verification failed")
    terminal, arm = load(root / "terminal-receipt.json"), load(root / "arm-result.json")
    require(terminal["terminal"] and terminal["state"] == "passed-quality-clean-sentinel" and terminal["launch_git_head"] == result["cleanup"]["launch_git_head"], "terminal/launch identity failed")
    require(arm["cleanup_passed"] and arm["tp4_worker_topology_passed"] and arm["rank_cache_isolation_passed"], "arm gates failed")

    authority = result["authority"]
    require(not authority["site_or_family_publication_authorized"] and authority["site_cells"] == 0, "publication authority widened")
    require(authority["selected_evidence_depths"] == [4096] and authority["missing_depths"] == [0, 2048, 8192, 16384, 24576, 32768], "depth authority widened")
    require(not authority["automatic_publication"] and not authority["automatic_descendant_expansion"] and not authority["historical_or_protected_replacement"], "automatic/replacement authority widened")
    caveat = result["historical_graph_corruption_caveat"]
    require(caveat["retained"] and caveat["excluded_depth"] == 8192 and caveat["first_divergence"] == {"one_based": 99, "graph": 411, "eager_target": 579}, "8K caveat missing")

    for item in result["tracked_inputs"].values():
        require(sha(REPO / item["path"]) == item["sha256"], f"tracked input mismatch: {item['path']}")
    print("PASS: TP4/MTP1 PIECEWISE exact-4K evidence packet is raw-bound and zero-publication")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
