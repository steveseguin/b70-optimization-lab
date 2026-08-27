#!/usr/bin/env python3
"""Build a LocalMaxxing queue entry from a Gemma realistic-suite summary.

This helper intentionally refuses pre-final-gate/synthetic summaries. It emits
the policy markers enforced by scripts/submit_localmaxxing_results.py.
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
from pathlib import Path

from qualify_realistic_window_metrics import qualify, promotion_evidence_failures
from promotion_evidence import sha256_file, validate_promotion_attestation


def flag_value(args: list[str], name: str) -> str | None:
    try:
        return args[args.index(name) + 1]
    except (ValueError, IndexError):
        return None


def infer_stamp(summary: dict) -> str:
    for candidate in (str(summary.get("label", "")), str(summary.get("run_dir", ""))):
        match = re.search(r"20\d{6}T\d{4,6}Z?", candidate)
        if match:
            return match.group(0).replace("Z", "")
    return "20260627"


def median(values: list[float]) -> float:
    ordered = sorted(values)
    n = len(ordered)
    if n == 0:
        raise ValueError("empty list")
    mid = n // 2
    if n % 2:
        return float(ordered[mid])
    return float((ordered[mid - 1] + ordered[mid]) / 2.0)


def load_summary(path: Path) -> dict:
    summary = json.loads(path.read_text())
    bench_path = Path(str(summary.get("bench_path") or ""))
    if not bench_path.is_absolute():
        bench_path = path.parent / bench_path
    elif not bench_path.is_file():
        tracked_sibling = path.parent / bench_path.name
        if tracked_sibling.is_file():
            bench_path = tracked_sibling
    if not bench_path.is_file():
        raise SystemExit(f"{path}: benchmark JSON is missing: {bench_path}")
    summary["bench_path"] = str(bench_path)
    qualified_bench = qualify(json.loads(bench_path.read_text()))
    summary["bench_summary"] = qualified_bench["summary"]
    summary["realistic_final_gate"] = qualified_bench["realistic_final_gate"]
    summary["fresh_response_validity"] = qualified_bench[
        "fresh_response_validity"
    ]
    failures = promotion_evidence_failures(qualified_bench)
    if failures:
        raise SystemExit(
            f"{path}: not promotion eligible: {', '.join(failures)}"
        )
    gate = summary.get("realistic_final_gate") or {}
    validity = summary.get("fresh_response_validity") or {}
    if not gate.get("passed"):
        raise SystemExit(f"{path}: realistic_final_gate.passed is not true")
    if not gate.get("cached_tokens_all_zero"):
        raise SystemExit(f"{path}: cached_tokens_all_zero is not true")
    if validity.get("valid") is not True:
        raise SystemExit(f"{path}: fresh_response_validity.valid is not true")
    if (
        validity.get("preferred_metric_name")
        != "median_of_prompt_class_medians_tok_s_1_100_intervals_after_ttft"
    ):
        raise SystemExit(f"{path}: conventional interval metric is not preferred")
    if "class_balanced_tok_s_1_100_intervals_after_ttft" not in (
        summary.get("bench_summary") or {}
    ):
        raise SystemExit(f"{path}: class-balanced interval summary is missing")
    model_path = str(summary.get("model_path") or "")
    if "UD-Q8_K_XL" not in model_path:
        raise SystemExit(
            f"{path}: model_path is not the promoted UD-Q8_K_XL target/verifier "
            f"lane: {model_path}"
        )
    if summary.get("headline_eligible_for_gemma_q8") is not True:
        raise SystemExit(
            f"{path}: headline_eligible_for_gemma_q8 is not true; do not build "
            "a LocalMaxxing payload from alternate/lower-precision controls"
        )
    return summary


def infer_q8_vdr_from_launcher(launcher: dict) -> str | None:
    explicit = launcher.get("ggml_sycl_reorder_q8_0_vdr_mmvq")
    if explicit not in (None, "", "<unset>"):
        return str(explicit)

    server = str(launcher.get("llama_server") or "")
    if "q8reorder-vdr2" in server:
        return "2 (inferred from llama_server build path)"
    if "q8reorder-vdr4" in server:
        return "4 (inferred from llama_server build path)"
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("summary_json", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--label")
    parser.add_argument(
        "--promotion-attestation",
        type=Path,
        required=True,
        help=(
            "Hash-bound quality/determinism attestation for the exact benchmark "
            "referenced by the summary."
        ),
    )
    parser.add_argument(
        "--confirmation-summary",
        type=Path,
        action="append",
        default=[],
        help="Additional same-family realistic-suite summaries used as confirmation.",
    )
    args = parser.parse_args()

    summary = load_summary(args.summary_json)
    try:
        expected_runtime = str(
            (summary.get("launcher_identity") or {}).get("llama_cpp_commit")
            or ""
        )
        if not expected_runtime:
            raise SystemExit(
                f"{args.summary_json}: launcher identity lacks llama_cpp_commit"
            )
        attestation = validate_promotion_attestation(
            args.promotion_attestation,
            Path(summary["bench_path"]),
            expected_runtime_revision=expected_runtime,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(str(exc)) from exc
    confirmations = [load_summary(path) for path in args.confirmation_summary]

    bench = summary["bench_summary"]
    identity = summary["bench_run_identity"]
    launcher = summary["launcher_identity"]
    validity = summary["fresh_response_validity"]
    bench_json = Path(summary["bench_path"])
    bench_rows = json.loads(bench_json.read_text())["rows"]
    extra_args = shlex.split(launcher.get("extra_llama_args") or "")

    prompt_tokens = [float(row.get("prompt_tokens", 0)) for row in bench_rows]
    completion_tokens = [float(row.get("completion_tokens", 0)) for row in bench_rows]
    prompt_hashes = [row.get("prompt_sha256") for row in bench_rows]
    output_hashes = [row.get("sha256") for row in bench_rows]
    cached_tokens = [
        ((row.get("usage") or {}).get("prompt_tokens_details") or {}).get("cached_tokens")
        for row in bench_rows
    ]

    spec_enabled = "--spec-type" in extra_args
    n_max = flag_value(extra_args, "--spec-draft-n-max")
    n_min = flag_value(extra_args, "--spec-draft-n-min")
    p_min = flag_value(extra_args, "--spec-draft-p-min")
    ctx_checkpoints = flag_value(extra_args, "--ctx-checkpoints")

    stamp = infer_stamp(summary)
    label = args.label or (
        "gemma4-26b-a4b-q8-b70-llamacpp-realistic-mtp-"
        f"n{n_max or '0'}-nmin{n_min or '0'}-p{str(p_min or '0').replace('.', '')}-"
        f"ub{launcher.get('ubatch_size')}-{stamp}"
    )

    primary = bench["class_balanced_tok_s_1_100_intervals_after_ttft"]
    full = bench["tok_s_after_ttft_full"]
    wall = bench["tok_s_wall_full"]
    ttft = bench["ttft_ms"]
    confirmation_rows = []
    for item in confirmations:
        s = item["bench_summary"][
            "class_balanced_tok_s_1_100_intervals_after_ttft"
        ]
        f = item["bench_summary"]["tok_s_after_ttft_full"]
        w = item["bench_summary"]["tok_s_wall_full"]
        confirmation_rows.append(
            {
                "label": item.get("label"),
                "summaryJson": str(Path(item["run_dir"]) / "summary.json"),
                "medianTokS1To100AfterTtft": s["median"],
                "p10TokS1To100AfterTtft": s["p10"],
                "meanTokS1To100AfterTtft": s["mean"],
                "medianTokSFull512AfterTtft": f["median"],
                "medianWallTokSFull512": w["median"],
            }
        )

    engine_flags = {
        "apiMode": identity.get("api_mode"),
        "attentionBackend": "llama.cpp SYCL/Level Zero",
        "apiAttentionBackend": (
            "flash_attn" if launcher.get("flash_attn") == "on" else "sdpa"
        ),
        "apiKvCacheDtype": (
            "fp16"
            if launcher.get("cache_type_k") == "f16"
            and launcher.get("cache_type_v") == "f16"
            else "auto"
        ),
        "benchmarkJson": str(bench_json),
        "batchSize": int(launcher["batch_size"]),
        "ubatchSize": int(launcher["ubatch_size"]),
        "ctxSize": int(launcher["ctx_size"]),
        "concurrency": 1,
        "contextCheckpoints": int(ctx_checkpoints or 0),
        "commandSnippet": (
            f"LLAMA_SERVER={launcher.get('llama_server')} "
            f"GPU_INDEX={launcher.get('gpu_index')} PORT={launcher.get('port')} "
            f"LABEL={summary.get('label')} BATCH_SIZE={launcher.get('batch_size')} "
            f"UBATCH_SIZE={launcher.get('ubatch_size')} POLL={launcher.get('poll')} "
            "REALISTIC_GATE=1 REALISTIC_METRIC_TOKENS=100 "
            f"EXTRA_LLAMA_ARGS={shlex.quote(launcher.get('extra_llama_args') or '')} "
            "scripts/run-gemma4-26b-first-baseline.sh"
        ),
        "draftModelFile": Path(flag_value(extra_args, "--spec-draft-model") or "").name,
        "engineSummaryJson": str(args.summary_json),
        "extraArgs": launcher.get("extra_llama_args"),
        "flashAttention": launcher.get("flash_attn") == "on",
        "flashAttn": launcher.get("flash_attn") == "on",
        "freshResponseHeadlineValid": True,
        "freshResponseValidity": (
            "Fixed realistic prompt suite; each prompt sent once as a cold response; "
            "cached_tokens=0 for every request; no prompt/KV cache reuse, context "
            "checkpoints, response reuse, n-gram/history acceleration, or warmed "
            "repeated prompts; MTP draft tokens verified by the UD-Q8_K_XL target."
        ),
        "ggmlSyclDisableGraph": launcher.get("ggml_sycl_disable_graph"),
        "ggmlSyclDisableOpt": launcher.get("ggml_sycl_disable_opt"),
        "ggmlSyclEnableVmm": launcher.get("ggml_sycl_enable_vmm"),
        "ggmlSyclReorderQ8_0VdrMmvq": infer_q8_vdr_from_launcher(launcher),
        "gpuIndex": int(launcher["gpu_index"]),
        "headlineUse": "fresh-realistic-suite",
        "historyAccelerated": False,
        "kvCacheDtype": f"{launcher.get('cache_type_k')}/{launcher.get('cache_type_v')}",
        "llamaCppCommit": launcher.get("llama_cpp_commit"),
        "llamaServer": launcher.get("llama_server"),
        "llamaGemma4MoeReuseAttnRms": launcher.get("llama_gemma4_moe_reuse_attn_rms") == "1",
        "llamaGemma4FusedFinalPostNormResidual": (
            launcher.get("llama_gemma4_fused_final_post_norm_residual") == "1"
        ),
        "llamaGemma4FusedAttnPostNormResidual": (
            launcher.get("llama_gemma4_fused_attn_post_norm_residual") == "1"
        ),
        "llamaGemma4FusedPerLayerPostNormResidual": (
            launcher.get("llama_gemma4_fused_per_layer_post_norm_residual") == "1"
        ),
        "llamaGemma4MoeFusedBranchPostNormAdd": (
            launcher.get("llama_gemma4_moe_fused_branch_post_norm_add") == "1"
        ),
        "llamaGemma4MoeFusedDownWeightedSumReorderVdr2": (
            launcher.get("llama_gemma4_moe_fused_down_weighted_sum_reorder_vdr2") == "1"
        ),
        "llamaGemma4MoeSelectedSoftmax": launcher.get("llama_gemma4_moe_selected_softmax") == "1",
        "llamaGemma4MoeSelectedSoftmaxFused": launcher.get("llama_gemma4_moe_selected_softmax_fused") == "1",
        "llamaGemma4MoeWeightedSum": launcher.get("llama_gemma4_moe_weighted_sum") == "1",
        "llamaGemma4MtpFusedOutputArgmax": launcher.get("llama_gemma4_mtp_fused_output_argmax") == "1",
        "llamaGemma4MtpQonlyAttnInputs": launcher.get("llama_gemma4_mtp_qonly_attn_inputs") == "1",
        "llamaMtpDeferTargetHNextn": launcher.get("llama_mtp_defer_target_h_nextn") == "1",
        "llamaMtpDraftDirectArgmaxIds": launcher.get("llama_mtp_draft_direct_argmax_ids") == "1",
        "llamaMtpDraftDirectArgmaxUnroll": launcher.get("llama_mtp_draft_direct_argmax_unroll"),
        "llamaMtpDraftFastArgmax": launcher.get("llama_mtp_draft_fast_argmax") == "1",
        "llamaSpecVerifyBackendArgmaxIds": launcher.get("llama_spec_verify_backend_argmax_ids") == "1",
        "llamaSpecVerifyBulkSampledIds": launcher.get("llama_spec_verify_bulk_sampled_ids") == "1",
        "llamaSpecVerifyAcceptPrefixParity": launcher.get("llama_spec_verify_accept_prefix_parity") == "1",
        "llamaSyclF16P021SmallNcols": launcher.get("llama_sycl_f16_p021_small_ncols") == "1",
        "llamaSyclMulMatIdMultiTokenFast": launcher.get("llama_sycl_mul_mat_id_multi_token_fast") == "1",
        "llamaSyclMulMatIdQ8_0Reorder": launcher.get("llama_sycl_mul_mat_id_q8_0_reorder") == "1",
        "llamaSyclMulMatIdRouteCache": launcher.get("llama_sycl_mul_mat_id_route_cache") == "1",
        "llamaSyclQ8MmvqSmallNcols": launcher.get("llama_sycl_q8_mmvq_small_ncols") == "1",
        "llamaSyclQ8_0LmHead1ColDmmv": launcher.get("llama_sycl_q8_0_lm_head_1col_dmmv") == "1",
        "llamaSyclQ8_0LmHead1ColNoReorder": (
            launcher.get("llama_sycl_q8_0_lm_head_1col_no_reorder") == "1"
        ),
        "localmaxxingSubmissionAllowedUnderCurrentPolicy": True,
        "maxGeneratedTokens": identity.get("max_tokens"),
        "metricWindowGeneratedTokens": validity.get("primary_metric_tokens"),
        "metricWindowIntervals": validity.get("primary_metric_intervals"),
        "modelFile": Path(summary["model_path"]).name,
        "modelFileBytes": summary.get("model_file_bytes"),
        "mtpEnabled": spec_enabled,
        "oneapiDeviceSelector": launcher.get("oneapi_device_selector"),
        "outputSha256": output_hashes,
        "poll": int(launcher["poll"]),
        "prefixCaching": False,
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
        "realisticSuiteId": validity.get("suite_id"),
        "realisticSuitePath": identity.get("suite_path"),
        "realisticSuiteVersion": validity.get("suite_version"),
        "responseReuse": False,
        "serverLog": summary.get("server_log"),
        "specDecoding": spec_enabled,
        "specDraftModel": flag_value(extra_args, "--spec-draft-model"),
        "specDraftNMin": int(n_min) if n_min else None,
        "specDraftPMin": float(p_min) if p_min else None,
        "specMethod": flag_value(extra_args, "--spec-type"),
        "specNumTokens": int(n_max) if n_max else None,
        "summaryJson": str(args.summary_json),
        "supportingConfirmationRuns": confirmation_rows,
        "targetModelVerifiedAcceptedTokens": True,
        "temperature": 0,
        "tokenTimingSource": validity.get("token_timing_source"),
        "tokSFull512AfterTtftMean": full["mean"],
        "tokSFull512AfterTtftMedian": full["median"],
        "tokSFull512AfterTtftP10": full["p10"],
        "tokSOutMean": primary["mean"],
        "tokSOutMedian": primary["median"],
        "tokSOutP10": primary["p10"],
        "tokSOutStdev": primary.get("stdev"),
        "tokSTotalWallMean": wall["mean"],
        "tokSTotalWallMedian": wall["median"],
        "tokSTotalWallP10": wall["p10"],
        "ttftMsMean": ttft["mean"],
        "ttftMsMedian": ttft["median"],
        "ttftMsP10": ttft["p10"],
    }

    payload = {
        "hfId": "unsloth/gemma-4-26B-A4B-it-GGUF",
        "modelRevision": "gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf",
        "engineName": "llama.cpp",
        "engineVersion": f"{launcher.get('llama_cpp_commit')} local B70 SYCL/AOT Gemma patch stack",
        "backend": "xpu",
        "quantization": "Q8_K_XL",
        "hardware": {
            "hwClass": "DISCRETE_GPU",
            "gpuName": "Intel Arc Pro B70",
            "gpuCount": 1,
            "vramGb": 32,
            "cpu": "AMD Ryzen Threadripper PRO 5955WX 16-Cores",
            "ramGb": 128,
            "os": "Ubuntu 24.04.4 LTS",
        },
        "contextLength": int(launcher["ctx_size"]),
        "batchSize": 1,
        "promptTokens": median(prompt_tokens),
        "outputTokens": median(completion_tokens),
        "tokSOut": primary["median"],
        "tokSTotal": wall["median"],
        "ttftMs": ttft["median"],
        "engineFlags": engine_flags,
        "notes": (
            "Gemma 4 26B A4B Q8/INT8-quality single-B70 realistic-suite result. "
            "Primary metric is median generated-token throughput for tokens 1-100 "
            "after TTFT across the fixed cold prompt suite. Each prompt was sent "
            "exactly once; every request reported cached_tokens=0; context "
            "checkpoints, prompt/KV cache reuse, response reuse, n-gram/history "
            "acceleration, and warmed repeated prompts were disabled. Target and "
            "verifier are UD-Q8_K_XL; only the MTP draft is Q4_0, and accepted "
            "tokens are verified by the target model. Supporting confirmations are "
            "listed in engineFlags.supportingConfirmationRuns."
        ),
    }

    item = {"label": label, "payload": payload}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps([item], indent=2) + "\n")
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
