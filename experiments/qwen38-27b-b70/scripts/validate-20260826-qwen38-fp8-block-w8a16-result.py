#!/usr/bin/env python3
"""Validate the frozen Qwen3.8 block-W8A16 result and dependency closure."""

from __future__ import annotations

import hashlib
import json
import statistics
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "experiments/qwen38-27b-b70/data"
RAW = DATA / "qwen38-fp8-block-w8a16-tp2-p128-20260826-r1"
DEPTH_W8A16 = DATA / "qwen38-fp8-block-w8a16-tp2-http-depth-20260826-r2"
DEPTH_CONTROL = DATA / "qwen38-fp8-tp2-http-depth-20260826-r1-attempt1"
SUMMARY = DATA / "2026-08-26-qwen38-fp8-block-w8a16-tp2-p128-summary.json"
PATCH = (
    ROOT
    / "experiments/qwen38-27b-b70/patches"
    / "vllm-qwen38-fp8-block-w8a16-20260826.patch"
)
REPRO = ROOT / "repro/qwen38-27b-fp8-vllm-tp2-asrock-b70"


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def close(actual: float, expected: float, tolerance: float = 1e-9) -> None:
    assert abs(actual - expected) <= tolerance, (actual, expected)


def conditioned_median(path: Path) -> float:
    values = [row["aggregate_tok_s_wall"] for row in load(path)["batches"]]
    assert len(values) == 5
    return statistics.median(values[1:])


def main() -> int:
    summary = load(SUMMARY)
    assert summary["status"] == "quality-qualified-candidate"
    assert summary["change"]["default_off"] is True
    assert summary["reporting_boundary"].startswith(
        "Every performance value is directly measured"
    )

    optimized = load(RAW / "w8a16-c128-measured-x5.json")
    control = load(RAW / "default-off-c128-measured-x5.json")
    for result in (optimized, control):
        assert result["classification"] == "output-isolation-qualified-shape-variant"
        assert len(result["batches"]) == 5
        for batch in result["batches"]:
            assert batch["request_count"] == 128
            assert batch["total_completion_tokens"] == 16384
            assert batch["completion_tokens_complete"] is True
            assert batch["cached_tokens_all_zero"] is True
            assert batch["cross_base_oracle_collision_count"] == 0
            assert batch["complete_token_id_identity_all"] is True

    optimized_rate = conditioned_median(RAW / "w8a16-c128-measured-x5.json")
    control_rate = conditioned_median(RAW / "default-off-c128-measured-x5.json")
    close(optimized_rate, summary["aggregate"]["w8a16_tok_s"])
    close(control_rate, summary["aggregate"]["default_off_tok_s"])
    close(
        (optimized_rate / control_rate - 1) * 100,
        summary["aggregate"]["improvement_percent"],
    )
    assert optimized_rate > 1000

    depth_optimized = load(DEPTH_W8A16 / "summary.json")
    depth_control = load(DEPTH_CONTROL / "summary.json")
    assert depth_optimized["classification"] == "qualified-exact-depth"
    assert depth_control["classification"] == "qualified-exact-depth"
    assert len(summary["exact_context"]["points"]) == 6
    for frozen, optimized_point, control_point in zip(
        summary["exact_context"]["points"],
        depth_optimized["points"],
        depth_control["points"],
        strict=True,
    ):
        depth = frozen["context_tokens"]
        assert optimized_point["active_context_tokens"] == depth
        assert control_point["active_context_tokens"] == depth
        assert optimized_point["status"] == "passed"
        assert optimized_point["cached_tokens_zero"] is True
        close(optimized_point["decode_tok_s"], frozen["w8a16_decode_tok_s"])
        close(control_point["decode_tok_s"], frozen["default_off_decode_tok_s"])
        close(optimized_point["ttft_ms"], frozen["w8a16_ttft_ms"])
        close(
            (optimized_point["decode_tok_s"] / control_point["decode_tok_s"] - 1)
            * 100,
            frozen["decode_improvement_percent"],
        )
        close(
            (1 - optimized_point["ttft_ms"] / control_point["ttft_ms"]) * 100,
            frozen["ttft_reduction_percent"],
        )
        receipt = load(DEPTH_W8A16 / f"depth-{depth}.json")
        assert receipt["gate"]["passed"] is True
        assert receipt["response"]["output_token_ids_sha256"] == frozen[
            "output_token_ids_sha256"
        ]

    optimized_single = load(RAW / "w8a16-c1-p128-p40-o128.json")
    control_single = load(RAW / "default-off-c1-p40-o128.json")
    for result in (optimized_single, control_single):
        assert result["rows"][0]["prompt_tokens"] == 40
        assert result["rows"][0]["completion_tokens"] == 128
        assert result["rows"][0]["usage"]["prompt_tokens_details"]["cached_tokens"] == 0
    optimized_single_rate = optimized_single["fresh_response_validity"][
        "headline_tok_s_after_ttft"
    ]
    control_single_rate = control_single["fresh_response_validity"][
        "headline_tok_s_after_ttft"
    ]
    close(optimized_single_rate, summary["single_user"]["w8a16_tok_s"])
    close(control_single_rate, summary["single_user"]["default_off_tok_s"])
    close(
        (optimized_single_rate / control_single_rate - 1) * 100,
        summary["single_user"]["improvement_percent"],
    )

    sequential = load(RAW / "w8a16-sequential-quality.json")
    assert sequential["pass_all"] is True
    assert len(sequential["exact_cases"]) == 7
    assert all(case["pass"] for case in sequential["exact_cases"])
    assert sequential["repeat_case"]["pass"] is True
    assert len(sequential["repeat_case"]["unique_hashes"]) == 1

    concurrent = load(RAW / "w8a16-c128-quality-1024.json")
    assert concurrent["pass_all"] is True
    assert concurrent["total_requests"] == 1024
    assert concurrent["concurrency"] == 128
    assert concurrent["rounds"] == 8
    assert all(row["failed"] == 0 and row["passed"] == 128 for row in concurrent["results"])

    ladder = load(RAW / "w8a16-c64-c128-ladder.json")
    measured = {
        row["concurrency"]: row["aggregate_tok_s_wall"] for row in ladder["batches"]
    }
    assert set(measured) == {64, 80, 96, 112, 128}
    for point in summary["measured_concurrency_screen"]:
        close(measured[point["concurrent_users"]], point["aggregate_tok_s"])
        assert point["samples"] == 1

    assert hashlib.sha256(PATCH.read_bytes()).hexdigest() == (
        "5db7f1af1156f3490ca91d0d74a07aa2d0909e175eeb1ae23f2074c55c44ff8a"
    )
    for name in (
        "Dockerfile.w8a16",
        "build-w8a16-image.sh",
        "run-w8a16-concurrency-server.sh",
        "run-w8a16-depth-server.sh",
        "bench-w8a16-concurrency.sh",
        "verify-model-direct.sh",
    ):
        assert (REPRO / name).is_file(), name

    print(
        json.dumps(
            {
                "status": "PASS",
                "aggregate_w8a16_tok_s": optimized_rate,
                "aggregate_default_off_tok_s": control_rate,
                "single_w8a16_tok_s": optimized_single_rate,
                "depth_32k_w8a16_tok_s": summary["exact_context"]["points"][-1][
                    "w8a16_decode_tok_s"
                ],
                "concurrent_quality": "1024/1024",
                "sequential_quality": "7/7 + repeat 8/8",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
