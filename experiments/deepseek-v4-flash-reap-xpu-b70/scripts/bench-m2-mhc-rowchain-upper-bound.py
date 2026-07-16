#!/usr/bin/env python3
"""Gate exact M=2 MHC post/pre candidates against the generic operator."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

import torch
import vllm_xpu_kernels._C  # noqa: F401
import vllm_xpu_kernels._xpu_C  # noqa: F401


M = 2
HIDDEN = 4096
HC = 4
HC3 = 24
EPS = 1e-6


def make_inputs(epoch: int) -> tuple[torch.Tensor, ...]:
    h = torch.arange(HIDDEN, dtype=torch.float32, device="xpu")
    k = torch.arange(HC * HIDDEN, dtype=torch.float32, device="xpu")
    x = torch.stack(
        [
            torch.sin(h * (0.00091 + row * 0.00007) + epoch * 0.017)
            .mul_(1.25 + row * 0.125)
            .to(torch.bfloat16)
            for row in range(M)
        ]
    )
    residual = torch.stack(
        [
            torch.stack(
                [
                    torch.cos(
                        h * (0.00037 * (channel + 1) + row * 0.000011) + epoch * 0.011
                    )
                    .mul_(channel + 0.75 + row * 0.0625)
                    .to(torch.bfloat16)
                    for channel in range(HC)
                ]
            )
            for row in range(M)
        ]
    )
    post = (
        torch.tensor(
            [[0.25, -0.5, 0.75, 1.125], [-0.375, 0.625, 0.875, -1.0]],
            dtype=torch.float32,
            device="xpu",
        )
        .add_(epoch * 0.0001)
        .unsqueeze(-1)
    )
    comb = (
        torch.arange(M * HC * HC, dtype=torch.float32, device="xpu")
        .reshape(M, HC, HC)
        .mul_(0.017)
        .sub_(0.21)
        .add_(epoch * 0.00003)
    )
    fn = torch.stack(
        [
            torch.sin(k * (0.000013 * (j + 1)) + j * 0.071)
            .mul_(0.00035)
            .add_(torch.cos(k * 0.000009 + j * 0.019) * 0.00015)
            for j in range(HC3)
        ]
    )
    scale = torch.tensor([0.7, 0.8, 0.9], dtype=torch.float32, device="xpu")
    base = torch.linspace(-0.12, 0.13, HC3, dtype=torch.float32, device="xpu")
    return x, residual, post, comb, fn, scale, base


def reference(inputs: tuple[torch.Tensor, ...]) -> tuple[torch.Tensor, ...]:
    return torch.ops._xpu_C.mhc_fused_post_pre(
        *inputs,
        EPS,
        EPS,
        EPS,
        2.0,
        20,
    )


def make_outputs(inputs: tuple[torch.Tensor, ...]) -> tuple[torch.Tensor, ...]:
    x, residual, post, comb, *_ = inputs
    return (
        torch.empty_like(residual),
        torch.empty_like(post),
        torch.empty_like(comb),
        torch.empty_like(x),
    )


def rowchain_candidate(
    inputs: tuple[torch.Tensor, ...], outputs: tuple[torch.Tensor, ...]
) -> None:
    x, residual, post, comb, fn, scale, base = inputs
    residual_out, next_post, next_comb, layer_input = outputs
    for row in range(M):
        row_slice = slice(row, row + 1)
        torch.ops._xpu_C.mhc_post_pre_m1_out(
            x[row_slice],
            residual[row_slice],
            post[row_slice],
            comb[row_slice],
            fn,
            scale,
            base,
            residual_out[row_slice],
            next_post[row_slice],
            next_comb[row_slice],
            layer_input[row_slice],
            EPS,
            EPS,
            EPS,
            2.0,
            20,
        )


def native_candidate(
    inputs: tuple[torch.Tensor, ...], outputs: tuple[torch.Tensor, ...]
) -> None:
    x, residual, post, comb, fn, scale, base = inputs
    residual_out, next_post, next_comb, layer_input = outputs
    torch.ops._xpu_C.mhc_post_pre_m2_out(
        x,
        residual,
        post,
        comb,
        fn,
        scale,
        base,
        residual_out,
        next_post,
        next_comb,
        layer_input,
        EPS,
        EPS,
        EPS,
        2.0,
        20,
    )


def mismatch_counts(
    actual: tuple[torch.Tensor, ...], expected: tuple[torch.Tensor, ...]
) -> dict[str, int]:
    names = ("residual", "post", "comb", "input")
    return {
        name: int((got.view(torch.int16) != want.view(torch.int16)).sum().item())
        for name, got, want in zip(names, actual, expected, strict=True)
    }


def time_graph_us(graph: torch.xpu.XPUGraph, iterations: int) -> float:
    start = torch.xpu.Event(enable_timing=True)
    end = torch.xpu.Event(enable_timing=True)
    start.record()
    for _ in range(iterations):
        graph.replay()
    end.record()
    end.synchronize()
    return start.elapsed_time(end) * 1000.0 / iterations


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--graph-epochs", type=int, default=8)
    parser.add_argument("--boundaries", type=int, default=85)
    parser.add_argument("--warmups", type=int, default=20)
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--repeats", type=int, default=9)
    parser.add_argument("--device", type=int, default=0)
    parser.add_argument(
        "--candidate", choices=("rowchain", "native"), default="rowchain"
    )
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    torch.xpu.set_device(args.device)
    candidate_call = (
        native_candidate if args.candidate == "native" else rowchain_candidate
    )
    eager_mismatches = {name: 0 for name in ("residual", "post", "comb", "input")}
    for epoch in range(1, args.epochs + 1):
        inputs = make_inputs(epoch)
        expected = reference(inputs)
        actual = make_outputs(inputs)
        candidate_call(inputs, actual)
        torch.xpu.synchronize()
        for name, count in mismatch_counts(actual, expected).items():
            eager_mismatches[name] += count

    inputs = make_inputs(501)
    candidate_outputs = make_outputs(inputs)
    reference_graph = torch.xpu.XPUGraph()
    with torch.xpu.graph(reference_graph):
        for _ in range(args.boundaries):
            reference_outputs = reference(inputs)
    candidate_graph = torch.xpu.XPUGraph()
    with torch.xpu.graph(candidate_graph):
        for _ in range(args.boundaries):
            candidate_call(inputs, candidate_outputs)
    torch.xpu.synchronize()

    graph_mismatches = {name: 0 for name in eager_mismatches}
    for epoch in range(args.graph_epochs):
        changed = make_inputs(701 + epoch)
        for destination, source in zip(inputs, changed, strict=True):
            destination.copy_(source)
        reference_graph.replay()
        torch.xpu.synchronize()
        expected = tuple(value.clone() for value in reference_outputs)
        candidate_graph.replay()
        torch.xpu.synchronize()
        for name, count in mismatch_counts(candidate_outputs, expected).items():
            graph_mismatches[name] += count

    for _ in range(args.warmups):
        reference_graph.replay()
        candidate_graph.replay()
    torch.xpu.synchronize()
    reference_samples = [
        time_graph_us(reference_graph, args.iterations) for _ in range(args.repeats)
    ]
    candidate_samples = [
        time_graph_us(candidate_graph, args.iterations) for _ in range(args.repeats)
    ]
    reference_us = statistics.median(reference_samples)
    candidate_us = statistics.median(candidate_samples)
    saved_us = reference_us - candidate_us
    all_bitwise = not any(eager_mismatches.values()) and not any(
        graph_mismatches.values()
    )
    result = {
        "classification": "deepseek_v4_m2_mhc_single_kernel_microgate"
        if args.candidate == "native"
        else "deepseek_v4_m2_mhc_two_m1_calls_upper_bound",
        "candidate": args.candidate,
        "device_index": args.device,
        "device": torch.xpu.get_device_name(),
        "torch": torch.__version__,
        "epochs": args.epochs,
        "graph_epochs": args.graph_epochs,
        "boundaries": args.boundaries,
        "eager_mismatches": eager_mismatches,
        "graph_mismatches": graph_mismatches,
        "all_bitwise": all_bitwise,
        "timing": {
            "reference_us_per_chain": reference_us,
            "candidate_us_per_chain": candidate_us,
            "saved_us_per_chain": saved_us,
            "saved_us_per_boundary": saved_us / args.boundaries,
            "reference_samples_us": reference_samples,
            "candidate_samples_us": candidate_samples,
        },
        "gate": {
            "required_saved_us_per_chain": 500.0,
            "passed": all_bitwise and saved_us >= 500.0,
        },
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered)
    print(rendered, end="")
    return 0 if all_bitwise else 1


if __name__ == "__main__":
    raise SystemExit(main())
