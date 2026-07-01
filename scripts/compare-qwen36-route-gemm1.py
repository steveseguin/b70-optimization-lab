#!/usr/bin/env python3
"""Compare Qwen3.6 routed GEMM1 against the exact offsets GEMM1 path."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

import torch

import vllm_xpu_kernels._xpu_C  # noqa: F401


BENCH_PATH = (
    Path(__file__).resolve().parent / "bench-qwen36-int8-moe-kernels.py"
)


def load_bench_module() -> Any:
    spec = importlib.util.spec_from_file_location("qwen36_moe_bench",
                                                  BENCH_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {BENCH_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_topk(value: str) -> list[int]:
    topk = [int(item.strip()) for item in value.split(",") if item.strip()]
    if len(topk) != 8:
        raise argparse.ArgumentTypeError("topk must contain exactly 8 IDs")
    return topk


def _row_summary(
    *,
    topk_idx: int,
    expert: int,
    permuted_row: int,
    ref: torch.Tensor,
    route: torch.Tensor,
) -> dict[str, Any]:
    row_diff = (ref[permuted_row] - route[permuted_row]).abs()
    candidate_diffs = (ref - route[permuted_row]).abs().amax(dim=1)
    best_ref_row = int(candidate_diffs.argmin().item())
    max_col = int(row_diff.argmax().item())
    return {
        "topk_idx": topk_idx,
        "expert": expert,
        "permuted_row": permuted_row,
        "row_max_abs_diff": float(row_diff.max().item()),
        "row_mean_abs_diff": float(row_diff.float().mean().item()),
        "max_diff_col": max_col,
        "ref_at_max_col": float(ref[permuted_row, max_col].float().item()),
        "route_at_max_col": float(route[permuted_row, max_col].float().item()),
        "best_matching_ref_row": best_ref_row,
        "best_matching_ref_row_max_abs_diff": float(
            candidate_diffs[best_ref_row].item()),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--topk",
                        type=parse_topk,
                        default=parse_topk("228,29,94,77,126,61,250,44"))
    parser.add_argument("--rows", type=int, default=1)
    parser.add_argument("--hidden-size", type=int, default=2048)
    parser.add_argument("--inter-size", type=int, default=128)
    parser.add_argument("--num-experts", type=int, default=256)
    parser.add_argument("--seed", type=int, default=20260609)
    parser.add_argument("--device", default="xpu")
    parser.add_argument("--output-json")
    args = parser.parse_args()

    if args.rows != 1:
        raise ValueError("The routed GEMM1 diagnostic currently targets rows=1")

    bench = load_bench_module()
    dtype = torch.bfloat16
    inputs = bench.make_inputs(
        rows=args.rows,
        hidden_size=args.hidden_size,
        inter_size=args.inter_size,
        num_experts=args.num_experts,
        topk=8,
        dtype=dtype,
        device=args.device,
        seed=args.seed,
        synthetic_route_mode="uniform",
        route_topk_rows=[args.topk],
        route_start_index=0,
    )
    scratch = bench.make_prologue_scratch(
        rows=args.rows,
        hidden_size=args.hidden_size,
        inter_size=args.inter_size,
        num_experts=args.num_experts,
        topk=8,
        dtype=dtype,
        device=args.device,
    )

    torch.ops._moe_C.fused_moe_prologue(
        input=inputs["hidden_states"],
        input_scales=None,
        token_selected_experts=inputs["topk_ids"],
        token_final_scales=inputs["topk_weights"],
        workspace=scratch["workspace"],
        hidden_size=args.hidden_size,
        inter_size=args.inter_size,
        block_k=1,
        ep_rank=0,
        ep_size=1,
        num_experts_on_rank=args.num_experts,
    )
    torch.xpu.synchronize()

    gemm1_a, gemm1_a_scales = bench._per_token_quant_int8_maybe_out(
        scratch["remapped_hidden_states"],
        scratch["gemm1_a"],
        scratch["gemm1_a_scales"],
    )
    gemm1_scales = bench._normalize_int8_weight_scales(
        inputs["w13_scales"], 2 * args.inter_size)
    ref = torch.empty_like(scratch["gemm1_output"])
    route = torch.empty_like(scratch["gemm1_output"])
    ref.fill_(0)
    route.fill_(0)

    torch.ops._xpu_C.cutlass_grouped_gemm_w8a8_int8_offsets_interface(
        ptr_A=gemm1_a,
        ptr_A_scales=gemm1_a_scales,
        ptr_B=inputs["w13"],
        ptr_B_scales=gemm1_scales,
        ptr_bias=None,
        ptr_D=ref,
        expert_first_token_offset=scratch["expert_offsets"],
        N=2 * args.inter_size,
        K=args.hidden_size,
        num_experts=args.num_experts,
    )
    torch.ops._xpu_C.cutlass_grouped_gemm_w8a8_int8_topk8_gemm1_interface(
        ptr_A=gemm1_a,
        ptr_A_scales=gemm1_a_scales,
        ptr_B=inputs["w13"],
        ptr_B_scales=gemm1_scales,
        ptr_bias=None,
        ptr_D=route,
        topk_ids=inputs["topk_ids"],
        unpermuted_row_to_permuted_row=scratch["unpermuted"].view(-1),
        N=2 * args.inter_size,
        K=args.hidden_size,
        num_experts=args.num_experts,
    )
    torch.xpu.synchronize()

    unpermuted_cpu = scratch["unpermuted"].view(-1).cpu().tolist()
    topk_cpu = inputs["topk_ids"].view(-1).cpu().tolist()
    offsets_cpu = scratch["expert_offsets"].cpu().tolist()
    ref_cpu = ref.float().cpu()
    route_cpu = route.float().cpu()
    diff = (ref_cpu - route_cpu).abs()

    row_summaries = [
        _row_summary(
            topk_idx=index,
            expert=int(topk_cpu[index]),
            permuted_row=int(unpermuted_cpu[index]),
            ref=ref_cpu,
            route=route_cpu,
        ) for index in range(8)
    ]
    result = {
        "topk": topk_cpu,
        "unpermuted_row_to_permuted_row": unpermuted_cpu,
        "expert_offsets_nonzero": {
            str(expert): [int(offsets_cpu[expert]), int(offsets_cpu[expert + 1])]
            for expert in sorted(set(int(x) for x in topk_cpu))
        },
        "overall_max_abs_diff": float(diff.max().item()),
        "overall_mean_abs_diff": float(diff.mean().item()),
        "rows": row_summaries,
    }
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.output_json:
        Path(args.output_json).write_text(text + "\n")


if __name__ == "__main__":
    main()
