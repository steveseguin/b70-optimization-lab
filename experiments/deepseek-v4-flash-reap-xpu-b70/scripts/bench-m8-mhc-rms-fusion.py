#!/usr/bin/env python3
"""Gate fixed M=8 MHC post/pre plus exact RMSNorm fusion on one B70."""

from __future__ import annotations

import argparse
import json
import statistics

import torch
import vllm_xpu_kernels._C  # noqa: F401
import vllm_xpu_kernels._xpu_C  # noqa: F401


TOKENS = 8
HIDDEN = 4096
HC = 4
HC3 = 24
EPS = 1e-6


def make_inputs(epoch: int) -> tuple[torch.Tensor, ...]:
    h = torch.arange(HIDDEN, dtype=torch.float32, device="xpu")
    k = torch.arange(HC * HIDDEN, dtype=torch.float32, device="xpu")
    token = torch.arange(TOKENS, dtype=torch.float32, device="xpu")[:, None]
    x = (
        torch.sin(h[None, :] * 0.00091 + token * 0.071 + epoch * 0.017)
        .mul_(1.25)
        .to(torch.bfloat16)
    )
    residual = torch.stack(
        [
            torch.cos(
                h[None, :] * (0.00037 * (i + 1))
                + token * (0.043 * (i + 1))
                + epoch * 0.011
            )
            .mul_(i + 0.75)
            .to(torch.bfloat16)
            for i in range(HC)
        ],
        dim=1,
    )
    post = (
        torch.tensor(
            [0.25, -0.5, 0.75, 1.125], dtype=torch.float32, device="xpu"
        )[None, :, None]
        .add(token[:, None, :] * 0.001)
        .add_(epoch * 0.0001)
    )
    comb = (
        torch.arange(HC * HC, dtype=torch.float32, device="xpu")
        .reshape(1, HC, HC)
        .mul_(0.017)
        .sub_(0.11)
        .add(token[:, None, :] * 0.0007)
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
    weight = (
        torch.sin(h * 0.00023 + epoch * 0.003)
        .mul_(0.21)
        .add_(1.0)
        .to(torch.bfloat16)
    )
    return x, residual, post, comb, fn, scale, base, weight


def make_outputs(inputs: tuple[torch.Tensor, ...]) -> tuple[torch.Tensor, ...]:
    x, residual, post, comb, *_ = inputs
    return (
        torch.empty_like(residual),
        torch.empty_like(post),
        torch.empty_like(comb),
        torch.empty_like(x),
    )


def reference(
    inputs: tuple[torch.Tensor, ...],
    outputs: tuple[torch.Tensor, ...],
    raw: torch.Tensor,
) -> None:
    x, residual, post, comb, fn, scale, base, weight = inputs
    residual_out, next_post, next_comb, normalized = outputs
    torch.ops._xpu_C.mhc_post_pre_m8_out(
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
        raw,
        EPS,
        EPS,
        EPS,
        2.0,
        20,
    )
    torch.ops._C.rms_norm(normalized, raw, weight, EPS)


def candidate(
    inputs: tuple[torch.Tensor, ...], outputs: tuple[torch.Tensor, ...]
) -> None:
    x, residual, post, comb, fn, scale, base, weight = inputs
    residual_out, next_post, next_comb, normalized = outputs
    torch.ops._xpu_C.mhc_post_pre_m8_rms_out(
        x,
        residual,
        post,
        comb,
        fn,
        scale,
        base,
        weight,
        residual_out,
        next_post,
        next_comb,
        normalized,
        EPS,
        EPS,
        EPS,
        EPS,
        2.0,
        20,
    )


def bits(tensor: torch.Tensor) -> torch.Tensor:
    if tensor.dtype == torch.bfloat16:
        return tensor.contiguous().view(torch.int16)
    if tensor.dtype == torch.float32:
        return tensor.contiguous().view(torch.int32)
    raise TypeError(tensor.dtype)


def timed_us(call, iterations: int) -> float:
    start = torch.xpu.Event(enable_timing=True)
    end = torch.xpu.Event(enable_timing=True)
    start.record()
    for _ in range(iterations):
        call()
    end.record()
    end.synchronize()
    return start.elapsed_time(end) * 1000.0 / iterations


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", type=int, default=0)
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--warmup", type=int, default=100)
    parser.add_argument("--batches", type=int, default=12)
    parser.add_argument("--batch-iterations", type=int, default=200)
    args = parser.parse_args()

    torch.xpu.set_device(args.device)
    mismatches = {name: 0 for name in ("residual", "post", "comb", "norm")}
    max_abs = {name: 0.0 for name in mismatches}
    names = tuple(mismatches)
    for epoch in range(1, args.epochs + 1):
        inputs = make_inputs(epoch)
        expected = make_outputs(inputs)
        actual = make_outputs(inputs)
        raw = torch.empty_like(inputs[0])
        reference(inputs, expected, raw)
        candidate(inputs, actual)
        torch.xpu.synchronize()
        for name, got, want in zip(names, actual, expected, strict=True):
            mismatch = bits(got) != bits(want)
            mismatches[name] += int(mismatch.sum().item())
            max_abs[name] = max(
                max_abs[name],
                float((got.float() - want.float()).abs().max().item()),
            )

    inputs = make_inputs(501)
    expected = make_outputs(inputs)
    actual = make_outputs(inputs)
    raw = torch.empty_like(inputs[0])
    ref_call = lambda: reference(inputs, expected, raw)
    candidate_call = lambda: candidate(inputs, actual)
    for _ in range(args.warmup):
        ref_call()
        candidate_call()
    torch.xpu.synchronize()

    reference_us: list[float] = []
    candidate_us: list[float] = []
    for batch in range(args.batches):
        if batch % 2 == 0:
            reference_us.append(timed_us(ref_call, args.batch_iterations))
            candidate_us.append(timed_us(candidate_call, args.batch_iterations))
        else:
            candidate_us.append(timed_us(candidate_call, args.batch_iterations))
            reference_us.append(timed_us(ref_call, args.batch_iterations))

    ref_median = statistics.median(reference_us)
    candidate_median = statistics.median(candidate_us)
    report = {
        "device": args.device,
        "epochs": args.epochs,
        "bit_mismatches": mismatches,
        "max_abs": max_abs,
        "reference_us_median": ref_median,
        "candidate_us_median": candidate_median,
        "saved_us_per_boundary": ref_median - candidate_median,
        "projected_saved_ms_85_boundaries": (ref_median - candidate_median)
        * 85
        / 1000.0,
        "speedup": ref_median / candidate_median,
        "reference_us_batches": reference_us,
        "candidate_us_batches": candidate_us,
        "passed": not any(mismatches.values()) and candidate_median < ref_median,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    if any(mismatches.values()):
        raise SystemExit("M=8 MHC/RMS exactness gate failed")


if __name__ == "__main__":
    main()
