#!/usr/bin/env python3
"""Microbenchmark Qwen3.6 W8A8 INT8 MoE kernel stages on XPU.

This is a kernel-level diagnostic for the Quark W8A8 INT8 path used by the
Qwen3.6 35B-A3B profile. It does not benchmark full model quality or service
latency; use it to decide which exact-preserving MoE subpath is worth attacking
next.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any

import torch

import vllm_xpu_kernels._moe_C  # noqa: F401
from vllm_xpu_kernels.fused_moe_interface import (
    _normalize_int8_weight_scales,
    _per_token_quant_int8,
    fused_moe_activation,
    ref_fused_moe,
    xpu_fused_moe,
)


DEFAULT_MODEL_CONFIG = (
    "/mnt/fast-ai/llm-cache/hf/models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8/"
    "snapshots/cced56592e8c8935f8220836b4baa04dfd389118/config.json"
)


def _per_token_quant_int8_maybe_out(
    x: torch.Tensor,
    q: torch.Tensor | None = None,
    scales: torch.Tensor | None = None,
) -> tuple[torch.Tensor, torch.Tensor]:
    out_op = getattr(torch.ops._xpu_C, "per_token_quant_int8_xpu_out", None)
    if q is not None and scales is not None and out_op is not None:
        return out_op(x, q, scales)
    return _per_token_quant_int8(x)


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
        "active_expert_ids": torch.empty((num_experts),
                                         device=device,
                                         dtype=torch.int32),
        "onednn_offsets": torch.empty((num_experts),
                                      device=device,
                                      dtype=torch.int32),
        "topk_ids_i32": torch.empty((rows, topk),
                                    device=device,
                                    dtype=torch.int32),
        "num_active_experts": 0,
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
        "gemm1_a": torch.empty((num_moe_inputs, hidden_size),
                               device=device,
                               dtype=torch.int8),
        "gemm1_a_scales": torch.empty((num_moe_inputs, 1),
                                      device=device,
                                      dtype=torch.float32),
        "gemm2_a": torch.empty((num_moe_inputs, inter_size),
                               device=device,
                               dtype=torch.int8),
        "gemm2_a_scales": torch.empty((num_moe_inputs, 1),
                                      device=device,
                                      dtype=torch.float32),
    }


def set_active_experts_from_topk(
    scratch: dict[str, Any],
    topk_ids: torch.Tensor,
) -> int:
    active_experts = torch.unique(topk_ids.flatten(), sorted=True).to(
        torch.int32)
    num_active = int(active_experts.numel())
    scratch["active_expert_ids"][:num_active].copy_(active_experts)
    scratch["num_active_experts"] = num_active
    return num_active


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


@contextmanager
def temporary_env(updates: dict[str, str | None]):
    previous = {key: os.environ.get(key) for key in updates}
    try:
        for key, value in updates.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def max_abs_diff(left: torch.Tensor | None,
                 right: torch.Tensor | None) -> float | None:
    if left is None or right is None:
        return None
    return float((left - right).abs().max().item())


def build_synthetic_topk_ids(
    *,
    rows: int,
    topk: int,
    num_experts: int,
    mode: str,
    device: str,
) -> torch.Tensor:
    if mode == "uniform":
        ids = (
            torch.arange(rows * topk, device=device, dtype=torch.int64) %
            num_experts
        ).view(rows, topk)
        return ids.contiguous()

    if mode == "hot_skew":
        hot_prefix = min(4, topk, num_experts)
        hot_pool = min(num_experts, max(topk + 8, 16))
        rows_out: list[list[int]] = []
        for row in range(rows):
            selected = list(range(hot_prefix))
            cursor = (row * 5) % max(1, hot_pool - hot_prefix)
            candidate = hot_prefix + cursor
            while len(selected) < topk:
                expert = candidate % hot_pool
                if expert not in selected:
                    selected.append(expert)
                candidate += 3
            rows_out.append(selected)
        return torch.tensor(rows_out, device=device, dtype=torch.int64)

    raise ValueError(f"Unsupported synthetic route mode: {mode}")


def measure_graph_replay_us(
    name: str,
    fn,
    *,
    warmup: int,
    iterations: int,
) -> dict[str, Any]:
    if not hasattr(torch.xpu, "XPUGraph") or not hasattr(torch.xpu, "graph"):
        return {
            "name": name,
            "status": "unsupported",
            "us_mean": None,
            "iterations": 0,
            "warmup": warmup,
        }

    try:
        for _ in range(warmup):
            fn()
        torch.xpu.synchronize()

        graph = torch.xpu.XPUGraph()
        with torch.xpu.graph(graph):
            fn()
        torch.xpu.synchronize()

        timings = []
        for _ in range(iterations):
            start, end = make_events()
            start.record()
            graph.replay()
            end.record()
            torch.xpu.synchronize()
            timings.append(elapsed_us(start, end))

        return {
            "name": name,
            "status": "executed",
            "us_mean": sum(timings) / max(1, len(timings)),
            "iterations": iterations,
            "warmup": warmup,
        }
    except Exception as exc:  # noqa: BLE001 - graph failures are data.
        return {
            "name": name,
            "status": "error",
            "us_mean": None,
            "iterations": 0,
            "warmup": warmup,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


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
    synthetic_route_mode: str,
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
        topk_ids = build_synthetic_topk_ids(
            rows=rows,
            topk=topk,
            num_experts=num_experts,
            mode=synthetic_route_mode,
            device=device,
        )
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
        "gemm1_a": torch.empty((num_moe_inputs, hidden_size),
                               device=device,
                               dtype=torch.int8),
        "gemm1_a_scales": torch.empty((num_moe_inputs, 1),
                                      device=device,
                                      dtype=torch.float32),
        "gemm2_a": torch.empty((num_moe_inputs,
                                inter_size),
                               device=device,
                               dtype=torch.int8),
        "gemm2_a_scales": torch.empty((num_moe_inputs, 1),
                                      device=device,
                                      dtype=torch.float32),
        "rows_per_expert": torch.empty((num_experts),
                                       device=device,
                                       dtype=torch.int32),
        "unpermuted": torch.empty((rows, topk),
                                  device=device,
                                  dtype=torch.int32),
    }


def make_xpu_scratch(scratch: dict[str, torch.Tensor]) -> dict[str, torch.Tensor]:
    """Adapt the manual scratch dict to xpu_fused_moe's scratch schema."""
    xpu_scratch = {
        "remapped_hidden_states": scratch["remapped_hidden_states"],
        "gemm1_output": scratch["gemm1_output"],
        "act_output": scratch["act_output"],
        "gemm2_output": scratch["gemm2_output"],
        "gemm1_a": scratch["gemm1_a"],
        "gemm1_a_scales": scratch["gemm1_a_scales"],
        "gemm2_a": scratch["gemm2_a"],
        "gemm2_a_scales": scratch["gemm2_a_scales"],
        "rows_per_expert": scratch["rows_per_expert"],
        "unpermuted_row_to_permuted_row": scratch["unpermuted"],
    }
    if "workspace" in scratch:
        xpu_scratch["prologue_workspace"] = scratch["workspace"]
    if "expert_offsets" in scratch:
        xpu_scratch["w8a8_offsets"] = scratch["expert_offsets"]
    if "active_expert_ids" in scratch:
        xpu_scratch["active_expert_ids"] = scratch["active_expert_ids"]
    return xpu_scratch


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
    gemm1_a, gemm1_a_scales = _per_token_quant_int8_maybe_out(
        scratch["remapped_hidden_states"],
        scratch["gemm1_a"],
        scratch["gemm1_a_scales"],
    )
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
    gemm2_a, gemm2_a_scales = _per_token_quant_int8_maybe_out(
        scratch["act_output"],
        scratch["gemm2_a"],
        scratch["gemm2_a_scales"],
    )
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
    use_active_offset_gemm: bool = False,
    events: dict[str, tuple[torch.xpu.Event, torch.xpu.Event]] | None = None,
) -> torch.Tensor:
    hidden_size = hidden_states.shape[1]
    inter_size = w13.shape[-1] // 2

    def run_stage(label: str, fn):
        if events is None:
            return fn()
        result, start, end = record_call(fn)
        events[label] = (start, end)
        return result

    offset_op = getattr(
        torch.ops._xpu_C,
        "cutlass_grouped_gemm_w8a8_int8_offsets_interface",
        None,
    )
    if use_offset_gemm and offset_op is None:
        raise RuntimeError(
            "cutlass_grouped_gemm_w8a8_int8_offsets_interface is not available"
        )
    active_offset_op = getattr(
        torch.ops._xpu_C,
        "cutlass_grouped_gemm_w8a8_int8_active_offsets_interface",
        None,
    )
    if use_active_offset_gemm and active_offset_op is None:
        raise RuntimeError(
            "cutlass_grouped_gemm_w8a8_int8_active_offsets_interface is not available"
        )

    if events is None:
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
        if not use_offset_gemm and not use_active_offset_gemm:
            scratch["rows_per_expert"].copy_(
                (expert_offsets[1:1 + num_experts] -
                 expert_offsets[:num_experts]).to(torch.int32))

        gemm1_a, gemm1_a_scales = _per_token_quant_int8_maybe_out(
            scratch["remapped_hidden_states"],
            scratch.get("gemm1_a"),
            scratch.get("gemm1_a_scales"),
        )
        gemm1_scales = _normalize_int8_weight_scales(w13_scales,
                                                     2 * inter_size)
        if use_active_offset_gemm:
            active_offset_op(
                ptr_A=gemm1_a,
                ptr_A_scales=gemm1_a_scales,
                ptr_B=w13,
                ptr_B_scales=gemm1_scales,
                ptr_bias=None,
                ptr_D=scratch["gemm1_output"],
                expert_first_token_offset=expert_offsets,
                active_expert_ids=scratch["active_expert_ids"],
                N=2 * inter_size,
                K=hidden_size,
                num_experts=num_experts,
                num_active_experts=int(scratch["num_active_experts"]),
            )
        elif use_offset_gemm:
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
        gemm2_a, gemm2_a_scales = _per_token_quant_int8_maybe_out(
            scratch["act_output"],
            scratch.get("gemm2_a"),
            scratch.get("gemm2_a_scales"),
        )
        gemm2_scales = _normalize_int8_weight_scales(w2_scales, hidden_size)
        if use_active_offset_gemm:
            active_offset_op(
                ptr_A=gemm2_a,
                ptr_A_scales=gemm2_a_scales,
                ptr_B=w2,
                ptr_B_scales=gemm2_scales,
                ptr_bias=None,
                ptr_D=scratch["gemm2_output"],
                expert_first_token_offset=expert_offsets,
                active_expert_ids=scratch["active_expert_ids"],
                N=hidden_size,
                K=inter_size,
                num_experts=num_experts,
                num_active_experts=int(scratch["num_active_experts"]),
            )
        elif use_offset_gemm:
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
        torch.ops._moe_C.moe_gather(scratch["output"],
                                    scratch["gemm2_output"], topk_weights,
                                    scratch["unpermuted"], num_experts)
        return scratch["output"]

    run_stage(
        "prologue",
        lambda: torch.ops._moe_C.fused_moe_prologue(
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
        ),
    )
    expert_offsets = scratch["expert_offsets"]
    if not use_offset_gemm and not use_active_offset_gemm:
        run_stage(
            "rows_from_offsets",
            lambda: scratch["rows_per_expert"].copy_(
                (expert_offsets[1:1 + num_experts] -
                 expert_offsets[:num_experts]).to(torch.int32)),
        )

    gemm1_a, gemm1_a_scales = run_stage(
        "quant1",
        lambda: _per_token_quant_int8_maybe_out(
            scratch["remapped_hidden_states"],
            scratch.get("gemm1_a"),
            scratch.get("gemm1_a_scales"),
        ),
    )
    gemm1_scales = _normalize_int8_weight_scales(w13_scales, 2 * inter_size)
    if use_active_offset_gemm:
        run_stage(
            "gemm1",
            lambda: active_offset_op(
                ptr_A=gemm1_a,
                ptr_A_scales=gemm1_a_scales,
                ptr_B=w13,
                ptr_B_scales=gemm1_scales,
                ptr_bias=None,
                ptr_D=scratch["gemm1_output"],
                expert_first_token_offset=expert_offsets,
                active_expert_ids=scratch["active_expert_ids"],
                N=2 * inter_size,
                K=hidden_size,
                num_experts=num_experts,
                num_active_experts=int(scratch["num_active_experts"]),
            ),
        )
    elif use_offset_gemm:
        run_stage(
            "gemm1",
            lambda: offset_op(
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
            ),
        )
    else:
        run_stage(
            "gemm1",
            lambda: torch.ops._xpu_C.cutlass_grouped_gemm_w8a8_int8_interface(
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
            ),
        )
    run_stage(
        "activation",
        lambda: fused_moe_activation(scratch["act_output"],
                                     scratch["gemm1_output"], "silu"),
    )
    gemm2_a, gemm2_a_scales = run_stage(
        "quant2",
        lambda: _per_token_quant_int8_maybe_out(
            scratch["act_output"],
            scratch.get("gemm2_a"),
            scratch.get("gemm2_a_scales"),
        ),
    )
    gemm2_scales = _normalize_int8_weight_scales(w2_scales, hidden_size)
    if use_active_offset_gemm:
        run_stage(
            "gemm2",
            lambda: active_offset_op(
                ptr_A=gemm2_a,
                ptr_A_scales=gemm2_a_scales,
                ptr_B=w2,
                ptr_B_scales=gemm2_scales,
                ptr_bias=None,
                ptr_D=scratch["gemm2_output"],
                expert_first_token_offset=expert_offsets,
                active_expert_ids=scratch["active_expert_ids"],
                N=hidden_size,
                K=inter_size,
                num_experts=num_experts,
                num_active_experts=int(scratch["num_active_experts"]),
            ),
        )
    elif use_offset_gemm:
        run_stage(
            "gemm2",
            lambda: offset_op(
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
            ),
        )
    else:
        run_stage(
            "gemm2",
            lambda: torch.ops._xpu_C.cutlass_grouped_gemm_w8a8_int8_interface(
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
            ),
        )
    run_stage(
        "gather",
        lambda: torch.ops._moe_C.moe_gather(
            scratch["output"],
            scratch["gemm2_output"],
            topk_weights,
            scratch["unpermuted"],
            num_experts,
        ),
    )
    return scratch["output"]


def manual_int8_moe_fused_prologue_middle_layerlet_once(
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
) -> torch.Tensor:
    hidden_size = hidden_states.shape[1]
    inter_size = w13.shape[-1] // 2
    middle_layerlet_op = getattr(
        torch.ops._xpu_C,
        "qwen36_moe_w8a8_middle_layerlet",
        None,
    )
    if middle_layerlet_op is None:
        raise RuntimeError("qwen36_moe_w8a8_middle_layerlet is not available")

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
    gemm1_a, gemm1_a_scales = _per_token_quant_int8_maybe_out(
        scratch["remapped_hidden_states"],
        scratch.get("gemm1_a"),
        scratch.get("gemm1_a_scales"),
    )
    middle_layerlet_op(
        gemm1_a,
        gemm1_a_scales,
        w13,
        _normalize_int8_weight_scales(w13_scales, 2 * inter_size),
        None,
        scratch["gemm1_output"],
        scratch["gemm2_a"],
        scratch["gemm2_a_scales"],
        w2,
        _normalize_int8_weight_scales(w2_scales, hidden_size),
        None,
        scratch["gemm2_output"],
        scratch["expert_offsets"],
        2 * inter_size,
        hidden_size,
        hidden_size,
        inter_size,
        num_experts,
    )
    torch.ops._moe_C.moe_gather(scratch["output"], scratch["gemm2_output"],
                                topk_weights, scratch["unpermuted"],
                                num_experts)
    return scratch["output"]


def manual_int8_moe_full_layerlet_once(
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
) -> torch.Tensor:
    hidden_size = hidden_states.shape[1]
    inter_size = w13.shape[-1] // 2
    full_layerlet_op = getattr(
        torch.ops._xpu_C,
        "qwen36_moe_w8a8_full_layerlet",
        None,
    )
    if full_layerlet_op is None:
        raise RuntimeError("qwen36_moe_w8a8_full_layerlet is not available")
    full_layerlet_op(
        hidden_states,
        topk_ids,
        topk_weights,
        scratch["workspace"],
        scratch["remapped_hidden_states"],
        scratch["unpermuted"].view(-1),
        scratch["expert_offsets"],
        scratch["gemm1_a"],
        scratch["gemm1_a_scales"],
        w13,
        _normalize_int8_weight_scales(w13_scales, 2 * inter_size),
        None,
        scratch["gemm1_output"],
        scratch["gemm2_a"],
        scratch["gemm2_a_scales"],
        w2,
        _normalize_int8_weight_scales(w2_scales, hidden_size),
        None,
        scratch["gemm2_output"],
        scratch["output"],
        hidden_size,
        inter_size,
        num_experts,
    )
    return scratch["output"]


SIDECAR_STATS_NAMES = (
    "ok",
    "device_index",
    "layer_index",
    "num_rows",
    "topk",
    "num_moe_inputs",
    "hidden_size",
    "inter_size",
    "num_experts",
    "gemm1_n",
    "gemm2_n",
    "dry_create_descriptors",
    "descriptor_create_ok",
    "offsets_supplied",
    "handle_wrap_ok",
    "w13_stride0",
    "w13_stride1",
    "w13_stride2",
    "w2_stride0",
    "w2_stride1",
    "requested_execute_mode",
    "execute_ok",
    "execute_construct_us",
    "execute_wait_us",
    "gemm1_cache_hit",
    "gemm1_construct_us",
    "gemm1_execute_us",
    "gemm2_cache_hit",
    "gemm2_construct_us",
    "gemm2_execute_us",
    "both_wall_us",
    "sidecar_matmul_cache_size",
    "gemm1_wait_after_execute",
    "gemm2_wait_after_execute",
    "cached_execution_path",
    "middle_activation_quant_us",
    "middle_wall_us",
    "reserved37",
    "reserved38",
    "reserved39",
)


def sidecar_stats_dict(stats: torch.Tensor | None) -> dict[str, int] | None:
    if stats is None:
        return None
    values = [int(item) for item in stats.detach().cpu().tolist()]
    return {
        name: values[index] if index < len(values) else 0
        for index, name in enumerate(SIDECAR_STATS_NAMES)
    }


def manual_int8_moe_onednn_sidecar_once(
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
    execute_mode: int = 23,
) -> tuple[torch.Tensor, dict[str, int] | None]:
    hidden_size = hidden_states.shape[1]
    inter_size = w13.shape[-1] // 2
    sidecar_op = getattr(
        torch.ops._xpu_C,
        "qwen36_moe_onednn_sidecar_probe",
        None,
    )
    if sidecar_op is None:
        raise RuntimeError("qwen36_moe_onednn_sidecar_probe is not available")

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
    _per_token_quant_int8_maybe_out(
        scratch["remapped_hidden_states"],
        scratch["gemm1_a"],
        scratch["gemm1_a_scales"],
    )

    # oneDNN grouped matmul uses end-only int32 offsets, while the CUTLASS path
    # uses leading-zero int64 offsets. Keep this diagnostic conversion explicit
    # so it is counted in the full sidecar timing.
    scratch["onednn_offsets"].copy_(scratch["expert_offsets"][1:].to(torch.int32))
    scratch["topk_ids_i32"].copy_(topk_ids.to(torch.int32))

    stats = sidecar_op(
        hidden_states,
        topk_weights,
        scratch["topk_ids_i32"],
        w13,
        _normalize_int8_weight_scales(w13_scales, 2 * inter_size),
        w2,
        _normalize_int8_weight_scales(w2_scales, hidden_size),
        scratch["output"],
        # The sidecar ABI names this argument remapped_hidden_states, but the
        # C++ diagnostic expects the int8 quantized GEMM1 input buffer here.
        scratch["gemm1_a"],
        scratch["rows_per_expert"],
        scratch["unpermuted"],
        scratch["gemm1_a"],
        scratch["gemm1_a_scales"],
        scratch["gemm1_output"],
        scratch["act_output"],
        scratch["gemm2_a"],
        scratch["gemm2_a_scales"],
        scratch["gemm2_output"],
        scratch["onednn_offsets"],
        -1,
        True,
        int(execute_mode),
    )
    torch.ops._moe_C.moe_gather(
        scratch["output"],
        scratch["gemm2_output"],
        topk_weights,
        scratch["unpermuted"],
        num_experts,
    )
    return scratch["output"], sidecar_stats_dict(stats)


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
        "topk_rows": topk_cpu[:topn],
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


def collect_runtime_identity(args) -> dict[str, Any]:
    env_keys = [
        "ONEAPI_DEVICE_SELECTOR",
        "ZE_AFFINITY_MASK",
        "VLLM_XPU_W8A8_GROUPED_GEMM_POLICY",
        "VLLM_XPU_W8A8_GROUPED_GEMM_N_LT_K_POLICY",
        "VLLM_XPU_W8A8_GROUPED_GEMM_N_GT_K_POLICY",
        "VLLM_XPU_MOE_W8A8_FUSED_Q1",
        "VLLM_XPU_MOE_W8A8_FAST_GATHER",
        "VLLM_XPU_MOE_W8A8_DIRECT_GEMM2_GATHER",
        "VLLM_XPU_MOE_W8A8_DPAS_GEMM2_GATHER",
        "VLLM_XPU_MOE_W8A8_DPAS_GEMM2_GATHER_NTILE",
        "VLLM_XPU_MOE_W8A8_WORKSPACE_ATOMIC",
        "VLLM_XPU_MOE_W8A8_ROUTE_GEMM1",
        "VLLM_XPU_MOE_W8A8_ROUTE_GEMM1_MTILE",
        "VLLM_XPU_MOE_W8A8_UNCHECKED_FULL_LAYERLET",
        "VLLM_XPU_INT8_MOE_ACTIVE_OFFSET_GEMM",
        "VLLM_XPU_FUSED_MOE_FUSE_SILU_QUANT",
        "SYCL_PI_LEVEL_ZERO_USE_IMMEDIATE_COMMANDLISTS",
        "UR_L0_USE_IMMEDIATE_COMMANDLISTS",
        "UR_L0_USE_COPY_ENGINE",
    ]
    xpu_count = None
    xpu_devices: list[str] = []
    try:
        xpu_count = int(torch.xpu.device_count())
        for idx in range(xpu_count):
            try:
                xpu_devices.append(str(torch.xpu.get_device_name(idx)))
            except Exception as exc:  # noqa: BLE001 - diagnostic only.
                xpu_devices.append(f"unavailable:{type(exc).__name__}")
    except Exception as exc:  # noqa: BLE001 - diagnostic only.
        xpu_devices.append(f"device_count_error:{type(exc).__name__}:{exc}")

    loaded_extensions = {
        name: getattr(module, "__file__", None)
        for name, module in sorted(sys.modules.items())
        if name.startswith("vllm_xpu_kernels")
    }

    return {
        "argv": sys.argv,
        "torch_version": torch.__version__,
        "xpu_device_count": xpu_count,
        "xpu_devices": xpu_devices,
        "env": {key: os.environ.get(key) for key in env_keys},
        "python": sys.executable,
        "loaded_extensions": loaded_extensions,
        "dtype": args.dtype,
        "device_arg": args.device,
        "iterations": args.iterations,
        "warmup": args.warmup,
        "graph_replay_timing": bool(args.graph_replay_timing),
        "stage_timing_iterations": args.stage_timing_iterations,
        "enable_onednn_sidecar": bool(args.enable_onednn_sidecar),
        "onednn_sidecar_mode": int(args.onednn_sidecar_mode),
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
        synthetic_route_mode=args.synthetic_route_mode,
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

    rows_oracle_output: torch.Tensor | None = None
    offset_oracle_output: torch.Tensor | None = None
    bf16_reference_output: torch.Tensor | None = None
    rows_oracle_env = {
        "VLLM_XPU_FUSED_MOE_USE_REF": "0",
        "VLLM_XPU_W8A8_USE_OFFSETS": "0",
        "VLLM_XPU_INT8_MOE_FUSED_PROLOGUE_OFFSET": "0",
        "VLLM_XPU_MOE_W8A8_MIDDLE_LAYERLET": "0",
        "VLLM_XPU_MOE_W8A8_FULL_LAYERLET": "0",
    }
    offset_oracle_env = {
        **rows_oracle_env,
        "VLLM_XPU_W8A8_USE_OFFSETS": "1",
    }
    offset_gemm_available = hasattr(
        torch.ops._xpu_C,
        "cutlass_grouped_gemm_w8a8_int8_offsets_interface",
    )
    if args.real_routing_oracle:
        with temporary_env(rows_oracle_env):
            rows_oracle_output = xpu_fused_moe(
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
        if offset_gemm_available:
            with temporary_env(offset_oracle_env):
                offset_oracle_output = xpu_fused_moe(
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
        if args.real_routing_bf16_reference:
            bf16_reference_output = ref_fused_moe(
                recipe="int8",
                x=inputs["hidden_states"],
                w13=inputs["w13"],
                w13_scales=inputs["w13_scales"],
                w13_bias=None,
                w2=inputs["w2"],
                w2_scales=inputs["w2_scales"],
                w2_bias=None,
                expert_weights=inputs["topk_weights"],
                expert_indices=inputs["topk_ids"],
                num_per_tok=topk,
                activation="silu",
                num_experts=num_experts,
            )
        torch.xpu.synchronize()
    xpu_fused_moe_rows_oracle_max_abs_diff = max_abs_diff(
        ref_output, rows_oracle_output)
    offset_oracle_rows_oracle_max_abs_diff = max_abs_diff(
        offset_oracle_output, rows_oracle_output)
    rows_oracle_bf16_reference_max_abs_diff = max_abs_diff(
        rows_oracle_output, bf16_reference_output)

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
    manual_max_abs_diff = float(
        (ref_output - manual_output).abs().max().item())
    manual_rows_oracle_max_abs_diff = max_abs_diff(manual_output,
                                                   rows_oracle_output)

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
    prealloc_rows_oracle_max_abs_diff = max_abs_diff(scratch_output,
                                                     rows_oracle_output)
    prologue_scratch = make_prologue_scratch(
        rows=rows,
        hidden_size=hidden_size,
        inter_size=inter_size,
        num_experts=num_experts,
        topk=topk,
        dtype=dtype,
        device=args.device,
    )
    set_active_experts_from_topk(prologue_scratch, inputs["topk_ids"])
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
    prologue_rows_oracle_max_abs_diff = max_abs_diff(prologue_output,
                                                     rows_oracle_output)
    active_offset_gemm_available = hasattr(
        torch.ops._xpu_C,
        "cutlass_grouped_gemm_w8a8_int8_active_offsets_interface",
    )
    middle_layerlet_available = hasattr(
        torch.ops._xpu_C,
        "qwen36_moe_w8a8_middle_layerlet",
    )
    full_layerlet_available = hasattr(
        torch.ops._xpu_C,
        "qwen36_moe_w8a8_full_layerlet",
    )
    onednn_sidecar_available = hasattr(
        torch.ops._xpu_C,
        "qwen36_moe_onednn_sidecar_probe",
    )
    prologue_offset_max_abs_diff: float | None = None
    prologue_active_offset_max_abs_diff: float | None = None
    prologue_middle_layerlet_max_abs_diff: float | None = None
    full_layerlet_max_abs_diff: float | None = None
    onednn_sidecar_max_abs_diff: float | None = None
    prologue_offset_rows_oracle_max_abs_diff: float | None = None
    prologue_active_offset_rows_oracle_max_abs_diff: float | None = None
    prologue_middle_layerlet_rows_oracle_max_abs_diff: float | None = None
    full_layerlet_rows_oracle_max_abs_diff: float | None = None
    onednn_sidecar_rows_oracle_max_abs_diff: float | None = None
    prologue_offset_output: torch.Tensor | None = None
    prologue_active_offset_output: torch.Tensor | None = None
    prologue_middle_layerlet_output: torch.Tensor | None = None
    full_layerlet_output: torch.Tensor | None = None
    onednn_sidecar_output: torch.Tensor | None = None
    onednn_sidecar_stats_once: dict[str, int] | None = None
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
        prologue_offset_rows_oracle_max_abs_diff = max_abs_diff(
            prologue_offset_output, rows_oracle_output)
    if args.enable_active_offset_gemm:
        prologue_active_offset_output = manual_int8_moe_fused_prologue_once(
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
            use_active_offset_gemm=True,
        )
        torch.xpu.synchronize()
        prologue_active_offset_max_abs_diff = float(
            (ref_output - prologue_active_offset_output).abs().max().item())
        prologue_active_offset_rows_oracle_max_abs_diff = max_abs_diff(
            prologue_active_offset_output, rows_oracle_output)
    if args.enable_middle_layerlet:
        prologue_middle_layerlet_output = (
            manual_int8_moe_fused_prologue_middle_layerlet_once(
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
            ))
        torch.xpu.synchronize()
        prologue_middle_layerlet_max_abs_diff = float(
            (ref_output - prologue_middle_layerlet_output).abs().max().item())
        prologue_middle_layerlet_rows_oracle_max_abs_diff = max_abs_diff(
            prologue_middle_layerlet_output, rows_oracle_output)
    if args.enable_full_layerlet:
        full_layerlet_output = manual_int8_moe_full_layerlet_once(
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
        full_layerlet_max_abs_diff = float(
            (ref_output - full_layerlet_output).abs().max().item())
        full_layerlet_rows_oracle_max_abs_diff = max_abs_diff(
            full_layerlet_output, rows_oracle_output)
    if args.enable_onednn_sidecar:
        onednn_sidecar_output, onednn_sidecar_stats_once = (
            manual_int8_moe_onednn_sidecar_once(
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
                execute_mode=args.onednn_sidecar_mode,
            ))
        torch.xpu.synchronize()
        onednn_sidecar_max_abs_diff = float(
            (ref_output - onednn_sidecar_output).abs().max().item())
        onednn_sidecar_rows_oracle_max_abs_diff = max_abs_diff(
            onednn_sidecar_output, rows_oracle_output)
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
    xpu_scratch_rows_oracle_max_abs_diff = max_abs_diff(
        xpu_scratch_output, rows_oracle_output)

    xpu_prologue_scratch_output = xpu_fused_moe(
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
        scratch=make_xpu_scratch(prologue_scratch),
    )
    torch.xpu.synchronize()
    xpu_prologue_scratch_max_abs_diff = float(
        (ref_output - xpu_prologue_scratch_output).abs().max().item())
    xpu_prologue_scratch_rows_oracle_max_abs_diff = max_abs_diff(
        xpu_prologue_scratch_output, rows_oracle_output)

    total_us = []
    scratch_total_us = []
    prologue_scratch_total_us = []
    preallocated_total_us = []
    prologue_preallocated_total_us = []
    prologue_offset_total_us = []
    prologue_active_offset_total_us = []
    prologue_middle_layerlet_total_us = []
    full_layerlet_total_us = []
    onednn_sidecar_total_us = []
    onednn_sidecar_middle_wall_us = []
    onednn_sidecar_execute_wait_us = []
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
    prologue_component_us: dict[str, list[float]] = {}
    prologue_offset_component_us: dict[str, list[float]] = {}
    prologue_active_offset_component_us: dict[str, list[float]] = {}

    def record_stage_components(
        target: dict[str, list[float]],
        events: dict[str, tuple[torch.xpu.Event, torch.xpu.Event]],
    ) -> None:
        for label, (component_start, component_end) in events.items():
            target.setdefault(label, []).append(
                elapsed_us(component_start, component_end))

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
            scratch=make_xpu_scratch(prologue_scratch),
        )
        end.record()
        torch.xpu.synchronize()
        prologue_scratch_total_us.append(elapsed_us(start, end))

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
        if args.enable_active_offset_gemm:
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
                use_active_offset_gemm=True,
            )
            end.record()
            torch.xpu.synchronize()
            prologue_active_offset_total_us.append(elapsed_us(start, end))
        if args.enable_middle_layerlet:
            start, end = make_events()
            start.record()
            manual_int8_moe_fused_prologue_middle_layerlet_once(
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
            prologue_middle_layerlet_total_us.append(elapsed_us(start, end))
        if args.enable_full_layerlet:
            start, end = make_events()
            start.record()
            manual_int8_moe_full_layerlet_once(
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
            full_layerlet_total_us.append(elapsed_us(start, end))
        if args.enable_onednn_sidecar:
            start, end = make_events()
            start.record()
            _, stats = manual_int8_moe_onednn_sidecar_once(
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
                execute_mode=args.onednn_sidecar_mode,
            )
            end.record()
            torch.xpu.synchronize()
            onednn_sidecar_total_us.append(elapsed_us(start, end))
            if stats is not None:
                onednn_sidecar_middle_wall_us.append(
                    float(stats.get("middle_wall_us", 0)))
                onednn_sidecar_execute_wait_us.append(
                    float(stats.get("execute_wait_us", 0)))

    for _ in range(args.stage_timing_iterations):
        prologue_events: dict[str, tuple[torch.xpu.Event,
                                         torch.xpu.Event]] = {}
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
            events=prologue_events,
        )
        torch.xpu.synchronize()
        record_stage_components(prologue_component_us, prologue_events)
        if args.enable_offset_gemm:
            prologue_offset_events: dict[str, tuple[torch.xpu.Event,
                                                    torch.xpu.Event]] = {}
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
                events=prologue_offset_events,
            )
            torch.xpu.synchronize()
            record_stage_components(prologue_offset_component_us,
                                    prologue_offset_events)
        if args.enable_active_offset_gemm:
            prologue_active_offset_events: dict[
                str, tuple[torch.xpu.Event, torch.xpu.Event]] = {}
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
                use_active_offset_gemm=True,
                events=prologue_active_offset_events,
            )
            torch.xpu.synchronize()
            record_stage_components(prologue_active_offset_component_us,
                                    prologue_active_offset_events)

    def mean(values: list[float]) -> float:
        return sum(values) / max(1, len(values))

    graph_replay: list[dict[str, Any]] = []
    if args.graph_replay_timing:
        graph_scratch = make_scratch(
            rows=rows,
            hidden_size=hidden_size,
            inter_size=inter_size,
            num_experts=num_experts,
            topk=topk,
            dtype=dtype,
            device=args.device,
        )
        graph_prologue_scratch = make_prologue_scratch(
            rows=rows,
            hidden_size=hidden_size,
            inter_size=inter_size,
            num_experts=num_experts,
            topk=topk,
            dtype=dtype,
            device=args.device,
        )
        set_active_experts_from_topk(graph_prologue_scratch,
                                     inputs["topk_ids"])
        graph_replay.append(
            measure_graph_replay_us(
                "xpu_fused_moe_with_scratch",
                lambda: xpu_fused_moe(
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
                    scratch=make_xpu_scratch(graph_scratch),
                ),
                warmup=args.graph_warmup,
                iterations=args.graph_iterations,
            ))
        graph_replay.append(
            measure_graph_replay_us(
                "xpu_fused_moe_with_prologue_scratch",
                lambda: xpu_fused_moe(
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
                    scratch=make_xpu_scratch(graph_prologue_scratch),
                ),
                warmup=args.graph_warmup,
                iterations=args.graph_iterations,
            ))
        graph_replay.append(
            measure_graph_replay_us(
                "preallocated_staged",
                lambda: manual_int8_moe_preallocated_once(
                    hidden_states=inputs["hidden_states"],
                    w13=inputs["w13"],
                    w13_scales=inputs["w13_scales"],
                    w2=inputs["w2"],
                    w2_scales=inputs["w2_scales"],
                    topk_weights=inputs["topk_weights"],
                    topk_ids=inputs["topk_ids"],
                    num_experts=num_experts,
                    topk=topk,
                    scratch=graph_scratch,
                ),
                warmup=args.graph_warmup,
                iterations=args.graph_iterations,
            ))
        graph_replay.append(
            measure_graph_replay_us(
                "fused_prologue_staged",
                lambda: manual_int8_moe_fused_prologue_once(
                    hidden_states=inputs["hidden_states"],
                    w13=inputs["w13"],
                    w13_scales=inputs["w13_scales"],
                    w2=inputs["w2"],
                    w2_scales=inputs["w2_scales"],
                    topk_weights=inputs["topk_weights"],
                    topk_ids=inputs["topk_ids"],
                    num_experts=num_experts,
                    topk=topk,
                    scratch=graph_prologue_scratch,
                ),
                warmup=args.graph_warmup,
                iterations=args.graph_iterations,
            ))
        if args.enable_offset_gemm:
            graph_replay.append(
                measure_graph_replay_us(
                    "fused_prologue_offset_gemm",
                    lambda: manual_int8_moe_fused_prologue_once(
                        hidden_states=inputs["hidden_states"],
                        w13=inputs["w13"],
                        w13_scales=inputs["w13_scales"],
                        w2=inputs["w2"],
                        w2_scales=inputs["w2_scales"],
                        topk_weights=inputs["topk_weights"],
                        topk_ids=inputs["topk_ids"],
                        num_experts=num_experts,
                        topk=topk,
                        scratch=graph_prologue_scratch,
                        use_offset_gemm=True,
                    ),
                    warmup=args.graph_warmup,
                    iterations=args.graph_iterations,
                ))
        if args.enable_active_offset_gemm:
            graph_replay.append(
                measure_graph_replay_us(
                    "fused_prologue_active_offset_gemm",
                    lambda: manual_int8_moe_fused_prologue_once(
                        hidden_states=inputs["hidden_states"],
                        w13=inputs["w13"],
                        w13_scales=inputs["w13_scales"],
                        w2=inputs["w2"],
                        w2_scales=inputs["w2_scales"],
                        topk_weights=inputs["topk_weights"],
                        topk_ids=inputs["topk_ids"],
                        num_experts=num_experts,
                        topk=topk,
                        scratch=graph_prologue_scratch,
                        use_active_offset_gemm=True,
                    ),
                    warmup=args.graph_warmup,
                    iterations=args.graph_iterations,
                ))
        if args.enable_full_layerlet:
            graph_replay.append(
                measure_graph_replay_us(
                    "full_layerlet",
                    lambda: manual_int8_moe_full_layerlet_once(
                        hidden_states=inputs["hidden_states"],
                        w13=inputs["w13"],
                        w13_scales=inputs["w13_scales"],
                        w2=inputs["w2"],
                        w2_scales=inputs["w2_scales"],
                        topk_weights=inputs["topk_weights"],
                        topk_ids=inputs["topk_ids"],
                        num_experts=num_experts,
                        topk=topk,
                        scratch=graph_prologue_scratch,
                    ),
                    warmup=args.graph_warmup,
                    iterations=args.graph_iterations,
                ))
        if args.enable_onednn_sidecar:
            graph_replay.append(
                measure_graph_replay_us(
                    "onednn_sidecar",
                    lambda: manual_int8_moe_onednn_sidecar_once(
                        hidden_states=inputs["hidden_states"],
                        w13=inputs["w13"],
                        w13_scales=inputs["w13_scales"],
                        w2=inputs["w2"],
                        w2_scales=inputs["w2_scales"],
                        topk_weights=inputs["topk_weights"],
                        topk_ids=inputs["topk_ids"],
                        num_experts=num_experts,
                        topk=topk,
                        scratch=graph_prologue_scratch,
                        execute_mode=args.onednn_sidecar_mode,
                    )[0],
                    warmup=args.graph_warmup,
                    iterations=args.graph_iterations,
                ))

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

    def summarize_stage_components(
        source: dict[str, list[float]],
    ) -> dict[str, float]:
        summarized = {label: mean(values) for label, values in source.items()}
        summarized["activation_plus_quant2"] = (
            summarized.get("activation", 0.0) +
            summarized.get("quant2", 0.0))
        summarized["component_sum"] = sum(
            summarized.get(label, 0.0)
            for label in ("prologue", "rows_from_offsets", "quant1", "gemm1",
                          "activation", "quant2", "gemm2", "gather"))
        return summarized

    prologue_components = summarize_stage_components(prologue_component_us)
    prologue_offset_components = summarize_stage_components(
        prologue_offset_component_us)
    prologue_active_offset_components = summarize_stage_components(
        prologue_active_offset_component_us)

    result = {
        "rows": rows,
        "moe_inputs": rows * topk,
        "hidden_size": hidden_size,
        "inter_size_per_tp": inter_size,
        "num_experts": num_experts,
        "topk": topk,
        "dtype": args.dtype,
        "selected_experts": topk_summary.get("topk_rows"),
        "topk_source": (
            "route_jsonl" if route_topk_rows
            else f"synthetic_{args.synthetic_route_mode}"),
        "synthetic_route_mode": (
            None if route_topk_rows else args.synthetic_route_mode),
        "route_start_index": route_start_index if route_topk_rows else None,
        "route_start_index_mod": (
            route_start_index % len(route_topk_rows)
            if route_topk_rows else None
        ),
        "topk_summary": topk_summary,
        "total_us_mean": mean(total_us),
        "xpu_fused_moe_scratch_total_us_mean": mean(scratch_total_us),
        "xpu_fused_moe_prologue_scratch_total_us_mean":
        mean(prologue_scratch_total_us),
        "preallocated_staged_total_us_mean": mean(preallocated_total_us),
        "fused_prologue_staged_total_us_mean":
        mean(prologue_preallocated_total_us),
        "fused_prologue_offset_gemm_total_us_mean":
        (mean(prologue_offset_total_us) if prologue_offset_total_us else None),
        "fused_prologue_active_offset_gemm_total_us_mean":
        (mean(prologue_active_offset_total_us)
         if prologue_active_offset_total_us else None),
        "fused_prologue_middle_layerlet_total_us_mean":
        (mean(prologue_middle_layerlet_total_us)
         if prologue_middle_layerlet_total_us else None),
        "full_layerlet_total_us_mean":
        (mean(full_layerlet_total_us) if full_layerlet_total_us else None),
        "onednn_sidecar_total_us_mean":
        (mean(onednn_sidecar_total_us) if onednn_sidecar_total_us else None),
        "onednn_sidecar_middle_wall_us_mean":
        (mean(onednn_sidecar_middle_wall_us)
         if onednn_sidecar_middle_wall_us else None),
        "onednn_sidecar_execute_wait_us_mean":
        (mean(onednn_sidecar_execute_wait_us)
         if onednn_sidecar_execute_wait_us else None),
        "onednn_sidecar_stats_once": onednn_sidecar_stats_once,
        "offset_gemm_available": offset_gemm_available,
        "offset_gemm_enabled": bool(args.enable_offset_gemm),
        "active_offset_gemm_available": active_offset_gemm_available,
        "active_offset_gemm_enabled": bool(args.enable_active_offset_gemm),
        "middle_layerlet_available": middle_layerlet_available,
        "middle_layerlet_enabled": bool(args.enable_middle_layerlet),
        "full_layerlet_available": full_layerlet_available,
        "full_layerlet_enabled": bool(args.enable_full_layerlet),
        "onednn_sidecar_available": onednn_sidecar_available,
        "onednn_sidecar_enabled": bool(args.enable_onednn_sidecar),
        "onednn_sidecar_execute_mode": int(args.onednn_sidecar_mode),
        "quant_out_op_available": hasattr(torch.ops._xpu_C,
                                          "per_token_quant_int8_xpu_out"),
        "quant_scratch_buffers": [
            "gemm1_a",
            "gemm1_a_scales",
            "gemm2_a",
            "gemm2_a_scales",
        ],
        "num_active_experts_for_active_offset":
        int(prologue_scratch["num_active_experts"]),
        "fused_prologue_workspace_bytes":
        int(prologue_scratch["workspace_bytes"]),
        "components_us_mean": components,
        "fused_prologue_components_us_mean": prologue_components,
        "fused_prologue_offset_components_us_mean":
        prologue_offset_components,
        "fused_prologue_active_offset_components_us_mean":
        prologue_active_offset_components,
        "manual_vs_xpu_fused_moe_max_abs_diff": manual_max_abs_diff,
        "xpu_scratch_vs_xpu_fused_moe_max_abs_diff": xpu_scratch_max_abs_diff,
        "xpu_prologue_scratch_vs_xpu_fused_moe_max_abs_diff":
        xpu_prologue_scratch_max_abs_diff,
        "preallocated_vs_xpu_fused_moe_max_abs_diff": prealloc_max_abs_diff,
        "fused_prologue_vs_xpu_fused_moe_max_abs_diff":
        prologue_max_abs_diff,
        "fused_prologue_offset_gemm_vs_xpu_fused_moe_max_abs_diff":
        prologue_offset_max_abs_diff,
        "fused_prologue_active_offset_gemm_vs_xpu_fused_moe_max_abs_diff":
        prologue_active_offset_max_abs_diff,
        "fused_prologue_middle_layerlet_vs_xpu_fused_moe_max_abs_diff":
        prologue_middle_layerlet_max_abs_diff,
        "full_layerlet_vs_xpu_fused_moe_max_abs_diff":
        full_layerlet_max_abs_diff,
        "onednn_sidecar_vs_xpu_fused_moe_max_abs_diff":
        onednn_sidecar_max_abs_diff,
        "real_routing_oracle_enabled": bool(args.real_routing_oracle),
        "real_routing_bf16_reference_enabled":
        bool(args.real_routing_bf16_reference),
        "xpu_fused_moe_vs_rows_oracle_max_abs_diff":
        xpu_fused_moe_rows_oracle_max_abs_diff,
        "offset_oracle_vs_rows_oracle_max_abs_diff":
        offset_oracle_rows_oracle_max_abs_diff,
        "manual_vs_rows_oracle_max_abs_diff":
        manual_rows_oracle_max_abs_diff,
        "xpu_scratch_vs_rows_oracle_max_abs_diff":
        xpu_scratch_rows_oracle_max_abs_diff,
        "xpu_prologue_scratch_vs_rows_oracle_max_abs_diff":
        xpu_prologue_scratch_rows_oracle_max_abs_diff,
        "preallocated_vs_rows_oracle_max_abs_diff":
        prealloc_rows_oracle_max_abs_diff,
        "fused_prologue_vs_rows_oracle_max_abs_diff":
        prologue_rows_oracle_max_abs_diff,
        "fused_prologue_offset_gemm_vs_rows_oracle_max_abs_diff":
        prologue_offset_rows_oracle_max_abs_diff,
        "fused_prologue_active_offset_gemm_vs_rows_oracle_max_abs_diff":
        prologue_active_offset_rows_oracle_max_abs_diff,
        "fused_prologue_middle_layerlet_vs_rows_oracle_max_abs_diff":
        prologue_middle_layerlet_rows_oracle_max_abs_diff,
        "full_layerlet_vs_rows_oracle_max_abs_diff":
        full_layerlet_rows_oracle_max_abs_diff,
        "onednn_sidecar_vs_rows_oracle_max_abs_diff":
        onednn_sidecar_rows_oracle_max_abs_diff,
        "rows_oracle_vs_bf16_reference_max_abs_diff":
        rows_oracle_bf16_reference_max_abs_diff,
        "iterations": args.iterations,
        "warmup": args.warmup,
        "stage_timing_iterations": args.stage_timing_iterations,
    }
    if args.graph_replay_timing:
        result["graph_replay"] = graph_replay
    result["prologue_inclusive_gate"] = build_prologue_inclusive_gate(
        result,
        exactness_threshold=args.exactness_threshold,
        target_layerlet_us=args.target_layerlet_us,
        min_speedup_vs_xpu=args.min_speedup_vs_xpu,
    )
    return result


def _fmt(value: Any, digits: int = 3) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "n/a"


def _maybe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(parsed) or math.isinf(parsed):
        return None
    return parsed


def build_prologue_inclusive_gate(
    row: dict[str, Any],
    *,
    exactness_threshold: float,
    target_layerlet_us: float,
    min_speedup_vs_xpu: float,
) -> dict[str, Any]:
    """Attach a full-MoE-layerlet gate to a benchmark row.

    The gate intentionally uses prologue-inclusive timings only. Isolated GEMM
    or prologue wins are diagnostics; they are not promotion candidates unless
    the full route/remap/quant/GEMM/activation/GEMM/gather layerlet also wins.
    """

    baseline_us = _maybe_float(row.get("total_us_mean"))
    candidates = [
        {
            "name": "xpu_fused_moe_reference",
            "us_mean": baseline_us,
            "max_abs_diff_vs_xpu": 0.0,
            "reference": True,
        },
        {
            "name": "xpu_fused_moe_with_scratch",
            "us_mean": _maybe_float(
                row.get("xpu_fused_moe_scratch_total_us_mean")),
            "max_abs_diff_vs_xpu": _maybe_float(
                row.get("xpu_scratch_vs_xpu_fused_moe_max_abs_diff")),
            "reference": False,
        },
        {
            "name": "xpu_fused_moe_with_prologue_scratch",
            "us_mean": _maybe_float(
                row.get("xpu_fused_moe_prologue_scratch_total_us_mean")),
            "max_abs_diff_vs_xpu": _maybe_float(row.get(
                "xpu_prologue_scratch_vs_xpu_fused_moe_max_abs_diff")),
            "reference": False,
        },
        {
            "name": "preallocated_staged",
            "us_mean": _maybe_float(row.get("preallocated_staged_total_us_mean")),
            "max_abs_diff_vs_xpu": _maybe_float(
                row.get("preallocated_vs_xpu_fused_moe_max_abs_diff")),
            "reference": False,
        },
        {
            "name": "fused_prologue_staged",
            "us_mean": _maybe_float(
                row.get("fused_prologue_staged_total_us_mean")),
            "max_abs_diff_vs_xpu": _maybe_float(
                row.get("fused_prologue_vs_xpu_fused_moe_max_abs_diff")),
            "reference": False,
        },
        {
            "name": "fused_prologue_offset_gemm",
            "us_mean": _maybe_float(
                row.get("fused_prologue_offset_gemm_total_us_mean")),
            "max_abs_diff_vs_xpu": _maybe_float(row.get(
                "fused_prologue_offset_gemm_vs_xpu_fused_moe_max_abs_diff")),
            "reference": False,
        },
        {
            "name": "fused_prologue_active_offset_gemm",
            "us_mean": _maybe_float(row.get(
                "fused_prologue_active_offset_gemm_total_us_mean")),
            "max_abs_diff_vs_xpu": _maybe_float(row.get(
                "fused_prologue_active_offset_gemm_vs_xpu_fused_moe_max_abs_diff")),
            "reference": False,
        },
        {
            "name": "fused_prologue_middle_layerlet",
            "us_mean": _maybe_float(row.get(
                "fused_prologue_middle_layerlet_total_us_mean")),
            "max_abs_diff_vs_xpu": _maybe_float(row.get(
                "fused_prologue_middle_layerlet_vs_xpu_fused_moe_max_abs_diff")),
            "reference": False,
        },
        {
            "name": "full_layerlet",
            "us_mean": _maybe_float(row.get("full_layerlet_total_us_mean")),
            "max_abs_diff_vs_xpu": _maybe_float(
                row.get("full_layerlet_vs_xpu_fused_moe_max_abs_diff")),
            "reference": False,
        },
        {
            "name": "onednn_sidecar",
            "us_mean": _maybe_float(row.get("onednn_sidecar_total_us_mean")),
            "max_abs_diff_vs_xpu": _maybe_float(
                row.get("onednn_sidecar_vs_xpu_fused_moe_max_abs_diff")),
            "reference": False,
        },
    ]

    usable_candidates = []
    for candidate in candidates:
        us_mean = candidate["us_mean"]
        max_abs_diff = candidate["max_abs_diff_vs_xpu"]
        exact = (
            max_abs_diff is not None and max_abs_diff <= exactness_threshold)
        speedup = (
            baseline_us / us_mean
            if baseline_us is not None and us_mean not in (None, 0.0)
            else None
        )
        candidate["exact_within_threshold"] = exact
        candidate["speedup_vs_xpu"] = speedup
        candidate["target_layerlet_met"] = (
            us_mean is not None and us_mean <= target_layerlet_us)
        candidate["beats_xpu_min_speedup"] = (
            (candidate.get("reference") is True) or
            (speedup is not None and speedup >= min_speedup_vs_xpu))
        if us_mean is not None:
            usable_candidates.append(candidate)

    exact_candidates = [
        candidate for candidate in usable_candidates
        if candidate["exact_within_threshold"]
    ]
    exact_nonreference = [
        candidate for candidate in exact_candidates
        if not candidate.get("reference")
    ]
    best_exact_any = (
        min(exact_candidates, key=lambda candidate: candidate["us_mean"])
        if exact_candidates else None
    )
    best_exact_nonreference = (
        min(exact_nonreference, key=lambda candidate: candidate["us_mean"])
        if exact_nonreference else None
    )

    candidate_ready_for_endpoint_gate = (
        best_exact_nonreference is not None and
        bool(best_exact_nonreference["target_layerlet_met"]) and
        bool(best_exact_nonreference["beats_xpu_min_speedup"]))

    if candidate_ready_for_endpoint_gate:
        status = "candidate_layerlet_meets_speed_and_exactness_gate"
    elif best_exact_nonreference is None:
        status = "no_exact_nonreference_layerlet_candidate"
    elif not best_exact_nonreference["beats_xpu_min_speedup"]:
        status = "best_exact_nonreference_does_not_beat_current_xpu"
    elif not best_exact_nonreference["target_layerlet_met"]:
        status = "best_exact_nonreference_misses_target_layerlet_us"
    else:
        status = "candidate_gate_not_met"

    return {
        "scope": "prologue_inclusive_full_moe_layerlet",
        "exactness_threshold": exactness_threshold,
        "target_layerlet_us": target_layerlet_us,
        "min_speedup_vs_xpu": min_speedup_vs_xpu,
        "baseline_xpu_fused_moe_us_mean": baseline_us,
        "candidates": candidates,
        "best_exact_any": best_exact_any,
        "best_exact_nonreference": best_exact_nonreference,
        "candidate_ready_for_endpoint_gate": candidate_ready_for_endpoint_gate,
        "status": status,
        "non_kernel_only_rule": (
            "Only full layerlet timings that include route/remap, quant, "
            "GEMM1, activation, quant2, GEMM2, and gather can satisfy this "
            "gate. Isolated GEMM/prologue timings are diagnostics only."
        ),
        "endpoint_promotion_blockers_after_gate": [
            "graph_path_tensor_capture_not_proven",
            "full_quality_gate_not_run",
            "accepted_lane_manifest_not_updated",
        ],
    }


def build_prologue_inclusive_gate_summary(
    rows: list[dict[str, Any]],
    *,
    exactness_threshold: float,
    target_layerlet_us: float,
    min_speedup_vs_xpu: float,
) -> dict[str, Any]:
    gates = [row.get("prologue_inclusive_gate", {}) for row in rows]
    best_nonreference = [
        gate.get("best_exact_nonreference")
        for gate in gates
        if gate.get("best_exact_nonreference")
    ]
    best_any = [
        gate.get("best_exact_any")
        for gate in gates
        if gate.get("best_exact_any")
    ]

    candidate_ready_rows = [
        gate for gate in gates if gate.get("candidate_ready_for_endpoint_gate")
    ]
    all_rows_ready = len(gates) > 0 and len(candidate_ready_rows) == len(gates)
    best_nonreference_overall = (
        min(best_nonreference, key=lambda candidate: candidate["us_mean"])
        if best_nonreference else None
    )
    best_any_overall = (
        min(best_any, key=lambda candidate: candidate["us_mean"])
        if best_any else None
    )
    worst_best_nonreference_us = (
        max(
            float(candidate["us_mean"])
            for candidate in best_nonreference
            if candidate.get("us_mean") is not None
        )
        if best_nonreference else None
    )

    if all_rows_ready:
        status = "all_rows_have_exact_nonreference_layerlet_candidate"
    elif candidate_ready_rows:
        status = "some_rows_have_exact_nonreference_layerlet_candidate"
    elif best_nonreference:
        status = "exact_nonreference_candidates_exist_but_gate_not_met"
    else:
        status = "no_exact_nonreference_layerlet_candidate"

    return {
        "scope": "aggregate_prologue_inclusive_full_moe_layerlet",
        "exactness_threshold": exactness_threshold,
        "target_layerlet_us": target_layerlet_us,
        "min_speedup_vs_xpu": min_speedup_vs_xpu,
        "rows_checked": len(gates),
        "rows_ready_for_endpoint_gate": len(candidate_ready_rows),
        "all_rows_ready_for_endpoint_gate": all_rows_ready,
        "best_exact_any_overall": best_any_overall,
        "best_exact_nonreference_overall": best_nonreference_overall,
        "worst_best_exact_nonreference_us_mean": worst_best_nonreference_us,
        "status": status,
        "endpoint_promotion_allowed": False,
        "endpoint_promotion_note": (
            "This benchmark can nominate a layerlet candidate only. Endpoint "
            "promotion still requires graph-path tensor capture, accepted-lane "
            "quality gates, and a manifest update."
        ),
    }


def write_markdown(path: str, results: dict[str, Any]) -> None:
    rows = results.get("results", [])
    fused = bool(results.get("fused_silu_quant_enabled"))

    def max_row_float(field: str) -> float:
        return max(
            (float(row[field]) for row in rows if row.get(field) is not None),
            default=float("nan"),
        )

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
        "prologue_scratch": max(
            (float(row.get(
                "xpu_prologue_scratch_vs_xpu_fused_moe_max_abs_diff", 0.0))
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
        "fused_prologue_active_offset": max(
            (float(row.get(
                "fused_prologue_active_offset_gemm_vs_xpu_fused_moe_max_abs_diff",
                0.0,
            )) for row in rows if row.get(
                "fused_prologue_active_offset_gemm_vs_xpu_fused_moe_max_abs_diff")
             is not None),
            default=float("nan"),
        ),
        "fused_prologue_middle_layerlet": max(
            (float(row.get(
                "fused_prologue_middle_layerlet_vs_xpu_fused_moe_max_abs_diff",
                0.0,
            )) for row in rows if row.get(
                "fused_prologue_middle_layerlet_vs_xpu_fused_moe_max_abs_diff")
             is not None),
            default=float("nan"),
        ),
        "full_layerlet": max(
            (float(row.get(
                "full_layerlet_vs_xpu_fused_moe_max_abs_diff",
                0.0,
            )) for row in rows if row.get(
                "full_layerlet_vs_xpu_fused_moe_max_abs_diff") is not None),
            default=float("nan"),
        ),
        "onednn_sidecar": max(
            (float(row.get(
                "onednn_sidecar_vs_xpu_fused_moe_max_abs_diff",
                0.0,
            )) for row in rows if row.get(
                "onednn_sidecar_vs_xpu_fused_moe_max_abs_diff") is not None),
            default=float("nan"),
        ),
        "xpu_vs_rows_oracle":
        max_row_float("xpu_fused_moe_vs_rows_oracle_max_abs_diff"),
        "offset_vs_rows_oracle":
        max_row_float("offset_oracle_vs_rows_oracle_max_abs_diff"),
        "full_layerlet_vs_rows_oracle":
        max_row_float("full_layerlet_vs_rows_oracle_max_abs_diff"),
        "onednn_sidecar_vs_rows_oracle":
        max_row_float("onednn_sidecar_vs_rows_oracle_max_abs_diff"),
        "rows_oracle_vs_bf16_reference":
        max_row_float("rows_oracle_vs_bf16_reference_max_abs_diff"),
    }

    lines = []
    lines.append("# Qwen3.6 INT8 MoE Route Replay")
    lines.append("")
    lines.append(f"- Fused SiLU+quant enabled: `{fused}`.")
    lines.append(f"- TP size: `{results['tp_size']}`.")
    lines.append(f"- Result rows: `{len(rows)}`.")
    if rows:
        lines.append(
            f"- Route mode/source: `{rows[0].get('topk_source')}`.")
    if rows:
        lines.append(
            f"- Quant out-variant available: "
            f"`{bool(rows[0].get('quant_out_op_available'))}`."
        )
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
    gate_summary = results.get("prologue_inclusive_gate_summary", {})
    if gate_summary:
        lines.append(
            f"- Prologue-inclusive target: "
            f"`{_fmt(gate_summary.get('target_layerlet_us'))} us/layerlet`."
        )
        lines.append(
            f"- Exactness threshold: "
            f"`{_fmt(gate_summary.get('exactness_threshold'), 6)}`."
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
        f"- Prologue-scratch `xpu_fused_moe` max abs diff: "
        f"`{_fmt(max_diffs['prologue_scratch'])}`."
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
    if any(row.get("active_offset_gemm_enabled") for row in rows):
        lines.append(
            f"- Fused-prologue active-offset-GEMM max abs diff: "
            f"`{_fmt(max_diffs['fused_prologue_active_offset'])}`."
        )
    if any(row.get("middle_layerlet_enabled") for row in rows):
        lines.append(
            f"- Fused-prologue middle-layerlet max abs diff: "
            f"`{_fmt(max_diffs['fused_prologue_middle_layerlet'])}`."
        )
    if any(row.get("full_layerlet_enabled") for row in rows):
        lines.append(
            f"- Full C++ layerlet max abs diff: "
            f"`{_fmt(max_diffs['full_layerlet'])}`."
        )
    if any(row.get("onednn_sidecar_enabled") for row in rows):
        lines.append(
            f"- oneDNN sidecar max abs diff: "
            f"`{_fmt(max_diffs['onednn_sidecar'])}`."
        )
    if any(row.get("real_routing_oracle_enabled") for row in rows):
        lines.append("")
        lines.append("### Rows-Oracle Checks")
        lines.append("")
        lines.append(
            "- Current `xpu_fused_moe` max abs diff versus forced "
            f"rows-per-expert oracle: `{_fmt(max_diffs['xpu_vs_rows_oracle'])}`."
        )
        lines.append(
            "- Forced offset-GEMM max abs diff versus rows-per-expert oracle: "
            f"`{_fmt(max_diffs['offset_vs_rows_oracle'])}`."
        )
        if any(row.get("full_layerlet_enabled") for row in rows):
            lines.append(
                "- Full C++ layerlet max abs diff versus rows-per-expert "
                f"oracle: `{_fmt(max_diffs['full_layerlet_vs_rows_oracle'])}`."
            )
        if any(row.get("onednn_sidecar_enabled") for row in rows):
            lines.append(
                "- oneDNN sidecar max abs diff versus rows-per-expert "
                f"oracle: `{_fmt(max_diffs['onednn_sidecar_vs_rows_oracle'])}`."
            )
        if any(row.get("real_routing_bf16_reference_enabled") for row in rows):
            lines.append(
                "- Rows-per-expert INT8 oracle max abs diff versus BF16 "
                "dequantized reference: "
                f"`{_fmt(max_diffs['rows_oracle_vs_bf16_reference'])}`."
            )
    lines.append("")
    lines.append("## Timing")
    lines.append("")
    mean_xpu = sum(float(row.get("total_us_mean", 0.0))
                   for row in rows) / max(1, len(rows))
    mean_xpu_scratch = sum(
        float(row.get("xpu_fused_moe_scratch_total_us_mean", 0.0))
        for row in rows) / max(1, len(rows))
    mean_xpu_prologue_scratch = sum(
        float(row.get("xpu_fused_moe_prologue_scratch_total_us_mean", 0.0))
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
    active_offset_rows = [
        row for row in rows
        if row.get("fused_prologue_active_offset_gemm_total_us_mean")
        is not None
    ]
    mean_prologue_active_offset = (
        sum(float(row["fused_prologue_active_offset_gemm_total_us_mean"])
            for row in active_offset_rows) / len(active_offset_rows)
        if active_offset_rows else None
    )
    middle_layerlet_rows = [
        row for row in rows
        if row.get("fused_prologue_middle_layerlet_total_us_mean") is not None
    ]
    mean_prologue_middle_layerlet = (
        sum(float(row["fused_prologue_middle_layerlet_total_us_mean"])
            for row in middle_layerlet_rows) / len(middle_layerlet_rows)
        if middle_layerlet_rows else None
    )
    full_layerlet_rows = [
        row for row in rows if row.get("full_layerlet_total_us_mean")
        is not None
    ]
    mean_full_layerlet = (
        sum(float(row["full_layerlet_total_us_mean"])
            for row in full_layerlet_rows) / len(full_layerlet_rows)
        if full_layerlet_rows else None
    )
    onednn_sidecar_rows = [
        row for row in rows if row.get("onednn_sidecar_total_us_mean")
        is not None
    ]
    mean_onednn_sidecar = (
        sum(float(row["onednn_sidecar_total_us_mean"])
            for row in onednn_sidecar_rows) / len(onednn_sidecar_rows)
        if onednn_sidecar_rows else None
    )
    mean_onednn_sidecar_middle = (
        sum(float(row["onednn_sidecar_middle_wall_us_mean"])
            for row in onednn_sidecar_rows
            if row.get("onednn_sidecar_middle_wall_us_mean") is not None)
        / len([
            row for row in onednn_sidecar_rows
            if row.get("onednn_sidecar_middle_wall_us_mean") is not None
        ])
        if any(row.get("onednn_sidecar_middle_wall_us_mean") is not None
               for row in onednn_sidecar_rows)
        else None
    )
    lines.append(f"- Mean `xpu_fused_moe`: `{_fmt(mean_xpu)} us`.")
    lines.append(
        f"- Mean scratch `xpu_fused_moe`: `{_fmt(mean_xpu_scratch)} us`.")
    lines.append(
        "- Mean prologue-scratch `xpu_fused_moe`: "
        f"`{_fmt(mean_xpu_prologue_scratch)} us`."
    )
    lines.append(f"- Mean preallocated staged: `{_fmt(mean_prealloc)} us`.")
    lines.append(
        f"- Mean fused-prologue staged: `{_fmt(mean_prologue)} us`.")
    if mean_prologue_offset is not None:
        lines.append(
            "- Mean fused-prologue offset-GEMM staged: "
            f"`{_fmt(mean_prologue_offset)} us`."
        )
    if mean_prologue_active_offset is not None:
        lines.append(
            "- Mean fused-prologue active-offset-GEMM staged: "
            f"`{_fmt(mean_prologue_active_offset)} us`."
        )
    if mean_prologue_middle_layerlet is not None:
        lines.append(
            "- Mean fused-prologue middle-layerlet staged: "
            f"`{_fmt(mean_prologue_middle_layerlet)} us`."
        )
    if mean_full_layerlet is not None:
        lines.append(
            "- Mean full C++ layerlet: "
            f"`{_fmt(mean_full_layerlet)} us`."
        )
    if mean_onednn_sidecar is not None:
        lines.append(
            "- Mean oneDNN sidecar total: "
            f"`{_fmt(mean_onednn_sidecar)} us`."
        )
    if mean_onednn_sidecar_middle is not None:
        lines.append(
            "- Mean oneDNN sidecar internal middle wall: "
            f"`{_fmt(mean_onednn_sidecar_middle)} us`."
        )
    lines.append("")
    lines.append(
        "| rows | route start | active experts | xpu fused us | "
        "xpu scratch us | xpu prologue scratch us | prealloc staged us | "
        "fused prologue staged us | "
        "fused prologue offset us | active offset us | middle layerlet us | "
        "full layerlet us | oneDNN sidecar us | gemm1 us | gemm2 us | "
        "act+quant2 us |"
    )
    lines.append(
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for row in rows:
        comp = row.get("components_us_mean", {})
        topk = row.get("topk_summary", {})
        lines.append(
            f"| {row.get('rows')} | {row.get('route_start_index')} | "
            f"{topk.get('active_experts')} | "
            f"{_fmt(row.get('total_us_mean'))} | "
            f"{_fmt(row.get('xpu_fused_moe_scratch_total_us_mean'))} | "
            f"{_fmt(row.get('xpu_fused_moe_prologue_scratch_total_us_mean'))} | "
            f"{_fmt(row.get('preallocated_staged_total_us_mean'))} | "
            f"{_fmt(row.get('fused_prologue_staged_total_us_mean'))} | "
            f"{_fmt(row.get('fused_prologue_offset_gemm_total_us_mean'))} | "
            f"{_fmt(row.get('fused_prologue_active_offset_gemm_total_us_mean'))} | "
            f"{_fmt(row.get('fused_prologue_middle_layerlet_total_us_mean'))} | "
            f"{_fmt(row.get('full_layerlet_total_us_mean'))} | "
            f"{_fmt(row.get('onednn_sidecar_total_us_mean'))} | "
            f"{_fmt(comp.get('gemm1'))} | "
            f"{_fmt(comp.get('gemm2'))} | "
            f"{_fmt(comp.get('activation_plus_quant2'))} |"
        )
    lines.append("")

    if any(int(row.get("stage_timing_iterations") or 0) > 0 for row in rows):
        lines.append("## Prologue Offset Stage Timing")
        lines.append("")
        lines.append(
            "These stage timings are for the exact fused-prologue "
            "offset-GEMM candidate and are used to decide the next native "
            "layerlet boundary. They are single-device replay diagnostics."
        )
        lines.append("")
        lines.append(
            "| rows | route start | total us | prologue | quant1 | gemm1 | "
            "activation | quant2 | gemm2 | gather | component sum |"
        )
        lines.append(
            "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for row in rows:
            comp = row.get("fused_prologue_offset_components_us_mean", {})
            if not comp:
                continue
            lines.append(
                f"| {row.get('rows')} | {row.get('route_start_index')} | "
                f"{_fmt(row.get('fused_prologue_offset_gemm_total_us_mean'))} | "
                f"{_fmt(comp.get('prologue'))} | "
                f"{_fmt(comp.get('quant1'))} | "
                f"{_fmt(comp.get('gemm1'))} | "
                f"{_fmt(comp.get('activation'))} | "
                f"{_fmt(comp.get('quant2'))} | "
                f"{_fmt(comp.get('gemm2'))} | "
                f"{_fmt(comp.get('gather'))} | "
                f"{_fmt(comp.get('component_sum'))} |"
            )
        lines.append("")

    if any(row.get("graph_replay") for row in rows):
        lines.append("## Graph Replay Timing")
        lines.append("")
        lines.append(
            "These timings capture each eligible candidate in an XPU graph "
            "and time `graph.replay()`. They remain single-device replay "
            "diagnostics, not endpoint throughput."
        )
        lines.append("")
        lines.append("| rows | route start | candidate | status | graph us |")
        lines.append("|---:|---:|---|---|---:|")
        for row in rows:
            for item in row.get("graph_replay", []):
                lines.append(
                    f"| {row.get('rows')} | {row.get('route_start_index')} | "
                    f"{item.get('name')} | {item.get('status')} | "
                    f"{_fmt(item.get('us_mean'))} |")
        lines.append("")

    lines.append("## Prologue-Inclusive Gate")
    lines.append("")
    if gate_summary:
        lines.append(f"- Gate status: `{gate_summary.get('status')}`.")
        lines.append(
            "- Rows ready for endpoint gate: "
            f"`{gate_summary.get('rows_ready_for_endpoint_gate')}` / "
            f"`{gate_summary.get('rows_checked')}`."
        )
        best_nonref = gate_summary.get("best_exact_nonreference_overall")
        if best_nonref:
            lines.append(
                "- Best exact non-reference full-layerlet candidate: "
                f"`{best_nonref.get('name')}` at "
                f"`{_fmt(best_nonref.get('us_mean'))} us` "
                f"(`{_fmt(best_nonref.get('speedup_vs_xpu'))}x` vs current "
                "`xpu_fused_moe`)."
            )
        else:
            lines.append(
                "- No exact non-reference full-layerlet candidate was available."
            )
        lines.append(
            "- Endpoint promotion allowed by this artifact: "
            f"`{bool(gate_summary.get('endpoint_promotion_allowed'))}`."
        )
        lines.append(
            "- Endpoint promotion still requires graph-path tensor capture, "
            "accepted-lane quality gates, and a manifest update."
        )
    else:
        lines.append("- No prologue-inclusive gate summary was present.")
    lines.append("")
    lines.append(
        "| rows | route start | best exact nonref | best nonref us | "
        "speedup vs xpu | target met | status |"
    )
    lines.append("|---:|---:|---|---:|---:|---:|---|")
    for row in rows:
        gate = row.get("prologue_inclusive_gate", {})
        candidate = gate.get("best_exact_nonreference") or {}
        lines.append(
            f"| {row.get('rows')} | {row.get('route_start_index')} | "
            f"{candidate.get('name', 'none')} | "
            f"{_fmt(candidate.get('us_mean'))} | "
            f"{_fmt(candidate.get('speedup_vs_xpu'))} | "
            f"{candidate.get('target_layerlet_met', False)} | "
            f"{gate.get('status', 'n/a')} |"
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
    if mean_onednn_sidecar is not None:
        if mean_full_layerlet is not None and mean_onednn_sidecar > mean_full_layerlet:
            lines.append(
                "- The oneDNN sidecar is exact, but its prologue-inclusive "
                "wrapper is slower than the current full C++ layerlet in this "
                "route replay. Keep the internal middle-wall timing as a "
                "diagnostic only; do not promote the sidecar endpoint path."
            )
        else:
            lines.append(
                "- The oneDNN sidecar is exact and should be evaluated by the "
                "prologue-inclusive gate before any endpoint promotion."
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
    parser.add_argument(
        "--target-layerlet-us",
        type=float,
        default=160.0,
        help=(
            "Full MoE layerlet mean latency target for a plausible >200 tok/s "
            "single-request decode lane. This gate includes prologue and "
            "gather work; isolated kernel timings do not satisfy it."
        ),
    )
    parser.add_argument(
        "--exactness-threshold",
        type=float,
        default=0.0,
        help=(
            "Maximum allowed max_abs_diff versus xpu_fused_moe for a candidate "
            "to count as no-quality-loss in this microbench gate."
        ),
    )
    parser.add_argument(
        "--min-speedup-vs-xpu",
        type=float,
        default=1.0,
        help=(
            "Minimum full-layerlet speedup over the current xpu_fused_moe "
            "reference required for a non-reference candidate."
        ),
    )
    parser.add_argument("--dtype", choices=("bf16", "fp16"), default="bf16")
    parser.add_argument("--device", default="xpu")
    parser.add_argument("--output-json")
    parser.add_argument(
        "--synthetic-route-mode",
        choices=("uniform", "hot_skew"),
        default="uniform",
        help=(
            "Synthetic top-k routing pattern used when --route-jsonl is not "
            "provided. hot_skew keeps many experts at zero rows and stresses "
            "skewed real-routing behavior."
        ),
    )
    parser.add_argument(
        "--real-routing-oracle",
        action="store_true",
        help=(
            "Also compare candidates against a forced rows-per-expert W8A8 "
            "path with offsets/layerlets/prologue disabled. This catches "
            "offset/layerlet bugs that are invisible when comparing two paths "
            "sharing the same offset kernels."
        ),
    )
    parser.add_argument(
        "--real-routing-bf16-reference",
        action="store_true",
        help=(
            "When --real-routing-oracle is enabled, also compare the forced "
            "rows-per-expert INT8 path against ref_fused_moe's dequantized "
            "BF16/FP32 reference. This is a drift diagnostic, not an exact "
            "promotion gate for Quark W8A8."
        ),
    )
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
    parser.add_argument(
        "--enable-active-offset-gemm",
        action="store_true",
        help=(
            "Benchmark the experimental fused-prologue path that feeds "
            "expert_first_token_offset plus compact active_expert_ids directly "
            "to the W8A8 grouped GEMM op."
        ),
    )
    parser.add_argument(
        "--enable-middle-layerlet",
        action="store_true",
        help=(
            "Benchmark fused-prologue plus the C++ W8A8 middle layerlet "
            "(GEMM1 + fused SiLU/quant + GEMM2) as an exact full-route "
            "candidate."
        ),
    )
    parser.add_argument(
        "--enable-full-layerlet",
        action="store_true",
        help=(
            "Benchmark the experimental C++ wrapper that calls prologue, "
            "quant1, W8A8 middle layerlet, and gather behind one _xpu_C op."
        ),
    )
    parser.add_argument(
        "--enable-onednn-sidecar",
        action="store_true",
        help=(
            "Benchmark the diagnostic cached oneDNN grouped-matmul sidecar "
            "inside the fused-prologue route replay. This is not endpoint "
            "promotion by itself; use it to decide whether the oneDNN "
            "middle boundary is worth making graph-safe/persistent."
        ),
    )
    parser.add_argument(
        "--onednn-sidecar-mode",
        type=int,
        default=23,
        help=(
            "Execution mode passed to qwen36_moe_onednn_sidecar_probe. "
            "Mode 23 is the cached GEMM1+activation/quant+GEMM2 path with "
            "post-GEMM2 wait used by earlier diagnostics."
        ),
    )
    parser.add_argument(
        "--graph-replay-timing",
        action="store_true",
        help=(
            "Capture and time XPU graph replay for preallocated exact "
            "candidates. This is a replay diagnostic, not an endpoint result."
        ),
    )
    parser.add_argument("--graph-warmup", type=int, default=3)
    parser.add_argument("--graph-iterations", type=int, default=30)
    parser.add_argument(
        "--stage-timing-iterations",
        type=int,
        default=0,
        help=(
            "Collect event-level stage timings for fused-prologue candidates "
            "in a separate diagnostic loop. Normal candidate totals are "
            "measured without this extra event overhead."
        ),
    )
    parser.add_argument("--markdown-out")
    args = parser.parse_args()
    if args.real_routing_bf16_reference and not args.real_routing_oracle:
        parser.error(
            "--real-routing-bf16-reference requires --real-routing-oracle")

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
        "synthetic_route_mode": args.synthetic_route_mode,
        "real_routing_oracle_enabled": args.real_routing_oracle,
        "real_routing_bf16_reference_enabled":
        args.real_routing_bf16_reference,
        "runtime_identity": collect_runtime_identity(args),
        "prologue_inclusive_gate_summary":
        build_prologue_inclusive_gate_summary(
            benchmark_results,
            exactness_threshold=args.exactness_threshold,
            target_layerlet_us=args.target_layerlet_us,
            min_speedup_vs_xpu=args.min_speedup_vs_xpu,
        ),
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
