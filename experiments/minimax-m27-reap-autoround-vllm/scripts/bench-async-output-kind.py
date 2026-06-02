#!/usr/bin/env python3
"""Compare vLLM async-engine throughput across RequestOutputKind modes."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any

from vllm import SamplingParams
from vllm.benchmarks.datasets import RandomDataset
from vllm.engine.arg_utils import AsyncEngineArgs
from vllm.entrypoints.openai.api_server import build_async_engine_client_from_engine_args
from vllm.inputs import TextPrompt
from vllm.sampling_params import RequestOutputKind
from vllm.tokenizers import get_tokenizer


SELECTED_ENV_NAMES = [
    "VLLM_CACHE_ROOT",
    "VLLM_MINIMAX_QK_RMS_XPU_HELPER",
    "VLLM_MINIMAX_QK_RMS_XPU_HELPER_MAX_TOKENS",
    "VLLM_MINIMAX_QK_RMS_DIRECT_INPLACE_SCALE",
    "VLLM_MINIMAX_QK_RMS_APPLY_TP_SCALE",
    "VLLM_MINIMAX_QK_NORM_RESTORE_WEIGHT",
    "VLLM_MINIMAX_QK_NORM_RESTORE_WEIGHT_MIN_TOKENS",
    "VLLM_MINIMAX_QK_NORM_COMPILE_USE_PARAM",
    "VLLM_MINIMAX_QK_NORM_PRECAPTURE_SANITIZE",
    "VLLM_MINIMAX_QK_NORM_PRECAPTURE_USE_PARAM",
    "VLLM_MINIMAX_QK_RMS_POST_AR_APPLY_CUSTOM_OP",
    "VLLM_MINIMAX_QKV_NARROW_SPLIT",
    "VLLM_MINIMAX_M2_ATTN_DELAY_ALLREDUCE",
    "VLLM_MINIMAX_M2_FP16_ROUTER",
    "VLLM_MINIMAX_M2_FP16_ROUTER_AUDIT",
    "VLLM_XPU_USE_LLM_SCALER_MOE_MINIMAX_LOGITS_WS",
    "VLLM_XPU_STATIC_PIECEWISE_RANGE_ENTRY",
    "VLLM_XPU_SKIP_COMPILED_PREFILL",
    "VLLM_BENCH_TEMPERATURE",
    "CCL_IPC",
    "CCL_ZE_IPC_EXCHANGE",
    "CCL_TOPO_FABRIC_VERTEX_CONNECTION_CHECK",
]


def make_engine_args(args: argparse.Namespace) -> AsyncEngineArgs:
    return AsyncEngineArgs(
        model=args.model,
        tokenizer=args.model,
        trust_remote_code=True,
        dtype=args.dtype,
        tensor_parallel_size=args.tensor_parallel_size,
        distributed_executor_backend="mp",
        max_model_len=args.max_model_len,
        max_num_batched_tokens=args.max_num_batched_tokens,
        max_num_seqs=1,
        block_size=args.block_size,
        enable_prefix_caching=False,
        disable_log_stats=True,
        compilation_config={
            "use_inductor_graph_partition": True,
            "compile_sizes": [1],
            "cudagraph_mode": "PIECEWISE",
        },
    )


async def run_one(
    llm: Any,
    prompt: str,
    prompt_len: int,
    output_len: int,
    kind_name: str,
) -> dict[str, Any]:
    kind = getattr(RequestOutputKind, kind_name)
    sampling_params = SamplingParams(
        temperature=float(os.environ.get("VLLM_BENCH_TEMPERATURE", "0")),
        top_p=1.0,
        ignore_eos=True,
        max_tokens=output_len,
        output_kind=kind,
    )
    chunks = 0
    output_tokens = 0
    first_s = None
    start = time.perf_counter()
    generator = llm.generate(
        TextPrompt(prompt=prompt),
        sampling_params,
        request_id=f"output-kind-{kind_name.lower()}-{time.time_ns()}",
    )
    async for result in generator:
        if first_s is None:
            first_s = time.perf_counter() - start
        chunks += 1
        if result.outputs:
            chunk_tokens = len(result.outputs[0].token_ids)
            if kind is RequestOutputKind.DELTA:
                output_tokens += chunk_tokens
            else:
                output_tokens = max(output_tokens, chunk_tokens)
    elapsed = time.perf_counter() - start
    return {
        "output_kind": kind_name,
        "elapsed_s": elapsed,
        "ttft_s": first_s,
        "chunks": chunks,
        "prompt_tokens": prompt_len,
        "output_tokens": output_tokens,
        "tok_s_out_e2e": output_tokens / elapsed,
        "tok_s_total_e2e": (prompt_len + output_tokens) / elapsed,
    }


async def run(args: argparse.Namespace) -> dict[str, Any]:
    tokenizer = get_tokenizer(args.model, trust_remote_code=True)
    sample = RandomDataset(random_seed=args.seed).sample(
        tokenizer=tokenizer,
        num_requests=1,
        prefix_len=0,
        range_ratio=0.0,
        input_len=args.prompt_tokens,
        output_len=args.output_tokens,
    )[0]

    records: list[dict[str, Any]] = []
    async with build_async_engine_client_from_engine_args(make_engine_args(args)) as llm:
        if args.warmup_output_tokens > 0:
            warmup_params = SamplingParams(
                temperature=0,
                top_p=1.0,
                ignore_eos=True,
                max_tokens=args.warmup_output_tokens,
                output_kind=RequestOutputKind.FINAL_ONLY,
            )
            async for _ in llm.generate(
                TextPrompt(prompt=sample.prompt),
                warmup_params,
                request_id=f"output-kind-warmup-{time.time_ns()}",
            ):
                pass
        for kind_name in args.output_kinds:
            records.append(
                await run_one(
                    llm,
                    sample.prompt,
                    sample.prompt_len,
                    sample.expected_output_len,
                    kind_name,
                )
            )

    return {
        "created_at_unix": time.time(),
        "model": args.model,
        "prompt_tokens_requested": args.prompt_tokens,
        "output_tokens_requested": args.output_tokens,
        "seed": args.seed,
        "selected_env": {
            name: os.environ.get(name) for name in SELECTED_ENV_NAMES
        },
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="/mnt/fast-ai/llm-models/minimax-m2.7-reap-autoround-w4a16")
    parser.add_argument("--dtype", default="float16")
    parser.add_argument("--tensor-parallel-size", type=int, default=4)
    parser.add_argument("--max-model-len", type=int, default=2048)
    parser.add_argument("--max-num-batched-tokens", type=int, default=512)
    parser.add_argument("--block-size", type=int, default=256)
    parser.add_argument("--prompt-tokens", type=int, default=512)
    parser.add_argument("--output-tokens", type=int, default=1536)
    parser.add_argument("--warmup-output-tokens", type=int, default=32)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--output-kinds",
        nargs="+",
        choices=[kind.name for kind in RequestOutputKind],
        default=["FINAL_ONLY", "CUMULATIVE", "DELTA"],
    )
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    artifact = asyncio.run(run(args))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2) + "\n")
    print(json.dumps(artifact, indent=2))
    print(f"wrote={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
