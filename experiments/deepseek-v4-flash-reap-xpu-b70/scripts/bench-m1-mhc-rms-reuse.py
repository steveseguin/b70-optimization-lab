#!/usr/bin/env python3
"""Four-card-ready exact/timing gate for M=1 MHC RMS-reduction reuse."""

from __future__ import annotations

import argparse
import json
import os
import statistics
from pathlib import Path

import torch
import vllm_xpu_kernels._C  # noqa: F401
import vllm_xpu_kernels._xpu_C  # noqa: F401


HIDDEN = 4096
HC = 4
HC3 = 24
EPS = 1e-6
FLAG = "VLLM_XPU_V4_MHC_REUSE_RMS_REDUCTION"


def make_inputs(epoch: int) -> tuple[torch.Tensor, ...]:
    h = torch.arange(HIDDEN, dtype=torch.float32, device="xpu")
    k = torch.arange(HC * HIDDEN, dtype=torch.float32, device="xpu")
    x = (
        torch.sin(h * 0.00091 + epoch * 0.017)
        .mul_(1.25)
        .to(torch.bfloat16)
        .unsqueeze(0)
    )
    residual = torch.stack(
        [
            torch.cos(h * (0.00037 * (i + 1)) + epoch * 0.011)
            .mul_(i + 0.75)
            .to(torch.bfloat16)
            for i in range(HC)
        ]
    ).unsqueeze(0)
    post = (
        torch.tensor(
            [0.25, -0.5, 0.75, 1.125], dtype=torch.float32, device="xpu"
        )
        .add_(epoch * 0.0001)
        .reshape(1, HC, 1)
    )
    comb = (
        torch.arange(HC * HC, dtype=torch.float32, device="xpu")
        .reshape(1, HC, HC)
        .mul_(0.017)
        .sub_(0.11)
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


def make_outputs(inputs: tuple[torch.Tensor, ...]) -> tuple[torch.Tensor, ...]:
    x, residual, post, comb, *_ = inputs
    return (
        torch.empty_like(residual),
        torch.empty_like(post),
        torch.empty_like(comb),
        torch.empty_like(x),
    )


def run(inputs: tuple[torch.Tensor, ...], outputs: tuple[torch.Tensor, ...]) -> None:
    x, residual, post, comb, fn, scale, base = inputs
    residual_out, next_post, next_comb, layer_input = outputs
    torch.ops._xpu_C.mhc_post_pre_m1_out(
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


def set_candidate(enabled: bool) -> None:
    if enabled:
        os.environ[FLAG] = "1"
    else:
        os.environ.pop(FLAG, None)


def bits(value: torch.Tensor) -> torch.Tensor:
    if value.dtype == torch.bfloat16:
        return value.contiguous().view(torch.int16)
    if value.dtype == torch.float32:
        return value.contiguous().view(torch.int32)
    raise TypeError(value.dtype)


def compare(
    expected: tuple[torch.Tensor, ...], actual: tuple[torch.Tensor, ...]
) -> dict[str, int]:
    names = ("residual", "post", "comb", "input")
    return {
        name: int((bits(got) != bits(want)).sum().item())
        for name, got, want in zip(names, actual, expected, strict=True)
    }


def accumulate(total: dict[str, int], row: dict[str, int]) -> None:
    for name, count in row.items():
        total[name] += count


def timed_graph_us(graph: torch.xpu.XPUGraph, iterations: int) -> float:
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
    parser.add_argument("--device", type=int, required=True)
    parser.add_argument("--eager-epochs", type=int, default=40)
    parser.add_argument("--graph-epochs", type=int, default=40)
    parser.add_argument("--warmups", type=int, default=40)
    parser.add_argument("--iterations", type=int, default=200)
    parser.add_argument("--repeats", type=int, default=9)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    torch.xpu.set_device(args.device)
    eager_mismatches = {name: 0 for name in ("residual", "post", "comb", "input")}
    eager_cases_exact = 0
    for epoch in range(1, args.eager_epochs + 1):
        inputs = make_inputs(epoch)
        expected = make_outputs(inputs)
        actual = make_outputs(inputs)
        set_candidate(False)
        run(inputs, expected)
        set_candidate(True)
        run(inputs, actual)
        torch.xpu.synchronize()
        row = compare(expected, actual)
        accumulate(eager_mismatches, row)
        eager_cases_exact += not any(row.values())

    persistent = make_inputs(1001)
    expected = make_outputs(persistent)
    actual = make_outputs(persistent)
    set_candidate(False)
    reference_graph = torch.xpu.XPUGraph()
    with torch.xpu.graph(reference_graph):
        run(persistent, expected)
    set_candidate(True)
    candidate_graph = torch.xpu.XPUGraph()
    with torch.xpu.graph(candidate_graph):
        run(persistent, actual)

    graph_mismatches = {name: 0 for name in eager_mismatches}
    graph_cases_exact = 0
    for epoch in range(2001, 2001 + args.graph_epochs):
        changed = make_inputs(epoch)
        for stable, fresh in zip(persistent, changed, strict=True):
            stable.copy_(fresh)
        torch.xpu.synchronize()
        reference_graph.replay()
        candidate_graph.replay()
        torch.xpu.synchronize()
        row = compare(expected, actual)
        accumulate(graph_mismatches, row)
        graph_cases_exact += not any(row.values())

    for _ in range(args.warmups):
        reference_graph.replay()
        candidate_graph.replay()
    torch.xpu.synchronize()
    reference_us: list[float] = []
    candidate_us: list[float] = []
    for repeat in range(args.repeats):
        if repeat % 2 == 0:
            reference_us.append(timed_graph_us(reference_graph, args.iterations))
            candidate_us.append(timed_graph_us(candidate_graph, args.iterations))
        else:
            candidate_us.append(timed_graph_us(candidate_graph, args.iterations))
            reference_us.append(timed_graph_us(reference_graph, args.iterations))

    reference_median = statistics.median(reference_us)
    candidate_median = statistics.median(candidate_us)
    saved_us = reference_median - candidate_median
    all_exact = not any(eager_mismatches.values()) and not any(
        graph_mismatches.values()
    )
    report = {
        "schema_version": 1,
        "classification": "deepseek_v4_m1_mhc_rms_reduction_reuse_gate",
        "device": args.device,
        "device_name": torch.xpu.get_device_name(),
        "flag": f"{FLAG}=1",
        "default_off": True,
        "launch_count_before": 85,
        "launch_count_after": 85,
        "eager": {
            "cases_exact": eager_cases_exact,
            "cases_total": args.eager_epochs,
            "bit_mismatches": eager_mismatches,
        },
        "fixed_address_graph": {
            "cases_exact": graph_cases_exact,
            "cases_total": args.graph_epochs,
            "bit_mismatches": graph_mismatches,
        },
        "timing": {
            "reference_median_us_per_boundary": reference_median,
            "candidate_median_us_per_boundary": candidate_median,
            "saved_us_per_boundary": saved_us,
            "projected_saved_ms_per_token_85_boundaries": saved_us * 85 / 1000.0,
            "reference_samples_us": reference_us,
            "candidate_samples_us": candidate_us,
        },
        "gate": {
            "required_saved_ms_per_token": 0.30,
            "exact": all_exact,
            "passed": all_exact and saved_us * 85 / 1000.0 >= 0.30,
        },
    }
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(rendered)
    print(rendered, end="")
    return 0 if all_exact else 1


if __name__ == "__main__":
    raise SystemExit(main())
