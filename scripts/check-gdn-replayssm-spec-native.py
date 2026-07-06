#!/usr/bin/env python3
"""Direct parity check for native ReplaySSM spec decode.

Compares ``gdn_replayssm_spec_decode`` native dispatch against the PyTorch
fallback for synthetic cache/spec shapes. This is intended to catch shape
specialization mistakes before spending endpoint runs.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any


def _repo_root() -> str:
    return os.environ.get("VLLM_REPO_ROOT", "/home/steve/src/vllm")


def _truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="xpu:0")
    parser.add_argument("--rows", type=int, default=2)
    parser.add_argument("--spec-len", type=int, default=4)
    parser.add_argument("--cache-len", type=int, default=8)
    parser.add_argument("--num-k-heads", type=int, default=2)
    parser.add_argument("--kv-ratio", type=int, default=1)
    parser.add_argument("--head-k-dim", type=int, default=64)
    parser.add_argument("--head-v-dim", type=int, default=64)
    parser.add_argument("--dtype", choices=("bf16", "fp16", "fp32"),
                        default="bf16")
    parser.add_argument("--state-dtype", choices=("bf16", "fp16", "fp32"),
                        default="bf16")
    parser.add_argument("--seed", type=int, default=20260706)
    parser.add_argument(
        "--xpu-c-extension",
        default=os.environ.get("VLLM_XPU_C_EXTENSION"),
        help=("Optional candidate _xpu_C.abi3.so to preload before importing "
              "vLLM. Useful for testing a temporary kernel build without "
              "replacing the live source-tree extension."),
    )
    parser.add_argument("--out-json")
    args = parser.parse_args()

    os.environ.setdefault("VLLM_TARGET_DEVICE", "xpu")
    sys.path.insert(0, _repo_root())

    import torch
    if args.xpu_c_extension:
        import importlib.util

        ext_path = os.path.abspath(args.xpu_c_extension)
        if not os.path.exists(ext_path):
            raise SystemExit(f"_xpu_C extension not found: {ext_path}")
        spec = importlib.util.spec_from_file_location(
            "vllm_xpu_kernels._xpu_C", ext_path)
        if spec is None or spec.loader is None:
            raise SystemExit(f"Could not load extension spec: {ext_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules["vllm_xpu_kernels._xpu_C"] = module
        spec.loader.exec_module(module)

    if not hasattr(torch, "xpu") or not torch.xpu.is_available():
        raise SystemExit("torch.xpu is not available")

    from vllm.model_executor.layers.mamba.gdn_linear_attn import (
        gdn_replayssm_spec_decode,
    )

    if not hasattr(torch.ops, "_xpu_C") or not hasattr(
            torch.ops._xpu_C, "gdn_replayssm_spec_decode"):
        raise SystemExit("torch.ops._xpu_C.gdn_replayssm_spec_decode missing")

    dtype_map = {
        "bf16": torch.bfloat16,
        "fp16": torch.float16,
        "fp32": torch.float32,
    }
    dtype = dtype_map[args.dtype]
    state_dtype = dtype_map[args.state_dtype]
    device = torch.device(args.device)
    torch.xpu.set_device(device)
    torch.manual_seed(args.seed)
    torch.xpu.manual_seed_all(args.seed)

    rows = args.rows
    spec_len = args.spec_len
    cache_len = args.cache_len
    num_k_heads = args.num_k_heads
    num_v_heads = num_k_heads * args.kv_ratio
    head_k_dim = args.head_k_dim
    head_v_dim = args.head_v_dim
    total_tokens = rows * spec_len
    num_slots = rows + 1
    null_block_id = 0
    slots = torch.arange(1, rows + 1, device=device, dtype=torch.int64)
    query_start_loc = torch.arange(
        0,
        total_tokens + 1,
        spec_len,
        device=device,
        dtype=torch.int32,
    )

    q = torch.randn((1, total_tokens, num_k_heads, head_k_dim),
                    device=device,
                    dtype=dtype)
    k = torch.randn_like(q)
    v = torch.randn((1, total_tokens, num_v_heads, head_v_dim),
                    device=device,
                    dtype=dtype)
    a = torch.randn((total_tokens, num_v_heads), device=device, dtype=dtype)
    b = torch.randn_like(a)
    A_log = torch.randn((num_v_heads,), device=device, dtype=torch.float32)
    dt_bias = torch.randn((num_v_heads,), device=device, dtype=dtype)

    checkpoint = torch.randn((num_slots, num_v_heads, head_v_dim, head_k_dim),
                             device=device,
                             dtype=state_dtype)
    d_cache = torch.randn((num_slots, num_v_heads, cache_len, head_v_dim),
                          device=device,
                          dtype=state_dtype)
    k_cache = torch.randn((num_slots, num_k_heads, cache_len, head_k_dim),
                          device=device,
                          dtype=state_dtype)
    g_cache = torch.randn((num_slots, num_v_heads, cache_len),
                          device=device,
                          dtype=torch.float32) * 0.03
    write_pos = torch.full((num_slots,),
                           max(0, cache_len - spec_len),
                           device=device,
                           dtype=torch.int32)
    write_pos[0] = 0
    cache_base = torch.arange(num_slots, device=device,
                              dtype=torch.int32) % cache_len
    is_flush = torch.zeros((num_slots,), device=device, dtype=torch.int8)
    if rows > 1:
        is_flush[2] = 1

    def run(force_fallback: bool) -> dict[str, Any]:
        old = os.environ.get("VLLM_XPU_GDN_REPLAYSSM_TORCH_FALLBACK")
        os.environ["VLLM_XPU_GDN_REPLAYSSM_TORCH_FALLBACK"] = (
            "1" if force_fallback else "0")
        out = torch.empty((1, total_tokens, num_v_heads, head_v_dim),
                          device=device,
                          dtype=dtype)
        local = {
            "out": out,
            "checkpoint": checkpoint.clone(),
            "d_cache": d_cache.clone(),
            "k_cache": k_cache.clone(),
            "g_cache": g_cache.clone(),
        }
        gdn_replayssm_spec_decode(
            A_log=A_log,
            a=a,
            b=b,
            dt_bias=dt_bias,
            q=q,
            k=k,
            v=v,
            checkpoint_state=local["checkpoint"],
            d_cache=local["d_cache"],
            k_cache=local["k_cache"],
            g_cache=local["g_cache"],
            out=local["out"],
            query_start_loc=query_start_loc,
            ssm_state_indices=slots,
            write_pos=write_pos,
            cache_base=cache_base,
            is_flush=is_flush,
            max_cache_len=cache_len,
            max_spec_len=spec_len,
            null_block_id=null_block_id,
        )
        torch.xpu.synchronize(device)
        if old is None:
            os.environ.pop("VLLM_XPU_GDN_REPLAYSSM_TORCH_FALLBACK", None)
        else:
            os.environ["VLLM_XPU_GDN_REPLAYSSM_TORCH_FALLBACK"] = old
        return local

    fallback = run(force_fallback=True)
    native = run(force_fallback=False)

    comparisons: dict[str, dict[str, Any]] = {}
    pass_all = True
    for name in ("out", "checkpoint", "d_cache", "k_cache", "g_cache"):
        diff = (native[name].to(torch.float32) -
                fallback[name].to(torch.float32)).abs()
        max_abs = float(diff.max().item())
        atol = 0.03 if name != "g_cache" else 1e-5
        ok = bool(max_abs <= atol)
        comparisons[name] = {
            "max_abs": max_abs,
            "atol": atol,
            "pass": ok,
        }
        pass_all = pass_all and ok

    result = {
        "pass": pass_all,
        "shape": {
            "rows": rows,
            "spec_len": spec_len,
            "cache_len": cache_len,
            "num_k_heads": num_k_heads,
            "num_v_heads": num_v_heads,
            "head_k_dim": head_k_dim,
            "head_v_dim": head_v_dim,
            "dtype": args.dtype,
            "state_dtype": args.state_dtype,
        },
        "xpu_c_extension": args.xpu_c_extension,
        "native_available": not _truthy(
            os.environ.get("VLLM_XPU_GDN_REPLAYSSM_TORCH_FALLBACK")),
        "comparisons": comparisons,
    }
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.out_json:
        with open(args.out_json, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    print(text)
    return 0 if pass_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
