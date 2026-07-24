#!/usr/bin/env python3
"""Fail-closed exactness analyzer for two fresh Laguna graph endpoints."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


EXPECTED_VLLM = "0ce373a3115fb4498c5e7a041d4fc9212fd6b5ca"
EXPECTED_KERNELS = "4772f727590c51b72add79350b913d098cf67872"
EXPECTED_PROMPT_IDS = [
    "python-lru-cache",
    "python-debug-window",
    "sql-sessionization",
    "concurrency-review",
    "arithmetic-reasoning",
    "factual-protocol",
    "typescript-cancellation",
    "rust-stream-parser",
    "repository-refactor-plan",
    "shell-safety-review",
    "structured-extraction",
    "prose-decision-memo",
    "long-rollover-repository-audit",
]


def load(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def analyze_leg(root: Path, name: str) -> dict[str, Any]:
    leg = root / name
    bench = load(leg / "bench.json")
    exactness = load(leg / "exactness-vs-q1.json")
    identity = load(leg / "identity.json")
    comparison = exactness["candidates"][0]["comparison"]
    rows = bench.get("rows") or []
    server_log = (leg / "server.log").read_text(encoding="utf-8", errors="replace")
    capture_lines = [
        line
        for line in server_log.splitlines()
        if "Captured audited breakable cudagraph" in line
    ]
    replay_lines = [
        line
        for line in server_log.splitlines()
        if "Replayed audited breakable cudagraph" in line
    ]
    topology_lines = capture_lines + replay_lines
    rank_pattern = re.compile(r"Worker_TP([0-3])_EP([0-3])")
    capture_ranks = {
        tuple(int(value) for value in match.groups())
        for line in capture_lines
        if (match := rank_pattern.search(line)) is not None
    }
    replay_ranks = {
        tuple(int(value) for value in match.groups())
        for line in replay_lines
        if (match := rank_pattern.search(line)) is not None
    }
    environment = dict(
        line.split("=", 1)
        for line in (leg / "service-environment.txt")
        .read_text(encoding="utf-8")
        .splitlines()
        if "=" in line
    )
    checks = {
        "vllm_commit": identity.get("vllm_commit") == EXPECTED_VLLM,
        "kernel_commit": identity.get("kernel_commit") == EXPECTED_KERNELS,
        "graph_contract": identity.get("execution")
        == {
            "VLLM_USE_AOT_COMPILE": "0",
            "VLLM_USE_BREAKABLE_CUDAGRAPH": "1",
            "VLLM_XPU_ENABLE_XPU_GRAPH": "1",
            "VLLM_XPU_LAGUNA_DETERMINISTIC_GRAPH": "0",
            "VLLM_XPU_LAGUNA_M8_BREAKABLE_GRAPH": "1",
            "XPU_GRAPH": "1",
            "compilation": {
                "cudagraph_capture_sizes": [8],
                "cudagraph_mode": "PIECEWISE",
                "max_cudagraph_capture_size": 8,
                "mode": "NONE",
            },
        },
        "nonbenchmark": identity.get("claim") == "endpoint correctness only",
        "selector_identity": identity.get("selectors")
        == {
            "batched_exact_moe": 1,
            "exact_spec_attention": 1,
            "fused_w1_route_w2": 1,
            "qknorm_rope": 1,
            "route_interleave": 1,
            "shared_elementwise": 1,
            "w1_n_tile": 64,
        },
        "request_identity": identity.get("request")
        == {
            "async_scheduling": False,
            "concurrency": 1,
            "enable_thinking": False,
            "kv_cache_dtype": "bfloat16",
            "max_tokens": 512,
            "prefix_caching": False,
            "return_token_ids": True,
            "seed": 1,
        },
        "actual_graph_environment": all(
            environment.get(name) == value
            for name, value in {
                "VLLM_USE_AOT_COMPILE": "0",
                "VLLM_USE_BREAKABLE_CUDAGRAPH": "1",
                "VLLM_XPU_ENABLE_XPU_GRAPH": "1",
                "VLLM_XPU_LAGUNA_DETERMINISTIC_GRAPH": "0",
                "VLLM_XPU_LAGUNA_M8_BREAKABLE_GRAPH": "1",
                "VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE": "1",
                "VLLM_XPU_LAGUNA_M8_QKNORM_ROPE": "1",
                "VLLM_XPU_LAGUNA_M8_W1_N_TILE": "64",
                "XPU_GRAPH": "1",
            }.items()
        ),
        "diagnostic_environment_absent": not any(
            name in environment
            for name in {
                "VLLM_XPU_LAGUNA_M8_EVIDENCE",
                "VLLM_XPU_LAGUNA_M8_EVIDENCE_ARM",
                "VLLM_XPU_LAGUNA_M8_EVIDENCE_ROOT",
            }
        ),
        "fresh_suite": (
            bench.get("fresh_response_validity", {}).get("valid") is True
            and bench.get("fresh_response_validity", {}).get("each_prompt_run_once")
            is True
            and bench.get("fresh_response_validity", {}).get("cached_tokens_all_zero")
            is True
        ),
        "bench_identity": bench.get("run_identity", {})
        == {
            **bench.get("run_identity", {}),
            "api_mode": "chat",
            "base_url": "http://127.0.0.1:18080",
            "max_tokens": 512,
            "model": "laguna-s-2.1-int4",
            "prompt_count": 13,
            "request_extra": {"chat_template_kwargs": {"enable_thinking": False}},
            "return_token_ids": True,
            "seed": 1,
            "suite_path": ("experiments/laguna-s-2.1-xpu-b70/realistic-suite-v1.json"),
        }
        and bench.get("run_identity", {}).get("suite", {}).get("suite_id")
        == "laguna-s-2.1-realistic-cold-v1"
        and bench.get("run_identity", {}).get("suite", {}).get("version") == 1,
        "prompt_order": [row.get("prompt_id") for row in rows] == EXPECTED_PROMPT_IDS,
        "thirteen_rows": len(rows) == 13,
        "all_cached_zero": all(row.get("cached_tokens") == 0 for row in rows),
        "teacher_exact": (
            exactness.get("all_exact") is True
            and comparison.get("exact") is True
            and comparison.get("exact_count") == 13
            and comparison.get("total") == 13
        ),
        "long_then_next": comparison.get("long_then_next", {}).get("passed") is True,
        "rollover": (
            comparison.get("rollover", {}).get("count") == 1
            and comparison.get("rollover", {}).get("exact_count") == 1
        ),
        "four_capture_topologies": len(capture_lines) == 4,
        "four_replay_topologies": len(replay_lines) == 4,
        "distinct_capture_ranks": capture_ranks == {(0, 0), (1, 1), (2, 2), (3, 3)},
        "distinct_replay_ranks": replay_ranks == {(0, 0), (1, 1), (2, 2), (3, 3)},
        "topology_146_145": all(
            "BatchDescriptor(num_tokens=8, num_reqs=None, uniform=False, "
            "has_lora=False, num_active_loras=0): "
            "BreakableCUDAGraphCapture(graphs=146, eager_breaks=145)" in line
            for line in topology_lines
        )
        and len(topology_lines) == 8,
        "clean_shutdown": (leg / "cleanup-status.txt").read_text(encoding="utf-8")
        == "stop_status=0\nworker_status=0\nidle_status=0\n",
    }
    require(all(checks.values()), f"{name}: failed checks {checks}")
    return {
        "checks": checks,
        "cached_tokens": [row["cached_tokens"] for row in rows],
        "output_sha256s": bench.get("output_sha256s"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    first = analyze_leg(args.run_dir, "start-a")
    second = analyze_leg(args.run_dir, "start-b")
    cross = load(args.run_dir / "cross-start.json")
    comparison = cross["candidates"][0]["comparison"]
    cross_checks = {
        "all_exact": cross.get("all_exact") is True,
        "exact_13": (
            comparison.get("exact") is True
            and comparison.get("exact_count") == 13
            and comparison.get("total") == 13
        ),
        "cache_zero": comparison.get("all_cached_zero") is True,
        "long_then_next": comparison.get("long_then_next", {}).get("passed") is True,
        "rollover": (
            comparison.get("rollover", {}).get("count") == 1
            and comparison.get("rollover", {}).get("exact_count") == 1
        ),
        "output_hash_lists_equal": first["output_sha256s"] == second["output_sha256s"],
    }
    require(all(cross_checks.values()), f"cross-start failed checks {cross_checks}")
    result = {
        "schema": "laguna-m8-graph-endpoint-qualification-v1",
        "status": "PASS",
        "claim": "endpoint correctness only; no timing or record claim",
        "start_a": first,
        "start_b": second,
        "cross_start": cross_checks,
    }
    args.out.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"schema": result["schema"], "status": "PASS"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
