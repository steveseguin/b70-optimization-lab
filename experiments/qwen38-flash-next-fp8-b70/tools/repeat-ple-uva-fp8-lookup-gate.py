#!/usr/bin/env python3
"""Check the exact TP4 selective-UVA FP8 PLE lookup path on fixed inputs."""

import argparse
import hashlib
import json
import os
import time

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
    parser.add_argument(
        "--async-prefetch",
        action="store_true",
        help=(
            "Run the local UVA lookup on a side XPU stream, join it on the "
            "main stream, and keep the TP reduction on the main stream"
        ),
    )
    parser.add_argument(
        "--vary-generations",
        action="store_true",
        help=(
            "Cycle maximum, small, and medium token counts with different row "
            "IDs to expose stale-buffer and cross-generation reuse errors"
        ),
    )
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

        generation_specs = [("fixed", args.rows, 0)]
        if args.vary_generations:
            generation_specs = [
                ("maximum", args.rows, 0),
                ("small", max(1, args.rows // 3), 104729),
                ("medium", max(1, args.rows * 2 // 3), 224737),
            ]
        generations = []
        expected_columns = torch.arange(args.head_dim, dtype=torch.int64).reshape(1, -1)
        for label, row_count, offset in generation_specs:
            token_heads = row_count * args.heads
            ids_cpu = (
                torch.arange(token_heads, dtype=torch.int64) * 7919 + 17 + offset
            ) % global_vocab
            ids = ids_cpu.reshape(row_count, args.heads).to(device)
            input_mask = (ids < global_start) | (ids >= global_start + args.local_vocab)
            local_ids = (ids - global_start).masked_fill(input_mask, 0)
            expected_rows = ids_cpu.reshape(-1, 1)
            expected = fp8_values(expected_rows, expected_columns).reshape(
                row_count, args.heads, args.head_dim
            )
            generations.append(
                (label, local_ids, input_mask, expected.view(torch.int8))
            )

        snapshots: list[tuple[str, torch.Tensor, torch.Tensor]] = []
        started = time.perf_counter()
        if args.async_prefetch:
            lookup_stream = torch.xpu.Stream()
            input_ready = torch.xpu.Event()
            lookup_done = torch.xpu.Event()
            output_parallel = torch.empty(
                args.rows,
                args.heads,
                args.head_dim,
                dtype=host_weight.dtype,
                device=device,
            )
            for repeat in range(args.repeats):
                label, local_ids, input_mask, expected_bytes = generations[
                    repeat % len(generations)
                ]
                row_count = local_ids.shape[0]
                active = output_parallel[:row_count]
                main_stream = torch.xpu.current_stream()
                input_ready.record(main_stream)
                lookup_stream.wait_event(input_ready)
                local_ids.record_stream(lookup_stream)
                with torch.xpu.stream(lookup_stream):
                    torch.index_select(
                        uva_weight,
                        0,
                        local_ids.reshape(-1),
                        out=active.reshape(-1, args.head_dim),
                    )
                    active.view(torch.int8).masked_fill_(input_mask.unsqueeze(-1), 0)
                    lookup_done.record(lookup_stream)
                main_stream.wait_event(lookup_done)
                comm_output = active.view(torch.int8)
                dist.all_reduce(comm_output, op=dist.ReduceOp.SUM)
                # The clone models downstream main-stream consumption. The next
                # input_ready event prevents the side stream from overwriting
                # the persistent buffer until that consumption is enqueued.
                snapshots.append((label, comm_output.clone(), expected_bytes))
            torch.xpu.synchronize()
        else:
            for repeat in range(args.repeats):
                label, local_ids, input_mask, expected_bytes = generations[
                    repeat % len(generations)
                ]
                output_parallel = F.embedding(local_ids, uva_weight)
                comm_output = output_parallel.view(torch.int8)
                comm_output.masked_fill_(input_mask.unsqueeze(-1), 0)
                dist.all_reduce(comm_output, op=dist.ReduceOp.SUM)
                snapshots.append((label, comm_output.cpu(), expected_bytes))
            torch.xpu.synchronize()
        elapsed_s = time.perf_counter() - started

        hashes: list[str] = []
        oracle_matches: list[bool] = []
        generation_hashes: dict[str, list[str]] = {
            label: [] for label, *_ in generations
        }
        for label, snapshot, expected_bytes in snapshots:
            output_bytes = snapshot.cpu()
            raw = output_bytes.contiguous().view(torch.uint8).numpy().tobytes()
            output_hash = hashlib.sha256(raw).hexdigest()
            hashes.append(output_hash)
            generation_hashes[label].append(output_hash)
            oracle_matches.append(bool(torch.equal(output_bytes, expected_bytes)))
        generation_unique_hashes = {
            label: sorted(set(values)) for label, values in generation_hashes.items()
        }
        generations_repeatable = all(
            len(values) == 1 for values in generation_unique_hashes.values()
        )

        print(
            json.dumps(
                {
                    "dtype": "float8_e4m3fn_via_int8_sum",
                    "elapsed_s": elapsed_s,
                    "head_dim": args.head_dim,
                    "heads": args.heads,
                    "generation_output_sha256": generation_unique_hashes,
                    "generations_repeatable": generations_repeatable,
                    "local_vocab": args.local_vocab,
                    "oracle_match_all": all(oracle_matches),
                    "output_sha256_first": hashes[0],
                    "output_sha256_unique_values": sorted(set(hashes)),
                    "rank": rank,
                    "repeats": args.repeats,
                    "rows": args.rows,
                    "side_stream_lookup": args.async_prefetch,
                    "storage": "pinned_cpu_with_accelerator_uva_view",
                    "unique_output_sha256": len(set(hashes)),
                    "vary_generations": args.vary_generations,
                    "world_size": world_size,
                },
                sort_keys=True,
            ),
            flush=True,
        )
        if not generations_repeatable or not all(oracle_matches):
            raise SystemExit(1)
        dist.barrier(device_ids=[local_rank])
    finally:
        dist.destroy_process_group()


if __name__ == "__main__":
    main()
