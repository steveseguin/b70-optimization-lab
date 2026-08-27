#!/usr/bin/env python3
"""Build a guarded LocalMaxxing queue entry for rapid model snapshots."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

from qualify_realistic_window_metrics import qualify, promotion_evidence_failures
from promotion_evidence import sha256_file, validate_promotion_attestation


def parse_identity(path: Path | None) -> dict[str, str]:
    if path is None or not path.exists():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text().splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip()
    return out


def median(values: list[float]) -> float:
    return float(statistics.median(values))


def rounded_median_int(values: list[float]) -> int:
    return int(round(statistics.median(values)))


def load_strict_bench(path: Path) -> dict:
    bench = qualify(json.loads(path.read_text()))
    failures = promotion_evidence_failures(bench)
    if failures:
        raise SystemExit(
            f"{path}: not promotion eligible: {', '.join(failures)}"
        )
    gate = bench.get("realistic_final_gate") or {}
    fresh = bench.get("fresh_response_validity") or {}
    if gate.get("passed") is not True:
        raise SystemExit(f"{path}: realistic_final_gate.passed is not true")
    if gate.get("cached_tokens_all_zero") is not True:
        raise SystemExit(f"{path}: cached_tokens_all_zero is not true")
    if fresh.get("valid") is not True:
        raise SystemExit(f"{path}: fresh_response_validity.valid is not true")
    if (
        fresh.get("preferred_metric_name")
        != "median_of_prompt_class_medians_tok_s_1_100_intervals_after_ttft"
    ):
        raise SystemExit(
            f"{path}: preferred metric is not the conventional interval field"
        )
    if "class_balanced_tok_s_1_100_intervals_after_ttft" not in (
        bench.get("summary") or {}
    ):
        raise SystemExit(f"{path}: class-balanced interval summary is missing")
    return bench


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bench_json", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--hf-id", required=True)
    parser.add_argument("--model-revision", required=True)
    parser.add_argument("--engine-name", required=True)
    parser.add_argument("--engine-version", required=True)
    parser.add_argument("--quantization", required=True)
    parser.add_argument("--context-length", type=int, required=True)
    parser.add_argument("--gpu-count", type=int, default=1)
    parser.add_argument("--identity-env", type=Path)
    parser.add_argument("--result-packet", default="")
    parser.add_argument("--notes", required=True)
    parser.add_argument(
        "--promotion-attestation",
        type=Path,
        required=True,
        help=(
            "Hash-bound quality/determinism attestation for this exact "
            "performance evidence and model/runtime identity."
        ),
    )
    args = parser.parse_args()

    bench = load_strict_bench(args.bench_json)
    try:
        attestation = validate_promotion_attestation(
            args.promotion_attestation,
            args.bench_json,
            expected_model_revision=args.model_revision,
            expected_runtime_revision=args.engine_version,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(str(exc)) from exc
    identity = parse_identity(args.identity_env)
    rows = bench["rows"]
    summary = bench["summary"]
    primary = summary["class_balanced_tok_s_1_100_intervals_after_ttft"]
    full = summary["tok_s_after_ttft_full"]
    wall = summary["tok_s_wall_full"]
    ttft = summary["ttft_ms"]
    fresh = bench["fresh_response_validity"]
    run_identity = bench.get("run_identity") or {}

    prompt_tokens = [float(row.get("prompt_tokens", 0)) for row in rows]
    completion_tokens = [float(row.get("completion_tokens", 0)) for row in rows]
    prompt_hashes = [row.get("prompt_sha256") for row in rows]
    output_hashes = [row.get("sha256") for row in rows]
    cached_tokens = [row.get("cached_tokens") for row in rows]

    engine_flags = {
        "apiMode": bench.get("api_mode") or run_identity.get("api_mode"),
        "attentionBackend": identity.get("llama_server") and "llama.cpp SYCL/Level Zero"
        or "vLLM XPU",
        "benchmarkJson": str(args.bench_json),
        "commandIdentityEnv": str(args.identity_env) if args.identity_env else None,
        "contextCheckpoints": 0,
        "engineSummaryJson": identity.get("summary_out"),
        "freshResponseHeadlineValid": True,
        "freshResponseValidity": (
            "Fixed realistic prompt suite; each prompt sent once as a cold response; "
            "cached_tokens=0 for every request; no prompt/KV cache reuse, context "
            "checkpoints, response reuse, n-gram/history acceleration, or warmed "
            "repeated prompts."
        ),
        "githubResultPacket": args.result_packet,
        "headlineUse": "fresh-realistic-suite",
        "historyAccelerated": False,
        "responseReuse": False,
        "prefixCaching": False,
        "localmaxxingSubmissionAllowedUnderCurrentPolicy": True,
        "metricWindowGeneratedTokens": fresh.get("primary_metric_tokens"),
        "metricWindowIntervals": fresh.get("primary_metric_intervals"),
        "modelPath": identity.get("model") or identity.get("model_dir") or identity.get("MODEL_DIR"),
        "outputSha256": output_hashes,
        "outputTokens": completion_tokens,
        "primaryMetricName": (
            "median_of_prompt_class_medians_tok_s_1_100_intervals_after_ttft"
        ),
        "primaryMetricAggregation": "median-of-prompt-class-medians",
        "promotionAttestation": str(args.promotion_attestation),
        "promotionAttestationSha256": sha256_file(args.promotion_attestation),
        "promotionIdentity": attestation["identity"],
        "primaryMetricAccounting": "inter-token-intervals",
        "promptSha256": prompt_hashes,
        "promptTokens": prompt_tokens,
        "realisticSuiteCachedTokens": cached_tokens,
        "realisticSuiteCachedTokensAllZero": True,
        "realisticSuiteGatePassed": True,
        "realisticSuiteId": fresh.get("suite_id"),
        "realisticSuitePath": (
            fresh.get("suite_path")
            or run_identity.get("suite_path")
            or identity.get("suite")
        ),
        "realisticSuiteVersion": fresh.get("suite_version"),
        "temperature": 0,
        "tokenTimingSource": fresh.get("token_timing_source"),
        "tokSOutMedian": primary["median"],
        "tokSOutP10": primary["p10"],
        "tokSOutMean": primary["mean"],
        "tokSOutStdev": primary.get("stdev"),
        "tokSFullAfterTtftMedian": full["median"],
        "tokSFullAfterTtftP10": full["p10"],
        "tokSFullAfterTtftMean": full["mean"],
        "tokSTotalWallMedian": wall["median"],
        "tokSTotalWallP10": wall["p10"],
        "tokSTotalWallMean": wall["mean"],
        "ttftMsMedian": ttft["median"],
        "ttftMsP10": ttft["p10"],
        "ttftMsMean": ttft["mean"],
    }

    if identity.get("llama_server"):
        model_path = identity.get("model", "<model>")
        ctx_size = identity.get("ctx_size", str(args.context_length))
        batch_size = identity.get("batch_size", "1024")
        ubatch_size = identity.get("ubatch_size", "256")
        flash_attn = identity.get("flash_attn", "on")
        n_parallel = identity.get("n_parallel", "1")
        cache_k = identity.get("cache_type_k", "f16")
        cache_v = identity.get("cache_type_v", "f16")
        engine_flags.update({
            "commandSnippet": (
                f"llama-server -m {model_path} -c {ctx_size} -ngl 99 "
                f"-b {batch_size} -ub {ubatch_size} -fa {flash_attn} "
                "--ctx-checkpoints 0 --jinja --reasoning off"
            ),
            "gpuLayers": 99,
            "kvCacheDtype": f"K={cache_k} V={cache_v}",
            "apiKvCacheDtype": (
                "fp16"
                if cache_k == "f16" and cache_v == "f16"
                else cache_k
                if cache_k == cache_v and cache_k in {"q8_0", "q4_0", "fp8"}
                else "auto"
            ),
            "flashAttn": flash_attn == "on",
            "apiAttentionBackend": (
                "flash_attn" if flash_attn == "on" else "sdpa"
            ),
            "prefixCaching": False,
            "specDecoding": False,
            "concurrency": int(n_parallel),
            "temperature": 0.0,
            "topP": 1.0,
        })
    elif identity.get("argv"):
        engine_flags["commandSnippet"] = identity["argv"]

    for key in (
        "gpu_index",
        "port",
        "ctx_size",
        "batch_size",
        "ubatch_size",
        "n_parallel",
        "flash_attn",
        "cache_type_k",
        "cache_type_v",
        "llama_server",
        "extra_llama_args",
        "max_model_len",
        "max_num_batched_tokens",
        "max_num_seqs",
        "gpu_memory_utilization",
        "tensor_parallel_size",
        "enable_xpu_graph",
        "compilation_config",
        "speculative_config",
        "vllm_extra_args",
        "vllm_commit",
        "kernel_commit",
        "xpu_graph",
        "vllm_xpu_enable_xpu_graph",
        "vllm_xpu_force_graph_with_comm",
        "vllm_xpu_graph_noop_comm_capture",
        "vllm_xpu_v4_direct_fp8_attn",
        "vllm_xpu_v4_split_fp8_attn",
        "vllm_xpu_v4_split_fp8_block_h",
        "vllm_xpu_v4_split_fp8_qk_num_warps",
        "vllm_xpu_v4_split_fp8_pv_num_warps",
        "vllm_xpu_v4_fp8_wo_a",
        "vllm_xpu_v4_inplace_allreduce",
        "vllm_xpu_v4_mhc_norm_fusion",
        "vllm_xpu_v4_tp4_ring_mhc_post",
        "vllm_xpu_v4_tp4_ring_mhc_post_pre",
        "vllm_xpu_v4_mhc_pre_m1_single_kernel",
        "vllm_xpu_v4_mhc_post_pre_m1_single_kernel",
        "vllm_xpu_v4_shared_expert_fused_act_quant",
        "vllm_xpu_v4_shared_expert_fused_act_quant_max_m",
        "vllm_xpu_v4_m2_routed_clamp_silu",
        "vllm_xpu_v4_m1_biased_topk",
        "vllm_xpu_v4_m1_router_norm",
        "vllm_xpu_v4_m1_direct_routed_moe",
        "vllm_xpu_v4_compressor_m2_row_exact",
        "vllm_xpu_v4_compressor_m2_batched_exact",
        "vllm_xpu_v4_block_fp8_w8a16",
        "vllm_xpu_v4_block_fp8_w8a16_max_m",
        "vllm_xpu_v4_block_fp8_w8a16_shapes",
        "vllm_xpu_mxfp4_small_m_n",
        "vllm_xpu_log_fp8_linear_shapes",
        "vllm_xpu_native_mhc",
        "pipeline_parallel_size",
        "data_parallel_size",
        "data_parallel_size_local",
        "kv_cache_dtype",
        "ccl_sycl_allreduce_ll",
        "ccl_sycl_allreduce_ll_threshold",
        "ccl_sycl_allreduce_arc",
    ):
        if key in identity:
            engine_flags[key] = identity[key]

    payload = {
        "hfId": args.hf_id,
        "modelRevision": args.model_revision,
        "engineName": args.engine_name,
        "engineVersion": args.engine_version,
        "backend": "xpu",
        "quantization": args.quantization,
        "hardware": {
            "hwClass": "DISCRETE_GPU",
            "gpuName": "Intel Arc Pro B70",
            "gpuCount": args.gpu_count,
            "vramGb": 32,
            "cpu": "AMD Ryzen Threadripper PRO 5955WX 16-Cores",
            "ramGb": 128,
            "os": "Ubuntu 24.04.4 LTS",
        },
        "contextLength": args.context_length,
        "batchSize": 1,
        "promptTokens": rounded_median_int(prompt_tokens),
        "outputTokens": rounded_median_int(completion_tokens),
        "tokSOut": primary["median"],
        "tokSTotal": wall["median"],
        "ttftMs": ttft["median"],
        "engineFlags": engine_flags,
        "notes": args.notes,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps([{"label": args.label, "payload": payload}], indent=2) + "\n")
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
