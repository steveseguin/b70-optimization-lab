#!/usr/bin/env python3
"""Direct parity check for native ReplaySSM slot copy/reset helpers."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


DEFAULT_KERNEL_REPO = Path("/home/steve/src/vllm-xpu-kernels")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default="xpu:0")
    parser.add_argument("--dtype", choices=("bf16", "fp16", "fp32"),
                        default="bf16")
    parser.add_argument("--seed", type=int, default=20260706)
    parser.add_argument("--slots", type=int, default=6)
    parser.add_argument("--num-k-heads", type=int, default=2)
    parser.add_argument("--num-v-heads", type=int, default=4)
    parser.add_argument("--head-k-dim", type=int, default=8)
    parser.add_argument("--head-v-dim", type=int, default=8)
    parser.add_argument("--cache-len", type=int, default=8)
    parser.add_argument("--max-spec-len", type=int, default=4)
    parser.add_argument("--conv-dim", type=int, default=40)
    parser.add_argument("--kernel-repo", type=Path, default=DEFAULT_KERNEL_REPO)
    parser.add_argument("--json-out", type=Path)
    return parser.parse_args()


def add_kernel_repo_to_path(kernel_repo: Path) -> None:
    repo = str(kernel_repo)
    if repo not in sys.path:
        sys.path.insert(0, repo)


def dtype_from_name(torch: Any, name: str) -> Any:
    if name == "bf16":
        return torch.bfloat16
    if name == "fp16":
        return torch.float16
    return torch.float32


def tensor_equal(torch: Any, left: Any, right: Any) -> bool:
    return bool(torch.equal(left.cpu(), right.cpu()))


def main() -> int:
    args = parse_args()
    os.environ.setdefault("VLLM_TARGET_DEVICE", "xpu")
    add_kernel_repo_to_path(args.kernel_repo)

    import torch
    import vllm_xpu_kernels._xpu_C  # noqa: F401

    required = ("gdn_replayssm_copy_slots", "gdn_replayssm_reset_slots")
    missing = [name for name in required if not hasattr(torch.ops._xpu_C, name)]
    if missing:
        raise SystemExit("Missing native ops: " + ", ".join(missing))
    if not hasattr(torch, "xpu") or not torch.xpu.is_available():
        raise SystemExit("torch.xpu is not available")

    device = torch.device(args.device)
    torch.xpu.set_device(device)
    torch.manual_seed(args.seed)
    torch.xpu.manual_seed_all(args.seed)
    dtype = dtype_from_name(torch, args.dtype)

    slots = args.slots
    d_cache = torch.randn(
        (slots, args.num_v_heads, args.cache_len, args.head_v_dim),
        device=device,
        dtype=dtype,
    ).contiguous()
    k_cache = torch.randn(
        (slots, args.num_k_heads, args.cache_len, args.head_k_dim),
        device=device,
        dtype=dtype,
    ).contiguous()
    g_cache = torch.randn(
        (slots, args.num_v_heads, args.cache_len),
        device=device,
        dtype=torch.float32,
    ).contiguous()
    conv_pending = torch.randn(
        (slots, args.max_spec_len, args.conv_dim),
        device=device,
        dtype=dtype,
    ).contiguous()
    write_pos = torch.randint(
        0, args.cache_len, (slots,), device=device, dtype=torch.int32)
    cache_base = torch.randint(
        0, args.cache_len, (slots,), device=device, dtype=torch.int32)
    is_flush = torch.randint(
        0, 2, (slots,), device=device, dtype=torch.int8)
    pending = torch.randint(
        0, 2, (slots,), device=device, dtype=torch.int8)
    pending_len = torch.randint(
        0, args.max_spec_len + 1, (slots,), device=device, dtype=torch.int32)

    ref = {
        "d_cache": d_cache.clone(),
        "k_cache": k_cache.clone(),
        "g_cache": g_cache.clone(),
        "conv_pending": conv_pending.clone(),
        "write_pos": write_pos.clone(),
        "cache_base": cache_base.clone(),
        "is_flush": is_flush.clone(),
        "pending": pending.clone(),
        "pending_len": pending_len.clone(),
    }

    src = torch.tensor([1, 2], device=device, dtype=torch.long)
    dst = torch.tensor([4, 5], device=device, dtype=torch.long)
    for name in ("d_cache", "k_cache", "g_cache", "conv_pending",
                 "write_pos", "cache_base", "is_flush", "pending",
                 "pending_len"):
        ref[name].index_copy_(0, dst, ref[name].index_select(0, src))

    torch.ops._xpu_C.gdn_replayssm_copy_slots(
        d_cache,
        k_cache,
        g_cache,
        write_pos,
        cache_base,
        is_flush,
        pending,
        pending_len,
        conv_pending,
        src,
        dst,
        0,
    )
    torch.xpu.synchronize(device)

    copy_checks = {
        name: tensor_equal(torch, tensor, ref[name])
        for name, tensor in (
            ("d_cache", d_cache),
            ("k_cache", k_cache),
            ("g_cache", g_cache),
            ("conv_pending", conv_pending),
            ("write_pos", write_pos),
            ("cache_base", cache_base),
            ("is_flush", is_flush),
            ("pending", pending),
            ("pending_len", pending_len),
        )
    }

    reset_slots = torch.tensor([4, 5, 0, -1, 999], device=device,
                               dtype=torch.long)
    init_flush = 1
    for slot in (4, 5):
        ref["write_pos"][slot] = 0
        ref["cache_base"][slot] = 0
        ref["is_flush"][slot] = init_flush
        ref["pending"][slot] = 0
        ref["pending_len"][slot] = 0

    torch.ops._xpu_C.gdn_replayssm_reset_slots(
        write_pos,
        cache_base,
        is_flush,
        pending,
        pending_len,
        reset_slots,
        init_flush,
        0,
    )
    torch.xpu.synchronize(device)

    reset_checks = {
        name: tensor_equal(torch, tensor, ref[name])
        for name, tensor in (
            ("write_pos", write_pos),
            ("cache_base", cache_base),
            ("is_flush", is_flush),
            ("pending", pending),
            ("pending_len", pending_len),
        )
    }

    result = {
        "pass": all(copy_checks.values()) and all(reset_checks.values()),
        "device": args.device,
        "dtype": args.dtype,
        "seed": args.seed,
        "copy_checks": copy_checks,
        "reset_checks": reset_checks,
    }
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text + "\n", encoding="utf-8")
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
