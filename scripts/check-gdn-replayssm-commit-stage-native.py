#!/usr/bin/env python3
"""Bitwise parity guard for fused ReplaySSM commit + stage-conv."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path


def _load_extension(path: str) -> None:
    ext_path = str(Path(path).resolve())
    spec = importlib.util.spec_from_file_location(
        "vllm_xpu_kernels._xpu_C", ext_path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"Could not load extension spec: {ext_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["vllm_xpu_kernels._xpu_C"] = module
    spec.loader.exec_module(module)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="xpu:0")
    parser.add_argument("--rows", type=int, default=3)
    parser.add_argument("--spec-len", type=int, default=4)
    parser.add_argument("--num-k-heads", type=int, default=16)
    parser.add_argument("--num-v-heads", type=int, default=48)
    parser.add_argument("--head-k-dim", type=int, default=128)
    parser.add_argument("--head-v-dim", type=int, default=128)
    parser.add_argument("--conv-width", type=int, default=4)
    parser.add_argument("--cache-len", type=int, default=8)
    parser.add_argument("--seed", type=int, default=20260710)
    parser.add_argument("--xpu-c-extension", required=True)
    parser.add_argument("--out-json")
    args = parser.parse_args()

    if args.rows != 3 or args.spec_len != 4:
        raise SystemExit("This guard currently defines the exact rows=3/spec_len=4 case")

    os.environ.setdefault("VLLM_TARGET_DEVICE", "xpu")
    import torch

    _load_extension(args.xpu_c_extension)
    if not torch.xpu.is_available():
        raise SystemExit("torch.xpu is unavailable")
    device = torch.device(args.device)
    torch.xpu.set_device(device)
    torch.manual_seed(args.seed)
    torch.xpu.manual_seed_all(args.seed)

    dtype = torch.bfloat16
    rows = args.rows
    max_spec_len = args.spec_len
    query_start_loc = torch.tensor(
        [0, 4, 6, 7], device=device, dtype=torch.int32)
    total_tokens = int(query_start_loc[-1].item())
    num_actual_tokens = total_tokens + 3
    q_total = args.num_k_heads * args.head_k_dim
    v_total = args.num_v_heads * args.head_v_dim
    conv_dim = 2 * q_total + v_total
    num_slots = rows + 2

    mixed_qkv = torch.randn(
        (num_actual_tokens, conv_dim), device=device, dtype=dtype)
    a_src = torch.randn(
        (num_actual_tokens, args.num_v_heads), device=device, dtype=dtype)
    b_src = torch.randn_like(a_src)
    conv_weights = torch.randn(
        (conv_dim, args.conv_width), device=device, dtype=dtype)
    conv_bias = torch.randn((conv_dim,), device=device, dtype=dtype)
    spec_token_indices = torch.tensor(
        [2, 0, 6, 4, 1, 8, 5], device=device, dtype=torch.int32)
    state_indices = torch.tensor([1, 2, 3], device=device, dtype=torch.int64)
    num_accepted_tokens = torch.tensor(
        [2, 4, 1], device=device, dtype=torch.int32)

    base = {
        "conv_state": torch.randn(
            (num_slots, conv_dim, args.conv_width),
            device=device,
            dtype=dtype,
        ),
        "conv_pending": torch.randn(
            (num_slots, max_spec_len, conv_dim),
            device=device,
            dtype=dtype,
        ),
        "write_pos": torch.tensor(
            [0, 1, 5, 2, 0], device=device, dtype=torch.int32),
        "cache_base": torch.tensor(
            [0, 2, 3, 1, 0], device=device, dtype=torch.int32),
        "is_flush": torch.tensor(
            [0, 0, 1, 0, 0], device=device, dtype=torch.int8),
        "pending": torch.tensor(
            [0, 1, 1, 0, 0], device=device, dtype=torch.int8),
        "pending_len": torch.tensor(
            [0, 4, 3, 4, 0], device=device, dtype=torch.int32),
    }

    def make_case() -> dict[str, torch.Tensor]:
        case = {name: tensor.clone() for name, tensor in base.items()}
        case["q"] = torch.empty(
            (1, total_tokens, args.num_k_heads, args.head_k_dim),
            device=device,
            dtype=dtype,
        )
        case["k"] = torch.empty_like(case["q"])
        case["v"] = torch.empty(
            (1, total_tokens, args.num_v_heads, args.head_v_dim),
            device=device,
            dtype=dtype,
        )
        case["a"] = torch.empty(
            (total_tokens, args.num_v_heads), device=device, dtype=dtype)
        case["b"] = torch.empty_like(case["a"])
        return case

    sequential = make_case()
    fused = make_case()

    torch.ops._xpu_C.gdn_replayssm_commit_pending(
        sequential["conv_state"],
        sequential["write_pos"],
        sequential["cache_base"],
        sequential["is_flush"],
        sequential["pending"],
        sequential["pending_len"],
        sequential["conv_pending"],
        num_accepted_tokens,
        state_indices,
        args.cache_len,
        max_spec_len,
        args.conv_width - 1,
        0,
    )
    torch.ops._xpu_C.gdn_replayssm_stage_conv(
        sequential["q"],
        sequential["k"],
        sequential["v"],
        sequential["a"],
        sequential["b"],
        mixed_qkv,
        a_src,
        b_src,
        sequential["conv_state"],
        conv_weights,
        conv_bias,
        sequential["conv_pending"],
        spec_token_indices,
        query_start_loc,
        state_indices,
        rows,
        num_actual_tokens,
        max_spec_len,
        "silu",
        0,
    )

    torch.ops._xpu_C.gdn_replayssm_commit_stage_conv(
        fused["q"],
        fused["k"],
        fused["v"],
        fused["a"],
        fused["b"],
        mixed_qkv,
        a_src,
        b_src,
        fused["conv_state"],
        conv_weights,
        conv_bias,
        fused["conv_pending"],
        spec_token_indices,
        query_start_loc,
        state_indices,
        fused["write_pos"],
        fused["cache_base"],
        fused["is_flush"],
        fused["pending"],
        fused["pending_len"],
        num_accepted_tokens,
        rows,
        num_actual_tokens,
        max_spec_len,
        args.cache_len,
        "silu",
        0,
    )
    torch.xpu.synchronize(device)

    comparisons = {}
    passed = True
    for name in (
        "q",
        "k",
        "v",
        "a",
        "b",
        "conv_state",
        "conv_pending",
        "write_pos",
        "cache_base",
        "is_flush",
        "pending",
        "pending_len",
    ):
        lhs = fused[name]
        rhs = sequential[name]
        neq = int(torch.count_nonzero(lhs != rhs).item())
        max_abs = float(
            (lhs.to(torch.float32) - rhs.to(torch.float32)).abs().max().item())
        ok = neq == 0
        comparisons[name] = {
            "pass": ok,
            "nonzero_diff_count": neq,
            "max_abs": max_abs,
        }
        passed = passed and ok

    result = {
        "pass": passed,
        "classification": "native_commit_stage_bitwise_parity_guard",
        "shape": {
            "rows": rows,
            "sequence_lengths": [4, 2, 1],
            "max_spec_len": max_spec_len,
            "num_k_heads": args.num_k_heads,
            "num_v_heads": args.num_v_heads,
            "head_k_dim": args.head_k_dim,
            "head_v_dim": args.head_v_dim,
            "conv_width": args.conv_width,
            "conv_dim": conv_dim,
            "dtype": "bfloat16",
        },
        "accepted_counts": [2, 4, 1],
        "pending_lengths": [4, 3, 4],
        "note": "row 2 clamps accepted 4 to pending_len 3; row 3 is inactive",
        "xpu_c_extension": str(Path(args.xpu_c_extension).resolve()),
        "comparisons": comparisons,
    }
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.out_json:
        Path(args.out_json).write_text(text + "\n")
    print(text)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
