#!/usr/bin/env python3
"""Gate DSpark local bias+argmax and compact TP-winner native kernels."""

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
    vocab = 32320
    vocab_start = 96960
    base = torch.empty((1, vocab), device=device, dtype=torch.bfloat16)
    bias = torch.empty_like(base)
    summed = torch.empty_like(base)
    local_pair = torch.empty((1, 2), device=device, dtype=torch.float32)
    gathered = torch.empty((1, 4, 2), device=device, dtype=torch.float32)
    output_token = torch.empty((1,), device=device, dtype=torch.int64)

    def local_control() -> torch.Tensor:
        torch.add(base, bias, out=summed)
        values, indices = summed.max(dim=-1)
        return torch.stack(
            [values.float(), (indices + vocab_start).float()], dim=-1
        )

    def local_candidate() -> torch.Tensor:
        torch.ops._xpu_C.dspark_local_bias_argmax_pair_out(
            base, bias, local_pair, vocab_start
        )
        return local_pair

    def global_control() -> torch.Tensor:
        rank = gathered[:, :, 0].argmax(dim=-1, keepdim=True)
        return gathered[:, :, 1].gather(dim=-1, index=rank).squeeze(-1).to(torch.int64)

    def global_candidate() -> torch.Tensor:
        torch.ops._xpu_C.argmax_from_gathered_pairs_out(gathered, output_token)
        return output_token

    def set_case(epoch: int) -> None:
        generator = torch.Generator(device=device).manual_seed(1000 + epoch)
        base.copy_(torch.randn(base.shape, generator=generator, device=device).to(torch.bfloat16))
        bias.copy_(torch.randn(bias.shape, generator=generator, device=device).to(torch.bfloat16))
        peak = (epoch * 811) % vocab
        base[0, peak] = torch.tensor(32.0, device=device, dtype=torch.bfloat16)
        if epoch % 5 == 0:
            base[0, 3] = torch.tensor(40.0, device=device, dtype=torch.bfloat16)
            base[0, 19] = torch.tensor(40.0, device=device, dtype=torch.bfloat16)
            bias[0, 3] = 0
            bias[0, 19] = 0
        gathered.copy_(
            torch.randn(gathered.shape, generator=generator, device=device)
        )
        gathered[:, :, 1].copy_(
            torch.tensor(
                [[vocab_start, 1024.0, 2048.0, 3072.0]],
                device=device,
                dtype=torch.float32,
            )
        )
        winner = epoch % 4
        gathered[0, winner, 0] = 16.0
        if epoch % 7 == 0:
            gathered[0, 0, 0] = 20.0
            gathered[0, 1, 0] = 20.0

    def equal(lhs: torch.Tensor, rhs: torch.Tensor) -> bool:
        torch.xpu.synchronize()
        return bool(torch.equal(lhs, rhs))

    local_eager_exact = 0
    global_eager_exact = 0
    for epoch in range(args.epochs):
        set_case(epoch)
        local_eager_exact += equal(local_candidate(), local_control())
        global_eager_exact += equal(global_candidate(), global_control())

    set_case(100)
    local_control_graph = torch.xpu.XPUGraph()
    with torch.xpu.graph(local_control_graph):
        local_control_output = local_control()
    local_candidate_graph = torch.xpu.XPUGraph()
    with torch.xpu.graph(local_candidate_graph):
        local_candidate_output = local_candidate()
    global_control_graph = torch.xpu.XPUGraph()
    with torch.xpu.graph(global_control_graph):
        global_control_output = global_control()
    global_candidate_graph = torch.xpu.XPUGraph()
    with torch.xpu.graph(global_candidate_graph):
        global_candidate_output = global_candidate()

    local_graph_exact = 0
    global_graph_exact = 0
    for epoch in range(args.epochs):
        set_case(1000 + epoch)
        local_candidate_graph.replay()
        local_control_graph.replay()
        global_candidate_graph.replay()
        global_control_graph.replay()
        local_graph_exact += equal(local_candidate_output, local_control_output)
        global_graph_exact += equal(global_candidate_output, global_control_output)

    def timed_us(fn) -> float:
        start = torch.xpu.Event(enable_timing=True)
        end = torch.xpu.Event(enable_timing=True)
        start.record()
        for _ in range(args.iterations):
            fn()
        end.record()
        end.synchronize()
        return start.elapsed_time(end) * 1000.0 / args.iterations

    def samples(control, candidate, control_graph, candidate_graph) -> dict[str, object]:
        eager_control = [timed_us(control) for _ in range(10)]
        eager_candidate = [timed_us(candidate) for _ in range(10)]
        graph_control = [timed_us(control_graph.replay) for _ in range(10)]
        graph_candidate = [timed_us(candidate_graph.replay) for _ in range(10)]
        return {
            "eager_control_median": statistics.median(eager_control),
            "eager_candidate_median": statistics.median(eager_candidate),
            "graph_control_median": statistics.median(graph_control),
            "graph_candidate_median": statistics.median(graph_candidate),
            "eager_control_samples": eager_control,
            "eager_candidate_samples": eager_candidate,
            "graph_control_samples": graph_control,
            "graph_candidate_samples": graph_candidate,
        }

    result = {
        "schema_version": 1,
        "classification": "deepseek_v4_dspark_sharded_markov_argmax_gate",
        "device_name": torch.xpu.get_device_name(device),
        "local_gate": {
            "eager_exact": local_eager_exact,
            "graph_exact": local_graph_exact,
            "epochs": args.epochs,
            "timing_us": samples(
                local_control,
                local_candidate,
                local_control_graph,
                local_candidate_graph,
            ),
        },
        "global_gate": {
            "eager_exact": global_eager_exact,
            "graph_exact": global_graph_exact,
            "epochs": args.epochs,
            "timing_us": samples(
                global_control,
                global_candidate,
                global_control_graph,
                global_candidate_graph,
            ),
        },
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    exact = [
        local_eager_exact,
        local_graph_exact,
        global_eager_exact,
        global_graph_exact,
    ]
    return 0 if all(value == args.epochs for value in exact) else 2


if __name__ == "__main__":
    raise SystemExit(main())
