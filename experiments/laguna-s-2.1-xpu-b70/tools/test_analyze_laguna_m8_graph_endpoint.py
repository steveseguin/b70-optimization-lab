from __future__ import annotations

import json
from pathlib import Path

import pytest

from analyze_laguna_m8_graph_endpoint import (
    EXPECTED_KERNELS,
    EXPECTED_PROMPT_IDS,
    EXPECTED_VLLM,
    analyze_leg,
)


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def valid_leg(root: Path, name: str) -> Path:
    leg = root / name
    leg.mkdir()
    rows = [
        {
            "cached_tokens": 0,
            "completion_tokens": 512,
            "prompt_id": EXPECTED_PROMPT_IDS[index],
            "prompt_tokens": 863 if index == 12 else 100,
        }
        for index in range(13)
    ]
    write_json(
        leg / "bench.json",
        {
            "rows": rows,
            "output_sha256s": [f"hash-{index}" for index in range(13)],
            "fresh_response_validity": {
                "valid": True,
                "each_prompt_run_once": True,
                "cached_tokens_all_zero": True,
            },
            "run_identity": {
                "api_mode": "chat",
                "base_url": "http://127.0.0.1:18080",
                "created_at_utc": "fixture",
                "max_tokens": 512,
                "model": "laguna-s-2.1-int4",
                "prompt_count": 13,
                "request_extra": {"chat_template_kwargs": {"enable_thinking": False}},
                "return_token_ids": True,
                "seed": 1,
                "suite": {
                    "description": "fixture",
                    "metric": "fixture",
                    "suite_id": "laguna-s-2.1-realistic-cold-v1",
                    "version": 1,
                },
                "suite_path": (
                    "experiments/laguna-s-2.1-xpu-b70/realistic-suite-v1.json"
                ),
            },
        },
    )
    write_json(
        leg / "exactness-vs-q1.json",
        {
            "all_exact": True,
            "candidates": [
                {
                    "comparison": {
                        "exact": True,
                        "exact_count": 13,
                        "total": 13,
                        "long_then_next": {"passed": True},
                        "rollover": {"count": 1, "exact_count": 1},
                    }
                }
            ],
        },
    )
    write_json(
        leg / "identity.json",
        {
            "claim": "endpoint correctness only",
            "vllm_commit": EXPECTED_VLLM,
            "kernel_commit": EXPECTED_KERNELS,
            "execution": {
                "VLLM_USE_AOT_COMPILE": "0",
                "VLLM_USE_BREAKABLE_CUDAGRAPH": "1",
                "VLLM_XPU_ENABLE_XPU_GRAPH": "1",
                "VLLM_XPU_LAGUNA_DETERMINISTIC_GRAPH": "0",
                "VLLM_XPU_LAGUNA_M8_BREAKABLE_GRAPH": "1",
                "XPU_GRAPH": "1",
                "compilation": {
                    "mode": "NONE",
                    "cudagraph_mode": "PIECEWISE",
                    "cudagraph_capture_sizes": [8],
                    "max_cudagraph_capture_size": 8,
                },
            },
            "selectors": {
                "batched_exact_moe": 1,
                "exact_spec_attention": 1,
                "fused_w1_route_w2": 1,
                "qknorm_rope": 1,
                "route_interleave": 1,
                "shared_elementwise": 1,
                "w1_n_tile": 64,
            },
            "request": {
                "async_scheduling": False,
                "concurrency": 1,
                "enable_thinking": False,
                "kv_cache_dtype": "bfloat16",
                "max_tokens": 512,
                "prefix_caching": False,
                "return_token_ids": True,
                "seed": 1,
            },
        },
    )
    descriptor = (
        "BatchDescriptor(num_tokens=8, num_reqs=None, uniform=False, "
        "has_lora=False, num_active_loras=0): "
        "BreakableCUDAGraphCapture(graphs=146, eager_breaks=145)"
    )
    logs = []
    for action in ("Captured", "Replayed"):
        logs.extend(
            f"(Worker_TP{rank}_EP{rank} pid={100 + rank}) "
            f"{action} audited breakable cudagraph {descriptor}"
            for rank in range(4)
        )
    (leg / "server.log").write_text("\n".join(logs) + "\n", encoding="utf-8")
    (leg / "cleanup-status.txt").write_text(
        "stop_status=0\nworker_status=0\nidle_status=0\n", encoding="utf-8"
    )
    (leg / "service-environment.txt").write_text(
        "\n".join(
            [
                "VLLM_USE_AOT_COMPILE=0",
                "VLLM_USE_BREAKABLE_CUDAGRAPH=1",
                "VLLM_XPU_ENABLE_XPU_GRAPH=1",
                "VLLM_XPU_LAGUNA_DETERMINISTIC_GRAPH=0",
                "VLLM_XPU_LAGUNA_M8_BREAKABLE_GRAPH=1",
                "VLLM_XPU_LAGUNA_M8_QKNORM_ROPE=1",
                "VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE=1",
                "VLLM_XPU_LAGUNA_M8_W1_N_TILE=64",
                "XPU_GRAPH=1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return leg


def test_analyze_leg_accepts_exact_four_rank_topology_fixture(tmp_path: Path) -> None:
    valid_leg(tmp_path, "start-a")
    result = analyze_leg(tmp_path, "start-a")
    assert all(result["checks"].values())


def test_analyze_leg_rejects_missing_rank_capture(tmp_path: Path) -> None:
    leg = valid_leg(tmp_path, "start-a")
    log = (leg / "server.log").read_text(encoding="utf-8")
    (leg / "server.log").write_text(
        log.replace("Captured audited breakable cudagraph", "missing", 1),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="four_capture_topologies"):
        analyze_leg(tmp_path, "start-a")


def test_analyze_leg_rejects_selector_drift(tmp_path: Path) -> None:
    leg = valid_leg(tmp_path, "start-a")
    identity = json.loads((leg / "identity.json").read_text(encoding="utf-8"))
    identity["selectors"]["shared_elementwise"] = 0
    write_json(leg / "identity.json", identity)
    with pytest.raises(ValueError, match="selector_identity"):
        analyze_leg(tmp_path, "start-a")


def test_analyze_leg_rejects_benchmark_identity_drift(tmp_path: Path) -> None:
    leg = valid_leg(tmp_path, "start-a")
    bench = json.loads((leg / "bench.json").read_text(encoding="utf-8"))
    bench["run_identity"]["seed"] = 2
    write_json(leg / "bench.json", bench)
    with pytest.raises(ValueError, match="bench_identity"):
        analyze_leg(tmp_path, "start-a")
