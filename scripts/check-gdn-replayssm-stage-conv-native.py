#!/usr/bin/env python3
"""Bitwise parity guard for the native ReplaySSM stage-conv kernel."""

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
    parser.add_argument("--rows", type=int, default=1)
    parser.add_argument("--spec-len", type=int, default=4)
    parser.add_argument("--num-k-heads", type=int, default=16)
    parser.add_argument("--num-v-heads", type=int, default=48)
    parser.add_argument("--head-k-dim", type=int, default=128)
    parser.add_argument("--head-v-dim", type=int, default=128)
    parser.add_argument("--conv-width", type=int, default=4)
    parser.add_argument("--num-slots", type=int, default=8)
    parser.add_argument("--seed", type=int, default=20260710)
    parser.add_argument("--xpu-c-extension", required=True)
    parser.add_argument("--out-json")
    args = parser.parse_args()

    os.environ.setdefault("VLLM_TARGET_DEVICE", "xpu")
    sys.path.insert(0, "/home/steve/src/vllm")

    import torch

    _load_extension(args.xpu_c_extension)
    from vllm.model_executor.layers.mamba.ops.causal_conv1d import (
        causal_conv1d_update,
    )

    if not torch.xpu.is_available():
        raise SystemExit("torch.xpu is unavailable")
    device = torch.device(args.device)
    torch.xpu.set_device(device)
    torch.manual_seed(args.seed)
    torch.xpu.manual_seed_all(args.seed)

    dtype = torch.bfloat16
    rows = args.rows
    spec_len = args.spec_len
    total_tokens = rows * spec_len
    q_total = args.num_k_heads * args.head_k_dim
    v_total = args.num_v_heads * args.head_v_dim
    conv_dim = 2 * q_total + v_total
    num_slots = max(args.num_slots, rows + 1)

    mixed_qkv = torch.randn(
        (total_tokens, conv_dim), device=device, dtype=dtype)
    a_src = torch.randn(
        (total_tokens, args.num_v_heads), device=device, dtype=dtype)
    b_src = torch.randn_like(a_src)
    conv_state = torch.randn(
        (num_slots, conv_dim, args.conv_width),
        device=device,
        dtype=dtype,
    )
    conv_state_before = conv_state.clone()
    conv_weights = torch.randn(
        (conv_dim, args.conv_width), device=device, dtype=dtype)
    conv_bias = torch.randn((conv_dim,), device=device, dtype=dtype)
    conv_pending = torch.zeros(
        (num_slots, spec_len, conv_dim), device=device, dtype=dtype)
    spec_token_indices = torch.arange(
        total_tokens, device=device, dtype=torch.int32)
    query_start_loc = torch.arange(
        0,
        total_tokens + 1,
        spec_len,
        device=device,
        dtype=torch.int32,
    )
    slots = torch.arange(1, rows + 1, device=device, dtype=torch.int64)

    q_out = torch.empty(
        (1, total_tokens, args.num_k_heads, args.head_k_dim),
        device=device,
        dtype=dtype,
    )
    k_out = torch.empty_like(q_out)
    v_out = torch.empty(
        (1, total_tokens, args.num_v_heads, args.head_v_dim),
        device=device,
        dtype=dtype,
    )
    a_out = torch.empty_like(a_src)
    b_out = torch.empty_like(b_src)

    torch.ops._xpu_C.gdn_replayssm_stage_conv(
        q_out,
        k_out,
        v_out,
        a_out,
        b_out,
        mixed_qkv,
        a_src,
        b_src,
        conv_state,
        conv_weights,
        conv_bias,
        conv_pending,
        spec_token_indices,
        query_start_loc,
        slots,
        rows,
        total_tokens,
        spec_len,
        "silu",
        0,
    )

    temp_conv_state = torch.cat(
        (torch.zeros_like(conv_state[:1]), conv_state.index_select(0, slots)),
        dim=0,
    )
    temp_indices = torch.arange(
        1, rows + 1, device=device, dtype=torch.int32)
    conv_ref = causal_conv1d_update(
        mixed_qkv.clone(),
        temp_conv_state,
        conv_weights,
        conv_bias,
        "silu",
        conv_state_indices=temp_indices,
        num_accepted_tokens=None,
        query_start_loc=query_start_loc,
        max_query_len=spec_len,
        validate_data=False,
    )
    q_ref = conv_ref[:, :q_total].reshape(
        1, total_tokens, args.num_k_heads, args.head_k_dim)
    k_ref = conv_ref[:, q_total:2 * q_total].reshape_as(q_ref)
    v_ref = conv_ref[:, 2 * q_total:].reshape(
        1, total_tokens, args.num_v_heads, args.head_v_dim)
    pending_ref = torch.zeros_like(conv_pending)
    pending_ref.index_copy_(
        0, slots, mixed_qkv.reshape(rows, spec_len, conv_dim))
    torch.xpu.synchronize(device)

    actual = {
        "q": q_out,
        "k": k_out,
        "v": v_out,
        "a": a_out,
        "b": b_out,
        "conv_pending": conv_pending,
        "conv_state_unchanged": conv_state,
    }
    expected = {
        "q": q_ref,
        "k": k_ref,
        "v": v_ref,
        "a": a_src,
        "b": b_src,
        "conv_pending": pending_ref,
        "conv_state_unchanged": conv_state_before,
    }
    comparisons = {}
    passed = True
    for name in actual:
        lhs = actual[name]
        rhs = expected[name]
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
        "classification": "native_stage_conv_bitwise_parity_guard",
        "shape": {
            "rows": rows,
            "spec_len": spec_len,
            "num_k_heads": args.num_k_heads,
            "num_v_heads": args.num_v_heads,
            "head_k_dim": args.head_k_dim,
            "head_v_dim": args.head_v_dim,
            "conv_width": args.conv_width,
            "conv_dim": conv_dim,
            "dtype": "bfloat16",
        },
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
