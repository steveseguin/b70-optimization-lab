#!/usr/bin/env python3
"""Quality smoke for the async-engine MiniMax REAP benchmark path."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any


DEFAULT_PROMPTS = [
    (
        "You are a precise assistant. Answer in three short numbered points. "
        "Explain why tensor parallel inference can be communication-bound on "
        "four PCIe GPUs, and include one concrete mitigation that preserves "
        "model quality."
    ),
    (
        "A user asks whether speculative decoding can change answer quality. "
        "Give a concise, technically accurate answer and mention one validation "
        "step before publishing a benchmark."
    ),
    (
        "Write a short Python function named median_latency_ms that accepts a "
        "list of floating point seconds and returns the median in milliseconds. "
        "Include only the function."
    ),
]

SELECTED_ENV_NAMES = [
    "VLLM_CACHE_ROOT",
    "VLLM_XPU_USE_LLM_SCALER_MOE",
    "VLLM_XPU_USE_LLM_SCALER_MOE_WS",
    "VLLM_XPU_USE_LLM_SCALER_MOE_MINIMAX_LOGITS_WS",
    "VLLM_XPU_COMPILE_ALLREDUCE_CUSTOM_OP",
    "VLLM_XPU_CUSTOM_ALLREDUCE_CLONE_INPUT",
    "VLLM_MINIMAX_MOE_OUTPUT_ALLREDUCE_INSIDE_CUSTOM_OP",
    "VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP",
    "VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP_MAX_TOKENS",
    "VLLM_MINIMAX_M2_ATTN_DELAY_ALLREDUCE",
    "VLLM_MINIMAX_QK_RMS_XPU_HELPER",
    "VLLM_MINIMAX_QK_NORM_RESTORE_WEIGHT",
    "VLLM_XPU_SKIP_COMPILED_PREFILL",
    "CCL_ZE_IPC_EXCHANGE",
]


def prepend_env_path(name: str, value: str) -> None:
    current = os.environ.get(name, "")
    parts = [part for part in current.split(":") if part]
    if value not in parts:
        os.environ[name] = ":".join([value, *parts])
    if name == "PYTHONPATH" and value not in sys.path:
        sys.path.insert(0, value)


def configure_env(args: argparse.Namespace) -> None:
    os.environ.setdefault("ONEAPI_DEVICE_SELECTOR", "level_zero:0,1,2,3")
    os.environ.setdefault("ZE_AFFINITY_MASK", "0,1,2,3")
    os.environ.setdefault("CCL_ATL_TRANSPORT", "ofi")
    os.environ.setdefault("CCL_TOPO_P2P_ACCESS", "1")
    os.environ.setdefault("HF_HOME", "/mnt/fast-ai/llm-cache/hf")
    os.environ.setdefault("TRANSFORMERS_CACHE", f"{os.environ['HF_HOME']}/transformers")
    if args.vllm_cache_root:
        os.environ["VLLM_CACHE_ROOT"] = args.vllm_cache_root
    prepend_env_path(
        "PYTHONPATH",
        os.environ.get(
            "LLM_SCALER_KERNELS",
            "/home/steve/src/llm-scaler/vllm/custom-esimd-kernels-vllm/python",
        ),
    )
    prepend_env_path("LD_LIBRARY_PATH", os.environ.get("VENV", "/home/steve/.venvs/vllm-xpu") + "/lib")
    prepend_env_path(
        "LD_LIBRARY_PATH",
        os.environ.get("VENV", "/home/steve/.venvs/vllm-xpu")
        + "/lib/python3.12/site-packages/torch/lib",
    )


def text_quality_stats(token_ids: list[int], text: str) -> dict[str, Any]:
    distinct_tokens = sorted(set(token_ids))
    printable_chars = sum(
        1 for char in text if char.isprintable() and not char.isspace()
    )
    control_nonspace_chars = sum(
        1 for char in text if not char.isprintable() and not char.isspace()
    )
    nul_token_count = sum(1 for token in token_ids if token == 0)
    return {
        "n_tokens": len(token_ids),
        "distinct_generated_token_count": len(distinct_tokens),
        "first_distinct_generated_tokens": distinct_tokens[:16],
        "printable_nonspace_text_chars": printable_chars,
        "control_nonspace_text_chars": control_nonspace_chars,
        "nul_token_count": nul_token_count,
        "nontrivial_tokens": len(distinct_tokens) > 1,
        "nontrivial_text": printable_chars > 0,
        "control_char_output": control_nonspace_chars > 0 or nul_token_count > 0,
    }


def render_prompts(args: argparse.Namespace, tokenizer: Any) -> tuple[list[str], dict[str, Any]]:
    prompts = list(args.prompt or DEFAULT_PROMPTS)
    diagnostics: dict[str, Any] = {
        "raw_prompt_token_counts": [
            len(tokenizer(prompt, add_special_tokens=False).input_ids)
            for prompt in prompts
        ],
        "rendered_prompt_token_counts": None,
        "chat_template": None,
    }
    if args.raw_prompt:
        return prompts, diagnostics

    template_path = Path(args.chat_template or Path(args.model) / "chat_template.jinja")
    chat_template = template_path.read_text()
    rendered = [
        tokenizer.apply_chat_template(
            [{"role": "user", "content": prompt}],
            tokenize=False,
            chat_template=chat_template,
            add_generation_prompt=True,
        )
        for prompt in prompts
    ]
    diagnostics["chat_template"] = str(template_path)
    diagnostics["rendered_prompt_token_counts"] = [
        len(tokenizer(prompt, add_special_tokens=False).input_ids)
        for prompt in rendered
    ]
    return rendered, diagnostics


def make_engine_args(args: argparse.Namespace):
    from vllm.engine.arg_utils import AsyncEngineArgs

    compilation_config: dict[str, Any] = {
        "use_inductor_graph_partition": True,
        "compile_sizes": [1],
        "cudagraph_mode": "PIECEWISE",
    }
    if args.compilation_cache_dir:
        compilation_config["cache_dir"] = args.compilation_cache_dir

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
        compilation_config=compilation_config,
    )


async def generate_one(llm: Any, prompt: str, prompt_index: int, args: argparse.Namespace) -> dict[str, Any]:
    from vllm import SamplingParams
    from vllm.inputs import TextPrompt
    from vllm.sampling_params import RequestOutputKind

    params = SamplingParams(
        temperature=args.temperature,
        top_p=1.0,
        max_tokens=args.max_tokens,
        seed=0,
        stop_token_ids=[200020],
        output_kind=RequestOutputKind.FINAL_ONLY,
    )
    final = None
    start = time.perf_counter()
    async for result in llm.generate(
        TextPrompt(prompt=prompt),
        params,
        request_id=f"async-quality-{prompt_index}-{time.time_ns()}",
    ):
        final = result
    elapsed = time.perf_counter() - start
    if final is None or not final.outputs:
        raise RuntimeError(f"prompt {prompt_index} produced no output")
    output = final.outputs[0]
    token_ids = list(output.token_ids)
    text = output.text
    quality = text_quality_stats(token_ids, text)
    return {
        "prompt_index": prompt_index,
        "elapsed_s": elapsed,
        "n_tokens": len(token_ids),
        "tok_s_out_e2e": len(token_ids) / elapsed if elapsed > 0 else None,
        "token_ids": token_ids,
        "token_sha256": hashlib.sha256(
            ",".join(map(str, token_ids)).encode()
        ).hexdigest(),
        "text": text,
        "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "quality": quality,
    }


async def run(args: argparse.Namespace) -> dict[str, Any]:
    from vllm import SamplingParams
    from vllm.entrypoints.openai.api_server import (
        build_async_engine_client_from_engine_args,
    )
    from vllm.inputs import TextPrompt
    from vllm.sampling_params import RequestOutputKind
    from vllm.tokenizers import get_tokenizer

    tokenizer = get_tokenizer(args.model, trust_remote_code=True)
    prompts, diagnostics = render_prompts(args, tokenizer)
    records: list[dict[str, Any]] = []

    async with build_async_engine_client_from_engine_args(make_engine_args(args)) as llm:
        if args.warmup_output_tokens > 0:
            warmup_params = SamplingParams(
                temperature=0,
                top_p=1.0,
                max_tokens=args.warmup_output_tokens,
                seed=0,
                output_kind=RequestOutputKind.FINAL_ONLY,
            )
            async for _ in llm.generate(
                TextPrompt(prompt=prompts[0]),
                warmup_params,
                request_id=f"async-quality-warmup-{time.time_ns()}",
            ):
                pass
        for index, prompt in enumerate(prompts):
            records.append(await generate_one(llm, prompt, index, args))

    combined_token_ids = [
        token for record in records for token in record["token_ids"]
    ]
    combined_text = "".join(record["text"] for record in records)
    combined_quality = text_quality_stats(combined_token_ids, combined_text)
    failure_reasons = []
    if combined_quality["distinct_generated_token_count"] < args.min_distinct_generated_tokens:
        failure_reasons.append("too few distinct generated tokens")
    if combined_quality["printable_nonspace_text_chars"] < args.min_printable_nonspace_chars:
        failure_reasons.append("too few printable non-space text chars")
    if combined_quality["control_nonspace_text_chars"] > args.max_control_nonspace_chars:
        failure_reasons.append("control character output")
    if combined_quality["nul_token_count"] > args.max_nul_token_count:
        failure_reasons.append("NUL token output")
    if not combined_quality["nontrivial_tokens"] or not combined_quality["nontrivial_text"]:
        failure_reasons.append("degenerate output")

    return {
        "created_at_unix": time.time(),
        "model": args.model,
        "selected_env": {name: os.environ.get(name) for name in SELECTED_ENV_NAMES},
        "compilation_cache_dir": args.compilation_cache_dir,
        "prompt_diagnostics": diagnostics,
        "records": records,
        "combined": {
            "token_sha256": hashlib.sha256(
                ",".join(map(str, combined_token_ids)).encode()
            ).hexdigest(),
            "text_sha256": hashlib.sha256(combined_text.encode()).hexdigest(),
            "quality": combined_quality,
        },
        "passed": not failure_reasons,
        "failure_reasons": failure_reasons,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="/mnt/fast-ai/llm-models/minimax-m2.7-reap-autoround-w4a16")
    parser.add_argument("--out", required=True)
    parser.add_argument("--prompt", action="append")
    parser.add_argument("--raw-prompt", action="store_true")
    parser.add_argument("--chat-template")
    parser.add_argument("--dtype", default="float16")
    parser.add_argument("--tensor-parallel-size", type=int, default=4)
    parser.add_argument("--max-model-len", type=int, default=2048)
    parser.add_argument("--max-num-batched-tokens", type=int, default=512)
    parser.add_argument("--block-size", type=int, default=256)
    parser.add_argument("--max-tokens", type=int, default=128)
    parser.add_argument("--warmup-output-tokens", type=int, default=16)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--vllm-cache-root")
    parser.add_argument("--compilation-cache-dir")
    parser.add_argument("--min-distinct-generated-tokens", type=int, default=16)
    parser.add_argument("--min-printable-nonspace-chars", type=int, default=80)
    parser.add_argument("--max-control-nonspace-chars", type=int, default=0)
    parser.add_argument("--max-nul-token-count", type=int, default=0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    configure_env(args)
    artifact = asyncio.run(run(args))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2) + "\n")
    print(json.dumps({
        "out": str(out),
        "passed": artifact["passed"],
        "failure_reasons": artifact["failure_reasons"],
        "combined": artifact["combined"],
    }, indent=2))
    return 0 if artifact["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
