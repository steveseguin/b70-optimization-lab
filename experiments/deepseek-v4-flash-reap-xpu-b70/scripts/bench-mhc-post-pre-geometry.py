#!/usr/bin/env python3
"""Benchmark the promoted H4096/HC4 M=1 fused MHC post/pre operator."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

import torch
import vllm_xpu_kernels._C  # noqa: F401
import vllm_xpu_kernels._xpu_C  # noqa: F401


HIDDEN = 4096
HC = 4
HC3 = 24
EPS = 1e-6


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


def timed_us(call, iterations: int) -> float:
    start = torch.xpu.Event(enable_timing=True)
    end = torch.xpu.Event(enable_timing=True)
    start.record()
    for _ in range(iterations):
        call()
    end.record()
    end.synchronize()
    return start.elapsed_time(end) * 1000.0 / iterations


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--warmups", type=int, default=100)
    parser.add_argument("--iterations", type=int, default=300)
    parser.add_argument("--repeats", type=int, default=11)
    parser.add_argument("--write-golden", type=Path)
    parser.add_argument("--golden", type=Path)
    parser.add_argument("--baseline-us", type=float)
    parser.add_argument("--label", default="candidate")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    torch.xpu.set_device(0)
    epoch_outputs: list[list[torch.Tensor]] = []
    for epoch in range(1, args.epochs + 1):
        inputs = make_inputs(epoch)
        outputs = make_outputs(inputs)
        run(inputs, outputs)
        torch.xpu.synchronize()
        epoch_outputs.append([value.cpu() for value in outputs])

    if args.write_golden:
        args.write_golden.parent.mkdir(parents=True, exist_ok=True)
        torch.save(epoch_outputs, args.write_golden)

    mismatches = {name: 0 for name in ("residual", "post", "comb", "input")}
    if args.golden:
        expected = torch.load(args.golden, map_location="cpu", weights_only=True)
        if len(expected) != len(epoch_outputs):
            raise ValueError("golden epoch count does not match --epochs")
        for actual_epoch, expected_epoch in zip(epoch_outputs, expected, strict=True):
            for name, actual, wanted in zip(
                mismatches, actual_epoch, expected_epoch, strict=True
            ):
                mismatches[name] += int((actual.view(torch.int16) != wanted.view(torch.int16)).sum())

    inputs = make_inputs(501)
    outputs = make_outputs(inputs)
    def call():
        return run(inputs, outputs)
    for _ in range(args.warmups):
        call()
    torch.xpu.synchronize()
    samples = [timed_us(call, args.iterations) for _ in range(args.repeats)]
    median_us = statistics.median(samples)
    saved_us = None if args.baseline_us is None else args.baseline_us - median_us
    result = {
        "classification": "deepseek_v4_mhc_post_pre_m1_geometry_microgate",
        "label": args.label,
        "device": torch.xpu.get_device_name(),
        "torch": torch.__version__,
        "epochs": args.epochs,
        "mismatches": mismatches,
        "all_bitwise": not any(mismatches.values()),
        "timing": {
            "median_us": median_us,
            "min_us": min(samples),
            "max_us": max(samples),
            "samples_us": samples,
        },
        "baseline_us": args.baseline_us,
        "saved_us_per_boundary": saved_us,
        "projected_saved_ms_per_85_boundaries": None
        if saved_us is None
        else saved_us * 85 / 1000.0,
        "gate": {
            "required_saved_us_per_boundary": 6.0,
            "passed": saved_us is not None
            and saved_us >= 6.0
            and not any(mismatches.values()),
        },
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered)
    print(rendered, end="")
    return 0 if not any(mismatches.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
