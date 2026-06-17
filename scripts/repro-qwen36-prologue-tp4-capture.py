#!/usr/bin/env python3
"""Reduced TP4 capture reproducer for Qwen3.6 W8A8 MoE prologue.

This is not a benchmark. It isolates the endpoint failure mode where
`fused_moe_prologue` plus the W8A8 middle layerlet device-loses during vLLM
PIECEWISE graph capture. The script runs several worker processes, pins one XPU
per process, captures a model-shaped sequence of MoE layer calls, and performs
the small CPU-to-XPU dummy tensor copy that surfaced the endpoint failure.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_KERNEL_REPO = Path("/home/steve/src/vllm-xpu-kernels")
DEFAULT_DATA_DIR = Path("/home/steve/llm-optimizations/data")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ranks", type=int, default=4)
    parser.add_argument("--captures", type=int, default=1)
    parser.add_argument("--layers-per-capture", type=int, default=40)
    parser.add_argument("--replays", type=int, default=3)
    parser.add_argument("--distinct-layers", action="store_true")
    parser.add_argument("--rows", type=int, default=1)
    parser.add_argument("--hidden", type=int, default=2048)
    parser.add_argument("--inter", type=int, default=128)
    parser.add_argument("--experts", type=int, default=256)
    parser.add_argument("--topk", type=int, default=8)
    parser.add_argument("--topk-dtype",
                        choices=("int64", "int32"),
                        default="int64")
    parser.add_argument("--prewarm-rows", type=int, default=0)
    parser.add_argument("--prewarm-repeats", type=int, default=1)
    parser.add_argument("--seed", type=int, default=20260615)
    parser.add_argument("--kernel-repo", type=Path, default=DEFAULT_KERNEL_REPO)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--md-out", type=Path)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--timeout", type=float, default=240.0)
    parser.add_argument("--no-post-copy", action="store_true")
    parser.add_argument(
        "--endpoint-context",
        action="store_true",
        help=(
            "Wrap the prologue/layerlet call in endpoint-like neighboring "
            "ops: shared-expert GEMMs, shared+routed combine, residual/RMS "
            "normalization, and next-layer int8 projections."
        ),
    )
    parser.add_argument(
        "--compile-wrapper",
        action="store_true",
        help=(
            "Run the layer stack through torch.compile before XPU graph "
            "capture. This more closely models the vLLM PIECEWISE capture "
            "path than raw eager ops."
        ),
    )
    parser.add_argument(
        "--workspace-manager",
        action="store_true",
        help=(
            "Allocate per-layer scratch through vLLM's WorkspaceManager. "
            "This models the real moe_forward_shared custom-op path more "
            "closely than static tensors owned by the reduced repro."
        ),
    )
    parser.add_argument(
        "--custom-op-wrapper",
        action="store_true",
        help=(
            "Call the MoE body through a local torch custom op that mirrors "
            "vLLM's moe_forward_shared boundary. This keeps the reduced "
            "kernel sequence but makes Dynamo/XPU graph capture see an "
            "opaque op like the real endpoint."
        ),
    )
    return parser.parse_args()


def add_kernel_repo_to_path(kernel_repo: Path) -> None:
    repo = str(kernel_repo)
    if repo not in sys.path:
        sys.path.insert(0, repo)


def align_256(size: int) -> int:
    return (size + 255) & ~255


def ceil_div(a: int, b: int) -> int:
    return (a + b - 1) // b


def compute_num_tokens_per_block(num_tokens: int,
                                 num_experts_per_node: int) -> int:
    for block in (32, 64, 128, 256, 512, 1024):
        if ceil_div(num_tokens, block) * num_experts_per_node <= block:
            return block
    return 1024


def make_workspace_layout(torch: Any, *, rows: int, hidden: int, inter: int,
                          experts: int, topk: int,
                          dtype: Any) -> tuple[dict[str, tuple[int, int]], int]:
    num_moe_inputs = rows * topk
    num_tokens_per_block = compute_num_tokens_per_block(rows, experts)
    num_blocks_per_seq = ceil_div(rows, num_tokens_per_block)
    dtype_size = torch.empty((), dtype=dtype).element_size()
    sizes = {
        "permuted_row_to_unpermuted_row":
        num_moe_inputs * 4,
        "permuted_token_selected_experts":
        num_moe_inputs * 4,
        "unpermuted_row_to_permuted_row":
        num_moe_inputs * 4,
        "blocked_expert_counts":
        experts * num_blocks_per_seq * 4,
        "blocked_expert_counts_cumsum":
        experts * num_blocks_per_seq * 4,
        "blocked_row_to_unpermuted_row":
        experts * rows * 4,
        "expert_first_token_offset":
        (experts + 1) * 8,
        "permuted_token_final_scales":
        num_moe_inputs * 4,
        "overlapped_gemm1_gemm2_inputs":
        num_moe_inputs * hidden * dtype_size,
    }
    layout: dict[str, tuple[int, int]] = {}
    offset = 0
    for name, size in sizes.items():
        aligned = align_256(size)
        layout[name] = (offset, aligned)
        offset += aligned
    return layout, offset


def workspace_view(torch: Any, workspace: Any, layout: dict[str, tuple[int, int]],
                   name: str, dtype: Any, shape: tuple[int, ...]) -> Any:
    offset, _ = layout[name]
    elems = 1
    for dim in shape:
        elems *= dim
    bytes_needed = elems * torch.empty((), dtype=dtype).element_size()
    return workspace[offset:offset + bytes_needed].view(dtype).view(*shape)


def selected_experts(rank: int, experts: int, topk: int) -> list[int]:
    base = (3, 17, 42, 64, 101, 149, 203, 241)
    return [int((value + rank * 11) % experts) for value in base[:topk]]


def make_case_tensors(torch: Any,
                      args: argparse.Namespace,
                      rank: int,
                      device: str,
                      *,
                      rows_override: int | None = None) -> dict[str, Any]:
    dtype = torch.bfloat16
    rows = args.rows if rows_override is None else rows_override
    hidden = args.hidden
    inter = args.inter
    experts = args.experts
    topk = args.topk
    num_moe_inputs = rows * topk
    layout, workspace_bytes = make_workspace_layout(
        torch,
        rows=rows,
        hidden=hidden,
        inter=inter,
        experts=experts,
        topk=topk,
        dtype=dtype,
    )
    generator = torch.Generator(device=device)
    generator.manual_seed(args.seed + rank)
    topk_dtype = torch.int64 if args.topk_dtype == "int64" else torch.int32
    topk_ids = torch.tensor(
        [selected_experts(rank + row, experts, topk) for row in range(rows)],
        dtype=topk_dtype,
        device=device,
    )
    topk_weights = torch.rand((rows, topk),
                              generator=generator,
                              dtype=torch.float32,
                              device=device)
    topk_weights = topk_weights / topk_weights.sum(dim=-1, keepdim=True)
    workspace = torch.empty((workspace_bytes,), dtype=torch.uint8, device=device)
    remapped = workspace_view(torch, workspace, layout,
                              "overlapped_gemm1_gemm2_inputs", dtype,
                              (num_moe_inputs, hidden))
    offsets = workspace_view(torch, workspace, layout,
                             "expert_first_token_offset", torch.int64,
                             (experts + 1,))
    tensors = {
        "hidden_states":
        torch.randn((rows, hidden), generator=generator, dtype=dtype,
                    device=device),
        "topk_ids":
        topk_ids,
        "topk_weights":
        topk_weights,
        "workspace":
        workspace,
        "remapped":
        remapped,
        "offsets":
        offsets,
        "gemm1_a":
        torch.empty((num_moe_inputs, hidden), dtype=torch.int8, device=device),
        "gemm1_a_scales":
        torch.empty((num_moe_inputs, 1), dtype=torch.float32, device=device),
        "w13":
        torch.randint(-4,
                      4,
                      (experts, hidden, 2 * inter),
                      generator=generator,
                      dtype=torch.int8,
                      device=device),
        "w13_scales":
        torch.rand((experts, 2 * inter),
                   generator=generator,
                   dtype=torch.float32,
                   device=device) * 0.004 + 0.001,
        "gemm1_output":
        torch.empty((num_moe_inputs, 2 * inter), dtype=dtype, device=device),
        "gemm2_a":
        torch.empty((num_moe_inputs, inter), dtype=torch.int8, device=device),
        "gemm2_a_scales":
        torch.empty((num_moe_inputs, 1), dtype=torch.float32, device=device),
        "w2":
        torch.randint(-4,
                      4,
                      (experts, inter, hidden),
                      generator=generator,
                      dtype=torch.int8,
                      device=device),
        "w2_scales":
        torch.rand((experts, hidden),
                   generator=generator,
                   dtype=torch.float32,
                   device=device) * 0.004 + 0.001,
        "output":
        torch.empty((num_moe_inputs, hidden), dtype=dtype, device=device),
        "routed_reduced":
        torch.empty((rows, hidden), dtype=dtype, device=device),
    }
    if args.endpoint_context:
        # Qwen3.6's endpoint-failing PIECEWISE segment contains more than the
        # prologue.  It also has shared-expert work, the shared+routed combine,
        # a residual/norm boundary, and the next layer's input projection.  This
        # block models that adjacency while keeping the reproducer independent
        # from vLLM's full module and distributed setup.
        shared_inter = max(1, inter * 4)
        tensors.update({
            "residual":
            torch.randn((rows, hidden),
                        generator=generator,
                        dtype=dtype,
                        device=device),
            "post_attn_norm_weight":
            torch.rand((hidden,),
                       generator=generator,
                       dtype=dtype,
                       device=device),
            "next_input_norm_weight":
            torch.rand((hidden,),
                       generator=generator,
                       dtype=dtype,
                       device=device),
            "shared_w13":
            torch.randint(-4,
                          4,
                          (hidden, 2 * shared_inter),
                          generator=generator,
                          dtype=torch.int8,
                          device=device),
            "shared_w13_scales":
            torch.rand((2 * shared_inter,),
                       generator=generator,
                       dtype=torch.float32,
                       device=device) * 0.004 + 0.001,
            "shared_act":
            torch.empty((rows, shared_inter), dtype=dtype, device=device),
            "shared_q":
            torch.empty((rows, shared_inter), dtype=torch.int8, device=device),
            "shared_q_scales":
            torch.empty((rows, 1), dtype=torch.float32, device=device),
            "shared_w2":
            torch.randint(-4,
                          4,
                          (shared_inter, hidden),
                          generator=generator,
                          dtype=torch.int8,
                          device=device),
            "shared_w2_scales":
            torch.rand((hidden,),
                       generator=generator,
                       dtype=torch.float32,
                       device=device) * 0.004 + 0.001,
            "shared_output":
            torch.empty((rows, hidden), dtype=dtype, device=device),
            "combined":
            torch.empty((rows, hidden), dtype=dtype, device=device),
            "next_qkvz_w":
            torch.randint(-4,
                          4,
                          (hidden, 3072),
                          generator=generator,
                          dtype=torch.int8,
                          device=device),
            "next_qkvz_scales":
            torch.rand((3072,),
                       generator=generator,
                       dtype=torch.float32,
                       device=device) * 0.004 + 0.001,
            "next_ba_w":
            torch.randint(-4,
                          4,
                          (hidden, 16),
                          generator=generator,
                          dtype=torch.int8,
                          device=device),
            "next_ba_scales":
            torch.rand((16,),
                       generator=generator,
                       dtype=torch.float32,
                       device=device) * 0.004 + 0.001,
        })
    return tensors


def _rms_norm(torch: Any, x: Any, weight: Any, eps: float = 1e-6) -> Any:
    variance = x.float().pow(2).mean(dim=-1, keepdim=True)
    return (x.float() * torch.rsqrt(variance + eps)).to(x.dtype) * weight


def _run_endpoint_context_prefix(torch: Any, tensors: dict[str, Any],
                                 args: argparse.Namespace) -> None:
    if not args.endpoint_context:
        return

    normed = _rms_norm(
        torch,
        tensors["hidden_states"] + tensors["residual"],
        tensors["post_attn_norm_weight"],
    )
    shared_q, shared_q_scales = torch.ops._xpu_C.per_token_quant_int8_xpu(
        normed)
    shared_gate_up = torch.ops._xpu_C.int8_gemm_w8a8(
        shared_q,
        shared_q_scales,
        tensors["shared_w13"],
        tensors["shared_w13_scales"],
        torch.bfloat16,
        None,
    )
    torch.ops._C.silu_and_mul(tensors["shared_act"], shared_gate_up)
    torch.ops._xpu_C.per_token_quant_int8_xpu_out(
        tensors["shared_act"],
        tensors["shared_q"],
        tensors["shared_q_scales"],
    )
    shared_output = torch.ops._xpu_C.int8_gemm_w8a8(
        tensors["shared_q"],
        tensors["shared_q_scales"],
        tensors["shared_w2"],
        tensors["shared_w2_scales"],
        torch.bfloat16,
        None,
    )
    tensors["shared_output"].copy_(shared_output)


def _run_endpoint_context_suffix(torch: Any, tensors: dict[str, Any],
                                 args: argparse.Namespace,
                                 routed_output: Any,
                                 *,
                                 shared_output: Any | None = None,
                                 routed_is_reduced: bool = False) -> Any:
    if not args.endpoint_context:
        return routed_output

    rows = tensors["hidden_states"].shape[0]
    if routed_is_reduced:
        routed = routed_output
    else:
        routed = routed_output.view(rows, args.topk, args.hidden)
        weights = tensors["topk_weights"].to(routed.dtype).unsqueeze(-1)
        routed = (routed * weights).sum(dim=1)
    shared = tensors["shared_output"] if shared_output is None else shared_output
    tensors["combined"].copy_(routed + shared)

    next_norm = _rms_norm(
        torch,
        tensors["combined"] + tensors["residual"],
        tensors["next_input_norm_weight"],
    )
    next_q, next_scales = torch.ops._xpu_C.per_token_quant_int8_xpu(next_norm)
    torch.ops._xpu_C.int8_gemm_w8a8(
        next_q,
        next_scales,
        tensors["next_qkvz_w"],
        tensors["next_qkvz_scales"],
        torch.bfloat16,
        None,
    )
    torch.ops._xpu_C.int8_gemm_w8a8(
        next_q,
        next_scales,
        tensors["next_ba_w"],
        tensors["next_ba_scales"],
        torch.bfloat16,
        None,
    )
    return tensors["combined"]


def workspace_scratch(torch: Any, tensors: dict[str, Any],
                      args: argparse.Namespace) -> dict[str, Any]:
    if not args.workspace_manager:
        return {
            "workspace": tensors["workspace"],
            "remapped": tensors["remapped"],
            "offsets": tensors["offsets"],
            "gemm1_a": tensors["gemm1_a"],
            "gemm1_a_scales": tensors["gemm1_a_scales"],
            "gemm1_output": tensors["gemm1_output"],
            "gemm2_a": tensors["gemm2_a"],
            "gemm2_a_scales": tensors["gemm2_a_scales"],
            "output": tensors["output"],
        }

    from vllm.v1.worker.workspace import current_workspace_manager

    rows = tensors["hidden_states"].shape[0]
    hidden = tensors["hidden_states"].shape[1]
    topk = tensors["topk_ids"].shape[-1]
    num_moe_inputs = rows * topk
    layout, workspace_bytes = make_workspace_layout(
        torch,
        rows=rows,
        hidden=hidden,
        inter=args.inter,
        experts=args.experts,
        topk=topk,
        dtype=tensors["hidden_states"].dtype,
    )
    (
        prologue_workspace,
        gemm1_a,
        gemm1_a_scales,
        gemm1_output,
        _act_output,
        gemm2_a,
        gemm2_a_scales,
        gemm2_output,
        _rows_per_expert,
    ) = current_workspace_manager().get_simultaneous(
        ((workspace_bytes,), torch.uint8),
        ((num_moe_inputs, hidden), torch.int8),
        ((num_moe_inputs, 1), torch.float32),
        ((num_moe_inputs, 2 * args.inter), tensors["hidden_states"].dtype),
        ((num_moe_inputs, args.inter), tensors["hidden_states"].dtype),
        ((num_moe_inputs, args.inter), torch.int8),
        ((num_moe_inputs, 1), torch.float32),
        ((num_moe_inputs, hidden), tensors["hidden_states"].dtype),
        ((args.experts,), torch.int32),
    )
    return {
        "workspace":
        prologue_workspace,
        "remapped":
        workspace_view(torch, prologue_workspace, layout,
                       "overlapped_gemm1_gemm2_inputs",
                       tensors["hidden_states"].dtype,
                       (num_moe_inputs, hidden)),
        "offsets":
        workspace_view(torch, prologue_workspace, layout,
                       "expert_first_token_offset", torch.int64,
                       (args.experts + 1,)),
        "gemm1_a":
        gemm1_a,
        "gemm1_a_scales":
        gemm1_a_scales,
        "gemm1_output":
        gemm1_output,
        "gemm2_a":
        gemm2_a,
        "gemm2_a_scales":
        gemm2_a_scales,
        "output":
        gemm2_output,
    }


def _run_moe_core_unreduced(torch: Any, tensors: dict[str, Any],
                            args: argparse.Namespace) -> Any:
    scratch = workspace_scratch(torch, tensors, args)
    torch.ops._moe_C.fused_moe_prologue(
        input=tensors["hidden_states"],
        input_scales=None,
        token_selected_experts=tensors["topk_ids"],
        token_final_scales=tensors["topk_weights"],
        workspace=scratch["workspace"],
        hidden_size=args.hidden,
        inter_size=args.inter,
        block_k=1,
        ep_rank=0,
        ep_size=1,
        num_experts_on_rank=args.experts,
    )
    torch.ops._xpu_C.per_token_quant_int8_xpu_out(
        scratch["remapped"], scratch["gemm1_a"], scratch["gemm1_a_scales"])
    torch.ops._xpu_C.qwen36_moe_w8a8_middle_layerlet(
        scratch["gemm1_a"],
        scratch["gemm1_a_scales"],
        tensors["w13"],
        tensors["w13_scales"],
        None,
        scratch["gemm1_output"],
        scratch["gemm2_a"],
        scratch["gemm2_a_scales"],
        tensors["w2"],
        tensors["w2_scales"],
        None,
        scratch["output"],
        scratch["offsets"],
        2 * args.inter,
        args.hidden,
        args.hidden,
        args.inter,
        args.experts,
    )
    return scratch["output"]


def run_layer(torch: Any, tensors: dict[str, Any],
              args: argparse.Namespace) -> Any:
    _run_endpoint_context_prefix(torch, tensors, args)
    routed_output = _run_moe_core_unreduced(torch, tensors, args)
    out = _run_endpoint_context_suffix(torch, tensors, args, routed_output)
    tensors["_last_output"] = out
    return out


_CUSTOM_OP_LAYER_TENSORS: list[dict[str, Any]] = []
_CUSTOM_OP_ARGS: argparse.Namespace | None = None
_CUSTOM_OP_LIB: Any | None = None


def register_repro_custom_op(torch: Any, args: argparse.Namespace) -> None:
    global _CUSTOM_OP_ARGS, _CUSTOM_OP_LIB
    if _CUSTOM_OP_LIB is not None:
        _CUSTOM_OP_ARGS = args
        return

    from torch.library import Library
    from vllm.utils.torch_utils import direct_register_custom_op

    globals()["torch"] = torch
    _CUSTOM_OP_ARGS = args
    _CUSTOM_OP_LIB = Library("qwen36_repro", "FRAGMENT")

    def _repro_moe_forward_shared(
        hidden_states: torch.Tensor,
        router_logits: torch.Tensor,
        shared_experts_input: torch.Tensor,
        input_ids: torch.Tensor | None,
        layer_index: int,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        del router_logits, shared_experts_input, input_ids
        assert _CUSTOM_OP_ARGS is not None
        tensors = _CUSTOM_OP_LAYER_TENSORS[int(layer_index)]
        old_hidden_states = tensors["hidden_states"]
        tensors["hidden_states"] = hidden_states
        try:
            _run_endpoint_context_prefix(torch, tensors, _CUSTOM_OP_ARGS)
            routed_unreduced = _run_moe_core_unreduced(
                torch, tensors, _CUSTOM_OP_ARGS)
            rows = hidden_states.shape[0]
            routed = routed_unreduced.view(rows, _CUSTOM_OP_ARGS.topk,
                                           _CUSTOM_OP_ARGS.hidden)
            weights = tensors["topk_weights"].to(routed.dtype).unsqueeze(-1)
            tensors["routed_reduced"].copy_((routed * weights).sum(dim=1))
            shared = (
                tensors["shared_output"]
                if _CUSTOM_OP_ARGS.endpoint_context else hidden_states)
            return shared, tensors["routed_reduced"]
        finally:
            tensors["hidden_states"] = old_hidden_states

    def _repro_moe_forward_shared_fake(
        hidden_states: torch.Tensor,
        router_logits: torch.Tensor,
        shared_experts_input: torch.Tensor,
        input_ids: torch.Tensor | None,
        layer_index: int,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        del router_logits, shared_experts_input, input_ids, layer_index
        return torch.empty_like(hidden_states), torch.empty_like(hidden_states)

    direct_register_custom_op(
        op_name="moe_forward_shared",
        op_func=_repro_moe_forward_shared,
        fake_impl=_repro_moe_forward_shared_fake,
        target_lib=_CUSTOM_OP_LIB,
        tags=(torch.Tag.needs_fixed_stride_order,),
    )


def run_layer_custom_op(torch: Any, tensors: dict[str, Any],
                        args: argparse.Namespace, layer_index: int) -> Any:
    shared_output, routed_output = torch.ops.qwen36_repro.moe_forward_shared(
        tensors["hidden_states"],
        tensors["hidden_states"],
        tensors["hidden_states"],
        None,
        layer_index,
    )
    out = _run_endpoint_context_suffix(
        torch,
        tensors,
        args,
        routed_output,
        shared_output=shared_output,
        routed_is_reduced=True,
    )
    tensors["_last_output"] = out
    return out


def run_rank(rank: int, args: argparse.Namespace, barrier: Any,
             queue: Any) -> None:
    result: dict[str, Any] = {
        "rank": rank,
        "status": "unknown",
        "captures_completed": 0,
        "replays_completed": 0,
    }
    try:
        add_kernel_repo_to_path(args.kernel_repo)
        import numpy as np
        import torch
        import vllm_xpu_kernels._C  # noqa: F401
        import vllm_xpu_kernels._moe_C  # noqa: F401
        import vllm_xpu_kernels._xpu_C  # noqa: F401

        if not torch.xpu.is_available():
            raise RuntimeError("torch.xpu is not available")
        torch.xpu.set_device(rank)
        device = f"xpu:{rank}"
        if args.workspace_manager:
            from vllm.v1.worker.workspace import (
                init_workspace_manager,
                reset_workspace_manager,
            )

            reset_workspace_manager()
            init_workspace_manager(torch.device(device))
        if args.distinct_layers:
            layer_tensors = [
                make_case_tensors(torch, args, rank * 1000 + layer, device)
                for layer in range(args.layers_per_capture)
            ]
        else:
            tensors = make_case_tensors(torch, args, rank, device)
            layer_tensors = [tensors for _ in range(args.layers_per_capture)]
        if args.custom_op_wrapper:
            global _CUSTOM_OP_LAYER_TENSORS
            _CUSTOM_OP_LAYER_TENSORS = layer_tensors
            register_repro_custom_op(torch, args)
        if args.prewarm_rows > 0:
            prewarm_tensors = make_case_tensors(
                torch,
                args,
                rank,
                device,
                rows_override=args.prewarm_rows,
            )
            for _ in range(args.prewarm_repeats):
                run_layer(torch, prewarm_tensors, args)
            torch.xpu.synchronize()
        dummy = torch.zeros((1,), dtype=torch.float32, device=device)

        def run_stack() -> Any:
            last_output = None
            for layer_index, tensors in enumerate(layer_tensors):
                if args.custom_op_wrapper:
                    last_output = run_layer_custom_op(torch, tensors, args,
                                                      layer_index)
                else:
                    last_output = run_layer(torch, tensors, args)
            assert last_output is not None
            return last_output + dummy.to(last_output.dtype).sum() * 0

        if args.compile_wrapper:
            run_stack_impl = torch.compile(
                run_stack,
                fullgraph=False,
                dynamic=False,
            )
        else:
            run_stack_impl = run_stack

        for _ in range(3):
            run_stack_impl()
        torch.xpu.synchronize()
        barrier.wait(args.timeout)

        graphs = []
        for capture_index in range(args.captures):
            graph = torch.xpu.XPUGraph()
            with torch.xpu.graph(graph):
                run_stack_impl()
            torch.xpu.synchronize()
            graphs.append(graph)
            result["captures_completed"] = capture_index + 1
            if not args.no_post_copy:
                probe = torch.from_numpy(np.arange(16, dtype=np.int64)).to(
                    device=device)
                result["post_copy_checksum"] = int(probe.sum().cpu().item())

        for replay_index in range(args.replays):
            for graph in graphs:
                graph.replay()
            torch.xpu.synchronize()
            result["replays_completed"] = replay_index + 1

        result.update({
            "status": "pass",
            "device": str(torch.xpu.get_device_name(rank)),
            "output_checksum": float(
                layer_tensors[-1]["_last_output"].float().sum().cpu().item()),
        })
    except Exception as exc:  # noqa: BLE001 - script reports reducer errors.
        result.update({
            "status": "fail",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        })
    queue.put(result)


def write_artifacts(args: argparse.Namespace, report: dict[str, Any]) -> None:
    args.data_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_out = args.json_out or (
        args.data_dir / f"qwen36-prologue-tp4-capture-repro-{stamp}.json")
    md_out = args.md_out or (
        args.data_dir / f"qwen36-prologue-tp4-capture-repro-{stamp}.md")
    json_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    lines = [
        "# Qwen3.6 Prologue TP Capture Repro",
        "",
        f"- overall_status: `{report['overall_status']}`",
        f"- ranks: `{report['config']['ranks']}`",
        f"- captures: `{report['config']['captures']}`",
        f"- layers_per_capture: `{report['config']['layers_per_capture']}`",
        f"- distinct_layers: `{report['config']['distinct_layers']}`",
        f"- endpoint_context: `{report['config']['endpoint_context']}`",
        f"- workspace_manager: `{report['config']['workspace_manager']}`",
        f"- custom_op_wrapper: `{report['config']['custom_op_wrapper']}`",
        f"- post_copy: `{not report['config']['no_post_copy']}`",
        "",
        "| rank | status | captures | replays | error |",
        "| ---: | --- | ---: | ---: | --- |",
    ]
    for item in sorted(report["ranks"], key=lambda row: row["rank"]):
        lines.append("| {rank} | {status} | {captures} | {replays} | {err} |".format(
            rank=item["rank"],
            status=item["status"],
            captures=item.get("captures_completed", 0),
            replays=item.get("replays_completed", 0),
            err=(item.get("error") or "").replace("|", "\\|"),
        ))
    lines.append("")
    md_out.write_text("\n".join(lines))
    report["json_out"] = str(json_out)
    report["md_out"] = str(md_out)


def main() -> int:
    args = parse_args()
    ctx = mp.get_context("spawn")
    barrier = ctx.Barrier(args.ranks)
    queue = ctx.Queue()
    processes = [
        ctx.Process(target=run_rank, args=(rank, args, barrier, queue))
        for rank in range(args.ranks)
    ]
    for process in processes:
        process.start()

    results = []
    for _ in processes:
        results.append(queue.get(timeout=args.timeout))

    for process in processes:
        process.join(timeout=5.0)
        if process.is_alive():
            process.kill()
            process.join(timeout=5.0)

    for process, item in zip(processes, results, strict=False):
        item["exitcode"] = process.exitcode

    report = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "config": {
            "ranks": args.ranks,
            "captures": args.captures,
            "layers_per_capture": args.layers_per_capture,
            "distinct_layers": args.distinct_layers,
            "replays": args.replays,
            "rows": args.rows,
            "hidden": args.hidden,
            "inter": args.inter,
            "experts": args.experts,
            "topk": args.topk,
            "topk_dtype": args.topk_dtype,
            "prewarm_rows": args.prewarm_rows,
            "prewarm_repeats": args.prewarm_repeats,
            "no_post_copy": args.no_post_copy,
            "endpoint_context": args.endpoint_context,
            "compile_wrapper": args.compile_wrapper,
            "workspace_manager": args.workspace_manager,
            "custom_op_wrapper": args.custom_op_wrapper,
            "kernel_repo": str(args.kernel_repo),
            "pid": os.getpid(),
        },
        "ranks": results,
    }
    report["overall_status"] = (
        "pass" if all(item["status"] == "pass" for item in results) else "fail")
    write_artifacts(args, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["overall_status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
