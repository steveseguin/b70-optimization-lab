#!/usr/bin/env python3
"""Check repeatability of the Flash-Next TP4-sized XCCL reduction."""

import argparse
import hashlib
import json
import os

import torch
import torch.distributed as dist


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=64)
    parser.add_argument("--hidden", type=int, default=2560)
    parser.add_argument("--repeats", type=int, default=100)
    parser.add_argument("--dtype", choices=("bfloat16", "float32"), default="bfloat16")
    args = parser.parse_args()
    if args.rows <= 0 or args.hidden <= 0:
        raise ValueError("rows and hidden must be positive")
    if not 1 <= args.repeats <= 1000:
        raise ValueError("repeats must be between 1 and 1000")

    rank = int(os.environ["RANK"])
    local_rank = int(os.environ["LOCAL_RANK"])
    world_size = int(os.environ["WORLD_SIZE"])
    dtype = getattr(torch, args.dtype)
    device = torch.device(f"xpu:{local_rank}")
    torch.xpu.set_device(device)
    dist.init_process_group("xccl")

    try:
        numel = args.rows * args.hidden
        indices = torch.arange(numel, dtype=torch.int64)
        values = ((indices * 17 + rank * 31) % 251 - 125).to(torch.float32) / 128
        base = values.to(dtype).reshape(args.rows, args.hidden).to(device)
        hashes: list[str] = []
        output = None
        for _ in range(args.repeats):
            output = base.clone()
            dist.all_reduce(output, op=dist.ReduceOp.SUM)
            torch.xpu.synchronize()
            raw = output.contiguous().view(torch.uint8).cpu().numpy().tobytes()
            hashes.append(hashlib.sha256(raw).hexdigest())

        assert output is not None
        output_float = output.float().cpu()
        print(
            json.dumps(
                {
                    "dtype": args.dtype,
                    "finite": bool(torch.isfinite(output_float).all()),
                    "hidden": args.hidden,
                    "max_abs": float(output_float.abs().max()),
                    "output_sha256_first": hashes[0],
                    "output_sha256_unique_values": sorted(set(hashes)),
                    "rank": rank,
                    "repeats": args.repeats,
                    "rows": args.rows,
                    "unique_output_sha256": len(set(hashes)),
                    "world_size": world_size,
                },
                sort_keys=True,
            ),
            flush=True,
        )
        dist.barrier(device_ids=[local_rank])
    finally:
        dist.destroy_process_group()


if __name__ == "__main__":
    main()
