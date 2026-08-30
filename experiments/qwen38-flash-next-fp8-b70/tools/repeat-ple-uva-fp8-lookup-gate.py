#!/usr/bin/env python3
"""Check the exact TP4 selective-UVA FP8 PLE lookup path on fixed inputs."""

import argparse
import hashlib
import json
import os

import torch
import torch.distributed as dist
import torch.nn.functional as F

from vllm.utils.torch_utils import get_accelerator_view_from_cpu_tensor


def fp8_values(rows: torch.Tensor, columns: torch.Tensor) -> torch.Tensor:
    values = ((rows * 17 + columns * 31) % 241 - 120).to(torch.float32) / 32
    return values.to(torch.float8_e4m3fn)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=64)
    parser.add_argument("--heads", type=int, default=16)
    parser.add_argument("--head-dim", type=int, default=160)
    parser.add_argument("--local-vocab", type=int, default=4096)
    parser.add_argument("--repeats", type=int, default=100)
    args = parser.parse_args()
    if (
        min(
            args.rows,
            args.heads,
            args.head_dim,
            args.local_vocab,
            args.repeats,
        )
        <= 0
    ):
        raise ValueError("all dimensions and repeat counts must be positive")

    rank = int(os.environ["RANK"])
    local_rank = int(os.environ["LOCAL_RANK"])
    world_size = int(os.environ["WORLD_SIZE"])
    device = torch.device(f"xpu:{local_rank}")
    torch.xpu.set_device(device)
    dist.init_process_group("xccl")

    try:
        global_vocab = args.local_vocab * world_size
        global_start = rank * args.local_vocab
        local_rows = torch.arange(args.local_vocab, dtype=torch.int64).unsqueeze(1)
        columns = torch.arange(args.head_dim, dtype=torch.int64).unsqueeze(0)
        host_weight = fp8_values(global_start + local_rows, columns).pin_memory()
        uva_weight = get_accelerator_view_from_cpu_tensor(host_weight)

        token_heads = args.rows * args.heads
        ids_cpu = (
            torch.arange(token_heads, dtype=torch.int64) * 7919 + 17
        ) % global_vocab
        ids = ids_cpu.reshape(args.rows, args.heads).to(device)
        input_mask = (ids < global_start) | (ids >= global_start + args.local_vocab)
        local_ids = (ids - global_start).masked_fill(input_mask, 0)

        expected_rows = ids_cpu.reshape(-1, 1)
        expected_columns = torch.arange(args.head_dim, dtype=torch.int64).reshape(1, -1)
        expected = fp8_values(expected_rows, expected_columns).reshape(
            args.rows, args.heads, args.head_dim
        )
        expected_bytes = expected.view(torch.int8)

        hashes: list[str] = []
        oracle_matches: list[bool] = []
        for _ in range(args.repeats):
            output_parallel = F.embedding(local_ids, uva_weight)
            comm_output = output_parallel.view(torch.int8)
            comm_output.masked_fill_(input_mask.unsqueeze(-1), 0)
            dist.all_reduce(comm_output, op=dist.ReduceOp.SUM)
            torch.xpu.synchronize()
            output_bytes = comm_output.cpu()
            raw = output_bytes.contiguous().view(torch.uint8).numpy().tobytes()
            hashes.append(hashlib.sha256(raw).hexdigest())
            oracle_matches.append(bool(torch.equal(output_bytes, expected_bytes)))

        print(
            json.dumps(
                {
                    "dtype": "float8_e4m3fn_via_int8_sum",
                    "head_dim": args.head_dim,
                    "heads": args.heads,
                    "local_vocab": args.local_vocab,
                    "oracle_match_all": all(oracle_matches),
                    "output_sha256_first": hashes[0],
                    "output_sha256_unique_values": sorted(set(hashes)),
                    "rank": rank,
                    "repeats": args.repeats,
                    "rows": args.rows,
                    "storage": "pinned_cpu_with_accelerator_uva_view",
                    "unique_output_sha256": len(set(hashes)),
                    "world_size": world_size,
                },
                sort_keys=True,
            ),
            flush=True,
        )
        if len(set(hashes)) != 1 or not all(oracle_matches):
            raise SystemExit(1)
        dist.barrier(device_ids=[local_rank])
    finally:
        dist.destroy_process_group()


if __name__ == "__main__":
    main()
