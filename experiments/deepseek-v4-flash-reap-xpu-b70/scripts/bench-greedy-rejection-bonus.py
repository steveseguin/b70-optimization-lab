#!/usr/bin/env python3
"""Gate the fixed M=8 greedy rejection/bonus transaction on one B70."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics

import torch

from vllm.v1.worker.gpu.spec_decode.rejection_sampler_utils import (
    greedy_rejection_sample,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="xpu:0")
    parser.add_argument("--vocab-size", type=int, default=129280)
    parser.add_argument("--spec-steps", type=int, default=7)
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--warmup", type=int, default=100)
    parser.add_argument("--batches", type=int, default=10)
    parser.add_argument("--batch-iterations", type=int, default=200)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if args.spec_steps != 7:
        raise SystemExit("this production gate requires exactly seven draft steps")
    torch.xpu.set_device(args.device)
    device = torch.device(args.device)
    logits = torch.empty(
        (args.spec_steps + 1, args.vocab_size),
        device=device,
        dtype=torch.float32,
    )
    draft_sampled = torch.empty(
        (args.spec_steps + 1,), device=device, dtype=torch.int64
    )
    cu_num_logits = torch.tensor(
        [0, args.spec_steps + 1], device=device, dtype=torch.int32
    )
    expanded_idx_mapping = torch.zeros(
        (args.spec_steps + 1,), device=device, dtype=torch.int32
    )
    expanded_local_pos = torch.arange(
        args.spec_steps + 1, device=device, dtype=torch.int32
    )
    temperature = torch.zeros((1,), device=device, dtype=torch.float32)

    def candidate() -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        return greedy_rejection_sample(
            logits,
            draft_sampled,
            cu_num_logits,
            expanded_idx_mapping,
            expanded_local_pos,
            temperature,
            args.spec_steps,
        )

    def set_epoch(epoch: int) -> tuple[list[int], int, int]:
        generator = torch.Generator(device=device)
        generator.manual_seed(20260718 + epoch)
        logits.copy_(
            torch.randn(
                logits.shape,
                generator=generator,
                device=device,
                dtype=logits.dtype,
            )
        )
        target = logits.argmax(dim=-1)
        draft_sampled.zero_()
        draft_sampled[1:].copy_(target[:-1])
        reject_at = epoch % (args.spec_steps + 1)
        if reject_at < args.spec_steps:
            draft_sampled[reject_at + 1] = (target[reject_at] + 1) % args.vocab_size
            expected = target[: reject_at + 1].tolist()
            expected[:reject_at] = draft_sampled[1 : reject_at + 1].tolist()
            num_sampled = reject_at + 1
        else:
            expected = draft_sampled[1:].tolist() + [int(target[-1].item())]
            num_sampled = args.spec_steps + 1
        return expected, num_sampled, args.spec_steps + 1 - num_sampled

    def compare(epoch: int) -> dict[str, int | bool]:
        expected, expected_num, expected_rejected = set_epoch(epoch)
        sampled, num_sampled, num_rejected = candidate()
        torch.xpu.synchronize()
        actual_num = int(num_sampled.item())
        actual = sampled[0, :actual_num].tolist()
        return {
            "epoch": epoch,
            "exact": actual == expected,
            "expected_num_sampled": expected_num,
            "actual_num_sampled": actual_num,
            "expected_num_rejected": expected_rejected,
            "actual_num_rejected": int(num_rejected.item()),
        }

    eager_rows = [compare(epoch) for epoch in range(args.epochs)]

    set_epoch(args.epochs + 1)
    graph = torch.xpu.XPUGraph()
    with torch.xpu.graph(graph):
        graph_sampled, graph_num_sampled, graph_num_rejected = candidate()
    graph.replay()
    torch.xpu.synchronize()

    graph_rows = []
    for epoch in range(args.epochs):
        expected, expected_num, expected_rejected = set_epoch(1000 + epoch)
        graph.replay()
        torch.xpu.synchronize()
        actual_num = int(graph_num_sampled.item())
        graph_rows.append(
            {
                "epoch": epoch,
                "exact": graph_sampled[0, :actual_num].tolist() == expected,
                "expected_num_sampled": expected_num,
                "actual_num_sampled": actual_num,
                "expected_num_rejected": expected_rejected,
                "actual_num_rejected": int(graph_num_rejected.item()),
            }
        )

    def timed_us(call) -> float:
        start = torch.xpu.Event(enable_timing=True)
        end = torch.xpu.Event(enable_timing=True)
        start.record()
        for _ in range(args.batch_iterations):
            call()
        end.record()
        end.synchronize()
        return start.elapsed_time(end) * 1000.0 / args.batch_iterations

    for _ in range(args.warmup):
        candidate()
    torch.xpu.synchronize()
    eager_us = [timed_us(candidate) for _ in range(args.batches)]
    graph_us = [timed_us(graph.replay) for _ in range(args.batches)]

    def rows_exact(rows: list[dict[str, int | bool]]) -> bool:
        return all(
            row["exact"]
            and row["expected_num_sampled"] == row["actual_num_sampled"]
            and row["expected_num_rejected"] == row["actual_num_rejected"]
            for row in rows
        )

    result = {
        "schema_version": 1,
        "classification": "deepseek_v4_greedy_rejection_bonus_microgate",
        "device": args.device,
        "device_name": torch.xpu.get_device_name(device),
        "shape": {
            "num_logits": args.spec_steps + 1,
            "vocab_size": args.vocab_size,
            "spec_steps": args.spec_steps,
        },
        "eager_gate": {
            "epochs": len(eager_rows),
            "exact_epochs": sum(row["exact"] for row in eager_rows),
            "passes": rows_exact(eager_rows),
        },
        "graph_gate": {
            "epochs": len(graph_rows),
            "exact_epochs": sum(row["exact"] for row in graph_rows),
            "passes": rows_exact(graph_rows),
        },
        "timing": {
            "warmup": args.warmup,
            "batch_iterations": args.batch_iterations,
            "eager_us": {
                "median": statistics.median(eager_us),
                "samples": eager_us,
            },
            "graph_us": {
                "median": statistics.median(graph_us),
                "samples": graph_us,
            },
        },
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if rows_exact(eager_rows) and rows_exact(graph_rows) else 2


if __name__ == "__main__":
    raise SystemExit(main())
