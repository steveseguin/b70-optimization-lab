#!/usr/bin/env python3
"""Gate native BF16 local-vocabulary argmax and pair packing on one XPU."""

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
    parser.add_argument("--rows", type=int, default=8)
    parser.add_argument("--vocab", type=int, default=32320)
    parser.add_argument("--valid-vocab", type=int, default=32320)
    parser.add_argument("--vocab-start", type=int, default=96960)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    device = torch.device(args.device)
    torch.xpu.set_device(device)
    logits = torch.empty(
        (args.rows, args.vocab), device=device, dtype=torch.bfloat16
    )

    def control() -> torch.Tensor:
        values, indices = logits[:, : args.valid_vocab].max(dim=-1)
        return torch.stack(
            [values.float(), (indices + args.vocab_start).float()], dim=-1
        )

    def candidate() -> torch.Tensor:
        return torch.ops._xpu_C.sharded_argmax_pair(
            logits, args.vocab_start, args.valid_vocab
        )

    def set_case(epoch: int) -> None:
        logits.fill_(-32.0)
        rows = torch.arange(args.rows, device=device, dtype=torch.int64)
        indices = (rows * 4051 + epoch * 97) % args.valid_vocab
        values = (rows.float() * 0.25 + 4.0).to(torch.bfloat16)
        logits[rows, indices] = values
        if epoch % 5 == 0:
            logits[0, 3] = torch.tensor(12.0, device=device, dtype=torch.bfloat16)
            logits[0, 19] = torch.tensor(12.0, device=device, dtype=torch.bfloat16)
        if args.valid_vocab < args.vocab:
            logits[:, args.valid_vocab :].fill_(64.0)

    def tensor_equal(lhs: torch.Tensor, rhs: torch.Tensor) -> bool:
        torch.xpu.synchronize()
        return bool(torch.equal(lhs, rhs))

    eager_exact = 0
    for epoch in range(args.epochs):
        set_case(epoch)
        eager_exact += tensor_equal(candidate(), control())

    set_case(100)
    control_graph = torch.xpu.XPUGraph()
    with torch.xpu.graph(control_graph):
        control_output = control()
    candidate_graph = torch.xpu.XPUGraph()
    with torch.xpu.graph(candidate_graph):
        candidate_output = candidate()

    graph_exact = 0
    for epoch in range(args.epochs):
        set_case(1000 + epoch)
        candidate_graph.replay()
        control_graph.replay()
        graph_exact += tensor_equal(candidate_output, control_output)

    def timed_us(fn) -> float:
        start = torch.xpu.Event(enable_timing=True)
        end = torch.xpu.Event(enable_timing=True)
        start.record()
        for _ in range(args.iterations):
            fn()
        end.record()
        end.synchronize()
        return start.elapsed_time(end) * 1000.0 / args.iterations

    eager_control = [timed_us(control) for _ in range(10)]
    eager_candidate = [timed_us(candidate) for _ in range(10)]
    graph_control = [timed_us(control_graph.replay) for _ in range(10)]
    graph_candidate = [timed_us(candidate_graph.replay) for _ in range(10)]
    result = {
        "schema_version": 1,
        "classification": "deepseek_v4_sharded_argmax_pair_gate",
        "device_name": torch.xpu.get_device_name(device),
        "shape": [args.rows, args.vocab],
        "valid_vocab": args.valid_vocab,
        "vocab_start": args.vocab_start,
        "eager_gate": {"exact": eager_exact, "epochs": args.epochs},
        "graph_gate": {"exact": graph_exact, "epochs": args.epochs},
        "timing_us": {
            "eager_control_median": statistics.median(eager_control),
            "eager_candidate_median": statistics.median(eager_candidate),
            "graph_control_median": statistics.median(graph_control),
            "graph_candidate_median": statistics.median(graph_candidate),
            "eager_control_samples": eager_control,
            "eager_candidate_samples": eager_candidate,
            "graph_control_samples": graph_control,
            "graph_candidate_samples": graph_candidate,
        },
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if eager_exact == graph_exact == args.epochs else 2


if __name__ == "__main__":
    raise SystemExit(main())
