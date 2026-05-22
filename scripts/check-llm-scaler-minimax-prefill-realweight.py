#!/usr/bin/env python3
"""Real-weight math check for MiniMax M2.7 llm-scaler INT4 prefill ops.

This validates the lower-level prefill op chain with externally supplied
MiniMax-correct top-k ids/weights:

  gather -> up -> down -> accumulate

It intentionally avoids ``moe_prefill_full_int4`` because that all-in-one helper
uses a softmax router internally, while MiniMax M2 routing uses sigmoid plus
e_score_correction_bias and renormalization.
"""

from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path

import torch
from safetensors import safe_open


ZERO_POINTED_INT4_ZERO_I32 = -0x77777778
UNSHUFFLE = [0, 2, 4, 6, 1, 3, 5, 7]


def decode_i32_weight(q_i32: torch.Tensor,
                      scales: torch.Tensor,
                      group_size: int = 128) -> torch.Tensor:
    """Decode AutoRound/GPTQ int32 packed weights to fp32 [K, N]."""
    q = q_i32.to(torch.int64) & 0xFFFFFFFF
    packed_k, n_cols = q.shape
    out = torch.empty((packed_k * 8, n_cols), dtype=torch.float32)
    all_rows = torch.arange(packed_k * 8)
    for inner_k, slot in enumerate(UNSHUFFLE):
        nibble = ((q >> (slot * 4)) & 0xF).to(torch.int16) - 8
        rows = all_rows[inner_k::8]
        out[rows, :] = (
            nibble.float() *
            scales[(rows // group_size).long(), :].float()
        )
    return out


def load_expert_to_gpu(handle,
                       expert: int,
                       layer: int,
                       rank: int,
                       inter_local: int,
                       group_size: int,
                       gate_up_weight: torch.Tensor,
                       gate_up_scale: torch.Tensor,
                       down_weight: torch.Tensor,
                       down_scale: torch.Tensor) -> None:
    prefix = f"model.layers.{layer}.block_sparse_moe.experts.{expert}"
    w1q = handle.get_tensor(f"{prefix}.w1.qweight")[
        :, rank * inter_local:(rank + 1) * inter_local].contiguous()
    w1s = handle.get_tensor(f"{prefix}.w1.scales")[
        :, rank * inter_local:(rank + 1) * inter_local].contiguous()
    w3q = handle.get_tensor(f"{prefix}.w3.qweight")[
        :, rank * inter_local:(rank + 1) * inter_local].contiguous()
    w3s = handle.get_tensor(f"{prefix}.w3.scales")[
        :, rank * inter_local:(rank + 1) * inter_local].contiguous()
    w2q = handle.get_tensor(f"{prefix}.w2.qweight")[
        rank * (inter_local // 8):(rank + 1) * (inter_local // 8),
        :,
    ].contiguous()
    w2s = handle.get_tensor(f"{prefix}.w2.scales")[
        rank * (inter_local // group_size):
        (rank + 1) * (inter_local // group_size),
        :,
    ].contiguous()

    gate_up_weight[expert, :, :inter_local].copy_(
        w1q.to(gate_up_weight.device))
    gate_up_weight[expert, :, inter_local:].copy_(
        w3q.to(gate_up_weight.device))
    gate_up_scale[expert, :, :inter_local].copy_(
        w1s.to(torch.float16).to(gate_up_scale.device))
    gate_up_scale[expert, :, inter_local:].copy_(
        w3s.to(torch.float16).to(gate_up_scale.device))
    down_weight[expert].copy_(w2q.to(down_weight.device))
    down_scale[expert].copy_(
        w2s.to(torch.float16).to(down_scale.device))


def load_expert_reference(handle,
                          expert: int,
                          layer: int,
                          rank: int,
                          inter_local: int,
                          group_size: int) -> tuple[torch.Tensor, torch.Tensor,
                                                     torch.Tensor]:
    prefix = f"model.layers.{layer}.block_sparse_moe.experts.{expert}"
    w1q = handle.get_tensor(f"{prefix}.w1.qweight")[
        :, rank * inter_local:(rank + 1) * inter_local].contiguous()
    w1s = handle.get_tensor(f"{prefix}.w1.scales")[
        :, rank * inter_local:(rank + 1) * inter_local].contiguous()
    w3q = handle.get_tensor(f"{prefix}.w3.qweight")[
        :, rank * inter_local:(rank + 1) * inter_local].contiguous()
    w3s = handle.get_tensor(f"{prefix}.w3.scales")[
        :, rank * inter_local:(rank + 1) * inter_local].contiguous()
    w2q = handle.get_tensor(f"{prefix}.w2.qweight")[
        rank * (inter_local // 8):(rank + 1) * (inter_local // 8),
        :,
    ].contiguous()
    w2s = handle.get_tensor(f"{prefix}.w2.scales")[
        rank * (inter_local // group_size):
        (rank + 1) * (inter_local // group_size),
        :,
    ].contiguous()
    return (
        decode_i32_weight(w1q, w1s, group_size),
        decode_i32_weight(w3q, w3s, group_size),
        decode_i32_weight(w2q, w2s, group_size),
    )


def check_case(args: argparse.Namespace, token_experts: list[list[int]]) -> dict:
    importlib.import_module("custom_esimd_kernels_vllm.moe_int4_prefill_ops")
    if not torch.xpu.is_available():
        raise RuntimeError("torch.xpu is not available")

    model_dir = Path(args.model)
    safetensor = model_dir / args.safetensor
    device = torch.device(args.device)
    inter_local = args.intermediate_size // args.tp_size
    n_tokens = len(token_experts)
    unique_experts = sorted({e for row in token_experts for e in row})

    gate_up_weight = torch.full(
        (args.num_experts, args.hidden_size // 8, 2 * inter_local),
        ZERO_POINTED_INT4_ZERO_I32,
        dtype=torch.int32,
        device=device,
    )
    gate_up_scale = torch.zeros(
        (args.num_experts, args.hidden_size // args.group_size,
         2 * inter_local),
        dtype=torch.float16,
        device=device,
    )
    down_weight = torch.full(
        (args.num_experts, inter_local // 8, args.hidden_size),
        ZERO_POINTED_INT4_ZERO_I32,
        dtype=torch.int32,
        device=device,
    )
    down_scale = torch.zeros(
        (args.num_experts, inter_local // args.group_size, args.hidden_size),
        dtype=torch.float16,
        device=device,
    )

    with safe_open(str(safetensor), framework="pt", device="cpu") as handle:
        for expert in unique_experts:
            load_expert_to_gpu(
                handle, expert, args.layer, args.rank, inter_local,
                args.group_size, gate_up_weight, gate_up_scale, down_weight,
                down_scale)

    torch.manual_seed(args.seed + n_tokens)
    x_cpu = (torch.randn((n_tokens, args.hidden_size), dtype=torch.float32) *
             args.input_scale).to(torch.float16)
    ids_cpu = torch.tensor(token_experts, dtype=torch.int32)
    raw_weights = torch.arange(
        args.top_k, 0, -1, dtype=torch.float32).repeat(n_tokens, 1)
    topk_weights_cpu = (
        raw_weights / raw_weights.sum(dim=-1, keepdim=True)
    ).to(torch.float16)

    x = x_cpu.to(device)
    ids = ids_cpu.to(device)
    topk_weights = topk_weights_cpu.to(device)

    gather = torch.ops.moe_int4_prefill_ops.moe_prefill_gather_forward_v2(
        ids, args.num_experts)
    intermediate = torch.ops.moe_int4_prefill_ops.moe_prefill_up_forward_v2(
        x, gate_up_weight, gate_up_scale, gather[0], gather[1], args.top_k)
    expert_output = (
        torch.ops.moe_int4_prefill_ops.moe_prefill_down_forward_v2(
            intermediate, down_weight, down_scale, gather[0], gather[1]))
    output = torch.ops.moe_int4_prefill_ops.moe_prefill_accumulate_forward_v2(
        expert_output, topk_weights)
    torch.xpu.synchronize()
    output_cpu = output.cpu().float()

    reference = torch.zeros((n_tokens, args.hidden_size), dtype=torch.float32)
    x_float = x_cpu.float()
    with safe_open(str(safetensor), framework="pt", device="cpu") as handle:
        for tok, row in enumerate(token_experts):
            for slot, expert in enumerate(row):
                w1, w3, w2 = load_expert_reference(
                    handle, expert, args.layer, args.rank, inter_local,
                    args.group_size)
                gate = x_float[tok:tok + 1] @ w1
                up = x_float[tok:tok + 1] @ w3
                activated = torch.nn.functional.silu(gate) * up
                down = activated @ w2
                reference[tok:tok + 1] += (
                    topk_weights_cpu[tok, slot].float() * down)

    reference16 = reference.to(torch.float16).float()
    error = (output_cpu - reference16).abs()
    return {
        "tokens": n_tokens,
        "unique_experts": len(unique_experts),
        "expert_ids": token_experts,
        "max_abs_vs_ref16": float(error.max()),
        "mean_abs_vs_ref16": float(error.mean()),
        "ref16_abs_max": float(reference16.abs().max()),
        "out_abs_max": float(output_cpu.abs().max()),
        "allclose": bool(torch.allclose(
            output_cpu, reference16, atol=args.atol, rtol=args.rtol)),
        "atol": args.atol,
        "rtol": args.rtol,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=(
        "/mnt/fast-ai/llm-models/minimax-m2.7-int4-autoround"))
    parser.add_argument("--safetensor", default="model-00001-of-00023.safetensors")
    parser.add_argument("--device", default="xpu:0")
    parser.add_argument("--seed", type=int, default=123)
    parser.add_argument("--layer", type=int, default=0)
    parser.add_argument("--rank", type=int, default=0)
    parser.add_argument("--tp-size", type=int, default=4)
    parser.add_argument("--hidden-size", type=int, default=3072)
    parser.add_argument("--intermediate-size", type=int, default=1536)
    parser.add_argument("--num-experts", type=int, default=256)
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--group-size", type=int, default=128)
    parser.add_argument("--input-scale", type=float, default=0.05)
    parser.add_argument("--atol", type=float, default=1e-4)
    parser.add_argument("--rtol", type=float, default=0.05)
    parser.add_argument("--out", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cases = [
        [list(range(args.top_k))],
        [list(range(tok * args.top_k, (tok + 1) * args.top_k))
         for tok in range(4)],
    ]
    result = {
        "model": args.model,
        "safetensor": args.safetensor,
        "layer": args.layer,
        "rank": args.rank,
        "tp_size": args.tp_size,
        "semantic_guardrail": (
            "Uses lower-level prefill ops with externally supplied top-k "
            "ids/weights; does not use moe_prefill_full_int4 softmax router."
        ),
        "cases": [check_case(args, case) for case in cases],
    }
    result["passed"] = all(case["allclose"] for case in result["cases"])
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n")
    print(text)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
