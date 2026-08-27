#!/usr/bin/env python3
"""Isolate the Flash-Next local FP8 MoE shape on one XPU."""

import argparse
import json
import time
from pathlib import Path

import torch
from safetensors import safe_open

from vllm.model_executor.layers.fused_moe.config import FusedMoEQuantConfig
from vllm.model_executor.layers.fused_moe.activation import MoEActivation
from vllm.model_executor.layers.fused_moe.all2all_utils import (
    maybe_make_prepare_finalize,
)
from vllm.model_executor.layers.fused_moe.config import (
    FusedMoEConfig,
    FusedMoEParallelConfig,
    RoutingMethodType,
)
from vllm.model_executor.layers.fused_moe.experts.triton_moe import TritonExperts
from vllm.model_executor.layers.fused_moe.fused_moe import (
    fused_experts,
    get_default_config,
)
from vllm.model_executor.layers.fused_moe.modular_kernel import FusedMoEKernel
from vllm.utils.torch_utils import get_accelerator_view_from_cpu_tensor
from vllm.v1.worker.workspace import init_workspace_manager


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--tokens", type=int, choices=(1, 64, 128, 256, 512), required=True
    )
    parser.add_argument(
        "--ep-rank",
        type=int,
        choices=range(4),
        default=None,
        help="Exercise the production 512-global/128-local EP expert map",
    )
    parser.add_argument(
        "--path", choices=("functional", "modular"), default="functional"
    )
    parser.add_argument(
        "--weights", choices=("constant", "layer0-rank0-checkpoint"), default="constant"
    )
    parser.add_argument(
        "--model-path",
        type=Path,
        default=Path("/mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8"),
    )
    parser.add_argument(
        "--map-ple-uva",
        action="store_true",
        help="Keep the exact TP4-local 11.92 GiB PLE host-USM view live",
    )
    parser.add_argument(
        "--target-allocated-gib",
        type=float,
        default=None,
        help="Touch XPU ballast until torch reports this total allocation",
    )
    parser.add_argument(
        "--target-reserved-gib",
        type=float,
        default=None,
        help="Raise and retain the allocator reservation after ballast is ready",
    )
    args = parser.parse_args()

    torch.manual_seed(20260826)
    device = torch.device("xpu:0")
    dtype = torch.bfloat16
    weight_dtype = torch.float8_e4m3fn
    experts, global_experts, intermediate, hidden, topk = 128, 512, 640, 2560, 10
    block_shape = [128, 128]

    config = get_default_config(
        args.tokens,
        experts,
        intermediate,
        hidden,
        topk,
        "fp8_w8a8",
        block_shape,
    )
    identity = {
        "tokens": args.tokens,
        "experts": experts,
        "intermediate": intermediate,
        "hidden": hidden,
        "topk": topk,
        "global_experts": global_experts if args.ep_rank is not None else experts,
        "ep_rank": args.ep_rank,
        "path": args.path,
        "weights": args.weights,
        "ple_uva": args.map_ple_uva,
        "target_allocated_gib": args.target_allocated_gib,
        "target_reserved_gib": args.target_reserved_gib,
        "block_shape": block_shape,
        "input_dtype": str(dtype),
        "weight_dtype": str(weight_dtype),
        "config": config,
    }
    print(json.dumps({"event": "start", "identity": identity}), flush=True)

    ple_cpu = None
    ple_view = None
    if args.map_ple_uva:
        ple_started = time.monotonic()
        ple_cpu = torch.empty(
            (80_000_384, 160),
            dtype=weight_dtype,
            device="cpu",
            pin_memory=True,
        )
        ple_view = get_accelerator_view_from_cpu_tensor(ple_cpu)
        if ple_view.shape != ple_cpu.shape or ple_view.device != device:
            raise RuntimeError("PLE UVA view identity mismatch")
        print(
            json.dumps(
                {
                    "event": "ple_uva_ready",
                    "seconds": time.monotonic() - ple_started,
                    "bytes": ple_view.numel() * ple_view.element_size(),
                }
            ),
            flush=True,
        )
    hidden_states = torch.randn((args.tokens, hidden), device=device, dtype=dtype).mul_(
        0.01
    )
    w1 = torch.empty(
        (experts, 2 * intermediate, hidden),
        device=device,
        dtype=weight_dtype,
    )
    w2 = torch.empty(
        (experts, hidden, intermediate),
        device=device,
        dtype=weight_dtype,
    )
    w1_scale = torch.empty(
        (experts, 2 * intermediate // 128, hidden // 128),
        device=device,
        dtype=torch.float32,
    )
    w2_scale = torch.empty(
        (experts, hidden // 128, intermediate // 128),
        device=device,
        dtype=torch.float32,
    )
    if args.weights == "constant":
        w1.fill_(0.015625)
        w2.fill_(0.015625)
        w1_scale.fill_(0.015625)
        w2_scale.fill_(0.015625)
    else:
        gate_up_shard = args.model_path / "model-00002-of-00131.safetensors"
        down_shard = args.model_path / "model-00003-of-00131.safetensors"
        if not gate_up_shard.is_file() or not down_shard.is_file():
            raise FileNotFoundError("layer-0 checkpoint shards are missing")
        prefix = "model.language_model.layers.0.mlp.experts"
        load_started = time.monotonic()
        with (
            safe_open(gate_up_shard, framework="pt", device="cpu") as gate_up,
            safe_open(down_shard, framework="pt", device="cpu") as down,
        ):
            for expert in range(experts):
                expert_prefix = f"{prefix}.{expert}"
                w1[expert, :intermediate].copy_(
                    gate_up.get_tensor(f"{expert_prefix}.gate_proj.weight")
                )
                w1[expert, intermediate:].copy_(
                    gate_up.get_tensor(f"{expert_prefix}.up_proj.weight")
                )
                w2[expert].copy_(down.get_tensor(f"{expert_prefix}.down_proj.weight"))
                w1_scale[expert, : intermediate // 128].copy_(
                    gate_up.get_tensor(f"{expert_prefix}.gate_proj.weight_scale_inv")
                )
                w1_scale[expert, intermediate // 128 :].copy_(
                    gate_up.get_tensor(f"{expert_prefix}.up_proj.weight_scale_inv")
                )
                w2_scale[expert].copy_(
                    down.get_tensor(f"{expert_prefix}.down_proj.weight_scale_inv")
                )
        torch.xpu.synchronize()
        print(
            json.dumps(
                {
                    "event": "weights_loaded",
                    "seconds": time.monotonic() - load_started,
                    "experts": experts,
                    "layer": 0,
                }
            ),
            flush=True,
        )
    routed_experts = global_experts if args.ep_rank is not None else experts
    ballast = None
    if args.target_allocated_gib is not None:
        if not 1.0 <= args.target_allocated_gib <= 31.75:
            raise ValueError("target allocation must be between 1.0 and 31.75 GiB")
        target_bytes = int(args.target_allocated_gib * 1024**3)
        allocated_before = torch.xpu.memory_allocated()
        if target_bytes <= allocated_before:
            raise ValueError(
                f"target {target_bytes} is not above current {allocated_before}"
            )
        ballast = torch.empty(
            (target_bytes - allocated_before,), dtype=torch.uint8, device=device
        )
        ballast.zero_()
        torch.xpu.synchronize()
        print(
            json.dumps(
                {
                    "event": "ballast_ready",
                    "target_bytes": target_bytes,
                    "allocated_before": allocated_before,
                    "allocated_after": torch.xpu.memory_allocated(),
                    "reserved_after": torch.xpu.memory_reserved(),
                    "max_allocated_after": torch.xpu.max_memory_allocated(),
                }
            ),
            flush=True,
        )
    if args.target_reserved_gib is not None:
        if args.target_allocated_gib is None:
            raise ValueError("a reserved target requires an allocated target")
        if not args.target_allocated_gib <= args.target_reserved_gib <= 31.86:
            raise ValueError("reserved target must be between allocated and 31.86 GiB")
        target_reserved_bytes = int(args.target_reserved_gib * 1024**3)
        reserved_before = torch.xpu.memory_reserved()
        if target_reserved_bytes <= reserved_before:
            raise ValueError(
                f"reserved target {target_reserved_bytes} is not above current "
                f"{reserved_before}"
            )
        reservation_padding = torch.empty(
            (target_reserved_bytes - reserved_before,), dtype=torch.uint8, device=device
        )
        reservation_padding.zero_()
        torch.xpu.synchronize()
        del reservation_padding
        torch.xpu.synchronize()
        print(
            json.dumps(
                {
                    "event": "reservation_ready",
                    "target_reserved_bytes": target_reserved_bytes,
                    "allocated_after": torch.xpu.memory_allocated(),
                    "reserved_after": torch.xpu.memory_reserved(),
                    "max_allocated_after": torch.xpu.max_memory_allocated(),
                }
            ),
            flush=True,
        )
    topk_ids = (
        torch.arange(args.tokens * topk, device=device, dtype=torch.int32)
        .remainder_(routed_experts)
        .reshape(args.tokens, topk)
    )
    topk_weights = torch.full(
        (args.tokens, topk),
        1.0 / topk,
        device=device,
        dtype=torch.float32,
    )
    quant_config = FusedMoEQuantConfig.make(
        quant_dtype=weight_dtype,
        block_shape=block_shape,
        w1_scale=w1_scale,
        w2_scale=w2_scale,
    )
    expert_map = None
    if args.ep_rank is not None:
        expert_map = torch.full((global_experts,), -1, device=device, dtype=torch.int32)
        first_expert = args.ep_rank * experts
        expert_map[first_expert : first_expert + experts] = torch.arange(
            experts, device=device, dtype=torch.int32
        )

    started = time.monotonic()
    if args.path == "functional":
        output = fused_experts(
            hidden_states,
            w1,
            w2,
            topk_weights,
            topk_ids,
            global_num_experts=routed_experts,
            expert_map=expert_map,
            quant_config=quant_config,
        )
    else:
        moe_config = FusedMoEConfig(
            num_experts=routed_experts,
            num_local_experts=experts,
            num_logical_experts=routed_experts,
            experts_per_token=topk,
            hidden_dim=hidden,
            intermediate_size=intermediate,
            activation=MoEActivation.SILU,
            device=device,
            routing_method=RoutingMethodType.TopK,
            moe_parallel_config=FusedMoEParallelConfig.make_no_parallel(),
            in_dtype=dtype,
            moe_backend="triton",
            max_num_tokens=args.tokens,
        )
        prepare_finalize = maybe_make_prepare_finalize(
            moe=moe_config,
            quant_config=quant_config,
            allow_new_interface=True,
            use_monolithic=False,
        )
        if prepare_finalize is None:
            raise RuntimeError("modular prepare/finalize was not constructed")
        init_workspace_manager(device)
        kernel = FusedMoEKernel(
            prepare_finalize,
            TritonExperts(moe_config, quant_config),
        )
        output = kernel.apply(
            hidden_states,
            w1,
            w2,
            topk_weights,
            topk_ids,
            activation=MoEActivation.SILU,
            global_num_experts=routed_experts,
            expert_map=expert_map,
            apply_router_weight_on_input=False,
        )
    torch.xpu.synchronize()
    output_float = output.float().cpu()
    result = {
        "status": "pass",
        "identity": identity,
        "elapsed_seconds": time.monotonic() - started,
        "output_shape": list(output.shape),
        "finite": bool(torch.isfinite(output_float).all()),
        "max_abs": float(output_float.abs().max()),
        "mean_abs": float(output_float.abs().mean()),
    }
    if not result["finite"]:
        raise RuntimeError(f"non-finite MoE output: {result}")
    print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
