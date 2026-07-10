#!/usr/bin/env python3
"""Microbench Qwen27 ReplaySSM stage-conv + spec-decode native ops.

Diagnostic only. This measures the current two-op ReplaySSM verifier core at
realistic Qwen3.6 27B MTP3/cache8 dimensions:

    stage_conv: mixed_qkv/a/b + conv history -> q/k/v/a/b + conv_pending
    spec_decode: q/k/v/a/b + ring caches -> recurrent GDN output

The result is a pre-gate for a possible fused native op. It is not an endpoint
benchmark and not a LocalMaxxing result.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable


HIDDEN = 5120
NUM_K_HEADS = 16
NUM_V_HEADS = 48
HEAD_K_DIM = 128
HEAD_V_DIM = 128
CONV_WIDTH = 4
CONV_DIM = 2 * (NUM_K_HEADS * HEAD_K_DIM) + (NUM_V_HEADS * HEAD_V_DIM)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-prefix", default="/home/steve/src/vllm-xpu-kernels")
    parser.add_argument("--out", required=True)
    parser.add_argument("--device", default="xpu:0")
    parser.add_argument("--rows", type=int, default=1)
    parser.add_argument("--spec-len", type=int, default=4)
    parser.add_argument("--cache-len", type=int, default=8)
    parser.add_argument("--num-slots", type=int, default=2)
    parser.add_argument("--dtype", choices=("bf16", "fp16", "fp32"), default="bf16")
    parser.add_argument("--state-dtype", choices=("bf16", "fp16", "fp32"), default="bf16")
    parser.add_argument("--warmup", type=int, default=50)
    parser.add_argument("--iterations", type=int, default=500)
    parser.add_argument("--seed", type=int, default=20260707)
    return parser.parse_args()


def sync(torch_mod: Any) -> None:
    torch_mod.xpu.synchronize()


def bench(
    *,
    torch_mod: Any,
    name: str,
    fn: Callable[[], Any],
    warmup: int,
    iterations: int,
) -> dict[str, Any]:
    for _ in range(warmup):
        fn()
    sync(torch_mod)
    t0 = time.perf_counter()
    for _ in range(iterations):
        fn()
    sync(torch_mod)
    mean_us = (time.perf_counter() - t0) * 1_000_000.0 / iterations
    return {"name": name, "mean_us": mean_us, "mean_ms": mean_us / 1000.0}


def dtype_from_name(torch_mod: Any, name: str) -> Any:
    return {
        "bf16": torch_mod.bfloat16,
        "fp16": torch_mod.float16,
        "fp32": torch_mod.float32,
    }[name]


def main() -> None:
    args = parse_args()
    sys.path.insert(0, args.candidate_prefix)

    import torch
    import vllm_xpu_kernels._xpu_C as xpu_c  # noqa: F401

    if not hasattr(torch.ops, "_xpu_C"):
        raise SystemExit("torch.ops._xpu_C is unavailable")
    required = ["gdn_replayssm_stage_conv", "gdn_replayssm_spec_decode"]
    missing = [name for name in required if not hasattr(torch.ops._xpu_C, name)]
    if missing:
        raise SystemExit(f"missing XPU ops: {missing}")

    device = torch.device(args.device)
    torch.xpu.set_device(device)
    dtype = dtype_from_name(torch, args.dtype)
    state_dtype = dtype_from_name(torch, args.state_dtype)
    gen = torch.Generator(device=args.device)
    gen.manual_seed(args.seed)

    rows = args.rows
    spec_len = args.spec_len
    total_tokens = rows * spec_len
    if args.num_slots <= rows:
        raise ValueError("--num-slots must be > --rows so slot 0 can be null")
    slots = torch.arange(1, rows + 1, device=device, dtype=torch.int64)
    query_start_loc = torch.arange(
        0,
        total_tokens + 1,
        spec_len,
        device=device,
        dtype=torch.int32,
    ).contiguous()
    spec_token_indices = torch.arange(
        total_tokens,
        device=device,
        dtype=torch.int32,
    ).contiguous()

    mixed_qkv = torch.randn(
        (total_tokens, CONV_DIM),
        device=device,
        dtype=dtype,
        generator=gen,
    ).contiguous()
    a_src = torch.randn(
        (total_tokens, NUM_V_HEADS),
        device=device,
        dtype=dtype,
        generator=gen,
    ).contiguous()
    b_src = torch.randn_like(a_src)
    conv_state = torch.randn(
        (args.num_slots, CONV_DIM, CONV_WIDTH),
        device=device,
        dtype=dtype,
        generator=gen,
    ).contiguous()
    conv_weights = torch.randn(
        (CONV_DIM, CONV_WIDTH),
        device=device,
        dtype=dtype,
        generator=gen,
    ).contiguous()
    conv_pending = torch.empty(
        (args.num_slots, spec_len, CONV_DIM),
        device=device,
        dtype=dtype,
    ).contiguous()
    q = torch.empty(
        (1, total_tokens, NUM_K_HEADS, HEAD_K_DIM),
        device=device,
        dtype=dtype,
    )
    k = torch.empty_like(q)
    v = torch.empty(
        (1, total_tokens, NUM_V_HEADS, HEAD_V_DIM),
        device=device,
        dtype=dtype,
    )
    a_out = torch.empty((total_tokens, NUM_V_HEADS), device=device, dtype=dtype)
    b_out = torch.empty_like(a_out)

    checkpoint = torch.randn(
        (args.num_slots, NUM_V_HEADS, HEAD_V_DIM, HEAD_K_DIM),
        device=device,
        dtype=state_dtype,
        generator=gen,
    )
    d_cache = torch.randn(
        (args.num_slots, NUM_V_HEADS, args.cache_len, HEAD_V_DIM),
        device=device,
        dtype=state_dtype,
        generator=gen,
    )
    k_cache = torch.randn(
        (args.num_slots, NUM_K_HEADS, args.cache_len, HEAD_K_DIM),
        device=device,
        dtype=state_dtype,
        generator=gen,
    )
    g_cache = torch.randn(
        (args.num_slots, NUM_V_HEADS, args.cache_len),
        device=device,
        dtype=torch.float32,
        generator=gen,
    ) * 0.03
    A_log = torch.randn((NUM_V_HEADS,), device=device, dtype=torch.float32,
                        generator=gen)
    dt_bias = torch.randn((NUM_V_HEADS,), device=device, dtype=dtype,
                          generator=gen)
    out = torch.empty(
        (1, total_tokens, NUM_V_HEADS, HEAD_V_DIM),
        device=device,
        dtype=dtype,
    )
    write_pos = torch.full(
        (args.num_slots,),
        max(0, args.cache_len - spec_len),
        device=device,
        dtype=torch.int32,
    )
    write_pos[0] = 0
    cache_base = torch.arange(args.num_slots, device=device, dtype=torch.int32)
    cache_base %= args.cache_len
    is_flush = torch.zeros((args.num_slots,), device=device, dtype=torch.int8)
    pending = torch.zeros((args.num_slots,), device=device, dtype=torch.int8)
    pending_len = torch.zeros(
        (args.num_slots,), device=device, dtype=torch.int32)
    if args.num_slots > 2:
        is_flush[2] = 1

    def stage_conv() -> None:
        torch.ops._xpu_C.gdn_replayssm_stage_conv(
            q,
            k,
            v,
            a_out,
            b_out,
            mixed_qkv,
            a_src,
            b_src,
            conv_state,
            conv_weights,
            None,
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

    def spec_decode() -> None:
        torch.ops._xpu_C.gdn_replayssm_spec_decode(
            out,
            q,
            k,
            v,
            a_out,
            b_out,
            A_log,
            dt_bias,
            checkpoint,
            d_cache,
            k_cache,
            g_cache,
            query_start_loc,
            slots,
            write_pos,
            cache_base,
            is_flush,
            pending,
            pending_len,
            False,
            args.cache_len,
            spec_len,
            HEAD_K_DIM**-0.5,
            True,
            0,
        )

    def stage_then_decode() -> None:
        stage_conv()
        spec_decode()

    stage_conv()
    spec_decode()
    sync(torch)

    records = [
        bench(
            torch_mod=torch,
            name="stage_conv",
            fn=stage_conv,
            warmup=args.warmup,
            iterations=args.iterations,
        ),
        bench(
            torch_mod=torch,
            name="spec_decode",
            fn=spec_decode,
            warmup=args.warmup,
            iterations=args.iterations,
        ),
        bench(
            torch_mod=torch,
            name="stage_then_decode",
            fn=stage_then_decode,
            warmup=args.warmup,
            iterations=args.iterations,
        ),
    ]
    by_name = {row["name"]: row for row in records}
    separate_sum = (
        by_name["stage_conv"]["mean_ms"] + by_name["spec_decode"]["mean_ms"]
    )
    by_name["stage_then_decode"]["separate_sum_ms"] = separate_sum
    by_name["stage_then_decode"]["python_pair_overhead_ms"] = (
        by_name["stage_then_decode"]["mean_ms"] - separate_sum
    )

    result = {
        "classification": "diagnostic_microbench_not_endpoint_not_localmaxxing",
        "hypothesis": "ReplaySSM stage_conv + spec_decode fusion pre-gate",
        "candidate_module": getattr(xpu_c, "__file__", None),
        "env": {
            "ZE_AFFINITY_MASK": os.environ.get("ZE_AFFINITY_MASK"),
            "ONEAPI_DEVICE_SELECTOR": os.environ.get("ONEAPI_DEVICE_SELECTOR"),
            "LD_LIBRARY_PATH": os.environ.get("LD_LIBRARY_PATH"),
        },
        "shape": {
            "rows": rows,
            "spec_len": spec_len,
            "total_tokens": total_tokens,
            "cache_len": args.cache_len,
            "num_slots": args.num_slots,
            "num_k_heads": NUM_K_HEADS,
            "num_v_heads": NUM_V_HEADS,
            "head_k_dim": HEAD_K_DIM,
            "head_v_dim": HEAD_V_DIM,
            "conv_dim": CONV_DIM,
            "conv_width": CONV_WIDTH,
            "dtype": args.dtype,
            "state_dtype": args.state_dtype,
        },
        "records": records,
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
