#!/usr/bin/env python3
"""Gate one packed max-token XCCL reduction against pair all-gather.

DSpark's sharded Markov head needs the maximum BF16 score across four ranks,
with lowest global token ID winning exact score ties.  A BF16 order key and an
18-bit inverse token ID fit in one positive int64, allowing one MAX all-reduce
instead of gathering four float32 pairs.  The timed bundle includes packing,
the collective, decoding, and synchronization for seven sequential decisions.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
from pathlib import Path
import statistics
import time


WORLD = 4
STEPS = 7
VOCAB_PER_RANK = 32320
TOKEN_BITS = 18
TOKEN_MASK = (1 << TOKEN_BITS) - 1


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
    device = torch.device(f"xpu:{rank}")
    dist.init_process_group(
        "xccl",
        rank=rank,
        world_size=WORLD,
        init_method=init_method,
        device_id=device,
    )

    local_pairs = [torch.empty(2, dtype=torch.float32, device=device) for _ in range(STEPS)]
    gathered = [torch.empty(WORLD, 2, dtype=torch.float32, device=device) for _ in range(STEPS)]
    reference_tokens = [torch.empty(1, dtype=torch.int64, device=device) for _ in range(STEPS)]
    packed = [torch.empty(1, dtype=torch.int64, device=device) for _ in range(STEPS)]
    candidate_tokens = [torch.empty(1, dtype=torch.int64, device=device) for _ in range(STEPS)]

    def set_inputs(epoch: int) -> None:
        for step, pair in enumerate(local_pairs):
            winner = (epoch * 3 + step * 5) % WORLD
            score = 5.0 + 0.125 * step - abs(rank - winner) * 0.75
            token = rank * VOCAB_PER_RANK + ((epoch * 97 + step * 193) % VOCAB_PER_RANK)
            if epoch % 11 == 0 and rank in (1, 2):
                score = 9.0 + 0.125 * step
            if epoch % 17 == 0:
                score -= 16.0
            pair.copy_(torch.tensor([score, float(token)], dtype=torch.float32))
        torch.xpu.synchronize()

    def control() -> None:
        for step in range(STEPS):
            dist.all_gather_into_tensor(gathered[step], local_pairs[step])
            torch.ops._xpu_C.argmax_from_gathered_pairs_out(
                gathered[step].view(1, WORLD, 2), reference_tokens[step]
            )

    def candidate() -> None:
        for step in range(STEPS):
            score_bits = local_pairs[step][0].to(torch.bfloat16).view(torch.int16).to(torch.int64)
            score_bits = score_bits & 0xFFFF
            ordered = torch.where(
                (score_bits & 0x8000) != 0,
                (~score_bits) & 0xFFFF,
                score_bits ^ 0x8000,
            )
            token = local_pairs[step][1].to(torch.int64)
            packed[step].copy_((ordered << TOKEN_BITS) | (TOKEN_MASK - token))
            dist.all_reduce(packed[step], op=dist.ReduceOp.MAX)
            candidate_tokens[step].copy_(TOKEN_MASK - (packed[step] & TOKEN_MASK))

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

        for step, (reference, actual) in enumerate(zip(reference_tokens, candidate_tokens, strict=True)):
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
            "median_saved_us": statistics.median(control_us) - statistics.median(candidate_us),
        }
    )
    dist.destroy_process_group()
    conn.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--warmups", type=int, default=12)
    parser.add_argument("--iterations", type=int, default=80)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    context = mp.get_context("spawn")
    port = 31570 + (os.getpid() % 1000)
    init_method = f"tcp://127.0.0.1:{port}"
    parents = []
    children = []
    for rank in range(WORLD):
        parent, child = context.Pipe(duplex=True)
        process = context.Process(
            target=worker,
            args=(rank, child, init_method, args.warmups, args.iterations),
        )
        process.start()
        child.close()
        parents.append(parent)
        children.append(process)

    for parent in parents:
        message, _ = parent.recv()
        if message != "ready":
            raise RuntimeError(f"unexpected worker message {message}")
    for parent in parents:
        parent.send("go")
    ranks = [parent.recv() for parent in parents]
    for process in children:
        process.join(timeout=60)
        if process.exitcode != 0:
            raise RuntimeError(f"worker {process.pid} exited {process.exitcode}")

    slowest_control = max(row["control_seven_steps"]["median_us"] for row in ranks)
    slowest_candidate = max(row["candidate_seven_steps"]["median_us"] for row in ranks)
    result = {
        "schema_version": 1,
        "classification": "deepseek_v4_tp4_packed_max_allreduce_gate",
        "passed": all(row["exact"] for row in ranks) and slowest_candidate < slowest_control,
        "exact_all_ranks": all(row["exact"] for row in ranks),
        "world_size": WORLD,
        "sequential_steps": STEPS,
        "warmups": args.warmups,
        "iterations": args.iterations,
        "control": "XCCL float32 pair all-gather plus native pair selection",
        "candidate": "BF16 sortable key packing plus one XCCL int64 MAX all-reduce",
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
