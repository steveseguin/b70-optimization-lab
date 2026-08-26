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
MTP_RAW = DATA / "qwen38-fp8-block-w8a16-mtp1-tp2-p128-screen-20260826-r1"
MTP_SUMMARY = (
    DATA / "2026-08-26-qwen38-fp8-block-w8a16-mtp1-tp2-summary.json"
)
MTP2_RAW = DATA / "qwen38-fp8-block-w8a16-mtp2-reuse-screen-20260826-r1"
MTP2_MBT768_RAW = (
    DATA / "qwen38-fp8-block-w8a16-mtp2-reuse-mbt768-screen-20260826-r1"
)
MTP2_SUMMARY = (
    DATA / "2026-08-26-qwen38-fp8-block-w8a16-mtp2-reuse-summary.json"
)
PATCH = (
    ROOT
    / "experiments/qwen38-27b-b70/patches"
    / "vllm-qwen38-fp8-block-w8a16-20260826.patch"
)
REPRO = ROOT / "repro/qwen38-27b-fp8-vllm-tp2-asrock-b70"
MTP_KERNEL_DOCKERFILE = (
    ROOT / "experiments/qwen38-27b-b70/docker/Dockerfile.fp8-kernel-1e90-r13"
)
PACKAGE = ROOT / "packages/qwen38-27b-fp8-tp2-b70/package.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def close(actual: float, expected: float, tolerance: float = 1e-9) -> None:
    assert abs(actual - expected) <= tolerance, (actual, expected)


def conditioned_median(path: Path) -> float:
    values = [row["aggregate_tok_s_wall"] for row in load(path)["batches"]]
    assert len(values) == 5
    return statistics.median(values[1:])


def validate_output_isolation_batch(batch: dict, concurrency: int) -> None:
    assert batch["concurrency"] == concurrency
    assert batch["request_count"] == concurrency
    assert batch["total_completion_tokens"] == concurrency * 128
    assert batch["completion_tokens_complete"] is True
    assert batch["cached_tokens_all_zero"] is True
    assert batch["cross_base_oracle_collision_count"] == 0
    assert batch["complete_token_id_identity_all"] is True


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

    mtp = load(MTP_SUMMARY)
    assert mtp["classification"] == "measured-candidate-profile"
    assert mtp["model"]["speculative_tokens"] == 1
    assert mtp["service"]["max_model_len"] == 256
    assert mtp["service"]["max_num_batched_tokens"] == 512
    assert "No point is interpolated or extrapolated" in mtp["reporting_boundary"]
    assert "MTP0 and MTP1 remain separate" in mtp["reporting_boundary"]

    mtp_single = load(MTP_RAW / "mbt512-single-p40-o128.json")
    mtp_single_row = mtp_single["rows"][0]
    assert mtp_single_row["prompt_tokens"] == 40
    assert mtp_single_row["completion_tokens"] == 128
    assert mtp_single_row["usage"]["prompt_tokens_details"]["cached_tokens"] == 0
    mtp_single_rate = mtp_single["fresh_response_validity"][
        "headline_tok_s_after_ttft"
    ]
    close(mtp_single_rate, mtp["single_user"]["fresh_response_after_ttft_tok_s"])
    close(
        (mtp_single_rate / optimized_single_rate - 1) * 100,
        mtp["single_user"]["gain_vs_mtp0_percent"],
        tolerance=1e-6,
    )

    mtp_points = {
        point["concurrent_sequences"]: point for point in mtp["concurrency"]["points"]
    }
    mtp_files = {
        8: "mbt512-replay-c8.json",
        16: "mbt512-replay-c16.json",
        32: "mbt512-replay-c32.json",
        64: "mbt512-c64-replication-x3.json",
        128: "mbt512-c128-replication-x3.json",
    }
    assert set(mtp_points) == set(mtp_files)
    for concurrency, filename in mtp_files.items():
        result = load(MTP_RAW / filename)
        assert result["classification"] in {
            "output-identity-qualified",
            "output-isolation-qualified-shape-variant",
        }
        expected_samples = 3 if concurrency in {64, 128} else 1
        assert len(result["batches"]) == expected_samples
        values = []
        for batch in result["batches"]:
            validate_output_isolation_batch(batch, concurrency)
            values.append(batch["aggregate_tok_s_wall"])
        measured_rate = statistics.median(values)
        close(measured_rate, mtp_points[concurrency]["aggregate_tok_s"])
        close(measured_rate / concurrency, mtp_points[concurrency]["per_user_tok_s"])
        assert mtp_points[concurrency]["samples"] == expected_samples
        if expected_samples == 3:
            assert mtp_points[concurrency]["statistic"] == "median"
            assert mtp_points[concurrency]["sample_values"] == values

    mtp_sequential = load(MTP_RAW / "mbt512-sequential-quality.json")
    assert mtp_sequential["pass_all"] is True
    assert len(mtp_sequential["exact_cases"]) == 7
    assert all(case["pass"] for case in mtp_sequential["exact_cases"])
    assert mtp_sequential["repeat_case"]["pass"] is True
    assert len(mtp_sequential["repeat_case"]["unique_hashes"]) == 1

    mtp_concurrent = load(MTP_RAW / "mbt512-c64-quality-512.json")
    assert mtp_concurrent["pass_all"] is True
    assert mtp_concurrent["total_requests"] == 512
    assert mtp_concurrent["concurrency"] == 64
    assert mtp_concurrent["rounds"] == 8
    assert all(
        row["failed"] == 0 and row["passed"] == 64
        for row in mtp_concurrent["results"]
    )

    rejected_log = (MTP_RAW / "r121-server.log").read_text(errors="replace")
    assert (
        "causal_conv1d does not support spec-decode and non-spec "
        "(prefill + decode) tokens in the same invocation"
    ) in rejected_log
    assert MTP_KERNEL_DOCKERFILE.is_file()
    kernel_dockerfile = MTP_KERNEL_DOCKERFILE.read_text()
    assert "1e90ffa672ba02f17a909da11838a4c55b199783" in kernel_dockerfile
    assert "f3d999060c11ad6db5b4033d50d19c6b665492380075480d041ec4ee58fdfeb6" in kernel_dockerfile

    mtp2 = load(MTP2_SUMMARY)
    assert mtp2["classification"] == "measured-research-screen"
    assert mtp2["model"]["publisher_mtp_layers"] == 1
    assert mtp2["model"]["requested_speculative_tokens"] == 2
    assert "not native two-layer MTP" in mtp2["model"]["mode"]
    assert mtp2["decision"]["status"] == "closed-research-profile"
    assert mtp2["decision"]["mbt1024"] == "not run by preregistered stop rule"
    assert "No value is interpolated or extrapolated" in mtp2["reporting_boundary"]

    mtp2_single = load(MTP2_RAW / "single-p40-o128.json")
    mtp2_single_row = mtp2_single["rows"][0]
    assert mtp2_single_row["prompt_tokens"] == 40
    assert mtp2_single_row["completion_tokens"] == 128
    assert mtp2_single_row["usage"]["prompt_tokens_details"]["cached_tokens"] == 0
    mtp2_single_rate = mtp2_single["fresh_response_validity"][
        "headline_tok_s_after_ttft"
    ]
    close(mtp2_single_rate, mtp2["single_user"]["fresh_response_after_ttft_tok_s"])
    close(
        (mtp2_single_rate / mtp_single_rate - 1) * 100,
        mtp2["single_user"]["gain_vs_mtp1_percent"],
    )

    for raw_dir, point in zip(
        (MTP2_RAW, MTP2_MBT768_RAW),
        mtp2["concurrency"]["points"],
        strict=True,
    ):
        c64 = load(raw_dir / "c64-screen.json")
        assert c64["classification"] == "output-isolation-qualified-shape-variant"
        assert len(c64["batches"]) == 1
        batch = c64["batches"][0]
        validate_output_isolation_batch(batch, 64)
        close(batch["aggregate_tok_s_wall"], point["aggregate_tok_s"])
        assert f'{batch["oracle_exact_count"]}/{batch["oracle_exact_total"]}' == point[
            "sequential_oracle_exact"
        ]

        mtp2_quality = load(raw_dir / "sequential-quality.json")
        assert mtp2_quality["pass_all"] is True
        assert len(mtp2_quality["exact_cases"]) == 7
        assert all(case["pass"] for case in mtp2_quality["exact_cases"])
        assert mtp2_quality["repeat_case"]["pass"] is True

    assert mtp2["quality"]["sequential_evidence"] == [
        f"{MTP2_RAW.name}/sequential-quality.json",
        f"{MTP2_MBT768_RAW.name}/sequential-quality.json",
    ]

    package = load(PACKAGE)
    depth_profile = next(
        profile
        for profile in package["performance_profiles"]
        if profile["id"]
        == "http-block-w8a16-single-user-vs-speculative-tokens"
    )
    assert depth_profile["x_metric"] == "speculative_tokens"
    assert "No point is interpolated or extrapolated" in depth_profile["scope"]
    assert [point["speculative_tokens"] for point in depth_profile["points"]] == [
        0,
        1,
        2,
    ]
    for point, expected in zip(
        depth_profile["points"],
        (optimized_single_rate, mtp_single_rate, mtp2_single_rate),
        strict=True,
    ):
        close(point["value"], expected)
        assert point["samples"] == 1

    package_dependencies = set(package["dependencies"])
    for raw_dir in (MTP2_RAW, MTP2_MBT768_RAW):
        relative_quality = str(
            (raw_dir / "sequential-quality.json").relative_to(ROOT)
        )
        assert relative_quality in package_dependencies

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
        "build-mtp1-kernel-image.sh",
        "run-w8a16-mtp1-server.sh",
        "bench-w8a16-mtp1.sh",
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
                "mtp1_single_w8a16_tok_s": mtp_single_rate,
                "mtp1_aggregate_peak_tok_s": mtp_points[64]["aggregate_tok_s"],
                "mtp2_reuse_single_w8a16_tok_s": mtp2_single_rate,
                "mtp2_reuse_c64_tok_s": mtp2["concurrency"]["points"][0][
                    "aggregate_tok_s"
                ],
                "depth_32k_w8a16_tok_s": summary["exact_context"]["points"][-1][
                    "w8a16_decode_tok_s"
                ],
                "concurrent_quality": "1024/1024",
                "sequential_quality": "7/7 + repeat 8/8",
                "mtp1_concurrent_quality": "512/512",
                "mtp1_sequential_quality": "7/7 + repeat 8/8",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
