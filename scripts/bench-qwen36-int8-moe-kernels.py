#!/usr/bin/env python3
"""Microbenchmark Qwen3.6 W8A8 INT8 MoE kernel stages on XPU.

This is a kernel-level diagnostic for the Quark W8A8 INT8 path used by the
Qwen3.6 35B-A3B profile. It does not benchmark full model quality or service
latency; use it to decide which exact-preserving MoE subpath is worth attacking
next.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

import torch

import vllm_xpu_kernels._moe_C  # noqa: F401
from vllm_xpu_kernels.fused_moe_interface import (
    _normalize_int8_weight_scales,
    _per_token_quant_int8,
    fused_moe_activation,
    xpu_fused_moe,
)


DEFAULT_MODEL_CONFIG = (
    "/mnt/fast-ai/llm-cache/hf/models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8/"
    "snapshots/cced56592e8c8935f8220836b4baa04dfd389118/config.json"
)


def parse_rows(value: str) -> list[int]:
    rows = []
    for item in value.split(","):
        item = item.strip()
        if item:
            rows.append(int(item))
    if not rows:
        raise argparse.ArgumentTypeError("at least one row count is required")
    return rows


def parse_int_list(value: str) -> list[int]:
    values: list[int] = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        if ":" in item:
            parts = item.split(":")
            if len(parts) not in (2, 3):
                raise argparse.ArgumentTypeError(
                    f"Invalid integer range {item!r}; use start:stop[:step]")
            start = int(parts[0])
            stop = int(parts[1])
            step = int(parts[2]) if len(parts) == 3 else 1
            if step == 0:
                raise argparse.ArgumentTypeError("range step cannot be zero")
            values.extend(range(start, stop, step))
        else:
            values.append(int(item))
    if not values:
        raise argparse.ArgumentTypeError("at least one integer is required")
    return values


def load_text_config(path: str) -> dict[str, Any]:
    cfg = json.loads(Path(path).read_text())
    text_config = cfg.get("text_config")
    if not isinstance(text_config, dict):
        raise ValueError(f"Missing text_config in {path}")
    return text_config


def load_route_topk_rows(
    path: str | None,
    *,
    layer_regex: str | None,
    stage_regex: str | None,
    min_num_tokens: int | None,
    max_num_tokens: int | None,
) -> tuple[list[list[int]], dict[str, Any] | None]:
    if not path:
        return [], None

    layer_pattern = re.compile(layer_regex) if layer_regex else None
    stage_pattern = re.compile(stage_regex) if stage_regex else None
    rows: list[list[int]] = []
    layers: dict[str, int] = {}
    stages: dict[str, int] = {}
    loaded = 0
    matched = 0

    with Path(path).open() as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            loaded += 1
            record = json.loads(line)
            layer = str(record.get("layer") or "")
            stage = str(record.get("stage") or "")
            if layer_pattern and not layer_pattern.search(layer):
                continue
            if stage_pattern and not stage_pattern.search(stage):
                continue
            num_tokens = int(record.get("num_tokens") or 0)
            if min_num_tokens is not None and num_tokens < min_num_tokens:
                continue
            if max_num_tokens is not None and num_tokens > max_num_tokens:
                continue
            topk_ids = record.get("topk_ids")
            if not isinstance(topk_ids, list):
                continue
            matched += 1
            layers[layer] = layers.get(layer, 0) + 1
            stages[stage] = stages.get(stage, 0) + 1
            for row in topk_ids:
                if not isinstance(row, list):
                    continue
                rows.append([int(item) for item in row])

    if not rows:
        raise ValueError(f"No topk_ids matched route filters in {path}")

    tuple_counts: dict[tuple[int, ...], int] = {}
    expert_counts: dict[int, int] = {}
    for row in rows:
        tuple_counts[tuple(row)] = tuple_counts.get(tuple(row), 0) + 1
        for expert in row:
            expert_counts[expert] = expert_counts.get(expert, 0) + 1

    metadata = {
        "route_jsonl": path,
        "records_loaded": loaded,
        "records_matched": matched,
        "topk_rows_loaded": len(rows),
        "layers": dict(sorted(layers.items())),
        "stages": dict(sorted(stages.items())),
        "unique_topk_tuples": len(tuple_counts),
        "active_experts": len(expert_counts),
        "top_experts": [
            {"expert": expert, "count": count}
            for expert, count in sorted(
                expert_counts.items(), key=lambda item: item[1], reverse=True
            )[:16]
        ],
    }
    return rows, metadata


def pack_hot_route_experts(
    rows: list[list[int]],
    *,
    num_experts: int,
) -> tuple[list[list[int]], dict[str, Any]]:
    expert_counts: dict[int, int] = {}
    for row in rows:
        for expert in row:
            expert_counts[expert] = expert_counts.get(expert, 0) + 1

    hot_experts = [
        expert for expert, _ in sorted(
            expert_counts.items(), key=lambda item: item[1], reverse=True)
    ]
    cold_experts = [
        expert for expert in range(num_experts) if expert not in expert_counts
    ]
    physical_order = hot_experts + cold_experts
    logical_to_physical = {
        logical: physical for physical, logical in enumerate(physical_order)
    }
    packed = [
        [logical_to_physical[int(expert)] for expert in row]
        for row in rows
    ]
    metadata = {
        "enabled": True,
        "active_experts": len(hot_experts),
        "top_logical_to_physical": [
            {
                "logical_expert": expert,
                "physical_expert": logical_to_physical[expert],
                "count": expert_counts[expert],
            }
            for expert in hot_experts[:16]
        ],
    }
    return packed, metadata


def elapsed_us(start: torch.xpu.Event, end: torch.xpu.Event) -> float:
    return float(start.elapsed_time(end) * 1000.0)


def ceil_div(a: int, b: int) -> int:
    return (a + b - 1) // b


def compute_num_tokens_per_block(num_tokens: int,
                                 num_experts_per_node: int) -> int:
    for num_tokens_per_block in [32, 64, 128, 256, 512, 1024]:
        num_blocks_per_seq = ceil_div(num_tokens, num_tokens_per_block)
        if num_blocks_per_seq * num_experts_per_node <= num_tokens_per_block:
            return num_tokens_per_block
    return 1024


def align_256(size: int) -> int:
    return (size + 255) & ~255


def make_prologue_workspace_layout(
    *,
    rows: int,
    hidden_size: int,
    inter_size: int,
    num_experts: int,
    topk: int,
    dtype: torch.dtype,
    block_k: int = 1,
    scale_dtype: torch.dtype | None = None,
) -> tuple[dict[str, tuple[int, int]], int]:
    num_moe_inputs = rows * topk
    num_tokens_per_block = compute_num_tokens_per_block(rows, num_experts)
    num_blocks_per_seq = ceil_div(rows, num_tokens_per_block)

    sizes = {
        "permuted_row_to_unpermuted_row": num_moe_inputs * 4,
        "permuted_token_selected_experts": num_moe_inputs * 4,
        "unpermuted_row_to_permuted_row": num_moe_inputs * 4,
        "blocked_expert_counts": num_experts * num_blocks_per_seq * 4,
        "blocked_expert_counts_cumsum": num_experts * num_blocks_per_seq * 4,
        "blocked_row_to_unpermuted_row": num_experts * rows * 4,
        "expert_first_token_offset": (num_experts + 1) * 8,
        "permuted_token_final_scales": num_moe_inputs * 4,
        "overlapped_gemm1_gemm2_inputs":
        num_moe_inputs * hidden_size *
        torch.tensor([], dtype=dtype).element_size(),
        "permuted_act_scales": 0
        if scale_dtype is None else num_moe_inputs *
        (hidden_size // block_k) *
        torch.tensor([], dtype=scale_dtype).element_size(),
    }

    layout: dict[str, tuple[int, int]] = {}
    offset = 0
    for name, size in sizes.items():
        aligned = align_256(size)
        layout[name] = (offset, aligned)
        offset += aligned
    return layout, offset


def workspace_view(
    workspace: torch.Tensor,
    layout: dict[str, tuple[int, int]],
    name: str,
    dtype: torch.dtype,
    shape: tuple[int, ...],
) -> torch.Tensor:
    offset, _ = layout[name]
    elems = 1
    for dim in shape:
        elems *= dim
    bytes_needed = elems * torch.tensor([], dtype=dtype).element_size()
    segment = workspace[offset:offset + bytes_needed]
    return segment.view(dtype).view(*shape)


def make_prologue_scratch(
    *,
    rows: int,
    hidden_size: int,
    inter_size: int,
    num_experts: int,
    topk: int,
    dtype: torch.dtype,
    device: str,
) -> dict[str, Any]:
    layout, workspace_bytes = make_prologue_workspace_layout(
        rows=rows,
        hidden_size=hidden_size,
        inter_size=inter_size,
        num_experts=num_experts,
        topk=topk,
        dtype=dtype,
    )
    workspace = torch.empty((workspace_bytes), dtype=torch.uint8, device=device)
    num_moe_inputs = rows * topk
    return {
        "workspace": workspace,
        "workspace_bytes": workspace_bytes,
        "layout": layout,
        "remapped_hidden_states": workspace_view(
            workspace,
            layout,
            "overlapped_gemm1_gemm2_inputs",
            dtype,
            (num_moe_inputs, hidden_size),
        ),
        "unpermuted": workspace_view(
            workspace,
            layout,
            "unpermuted_row_to_permuted_row",
            torch.int32,
            (rows, topk),
        ),
        "expert_offsets": workspace_view(
            workspace,
            layout,
            "expert_first_token_offset",
            torch.int64,
            (num_experts + 1,),
        ),
        "rows_per_expert": torch.empty((num_experts),
                                       device=device,
                                       dtype=torch.int32),
        "output": torch.empty((rows, hidden_size), device=device, dtype=dtype),
        "gemm1_output": torch.empty((num_moe_inputs, 2 * inter_size),
                                    device=device,
                                    dtype=dtype),
        "act_output": torch.empty((num_moe_inputs, inter_size),
                                  device=device,
                                  dtype=dtype),
        "gemm2_output": torch.empty((num_moe_inputs, hidden_size),
                                    device=device,
                                    dtype=dtype),
    }


def make_events() -> tuple[torch.xpu.Event, torch.xpu.Event]:
    return (
        torch.xpu.Event(enable_timing=True),
        torch.xpu.Event(enable_timing=True),
    )


def record_call(fn):
    start, end = make_events()
    start.record()
    result = fn()
    end.record()
    return result, start, end


def make_inputs(
    *,
    rows: int,
    hidden_size: int,
    inter_size: int,
    num_experts: int,
    topk: int,
    dtype: torch.dtype,
    device: str,
    seed: int,
    route_topk_rows: list[list[int]] | None = None,
    route_start_index: int = 0,
) -> dict[str, torch.Tensor]:
    torch.manual_seed(seed)
    hidden_states = torch.randn(
        (rows, hidden_size), device=device, dtype=dtype) / 16
    w13 = torch.randint(
        -127,
        128,
        (num_experts, hidden_size, 2 * inter_size),
        device=device,
        dtype=torch.int8,
    ).contiguous()
    w2 = torch.randint(
        -127,
        128,
        (num_experts, inter_size, hidden_size),
        device=device,
        dtype=torch.int8,
    ).contiguous()

    w13_scales = (
        torch.rand((num_experts, 2 * inter_size),
                   device=device,
                   dtype=torch.float32) * 0.02 + 0.001
    ).contiguous()
    w2_scales = (
        torch.rand((num_experts, hidden_size),
                   device=device,
                   dtype=torch.float32) * 0.02 + 0.001
    ).contiguous()

    if route_topk_rows:
        selected_rows = [
            route_topk_rows[(route_start_index + index) % len(route_topk_rows)]
            for index in range(rows)
        ]
        if any(len(row) != topk for row in selected_rows):
            raise ValueError(
                f"Route topk row width does not match model topk={topk}")
        if any(expert < 0 or expert >= num_experts
               for row in selected_rows for expert in row):
            raise ValueError(
                f"Route topk IDs contain expert outside [0, {num_experts})")
        topk_ids = torch.tensor(selected_rows,
                                device=device,
                                dtype=torch.int64)
    else:
        topk_ids = (
            torch.arange(rows * topk, device=device, dtype=torch.int64) %
            num_experts
        ).view(rows, topk)
    topk_weights = torch.rand((rows, topk),
                              device=device,
                              dtype=torch.float32)
    topk_weights = torch.softmax(topk_weights, dim=-1).contiguous()

    return {
        "hidden_states": hidden_states.contiguous(),
        "w13": w13,
        "w13_scales": w13_scales,
        "w2": w2,
        "w2_scales": w2_scales,
        "topk_ids": topk_ids.contiguous(),
        "topk_weights": topk_weights,
    }


def manual_int8_moe_once(
    *,
    hidden_states: torch.Tensor,
    w13: torch.Tensor,
    w13_scales: torch.Tensor,
    w2: torch.Tensor,
    w2_scales: torch.Tensor,
    topk_weights: torch.Tensor,
    topk_ids: torch.Tensor,
    num_experts: int,
    topk: int,
) -> tuple[torch.Tensor, dict[str, tuple[torch.xpu.Event, torch.xpu.Event]]]:
    num_rows, hidden_size = hidden_states.shape
    inter_size = w13.shape[-1] // 2
    num_moe_inputs = topk * num_rows
    events: dict[str, tuple[torch.xpu.Event, torch.xpu.Event]] = {}

    output = torch.empty_like(hidden_states)
    gemm1_output = torch.empty((num_moe_inputs, 2 * inter_size),
                               dtype=hidden_states.dtype,
                               device=hidden_states.device)
    remapped_hidden_states = torch.empty((num_moe_inputs, hidden_size),
                                         dtype=hidden_states.dtype,
                                         device=hidden_states.device)
    rows_per_expert = torch.empty((num_experts),
                                  dtype=torch.int32,
                                  device=hidden_states.device)
    unpermuted = torch.empty((num_rows, topk),
                             dtype=torch.int32,
                             device=hidden_states.device)

    _, start, end = record_call(lambda: rows_per_expert.zero_())
    events["rows_zero"] = (start, end)

    _, start, end = record_call(
        lambda: torch.ops._moe_C.remap_hidden_states(
            hidden_states=hidden_states,
            hidden_states_scales=None,
            remapped_hidden_states=remapped_hidden_states,
            remapped_hidden_states_scales=None,
            expert_map=None,
            rows_per_expert=rows_per_expert,
            unpermuted_row_to_permuted_row=unpermuted,
            topk_ids=topk_ids,
            total_experts_num=num_experts,
            local_experts_num=num_experts,
        ))
    events["remap"] = (start, end)

    (gemm1_a, gemm1_a_scales), start, end = record_call(
        lambda: _per_token_quant_int8(remapped_hidden_states))
    events["quant1"] = (start, end)

    gemm1_scales = _normalize_int8_weight_scales(w13_scales, 2 * inter_size)
    _, start, end = record_call(
        lambda: torch.ops._xpu_C.cutlass_grouped_gemm_w8a8_int8_interface(
            ptr_A=gemm1_a,
            ptr_A_scales=gemm1_a_scales,
            ptr_B=w13,
            ptr_B_scales=gemm1_scales,
            ptr_bias=None,
            ptr_D=gemm1_output,
            rows_per_expert=rows_per_expert,
            N=2 * inter_size,
            K=hidden_size,
            num_experts=num_experts,
        ))
    events["gemm1"] = (start, end)

    act_output = torch.empty((num_moe_inputs, inter_size),
                             dtype=gemm1_output.dtype,
                             device=gemm1_output.device)
    _, start, end = record_call(
        lambda: fused_moe_activation(act_output, gemm1_output, "silu"))
    events["activation"] = (start, end)

    act_contiguous, start, end = record_call(lambda: act_output.contiguous())
    events["act_contiguous"] = (start, end)

    (gemm2_a, gemm2_a_scales), start, end = record_call(
        lambda: _per_token_quant_int8(act_contiguous))
    events["quant2"] = (start, end)

    gemm2_output = torch.empty((num_moe_inputs, hidden_size),
                               dtype=hidden_states.dtype,
                               device=hidden_states.device)
    gemm2_scales = _normalize_int8_weight_scales(w2_scales, hidden_size)
    _, start, end = record_call(
        lambda: torch.ops._xpu_C.cutlass_grouped_gemm_w8a8_int8_interface(
            ptr_A=gemm2_a,
            ptr_A_scales=gemm2_a_scales,
            ptr_B=w2,
            ptr_B_scales=gemm2_scales,
            ptr_bias=None,
            ptr_D=gemm2_output,
            rows_per_expert=rows_per_expert,
            N=hidden_size,
            K=inter_size,
            num_experts=num_experts,
        ))
    events["gemm2"] = (start, end)

    _, start, end = record_call(
        lambda: torch.ops._moe_C.moe_gather(output, gemm2_output,
                                           topk_weights, unpermuted,
                                           num_experts))
    events["gather"] = (start, end)

    return output, events


def make_scratch(
    *,
    rows: int,
    hidden_size: int,
    inter_size: int,
    num_experts: int,
    topk: int,
    dtype: torch.dtype,
    device: str,
) -> dict[str, torch.Tensor]:
    num_moe_inputs = rows * topk
    return {
        "output": torch.empty((rows, hidden_size), device=device, dtype=dtype),
        "gemm1_output": torch.empty((num_moe_inputs, 2 * inter_size),
                                    device=device,
                                    dtype=dtype),
        "act_output": torch.empty((num_moe_inputs, inter_size),
                                  device=device,
                                  dtype=dtype),
        "gemm2_output": torch.empty((num_moe_inputs, hidden_size),
                                    device=device,
                                    dtype=dtype),
        "remapped_hidden_states": torch.empty((num_moe_inputs, hidden_size),
                                              device=device,
                                              dtype=dtype),
        "rows_per_expert": torch.empty((num_experts),
                                       device=device,
                                       dtype=torch.int32),
        "unpermuted": torch.empty((rows, topk),
                                  device=device,
                                  dtype=torch.int32),
    }


def make_xpu_scratch(scratch: dict[str, torch.Tensor]) -> dict[str, torch.Tensor]:
    """Adapt the manual scratch dict to xpu_fused_moe's scratch schema."""
    return {
        "remapped_hidden_states": scratch["remapped_hidden_states"],
        "gemm1_output": scratch["gemm1_output"],
        "act_output": scratch["act_output"],
        "gemm2_output": scratch["gemm2_output"],
        "rows_per_expert": scratch["rows_per_expert"],
        "unpermuted_row_to_permuted_row": scratch["unpermuted"],
    }


def manual_int8_moe_preallocated_once(
    *,
    hidden_states: torch.Tensor,
    w13: torch.Tensor,
    w13_scales: torch.Tensor,
    w2: torch.Tensor,
    w2_scales: torch.Tensor,
    topk_weights: torch.Tensor,
    topk_ids: torch.Tensor,
    num_experts: int,
    topk: int,
    scratch: dict[str, torch.Tensor],
) -> torch.Tensor:
    hidden_size = hidden_states.shape[1]
    inter_size = w13.shape[-1] // 2
    rows_per_expert = scratch["rows_per_expert"]
    rows_per_expert.zero_()

    torch.ops._moe_C.remap_hidden_states(
        hidden_states=hidden_states,
        hidden_states_scales=None,
        remapped_hidden_states=scratch["remapped_hidden_states"],
        remapped_hidden_states_scales=None,
        expert_map=None,
        rows_per_expert=rows_per_expert,
        unpermuted_row_to_permuted_row=scratch["unpermuted"],
        topk_ids=topk_ids,
        total_experts_num=num_experts,
        local_experts_num=num_experts,
    )
    gemm1_a, gemm1_a_scales = _per_token_quant_int8(
        scratch["remapped_hidden_states"])
    gemm1_scales = _normalize_int8_weight_scales(w13_scales, 2 * inter_size)
    torch.ops._xpu_C.cutlass_grouped_gemm_w8a8_int8_interface(
        ptr_A=gemm1_a,
        ptr_A_scales=gemm1_a_scales,
        ptr_B=w13,
        ptr_B_scales=gemm1_scales,
        ptr_bias=None,
        ptr_D=scratch["gemm1_output"],
        rows_per_expert=rows_per_expert,
        N=2 * inter_size,
        K=hidden_size,
        num_experts=num_experts,
    )
    fused_moe_activation(scratch["act_output"], scratch["gemm1_output"],
                         "silu")
    gemm2_a, gemm2_a_scales = _per_token_quant_int8(scratch["act_output"])
    gemm2_scales = _normalize_int8_weight_scales(w2_scales, hidden_size)
    torch.ops._xpu_C.cutlass_grouped_gemm_w8a8_int8_interface(
        ptr_A=gemm2_a,
        ptr_A_scales=gemm2_a_scales,
        ptr_B=w2,
        ptr_B_scales=gemm2_scales,
        ptr_bias=None,
        ptr_D=scratch["gemm2_output"],
        rows_per_expert=rows_per_expert,
        N=hidden_size,
        K=inter_size,
        num_experts=num_experts,
    )
    torch.ops._moe_C.moe_gather(scratch["output"], scratch["gemm2_output"],
                                topk_weights, scratch["unpermuted"],
                                num_experts)
    return scratch["output"]


def manual_int8_moe_fused_prologue_once(
    *,
    hidden_states: torch.Tensor,
    w13: torch.Tensor,
    w13_scales: torch.Tensor,
    w2: torch.Tensor,
    w2_scales: torch.Tensor,
    topk_weights: torch.Tensor,
    topk_ids: torch.Tensor,
    num_experts: int,
    topk: int,
    scratch: dict[str, Any],
    use_offset_gemm: bool = False,
) -> torch.Tensor:
    hidden_size = hidden_states.shape[1]
    inter_size = w13.shape[-1] // 2
    offset_op = getattr(
        torch.ops._xpu_C,
        "cutlass_grouped_gemm_w8a8_int8_offsets_interface",
        None,
    )
    if use_offset_gemm and offset_op is None:
        raise RuntimeError(
            "cutlass_grouped_gemm_w8a8_int8_offsets_interface is not available"
        )

    torch.ops._moe_C.fused_moe_prologue(
        input=hidden_states,
        input_scales=None,
        token_selected_experts=topk_ids,
        token_final_scales=topk_weights,
        workspace=scratch["workspace"],
        hidden_size=hidden_size,
        inter_size=inter_size,
        block_k=1,
        ep_rank=0,
        ep_size=1,
        num_experts_on_rank=num_experts,
    )
    expert_offsets = scratch["expert_offsets"]
    if not use_offset_gemm:
        scratch["rows_per_expert"].copy_(
            (expert_offsets[1:1 + num_experts] -
             expert_offsets[:num_experts]).to(torch.int32))

    gemm1_a, gemm1_a_scales = _per_token_quant_int8(
        scratch["remapped_hidden_states"])
    gemm1_scales = _normalize_int8_weight_scales(w13_scales, 2 * inter_size)
    if use_offset_gemm:
        offset_op(
            ptr_A=gemm1_a,
            ptr_A_scales=gemm1_a_scales,
            ptr_B=w13,
            ptr_B_scales=gemm1_scales,
            ptr_bias=None,
            ptr_D=scratch["gemm1_output"],
            expert_first_token_offset=expert_offsets,
            N=2 * inter_size,
            K=hidden_size,
            num_experts=num_experts,
        )
    else:
        torch.ops._xpu_C.cutlass_grouped_gemm_w8a8_int8_interface(
            ptr_A=gemm1_a,
            ptr_A_scales=gemm1_a_scales,
            ptr_B=w13,
            ptr_B_scales=gemm1_scales,
            ptr_bias=None,
            ptr_D=scratch["gemm1_output"],
            rows_per_expert=scratch["rows_per_expert"],
            N=2 * inter_size,
            K=hidden_size,
            num_experts=num_experts,
        )
    fused_moe_activation(scratch["act_output"], scratch["gemm1_output"],
                         "silu")
    gemm2_a, gemm2_a_scales = _per_token_quant_int8(scratch["act_output"])
    gemm2_scales = _normalize_int8_weight_scales(w2_scales, hidden_size)
    if use_offset_gemm:
        offset_op(
            ptr_A=gemm2_a,
            ptr_A_scales=gemm2_a_scales,
            ptr_B=w2,
            ptr_B_scales=gemm2_scales,
            ptr_bias=None,
            ptr_D=scratch["gemm2_output"],
            expert_first_token_offset=expert_offsets,
            N=hidden_size,
            K=inter_size,
            num_experts=num_experts,
        )
    else:
        torch.ops._xpu_C.cutlass_grouped_gemm_w8a8_int8_interface(
            ptr_A=gemm2_a,
            ptr_A_scales=gemm2_a_scales,
            ptr_B=w2,
            ptr_B_scales=gemm2_scales,
            ptr_bias=None,
            ptr_D=scratch["gemm2_output"],
            rows_per_expert=scratch["rows_per_expert"],
            N=hidden_size,
            K=inter_size,
            num_experts=num_experts,
        )
    torch.ops._moe_C.moe_gather(scratch["output"], scratch["gemm2_output"],
                                topk_weights, scratch["unpermuted"],
                                num_experts)
    return scratch["output"]


def summarize_topk_ids(topk_ids: torch.Tensor, topn: int = 16) -> dict[str, Any]:
    topk_cpu = topk_ids.detach().cpu().tolist()
    tuple_counts: dict[tuple[int, ...], int] = {}
    expert_counts: dict[int, int] = {}
    for row in topk_cpu:
        row_tuple = tuple(int(item) for item in row)
        tuple_counts[row_tuple] = tuple_counts.get(row_tuple, 0) + 1
        for expert in row_tuple:
            expert_counts[expert] = expert_counts.get(expert, 0) + 1
    return {
        "unique_topk_tuples": len(tuple_counts),
        "active_experts": len(expert_counts),
        "top_experts": [
            {"expert": expert, "count": count}
            for expert, count in sorted(
                expert_counts.items(), key=lambda item: item[1], reverse=True
            )[:topn]
        ],
        "topk_tuple_examples": [
            {"topk_ids": list(row), "count": count}
            for row, count in sorted(
                tuple_counts.items(), key=lambda item: item[1], reverse=True
            )[:topn]
        ],
    }


def benchmark_rows(
    args,
    text_config: dict[str, Any],
    rows: int,
    route_topk_rows: list[list[int]],
    route_start_index: int,
) -> dict[str, Any]:
    full_hidden_size = int(text_config["hidden_size"])
    full_inter_size = int(text_config["moe_intermediate_size"])
    hidden_size = full_hidden_size
    inter_size = full_inter_size // args.tp_size
    num_experts = int(text_config["num_experts"])
    topk = int(text_config["num_experts_per_tok"])
    dtype = torch.bfloat16 if args.dtype == "bf16" else torch.float16

    inputs = make_inputs(
        rows=rows,
        hidden_size=hidden_size,
        inter_size=inter_size,
        num_experts=num_experts,
        topk=topk,
        dtype=dtype,
        device=args.device,
        seed=args.seed + rows,
        route_topk_rows=route_topk_rows,
        route_start_index=route_start_index,
    )
    topk_summary = summarize_topk_ids(inputs["topk_ids"])

    for _ in range(args.warmup):
        xpu_fused_moe(
            hidden_states=inputs["hidden_states"],
            w13=inputs["w13"],
            w13_scales=inputs["w13_scales"],
            w13_bias=None,
            w2=inputs["w2"],
            w2_scales=inputs["w2_scales"],
            w2_bias=None,
            topk_weights=inputs["topk_weights"],
            topk_ids=inputs["topk_ids"],
            n_experts_per_token=topk,
            activation="silu",
            num_experts=num_experts,
            is_int8=True,
        )
    torch.xpu.synchronize()

    ref_output = xpu_fused_moe(
        hidden_states=inputs["hidden_states"],
        w13=inputs["w13"],
        w13_scales=inputs["w13_scales"],
        w13_bias=None,
        w2=inputs["w2"],
        w2_scales=inputs["w2_scales"],
        w2_bias=None,
        topk_weights=inputs["topk_weights"],
        topk_ids=inputs["topk_ids"],
        n_experts_per_token=topk,
        activation="silu",
        num_experts=num_experts,
        is_int8=True,
    )
    manual_output, _ = manual_int8_moe_once(
        hidden_states=inputs["hidden_states"],
        w13=inputs["w13"],
        w13_scales=inputs["w13_scales"],
        w2=inputs["w2"],
        w2_scales=inputs["w2_scales"],
        topk_weights=inputs["topk_weights"],
        topk_ids=inputs["topk_ids"],
        num_experts=num_experts,
        topk=topk,
    )
    torch.xpu.synchronize()
    max_abs_diff = float((ref_output - manual_output).abs().max().item())

    scratch = make_scratch(
        rows=rows,
        hidden_size=hidden_size,
        inter_size=inter_size,
        num_experts=num_experts,
        topk=topk,
        dtype=dtype,
        device=args.device,
    )
    scratch_output = manual_int8_moe_preallocated_once(
        hidden_states=inputs["hidden_states"],
        w13=inputs["w13"],
        w13_scales=inputs["w13_scales"],
        w2=inputs["w2"],
        w2_scales=inputs["w2_scales"],
        topk_weights=inputs["topk_weights"],
        topk_ids=inputs["topk_ids"],
        num_experts=num_experts,
        topk=topk,
        scratch=scratch,
    )
    torch.xpu.synchronize()
    prealloc_max_abs_diff = float(
        (ref_output - scratch_output).abs().max().item())
    prologue_scratch = make_prologue_scratch(
        rows=rows,
        hidden_size=hidden_size,
        inter_size=inter_size,
        num_experts=num_experts,
        topk=topk,
        dtype=dtype,
        device=args.device,
    )
    prologue_output = manual_int8_moe_fused_prologue_once(
        hidden_states=inputs["hidden_states"],
        w13=inputs["w13"],
        w13_scales=inputs["w13_scales"],
        w2=inputs["w2"],
        w2_scales=inputs["w2_scales"],
        topk_weights=inputs["topk_weights"],
        topk_ids=inputs["topk_ids"],
        num_experts=num_experts,
        topk=topk,
        scratch=prologue_scratch,
    )
    torch.xpu.synchronize()
    prologue_max_abs_diff = float(
        (ref_output - prologue_output).abs().max().item())
    offset_gemm_available = hasattr(
        torch.ops._xpu_C,
        "cutlass_grouped_gemm_w8a8_int8_offsets_interface",
    )
    prologue_offset_max_abs_diff: float | None = None
    if args.enable_offset_gemm:
        prologue_offset_output = manual_int8_moe_fused_prologue_once(
            hidden_states=inputs["hidden_states"],
            w13=inputs["w13"],
            w13_scales=inputs["w13_scales"],
            w2=inputs["w2"],
            w2_scales=inputs["w2_scales"],
            topk_weights=inputs["topk_weights"],
            topk_ids=inputs["topk_ids"],
            num_experts=num_experts,
            topk=topk,
            scratch=prologue_scratch,
            use_offset_gemm=True,
        )
        torch.xpu.synchronize()
        prologue_offset_max_abs_diff = float(
            (ref_output - prologue_offset_output).abs().max().item())
    xpu_scratch_output = xpu_fused_moe(
        hidden_states=inputs["hidden_states"],
        w13=inputs["w13"],
        w13_scales=inputs["w13_scales"],
        w13_bias=None,
        w2=inputs["w2"],
        w2_scales=inputs["w2_scales"],
        w2_bias=None,
        topk_weights=inputs["topk_weights"],
        topk_ids=inputs["topk_ids"],
        n_experts_per_token=topk,
        activation="silu",
        num_experts=num_experts,
        is_int8=True,
        scratch=make_xpu_scratch(scratch),
    )
    torch.xpu.synchronize()
    xpu_scratch_max_abs_diff = float(
        (ref_output - xpu_scratch_output).abs().max().item())

    total_us = []
    scratch_total_us = []
    preallocated_total_us = []
    prologue_preallocated_total_us = []
    prologue_offset_total_us = []
    component_us: dict[str, list[float]] = {
        "rows_zero": [],
        "remap": [],
        "quant1": [],
        "gemm1": [],
        "activation": [],
        "act_contiguous": [],
        "quant2": [],
        "gemm2": [],
        "gather": [],
    }

    for _ in range(args.iterations):
        start, end = make_events()
        start.record()
        xpu_fused_moe(
            hidden_states=inputs["hidden_states"],
            w13=inputs["w13"],
            w13_scales=inputs["w13_scales"],
            w13_bias=None,
            w2=inputs["w2"],
            w2_scales=inputs["w2_scales"],
            w2_bias=None,
            topk_weights=inputs["topk_weights"],
            topk_ids=inputs["topk_ids"],
            n_experts_per_token=topk,
            activation="silu",
            num_experts=num_experts,
            is_int8=True,
        )
        end.record()

        _, events = manual_int8_moe_once(
            hidden_states=inputs["hidden_states"],
            w13=inputs["w13"],
            w13_scales=inputs["w13_scales"],
            w2=inputs["w2"],
            w2_scales=inputs["w2_scales"],
            topk_weights=inputs["topk_weights"],
            topk_ids=inputs["topk_ids"],
            num_experts=num_experts,
            topk=topk,
        )
        torch.xpu.synchronize()
        total_us.append(elapsed_us(start, end))
        for label, (component_start, component_end) in events.items():
            component_us.setdefault(label, []).append(
                elapsed_us(component_start, component_end))

        start, end = make_events()
        start.record()
        xpu_fused_moe(
            hidden_states=inputs["hidden_states"],
            w13=inputs["w13"],
            w13_scales=inputs["w13_scales"],
            w13_bias=None,
            w2=inputs["w2"],
            w2_scales=inputs["w2_scales"],
            w2_bias=None,
            topk_weights=inputs["topk_weights"],
            topk_ids=inputs["topk_ids"],
            n_experts_per_token=topk,
            activation="silu",
            num_experts=num_experts,
            is_int8=True,
            scratch=make_xpu_scratch(scratch),
        )
        end.record()
        torch.xpu.synchronize()
        scratch_total_us.append(elapsed_us(start, end))

        start, end = make_events()
        start.record()
        manual_int8_moe_preallocated_once(
            hidden_states=inputs["hidden_states"],
            w13=inputs["w13"],
            w13_scales=inputs["w13_scales"],
            w2=inputs["w2"],
            w2_scales=inputs["w2_scales"],
            topk_weights=inputs["topk_weights"],
            topk_ids=inputs["topk_ids"],
            num_experts=num_experts,
            topk=topk,
            scratch=scratch,
        )
        end.record()
        torch.xpu.synchronize()
        preallocated_total_us.append(elapsed_us(start, end))

        start, end = make_events()
        start.record()
        manual_int8_moe_fused_prologue_once(
            hidden_states=inputs["hidden_states"],
            w13=inputs["w13"],
            w13_scales=inputs["w13_scales"],
            w2=inputs["w2"],
            w2_scales=inputs["w2_scales"],
            topk_weights=inputs["topk_weights"],
            topk_ids=inputs["topk_ids"],
            num_experts=num_experts,
            topk=topk,
            scratch=prologue_scratch,
        )
        end.record()
        torch.xpu.synchronize()
        prologue_preallocated_total_us.append(elapsed_us(start, end))
        if args.enable_offset_gemm:
            start, end = make_events()
            start.record()
            manual_int8_moe_fused_prologue_once(
                hidden_states=inputs["hidden_states"],
                w13=inputs["w13"],
                w13_scales=inputs["w13_scales"],
                w2=inputs["w2"],
                w2_scales=inputs["w2_scales"],
                topk_weights=inputs["topk_weights"],
                topk_ids=inputs["topk_ids"],
                num_experts=num_experts,
                topk=topk,
                scratch=prologue_scratch,
                use_offset_gemm=True,
            )
            end.record()
            torch.xpu.synchronize()
            prologue_offset_total_us.append(elapsed_us(start, end))

    def mean(values: list[float]) -> float:
        return sum(values) / max(1, len(values))

    components = {label: mean(values)
                  for label, values in component_us.items()}
    components["activation_plus_quant2"] = (
        components["activation"] + components["quant2"])
    components["activation_contiguous_quant2"] = (
        components["activation"] + components["act_contiguous"] +
        components["quant2"])
    components["component_sum"] = sum(
        components[label]
        for label in ("rows_zero", "remap", "quant1", "gemm1",
                      "activation", "act_contiguous", "quant2", "gemm2",
                      "gather"))

    return {
        "rows": rows,
        "moe_inputs": rows * topk,
        "hidden_size": hidden_size,
        "inter_size_per_tp": inter_size,
        "num_experts": num_experts,
        "topk": topk,
        "dtype": args.dtype,
        "topk_source": "route_jsonl" if route_topk_rows else "synthetic_uniform",
        "route_start_index": route_start_index if route_topk_rows else None,
        "route_start_index_mod": (
            route_start_index % len(route_topk_rows)
            if route_topk_rows else None
        ),
        "topk_summary": topk_summary,
        "total_us_mean": mean(total_us),
        "xpu_fused_moe_scratch_total_us_mean": mean(scratch_total_us),
        "preallocated_staged_total_us_mean": mean(preallocated_total_us),
        "fused_prologue_staged_total_us_mean":
        mean(prologue_preallocated_total_us),
        "fused_prologue_offset_gemm_total_us_mean":
        (mean(prologue_offset_total_us) if prologue_offset_total_us else None),
        "offset_gemm_available": offset_gemm_available,
        "offset_gemm_enabled": bool(args.enable_offset_gemm),
        "fused_prologue_workspace_bytes":
        int(prologue_scratch["workspace_bytes"]),
        "components_us_mean": components,
        "manual_vs_xpu_fused_moe_max_abs_diff": max_abs_diff,
        "xpu_scratch_vs_xpu_fused_moe_max_abs_diff": xpu_scratch_max_abs_diff,
        "preallocated_vs_xpu_fused_moe_max_abs_diff": prealloc_max_abs_diff,
        "fused_prologue_vs_xpu_fused_moe_max_abs_diff":
        prologue_max_abs_diff,
        "fused_prologue_offset_gemm_vs_xpu_fused_moe_max_abs_diff":
        prologue_offset_max_abs_diff,
        "iterations": args.iterations,
        "warmup": args.warmup,
    }


def _fmt(value: Any, digits: int = 3) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "n/a"


def write_markdown(path: str, results: dict[str, Any]) -> None:
    rows = results.get("results", [])
    fused = bool(results.get("fused_silu_quant_enabled"))
    max_diffs = {
        "manual": max(
            (float(row.get("manual_vs_xpu_fused_moe_max_abs_diff", 0.0))
             for row in rows),
            default=float("nan"),
        ),
        "scratch": max(
            (float(row.get("xpu_scratch_vs_xpu_fused_moe_max_abs_diff", 0.0))
             for row in rows),
            default=float("nan"),
        ),
        "preallocated": max(
            (float(row.get("preallocated_vs_xpu_fused_moe_max_abs_diff", 0.0))
             for row in rows),
            default=float("nan"),
        ),
        "fused_prologue": max(
            (float(row.get("fused_prologue_vs_xpu_fused_moe_max_abs_diff",
                           0.0)) for row in rows),
            default=float("nan"),
        ),
        "fused_prologue_offset": max(
            (float(row.get(
                "fused_prologue_offset_gemm_vs_xpu_fused_moe_max_abs_diff",
                0.0,
            )) for row in rows if row.get(
                "fused_prologue_offset_gemm_vs_xpu_fused_moe_max_abs_diff")
             is not None),
            default=float("nan"),
        ),
    }

    lines = []
    lines.append("# Qwen3.6 INT8 MoE Route Replay")
    lines.append("")
    lines.append(f"- Fused SiLU+quant enabled: `{fused}`.")
    lines.append(f"- TP size: `{results['tp_size']}`.")
    lines.append(f"- Result rows: `{len(rows)}`.")
    if results.get("route_metadata"):
        meta = results["route_metadata"]
        lines.append(f"- Route source: `{meta.get('route_jsonl')}`.")
        lines.append(
            f"- Route records matched: `{meta.get('records_matched')}`; "
            f"top-k rows loaded: `{meta.get('topk_rows_loaded')}`."
        )
    if results.get("route_start_indices") is not None:
        lines.append(
            "- Route start indices: `"
            + ",".join(str(item) for item in results["route_start_indices"])
            + "`."
        )
    lines.append("")
    lines.append("## Exactness")
    lines.append("")
    lines.append(
        f"- Manual staged max abs diff versus `xpu_fused_moe`: "
        f"`{_fmt(max_diffs['manual'])}`."
    )
    lines.append(
        f"- Scratch `xpu_fused_moe` max abs diff: "
        f"`{_fmt(max_diffs['scratch'])}`."
    )
    lines.append(
        f"- Preallocated staged max abs diff: "
        f"`{_fmt(max_diffs['preallocated'])}`."
    )
    lines.append(
        f"- Fused-prologue staged max abs diff: "
        f"`{_fmt(max_diffs['fused_prologue'])}`."
    )
    if any(row.get("offset_gemm_enabled") for row in rows):
        lines.append(
            f"- Fused-prologue offset-GEMM max abs diff: "
            f"`{_fmt(max_diffs['fused_prologue_offset'])}`."
        )
    lines.append("")
    lines.append("## Timing")
    lines.append("")
    mean_xpu = sum(float(row.get("total_us_mean", 0.0))
                   for row in rows) / max(1, len(rows))
    mean_xpu_scratch = sum(
        float(row.get("xpu_fused_moe_scratch_total_us_mean", 0.0))
        for row in rows) / max(1, len(rows))
    mean_prealloc = sum(
        float(row.get("preallocated_staged_total_us_mean", 0.0))
        for row in rows) / max(1, len(rows))
    mean_prologue = sum(
        float(row.get("fused_prologue_staged_total_us_mean", 0.0))
        for row in rows) / max(1, len(rows))
    offset_rows = [
        row for row in rows
        if row.get("fused_prologue_offset_gemm_total_us_mean") is not None
    ]
    mean_prologue_offset = (
        sum(float(row["fused_prologue_offset_gemm_total_us_mean"])
            for row in offset_rows) / len(offset_rows)
        if offset_rows else None
    )
    lines.append(f"- Mean `xpu_fused_moe`: `{_fmt(mean_xpu)} us`.")
    lines.append(
        f"- Mean scratch `xpu_fused_moe`: `{_fmt(mean_xpu_scratch)} us`.")
    lines.append(f"- Mean preallocated staged: `{_fmt(mean_prealloc)} us`.")
    lines.append(
        f"- Mean fused-prologue staged: `{_fmt(mean_prologue)} us`.")
    if mean_prologue_offset is not None:
        lines.append(
            "- Mean fused-prologue offset-GEMM staged: "
            f"`{_fmt(mean_prologue_offset)} us`."
        )
    lines.append("")
    lines.append(
        "| rows | route start | active experts | xpu fused us | "
        "xpu scratch us | prealloc staged us | fused prologue staged us | "
        "fused prologue offset us | gemm1 us | gemm2 us | act+quant2 us |"
    )
    lines.append("|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for row in rows:
        comp = row.get("components_us_mean", {})
        topk = row.get("topk_summary", {})
        lines.append(
            f"| {row.get('rows')} | {row.get('route_start_index')} | "
            f"{topk.get('active_experts')} | "
            f"{_fmt(row.get('total_us_mean'))} | "
            f"{_fmt(row.get('xpu_fused_moe_scratch_total_us_mean'))} | "
            f"{_fmt(row.get('preallocated_staged_total_us_mean'))} | "
            f"{_fmt(row.get('fused_prologue_staged_total_us_mean'))} | "
            f"{_fmt(row.get('fused_prologue_offset_gemm_total_us_mean'))} | "
            f"{_fmt(comp.get('gemm1'))} | "
            f"{_fmt(comp.get('gemm2'))} | "
            f"{_fmt(comp.get('activation_plus_quant2'))} |"
        )
    lines.append("")
    lines.append("## Decision")
    lines.append("")
    if fused:
        if max_diffs["manual"] == 0.0:
            lines.append(
                "- The fused SiLU+quant candidate is exact against the "
                "manual staged path for this route replay."
            )
        else:
            lines.append(
                "- The fused SiLU+quant candidate is not exact against the "
                "manual staged path for this route replay. Do not promote it "
                "as a no-quality-loss path."
            )
    else:
        lines.append(
            "- This is a baseline route replay with the current non-fused "
            "activation and quantization path."
        )
    if max_diffs["fused_prologue"] == 0.0:
        lines.append(
            "- The fused-prologue staged path is exact against "
            "`xpu_fused_moe` for this route replay."
        )
        if mean_prologue > mean_prealloc:
            lines.append(
                "- The fused-prologue staged path is slower than the simpler "
                "preallocated staged path in this full-MoE screen. Do not "
                "wire it into the endpoint unless the downstream GEMM ABI can "
                "consume prologue offsets directly or the prologue is fused "
                "with more downstream work."
            )
    else:
        lines.append(
            "- The fused-prologue staged path is not exact against "
            "`xpu_fused_moe`; do not use it as an endpoint candidate."
        )
    lines.append(
        "- Compare `xpu fused us` with the current budget target of roughly "
        "`160 us/layer` for a plausible `200 tok/s` non-speculative lane."
    )
    lines.append("")
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-config", default=DEFAULT_MODEL_CONFIG)
    parser.add_argument("--tp-size", type=int, default=4)
    parser.add_argument("--rows", type=parse_rows, default=parse_rows("1,2,4,8,16"))
    parser.add_argument("--iterations", type=int, default=50)
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--seed", type=int, default=20260609)
    parser.add_argument("--dtype", choices=("bf16", "fp16"), default="bf16")
    parser.add_argument("--device", default="xpu")
    parser.add_argument("--output-json")
    parser.add_argument(
        "--route-jsonl",
        help="Optional route-capture JSONL whose topk_ids override synthetic routing.",
    )
    parser.add_argument(
        "--route-layer-regex",
        help="Only load route records whose layer matches this regex.",
    )
    parser.add_argument(
        "--route-stage-regex",
        default="^quark_int8_apply$",
        help="Only load route records whose stage matches this regex.",
    )
    parser.add_argument("--route-min-num-tokens", type=int, default=1)
    parser.add_argument("--route-max-num-tokens", type=int, default=1)
    parser.add_argument(
        "--route-start-index",
        type=int,
        default=0,
        help="Starting topk row offset when replaying captured routes.",
    )
    parser.add_argument(
        "--route-start-indices",
        type=parse_int_list,
        help=(
            "Comma-separated route offsets or ranges to scan, for example "
            "'0,8,16' or '0:128:8'. Overrides --route-start-index."
        ),
    )
    parser.add_argument(
        "--route-pack-hot-experts",
        action="store_true",
        help=(
            "Simulate a hot-first physical expert layout by remapping captured "
            "logical expert IDs to dense IDs. Real use would require matching "
            "weight layout remapping to preserve model math."
        ),
    )
    parser.add_argument(
        "--enable-fused-silu-quant",
        action="store_true",
        help="Benchmark the rejected fused SiLU+quant candidate; use for diagnostics only.",
    )
    parser.add_argument(
        "--enable-offset-gemm",
        action="store_true",
        help=(
            "Benchmark the experimental fused-prologue path that feeds "
            "expert_first_token_offset directly to the W8A8 grouped GEMM op."
        ),
    )
    parser.add_argument("--markdown-out")
    args = parser.parse_args()

    if args.enable_fused_silu_quant:
        os.environ["VLLM_XPU_FUSED_MOE_FUSE_SILU_QUANT"] = "1"

    text_config = load_text_config(args.model_config)
    route_topk_rows, route_metadata = load_route_topk_rows(
        args.route_jsonl,
        layer_regex=args.route_layer_regex,
        stage_regex=args.route_stage_regex,
        min_num_tokens=args.route_min_num_tokens,
        max_num_tokens=args.route_max_num_tokens,
    )
    route_packing_metadata = None
    if route_topk_rows and args.route_pack_hot_experts:
        route_topk_rows, route_packing_metadata = pack_hot_route_experts(
            route_topk_rows,
            num_experts=int(text_config["num_experts"]),
        )
    if route_topk_rows:
        route_start_indices = (
            args.route_start_indices
            if args.route_start_indices is not None
            else [args.route_start_index]
        )
    else:
        route_start_indices = [0]

    benchmark_results = []
    for rows in args.rows:
        for route_start_index in route_start_indices:
            benchmark_results.append(
                benchmark_rows(
                    args,
                    text_config,
                    rows,
                    route_topk_rows,
                    route_start_index,
                ))

    results = {
        "model_config": args.model_config,
        "tp_size": args.tp_size,
        "fused_silu_quant_enabled": args.enable_fused_silu_quant,
        "route_metadata": route_metadata,
        "route_packing_metadata": route_packing_metadata,
        "route_start_indices": route_start_indices if route_topk_rows else None,
        "results": benchmark_results,
    }

    text = json.dumps(results, indent=2, sort_keys=True)
    if args.output_json:
        Path(args.output_json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output_json).write_text(text + "\n")
    if args.markdown_out:
        Path(args.markdown_out).parent.mkdir(parents=True, exist_ok=True)
        write_markdown(args.markdown_out, results)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
