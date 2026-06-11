#!/usr/bin/env python3
"""Warm in-process throughput probe for Qwen3.6 Quark W8A8 INT8.

This removes OpenAI HTTP/frontdoor streaming from the measurement while keeping
the accepted model, quantization, TP4, graph, and no-prefix runtime posture. It
is a diagnostic for bottleneck attribution, not a production launcher.
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
from typing import Any


DEFAULT_MODEL = (
    "/mnt/fast-ai/llm-cache/hf/models--nameistoken--"
    "Qwen3.6-35B-A3B-Quark-W8A8-INT8/snapshots/"
    "cced56592e8c8935f8220836b4baa04dfd389118"
)


def prepend_env_path(name: str, value: str) -> None:
    current = os.environ.get(name, "")
    parts = [part for part in current.split(":") if part]
    if value not in parts:
        os.environ[name] = ":".join([value, *parts])
    if name == "PYTHONPATH" and value not in sys.path:
        sys.path.insert(0, value)


def apply_accepted_env(args: argparse.Namespace) -> None:
    cache_root = args.cache_root
    env_defaults = {
        "HF_HOME": "/mnt/fast-ai/llm-cache/hf",
        "HUGGINGFACE_HUB_CACHE": "/mnt/fast-ai/llm-cache/hf",
        "TORCHINDUCTOR_CACHE_DIR": (
            f"{cache_root}/qwen36-offline-warm-throughput/torchinductor"
        ),
        "VLLM_CACHE_ROOT": f"{cache_root}/qwen36-offline-warm-throughput/vllm",
        "VLLM_USE_V1": "1",
        "VLLM_TARGET_DEVICE": "xpu",
        "VLLM_ALLOW_LONG_MAX_MODEL_LEN": "1",
        "XPU_GRAPH": "1",
        "VLLM_XPU_ENABLE_XPU_GRAPH": "1",
        "VLLM_XPU_FORCE_GRAPH_WITH_COMM": "1",
        "VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE": "1",
        "VLLM_XPU_USE_CUSTOM_OP_COLLECTIVES": "1",
        "VLLM_XPU_COMPILE_ALLREDUCE_CUSTOM_OP": "1",
        "VLLM_XPU_CUSTOM_ALLREDUCE_GRAPH_CLONE_INPUT": "1",
        "VLLM_XPU_CUSTOM_ALLREDUCE_CLONE_INPUT": "1",
        "VLLM_XPU_QUARK_W8A8_MOE": "1",
        "VLLM_XPU_FORCE_QUARK_REPACK": "0",
        "VLLM_XPU_GDN_REUSE_QKVZ_BA_QUANT": "clone",
        "ONEAPI_DEVICE_SELECTOR": "level_zero:0,1,2,3",
        "ZE_AFFINITY_MASK": "0,1,2,3",
        "CCL_ATL_TRANSPORT": "ofi",
        "CCL_TOPO_P2P_ACCESS": "1",
        "FI_TCP_IFACE": "eth1",
        "CCL_KVS_IFACE": "eth1",
    }
    for key, value in env_defaults.items():
        os.environ.setdefault(key, value)

    # Keep rejected/diagnostic flags out unless the caller explicitly sets them.
    os.environ.pop("VLLM_XPU_GDN_SKIP_DECODE_CONV_TMP", None)
    os.environ.pop("VLLM_XPU_DEDUP_INT8_QUANT", None)
    os.environ.pop("CCL_ZE_IPC_EXCHANGE", None)
    os.environ.pop("CCL_WORKER_COUNT", None)

    prepend_env_path("PYTHONPATH", "/home/steve/src/vllm")
    prepend_env_path("PYTHONPATH", "/home/steve/src/vllm-xpu-kernels")
    prepend_env_path(
        "LD_LIBRARY_PATH",
        "/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels",
    )
    prepend_env_path("LD_LIBRARY_PATH", "/home/steve/.venvs/vllm-xpu/lib")
    prepend_env_path(
        "LD_LIBRARY_PATH",
        "/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--out", required=True)
    parser.add_argument("--tensor-parallel-size", type=int, default=4)
    parser.add_argument("--max-model-len", type=int, default=32768)
    parser.add_argument("--max-num-batched-tokens", type=int, default=8192)
    parser.add_argument("--max-num-seqs", type=int, default=48)
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.95)
    parser.add_argument("--input-len", type=int, default=512)
    parser.add_argument("--output-len", type=int, default=512)
    parser.add_argument("--num-prompts", type=int, default=1)
    parser.add_argument("--warmup-repeats", type=int, default=1)
    parser.add_argument("--repeats", type=int, default=4)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--prompt-seed", type=int, default=20260611)
    parser.add_argument("--repeat-period", type=int, default=503)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top-p", type=float, default=1.0)
    parser.add_argument("--top-k", type=int, default=0)
    parser.add_argument("--detokenize", action="store_true")
    parser.add_argument(
        "--cache-root",
        default="/mnt/fast-ai/vllm-cache-exp",
        help="Base cache directory used for offline graph/inductor artifacts.",
    )
    parser.add_argument(
        "--compilation-config-json",
        default='{"cudagraph_mode":"PIECEWISE"}',
        help="JSON object passed as vLLM compilation_config.",
    )
    return parser.parse_args()


def build_prompts(args: argparse.Namespace) -> list[dict[str, list[int]]]:
    prompts = []
    base = 1000 + args.prompt_seed % 1000
    period = max(1, args.repeat_period)
    for prompt_idx in range(args.num_prompts):
        offset = base + prompt_idx * 1009
        ids = [offset + (idx % period) for idx in range(args.input_len)]
        prompts.append({"prompt_token_ids": ids})
    return prompts


def token_hash(outputs: list[Any]) -> str:
    token_ids: list[int] = []
    for request in outputs:
        token_ids.extend(int(tok) for tok in request.outputs[0].token_ids)
        token_ids.append(-1)
    return hashlib.sha256(",".join(map(str, token_ids)).encode()).hexdigest()


def run_generate(llm: Any, prompts: list[dict[str, list[int]]],
                 sampling_params: Any) -> dict[str, Any]:
    start = time.perf_counter()
    outputs = llm.generate(prompts, sampling_params, use_tqdm=False)
    elapsed = time.perf_counter() - start
    output_tokens = sum(len(output.outputs[0].token_ids) for output in outputs)
    prompt_tokens = sum(len(prompt["prompt_token_ids"]) for prompt in prompts)
    return {
        "elapsed_s": elapsed,
        "prompt_tokens": prompt_tokens,
        "output_tokens": output_tokens,
        "total_tokens": prompt_tokens + output_tokens,
        "output_toks_per_second": output_tokens / elapsed,
        "total_toks_per_second": (prompt_tokens + output_tokens) / elapsed,
        "token_sha256": token_hash(outputs),
    }


def main() -> int:
    args = parse_args()
    apply_accepted_env(args)

    from vllm import LLM, SamplingParams

    compilation_config = json.loads(args.compilation_config_json)
    if not isinstance(compilation_config, dict):
        raise SystemExit("--compilation-config-json must be a JSON object")

    init_start = time.perf_counter()
    llm = LLM(
        model=args.model,
        tokenizer=args.model,
        trust_remote_code=True,
        dtype="auto",
        quantization="quark",
        tensor_parallel_size=args.tensor_parallel_size,
        distributed_executor_backend="mp",
        max_model_len=args.max_model_len,
        max_num_batched_tokens=args.max_num_batched_tokens,
        max_num_seqs=args.max_num_seqs,
        gpu_memory_utilization=args.gpu_memory_utilization,
        enable_prefix_caching=False,
        language_model_only=True,
        generation_config="vllm",
        compilation_config=compilation_config,
    )
    init_elapsed = time.perf_counter() - init_start

    sampling_params = SamplingParams(
        temperature=args.temperature,
        top_p=args.top_p,
        top_k=args.top_k,
        max_tokens=args.output_len,
        seed=args.seed,
        ignore_eos=True,
        detokenize=args.detokenize,
    )
    prompts = build_prompts(args)

    warmups = [
        {"repeat": idx, **run_generate(llm, prompts, sampling_params)}
        for idx in range(args.warmup_repeats)
    ]
    repeats = [
        {"repeat": idx, **run_generate(llm, prompts, sampling_params)}
        for idx in range(args.repeats)
    ]

    output_tps = [record["output_toks_per_second"] for record in repeats]
    total_tps = [record["total_toks_per_second"] for record in repeats]
    result = {
        "model": args.model,
        "engine": "vllm-offline-llm",
        "tensor_parallel_size": args.tensor_parallel_size,
        "quantization": "quark",
        "dtype": "auto",
        "max_model_len": args.max_model_len,
        "max_num_batched_tokens": args.max_num_batched_tokens,
        "max_num_seqs": args.max_num_seqs,
        "gpu_memory_utilization": args.gpu_memory_utilization,
        "prefix_caching": False,
        "compilation_config": compilation_config,
        "input_len": args.input_len,
        "output_len": args.output_len,
        "num_prompts": args.num_prompts,
        "temperature": args.temperature,
        "top_p": args.top_p,
        "top_k": args.top_k,
        "detokenize": args.detokenize,
        "init_elapsed_s": init_elapsed,
        "warmup_repeats": warmups,
        "repeats": repeats,
        "mean_output_toks_per_second": statistics.fmean(output_tps),
        "mean_total_toks_per_second": statistics.fmean(total_tps),
        "min_output_toks_per_second": min(output_tps),
        "max_output_toks_per_second": max(output_tps),
        "stdev_output_toks_per_second": (
            statistics.stdev(output_tps) if len(output_tps) > 1 else 0.0
        ),
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
