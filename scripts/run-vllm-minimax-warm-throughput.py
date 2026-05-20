#!/usr/bin/env python3
"""Warm-repeat MiniMax throughput probe.

This is a measurement tool, not a replacement for the strict quality gate. It
keeps one vLLM engine alive across repeats so we can separate decode/runtime
variance from repeated 112 GiB model reloads and process teardown noise.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import sys
import time
from pathlib import Path


def prepend_env_path(name: str, value: str) -> None:
    current = os.environ.get(name, "")
    parts = [part for part in current.split(":") if part]
    if value not in parts:
        os.environ[name] = ":".join([value, *parts])
    if name == "PYTHONPATH" and value not in sys.path:
        sys.path.insert(0, value)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model",
        default="/mnt/fast-ai/llm-models/minimax-m2.7-int4-autoround",
    )
    parser.add_argument("--out", required=True)
    parser.add_argument("--tensor-parallel-size", type=int, default=4)
    parser.add_argument("--dtype", default="float16")
    parser.add_argument("--max-model-len", type=int, default=2048)
    parser.add_argument("--max-num-batched-tokens", type=int, default=512)
    parser.add_argument("--max-num-seqs", type=int, default=1)
    parser.add_argument("--block-size", type=int, default=256)
    parser.add_argument("--input-len", type=int, default=512)
    parser.add_argument("--output-len", type=int, default=1536)
    parser.add_argument("--num-prompts", type=int, default=1)
    parser.add_argument("--warmup-repeats", type=int, default=1)
    parser.add_argument("--repeats", type=int, default=4)
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument("--top-p", type=float, default=1.0)
    parser.add_argument("--top-k", type=int, default=-1)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--prompt-seed",
        type=int,
        default=20260520,
        help="Seed used for deterministic synthetic prompt token ids.",
    )
    parser.add_argument(
        "--prompt-mode",
        choices=("repeat", "offset"),
        default="offset",
        help="repeat uses a short repeated token period; offset mimics vLLM random dataset shape.",
    )
    parser.add_argument("--repeat-period", type=int, default=16)
    parser.add_argument("--disable-detokenize", action="store_true")
    parser.add_argument("--enable-prefix-caching", action="store_true")
    parser.add_argument("--disable-chunked-prefill", action="store_true")
    parser.add_argument("--enforce-eager", action="store_true")
    parser.add_argument("--async-scheduling", choices=("default", "on", "off"), default="default")
    parser.add_argument("--attention-backend", default=None)
    parser.add_argument("--gpu-memory-utilization", type=float, default=None)
    parser.add_argument("--compilation-config-json", default=None)
    parser.add_argument("--llm-scaler-kernels", default=os.environ.get("LLM_SCALER_KERNELS"))
    return parser.parse_args()


def build_prompts(args: argparse.Namespace) -> list[dict[str, list[int]]]:
    prompts = []
    base_token = 1000 + (args.prompt_seed % 1000)
    for prompt_idx in range(args.num_prompts):
        if args.prompt_mode == "repeat":
            period = max(1, args.repeat_period)
            row = [base_token + (i % period) for i in range(args.input_len)]
        else:
            offset = base_token + (prompt_idx * 997)
            row = [offset + i for i in range(args.input_len)]
        prompts.append({"prompt_token_ids": row})
    return prompts


def token_hash(outputs) -> str:
    token_ids = []
    for request in outputs:
        token_ids.extend(request.outputs[0].token_ids)
        token_ids.append(-1)
    return hashlib.sha256(",".join(map(str, token_ids)).encode()).hexdigest()


def main() -> None:
    args = parse_args()
    if args.llm_scaler_kernels:
        prepend_env_path("PYTHONPATH", args.llm_scaler_kernels)

    from vllm import LLM, SamplingParams

    compilation_config = {"compile_sizes": [1]}
    if args.compilation_config_json:
        compilation_override = json.loads(args.compilation_config_json)
        if not isinstance(compilation_override, dict):
            raise SystemExit("--compilation-config-json must be a JSON object")
        compilation_config.update(compilation_override)

    llm_kwargs = {}
    if args.async_scheduling != "default":
        llm_kwargs["async_scheduling"] = args.async_scheduling == "on"
    if args.gpu_memory_utilization is not None:
        llm_kwargs["gpu_memory_utilization"] = args.gpu_memory_utilization

    init_start = time.perf_counter()
    llm = LLM(
        model=args.model,
        tokenizer=args.model,
        trust_remote_code=True,
        dtype=args.dtype,
        tensor_parallel_size=args.tensor_parallel_size,
        distributed_executor_backend="mp",
        max_model_len=args.max_model_len,
        max_num_batched_tokens=args.max_num_batched_tokens,
        max_num_seqs=args.max_num_seqs,
        block_size=args.block_size,
        enforce_eager=args.enforce_eager,
        disable_custom_all_reduce=False,
        enable_chunked_prefill=not args.disable_chunked_prefill,
        enable_prefix_caching=args.enable_prefix_caching,
        compilation_config=compilation_config,
        attention_backend=args.attention_backend,
        **llm_kwargs,
    )
    init_elapsed = time.perf_counter() - init_start

    sampling_params = SamplingParams(
        temperature=args.temperature,
        top_p=args.top_p,
        top_k=args.top_k,
        max_tokens=args.output_len,
        seed=args.seed,
        ignore_eos=True,
        detokenize=not args.disable_detokenize,
    )
    prompts = build_prompts(args)

    warmup_records = []
    for i in range(args.warmup_repeats):
        started = time.perf_counter()
        outputs = llm.generate(prompts, sampling_params, use_tqdm=False)
        elapsed = time.perf_counter() - started
        warmup_records.append(
            {
                "repeat": i,
                "elapsed_s": elapsed,
                "output_tokens": sum(len(out.outputs[0].token_ids) for out in outputs),
                "token_sha256": token_hash(outputs),
            }
        )

    records = []
    for i in range(args.repeats):
        started = time.perf_counter()
        outputs = llm.generate(prompts, sampling_params, use_tqdm=False)
        elapsed = time.perf_counter() - started
        output_tokens = sum(len(out.outputs[0].token_ids) for out in outputs)
        prompt_tokens = args.input_len * args.num_prompts
        records.append(
            {
                "repeat": i,
                "elapsed_s": elapsed,
                "prompt_tokens": prompt_tokens,
                "output_tokens": output_tokens,
                "total_tokens": prompt_tokens + output_tokens,
                "output_toks_per_second": output_tokens / elapsed,
                "total_toks_per_second": (prompt_tokens + output_tokens) / elapsed,
                "token_sha256": token_hash(outputs),
            }
        )

    output_tps = [record["output_toks_per_second"] for record in records]
    total_tps = [record["total_toks_per_second"] for record in records]
    result = {
        "model": args.model,
        "engine": "vllm",
        "tensor_parallel_size": args.tensor_parallel_size,
        "dtype": args.dtype,
        "max_model_len": args.max_model_len,
        "max_num_batched_tokens": args.max_num_batched_tokens,
        "max_num_seqs": args.max_num_seqs,
        "block_size": args.block_size,
        "input_len": args.input_len,
        "output_len": args.output_len,
        "num_prompts": args.num_prompts,
        "temperature": args.temperature,
        "top_p": args.top_p,
        "top_k": args.top_k,
        "prompt_mode": args.prompt_mode,
        "prompt_seed": args.prompt_seed,
        "init_elapsed_s": init_elapsed,
        "warmup_repeats": warmup_records,
        "repeats": records,
        "mean_output_toks_per_second": statistics.fmean(output_tps),
        "mean_total_toks_per_second": statistics.fmean(total_tps),
        "min_output_toks_per_second": min(output_tps),
        "max_output_toks_per_second": max(output_tps),
        "stdev_output_toks_per_second": (
            statistics.stdev(output_tps) if len(output_tps) > 1 else 0.0
        ),
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
