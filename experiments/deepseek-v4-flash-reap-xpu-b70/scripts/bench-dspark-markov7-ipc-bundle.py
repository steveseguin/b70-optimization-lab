#!/usr/bin/env python3
"""Four-B70 exact/performance gate for the bundled DSpark M7 transaction.

The control is the promoted replicated-W1/sharded-W2 implementation with a
full-vocabulary all-gather at each of seven sequential Markov positions.  The
candidate replaces the Python loop and collectives with one native call using
one-shot Level Zero IPC events.  Real checkpoint weights are mandatory.
"""

from __future__ import annotations

import argparse
import errno
import json
import multiprocessing as mp
import os
from pathlib import Path
import statistics
import time


WORLD = 4
STEPS = 7
VOCAB = 129280
MARKOV_RANK = 256
PARTITION = VOCAB // WORLD
CHANNELS = 128
SLOTS = 3
HIDDEN = 4096
WORKSPACE_BYTES = CHANNELS * SLOTS * HIDDEN * 2 + CHANNELS * SLOTS * WORLD * 4
W1_NAME = "mtp.2.markov_head.markov_w1.weight"
W2_NAME = "mtp.2.markov_head.markov_w2.weight"


def quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    position = q * (len(ordered) - 1)
    lo = int(position)
    hi = min(lo + 1, len(ordered) - 1)
    fraction = position - lo
    return ordered[lo] * (1.0 - fraction) + ordered[hi] * fraction


def summarize(values: list[float]) -> dict[str, float]:
    return {
        "min_us": min(values),
        "p10_us": quantile(values, 0.10),
        "median_us": statistics.median(values),
        "mean_us": statistics.mean(values),
        "p90_us": quantile(values, 0.90),
        "max_us": max(values),
    }


def close_if_owned(fd: int) -> None:
    try:
        os.close(fd)
    except OSError as error:
        if error.errno != errno.EBADF:
            raise


def worker(
    rank: int,
    conn,
    broker_socket: str,
    init_method: str,
    weights: str,
    warmups: int,
    iterations: int,
) -> None:
    os.environ["ZE_AFFINITY_MASK"] = "0,1,2,3"
    os.environ["ONEAPI_DEVICE_SELECTOR"] = "level_zero:*"

    import torch
    import torch.distributed as dist
    from safetensors import safe_open
    import vllm_xpu_kernels._xpu_C  # noqa: F401

    torch.xpu.set_device(rank)
    device = torch.device(f"xpu:{rank}")
    with safe_open(weights, framework="pt", device="cpu") as handle:
        w1_cpu = handle.get_tensor(W1_NAME).contiguous()
        w2_cpu = handle.get_tensor(W2_NAME).contiguous()
    if tuple(w1_cpu.shape) != (VOCAB, MARKOV_RANK):
        raise RuntimeError(f"unexpected W1 shape {tuple(w1_cpu.shape)}")
    if tuple(w2_cpu.shape) != (VOCAB, MARKOV_RANK):
        raise RuntimeError(f"unexpected W2 shape {tuple(w2_cpu.shape)}")
    full_w1 = w1_cpu.to(device)
    local_w2_transposed = (
        w2_cpu.narrow(0, rank * PARTITION, PARTITION)
        .t()
        .contiguous()
        .to(device)
    )
    del w1_cpu, w2_cpu

    anchor_byte = torch.empty(1, dtype=torch.uint8, device=device)
    workspace = torch.ops._xpu_C.tp4_ipc_allocate_workspace(anchor_byte)
    if workspace.numel() != WORKSPACE_BYTES:
        raise RuntimeError(f"unexpected workspace size {workspace.numel()}")
    memory_fd, allocation_offset, memory_words = torch.ops._xpu_C.tp4_ipc_export_fd(
        workspace
    )
    event_count = (warmups + iterations) * STEPS
    event_fd, event_words = torch.ops._xpu_C.tp4_ipc_event_pool_create(
        anchor_byte, event_count
    )
    from vllm.distributed.device_communicators.xpu_ipc_broker import (
        broker_tp4_ipc_handles,
    )

    peers = broker_tp4_ipc_handles(
        socket_path=broker_socket,
        rank=rank,
        world_size=WORLD,
        memory_fd=memory_fd,
        allocation_offset=allocation_offset,
        memory_words=memory_words,
        event_fd=event_fd,
        event_words=event_words,
    )
    peer_memory_fds: list[int] = []
    peer_event_fds: list[int] = []
    for peer in peers:
        torch.ops._xpu_C.tp4_ipc_register_fd(
            workspace,
            peer["rank"],
            peer["memory_fd"],
            peer["allocation_offset"],
            peer["memory_words"],
        )
        torch.ops._xpu_C.tp4_ipc_event_pool_register(
            anchor_byte,
            peer["rank"],
            peer["event_fd"],
            peer["event_words"],
        )
        peer_memory_fds.append(peer["memory_fd"])
        peer_event_fds.append(peer["event_fd"])

    dist.init_process_group(
        "xccl",
        rank=rank,
        world_size=WORLD,
        init_method=init_method,
        device_id=device,
    )
    generator = torch.Generator(device="cpu").manual_seed(0xD5A7)
    # Identical bases on every rank. Scale keeps winners sensitive to both the
    # target logits and real Markov weights instead of manufacturing easy wins.
    full_base_source = (
        torch.randn(
            STEPS, VOCAB, generator=generator, dtype=torch.bfloat16
        ) * 1.75
    ).to(device)
    local_base_logits = full_base_source.narrow(
        1, rank * PARTITION, PARTITION
    ).contiguous()
    anchors = torch.tensor(
        [17, PARTITION + 23, 2 * PARTITION + 31, VOCAB - 19, 97],
        dtype=torch.int32,
        device=device,
    )

    persistent_embed = torch.empty(
        (1, MARKOV_RANK), dtype=torch.bfloat16, device=device
    )
    persistent_local_bias = torch.empty(
        (1, PARTITION), dtype=torch.bfloat16, device=device
    )
    gathered_bias = torch.empty(
        (WORLD, PARTITION), dtype=torch.bfloat16, device=device
    )
    full_logits = torch.empty((1, VOCAB), dtype=torch.bfloat16, device=device)
    control_base_logits = torch.empty(
        (STEPS, VOCAB), dtype=torch.bfloat16, device=device
    )
    gathered_base_parts = [
        torch.empty_like(local_base_logits) for _ in range(WORLD)
    ]
    control_prev = torch.empty(1, dtype=torch.int64, device=device)
    control_tokens = torch.empty(STEPS, dtype=torch.int64, device=device)

    candidate_embed = torch.empty_like(persistent_embed)
    candidate_local_bias = torch.empty_like(persistent_local_bias)
    candidate_pair = torch.empty((1, 2), dtype=torch.float32, device=device)
    candidate_prev = torch.empty(1, dtype=torch.int64, device=device)
    candidate_tokens = torch.empty(STEPS, dtype=torch.int64, device=device)

    def control(anchor: torch.Tensor) -> None:
        dist.all_gather(gathered_base_parts, local_base_logits)
        torch.cat(gathered_base_parts, dim=1, out=control_base_logits)
        control_prev.copy_(anchor)
        for step in range(STEPS):
            torch.index_select(
                full_w1, 0, control_prev, out=persistent_embed
            )
            torch.mm(persistent_embed, local_w2_transposed, out=persistent_local_bias)
            dist.all_gather_into_tensor(gathered_bias, persistent_local_bias)
            torch.add(
                control_base_logits[step].view(1, VOCAB),
                gathered_bias.view(1, VOCAB),
                out=full_logits,
            )
            torch.argmax(full_logits, dim=-1, out=control_prev)
            control_tokens.narrow(0, step, 1).copy_(control_prev)

    def candidate(anchor: torch.Tensor, cycle: int) -> None:
        torch.ops._xpu_C.dspark_tp4_markov7_event_out(
            local_base_logits,
            full_w1,
            local_w2_transposed,
            anchor,
            workspace,
            candidate_embed,
            candidate_local_bias,
            candidate_pair,
            candidate_prev,
            candidate_tokens,
            rank,
            cycle * STEPS,
        )

    conn.send(("ready", rank))
    if conn.recv() != "go":
        raise RuntimeError("parent did not release workers")

    exact = True
    mismatch_cycles = 0
    first_mismatch: dict[str, object] | None = None
    control_us: list[float] = []
    candidate_us: list[float] = []
    total = warmups + iterations
    for cycle in range(total):
        anchor = anchors[cycle % anchors.numel() : cycle % anchors.numel() + 1]
        dist.barrier()
        start_ns = time.perf_counter_ns()
        control(anchor)
        torch.xpu.synchronize()
        control_elapsed = (time.perf_counter_ns() - start_ns) / 1000.0

        dist.barrier()
        start_ns = time.perf_counter_ns()
        candidate(anchor, cycle)
        torch.xpu.synchronize()
        candidate_elapsed = (time.perf_counter_ns() - start_ns) / 1000.0

        same = torch.equal(control_tokens, candidate_tokens)
        exact = exact and same
        if not same:
            mismatch_cycles += 1
            if first_mismatch is None:
                first_mismatch = {
                    "cycle": cycle,
                    "anchor": int(anchor.item()),
                    "control": control_tokens.cpu().tolist(),
                    "candidate": candidate_tokens.cpu().tolist(),
                }
        if cycle >= warmups:
            control_us.append(control_elapsed)
            candidate_us.append(candidate_elapsed)

    conn.send(
        {
            "rank": rank,
            "exact": exact,
            "mismatch_cycles": mismatch_cycles,
            "first_mismatch": first_mismatch,
            "control": summarize(control_us),
            "candidate": summarize(candidate_us),
        }
    )
    if conn.recv() != "cleanup":
        raise RuntimeError("parent did not release cleanup")
    dist.destroy_process_group()
    torch.ops._xpu_C.tp4_ipc_event_clear(anchor_byte)
    torch.ops._xpu_C.tp4_ipc_clear(workspace)
    for fd in peer_memory_fds:
        close_if_owned(fd)
    for fd in peer_event_fds:
        close_if_owned(fd)
    conn.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--warmups", type=int, default=12)
    parser.add_argument("--iterations", type=int, default=40)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.weights.is_file():
        parser.error(f"weights shard is missing: {args.weights}")
    if args.warmups < 0 or args.iterations <= 0:
        parser.error("warmups must be non-negative and iterations positive")

    context = mp.get_context("spawn")
    parents = []
    processes = []
    broker_socket = f"/tmp/dspark-markov7-bundle-{os.getpid()}.sock"
    init_method = f"tcp://127.0.0.1:{31570 + os.getpid() % 1000}"
    for rank in range(WORLD):
        parent, child = context.Pipe(duplex=True)
        process = context.Process(
            target=worker,
            args=(
                rank,
                child,
                broker_socket,
                init_method,
                str(args.weights),
                args.warmups,
                args.iterations,
            ),
        )
        process.start()
        child.close()
        parents.append(parent)
        processes.append(process)

    for connection in parents:
        message, _ = connection.recv()
        if message != "ready":
            raise RuntimeError(f"unexpected worker message {message}")
    for connection in parents:
        connection.send("go")
    ranks = [connection.recv() for connection in parents]
    for connection in parents:
        connection.send("cleanup")
    for process in processes:
        process.join(timeout=60)
        if process.exitcode != 0:
            raise RuntimeError(f"worker {process.pid} exited {process.exitcode}")

    slowest_control = max(row["control"]["median_us"] for row in ranks)
    slowest_candidate = max(row["candidate"]["median_us"] for row in ranks)
    saved = slowest_control - slowest_candidate
    result = {
        "schema_version": 1,
        "classification": "deepseek_v4_dspark_markov7_ipc_bundle_gate",
        "passed": all(row["exact"] for row in ranks) and saved >= 1000.0,
        "exact": all(row["exact"] for row in ranks),
        "performance_gate_us": 1000.0,
        "slowest_rank_control_median_us": slowest_control,
        "slowest_rank_candidate_median_us": slowest_candidate,
        "slowest_rank_saved_us": saved,
        "weights": str(args.weights),
        "warmups": args.warmups,
        "iterations": args.iterations,
        "ranks": ranks,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
