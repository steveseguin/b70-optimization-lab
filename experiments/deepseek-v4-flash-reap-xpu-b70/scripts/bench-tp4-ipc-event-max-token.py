#!/usr/bin/env python3
"""Gate exact TP4 pair exchange using one-shot Level Zero IPC events.

The parent brokers both the persistent IPC workspace and one IPC event pool
from every rank.  Each timed candidate cycle performs seven sequential Markov
winner exchanges without a host barrier.  Event slots are never reused; this
matches the bounded-request retirement strategy proven by the standalone
Level Zero event probe.
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
CHANNEL = 127
CHANNELS = 128
SLOTS = 3
HIDDEN = 4096
WORKSPACE_BYTES = CHANNELS * SLOTS * HIDDEN * 2 + CHANNELS * SLOTS * WORLD * 4
EXTENSION = Path(
    "/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc/vllm_xpu_kernels/_xpu_C.abi3.so"
)


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
        # Level Zero consumes imported event-pool descriptors on this driver.
        if error.errno != errno.EBADF:
            raise


def worker(
    rank: int,
    conn,
    broker_socket: str,
    init_method: str,
    warmups: int,
    iterations: int,
) -> None:
    os.environ["ZE_AFFINITY_MASK"] = "0,1,2,3"
    os.environ["ONEAPI_DEVICE_SELECTOR"] = "level_zero:*"

    import torch
    import torch.distributed as dist
    import vllm_xpu_kernels._xpu_C  # noqa: F401

    torch.xpu.set_device(rank)
    device = f"xpu:{rank}"
    anchor = torch.empty(1, dtype=torch.uint8, device=device)
    workspace = torch.ops._xpu_C.tp4_ipc_allocate_workspace(anchor)
    if workspace.numel() != WORKSPACE_BYTES:
        raise RuntimeError(f"unexpected workspace size {workspace.numel()}")

    memory_fd, allocation_offset, memory_words = torch.ops._xpu_C.tp4_ipc_export_fd(
        workspace
    )
    event_count = (warmups + iterations) * STEPS
    event_fd, event_words = torch.ops._xpu_C.tp4_ipc_event_pool_create(
        anchor, event_count
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
            anchor,
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
        device_id=torch.device(device),
    )
    local_pairs = [
        torch.empty(2, dtype=torch.float32, device=device) for _ in range(STEPS)
    ]
    gathered = [
        torch.empty(WORLD, 2, dtype=torch.float32, device=device) for _ in range(STEPS)
    ]
    reference_tokens = [
        torch.empty(1, dtype=torch.int64, device=device) for _ in range(STEPS)
    ]
    candidate_tokens = [
        torch.empty(1, dtype=torch.int64, device=device) for _ in range(STEPS)
    ]

    def set_inputs(epoch: int) -> None:
        host_pairs = []
        for step in range(STEPS):
            winner = (epoch * 3 + step * 5) % WORLD
            score = 5.0 + 0.125 * step - abs(rank - winner) * 0.75
            token = rank * 32320 + ((epoch * 97 + step * 193) % 32320)
            if epoch % 11 == 0 and rank in (1, 2):
                score = 9.0 + 0.125 * step
            host_pairs.append([score, float(token)])
        for pair, values in zip(local_pairs, host_pairs, strict=True):
            pair.copy_(torch.tensor(values, dtype=torch.float32))
        torch.xpu.synchronize()

    def control() -> None:
        for step in range(STEPS):
            dist.all_gather_into_tensor(gathered[step], local_pairs[step])
            torch.ops._xpu_C.argmax_from_gathered_pairs_out(
                gathered[step].view(1, WORLD, 2), reference_tokens[step]
            )

    def candidate(cycle: int) -> None:
        for step in range(STEPS):
            torch.ops._xpu_C.tp4_ipc_event_max_token_from_pair_out(
                local_pairs[step],
                workspace,
                candidate_tokens[step],
                rank,
                CHANNEL,
                cycle * STEPS + step,
            )

    conn.send(("ready", rank))
    if conn.recv() != "go":
        raise RuntimeError("parent did not release workers")

    exact = True
    mismatch_steps = 0
    first_mismatch: dict[str, object] | None = None
    control_us: list[float] = []
    candidate_us: list[float] = []
    total = warmups + iterations
    for cycle in range(total):
        set_inputs(cycle)
        dist.barrier()
        start = time.perf_counter_ns()
        control()
        torch.xpu.synchronize()
        control_elapsed = (time.perf_counter_ns() - start) / 1000.0

        dist.barrier()
        start = time.perf_counter_ns()
        candidate(cycle)
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
                        "cycle": cycle,
                        "step": step,
                        "reference": int(reference.item()),
                        "actual": int(actual.item()),
                        "local_pair": local_pairs[step].cpu().tolist(),
                        "gathered_pairs": gathered[step].cpu().tolist(),
                    }
        if cycle >= warmups:
            control_us.append(control_elapsed)
            candidate_us.append(candidate_elapsed)

    conn.send(
        {
            "rank": rank,
            "exact": exact,
            "mismatch_steps": mismatch_steps,
            "first_mismatch": first_mismatch,
            "control_seven_steps": summarize(control_us),
            "candidate_seven_steps": summarize(candidate_us),
            "median_saved_us": statistics.median(control_us)
            - statistics.median(candidate_us),
        }
    )
    if conn.recv() != "cleanup":
        raise RuntimeError("parent did not release cleanup")
    dist.destroy_process_group()
    torch.ops._xpu_C.tp4_ipc_event_clear(anchor)
    torch.ops._xpu_C.tp4_ipc_clear(workspace)
    for fd in peer_memory_fds:
        close_if_owned(fd)
    for fd in peer_event_fds:
        close_if_owned(fd)
    conn.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--warmups", type=int, default=12)
    parser.add_argument("--iterations", type=int, default=80)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.warmups < 0 or args.iterations <= 0:
        parser.error("warmups must be non-negative and iterations positive")
    if not EXTENSION.exists():
        parser.error(f"built extension is missing: {EXTENSION}")

    context = mp.get_context("spawn")
    parent_connections = []
    children = []
    broker_socket = f"/tmp/deepseek-v4-ipc-event-gate-{os.getpid()}.sock"
    port = 30570 + (os.getpid() % 1000)
    init_method = f"tcp://127.0.0.1:{port}"
    for rank in range(WORLD):
        parent, child = context.Pipe(duplex=True)
        process = context.Process(
            target=worker,
            args=(
                rank,
                child,
                broker_socket,
                init_method,
                args.warmups,
                args.iterations,
            ),
        )
        process.start()
        child.close()
        parent_connections.append(parent)
        children.append(process)

    for connection in parent_connections:
        message, _ = connection.recv()
        if message != "ready":
            raise RuntimeError(f"unexpected worker message {message}")
    for connection in parent_connections:
        connection.send("go")

    ranks = [connection.recv() for connection in parent_connections]
    for connection in parent_connections:
        connection.send("cleanup")
    for process in children:
        process.join(timeout=60)
        if process.exitcode != 0:
            raise RuntimeError(f"worker {process.pid} exited {process.exitcode}")

    slowest_control = max(row["control_seven_steps"]["median_us"] for row in ranks)
    slowest_candidate = max(row["candidate_seven_steps"]["median_us"] for row in ranks)
    result = {
        "schema_version": 1,
        "classification": "deepseek_v4_tp4_ipc_event_max_token_gate",
        "passed": all(row["exact"] for row in ranks)
        and slowest_candidate < slowest_control,
        "exact_all_ranks": all(row["exact"] for row in ranks),
        "world_size": WORLD,
        "sequential_steps": STEPS,
        "event_slots": (args.warmups + args.iterations) * STEPS,
        "event_reuse": False,
        "warmups": args.warmups,
        "iterations": args.iterations,
        "control": "seven XCCL pair all-gathers plus device pair selection",
        "candidate": (
            "seven direct IPC pair writes, one-shot device events, and device selection"
        ),
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
