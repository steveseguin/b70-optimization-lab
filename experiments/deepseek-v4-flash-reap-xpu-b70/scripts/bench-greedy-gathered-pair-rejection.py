#!/usr/bin/env python3
"""Gate fused TP-winner selection plus greedy rejection on one Intel XPU."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics

import torch
import vllm_xpu_kernels._xpu_C  # noqa: F401


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="xpu:0")
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--iterations", type=int, default=1000)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    device = torch.device(args.device)
    torch.xpu.set_device(device)
    pairs = torch.empty((8, 4, 2), device=device, dtype=torch.float32)
    draft = torch.empty(8, device=device, dtype=torch.int32)
    cu_num_logits = torch.tensor([0, 8], device=device, dtype=torch.int32)

    def old_call() -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        max_rank = pairs[:, :, 0].argmax(dim=-1, keepdim=True)
        target = pairs[:, :, 1].gather(dim=-1, index=max_rank)
        target = target.squeeze(-1).to(torch.int64)
        return torch.ops._xpu_C.greedy_rejection_from_target_tokens(
            target, draft, cu_num_logits, 7
        )

    def new_call() -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        return torch.ops._xpu_C.greedy_rejection_from_gathered_pairs(
            pairs, draft, cu_num_logits, 7
        )

    def set_case(epoch: int) -> None:
        rows = torch.arange(8, device=device, dtype=torch.float32)[:, None]
        ranks = torch.arange(4, device=device, dtype=torch.float32)[None, :]
        winner = (rows.to(torch.int64) + epoch) % 4
        values = -(rows * 0.125 + ranks * 0.25 + 3.0)
        values.scatter_(1, winner, 10.0 + rows)
        # Exercise first-rank tie behavior on every fifth epoch.
        if epoch % 5 == 0:
            values[0, 0] = 20.0
            values[0, 1] = 20.0
        indices = rows * 4096.0 + ranks * 1024.0 + float(epoch % 997)
        pairs[:, :, 0].copy_(values)
        pairs[:, :, 1].copy_(indices)

        max_rank = values.argmax(dim=-1, keepdim=True)
        target = indices.gather(dim=-1, index=max_rank).squeeze(-1).to(torch.int32)
        draft.zero_()
        draft[1:].copy_(target[:-1])
        reject_at = epoch % 8
        if reject_at < 7:
            draft[reject_at + 1] += 1

    def outputs(call) -> tuple[list[int], int, int]:
        sampled, num_sampled, num_rejected = call()
        torch.xpu.synchronize()
        count = int(num_sampled.item())
        return (
            sampled[0, :count].tolist(),
            count,
            int(num_rejected.item()),
        )

    eager_exact = 0
    for epoch in range(args.epochs):
        set_case(epoch)
        eager_exact += outputs(new_call) == outputs(old_call)

    set_case(100)
    old_graph = torch.xpu.XPUGraph()
    with torch.xpu.graph(old_graph):
        old_graph_outputs = old_call()
    new_graph = torch.xpu.XPUGraph()
    with torch.xpu.graph(new_graph):
        new_graph_outputs = new_call()

    def captured_outputs(graph, tensors) -> tuple[list[int], int, int]:
        graph.replay()
        torch.xpu.synchronize()
        sampled, num_sampled, num_rejected = tensors
        count = int(num_sampled.item())
        return (
            sampled[0, :count].tolist(),
            count,
            int(num_rejected.item()),
        )

    graph_exact = 0
    for epoch in range(args.epochs):
        set_case(1000 + epoch)
        new_result = captured_outputs(new_graph, new_graph_outputs)
        old_result = captured_outputs(old_graph, old_graph_outputs)
        graph_exact += new_result == old_result

    def timed_us(fn) -> float:
        start = torch.xpu.Event(enable_timing=True)
        end = torch.xpu.Event(enable_timing=True)
        start.record()
        for _ in range(args.iterations):
            fn()
        end.record()
        end.synchronize()
        return start.elapsed_time(end) * 1000.0 / args.iterations

    eager_old = [timed_us(old_call) for _ in range(10)]
    eager_new = [timed_us(new_call) for _ in range(10)]
    graph_old = [timed_us(old_graph.replay) for _ in range(10)]
    graph_new = [timed_us(new_graph.replay) for _ in range(10)]
    result = {
        "schema_version": 1,
        "classification": "deepseek_v4_gathered_pair_rejection_gate",
        "device_name": torch.xpu.get_device_name(device),
        "eager_gate": {"exact": eager_exact, "epochs": args.epochs},
        "graph_gate": {"exact": graph_exact, "epochs": args.epochs},
        "timing_us": {
            "eager_control_median": statistics.median(eager_old),
            "eager_candidate_median": statistics.median(eager_new),
            "graph_control_median": statistics.median(graph_old),
            "graph_candidate_median": statistics.median(graph_new),
            "eager_control_samples": eager_old,
            "eager_candidate_samples": eager_new,
            "graph_control_samples": graph_old,
            "graph_candidate_samples": graph_new,
        },
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if eager_exact == graph_exact == args.epochs else 2


if __name__ == "__main__":
    raise SystemExit(main())
