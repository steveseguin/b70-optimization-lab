#!/usr/bin/env python3
"""Read-only validator for the published TP1/MTP1 PIECEWISE exact-4K cell."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ROOT = Path("/mnt/fast-ai/bench-results/qwen38-official-f01e-autoround-tp1-mtp1-f16-piecewise-4k-sentinel-20260826-r1")
RESULT = REPO / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp1-mtp1-f16-piecewise-4k-sentinel-r1-result.json"


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


def arg_value(args, name):
    return args[args.index(name) + 1]


def validate(root: Path, result_path: Path):
    result = load(result_path)
    need(result["status"] == "passed-quality-clean-tp1-mtp1-piecewise-4k-sentinel", "result is not passed")
    for binding in result["tracked_inputs"].values():
        path = REPO / binding["path"]
        need(path.is_file() and digest(path) == binding["sha256"], f"tracked input changed: {path}")

    identity = result["identity"]
    for name, expected in identity["raw_sha256"].items():
        need(digest(root / name) == expected, f"raw identity changed: {name}")
    need((root / "image-id.txt").read_text().strip() == identity["image"].split("@", 1)[1], "image changed")
    need((root / "vllm-source-commit.txt").read_text().strip() == identity["vllm_source"], "vLLM source changed")
    need((root / "stack-versions.txt").read_text().splitlines() == [identity["vllm_version"], identity["xpu_kernels_version"]], "stack changed")

    container = load(root / "container-inspect.json")[0]
    args, env = container["Config"]["Cmd"], container["Config"]["Env"]
    need(arg_value(args, "--tensor-parallel-size") == "1", "TP1 changed")
    need("--enforce-eager" not in args and "--kv-cache-dtype" not in args, "graph/F16 identity changed")
    compilation = json.loads(arg_value(args, "--compilation-config"))
    need(compilation == {"cudagraph_mode": "PIECEWISE", "cudagraph_capture_sizes": [1], "max_cudagraph_capture_size": 1}, "PIECEWISE identity changed")
    need(json.loads(arg_value(args, "--speculative-config")) == {"method": "qwen3_next_mtp", "num_speculative_tokens": 1}, "MTP1 changed")
    need("ZE_AFFINITY_MASK=0" in env and "ONEAPI_DEVICE_SELECTOR=level_zero:0" in env, "TP1 device binding changed")
    need("VLLM_XPU_ENABLE_XPU_GRAPH=1" in env and "PYTHONHASHSEED=0" in env, "graph environment changed")
    startup = (root / "server-startup.log").read_text(errors="replace")
    for marker in ("enforce_eager=False", "world_size=1 rank=0 local_rank=0", "TP rank 0", "Capturing CUDA graphs (mixed prefill-decode, PIECEWISE)", "Graph capturing finished"):
        need(marker in startup, f"missing startup marker: {marker}")
    need("Capturing CUDA graphs (decode, FULL)" not in startup, "FULL capture appeared")

    terminal, arm = load(root / "terminal-receipt.json"), load(root / "arm-result.json")
    cleanup = result["cleanup"]
    need(digest(root / "terminal-receipt.json") == cleanup["terminal_receipt_sha256"], "terminal changed")
    need(digest(root / "arm-result.json") == cleanup["arm_result_sha256"], "arm changed")
    need(terminal["terminal"] and terminal["runner_return_code"] == 0 and terminal["state"] == "passed-quality-clean-sentinel", "terminal failed")
    need(arm["exact_4k_return_code"] == 0 and arm["quality_return_code"] == 0, "raw gate rc changed")
    need(all(arm[key] for key in ("acceptance_passed", "cleanup_passed", "dual_parent_verification_passed", "quality_contract_passed", "startup_identity_passed")), "raw gate failed")
    need(not arm["publication_authorized"] and not arm["descendant_expansion_authorized"], "raw authority changed")

    raw_path = root / "exact-depth/depth-4096.json"
    raw = load(raw_path)
    need(raw == load(root / "exact-depth/depth-4096.stdout.json"), "stdout mirror changed")
    need(raw["gate"]["passed"] and all(raw["gate"]["checks"].values()), "exact 4K gate failed")
    metric, usage = raw["metric_window"], raw["response"]["usage"]
    point = result["point"]
    need(digest(raw_path) == point["raw_sha256"], "raw point changed")
    need(metric["conventional_99_interval_tok_s"] == point["decode_tok_s"], "decode changed")
    need(metric["time_to_first_token_s"] * 1000 == point["ttft_ms"], "TTFT changed")
    need(usage["prompt_tokens"] == 4096 and usage["completion_tokens"] == 128 and usage["prompt_tokens_details"]["cached_tokens"] == 0, "usage changed")
    need(raw["response"]["output_token_ids_sha256"] == point["output_token_ids_sha256"], "output hash changed")

    gates = load(root / "verification-gates.json")
    mechanism, oracle = result["mechanism"], result["dual_parent_oracle"]
    need(digest(root / "verification-gates.json") == mechanism["raw_sha256"], "verification gates changed")
    acceptance = gates["acceptance"]
    need(acceptance["passed"] and acceptance["drafted_tokens"] == mechanism["drafted_tokens"] and acceptance["accepted_tokens"] == mechanism["accepted_tokens"], "acceptance changed")
    dual = gates["dual_parent_verification"]
    need(dual["passed"] and dual["parent_ids_equal"] and dual["candidate_vs_eager_first_divergence"] is None and dual["candidate_vs_graph_first_divergence"] is None, "dual-parent parity failed")
    eager, graph = load(Path(oracle["eager_target_path"])), load(Path(oracle["piecewise_parent_path"]))
    need(digest(Path(oracle["eager_target_path"])) == oracle["eager_target_raw_sha256"], "eager parent changed")
    need(digest(Path(oracle["piecewise_parent_path"])) == oracle["piecewise_parent_raw_sha256"], "graph parent changed")
    need(raw["response"]["token_ids"] == eager["response"]["token_ids"] == graph["response"]["token_ids"], "parent tokens changed")

    quality = load(root / "quality.json")
    expected = result["quality"]
    need(digest(root / "quality.json") == expected["raw_sha256"], "quality changed")
    need(quality["pass_all"] and quality["baseline_match_all"], "quality failed")
    need(len(quality["exact_cases"]) == 7 and all(case["pass"] for case in quality["exact_cases"]), "exact quality failed")
    repeat = quality["repeat_case"]
    need(repeat["pass"] and repeat["repeats"] == 8 and len(repeat["unique_hashes"]) == 1, "repeat quality failed")
    need(quality["long_context_case"]["pass"] and len(quality["baseline_comparisons"]) == 24 and all(quality["baseline_comparisons"].values()), "needle/baseline failed")
    usages = [case["usage"] for case in quality["exact_cases"]] + [run["usage"] for run in repeat["runs"]] + [quality["long_context_case"]["usage"]]
    need(len(usages) == 16 and all(item["prompt_tokens_details"]["cached_tokens"] == 0 for item in usages), "quality cache reuse appeared")
    verification = load(root / "model-verification.json")
    need(digest(root / "model-verification.json") == result["model_verification"]["raw_sha256"], "model verification changed")
    need(verification["status"] == "verified" and len(verification["files"]) == 19 and all(item["ok"] and item["paths_coherent"] for item in verification["files"]), "model verification failed")

    adjudication, authority = result["human_adjudication"], result["authority"]
    need(adjudication["decision"] == "publish-only-tp1-mtp1-piecewise-f16-exact-4k-as-grade-c", "adjudication widened")
    need(adjudication["selected_depths"] == [4096] and adjudication["missing_depths"] == [0, 2048, 8192, 16384, 24576, 32768], "depth scope widened")
    need(authority["site_cells"] == 1 and authority["site_or_family_publication_authorized"] and authority["quality_grade"] == "C", "one-cell authority missing")
    need(not authority["historical_or_protected_replacement"] and not authority["headline_graph_or_frontier_replacement"], "replacement authority appeared")
    need(authority["protected_decode_values_unchanged"] == [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144], "protected values changed")
    need(result["historical_graph_corruption_caveat"]["first_divergence"]["one_based"] == 99, "8K caveat lost")
    return {"status": "pass", "cells_published": 1, "exact_context": 4096, "tp": 1, "mtp": 1, "graph_mode": "PIECEWISE", "grade": "C", "accepted": 56, "drafted": 71, "dual_parent_parity": True}


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
