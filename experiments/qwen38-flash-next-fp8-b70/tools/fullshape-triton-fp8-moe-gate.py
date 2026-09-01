#!/usr/bin/env python3
"""Isolate the Flash-Next local FP8 MoE shape on one XPU."""

import argparse
import hashlib
import json
import os
import statistics
import time
from contextlib import nullcontext
from pathlib import Path

import torch
import torch.distributed as dist
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
    resolve_moe_gemm_configs,
    try_get_optimal_moe_config,
)
from vllm.model_executor.layers.fused_moe.modular_kernel import FusedMoEKernel
from vllm.model_executor.layers.fused_moe import override_config
from vllm.utils.torch_utils import get_accelerator_view_from_cpu_tensor
from vllm.v1.worker.workspace import init_workspace_manager


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--tokens", type=int, choices=(1, 4, 64, 128, 256, 512), required=True
    )
    parser.add_argument(
        "--ep-rank",
        type=int,
        choices=range(4),
        default=None,
        help="Exercise the production 512-global/128-local EP expert map",
    )
    parser.add_argument(
        "--tp-rank",
        type=int,
        choices=range(4),
        default=None,
        help=(
            "Exercise the native no-EP TP4 expert shape: all 512 experts with "
            "a 160-wide intermediate shard and losslessly refined 32x32 scales"
        ),
    )
    parser.add_argument(
        "--distributed-mode",
        choices=("ep4", "tp4-noep"),
        help=(
            "Initialize a four-rank XCCL process group, infer the EP/TP rank, "
            "and include the exact BF16 output all-reduce in each invocation"
        ),
    )
    parser.add_argument(
        "--path", choices=("functional", "modular"), default="functional"
    )
    parser.add_argument(
        "--weights",
        choices=("constant", "layer0-checkpoint", "layer0-rank0-checkpoint"),
        default="constant",
        help=(
            "Use constant weights or the exact layer-0 checkpoint shard for the "
            "selected EP/TP rank; the rank0 spelling is retained for compatibility"
        ),
    )
    parser.add_argument(
        "--routing",
        choices=("cyclic", "balanced-global", "fixed-ids", "all-padding"),
        default="cyclic",
        help="Use ordinary valid routing or the captured profile-run padding sentinel",
    )
    parser.add_argument(
        "--fixed-topk-ids",
        help="Comma-separated set of exactly ten global expert IDs for fixed-ids",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=1,
        help="Repeat the same initialized MoE invocation and report raw output hashes",
    )
    parser.add_argument(
        "--candidate-config-json",
        help="JSON object merged over the default Triton MoE configuration",
    )
    parser.add_argument("--warmups", type=int, default=10)
    parser.add_argument(
        "--timed-batches",
        type=int,
        default=0,
        help="Enable event timing with this many independent batches",
    )
    parser.add_argument("--iterations-per-batch", type=int, default=50)
    parser.add_argument("--hidden-seed", type=int, default=20260826)
    parser.add_argument("--hidden-scale", type=float, default=0.01)
    parser.add_argument("--routing-offset", type=int, default=17)
    parser.add_argument(
        "--model-path",
        type=Path,
        default=Path("/mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8"),
    )
    parser.add_argument(
        "--save-output",
        type=Path,
        help="Save the final CPU output tensor for cross-layout parity checks",
    )
    parser.add_argument(
        "--result-dir",
        type=Path,
        help="Write one final JSON result per distributed rank",
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
    distributed_rank = None
    local_rank = 0
    if args.distributed_mode is not None:
        if args.ep_rank is not None or args.tp_rank is not None:
            raise ValueError("distributed mode infers rank; omit --ep-rank/--tp-rank")
        dist.init_process_group("xccl")
        distributed_rank = dist.get_rank()
        local_rank = int(os.environ["LOCAL_RANK"])
        if dist.get_world_size() != 4 or not 0 <= distributed_rank < 4:
            raise ValueError("distributed mode requires exactly four ranks")
        if args.distributed_mode == "ep4":
            args.ep_rank = distributed_rank
        else:
            args.tp_rank = distributed_rank
    if not 1 <= args.repeats <= 100:
        raise ValueError("repeats must be between 1 and 100")
    if not 0 <= args.warmups <= 100:
        raise ValueError("warmups must be between 0 and 100")
    if not 0 <= args.timed_batches <= 25:
        raise ValueError("timed-batches must be between 0 and 25")
    if not 1 <= args.iterations_per_batch <= 200:
        raise ValueError("iterations-per-batch must be between 1 and 200")
    if args.routing == "balanced-global" and args.ep_rank is None:
        if args.tp_rank is None:
            raise ValueError("balanced-global routing requires --ep-rank or --tp-rank")
    fixed_topk_ids = None
    if args.routing == "fixed-ids":
        if args.fixed_topk_ids is None:
            raise ValueError("fixed-ids routing requires --fixed-topk-ids")
        fixed_topk_ids = [int(value) for value in args.fixed_topk_ids.split(",")]
        if len(fixed_topk_ids) != 10 or len(set(fixed_topk_ids)) != 10:
            raise ValueError("fixed top-k IDs must contain exactly ten unique values")
        if not all(0 <= value < 512 for value in fixed_topk_ids):
            raise ValueError("fixed top-k IDs must be between 0 and 511")
    elif args.fixed_topk_ids is not None:
        raise ValueError("--fixed-topk-ids requires --routing fixed-ids")
    if args.ep_rank is not None and args.tp_rank is not None:
        raise ValueError("--ep-rank and --tp-rank are mutually exclusive")
    if not 0.0 < args.hidden_scale <= 10.0:
        raise ValueError("hidden-scale must be in (0, 10]")

    candidate_config = None
    if args.candidate_config_json:
        candidate_delta = json.loads(args.candidate_config_json)
        if not isinstance(candidate_delta, dict):
            raise ValueError("candidate-config-json must decode to an object")
        candidate_config = None  # Filled after the default is resolved.

    torch.manual_seed(args.hidden_seed)
    device = torch.device(f"xpu:{local_rank}")
    torch.xpu.set_device(device)
    dtype = torch.bfloat16
    weight_dtype = torch.float8_e4m3fn
    global_experts, hidden, topk = 512, 2560, 10
    if args.tp_rank is not None:
        experts, intermediate, block_shape = 512, 160, [32, 32]
        parallel_mode = "tp4_no_ep"
    elif args.ep_rank is not None:
        experts, intermediate, block_shape = 128, 640, [128, 128]
        parallel_mode = "ep4"
    else:
        experts, intermediate, block_shape = 128, 640, [128, 128]
        parallel_mode = "single_rank_local"

    config = get_default_config(
        args.tokens,
        experts,
        intermediate,
        hidden,
        topk,
        "fp8_w8a8",
        block_shape,
    )
    if args.candidate_config_json:
        candidate_config = config | candidate_delta
    resolved_config = try_get_optimal_moe_config(
        (experts, 2 * intermediate, hidden),
        (experts, hidden, intermediate),
        topk,
        "fp8_w8a8",
        args.tokens,
        block_shape,
    )
    effective_config = candidate_config or resolved_config
    resolved_w1_config, resolved_w2_config = resolve_moe_gemm_configs(
        effective_config,
        M=args.tokens,
        enable_phase_configs=(
            args.path == "modular" and args.tokens == 1 and block_shape == [128, 128]
        ),
    )
    identity = {
        "tokens": args.tokens,
        "experts": experts,
        "intermediate": intermediate,
        "hidden": hidden,
        "topk": topk,
        "global_experts": (
            global_experts
            if args.ep_rank is not None or args.tp_rank is not None
            else experts
        ),
        "ep_rank": args.ep_rank,
        "tp_rank": args.tp_rank,
        "parallel_mode": parallel_mode,
        "distributed_mode": args.distributed_mode,
        "distributed_rank": distributed_rank,
        "distributed_world_size": dist.get_world_size() if dist.is_initialized() else 1,
        "path": args.path,
        "weights": args.weights,
        "routing": args.routing,
        "repeats": args.repeats,
        "ple_uva": args.map_ple_uva,
        "target_allocated_gib": args.target_allocated_gib,
        "target_reserved_gib": args.target_reserved_gib,
        "block_shape": block_shape,
        "input_dtype": str(dtype),
        "weight_dtype": str(weight_dtype),
        "config": config,
        "candidate_config": candidate_config,
        "resolved_config": effective_config,
        "resolved_w1_config": resolved_w1_config,
        "resolved_w2_config": resolved_w2_config,
        "warmups": args.warmups,
        "timed_batches": args.timed_batches,
        "iterations_per_batch": args.iterations_per_batch,
        "hidden_seed": args.hidden_seed,
        "hidden_scale": args.hidden_scale,
        "routing_offset": args.routing_offset,
        "fixed_topk_ids": fixed_topk_ids,
        "save_output": str(args.save_output) if args.save_output is not None else None,
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
        args.hidden_scale
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
        (
            experts,
            2 * intermediate // block_shape[0],
            hidden // block_shape[1],
        ),
        device=device,
        dtype=torch.float32,
    )
    w2_scale = torch.empty(
        (
            experts,
            hidden // block_shape[0],
            intermediate // block_shape[1],
        ),
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
            first_expert = args.ep_rank * experts if args.ep_rank is not None else 0
            shard_start = args.tp_rank * intermediate if args.tp_rank is not None else 0
            for local_expert in range(experts):
                global_expert = first_expert + local_expert
                expert_prefix = f"{prefix}.{global_expert}"
                gate_weight = gate_up.get_tensor(f"{expert_prefix}.gate_proj.weight")
                up_weight = gate_up.get_tensor(f"{expert_prefix}.up_proj.weight")
                down_weight = down.get_tensor(f"{expert_prefix}.down_proj.weight")
                gate_scale = gate_up.get_tensor(
                    f"{expert_prefix}.gate_proj.weight_scale_inv"
                )
                up_scale = gate_up.get_tensor(
                    f"{expert_prefix}.up_proj.weight_scale_inv"
                )
                down_scale = down.get_tensor(
                    f"{expert_prefix}.down_proj.weight_scale_inv"
                )
                if args.tp_rank is not None:
                    gate_weight = gate_weight.narrow(0, shard_start, intermediate)
                    up_weight = up_weight.narrow(0, shard_start, intermediate)
                    down_weight = down_weight.narrow(1, shard_start, intermediate)
                    refine = 128 // block_shape[0]
                    gate_scale = gate_scale.repeat_interleave(
                        refine, dim=0
                    ).repeat_interleave(refine, dim=1)
                    up_scale = up_scale.repeat_interleave(
                        refine, dim=0
                    ).repeat_interleave(refine, dim=1)
                    down_scale = down_scale.repeat_interleave(
                        refine, dim=0
                    ).repeat_interleave(refine, dim=1)
                    scale_start = args.tp_rank * (intermediate // block_shape[0])
                    gate_scale = gate_scale.narrow(
                        0, scale_start, intermediate // block_shape[0]
                    )
                    up_scale = up_scale.narrow(
                        0, scale_start, intermediate // block_shape[0]
                    )
                    down_scale = down_scale.narrow(
                        1, scale_start, intermediate // block_shape[1]
                    )
                w1[local_expert, :intermediate].copy_(gate_weight)
                w1[local_expert, intermediate:].copy_(up_weight)
                w2[local_expert].copy_(down_weight)
                scale_rows = intermediate // block_shape[0]
                w1_scale[local_expert, :scale_rows].copy_(gate_scale)
                w1_scale[local_expert, scale_rows:].copy_(up_scale)
                w2_scale[local_expert].copy_(down_scale)
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
    routed_experts = (
        global_experts
        if args.ep_rank is not None or args.tp_rank is not None
        else experts
    )
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
    if args.routing == "all-padding":
        topk_ids = torch.full((args.tokens, topk), -1, device=device, dtype=torch.int32)
        topk_weights = torch.zeros(
            (args.tokens, topk), device=device, dtype=torch.float32
        )
    elif args.routing == "balanced-global":
        topk_ids = (
            torch.arange(args.tokens * topk, device=device, dtype=torch.int32)
            .mul_(131)
            .add_(args.routing_offset)
            .remainder_(global_experts)
            .reshape(args.tokens, topk)
        )
        topk_weights = torch.full(
            (args.tokens, topk),
            1.0 / topk,
            device=device,
            dtype=torch.float32,
        )
    elif args.routing == "fixed-ids":
        topk_ids = torch.tensor(
            fixed_topk_ids,
            device=device,
            dtype=torch.int32,
        ).repeat(args.tokens, 1)
        topk_weights = torch.full(
            (args.tokens, topk),
            1.0 / topk,
            device=device,
            dtype=torch.float32,
        )
    else:
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

    if args.path == "functional":

        def invoke() -> torch.Tensor:
            return fused_experts(
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

        def invoke() -> torch.Tensor:
            return kernel.apply(
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

    local_invoke = invoke

    def invoke() -> torch.Tensor:
        output = local_invoke()
        if dist.is_initialized():
            dist.all_reduce(output)
        return output

    if args.ep_rank is not None:
        first_local_expert = args.ep_rank * experts
        local_valid_routes = int(
            (
                (topk_ids >= first_local_expert)
                & (topk_ids < first_local_expert + experts)
            )
            .sum()
            .item()
        )
    else:
        local_valid_routes = int((topk_ids >= 0).sum().item())
    identity["local_valid_routes"] = local_valid_routes

    started = time.monotonic()
    output_hashes = []
    timing_us_per_invoke = []
    compile_seconds = None
    config_context = (
        override_config(candidate_config)
        if candidate_config is not None
        else nullcontext()
    )
    with config_context:
        if args.timed_batches:
            compile_started = time.monotonic()
            output = invoke()
            torch.xpu.synchronize()
            compile_seconds = time.monotonic() - compile_started
            for _ in range(args.warmups):
                output = invoke()
            torch.xpu.synchronize()
            torch.xpu.reset_peak_memory_stats()
            for _ in range(args.timed_batches):
                start_event = torch.xpu.Event(enable_timing=True)
                end_event = torch.xpu.Event(enable_timing=True)
                start_event.record()
                for _ in range(args.iterations_per_batch):
                    output = invoke()
                end_event.record()
                end_event.synchronize()
                timing_us_per_invoke.append(
                    start_event.elapsed_time(end_event)
                    * 1000.0
                    / args.iterations_per_batch
                )
        for _ in range(args.repeats):
            output = invoke()
            torch.xpu.synchronize()
            raw = output.contiguous().view(torch.uint8).cpu().numpy().tobytes()
            output_hashes.append(hashlib.sha256(raw).hexdigest())

    if not output_hashes:
        torch.xpu.synchronize()
        raw = output.contiguous().view(torch.uint8).cpu().numpy().tobytes()
        output_hashes.append(hashlib.sha256(raw).hexdigest())
    output_float = output.float().cpu()
    if args.save_output is not None:
        output_path = args.save_output
        if distributed_rank is not None:
            output_path = output_path.with_name(
                f"{output_path.stem}-rank{distributed_rank}{output_path.suffix}"
            )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(output.cpu(), output_path)
    result = {
        "status": "pass",
        "identity": identity,
        "elapsed_seconds": time.monotonic() - started,
        "output_shape": list(output.shape),
        "finite": bool(torch.isfinite(output_float).all()),
        "max_abs": float(output_float.abs().max()),
        "mean_abs": float(output_float.abs().mean()),
        "output_sha256_first": output_hashes[0],
        "output_sha256_unique_values": sorted(set(output_hashes)),
        "unique_output_sha256": len(set(output_hashes)),
        "compile_seconds": compile_seconds,
        "timing_us_per_invoke": timing_us_per_invoke,
        "timing_median_us": (
            statistics.median(timing_us_per_invoke) if timing_us_per_invoke else None
        ),
        "timing_p10_us": (
            sorted(timing_us_per_invoke)[
                max(0, int(0.1 * (len(timing_us_per_invoke) - 1)))
            ]
            if timing_us_per_invoke
            else None
        ),
        "timing_p90_us": (
            sorted(timing_us_per_invoke)[
                min(
                    len(timing_us_per_invoke) - 1,
                    int(0.9 * (len(timing_us_per_invoke) - 1)),
                )
            ]
            if timing_us_per_invoke
            else None
        ),
        "memory_allocated": torch.xpu.memory_allocated(),
        "memory_reserved": torch.xpu.memory_reserved(),
        "max_memory_allocated": torch.xpu.max_memory_allocated(),
        "max_memory_reserved": torch.xpu.max_memory_reserved(),
    }
    if not result["finite"]:
        raise RuntimeError(f"non-finite MoE output: {result}")
    if args.result_dir is not None:
        args.result_dir.mkdir(parents=True, exist_ok=True)
        rank_label = distributed_rank if distributed_rank is not None else 0
        (args.result_dir / f"rank{rank_label}.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(result, sort_keys=True), flush=True)
    if dist.is_initialized():
        dist.destroy_process_group()


if __name__ == "__main__":
    main()
