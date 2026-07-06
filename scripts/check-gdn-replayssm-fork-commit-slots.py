#!/usr/bin/env python3
"""Parity check for ReplaySSM branch fork + accepted-prefix commit.

This validates the graph-safe composition available today:

1. copy the normal GDN conv state from source slot to branch slot;
2. use native ``gdn_replayssm_copy_slots`` for ReplaySSM ring/metadata;
3. use native ``gdn_replayssm_commit_pending`` on the branch slot.

That is the smallest branch/regenerate transaction we can test before wiring
any endpoint repair path. It is not a throughput benchmark.
"""

from __future__ import annotations

import argparse
import json
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
    parser.add_argument("--num-slots", type=int, default=9)
    parser.add_argument("--num-k-heads", type=int, default=2)
    parser.add_argument("--num-v-heads", type=int, default=4)
    parser.add_argument("--head-k-dim", type=int, default=8)
    parser.add_argument("--head-v-dim", type=int, default=8)
    parser.add_argument("--cache-len", type=int, default=8)
    parser.add_argument("--max-spec-len", type=int, default=4)
    parser.add_argument("--conv-dim", type=int, default=41)
    parser.add_argument("--conv-state-len", type=int, default=4)
    parser.add_argument("--conv-base-len", type=int, default=3)
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


def clone_case(case: dict[str, Any]) -> dict[str, Any]:
    return {name: tensor.clone() for name, tensor in case.items()}


def max_abs(torch: Any, left: Any, right: Any) -> float:
    if left.numel() == 0:
        return 0.0
    return float((left.float() - right.float()).abs().max().cpu().item())


def reference_fork_commit(
    torch: Any,
    case: dict[str, Any],
    *,
    src_indices: Any,
    dst_indices: Any,
    accepted_counts: Any,
    max_cache_len: int,
    max_spec_len: int,
    conv_base_len: int,
    null_block_id: int = 0,
) -> None:
    rows = min(
        int(src_indices.numel()),
        int(dst_indices.numel()),
        int(accepted_counts.numel()),
    )
    for row in range(rows):
        src = int(src_indices[row].item())
        dst = int(dst_indices[row].item())
        if src <= null_block_id or dst <= null_block_id:
            continue
        if src >= int(case["conv_state"].size(0)):
            continue
        if dst >= int(case["conv_state"].size(0)):
            continue

        for name in ("d_cache", "k_cache", "g_cache", "conv_pending",
                     "conv_state", "write_pos", "cache_base", "is_flush",
                     "pending", "pending_len"):
            case[name][dst].copy_(case[name][src])

        if int(case["pending"][src].item()) == 0:
            continue

        accepted = max(0, int(accepted_counts[row].item()))
        accepted = min(accepted, int(case["pending_len"][src].item()))

        if conv_base_len > 0:
            before = case["conv_state"][src].clone()
            old_conv = before[:, :conv_base_len]
            raw = case["conv_pending"][src]
            history = torch.cat((old_conv.t().contiguous(), raw), dim=0)
            for state_pos in range(conv_base_len):
                source_pos = accepted + state_pos
                case["conv_state"][dst, :, state_pos].copy_(
                    history[source_pos].to(case["conv_state"].dtype))
            if conv_base_len < int(case["conv_state"].size(2)):
                case["conv_state"][dst, :, conv_base_len:].copy_(
                    before[:, conv_base_len:])

        old_wp = int(case["write_pos"][src].item())
        old_base = int(case["cache_base"][src].item())
        old_flush = int(case["is_flush"][src].item()) != 0
        flush_now = accepted > 0 and old_flush
        new_base = (old_base + old_wp) % max_cache_len if flush_now else old_base
        new_wp = accepted if old_flush else old_wp + accepted
        next_flush = (new_wp + 2 * max_spec_len) > max_cache_len
        case["write_pos"][dst] = new_wp
        case["cache_base"][dst] = new_base
        case["is_flush"][dst] = 1 if next_flush else 0
        case["pending"][dst] = 0


def build_case(torch: Any, args: argparse.Namespace) -> dict[str, Any]:
    torch.manual_seed(args.seed)
    torch.xpu.manual_seed_all(args.seed)
    device = torch.device(args.device)
    dtype = dtype_from_name(torch, args.dtype)
    slots = args.num_slots
    case = {
        "conv_state": torch.randn(
            (slots, args.conv_dim, args.conv_state_len),
            device=device,
            dtype=dtype,
        ).contiguous(),
        "d_cache": torch.randn(
            (slots, args.num_v_heads, args.cache_len, args.head_v_dim),
            device=device,
            dtype=dtype,
        ).contiguous(),
        "k_cache": torch.randn(
            (slots, args.num_k_heads, args.cache_len, args.head_k_dim),
            device=device,
            dtype=dtype,
        ).contiguous(),
        "g_cache": torch.randn(
            (slots, args.num_v_heads, args.cache_len),
            device=device,
            dtype=torch.float32,
        ).contiguous(),
        "conv_pending": torch.randn(
            (slots, args.max_spec_len, args.conv_dim),
            device=device,
            dtype=dtype,
        ).contiguous(),
        "write_pos": torch.randint(
            0, args.cache_len // 2 + 1, (slots,),
            device=device,
            dtype=torch.int32,
        ),
        "cache_base": torch.randint(
            0, args.cache_len, (slots,), device=device, dtype=torch.int32),
        "is_flush": torch.randint(
            0, 2, (slots,), device=device, dtype=torch.int8),
        "pending": torch.randint(
            0, 2, (slots,), device=device, dtype=torch.int8),
        "pending_len": torch.randint(
            0, args.max_spec_len + 1, (slots,),
            device=device,
            dtype=torch.int32,
        ),
    }
    case["pending"][0] = 1
    case["write_pos"][0] = 99
    case["cache_base"][0] = 77
    case["is_flush"][0] = 1
    case["pending_len"][0] = args.max_spec_len
    case["pending"][1] = 1
    case["pending_len"][1] = args.max_spec_len
    case["pending"][2] = 0
    case["pending_len"][2] = args.max_spec_len
    return case


def main() -> int:
    args = parse_args()
    if args.conv_base_len > args.conv_state_len:
        raise SystemExit("--conv-base-len must be <= --conv-state-len")
    if args.cache_len & (args.cache_len - 1):
        raise SystemExit("--cache-len must be a power of two")

    add_kernel_repo_to_path(args.kernel_repo)
    import torch
    import vllm_xpu_kernels._xpu_C  # noqa: F401

    required = ("gdn_replayssm_copy_slots", "gdn_replayssm_commit_pending")
    missing = [name for name in required if not hasattr(torch.ops._xpu_C, name)]
    if missing:
        raise SystemExit("Missing native ops: " + ", ".join(missing))
    if not hasattr(torch, "xpu") or not torch.xpu.is_available():
        raise SystemExit("torch.xpu is not available")

    device = torch.device(args.device)
    torch.xpu.set_device(device)
    case = build_case(torch, args)
    observed = clone_case(case)
    expected = clone_case(case)
    original = clone_case(case)

    src = torch.tensor([1, 2, 0, -1, args.num_slots + 3],
                       device=device, dtype=torch.long)
    dst = torch.tensor([5, 6, 7, 8, 4], device=device, dtype=torch.long)
    accepted = torch.tensor([args.max_spec_len + 2, 2, 3, 1, 1],
                            device=device, dtype=torch.int32)
    reference_fork_commit(
        torch,
        expected,
        src_indices=src,
        dst_indices=dst,
        accepted_counts=accepted,
        max_cache_len=args.cache_len,
        max_spec_len=args.max_spec_len,
        conv_base_len=args.conv_base_len,
    )

    valid_copy = (
        (src > 0)
        & (src < observed["conv_state"].size(0))
        & (dst > 0)
        & (dst < observed["conv_state"].size(0))
    )
    if bool(torch.any(valid_copy).item()):
        observed["conv_state"].index_copy_(
            0,
            dst[valid_copy],
            observed["conv_state"].index_select(0, src[valid_copy]).clone(),
        )
    torch.ops._xpu_C.gdn_replayssm_copy_slots(
        observed["d_cache"],
        observed["k_cache"],
        observed["g_cache"],
        observed["write_pos"],
        observed["cache_base"],
        observed["is_flush"],
        observed["pending"],
        observed["pending_len"],
        observed["conv_pending"],
        src.contiguous(),
        dst.contiguous(),
        0,
    )
    # Important: commit only rows whose source and destination were valid.
    # Native copy_slots correctly ignores invalid source rows, but committing
    # the raw destination list would treat an unrelated active destination slot
    # as pending branch state and mutate it.
    if bool(torch.any(valid_copy).item()):
        torch.ops._xpu_C.gdn_replayssm_commit_pending(
            observed["conv_state"],
            observed["write_pos"],
            observed["cache_base"],
            observed["is_flush"],
            observed["pending"],
            observed["pending_len"],
            observed["conv_pending"],
            accepted[valid_copy].contiguous(),
            dst[valid_copy].contiguous(),
            args.cache_len,
            args.max_spec_len,
            args.conv_base_len,
            0,
        )
    torch.xpu.synchronize(device)

    fields = tuple(expected.keys())
    equality = {
        name: bool(torch.equal(observed[name], expected[name]))
        for name in fields
    }
    diffs = {
        name: max_abs(torch, observed[name], expected[name])
        for name in fields
    }
    source_unchanged = {
        f"{name}[{src_slot}]": bool(
            torch.equal(observed[name][src_slot], original[name][src_slot]))
        for name in fields
        for src_slot in (1, 2)
    }
    result = {
        "device": args.device,
        "dtype": args.dtype,
        "equal": equality,
        "max_abs_diff": diffs,
        "source_slots_unchanged": source_unchanged,
        "src_indices": [int(x) for x in src.cpu().tolist()],
        "dst_indices": [int(x) for x in dst.cpu().tolist()],
        "accepted": [int(x) for x in accepted.cpu().tolist()],
        "pass": (
            all(equality.values())
            and all(source_unchanged.values())
        ),
    }
    text = json.dumps(result, sort_keys=True)
    print(text)
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text + "\n", encoding="utf-8")
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
