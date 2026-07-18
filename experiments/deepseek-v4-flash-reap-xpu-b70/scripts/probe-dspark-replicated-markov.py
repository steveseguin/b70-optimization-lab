#!/usr/bin/env python3
"""Four-B70 gate for replicated DSpark Markov and target heads.

The production DSpark head vocab-shards both Markov matrices.  Every one of
the seven sequential positions therefore performs a small embedding all-reduce
and a full-vocabulary logits all-gather.  This probe compares that contract
with full per-rank copies of the two 129280x256 BF16 matrices.  The replicated
path preserves the production W2 partition geometry by running four
32320-output linear operations and concatenating them in rank order.

The optional target-head lane applies the same exact partition geometry to the
real 129280x4096 shared LM head. It measures whether removing the remaining
base-logits all-gather can repay the fourfold per-rank weight read.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import statistics
import time

import torch
import torch.distributed as dist
import torch.nn.functional as F
from safetensors import safe_open
from vllm.v1.worker.gpu.spec_decode.dspark.speculator import (
    _dspark_local_markov_embed_out_kernel,
)


W1_NAME = "mtp.2.markov_head.markov_w1.weight"
W2_NAME = "mtp.2.markov_head.markov_w2.weight"
LM_HEAD_NAME = "head.weight"


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = fraction * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def summarize(values: list[float]) -> dict[str, float]:
    return {
        "min_ms": min(values),
        "p10_ms": percentile(values, 0.10),
        "median_ms": statistics.median(values),
        "mean_ms": statistics.fmean(values),
        "p90_ms": percentile(values, 0.90),
        "max_ms": max(values),
    }


def load_markov_weights(
    path: Path, device: torch.device
) -> tuple[torch.Tensor, torch.Tensor]:
    with safe_open(path, framework="pt", device="cpu") as handle:
        w1 = handle.get_tensor(W1_NAME).contiguous()
        w2 = handle.get_tensor(W2_NAME).contiguous()
    return w1.to(device), w2.to(device)


def load_lm_head(path: Path, device: torch.device) -> torch.Tensor:
    with safe_open(path, framework="pt", device="cpu") as handle:
        head = handle.get_tensor(LM_HEAD_NAME).contiguous()
    return head.to(device)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--lm-head-weights", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--steps", type=int, default=7)
    parser.add_argument("--warmups", type=int, default=8)
    parser.add_argument("--iterations", type=int, default=30)
    args = parser.parse_args()

    local_rank = int(os.environ["LOCAL_RANK"])
    rank = int(os.environ["RANK"])
    world_size = int(os.environ["WORLD_SIZE"])
    if world_size != 4:
        raise SystemExit(
            f"this fixed-geometry gate requires world_size=4, got {world_size}"
        )

    torch.xpu.set_device(local_rank)
    device = torch.device(f"xpu:{local_rank}")
    dist.init_process_group(backend="xccl")

    full_w1, full_w2 = load_markov_weights(args.weights, device)
    vocab_size, markov_rank = full_w1.shape
    if full_w2.shape != full_w1.shape or vocab_size % world_size:
        raise RuntimeError(
            f"unexpected Markov weights: w1={tuple(full_w1.shape)} "
            f"w2={tuple(full_w2.shape)} world={world_size}"
        )
    partition = vocab_size // world_size
    start = rank * partition
    end = start + partition
    local_w1 = full_w1[start:end]
    local_w2 = full_w2[start:end]
    w2_parts = tuple(full_w2[i * partition : (i + 1) * partition] for i in range(4))

    full_lm_head = None
    local_lm_head = None
    lm_head_parts = None
    if args.lm_head_weights is not None:
        full_lm_head = load_lm_head(args.lm_head_weights, device)
        if full_lm_head.shape[0] != vocab_size:
            raise RuntimeError(f"unexpected LM head shape: {tuple(full_lm_head.shape)}")
        local_lm_head = full_lm_head[start:end]
        lm_head_parts = tuple(
            full_lm_head[i * partition : (i + 1) * partition] for i in range(4)
        )

    generator = torch.Generator(device="cpu").manual_seed(0xD5A7)
    base_logits = torch.randn(
        args.steps, vocab_size, generator=generator, dtype=torch.bfloat16
    ).to(device)
    anchors = torch.tensor(
        [17, partition + 23, 2 * partition + 31, vocab_size - 19],
        dtype=torch.int64,
        device=device,
    )
    head_hidden = torch.randn(
        args.steps,
        full_lm_head.shape[1] if full_lm_head is not None else 4096,
        generator=generator,
        dtype=torch.bfloat16,
    ).to(device)

    persistent_embed = torch.empty((1, markov_rank), dtype=full_w1.dtype, device=device)
    persistent_local_bias = torch.empty(
        (1, partition), dtype=full_w2.dtype, device=device
    )
    persistent_gathered_bias = torch.empty(
        (world_size, partition), dtype=full_w2.dtype, device=device
    )
    persistent_logits = torch.empty((1, vocab_size), dtype=full_w2.dtype, device=device)
    persistent_prev = torch.empty((1,), dtype=torch.int64, device=device)

    def sharded(anchor: torch.Tensor) -> torch.Tensor:
        prev = anchor
        sampled = []
        for position in range(args.steps):
            valid = (prev >= start) & (prev < end)
            local_ids = (prev - start).clamp_(0, partition - 1)
            embed = F.embedding(local_ids, local_w1)
            embed.masked_fill_(~valid.unsqueeze(-1), 0)
            dist.all_reduce(embed, op=dist.ReduceOp.SUM)

            local_bias = F.linear(embed, local_w2)
            gathered = [torch.empty_like(local_bias) for _ in range(world_size)]
            dist.all_gather(gathered, local_bias)
            logits = base_logits[position].unsqueeze(0) + torch.cat(gathered, dim=-1)
            prev = logits.argmax(dim=-1)
            sampled.append(prev)
        return torch.stack(sampled, dim=1)

    def persistent_sharded(anchor: torch.Tensor) -> torch.Tensor:
        prev = anchor[:1]
        sampled = []
        for position in range(args.steps):
            _dspark_local_markov_embed_out_kernel[(1,)](
                prev,
                local_w1,
                persistent_embed,
                start,
                partition,
                markov_rank=markov_rank,
                BLOCK_SIZE=256,
            )
            dist.all_reduce(persistent_embed, op=dist.ReduceOp.SUM)
            torch.mm(persistent_embed, local_w2.t(), out=persistent_local_bias)
            dist.all_gather_into_tensor(persistent_gathered_bias, persistent_local_bias)
            torch.add(
                base_logits[position].unsqueeze(0),
                persistent_gathered_bias.view(1, vocab_size),
                out=persistent_logits,
            )
            torch.argmax(persistent_logits, dim=-1, out=persistent_prev)
            sampled.append(persistent_prev.clone())
            prev = persistent_prev
        return torch.stack(sampled, dim=1)

    def replicated(anchor: torch.Tensor) -> torch.Tensor:
        prev = anchor
        sampled = []
        for position in range(args.steps):
            embed = F.embedding(prev, full_w1)
            bias = torch.cat([F.linear(embed, part) for part in w2_parts], dim=-1)
            logits = base_logits[position].unsqueeze(0) + bias
            prev = logits.argmax(dim=-1)
            sampled.append(prev)
        return torch.stack(sampled, dim=1)

    def sharded_pair(anchor: torch.Tensor) -> torch.Tensor:
        """Replicated W1, sharded W2, and only a max/id exchange per step."""
        prev = anchor
        sampled = []
        local_base = base_logits[:, start:end]
        for position in range(args.steps):
            embed = F.embedding(prev, full_w1)
            local_bias = F.linear(embed, local_w2)
            local_logits = local_base[position].unsqueeze(0) + local_bias
            local_values, local_indices = local_logits.max(dim=-1)
            local_pair = torch.stack(
                [local_values.float(), (local_indices + start).float()], dim=-1
            )
            gathered_pairs = [torch.empty_like(local_pair) for _ in range(world_size)]
            dist.all_gather(gathered_pairs, local_pair)
            pairs = torch.stack(gathered_pairs, dim=1)
            winning_rank = pairs[:, :, 0].argmax(dim=-1, keepdim=True)
            prev = pairs[:, :, 1].gather(1, winning_rank).squeeze(1).to(torch.int64)
            sampled.append(prev)
        return torch.stack(sampled, dim=1)

    def sharded_lm_head() -> torch.Tensor:
        assert local_lm_head is not None
        local_logits = F.linear(head_hidden, local_lm_head)
        gathered = [torch.empty_like(local_logits) for _ in range(world_size)]
        dist.all_gather(gathered, local_logits)
        return torch.cat(gathered, dim=-1)

    def replicated_lm_head() -> torch.Tensor:
        assert lm_head_parts is not None
        return torch.cat(
            [F.linear(head_hidden, part) for part in lm_head_parts], dim=-1
        )

    # Exercise every ownership case on every rank and require exact sampled IDs.
    sharded_ids = sharded(anchors)
    replicated_ids = replicated(anchors)
    sharded_pair_ids = sharded_pair(anchors)
    persistent_ids = persistent_sharded(anchors)
    torch.xpu.synchronize()
    local_exact = (
        torch.equal(sharded_ids, replicated_ids)
        and torch.equal(sharded_ids, sharded_pair_ids)
        and torch.equal(sharded_ids[:1], persistent_ids)
    )
    exact_flags = [None for _ in range(world_size)]
    dist.all_gather_object(exact_flags, local_exact)
    if not all(exact_flags):
        raise RuntimeError(f"replicated Markov IDs differ: exact_by_rank={exact_flags}")

    lm_head_exact = None
    if full_lm_head is not None:
        sharded_logits = sharded_lm_head()
        replicated_logits = replicated_lm_head()
        torch.xpu.synchronize()
        lm_head_exact = torch.equal(sharded_logits, replicated_logits)
        lm_exact_flags = [None for _ in range(world_size)]
        dist.all_gather_object(lm_exact_flags, lm_head_exact)
        if not all(lm_exact_flags):
            raise RuntimeError(
                f"replicated LM-head logits differ: exact_by_rank={lm_exact_flags}"
            )

    def timed(function) -> list[float]:
        for _ in range(args.warmups):
            function(anchors)
        torch.xpu.synchronize()
        samples = []
        for _ in range(args.iterations):
            dist.barrier()
            torch.xpu.synchronize()
            started = time.perf_counter()
            function(anchors)
            torch.xpu.synchronize()
            samples.append((time.perf_counter() - started) * 1000.0)
        return samples

    # A-B-A controls distinguish a real saving from one-time primitive warmup.
    sharded_a = timed(sharded)
    sharded_pair_b = timed(sharded_pair)
    sharded_c = timed(sharded)
    replicated_d = timed(replicated)
    sharded_single_e = timed(lambda anchor: sharded(anchor[:1]))
    persistent_f = timed(persistent_sharded)
    sharded_single_g = timed(lambda anchor: sharded(anchor[:1]))

    lm_head_timings = None
    if full_lm_head is not None:
        lm_sharded_a = timed(lambda _: sharded_lm_head())
        lm_replicated_b = timed(lambda _: replicated_lm_head())
        lm_sharded_c = timed(lambda _: sharded_lm_head())
        lm_head_timings = {
            "exact": lm_head_exact,
            "sharded_a": summarize(lm_sharded_a),
            "replicated_b": summarize(lm_replicated_b),
            "sharded_c": summarize(lm_sharded_c),
        }
        lm_head_timings["saving_vs_faster_control_ms"] = (
            min(
                lm_head_timings["sharded_a"]["median_ms"],
                lm_head_timings["sharded_c"]["median_ms"],
            )
            - lm_head_timings["replicated_b"]["median_ms"]
        )

    local_result = {
        "rank": rank,
        "device": local_rank,
        "exact": local_exact,
        "vocab_size": vocab_size,
        "markov_rank": markov_rank,
        "steps": args.steps,
        "sharded_a": summarize(sharded_a),
        "sharded_pair_b": summarize(sharded_pair_b),
        "sharded_c": summarize(sharded_c),
        "replicated_d": summarize(replicated_d),
        "sharded_single_e": summarize(sharded_single_e),
        "persistent_f": summarize(persistent_f),
        "sharded_single_g": summarize(sharded_single_g),
        "lm_head": lm_head_timings,
    }
    local_result["saving_vs_faster_control_ms"] = (
        min(
            local_result["sharded_a"]["median_ms"],
            local_result["sharded_c"]["median_ms"],
        )
        - local_result["sharded_pair_b"]["median_ms"]
    )
    local_result["persistent_saving_vs_faster_control_ms"] = (
        min(
            local_result["sharded_single_e"]["median_ms"],
            local_result["sharded_single_g"]["median_ms"],
        )
        - local_result["persistent_f"]["median_ms"]
    )

    gathered_results = [None for _ in range(world_size)]
    dist.all_gather_object(gathered_results, local_result)
    if rank == 0:
        result = {
            "schema_version": 1,
            "classification": "dspark_replicated_markov_four_b70_component_gate",
            "weights": str(args.weights),
            "lm_head_weights": (
                str(args.lm_head_weights) if args.lm_head_weights is not None else None
            ),
            "world_size": world_size,
            "warmups": args.warmups,
            "iterations": args.iterations,
            "exact_all_ranks": all(row["exact"] for row in gathered_results),
            "ranks": gathered_results,
            "slowest_rank_saving_ms": min(
                row["saving_vs_faster_control_ms"] for row in gathered_results
            ),
            "slowest_rank_persistent_saving_ms": min(
                row["persistent_saving_vs_faster_control_ms"]
                for row in gathered_results
            ),
            "pass_threshold_ms": 0.5,
        }
        if args.lm_head_weights is not None:
            result["slowest_rank_lm_head_saving_ms"] = min(
                row["lm_head"]["saving_vs_faster_control_ms"]
                for row in gathered_results
            )
            result["slowest_rank_combined_full_replication_saving_ms"] = min(
                row["sharded_a"]["median_ms"]
                - row["replicated_d"]["median_ms"]
                + row["lm_head"]["saving_vs_faster_control_ms"]
                for row in gathered_results
            )
        result["passed"] = (
            result["exact_all_ranks"]
            and result["slowest_rank_saving_ms"] >= result["pass_threshold_ms"]
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))

    dist.barrier()
    dist.destroy_process_group()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
