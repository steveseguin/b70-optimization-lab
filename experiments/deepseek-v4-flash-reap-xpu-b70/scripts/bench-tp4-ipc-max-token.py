#!/usr/bin/env python3
"""Gate a fixed-address TP4 max/token exchange against ordinary XCCL.

The candidate brokers Level Zero IPC allocations once, then publishes one
float32 ``(score, token)`` pair per rank and returns the exact global token with
peer-visible readiness atomics.  The timed seven-step bundle models DSpark's
sequential Markov decisions and includes synchronization on every rank.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
from multiprocessing.reduction import recv_handle, send_handle
from pathlib import Path
import statistics
import time


WORLD = 4
STEPS = 7
CHANNEL = 127
CHANNELS = 128
SLOTS = 3
HIDDEN = 4096
WORKSPACE_BYTES = CHANNELS * SLOTS * HIDDEN * 2 + CHANNELS * SLOTS * WORLD * 4


def quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    position = q * (len(ordered) - 1)
    lo = int(position)
    hi = min(lo + 1, len(ordered) - 1)
    fraction = position - lo
    return ordered[lo] * (1.0 - fraction) + ordered[hi] * fraction


def summary(values: list[float]) -> dict[str, float]:
    return {
        "min_us": min(values),
        "p10_us": quantile(values, 0.10),
        "median_us": statistics.median(values),
        "mean_us": statistics.mean(values),
        "p90_us": quantile(values, 0.90),
        "max_us": max(values),
    }


def worker(
    rank: int,
    conn,
    shm_name: str,
    init_method: str,
    warmups: int,
    iterations: int,
) -> None:
    # Match the vLLM worker topology: every process sees all four devices and
    # selects its local rank. Narrow per-process masks make oneCCL construct an
    # incomplete node topology and corrupt this small all-gather control.
    os.environ["ZE_AFFINITY_MASK"] = "0,1,2,3"
    os.environ["ONEAPI_DEVICE_SELECTOR"] = "level_zero:*"

    import torch
    import torch.distributed as dist
    import vllm_xpu_kernels._xpu_C  # noqa: F401

    torch.xpu.set_device(rank)
    anchor = torch.empty(1, dtype=torch.uint8, device=f"xpu:{rank}")
    workspace = torch.ops._xpu_C.tp4_ipc_allocate_workspace(anchor)
    if workspace.numel() != WORKSPACE_BYTES:
        raise RuntimeError(f"unexpected workspace size {workspace.numel()}")
    fd, allocation_offset, handle_words = torch.ops._xpu_C.tp4_ipc_export_fd(workspace)
    conn.send((rank, allocation_offset, os.getpid(), handle_words))
    send_handle(conn, fd, os.getppid())

    peer_metadata = conn.recv()
    peer_fds: list[int] = []
    for peer_rank, peer_offset, peer_handle_words in peer_metadata:
        peer_fd = recv_handle(conn)
        torch.ops._xpu_C.tp4_ipc_register_fd(
            workspace,
            peer_rank,
            peer_fd,
            peer_offset,
            peer_handle_words,
        )
        peer_fds.append(peer_fd)

    dist.init_process_group(
        "xccl",
        rank=rank,
        world_size=WORLD,
        init_method=init_method,
        device_id=torch.device(f"xpu:{rank}"),
    )
    torch.ops._xpu_C.tp4_host_pair_init(anchor, shm_name, rank)
    local_pairs = [
        torch.empty(2, dtype=torch.float32, device=f"xpu:{rank}") for _ in range(STEPS)
    ]
    gathered = [
        torch.empty(WORLD, 2, dtype=torch.float32, device=f"xpu:{rank}")
        for _ in range(STEPS)
    ]
    reference_tokens = [
        torch.empty(1, dtype=torch.int64, device=f"xpu:{rank}") for _ in range(STEPS)
    ]
    candidate_tokens = [
        torch.empty(1, dtype=torch.int64, device=f"xpu:{rank}") for _ in range(STEPS)
    ]

    def set_inputs(epoch: int) -> None:
        for step, pair in enumerate(local_pairs):
            # Rank/step winners change every epoch. Every eleventh epoch forces
            # a score tie so global lowest-token tie breaking is exercised.
            winner = (epoch * 3 + step * 5) % WORLD
            score = 5.0 + 0.125 * step - abs(rank - winner) * 0.75
            token = rank * 32320 + ((epoch * 97 + step * 193) % 32320)
            if epoch % 11 == 0 and rank in (1, 2):
                score = 9.0 + 0.125 * step
            pair.copy_(torch.tensor([score, float(token)], dtype=torch.float32))
        torch.xpu.synchronize()

    def control() -> None:
        for step in range(STEPS):
            dist.all_gather_into_tensor(gathered[step], local_pairs[step])
            torch.ops._xpu_C.argmax_from_gathered_pairs_out(
                gathered[step].view(1, WORLD, 2), reference_tokens[step]
            )

    candidate_epoch = 1

    def candidate() -> None:
        nonlocal candidate_epoch
        for step in range(STEPS):
            epoch = candidate_epoch
            torch.ops._xpu_C.tp4_host_max_token_from_pair_out(
                local_pairs[step],
                candidate_tokens[step],
                rank,
                epoch,
            )
            candidate_epoch += 1

    conn.send(("ready", rank))
    if conn.recv() != "go":
        raise RuntimeError("parent did not release workers")

    exact = True
    mismatch_steps = 0
    first_mismatch: dict[str, object] | None = None
    control_us: list[float] = []
    candidate_us: list[float] = []
    total = warmups + iterations
    for epoch in range(total):
        set_inputs(epoch)
        dist.barrier()
        start = time.perf_counter_ns()
        control()
        torch.xpu.synchronize()
        control_elapsed = (time.perf_counter_ns() - start) / 1000.0

        dist.barrier()
        start = time.perf_counter_ns()
        candidate()
        torch.xpu.synchronize()
        candidate_elapsed = (time.perf_counter_ns() - start) / 1000.0

        for step, (reference, actual) in enumerate(
            zip(reference_tokens, candidate_tokens, strict=True)
        ):
            same = torch.equal(reference, actual)
            exact = exact and same
            if not same:
                mismatch_steps += 1
                if first_mismatch is None:
                    first_mismatch = {
                        "epoch": epoch,
                        "step": step,
                        "reference": int(reference.item()),
                        "actual": int(actual.item()),
                        "local_pair": local_pairs[step].cpu().tolist(),
                        "gathered_pairs": gathered[step].cpu().tolist(),
                    }
        if epoch >= warmups:
            control_us.append(control_elapsed)
            candidate_us.append(candidate_elapsed)

    conn.send(
        {
            "rank": rank,
            "exact": exact,
            "mismatch_steps": mismatch_steps,
            "first_mismatch": first_mismatch,
            "control_seven_steps": summary(control_us),
            "candidate_seven_steps": summary(candidate_us),
            "median_saved_us": statistics.median(control_us)
            - statistics.median(candidate_us),
        }
    )
    dist.destroy_process_group()
    torch.ops._xpu_C.tp4_ipc_clear(workspace)
    for peer_fd in peer_fds:
        os.close(peer_fd)
    conn.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--warmups", type=int, default=12)
    parser.add_argument("--iterations", type=int, default=80)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    context = mp.get_context("spawn")
    shm_name = f"/deepseek-v4-host-pair-{os.getpid()}"
    parent_connections = []
    children = []
    port = 30570 + (os.getpid() % 1000)
    init_method = f"tcp://127.0.0.1:{port}"
    for rank in range(WORLD):
        parent, child = context.Pipe(duplex=True)
        process = context.Process(
            target=worker,
            args=(
                rank,
                child,
                shm_name,
                init_method,
                args.warmups,
                args.iterations,
            ),
        )
        process.start()
        child.close()
        parent_connections.append(parent)
        children.append(process)

    exports = []
    for connection in parent_connections:
        rank, offset, child_pid, handle_words = connection.recv()
        fd = recv_handle(connection)
        exports.append((rank, offset, child_pid, fd, handle_words))

    for destination, connection in enumerate(parent_connections):
        peers = [
            (rank, offset, handle_words)
            for rank, offset, _, _, handle_words in exports
            if rank != destination
        ]
        connection.send(peers)
        destination_pid = exports[destination][2]
        for rank, _, _, fd, _ in exports:
            if rank != destination:
                send_handle(connection, fd, destination_pid)
    for _, _, _, fd, _ in exports:
        os.close(fd)

    for connection in parent_connections:
        message, _ = connection.recv()
        if message != "ready":
            raise RuntimeError(f"unexpected worker message {message}")
    for connection in parent_connections:
        connection.send("go")

    ranks = [connection.recv() for connection in parent_connections]
    for process in children:
        process.join(timeout=60)
        if process.exitcode != 0:
            raise RuntimeError(f"worker {process.pid} exited {process.exitcode}")

    slowest_control = max(row["control_seven_steps"]["median_us"] for row in ranks)
    slowest_candidate = max(row["candidate_seven_steps"]["median_us"] for row in ranks)
    result = {
        "schema_version": 1,
        "classification": "deepseek_v4_tp4_fixed_ipc_max_token_gate",
        "passed": all(row["exact"] for row in ranks)
        and slowest_candidate < slowest_control,
        "exact_all_ranks": all(row["exact"] for row in ranks),
        "world_size": WORLD,
        "sequential_steps": STEPS,
        "warmups": args.warmups,
        "iterations": args.iterations,
        "control": "XCCL all_gather_into_tensor plus native pair selection",
        "candidate": "process-shared host pair barrier with direct D2H/H2D",
        "slowest_rank_control_median_us": slowest_control,
        "slowest_rank_candidate_median_us": slowest_candidate,
        "slowest_rank_saved_us": slowest_control - slowest_candidate,
        "ranks": ranks,
    }
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered + "\n")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
