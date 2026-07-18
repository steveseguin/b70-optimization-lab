#!/usr/bin/env python3
"""Gate the native fixed-M8 target-token rejection transaction on one B70."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics

import torch
import vllm_xpu_kernels  # noqa: F401

from vllm.v1.worker.gpu.spec_decode.rejection_sampler_utils import (
    greedy_rejection_from_target_tokens,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="xpu:0")
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--iterations", type=int, default=1000)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    device = torch.device(args.device)
    torch.xpu.set_device(device)
    target = torch.empty(8, device=device, dtype=torch.int64)
    draft = torch.empty(8, device=device, dtype=torch.int64)
    cu_num_logits = torch.tensor([0, 8], device=device, dtype=torch.int32)

    def set_case(epoch: int) -> list[int]:
        target.copy_(torch.arange(8, device=device, dtype=torch.int64) + epoch * 17)
        draft.zero_()
        draft[1:].copy_(target[:-1])
        reject_at = epoch % 8
        if reject_at < 7:
            draft[reject_at + 1] += 1
            return draft[1 : reject_at + 1].tolist() + [int(target[reject_at])]
        return draft[1:].tolist() + [int(target[-1])]

    def call() -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        return greedy_rejection_from_target_tokens(target, draft, cu_num_logits, 7)

    def exact(sampled: torch.Tensor, count: torch.Tensor, expected: list[int]) -> bool:
        torch.xpu.synchronize()
        num_sampled = int(count.item())
        return sampled[0, :num_sampled].tolist() == expected

    eager_exact = 0
    for epoch in range(args.epochs):
        expected = set_case(epoch)
        sampled, count, _ = call()
        eager_exact += exact(sampled, count, expected)

    set_case(100)
    graph = torch.xpu.XPUGraph()
    with torch.xpu.graph(graph):
        graph_sampled, graph_count, _ = call()
    graph_exact = 0
    for epoch in range(args.epochs):
        expected = set_case(1000 + epoch)
        graph.replay()
        graph_exact += exact(graph_sampled, graph_count, expected)

    def timed_us(fn) -> float:
        start = torch.xpu.Event(enable_timing=True)
        end = torch.xpu.Event(enable_timing=True)
        start.record()
        for _ in range(args.iterations):
            fn()
        end.record()
        end.synchronize()
        return start.elapsed_time(end) * 1000.0 / args.iterations

    eager_us = [timed_us(call) for _ in range(10)]
    graph_us = [timed_us(graph.replay) for _ in range(10)]
    result = {
        "schema_version": 1,
        "classification": "deepseek_v4_native_target_token_rejection_gate",
        "device_name": torch.xpu.get_device_name(device),
        "eager_gate": {"exact": eager_exact, "epochs": args.epochs},
        "graph_gate": {"exact": graph_exact, "epochs": args.epochs},
        "timing_us": {
            "eager_median": statistics.median(eager_us),
            "graph_median": statistics.median(graph_us),
            "eager_samples": eager_us,
            "graph_samples": graph_us,
        },
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if eager_exact == graph_exact == args.epochs else 2


if __name__ == "__main__":
    raise SystemExit(main())
