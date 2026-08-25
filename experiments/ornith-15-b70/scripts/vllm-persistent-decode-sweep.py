#!/usr/bin/env python3
"""Measure single-stream and aggregate decode in one persistent vLLM engine.

Every reported rate is calculated from observed tokens and timestamps.  The
script deliberately reports end-to-end output throughput separately from the
first-token-to-last-token decode window; it does not estimate or extrapolate
unmeasured points.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import statistics
import subprocess
import time
from pathlib import Path
from typing import Any


def parse_int_list(value: str) -> list[int]:
    values = [int(item) for item in value.split(",") if item.strip()]
    if not values or any(item < 1 for item in values):
        raise argparse.ArgumentTypeError("expected comma-separated positive integers")
    return values


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--batch-sizes", type=parse_int_list, default=[1, 2, 4, 8, 16, 32, 64])
    parser.add_argument("--input-tokens", type=int, default=128)
    parser.add_argument("--output-tokens", type=int, default=1024)
    parser.add_argument("--warmup-tokens", type=int, default=16)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--temperature", type=float, choices=(0.0, 1.0), default=0.0)
    parser.add_argument("--seed", type=int, default=20260824)
    parser.add_argument("--max-model-len", type=int, default=4096)
    parser.add_argument("--max-num-seqs", type=int, default=64)
    parser.add_argument("--max-num-batched-tokens", type=int, default=8192)
    parser.add_argument("--kv-cache-dtype", default="auto")
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.95)
    parser.add_argument("--tensor-parallel-size", type=int, default=1)
    parser.add_argument("--loader-threads", type=int, default=0)
    parser.add_argument("--speculative-tokens", type=int, default=0)
    parser.add_argument(
        "--speculative-model",
        help=(
            "optional local model view for the MTP drafter; the target model "
            "still supplies the tokenizer and main weights"
        ),
    )
    parser.add_argument("--graph", action="store_true")
    parser.add_argument("--quality-smoke", action="store_true")
    parser.add_argument(
        "--sequential-oracle",
        action="store_true",
        help=(
            "generate every distinct prompt alone and compare each batched "
            "request with that same-prompt token sequence"
        ),
    )
    parser.add_argument(
        "--record-token-ids",
        action="store_true",
        help="retain complete generated token arrays in the result JSON",
    )
    parser.add_argument(
        "--async-scheduling",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="explicitly enable/disable vLLM async scheduling; default is runtime auto",
    )
    parser.add_argument("--capture-sizes", type=parse_int_list, default=[1, 2, 4, 8, 16, 32, 64])
    args = parser.parse_args()
    if args.input_tokens + args.output_tokens > args.max_model_len:
        parser.error("input + output tokens exceed --max-model-len")
    if max(args.batch_sizes) > args.max_num_seqs:
        parser.error("a batch size exceeds --max-num-seqs")
    if (
        args.repeats < 1
        or args.warmup_tokens < 1
        or args.loader_threads < 0
        or args.speculative_tokens < 0
        or args.tensor_parallel_size < 1
    ):
        parser.error(
            "--repeats/--warmup-tokens must be positive and loader threads "
            "and speculative tokens nonnegative"
        )
    if args.speculative_model and not args.speculative_tokens:
        parser.error("--speculative-model requires --speculative-tokens")
    if args.speculative_model and not Path(args.speculative_model).is_dir():
        parser.error("--speculative-model must name an existing directory")
    return args


def git_head(path: str) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "-C", path, "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def git_diff_sha256(path: str) -> str | None:
    try:
        diff = subprocess.check_output(
            ["git", "-C", path, "diff", "--binary", "--no-ext-diff"],
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return hashlib.sha256(diff).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def xpu_runtime_files(package_file: str) -> list[dict[str, Any]]:
    package_dir = Path(package_file).resolve().parent
    patterns = (
        "_xpu_C*.so",
        "_moe_C*.so",
        "libgdn_attn_kernels*.so",
        "libgrouped_gemm*.so",
        "flash_attn_interface.py",
        "fused_moe_interface.py",
    )
    paths = sorted({path for pattern in patterns for path in package_dir.glob(pattern)})
    return [
        {
            "path": str(path),
            "size_bytes": path.stat().st_size,
            "sha256": file_sha256(path),
        }
        for path in paths
    ]


def speculative_model_view_identity(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    model_view = Path(path).resolve()
    index_path = model_view / "model.safetensors.index.json"
    manifest_path = model_view / "mtp-view-manifest.json"
    identity: dict[str, Any] = {
        "path": str(model_view),
        "index_sha256": file_sha256(index_path),
    }
    if manifest_path.is_file():
        identity["manifest_sha256"] = file_sha256(manifest_path)
        identity["manifest"] = json.loads(
            manifest_path.read_text(encoding="utf-8")
        )
    return identity


def make_prompt_token_ids(
    *, request_index: int, token_count: int, vocab_size: int, seed: int
) -> list[int]:
    # Deterministic, distinct prompts avoid prefix-cache artifacts.  Keeping IDs
    # away from vocabulary edges also avoids tokenizer-specific control tokens.
    usable = max(1, vocab_size - 2048)
    state = (seed ^ (request_index * 0x9E3779B1)) & 0xFFFFFFFF
    result: list[int] = []
    for _ in range(token_count):
        state = (1664525 * state + 1013904223) & 0xFFFFFFFF
        result.append(1024 + state % usable)
    return result


def token_digest(outputs: list[Any]) -> str:
    token_ids = [
        int(token)
        for request in outputs
        for completion in request.outputs
        for token in completion.token_ids
    ]
    return hashlib.sha256(",".join(map(str, token_ids)).encode()).hexdigest()


def request_token_digests(outputs: list[Any]) -> list[str]:
    return [
        hashlib.sha256(
            ",".join(map(str, request.outputs[0].token_ids)).encode()
        ).hexdigest()
        for request in outputs
    ]


def measure_arm(
    *,
    llm: Any,
    sampling_params_cls: Any,
    prompts: list[dict[str, list[int]]],
    batch_size: int,
    output_tokens: int,
    temperature: float,
    seed: int,
    repeat: int,
) -> tuple[dict[str, Any], list[list[int]]]:
    params = sampling_params_cls(
        temperature=temperature,
        max_tokens=output_tokens,
        min_tokens=output_tokens,
        ignore_eos=True,
        # Keep the seed fixed across repeats so output digests are a valid
        # determinism check.  `repeat` labels the timing sample only.
        seed=seed,
    )
    started = time.perf_counter()
    outputs = llm.generate(prompts[:batch_size], params, use_tqdm=False)
    elapsed_s = time.perf_counter() - started
    generated = sum(len(request.outputs[0].token_ids) for request in outputs)
    request_token_ids = [
        [int(token) for token in request.outputs[0].token_ids]
        for request in outputs
    ]

    first_token_ts = [request.metrics.first_token_ts for request in outputs]
    last_token_ts = [request.metrics.last_token_ts for request in outputs]
    timestamps_valid = all(first > 0 and last >= first for first, last in zip(first_token_ts, last_token_ts))
    decode_window_s = None
    aggregate_decode_tok_s = None
    per_request_decode_tok_s = None
    if timestamps_valid and output_tokens > 1:
        decode_window_s = max(last_token_ts) - min(first_token_ts)
        if decode_window_s > 0:
            aggregate_decode_tok_s = (generated - len(outputs)) / decode_window_s
        request_rates = [
            (len(request.outputs[0].token_ids) - 1) / (last - first)
            for request, first, last in zip(outputs, first_token_ts, last_token_ts)
            if last > first
        ]
        if request_rates:
            per_request_decode_tok_s = statistics.median(request_rates)

    arm = {
        "batch_size": batch_size,
        "repeat": repeat,
        "input_tokens_per_request": len(prompts[0]["prompt_token_ids"]),
        "requested_output_tokens_per_request": output_tokens,
        "generated_output_tokens": generated,
        "elapsed_s": elapsed_s,
        "end_to_end_output_tok_s": generated / elapsed_s,
        "decode_window_s": decode_window_s,
        "aggregate_decode_tok_s": aggregate_decode_tok_s,
        "median_per_request_decode_tok_s": per_request_decode_tok_s,
        "request_metrics_timestamps_valid": timestamps_valid,
        "token_ids_sha256": token_digest(outputs),
        "request_token_ids_sha256": request_token_digests(outputs),
    }
    return arm, request_token_ids


def compare_request_tokens(
    reference: list[list[int]], candidate: list[list[int]]
) -> dict[str, Any]:
    if len(reference) != len(candidate):
        raise ValueError("repeat request counts differ")
    first_mismatch_token_index: list[int | None] = []
    mismatch_token_counts: list[int] = []
    for expected, observed in zip(reference, candidate):
        shared = min(len(expected), len(observed))
        mismatch_positions = [
            index for index in range(shared) if expected[index] != observed[index]
        ]
        mismatch_count = len(mismatch_positions) + abs(len(expected) - len(observed))
        if mismatch_positions:
            first_mismatch = mismatch_positions[0]
        elif len(expected) != len(observed):
            first_mismatch = shared
        else:
            first_mismatch = None
        first_mismatch_token_index.append(first_mismatch)
        mismatch_token_counts.append(mismatch_count)
    return {
        "identical_requests": sum(count == 0 for count in mismatch_token_counts),
        "requests": len(reference),
        "first_mismatch_token_index": first_mismatch_token_index,
        "mismatch_token_counts": mismatch_token_counts,
    }


def oracle_entry(
    *, request_index: int, arm: dict[str, Any], request_token_ids: list[list[int]],
    record_token_ids: bool,
) -> dict[str, Any]:
    if len(request_token_ids) != 1:
        raise ValueError("a sequential oracle arm must contain exactly one request")
    entry = {
        "request_index": request_index,
        "generated_output_tokens": arm["generated_output_tokens"],
        "elapsed_s": arm["elapsed_s"],
        "decode_window_s": arm["decode_window_s"],
        "decode_tok_s": arm["median_per_request_decode_tok_s"],
        "token_ids_sha256": arm["request_token_ids_sha256"][0],
    }
    if record_token_ids:
        entry["token_ids"] = request_token_ids[0]
    return entry


def run_quality_smoke(
    *,
    llm: Any,
    tokenizer: Any,
    sampling_params_cls: Any,
    seed: int,
    batch_sizes: list[int],
) -> list[dict[str, Any]]:
    """Run deterministic, literal-answer canaries in the measured engine.

    These checks are intentionally small and are not a substitute for a full
    accuracy evaluation.  They detect gross generation regressions and retain
    the exact text/token identity needed for backend A/B comparison.
    """
    cases = [
        ("arithmetic", "Reply with only the integer: 17 * 23", "391"),
        ("prime", "Reply with only the integer: the first prime after 97", "101"),
        ("capital", "Reply with only the city: the capital of France", "Paris"),
        (
            "json",
            'Reply with only this compact JSON object: key "ok", boolean true',
            '{"ok":true}',
        ),
    ]
    prompts: list[str] = []
    for _, question, _ in cases:
        messages = [{"role": "user", "content": question}]
        prompts.append(
            tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            )
        )
    params = sampling_params_cls(
        temperature=0.0,
        max_tokens=32,
        seed=seed,
    )
    smoke: list[dict[str, Any]] = []
    invocation = 0
    for batch_size in batch_sizes:
        case_groups = (
            [[case_index] for case_index in range(len(cases))]
            if batch_size == 1
            else [[index % len(cases) for index in range(batch_size)]]
        )
        for case_indices in case_groups:
            outputs = llm.generate(
                [prompts[index] for index in case_indices], params, use_tqdm=False
            )
            for request_index, (case_index, output) in enumerate(
                zip(case_indices, outputs)
            ):
                case_id, question, expected = cases[case_index]
                text = output.outputs[0].text.strip()
                compact = "".join(text.split())
                expected_compact = "".join(expected.split())
                token_ids = [int(token) for token in output.outputs[0].token_ids]
                smoke.append(
                    {
                        "batch_size": len(case_indices),
                        "invocation": invocation,
                        "request_index": request_index,
                        "case_id": case_id,
                        "question": question,
                        "expected": expected,
                        "text": text,
                        "literal_match": (
                            expected_compact.casefold() in compact.casefold()
                        ),
                        "token_ids": token_ids,
                        "token_ids_sha256": hashlib.sha256(
                            ",".join(map(str, token_ids)).encode()
                        ).hexdigest(),
                    }
                )
            invocation += 1
    return smoke


def write_result(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def resolve_speculative_method(model_path: str) -> str:
    """Resolve an in-checkpoint MTP implementation without guessing."""
    config_path = Path(model_path) / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    text_config = config.get("text_config") or {}
    model_type = text_config.get("model_type") or config.get("model_type")
    if isinstance(model_type, str) and model_type.startswith("qwen3_5"):
        return "mtp"
    if isinstance(model_type, str) and model_type.startswith("qwen3_next"):
        return "mtp"
    raise ValueError(
        "--speculative-tokens requires a known in-checkpoint MTP model; "
        f"unsupported model_type={model_type!r}"
    )


def main() -> int:
    args = parse_args()
    output_path = Path(args.output)
    from vllm import LLM, SamplingParams
    import torch
    import vllm
    import vllm_xpu_kernels

    speculative_method = (
        resolve_speculative_method(args.model) if args.speculative_tokens else None
    )
    recorded_config = vars(args).copy()
    recorded_config["speculative_method"] = speculative_method
    result: dict[str, Any] = {
        "schema": "neural-download-vllm-decode-sweep-v1",
        "classification": "measured_no_extrapolation",
        "rate_definitions": {
            "end_to_end_output_tok_s": "all generated tokens / observed wall time; includes prefill",
            "aggregate_decode_tok_s": "all tokens after each request's first / observed earliest-first to latest-last monotonic window",
            "median_per_request_decode_tok_s": "median measured first-to-last-token rate across requests",
        },
        "token_comparison_definitions": {
            "repeat0_comparison": "same batch size and prompts versus the first measured repeat",
            "sequential_oracle_comparison": "each batched request versus the same prompt generated alone in the same engine",
        },
        "model": str(Path(args.model).resolve()),
        "config": recorded_config,
        "completed": False,
        "identity": {
            "hostname": platform.node(),
            "python": platform.python_version(),
            "torch": torch.__version__,
            "vllm": vllm.__version__,
            "vllm_xpu_kernels_file": vllm_xpu_kernels.__file__,
            "vllm_xpu_runtime_files": xpu_runtime_files(
                vllm_xpu_kernels.__file__
            ),
            "vllm_git_head": git_head("/home/steve/src/vllm"),
            "vllm_worktree_diff_sha256": git_diff_sha256("/home/steve/src/vllm"),
            "xpu_kernel_git_head": git_head("/home/steve/src/vllm-xpu-kernels"),
            "oneapi_device_selector": os.environ.get("ONEAPI_DEVICE_SELECTOR"),
            "vllm_xpu_enable_xpu_graph": os.environ.get("VLLM_XPU_ENABLE_XPU_GRAPH"),
            "vllm_xpu_inc_force_onednn_w4a16": os.environ.get(
                "VLLM_XPU_INC_FORCE_ONEDNN_W4A16"
            ),
            "vllm_xpu_moe_wna16_grouped": os.environ.get(
                "VLLM_XPU_MOE_WNA16_GROUPED"
            ),
            "vllm_xpu_onednn_int4_completion_barrier": os.environ.get(
                "VLLM_XPU_ONEDNN_INT4_COMPLETION_BARRIER"
            ),
            "vllm_xpu_onednn_int4_input_dependency": os.environ.get(
                "VLLM_XPU_ONEDNN_INT4_INPUT_DEPENDENCY"
            ),
            "vllm_xpu_onednn_int4_input_dependency_scope": os.environ.get(
                "VLLM_XPU_ONEDNN_INT4_INPUT_DEPENDENCY_SCOPE"
            ),
            "vllm_xpu_onednn_int4_determinism_pad": os.environ.get(
                "VLLM_XPU_ONEDNN_INT4_DETERMINISM_PAD"
            ),
            "vllm_xpu_gdn_replayssm_spec": os.environ.get(
                "VLLM_XPU_GDN_REPLAYSSM_SPEC"
            ),
            "vllm_qwen35_mtp_bf16_experts": os.environ.get(
                "VLLM_QWEN35_MTP_BF16_EXPERTS"
            ),
            "vllm_xpu_draft_lm_head_int4": os.environ.get(
                "VLLM_XPU_DRAFT_LM_HEAD_INT4"
            ),
            "vllm_xpu_draft_lm_head_int4_fallback_margin": os.environ.get(
                "VLLM_XPU_DRAFT_LM_HEAD_INT4_FALLBACK_MARGIN"
            ),
            "speculative_model_view": speculative_model_view_identity(
                args.speculative_model
            ),
            "ld_library_path": os.environ.get("LD_LIBRARY_PATH"),
        },
        "arms": [],
    }
    write_result(output_path, result)

    compilation_config: dict[str, Any] | None = None
    if args.graph:
        compilation_config = {
            "use_inductor_graph_partition": True,
            "cudagraph_mode": "PIECEWISE",
            "cudagraph_capture_sizes": args.capture_sizes,
            "max_cudagraph_capture_size": max(args.capture_sizes),
            # The optimization-level default enables an MLA-only fusion on
            # XPU, where its pass class is not imported.  This Qwen/GDN model
            # has no MLA path, so disable the irrelevant pass explicitly.
            "pass_config": {"fuse_rope_kvcache_cat_mla": False},
        }

    model_loader_extra_config: dict[str, Any] | None = None
    if args.loader_threads:
        model_loader_extra_config = {
            "enable_multithread_load": True,
            "num_threads": args.loader_threads,
        }

    speculative_config: dict[str, Any] | None = None
    if args.speculative_tokens:
        speculative_config = {
            "method": speculative_method,
            "num_speculative_tokens": args.speculative_tokens,
        }
        if args.speculative_model:
            speculative_config["model"] = str(
                Path(args.speculative_model).resolve()
            )

    optional_init_args: dict[str, Any] = {}
    if compilation_config is not None:
        optional_init_args["compilation_config"] = compilation_config
    if model_loader_extra_config is not None:
        optional_init_args["model_loader_extra_config"] = model_loader_extra_config
    if speculative_config is not None:
        optional_init_args["speculative_config"] = speculative_config
    if args.async_scheduling is not None:
        optional_init_args["async_scheduling"] = args.async_scheduling

    init_started = time.perf_counter()
    llm = LLM(
        model=args.model,
        tokenizer=args.model,
        trust_remote_code=True,
        dtype="float16",
        quantization="auto",
        tensor_parallel_size=args.tensor_parallel_size,
        max_model_len=args.max_model_len,
        max_num_seqs=args.max_num_seqs,
        max_num_batched_tokens=args.max_num_batched_tokens,
        kv_cache_dtype=args.kv_cache_dtype,
        gpu_memory_utilization=args.gpu_memory_utilization,
        enforce_eager=not args.graph,
        skip_mm_profiling=True,
        enable_prefix_caching=False,
        generation_config="vllm",
        disable_log_stats=False,
        **optional_init_args,
    )
    result["init_s"] = time.perf_counter() - init_started
    tokenizer = llm.get_tokenizer()
    vocab_size = int(getattr(tokenizer, "vocab_size", 0) or len(tokenizer))
    result["vocab_size"] = vocab_size
    prompts = [
        {
            "prompt_token_ids": make_prompt_token_ids(
                request_index=index,
                token_count=args.input_tokens,
                vocab_size=vocab_size,
                seed=args.seed,
            )
        }
        for index in range(max(args.batch_sizes))
    ]

    warmup_params = SamplingParams(
        temperature=args.temperature,
        max_tokens=args.warmup_tokens,
        min_tokens=args.warmup_tokens,
        ignore_eos=True,
        seed=args.seed - 1,
    )
    warmup_started = time.perf_counter()
    warmup_outputs = llm.generate(
        prompts[: max(args.batch_sizes)], warmup_params, use_tqdm=False
    )
    result["warmup"] = {
        "batch_size": max(args.batch_sizes),
        "tokens_per_request": args.warmup_tokens,
        "elapsed_s": time.perf_counter() - warmup_started,
        "token_ids_sha256": token_digest(warmup_outputs),
    }
    write_result(output_path, result)

    sequential_oracle_tokens: list[list[int]] | None = None
    if args.sequential_oracle:
        result["sequential_oracle"] = []
        sequential_oracle_tokens = []
        for request_index, prompt in enumerate(prompts):
            arm, request_token_ids = measure_arm(
                llm=llm,
                sampling_params_cls=SamplingParams,
                prompts=[prompt],
                batch_size=1,
                output_tokens=args.output_tokens,
                temperature=args.temperature,
                seed=args.seed,
                repeat=0,
            )
            sequential_oracle_tokens.append(request_token_ids[0])
            result["sequential_oracle"].append(
                oracle_entry(
                    request_index=request_index,
                    arm=arm,
                    request_token_ids=request_token_ids,
                    record_token_ids=args.record_token_ids,
                )
            )
            write_result(output_path, result)

    if args.quality_smoke:
        quality_batch_sizes = (
            sorted(set(args.capture_sizes))
            if args.graph
            else sorted({1, max(args.batch_sizes)})
        )
        result["quality_smoke"] = run_quality_smoke(
            llm=llm,
            tokenizer=tokenizer,
            sampling_params_cls=SamplingParams,
            seed=args.seed,
            batch_sizes=quality_batch_sizes,
        )
        write_result(output_path, result)
        print(json.dumps({"quality_smoke": result["quality_smoke"]}, sort_keys=True), flush=True)

    repeat0_tokens: dict[int, list[list[int]]] = {}
    for batch_size in args.batch_sizes:
        for repeat in range(args.repeats):
            arm, request_token_ids = measure_arm(
                llm=llm,
                sampling_params_cls=SamplingParams,
                prompts=prompts,
                batch_size=batch_size,
                output_tokens=args.output_tokens,
                temperature=args.temperature,
                seed=args.seed,
                repeat=repeat,
            )
            if repeat == 0:
                repeat0_tokens[batch_size] = request_token_ids
            else:
                arm["repeat0_comparison"] = compare_request_tokens(
                    repeat0_tokens[batch_size], request_token_ids
                )
            if sequential_oracle_tokens is not None:
                arm["sequential_oracle_comparison"] = compare_request_tokens(
                    sequential_oracle_tokens[:batch_size], request_token_ids
                )
            if args.record_token_ids:
                arm["request_token_ids"] = request_token_ids
            result["arms"].append(arm)
            write_result(output_path, result)
            print(json.dumps(arm, sort_keys=True), flush=True)

    result["completed"] = True
    write_result(output_path, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
