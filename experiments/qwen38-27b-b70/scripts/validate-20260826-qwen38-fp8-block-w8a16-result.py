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
MTP2_LOCAL_RAW = DATA / "qwen38-fp8-w8a16-mtp2-local-argmax-20260826-r1"
MTP2_LOCAL_SUMMARY = (
    DATA / "2026-08-26-qwen38-fp8-w8a16-mtp2-local-argmax-r1-summary.json"
)
MTP2_DYNAMIC_RAW = DATA / "qwen38-fp8-w8a16-mtp2-dynamic-20260826-r1"
MTP2_DYNAMIC_SUMMARY = (
    DATA / "2026-08-26-qwen38-fp8-w8a16-mtp2-dynamic-r1-summary.json"
)
MTP2_DYNAMIC_FIXED_RAW = (
    DATA / "qwen38-fp8-w8a16-mtp2-dynamic-mtp1-fixed-20260826-r2"
)
MTP2_DYNAMIC_FIXED_SUMMARY = (
    DATA
    / "2026-08-26-qwen38-fp8-w8a16-mtp2-dynamic-mtp1-fixed-r2-summary.json"
)
MTP2_DYNAMIC_P192_RAW = (
    DATA / "qwen38-fp8-w8a16-mtp2-dynamic-mtp1-fixed-r3-p192-20260826"
)
MTP2_DYNAMIC_P192_SUMMARY = (
    DATA
    / "2026-08-26-qwen38-fp8-w8a16-mtp2-dynamic-mtp1-fixed-r3-p192-summary.json"
)
MTP2_DYNAMIC_MAMBA_RAW = (
    DATA / "qwen38-fp8-w8a16-mtp2-dynamic-mamba-20260826-r4"
)
MTP2_DYNAMIC_MAMBA_SUMMARY = (
    DATA / "2026-08-26-qwen38-fp8-w8a16-mtp2-dynamic-mamba-r4-summary.json"
)
MTP2_DYNAMIC_MAMBA_REPLICATION_RAW = (
    DATA / "qwen38-fp8-w8a16-mtp2-dynamic-mamba-20260827-r5"
)
MTP2_DYNAMIC_MAMBA_REPLICATION_SUMMARY = (
    DATA / "2026-08-27-qwen38-fp8-w8a16-mtp2-dynamic-mamba-r5-summary.json"
)
MTP3_DYNAMIC_RAW = (
    DATA / "qwen38-fp8-w8a16-mtp3-dynamic-mtp1-20260827-r6"
)
MTP3_DYNAMIC_SCREEN_SUMMARY = (
    DATA / "2026-08-27-qwen38-fp8-w8a16-mtp3-dynamic-mtp1-r6-summary.json"
)
MTP3_DYNAMIC_REPLICATION_RAW = (
    DATA / "qwen38-fp8-w8a16-mtp3-dynamic-mtp1-20260827-r7"
)
MTP3_DYNAMIC_REPLICATION_SUMMARY = (
    DATA / "2026-08-27-qwen38-fp8-w8a16-mtp3-dynamic-mtp1-r7-summary.json"
)
MTP4_DYNAMIC_RAW = (
    DATA / "qwen38-fp8-w8a16-mtp4-dynamic-mtp1-20260827-r8"
)
MTP4_DYNAMIC_SCREEN_SUMMARY = (
    DATA / "2026-08-27-qwen38-fp8-w8a16-mtp4-dynamic-mtp1-r8-summary.json"
)
MTP4_DYNAMIC_REPLICATION_RAW = (
    DATA / "qwen38-fp8-w8a16-mtp4-dynamic-mtp1-20260827-r9"
)
MTP4_DYNAMIC_REPLICATION_SUMMARY = (
    DATA / "2026-08-27-qwen38-fp8-w8a16-mtp4-dynamic-mtp1-r9-summary.json"
)
MTP5_DYNAMIC_RAW = (
    DATA / "qwen38-fp8-w8a16-mtp5-dynamic-mtp1-20260827-r10"
)
MTP5_DYNAMIC_SCREEN_SUMMARY = (
    DATA / "2026-08-27-qwen38-fp8-w8a16-mtp5-dynamic-mtp1-r10-summary.json"
)
MTP5_DYNAMIC_REPLICATION_RAW = (
    DATA / "qwen38-fp8-w8a16-mtp5-dynamic-mtp1-20260827-r11"
)
MTP5_DYNAMIC_REPLICATION_SUMMARY = (
    DATA / "2026-08-27-qwen38-fp8-w8a16-mtp5-dynamic-mtp1-r11-summary.json"
)
DYNAMIC_MAMBA_PATCH = (
    ROOT
    / "experiments/qwen38-27b-b70/patches"
    / "vllm-qwen38-dynamic-mtp-mamba-active-allocation-20260826.patch"
)
PATCH = (
    ROOT
    / "experiments/qwen38-27b-b70/patches"
    / "vllm-qwen38-fp8-block-w8a16-20260826.patch"
)
LOCAL_ARGMAX_PATCH = (
    ROOT
    / "experiments/qwen38-27b-b70/patches"
    / "vllm-qwen38-next-mtp-local-argmax-hook-20260826.patch"
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


def validate_dynamic_attempt(
    raw_dir: Path,
    expected_single: float,
    expected_c64: float,
    expected_image_id: str,
    speculative_tokens: int,
    expect_shutdown_error: bool,
) -> tuple[float, float]:
    bench = raw_dir / "bench" if (raw_dir / "bench").is_dir() else raw_dir
    single = load(bench / "single-p40-o128.json")
    single_rate = single["fresh_response_validity"][
        "headline_tok_s_after_ttft"
    ]
    close(single_rate, expected_single)
    assert single["fresh_response_validity"]["cached_tokens_all_zero"] is True
    assert single["rows"][0]["usage"]["completion_tokens"] == 128
    assert single["rows"][0]["usage"]["prompt_tokens_details"][
        "cached_tokens"
    ] == 0

    c2 = load(bench / "excluded-c2-crash-canary.json")
    c64 = load(bench / "c64-screen.json")
    validate_output_isolation_batch(c2["batches"][0], 2)
    validate_output_isolation_batch(c64["batches"][0], 64)
    c64_rate = c64["batches"][0]["aggregate_tok_s_wall"]
    close(c64_rate, expected_c64)

    quality = load(bench / "sequential-quality.json")
    assert quality["pass_all"] is True
    assert quality["baseline_match_all"] is True
    assert len(quality["exact_cases"]) == 7
    assert len(quality["repeat_case"]["runs"]) == 8
    assert all(
        case["usage"]["prompt_tokens_details"]["cached_tokens"] == 0
        for case in quality["exact_cases"]
    )

    concurrent_quality = load(bench / "c64-quality-512.json")
    assert concurrent_quality["total_requests"] == 512
    assert concurrent_quality["pass_all"] is True
    assert all(row["passed"] == 64 for row in concurrent_quality["results"])
    assert all(row["failed"] == 0 for row in concurrent_quality["results"])
    assert all(
        row["cached_tokens_nonzero"] == 0
        for row in concurrent_quality["results"]
    )

    inspect = load(bench / "docker-inspect-final.json")[0]
    assert inspect["Image"] == expected_image_id
    assert inspect["State"]["ExitCode"] == 0
    assert inspect["State"]["OOMKilled"] is False
    command = inspect["Config"]["Cmd"]
    config = json.loads(command[command.index("--speculative-config") + 1])
    assert config == {
        "method": "qwen3_next_mtp",
        "num_speculative_tokens": speculative_tokens,
        "num_speculative_tokens_per_batch_size": [
            [1, 1, speculative_tokens],
            [2, 128, 1],
        ],
    }
    log = (raw_dir / "server-final.log").read_text(errors="replace")
    assert ("EngineDeadError" in log) is expect_shutdown_error
    return single_rate, c64_rate


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

    local = load(MTP2_LOCAL_SUMMARY)
    assert local["classification"] == "measured-negative-screen"
    assert local["treatment"]["target_verification_changed"] is False
    assert local["decision"]["status"] == "closed-negative"
    assert local["decision"]["replication"] == (
        "not run by preregistered stop rule"
    )
    assert "No value is interpolated or extrapolated" in local[
        "reporting_boundary"
    ]

    local_quality = load(MTP2_LOCAL_RAW / "sequential-quality.json")
    mtp2_control_quality = load(MTP2_RAW / "sequential-quality.json")
    control_hashes = [
        case["sha256"] for case in mtp2_control_quality["exact_cases"]
    ]
    local_hashes = [case["sha256"] for case in local_quality["exact_cases"]]
    assert local_quality["pass_all"] is True
    assert local_hashes == control_hashes
    assert local_quality["repeat_case"]["unique_hashes"] == mtp2_control_quality[
        "repeat_case"
    ]["unique_hashes"]
    local_quality_usages = [
        case["usage"]["prompt_tokens_details"]["cached_tokens"]
        for case in local_quality["exact_cases"]
    ] + [
        run["usage"]["prompt_tokens_details"]["cached_tokens"]
        for run in local_quality["repeat_case"]["runs"]
    ]
    assert all(value == 0 for value in local_quality_usages)

    local_single = load(MTP2_LOCAL_RAW / "single-p40-o128.json")
    local_single_rate = local_single["fresh_response_validity"][
        "headline_tok_s_after_ttft"
    ]
    assert local_single["fresh_response_validity"]["cached_tokens_all_zero"] is True
    close(local_single_rate, local["single_user"]["fresh_response_after_ttft_tok_s"])
    close(
        (local_single_rate / mtp2_single_rate - 1) * 100,
        local["single_user"]["change_vs_mtp2_control_percent"],
    )
    assert local["single_user"]["retention_gate_passed"] is True
    assert local["single_user"]["material_improvement"] is False

    local_c64 = load(MTP2_LOCAL_RAW / "c64-screen.json")
    assert local_c64["classification"] == "output-isolation-qualified-shape-variant"
    assert len(local_c64["batches"]) == 1
    local_batch = local_c64["batches"][0]
    validate_output_isolation_batch(local_batch, 64)
    local_c64_rate = local_batch["aggregate_tok_s_wall"]
    close(local_c64_rate, local["concurrency"]["aggregate_tok_s"])
    close(
        (local_c64_rate / mtp2["concurrency"]["points"][0]["aggregate_tok_s"] - 1)
        * 100,
        local["concurrency"]["change_vs_mtp2_control_percent"],
    )
    assert local["concurrency"]["gate_passed"] is False
    assert local_c64_rate < local["concurrency"]["gate_tok_s"]
    assert not (MTP2_LOCAL_RAW / "c64-replication.json").exists()
    assert not (MTP2_LOCAL_RAW / "c64-quality-512.json").exists()

    local_inspect = load(MTP2_LOCAL_RAW / "docker-inspect.json")[0]
    assert local_inspect["Image"] == local["runtime"]["image_id"]
    labels = local_inspect["Config"]["Labels"]
    assert labels["neural.download.mtp.local_argmax.patch.sha256"] == local[
        "treatment"
    ]["patch_sha256"]
    assert hashlib.sha256(LOCAL_ARGMAX_PATCH.read_bytes()).hexdigest() == local[
        "treatment"
    ]["patch_sha256"]

    dynamic = load(MTP2_DYNAMIC_SUMMARY)
    assert dynamic["classification"] == "measured-negative-screen"
    assert dynamic["treatment"]["source_patch"] is None
    assert dynamic["treatment"]["target_verification_changed"] is False
    assert dynamic["treatment"]["speculative_config"][
        "num_speculative_tokens_per_batch_size"
    ] == [[1, 1, 2], [2, 128, 0]]
    assert dynamic["decision"]["status"] == "closed-negative"
    assert dynamic["decision"]["replication"] == (
        "not run by preregistered stop rule"
    )
    assert "No value is interpolated or extrapolated" in dynamic[
        "reporting_boundary"
    ]

    dynamic_quality = load(MTP2_DYNAMIC_RAW / "sequential-quality.json")
    dynamic_hashes = [
        case["sha256"] for case in dynamic_quality["exact_cases"]
    ]
    assert dynamic_quality["pass_all"] is True
    assert dynamic_hashes == control_hashes
    assert dynamic_quality["repeat_case"]["hashes"] == mtp2_control_quality[
        "repeat_case"
    ]["hashes"]
    dynamic_quality_usages = [
        case["usage"]["prompt_tokens_details"]["cached_tokens"]
        for case in dynamic_quality["exact_cases"]
    ] + [
        run["usage"]["prompt_tokens_details"]["cached_tokens"]
        for run in dynamic_quality["repeat_case"]["runs"]
    ]
    assert len(dynamic_quality_usages) == 15
    assert all(value == 0 for value in dynamic_quality_usages)

    dynamic_single = load(MTP2_DYNAMIC_RAW / "single-p40-o128.json")
    dynamic_single_rate = dynamic_single["fresh_response_validity"][
        "headline_tok_s_after_ttft"
    ]
    assert dynamic_single["fresh_response_validity"][
        "cached_tokens_all_zero"
    ] is True
    close(
        dynamic_single_rate,
        dynamic["single_user"]["fresh_response_after_ttft_tok_s"],
    )
    close(
        (dynamic_single_rate / mtp2_single_rate - 1) * 100,
        dynamic["single_user"]["change_vs_static_mtp2_percent"],
    )
    assert dynamic["single_user"]["retention_gate_passed"] is True
    assert dynamic_single_rate >= dynamic["single_user"]["retention_gate_tok_s"]

    transition = load(MTP2_DYNAMIC_RAW / "excluded-c64-transition.json")
    dynamic_c64 = load(MTP2_DYNAMIC_RAW / "c64-screen.json")
    assert transition["classification"] == (
        "output-isolation-qualified-shape-variant"
    )
    assert dynamic_c64["classification"] == (
        "output-isolation-qualified-shape-variant"
    )
    assert len(transition["batches"]) == 1
    assert len(dynamic_c64["batches"]) == 1
    transition_batch = transition["batches"][0]
    dynamic_batch = dynamic_c64["batches"][0]
    validate_output_isolation_batch(transition_batch, 64)
    validate_output_isolation_batch(dynamic_batch, 64)
    dynamic_c64_rate = dynamic_batch["aggregate_tok_s_wall"]
    close(
        transition_batch["aggregate_tok_s_wall"],
        dynamic["concurrency"]["excluded_transition_tok_s"],
    )
    close(
        dynamic_c64_rate,
        dynamic["concurrency"]["declared_aggregate_tok_s"],
    )
    close(
        (dynamic_c64_rate / mtp2["concurrency"]["points"][0]["aggregate_tok_s"] - 1)
        * 100,
        dynamic["concurrency"]["change_vs_static_mtp2_percent"],
    )
    close(
        (dynamic_c64_rate / mtp_points[64]["aggregate_tok_s"] - 1) * 100,
        dynamic["concurrency"]["change_vs_static_mtp1_percent"],
    )
    base_ladder = load(RAW / "w8a16-c64-c128-ladder.json")
    base_c64_rate = next(
        batch["aggregate_tok_s_wall"]
        for batch in base_ladder["batches"]
        if batch["concurrency"] == 64
    )
    close(
        (dynamic_c64_rate / base_c64_rate - 1) * 100,
        dynamic["concurrency"]["change_vs_static_mtp0_same_shape_percent"],
    )
    assert dynamic["concurrency"]["gate_passed"] is False
    assert dynamic_c64_rate < dynamic["concurrency"]["gate_tok_s"]
    assert not (MTP2_DYNAMIC_RAW / "c64-replication.json").exists()
    assert not (MTP2_DYNAMIC_RAW / "c64-quality-512.json").exists()

    dynamic_inspect = load(MTP2_DYNAMIC_RAW / "docker-inspect.json")[0]
    assert dynamic_inspect["Image"] == dynamic["runtime"]["image_id"]
    dynamic_command = dynamic_inspect["Config"]["Cmd"]
    dynamic_config = dynamic_command[
        dynamic_command.index("--speculative-config") + 1
    ]
    assert '"num_speculative_tokens_per_batch_size":[[1,1,2],[2,128,0]]' in (
        dynamic_config
    )
    dynamic_launcher = REPRO / "run-w8a16-mtp2-dynamic-server.sh"
    assert dynamic_launcher.is_file()
    assert "[[1,1,2],[2,128,0]]" in dynamic_launcher.read_text()

    fixed = load(MTP2_DYNAMIC_FIXED_SUMMARY)
    assert fixed["classification"] == "measured-negative-screen"
    assert fixed["service"]["speculative_config"][
        "num_speculative_tokens_per_batch_size"
    ] == [[1, 1, 2], [2, 128, 1]]
    assert fixed["repair_validation"]["focused_test"].startswith("passed 1/1")
    assert fixed["repair_validation"]["c2_crash_canary"]["engine_health_after"] == (
        "pass"
    )
    assert fixed["quality"]["baseline_match_all"] is True
    assert fixed["decision"]["status"] == "closed-negative"
    assert fixed["decision"]["replication"] == (
        "not run by preregistered stop rule"
    )
    assert "No value is interpolated or extrapolated" in fixed[
        "reporting_boundary"
    ]

    fixed_quality = load(MTP2_DYNAMIC_FIXED_RAW / "sequential-quality.json")
    assert fixed_quality["pass_all"] is True
    assert fixed_quality["baseline_match_all"] is True
    fixed_single = load(MTP2_DYNAMIC_FIXED_RAW / "single-p40-o128.json")
    fixed_single_rate = fixed_single["fresh_response_validity"][
        "headline_tok_s_after_ttft"
    ]
    close(
        fixed_single_rate,
        fixed["single_user"]["fresh_response_after_ttft_tok_s"],
    )
    assert fixed_single_rate >= fixed["single_user"]["gate_tok_s"]
    fixed_c2 = load(MTP2_DYNAMIC_FIXED_RAW / "excluded-c2-crash-canary.json")
    validate_output_isolation_batch(fixed_c2["batches"][0], 2)
    fixed_transition = load(
        MTP2_DYNAMIC_FIXED_RAW / "excluded-c64-transition.json"
    )
    fixed_c64 = load(MTP2_DYNAMIC_FIXED_RAW / "c64-screen.json")
    validate_output_isolation_batch(fixed_transition["batches"][0], 64)
    validate_output_isolation_batch(fixed_c64["batches"][0], 64)
    close(
        fixed_transition["batches"][0]["aggregate_tok_s_wall"],
        fixed["concurrency"]["excluded_transition_tok_s"],
    )
    close(
        fixed_c64["batches"][0]["aggregate_tok_s_wall"],
        fixed["concurrency"]["declared_c64_tok_s"],
    )
    assert fixed["concurrency"]["gate_passed"] is False
    assert fixed["concurrency"]["declared_c64_tok_s"] < fixed[
        "concurrency"
    ]["gate_tok_s"]
    fixed_inspect = load(MTP2_DYNAMIC_FIXED_RAW / "docker-inspect.json")[0]
    assert fixed_inspect["Image"] == fixed["runtime"]["image_id"]
    assert fixed_inspect["Config"]["Labels"][
        "neural.download.kernel.patch.sha256"
    ] == fixed["runtime"]["kernel_patch_sha256"]
    assert not (MTP2_DYNAMIC_FIXED_RAW / "c64-replication.json").exists()
    assert not (MTP2_DYNAMIC_FIXED_RAW / "c64-quality-512.json").exists()

    p192 = load(MTP2_DYNAMIC_P192_SUMMARY)
    assert p192["classification"] == "mechanism-invalidated-before-aggregate"
    assert p192["service"]["max_model_len"] == 192
    assert p192["treatment"]["only_change_vs_r2"] == (
        "max_model_len 256 to 192"
    )
    assert p192["capacity"]["reported_max_concurrency_at_192_tokens"] == 49.2
    assert p192["capacity"]["r2_reported_max_concurrency_at_256_tokens"] == 49.2
    p192_conditioner = load(
        MTP2_DYNAMIC_P192_RAW / "excluded-single-conditioning.json"
    )
    p192_single = load(MTP2_DYNAMIC_P192_RAW / "single-p40-o128.json")
    close(
        p192_conditioner["fresh_response_validity"][
            "headline_tok_s_after_ttft"
        ],
        p192["single_user"]["excluded_conditioning_tok_s_after_ttft"],
    )
    p192_single_rate = p192_single["fresh_response_validity"][
        "headline_tok_s_after_ttft"
    ]
    close(
        p192_single_rate,
        p192["single_user"]["first_eligible_fresh_response_tok_s_after_ttft"],
    )
    assert p192_single["rows"][0]["usage"]["completion_tokens"] == 128
    assert p192_single["rows"][0]["usage"]["prompt_tokens"] == 40
    assert p192_single["rows"][0]["usage"]["prompt_tokens_details"][
        "cached_tokens"
    ] == 0
    assert p192_single_rate < p192["single_user"]["gate_tok_s"]
    assert p192["concurrency"]["declared_c64_run"] is False
    assert p192["concurrency"]["aggregate_tok_s"] is None
    assert not (MTP2_DYNAMIC_P192_RAW / "excluded-c64-transition.json").exists()
    assert not (MTP2_DYNAMIC_P192_RAW / "c64-screen.json").exists()
    p192_log = (MTP2_DYNAMIC_P192_RAW / "server-final.log").read_text(
        errors="replace"
    )
    assert "GPU KV cache size: 9,446 tokens" in p192_log
    assert "Maximum concurrency for 192 tokens per request: 49.20x" in p192_log
    p192_inspect = load(MTP2_DYNAMIC_P192_RAW / "docker-inspect.json")[0]
    assert p192_inspect["Image"] == p192["runtime"]["image_id"]
    assert "--max-model-len" in p192_inspect["Config"]["Cmd"]
    assert p192_inspect["Config"]["Cmd"][
        p192_inspect["Config"]["Cmd"].index("--max-model-len") + 1
    ] == "192"
    assert "none is interpolated or extrapolated" in p192["reporting_boundary"]

    mamba = load(MTP2_DYNAMIC_MAMBA_SUMMARY)
    assert mamba["classification"] == (
        "measured-positive-screen-pending-replication"
    )
    assert mamba["service"]["speculative_config"][
        "num_speculative_tokens_per_batch_size"
    ] == [[1, 1, 2], [2, 128, 1]]
    assert mamba["treatment"]["focused_block_count_oracle"] == [3, 2, 2, 2]
    assert mamba["quality"]["baseline_match_all"] is True
    assert mamba["decision"]["status"] == (
        "positive-screen-pending-replication"
    )
    assert hashlib.sha256(DYNAMIC_MAMBA_PATCH.read_bytes()).hexdigest() == (
        mamba["runtime"]["dynamic_mamba_allocation_patch_sha256"]
    )

    mamba_raw = MTP2_DYNAMIC_MAMBA_RAW / "bench"
    mamba_quality = load(mamba_raw / "sequential-quality.json")
    assert mamba_quality["pass_all"] is True
    assert mamba_quality["baseline_match_all"] is True
    mamba_single = load(mamba_raw / "single-p40-o128.json")
    mamba_single_rate = mamba_single["fresh_response_validity"][
        "headline_tok_s_after_ttft"
    ]
    close(
        mamba_single_rate,
        mamba["single_user"]["fresh_response_after_ttft_tok_s"],
    )
    assert mamba_single_rate >= mamba["single_user"]["gate_tok_s"]
    assert mamba_single["rows"][0]["usage"]["completion_tokens"] == 128
    assert mamba_single["rows"][0]["usage"]["prompt_tokens_details"][
        "cached_tokens"
    ] == 0
    mamba_c2 = load(mamba_raw / "excluded-c2-crash-canary.json")
    mamba_transition = load(mamba_raw / "excluded-c64-transition.json")
    mamba_c64 = load(mamba_raw / "c64-screen.json")
    validate_output_isolation_batch(mamba_c2["batches"][0], 2)
    validate_output_isolation_batch(mamba_transition["batches"][0], 64)
    validate_output_isolation_batch(mamba_c64["batches"][0], 64)
    close(
        mamba_transition["batches"][0]["aggregate_tok_s_wall"],
        mamba["concurrency"]["excluded_transition_tok_s"],
    )
    mamba_c64_rate = mamba_c64["batches"][0]["aggregate_tok_s_wall"]
    close(mamba_c64_rate, mamba["concurrency"]["declared_c64_tok_s"])
    assert mamba_c64_rate >= mamba["concurrency"]["gate_tok_s"]
    mamba_inspect = load(MTP2_DYNAMIC_MAMBA_RAW / "docker-inspect-final.json")[0]
    assert mamba_inspect["Image"] == mamba["runtime"]["image_id"]
    assert mamba_inspect["Config"]["Labels"][
        "neural.download.vllm.dynamic-mamba-allocation.patch.sha256"
    ] == mamba["runtime"]["dynamic_mamba_allocation_patch_sha256"]
    mamba_log = (MTP2_DYNAMIC_MAMBA_RAW / "server-final.log").read_text(
        errors="replace"
    )
    assert mamba_log.count("Running: 64 reqs, Waiting: 0 reqs") >= 2
    assert mamba_log.count("GPU KV cache usage: 91.9%") >= 2
    assert not (mamba_raw / "c64-replication.json").exists()
    assert not (mamba_raw / "c64-quality-512.json").exists()
    assert "no value is interpolated or extrapolated" in mamba[
        "reporting_boundary"
    ]

    replication = load(MTP2_DYNAMIC_MAMBA_REPLICATION_SUMMARY)
    assert replication["classification"] == (
        "quality-qualified-replicated-service-profile"
    )
    assert replication["decision"]["status"] == (
        "promoted-measured-service-profile"
    )
    replication_single = load(
        MTP2_DYNAMIC_MAMBA_REPLICATION_RAW / "single-p40-o128.json"
    )
    replication_single_rate = replication_single["fresh_response_validity"][
        "headline_tok_s_after_ttft"
    ]
    close(replication_single_rate, replication["single_user"]["r5_tok_s_after_ttft"])
    assert replication_single_rate >= replication["single_user"]["gate_tok_s"]
    close(
        statistics.median([mamba_single_rate, replication_single_rate]),
        replication["single_user"]["median_tok_s_after_ttft"],
    )
    replication_c64 = load(
        MTP2_DYNAMIC_MAMBA_REPLICATION_RAW / "c64-screen.json"
    )
    validate_output_isolation_batch(replication_c64["batches"][0], 64)
    replication_c64_rate = replication_c64["batches"][0][
        "aggregate_tok_s_wall"
    ]
    close(replication_c64_rate, replication["replication"]["r5_c64_tok_s"])
    assert replication_c64_rate >= replication["replication"][
        "preregistered_floor_tok_s"
    ]
    close(
        statistics.median([mamba_c64_rate, replication_c64_rate]),
        replication["replication"]["median_c64_tok_s"],
    )
    replication_quality = load(
        MTP2_DYNAMIC_MAMBA_REPLICATION_RAW / "c64-quality-512.json"
    )
    assert replication_quality["total_requests"] == 512
    assert replication_quality["pass_all"] is True
    assert all(row["passed"] == 64 for row in replication_quality["results"])
    assert all(row["failed"] == 0 for row in replication_quality["results"])
    assert all(
        row["cached_tokens_nonzero"] == 0
        for row in replication_quality["results"]
    )
    replication_inspect = load(
        MTP2_DYNAMIC_MAMBA_REPLICATION_RAW / "docker-inspect-final.json"
    )[0]
    assert replication_inspect["Image"] == replication["runtime"]["image_id"]
    assert replication_inspect["State"]["ExitCode"] == 0
    assert replication_inspect["Config"]["Labels"][
        "neural.download.vllm.dynamic-mamba-allocation.patch.sha256"
    ] == replication["runtime"]["dynamic_mamba_allocation_patch_sha256"]
    assert "No unmeasured concurrency" in replication["reporting_boundary"]

    mtp3_screen = load(MTP3_DYNAMIC_SCREEN_SUMMARY)
    mtp3_replication = load(MTP3_DYNAMIC_REPLICATION_SUMMARY)
    assert mtp3_screen["classification"] == (
        "measured-positive-screen-pending-replication"
    )
    assert mtp3_screen["decision"]["status"] == (
        "positive-screen-pending-replication"
    )
    assert mtp3_replication["classification"] == (
        "replicated-quality-qualified-measured-service-profile"
    )
    assert mtp3_replication["decision"]["status"] == (
        "promote-dynamic-mtp3-at-one-mtp1-at-load"
    )
    assert mtp3_replication["service"]["speculative_config"] == {
        "method": "qwen3_next_mtp",
        "num_speculative_tokens": 3,
        "num_speculative_tokens_per_batch_size": [[1, 1, 3], [2, 128, 1]],
    }
    assert mtp3_replication["quality"]["concurrent_exact_answer_total"] == (
        "1024/1024"
    )
    mtp3_r6_single, mtp3_r6_c64 = validate_dynamic_attempt(
        MTP3_DYNAMIC_RAW,
        mtp3_replication["attempts"]["r6"]["single_user_tok_s"],
        mtp3_replication["attempts"]["r6"]["c64_aggregate_tok_s"],
        mtp3_replication["runtime"]["image_id"],
        3,
        False,
    )
    mtp3_r7_single, mtp3_r7_c64 = validate_dynamic_attempt(
        MTP3_DYNAMIC_REPLICATION_RAW,
        mtp3_replication["attempts"]["r7"]["single_user_tok_s"],
        mtp3_replication["attempts"]["r7"]["c64_aggregate_tok_s"],
        mtp3_replication["runtime"]["image_id"],
        3,
        True,
    )
    close(
        statistics.median([mtp3_r6_single, mtp3_r7_single]),
        mtp3_replication["promoted_medians"][
            "single_user_fresh_response_after_ttft_tok_s"
        ],
    )
    close(
        statistics.median([mtp3_r6_c64, mtp3_r7_c64]),
        mtp3_replication["promoted_medians"]["c64_aggregate_tok_s"],
    )
    close(
        mtp3_replication["promoted_medians"]["c64_aggregate_tok_s"] / 64,
        mtp3_replication["promoted_medians"]["c64_per_user_tok_s"],
    )
    assert "No intermediate concurrency" in mtp3_replication[
        "reporting_boundary"
    ]

    mtp4_screen = load(MTP4_DYNAMIC_SCREEN_SUMMARY)
    mtp4_replication = load(MTP4_DYNAMIC_REPLICATION_SUMMARY)
    assert mtp4_screen["classification"] == (
        "measured-positive-screen-pending-replication"
    )
    assert mtp4_screen["decision"]["status"] == (
        "positive-screen-pending-replication"
    )
    assert mtp4_replication["classification"] == (
        "replicated-quality-qualified-measured-service-profile"
    )
    assert mtp4_replication["decision"]["status"] == (
        "promote-dynamic-mtp4-at-one-mtp1-at-load"
    )
    assert mtp4_replication["service"]["speculative_config"] == {
        "method": "qwen3_next_mtp",
        "num_speculative_tokens": 4,
        "num_speculative_tokens_per_batch_size": [[1, 1, 4], [2, 128, 1]],
    }
    assert mtp4_replication["quality"]["concurrent_exact_answer_total"] == (
        "1024/1024"
    )
    mtp4_r8_single, mtp4_r8_c64 = validate_dynamic_attempt(
        MTP4_DYNAMIC_RAW,
        mtp4_replication["attempts"]["r8"]["single_user_tok_s"],
        mtp4_replication["attempts"]["r8"]["c64_aggregate_tok_s"],
        mtp4_replication["runtime"]["image_id"],
        4,
        False,
    )
    mtp4_r9_single, mtp4_r9_c64 = validate_dynamic_attempt(
        MTP4_DYNAMIC_REPLICATION_RAW,
        mtp4_replication["attempts"]["r9"]["single_user_tok_s"],
        mtp4_replication["attempts"]["r9"]["c64_aggregate_tok_s"],
        mtp4_replication["runtime"]["image_id"],
        4,
        False,
    )
    close(
        statistics.median([mtp4_r8_single, mtp4_r9_single]),
        mtp4_replication["promoted_medians"][
            "single_user_fresh_response_after_ttft_tok_s"
        ],
    )
    close(
        statistics.median([mtp4_r8_c64, mtp4_r9_c64]),
        mtp4_replication["promoted_medians"]["c64_aggregate_tok_s"],
    )
    close(
        mtp4_replication["promoted_medians"]["c64_aggregate_tok_s"] / 64,
        mtp4_replication["promoted_medians"]["c64_per_user_tok_s"],
    )
    for raw_dir in (MTP4_DYNAMIC_RAW, MTP4_DYNAMIC_REPLICATION_RAW):
        shutdown_log = (raw_dir / "server-final.log").read_text(
            errors="replace"
        )
        assert "workers still running after grace period" in shutdown_log
        assert "EngineDeadError" not in shutdown_log
    assert "No intermediate concurrency" in mtp4_replication[
        "reporting_boundary"
    ]

    mtp5_screen = load(MTP5_DYNAMIC_SCREEN_SUMMARY)
    mtp5_replication = load(MTP5_DYNAMIC_REPLICATION_SUMMARY)
    assert mtp5_screen["classification"] == (
        "measured-positive-screen-pending-replication"
    )
    assert mtp5_screen["decision"]["status"] == (
        "positive-screen-pending-replication"
    )
    assert mtp5_replication["classification"] == (
        "replicated-quality-qualified-measured-service-profile"
    )
    assert mtp5_replication["decision"]["status"] == (
        "promote-dynamic-mtp5-at-one-mtp1-at-load"
    )
    assert mtp5_replication["service"]["speculative_config"] == {
        "method": "qwen3_next_mtp",
        "num_speculative_tokens": 5,
        "num_speculative_tokens_per_batch_size": [[1, 1, 5], [2, 128, 1]],
    }
    assert mtp5_replication["quality"]["concurrent_exact_answer_total"] == (
        "1024/1024"
    )
    mtp5_r10_single, mtp5_r10_c64 = validate_dynamic_attempt(
        MTP5_DYNAMIC_RAW,
        mtp5_replication["attempts"]["r10"]["single_user_tok_s"],
        mtp5_replication["attempts"]["r10"]["c64_aggregate_tok_s"],
        mtp5_replication["runtime"]["image_id"],
        5,
        False,
    )
    mtp5_r11_single, mtp5_r11_c64 = validate_dynamic_attempt(
        MTP5_DYNAMIC_REPLICATION_RAW,
        mtp5_replication["attempts"]["r11"]["single_user_tok_s"],
        mtp5_replication["attempts"]["r11"]["c64_aggregate_tok_s"],
        mtp5_replication["runtime"]["image_id"],
        5,
        False,
    )
    close(
        statistics.median([mtp5_r10_single, mtp5_r11_single]),
        mtp5_replication["promoted_medians"][
            "single_user_fresh_response_after_ttft_tok_s"
        ],
    )
    close(
        statistics.median([mtp5_r10_c64, mtp5_r11_c64]),
        mtp5_replication["promoted_medians"]["c64_aggregate_tok_s"],
    )
    close(
        mtp5_replication["promoted_medians"]["c64_aggregate_tok_s"] / 64,
        mtp5_replication["promoted_medians"]["c64_per_user_tok_s"],
    )
    for raw_dir in (MTP5_DYNAMIC_RAW, MTP5_DYNAMIC_REPLICATION_RAW):
        shutdown_log = (raw_dir / "server-final.log").read_text(
            errors="replace"
        )
        assert "workers still running after grace period" in shutdown_log
        assert "EngineDeadError" not in shutdown_log
    assert "No intermediate concurrency" in mtp5_replication[
        "reporting_boundary"
    ]

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
        3,
        4,
        5,
    ]
    for point, expected, samples in zip(
        depth_profile["points"],
        (
            optimized_single_rate,
            mtp_single_rate,
            replication["single_user"]["median_tok_s_after_ttft"],
            mtp3_replication["promoted_medians"][
                "single_user_fresh_response_after_ttft_tok_s"
            ],
            mtp4_replication["promoted_medians"][
                "single_user_fresh_response_after_ttft_tok_s"
            ],
            mtp5_replication["promoted_medians"][
                "single_user_fresh_response_after_ttft_tok_s"
            ],
        ),
        (1, 1, 2, 2, 2, 2),
        strict=True,
    ):
        close(point["value"], expected)
        assert point["samples"] == samples

    dynamic_profile = next(
        profile
        for profile in package["performance_profiles"]
        if profile["id"]
        == "http-block-w8a16-dynamic-mtp-output-audited-aggregate-vs-concurrent-users"
    )
    assert [point["concurrent_sequences"] for point in dynamic_profile["points"]] == [
        1,
        64,
    ]
    close(
        dynamic_profile["points"][0]["value"],
        mtp5_replication["promoted_medians"][
            "single_user_fresh_response_after_ttft_tok_s"
        ],
    )
    close(
        dynamic_profile["points"][1]["value"],
        mtp5_replication["promoted_medians"]["c64_aggregate_tok_s"],
    )
    assert all(point["samples"] == 2 for point in dynamic_profile["points"])
    assert "no intermediate concurrency is claimed" in dynamic_profile[
        "scope"
    ]

    package_dependencies = set(package["dependencies"])
    for raw_dir in (MTP2_RAW, MTP2_MBT768_RAW):
        relative_quality = str(
            (raw_dir / "sequential-quality.json").relative_to(ROOT)
        )
        assert relative_quality in package_dependencies

    ladder = base_ladder
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
        "run-w8a16-mtp2-dynamic-mtp1-fixed-r2-server.sh",
        "bench-w8a16-mtp2-dynamic-mtp1-fixed-r2.sh",
        "run-w8a16-mtp2-dynamic-mtp1-fixed-r3-p192-server.sh",
        "bench-w8a16-mtp2-dynamic-mtp1-fixed-r3-p192.sh",
        "run-w8a16-mtp2-dynamic-mamba-r4-server.sh",
        "bench-w8a16-mtp2-dynamic-mamba-r4.sh",
        "run-w8a16-mtp2-dynamic-mamba-r5-server.sh",
        "bench-w8a16-mtp2-dynamic-mamba-r5.sh",
        "run-w8a16-mtp3-dynamic-mtp1-r6-server.sh",
        "bench-w8a16-mtp3-dynamic-mtp1-r6.sh",
        "run-w8a16-mtp3-dynamic-mtp1-r7-server.sh",
        "bench-w8a16-mtp3-dynamic-mtp1-r7.sh",
        "run-w8a16-mtp4-dynamic-mtp1-r8-server.sh",
        "bench-w8a16-mtp4-dynamic-mtp1-r8.sh",
        "run-w8a16-mtp4-dynamic-mtp1-r9-server.sh",
        "bench-w8a16-mtp4-dynamic-mtp1-r9.sh",
        "run-w8a16-mtp5-dynamic-mtp1-r10-server.sh",
        "bench-w8a16-mtp5-dynamic-mtp1-r10.sh",
        "run-w8a16-mtp5-dynamic-mtp1-r11-server.sh",
        "bench-w8a16-mtp5-dynamic-mtp1-r11.sh",
        "run-w8a16-dynamic-mtp-server.sh",
        "bench-w8a16-dynamic-mtp.sh",
        "build-w8a16-dynamic-mamba-image.sh",
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
                "mtp2_local_argmax_single_tok_s": local_single_rate,
                "mtp2_local_argmax_c64_tok_s": local_c64_rate,
                "mtp2_dynamic_single_tok_s": dynamic_single_rate,
                "mtp2_dynamic_c64_tok_s": dynamic_c64_rate,
                "mtp2_dynamic_fixed_single_tok_s": fixed_single_rate,
                "mtp2_dynamic_fixed_c64_tok_s": fixed_c64["batches"][0][
                    "aggregate_tok_s_wall"
                ],
                "mtp2_dynamic_p192_single_tok_s": p192_single_rate,
                "mtp2_dynamic_p192_c64_tok_s": None,
                "mtp2_dynamic_mamba_single_tok_s": mamba_single_rate,
                "mtp2_dynamic_mamba_c64_tok_s": mamba_c64_rate,
                "mtp2_dynamic_mamba_replication_single_tok_s": replication_single_rate,
                "mtp2_dynamic_mamba_replication_c64_tok_s": replication_c64_rate,
                "mtp3_dynamic_single_median_tok_s": mtp3_replication[
                    "promoted_medians"
                ]["single_user_fresh_response_after_ttft_tok_s"],
                "mtp3_dynamic_c64_median_tok_s": mtp3_replication[
                    "promoted_medians"
                ]["c64_aggregate_tok_s"],
                "mtp4_dynamic_single_median_tok_s": mtp4_replication[
                    "promoted_medians"
                ]["single_user_fresh_response_after_ttft_tok_s"],
                "mtp4_dynamic_c64_median_tok_s": mtp4_replication[
                    "promoted_medians"
                ]["c64_aggregate_tok_s"],
                "mtp5_dynamic_single_median_tok_s": mtp5_replication[
                    "promoted_medians"
                ]["single_user_fresh_response_after_ttft_tok_s"],
                "mtp5_dynamic_c64_median_tok_s": mtp5_replication[
                    "promoted_medians"
                ]["c64_aggregate_tok_s"],
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
