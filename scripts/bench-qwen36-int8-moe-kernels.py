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
        "components_us_mean": components,
        "manual_vs_xpu_fused_moe_max_abs_diff": max_abs_diff,
        "xpu_scratch_vs_xpu_fused_moe_max_abs_diff": xpu_scratch_max_abs_diff,
        "preallocated_vs_xpu_fused_moe_max_abs_diff": prealloc_max_abs_diff,
        "iterations": args.iterations,
        "warmup": args.warmup,
    }


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
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
