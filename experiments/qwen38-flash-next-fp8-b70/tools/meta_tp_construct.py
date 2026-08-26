#!/usr/bin/env python3
"""Construct Qwen3.8 Flash-Next on meta tensors at the requested TP width.

This is a fail-closed preflight: it exercises the real local checkpoint config,
model registry, per-rank tensor shapes, quantization selection, and all layer
constructors without allocating or loading checkpoint weights.
"""

import argparse
import json
import os

import torch
import torch.distributed as dist

from vllm.config import set_current_vllm_config
from vllm.distributed.parallel_state import (
    ensure_model_parallel_initialized,
    init_distributed_environment,
)
from vllm.engine.arg_utils import EngineArgs
from vllm.model_executor.model_loader.utils import initialize_model
from vllm.model_executor.models import ModelRegistry
from vllm.utils.torch_utils import set_default_torch_dtype


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--max-model-len", type=int, default=512)
    parser.add_argument("--enable-expert-parallel", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rank = int(os.environ["RANK"])
    local_rank = int(os.environ["LOCAL_RANK"])
    world_size = int(os.environ["WORLD_SIZE"])

    engine_args = EngineArgs(
        model=args.model,
        tokenizer=args.model,
        trust_remote_code=False,
        tensor_parallel_size=world_size,
        enable_expert_parallel=args.enable_expert_parallel,
        language_model_only=True,
        enforce_eager=True,
        enable_prefix_caching=False,
        max_model_len=args.max_model_len,
        max_num_seqs=1,
        max_num_batched_tokens=args.max_model_len,
    )
    vllm_config = engine_args.create_engine_config(usage_context=None)
    init_distributed_environment(
        world_size=world_size,
        rank=rank,
        distributed_init_method="env://",
        local_rank=local_rank,
        backend="gloo",
    )
    with set_current_vllm_config(vllm_config):
        ensure_model_parallel_initialized(
            tensor_model_parallel_size=world_size,
            pipeline_model_parallel_size=1,
            backend="gloo",
        )
        model_cls, architecture = ModelRegistry.resolve_model_cls(
            vllm_config.model_config.architectures,
            vllm_config.model_config,
        )
        if args.enable_expert_parallel:
            # Expert placement control tensors inherit the meta device during
            # this dry construction. Avoid only the human-readable torch.where
            # used for logging; local expert counts and parameter shapes remain
            # governed by the real EP rank/size configuration.
            from vllm.model_executor.layers.fused_moe.expert_map_manager import (
                ExpertMapManager,
            )

            ExpertMapManager.get_compressed_map_string = lambda self: "<meta>"
        with (
            set_default_torch_dtype(vllm_config.model_config.dtype),
            torch.device("meta"),
        ):
            model = initialize_model(
                vllm_config=vllm_config,
                model_class=model_cls,
                model_config=vllm_config.model_config,
            )

    dtype_bytes: dict[str, int] = {}
    parameter_count = 0
    parameter_bytes = 0
    largest_parameters: list[dict[str, object]] = []
    for name, parameter in model.named_parameters():
        size = parameter.numel() * parameter.element_size()
        parameter_count += parameter.numel()
        parameter_bytes += size
        key = str(parameter.dtype).removeprefix("torch.")
        dtype_bytes[key] = dtype_bytes.get(key, 0) + size
        largest_parameters.append(
            {
                "name": name,
                "bytes": size,
                "shape": list(parameter.shape),
                "dtype": key,
            }
        )
    largest_parameters.sort(key=lambda item: int(item["bytes"]), reverse=True)
    largest_by_dtype = {
        dtype: [item for item in largest_parameters if item["dtype"] == dtype][:12]
        for dtype in sorted(dtype_bytes)
    }

    ple_modules = [
        {"name": name, "module": type(module).__module__}
        for name, module in model.named_modules()
        if type(module).__name__ == "Qwen4ExpNGramEmbedding"
    ]
    result = {
        "rank": rank,
        "world_size": world_size,
        "expert_parallel": args.enable_expert_parallel,
        "architecture": architecture,
        "model_class": f"{model_cls.__module__}.{model_cls.__name__}",
        "quantization": vllm_config.model_config.quantization,
        "dtype": str(vllm_config.model_config.dtype),
        "module_count": sum(1 for _ in model.modules()),
        "parameter_count": parameter_count,
        "parameter_bytes": parameter_bytes,
        "parameter_gib": parameter_bytes / 1024**3,
        "parameter_bytes_by_dtype": dtype_bytes,
        "largest_parameters": largest_parameters[:20],
        "largest_parameters_by_dtype": largest_by_dtype,
        "ple_modules": ple_modules,
    }
    print("QWEN38_META_RESULT=" + json.dumps(result, sort_keys=True), flush=True)
    dist.barrier()
    dist.destroy_process_group()


if __name__ == "__main__":
    main()
