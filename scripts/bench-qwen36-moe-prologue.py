#!/usr/bin/env python3
"""Benchmark XPU fused_moe_prologue against the current Qwen3.6 MoE remap.

This is a route-exact screen for a possible one-dispatch MoE path. The current
INT8 MoE implementation uses rows_per_expert.zero_() plus remap_hidden_states()
before quantization and grouped GEMM. vllm-xpu-kernels also has a
fused_moe_prologue() op that builds route maps and expands input rows into a
workspace. This script checks whether that op is an exact and faster candidate
for the Qwen3.6 W8A8 decode route windows.

It does not modify the live endpoint and it is not a full-model speed result.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

import torch

import vllm_xpu_kernels._moe_C  # noqa: F401


DEFAULT_ROUTE_JSONL = (
    "data/qwen36-quark-int8-tp4-routecapture6-routes-rank0-20260611.jsonl"
)
DEFAULT_LAYER_REGEX = r"layers\.9\."
DEFAULT_STAGE_REGEX = r"^quark_int8_apply$"


def load_moe_bench_module():
    path = Path(__file__).with_name("bench-qwen36-int8-moe-kernels.py")
    spec = importlib.util.spec_from_file_location("qwen36_moe_bench", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def ceil_div(a: int, b: int) -> int:
    return (a + b - 1) // b


def compute_num_tokens_per_block(num_tokens: int, num_experts_per_node: int) -> int:
    for num_tokens_per_block in [32, 64, 128, 256, 512, 1024]:
        num_blocks_per_seq = ceil_div(num_tokens, num_tokens_per_block)
        if num_blocks_per_seq * num_experts_per_node <= num_tokens_per_block:
            return num_tokens_per_block
    return 1024


def align_256(size: int) -> int:
    return (size + 255) & ~255


def make_workspace_layout(
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
        "overlapped_gemm1_gemm2_inputs": num_moe_inputs * hidden_size
        * torch.tensor([], dtype=dtype).element_size(),
        "permuted_act_scales": 0
        if scale_dtype is None
        else num_moe_inputs
        * (hidden_size // block_k)
        * torch.tensor([], dtype=scale_dtype).element_size(),
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


def make_events():
    return (
        torch.xpu.Event(enable_timing=True),
        torch.xpu.Event(enable_timing=True),
    )


def elapsed_us(start: torch.xpu.Event, end: torch.xpu.Event) -> float:
    return float(start.elapsed_time(end) * 1000.0)


def timed(fn):
    start, end = make_events()
    start.record()
    result = fn()
    end.record()
    torch.xpu.synchronize()
    return result, elapsed_us(start, end)


def summarize(values: list[float]) -> dict[str, float]:
    values = [float(v) for v in values]
    ordered = sorted(values)
    n = len(values)
    mid = n // 2
    median = ordered[mid] if n % 2 else (ordered[mid - 1] + ordered[mid]) / 2.0
    return {
        "count": n,
        "mean": sum(values) / n,
        "median": median,
        "min": min(values),
        "max": max(values),
    }


def run_case(
    *,
    helper,
    text_config: dict[str, Any],
    rows: int,
    route_topk_rows: list[list[int]],
    route_start_index: int,
    iterations: int,
    warmup: int,
    tp_size: int,
    dtype: torch.dtype,
    device: str,
    seed: int,
) -> dict[str, Any]:
    hidden_size = int(text_config["hidden_size"])
    inter_size = int(text_config["moe_intermediate_size"]) // tp_size
    num_experts = int(text_config["num_experts"])
    topk = int(text_config["num_experts_per_tok"])

    inputs = helper.make_inputs(
        rows=rows,
        hidden_size=hidden_size,
        inter_size=inter_size,
        num_experts=num_experts,
        topk=topk,
        dtype=dtype,
        device=device,
        seed=seed + rows + route_start_index,
        route_topk_rows=route_topk_rows,
        route_start_index=route_start_index,
    )

    hidden_states = inputs["hidden_states"]
    topk_ids = inputs["topk_ids"]
    topk_weights = inputs["topk_weights"]
    remapped = torch.empty((rows * topk, hidden_size),
                           dtype=dtype,
                           device=device)
    rows_per_expert = torch.empty((num_experts),
                                  dtype=torch.int32,
                                  device=device)
    unpermuted = torch.empty((rows, topk), dtype=torch.int32, device=device)

    layout, workspace_bytes = make_workspace_layout(
        rows=rows,
        hidden_size=hidden_size,
        inter_size=inter_size,
        num_experts=num_experts,
        topk=topk,
        dtype=dtype,
    )
    workspace = torch.empty((workspace_bytes), dtype=torch.uint8, device=device)
    prologue_expand = workspace_view(
        workspace,
        layout,
        "overlapped_gemm1_gemm2_inputs",
        dtype,
        (rows * topk, hidden_size),
    )
    expert_offsets = workspace_view(
        workspace,
        layout,
        "expert_first_token_offset",
        torch.int64,
        (num_experts + 1,),
    )

    def current_remap_once():
        rows_per_expert.zero_()
        torch.ops._moe_C.remap_hidden_states(
            hidden_states=hidden_states,
            hidden_states_scales=None,
            remapped_hidden_states=remapped,
            remapped_hidden_states_scales=None,
            expert_map=None,
            rows_per_expert=rows_per_expert,
            unpermuted_row_to_permuted_row=unpermuted,
            topk_ids=topk_ids,
            total_experts_num=num_experts,
            local_experts_num=num_experts,
        )

    def prologue_once():
        torch.ops._moe_C.fused_moe_prologue(
            input=hidden_states,
            input_scales=None,
            token_selected_experts=topk_ids,
            token_final_scales=topk_weights,
            workspace=workspace,
            hidden_size=hidden_size,
            inter_size=inter_size,
            block_k=1,
            ep_rank=0,
            ep_size=1,
            num_experts_on_rank=num_experts,
        )

    current_remap_once()
    prologue_once()
    torch.xpu.synchronize()

    offsets_tail = expert_offsets[1:1 + num_experts]
    zero = torch.zeros((1,), device=device, dtype=torch.int64)
    prologue_counts = offsets_tail - torch.cat((zero, offsets_tail[:-1]))
    torch.xpu.synchronize()
    max_expand_diff = float((remapped - prologue_expand).abs().max().item())
    max_counts_diff = int(
        (rows_per_expert.to(torch.int64) - prologue_counts).abs().max().item())

    current_us = []
    prologue_us = []
    for _ in range(warmup):
        current_remap_once()
        prologue_once()
    torch.xpu.synchronize()

    for _ in range(iterations):
        _, usec = timed(current_remap_once)
        current_us.append(usec)
        _, usec = timed(prologue_once)
        prologue_us.append(usec)

    return {
        "rows": rows,
        "route_start_index": route_start_index,
        "workspace_bytes": workspace_bytes,
        "topk_summary": helper.summarize_topk_ids(topk_ids),
        "max_expand_abs_diff": max_expand_diff,
        "max_rows_per_expert_diff": max_counts_diff,
        "current_zero_plus_remap_us": summarize(current_us),
        "fused_moe_prologue_us": summarize(prologue_us),
        "delta_us_mean": summarize(prologue_us)["mean"] -
        summarize(current_us)["mean"],
    }


def write_markdown(path: str, payload: dict[str, Any]) -> None:
    lines = [
        "# Qwen3.6 MoE Prologue Route Replay",
        "",
        f"- Result rows: `{len(payload['results'])}`.",
        f"- Route source: `{payload['route_metadata']['route_jsonl']}`.",
        f"- Route records matched: `{payload['route_metadata']['records_matched']}`; "
        f"top-k rows loaded: `{payload['route_metadata']['topk_rows_loaded']}`.",
        f"- Route start indices: `"
        + ",".join(str(item) for item in payload["route_start_indices"])
        + "`.",
        "",
        "## Timing",
        "",
        "| rows | route start | active experts | current zero+remap us | "
        "fused prologue us | delta us | expand diff | count diff |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["results"]:
        lines.append(
            f"| {row['rows']} | {row['route_start_index']} | "
            f"{row['topk_summary']['active_experts']} | "
            f"{row['current_zero_plus_remap_us']['mean']:.3f} | "
            f"{row['fused_moe_prologue_us']['mean']:.3f} | "
            f"{row['delta_us_mean']:.3f} | "
            f"{row['max_expand_abs_diff']:.3f} | "
            f"{row['max_rows_per_expert_diff']} |"
        )
    exact = all(
        row["max_expand_abs_diff"] == 0.0
        and row["max_rows_per_expert_diff"] == 0
        for row in payload["results"]
    )
    mean_current = payload["summary"]["current_zero_plus_remap_us"]["mean"]
    mean_prologue = payload["summary"]["fused_moe_prologue_us"]["mean"]
    lines.extend([
        "",
        "## Decision",
        "",
        f"- Exact route expansion/count parity: `{exact}`.",
        f"- Mean current zero+remap: `{mean_current:.3f} us`.",
        f"- Mean fused_moe_prologue: `{mean_prologue:.3f} us`.",
    ])
    if exact and mean_prologue < mean_current:
        lines.append(
            "- Existing fused_moe_prologue is a candidate for the next "
            "one-dispatch MoE layerlet screen."
        )
    elif exact:
        lines.append(
            "- Existing fused_moe_prologue is exact but not faster than the "
            "current zero+remap path in this route window."
        )
    else:
        lines.append(
            "- Existing fused_moe_prologue is not a drop-in exact replacement "
            "for the current route expansion in this fixture."
        )
    lines.append("")
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-config", default=None)
    parser.add_argument("--route-jsonl", default=DEFAULT_ROUTE_JSONL)
    parser.add_argument("--route-layer-regex", default=DEFAULT_LAYER_REGEX)
    parser.add_argument("--route-stage-regex", default=DEFAULT_STAGE_REGEX)
    parser.add_argument("--route-min-num-tokens", type=int, default=1)
    parser.add_argument("--route-max-num-tokens", type=int, default=1)
    parser.add_argument("--route-start-indices", default="0:64:4")
    parser.add_argument("--rows", type=int, default=1)
    parser.add_argument("--iterations", type=int, default=30)
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--tp-size", type=int, default=4)
    parser.add_argument("--dtype", choices=("bf16", "fp16"), default="bf16")
    parser.add_argument("--device", default="xpu")
    parser.add_argument("--seed", type=int, default=20260612)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--markdown-out")
    args = parser.parse_args()

    helper = load_moe_bench_module()
    model_config = args.model_config or helper.DEFAULT_MODEL_CONFIG
    text_config = helper.load_text_config(model_config)
    route_rows, route_metadata = helper.load_route_topk_rows(
        args.route_jsonl,
        layer_regex=args.route_layer_regex,
        stage_regex=args.route_stage_regex,
        min_num_tokens=args.route_min_num_tokens,
        max_num_tokens=args.route_max_num_tokens,
    )
    route_start_indices = helper.parse_int_list(args.route_start_indices)
    dtype = torch.bfloat16 if args.dtype == "bf16" else torch.float16

    results = [
        run_case(
            helper=helper,
            text_config=text_config,
            rows=args.rows,
            route_topk_rows=route_rows,
            route_start_index=start_index,
            iterations=args.iterations,
            warmup=args.warmup,
            tp_size=args.tp_size,
            dtype=dtype,
            device=args.device,
            seed=args.seed,
        )
        for start_index in route_start_indices
    ]

    payload = {
        "model_config": model_config,
        "route_metadata": route_metadata,
        "route_start_indices": route_start_indices,
        "rows": args.rows,
        "iterations": args.iterations,
        "warmup": args.warmup,
        "tp_size": args.tp_size,
        "dtype": args.dtype,
        "results": results,
        "summary": {
            "current_zero_plus_remap_us": summarize([
                row["current_zero_plus_remap_us"]["mean"] for row in results
            ]),
            "fused_moe_prologue_us": summarize([
                row["fused_moe_prologue_us"]["mean"] for row in results
            ]),
            "delta_us_mean": summarize([
                row["delta_us_mean"] for row in results
            ]),
            "max_expand_abs_diff": max(
                row["max_expand_abs_diff"] for row in results),
            "max_rows_per_expert_diff": max(
                row["max_rows_per_expert_diff"] for row in results),
        },
    }

    text = json.dumps(payload, indent=2, sort_keys=True)
    Path(args.output_json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output_json).write_text(text + "\n", encoding="utf-8")
    if args.markdown_out:
        Path(args.markdown_out).parent.mkdir(parents=True, exist_ok=True)
        write_markdown(args.markdown_out, payload)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
