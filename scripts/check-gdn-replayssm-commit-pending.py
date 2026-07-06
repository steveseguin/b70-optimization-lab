#!/usr/bin/env python3
"""Native ReplaySSM pending-commit parity check.

This validates the native ``torch.ops._xpu_C.gdn_replayssm_commit_pending``
primitive without launching vLLM. The op is the graph-safe piece that commits
accepted speculative GDN convolution rows and ReplaySSM ring cursors after the
target verifier decides how many draft rows survived.

The check intentionally includes inactive/null slots, accepted counts beyond
``pending_len``, flush and non-flush cursors, and conv-state tails beyond the
active causal window. It should remain cheap enough to run before any endpoint
experiment that changes ReplaySSM/GDN state handling.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any


DEFAULT_KERNEL_REPO = Path("/home/steve/src/vllm-xpu-kernels")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default="xpu:0")
    parser.add_argument("--dtype", choices=("bf16", "fp16", "fp32"),
                        default="bf16")
    parser.add_argument("--seed", type=int, default=20260706)
    parser.add_argument("--rows", type=int, default=9)
    parser.add_argument("--num-slots", type=int, default=13)
    parser.add_argument("--conv-dim", type=int, default=257)
    parser.add_argument("--conv-base-len", type=int, default=3)
    parser.add_argument("--conv-state-len", type=int, default=4)
    parser.add_argument("--max-spec-len", type=int, default=5)
    parser.add_argument("--max-cache-len", type=int, default=16)
    parser.add_argument("--benchmark-iters", type=int, default=0,
                        help="Optional synchronized timing loop.")
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


def _masked_index_fill(tensor: Any, indices: Any, values: Any) -> None:
    if indices.numel() == 0:
        return
    tensor.index_copy_(0, indices, values.to(tensor.dtype))


def reference_commit_pending(
    torch: Any,
    *,
    conv_state: Any,
    write_pos: Any,
    cache_base: Any,
    is_flush: Any,
    pending: Any,
    pending_len: Any,
    conv_pending: Any,
    num_accepted_tokens: Any,
    state_indices: Any,
    max_cache_len: int,
    max_spec_len: int,
    conv_base_len: int,
    null_block_id: int = 0,
) -> None:
    rows = min(int(num_accepted_tokens.numel()), int(state_indices.numel()))
    if rows <= 0:
        return

    slots_raw = state_indices[:rows].to(torch.long)
    valid = (
        (slots_raw > null_block_id)
        & (slots_raw < int(conv_state.size(0)))
    )
    if not bool(torch.any(valid).item()):
        return

    slots = slots_raw[valid]
    active = pending.index_select(0, slots) != 0
    if not bool(torch.any(active).item()):
        return
    slots = slots[active]
    accepted = num_accepted_tokens[:rows].to(torch.long)[valid][active]
    prev_len = pending_len.index_select(0, slots).to(torch.long)
    accepted = torch.clamp(accepted, min=0)
    accepted = torch.minimum(accepted, prev_len)

    if conv_base_len > 0:
        before = conv_state.index_select(0, slots).clone()
        old_conv = before[:, :, :conv_base_len]
        raw = conv_pending.index_select(0, slots)
        history = torch.cat((old_conv.transpose(1, 2).contiguous(), raw), dim=1)
        offsets = torch.arange(conv_base_len, device=slots.device,
                               dtype=torch.long)
        window = accepted.unsqueeze(1) + offsets.unsqueeze(0)
        new_conv = history.gather(
            1, window.unsqueeze(-1).expand(-1, -1, history.size(-1)))
        updated = before.clone()
        updated[:, :, :conv_base_len] = new_conv.transpose(1, 2).to(updated.dtype)
        _masked_index_fill(conv_state, slots, updated)

    old_wp = write_pos.index_select(0, slots).to(torch.long)
    old_base = cache_base.index_select(0, slots).to(torch.long)
    old_flush = is_flush.index_select(0, slots) != 0
    flush_now = (accepted > 0) & old_flush
    new_base = torch.where(flush_now, (old_base + old_wp) % max_cache_len,
                           old_base)
    new_wp = torch.where(old_flush, accepted, old_wp + accepted)
    next_flush = (new_wp + 2 * max_spec_len) > max_cache_len

    write_pos.index_copy_(0, slots, new_wp.to(write_pos.dtype))
    cache_base.index_copy_(0, slots, new_base.to(cache_base.dtype))
    is_flush.index_copy_(0, slots, next_flush.to(is_flush.dtype))
    pending.index_fill_(0, slots, 0)


def build_case(torch: Any, args: argparse.Namespace) -> dict[str, Any]:
    torch.manual_seed(args.seed)
    dtype = dtype_from_name(torch, args.dtype)
    device = torch.device(args.device)
    num_slots = args.num_slots
    rows = args.rows

    conv_state = (
        torch.randn(
            (num_slots, args.conv_dim, args.conv_state_len),
            device=device,
            dtype=dtype,
        ) * 0.2
    ).contiguous()
    conv_pending = (
        torch.randn(
            (num_slots, args.max_spec_len, args.conv_dim),
            device=device,
            dtype=dtype,
        ) * 0.2
    ).contiguous()
    write_pos = torch.randint(
        0, args.max_cache_len // 2 + 1, (num_slots,),
        device=device, dtype=torch.int32)
    cache_base = torch.randint(
        0, args.max_cache_len, (num_slots,), device=device, dtype=torch.int32)
    is_flush = torch.randint(
        0, 2, (num_slots,), device=device, dtype=torch.int8)
    pending = torch.randint(
        0, 2, (num_slots,), device=device, dtype=torch.int8)
    pending_len = torch.randint(
        0, args.max_spec_len + 1, (num_slots,),
        device=device, dtype=torch.int32)

    # Deliberately include null, negative, valid, and too-large slot indices.
    base_slots = torch.arange(rows, device=device, dtype=torch.int64)
    state_indices = (base_slots % (num_slots + 3)) - 1
    if rows >= 4:
        state_indices[0] = 0
        state_indices[1] = 1
        state_indices[2] = num_slots - 1
        state_indices[3] = num_slots + 2
    num_accepted_tokens = (
        torch.arange(rows, device=device, dtype=torch.int32)
        % (args.max_spec_len + 3)
    ) - 1

    # Slot zero is the null block. Poison it so accidental writes are visible.
    conv_state[0].fill_(123)
    conv_pending[0].fill_(-123)
    write_pos[0] = 99
    cache_base[0] = 77
    is_flush[0] = 1
    pending[0] = 1
    pending_len[0] = args.max_spec_len

    return {
        "conv_state": conv_state,
        "write_pos": write_pos,
        "cache_base": cache_base,
        "is_flush": is_flush,
        "pending": pending,
        "pending_len": pending_len,
        "conv_pending": conv_pending,
        "num_accepted_tokens": num_accepted_tokens.contiguous(),
        "state_indices": state_indices.contiguous(),
    }


def clone_case(torch: Any, case: dict[str, Any]) -> dict[str, Any]:
    return {key: value.clone() for key, value in case.items()}


def max_abs(torch: Any, left: Any, right: Any) -> float:
    if left.numel() == 0:
        return 0.0
    return float((left.float() - right.float()).abs().max().cpu().item())


def main() -> int:
    args = parse_args()
    if args.conv_base_len > args.conv_state_len:
        raise SystemExit("--conv-base-len must be <= --conv-state-len")
    if args.max_cache_len & (args.max_cache_len - 1):
        raise SystemExit("--max-cache-len must be a power of two")

    add_kernel_repo_to_path(args.kernel_repo)
    import torch
    import vllm_xpu_kernels._xpu_C  # noqa: F401

    if not hasattr(torch, "xpu") or not torch.xpu.is_available():
        raise SystemExit("torch.xpu is not available")

    device = torch.device(args.device)
    torch.xpu.set_device(device)
    case = build_case(torch, args)
    expected = clone_case(torch, case)
    observed = clone_case(torch, case)

    reference_commit_pending(
        torch,
        conv_state=expected["conv_state"],
        write_pos=expected["write_pos"],
        cache_base=expected["cache_base"],
        is_flush=expected["is_flush"],
        pending=expected["pending"],
        pending_len=expected["pending_len"],
        conv_pending=expected["conv_pending"],
        num_accepted_tokens=expected["num_accepted_tokens"],
        state_indices=expected["state_indices"],
        max_cache_len=args.max_cache_len,
        max_spec_len=args.max_spec_len,
        conv_base_len=args.conv_base_len,
    )
    torch.ops._xpu_C.gdn_replayssm_commit_pending(
        observed["conv_state"],
        observed["write_pos"],
        observed["cache_base"],
        observed["is_flush"],
        observed["pending"],
        observed["pending_len"],
        observed["conv_pending"],
        observed["num_accepted_tokens"],
        observed["state_indices"],
        args.max_cache_len,
        args.max_spec_len,
        args.conv_base_len,
        0,
    )
    torch.xpu.synchronize(device)

    fields = ("conv_state", "write_pos", "cache_base", "is_flush", "pending")
    equality = {
        name: bool(torch.equal(observed[name], expected[name]))
        for name in fields
    }
    diffs = {
        name: max_abs(torch, observed[name], expected[name])
        for name in fields
    }
    result: dict[str, Any] = {
        "device": str(device),
        "dtype": args.dtype,
        "rows": args.rows,
        "num_slots": args.num_slots,
        "conv_dim": args.conv_dim,
        "conv_base_len": args.conv_base_len,
        "conv_state_len": args.conv_state_len,
        "max_spec_len": args.max_spec_len,
        "max_cache_len": args.max_cache_len,
        "equal": equality,
        "max_abs_diff": diffs,
        "state_indices": [
            int(x) for x in case["state_indices"].detach().cpu().tolist()
        ],
        "num_accepted_tokens": [
            int(x)
            for x in case["num_accepted_tokens"].detach().cpu().tolist()
        ],
    }

    if args.benchmark_iters > 0:
        bench = clone_case(torch, case)
        for _ in range(10):
            torch.ops._xpu_C.gdn_replayssm_commit_pending(
                bench["conv_state"],
                bench["write_pos"],
                bench["cache_base"],
                bench["is_flush"],
                bench["pending"],
                bench["pending_len"],
                bench["conv_pending"],
                bench["num_accepted_tokens"],
                bench["state_indices"],
                args.max_cache_len,
                args.max_spec_len,
                args.conv_base_len,
                0,
            )
        torch.xpu.synchronize(device)
        start = time.perf_counter()
        for _ in range(args.benchmark_iters):
            torch.ops._xpu_C.gdn_replayssm_commit_pending(
                bench["conv_state"],
                bench["write_pos"],
                bench["cache_base"],
                bench["is_flush"],
                bench["pending"],
                bench["pending_len"],
                bench["conv_pending"],
                bench["num_accepted_tokens"],
                bench["state_indices"],
                args.max_cache_len,
                args.max_spec_len,
                args.conv_base_len,
                0,
            )
        torch.xpu.synchronize(device)
        elapsed = time.perf_counter() - start
        result["benchmark"] = {
            "iters": args.benchmark_iters,
            "total_ms": elapsed * 1000.0,
            "mean_us": elapsed * 1_000_000.0 / args.benchmark_iters,
        }

    text = json.dumps(result, sort_keys=True)
    print(text)
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text + "\n", encoding="utf-8")

    if not all(equality.values()):
        raise SystemExit("native ReplaySSM pending commit did not match reference")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
