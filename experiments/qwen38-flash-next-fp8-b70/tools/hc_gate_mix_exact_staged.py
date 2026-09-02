#!/usr/bin/env python3
"""Exact staged Qwen4Exp XPU HC gate-mix candidate.

The current XPU fallback materializes two avoidable casts around every gate
mix: BF16 ``x`` is first copied to FP32 before the multiply, and the FP32 mean
is copied to BF16 afterwards.  PyTorch can perform both conversions inside
the existing multiply and mean kernels while retaining the same public Torch
operators, FP32 sigmoid, FP32 product/reduction, and final BF16 boundary.

This module is experiment-local.  It does not alter live vLLM dispatch.
"""

from __future__ import annotations

import torch


HC_COUNT = 4
HIDDEN_SIZE = 2560
HYPER_HIDDEN_SIZE = HC_COUNT * HIDDEN_SIZE


def _validate_inputs(
    x: torch.Tensor,
    gate: torch.Tensor,
    hc_count: int,
) -> int:
    if hc_count != HC_COUNT:
        raise ValueError(f"the frozen candidate requires hc_count={HC_COUNT}")
    if x.dtype != torch.bfloat16 or gate.dtype != torch.bfloat16:
        raise TypeError("x and gate must be BF16")
    if x.ndim != 2 or x.shape[0] != 1 or x.shape[1] != HYPER_HIDDEN_SIZE:
        raise ValueError(f"the frozen candidate requires x [1,{HYPER_HIDDEN_SIZE}]")
    if gate.shape != x.shape:
        raise ValueError("gate must have the same shape as x")
    if gate.device != x.device:
        raise ValueError("x and gate must be on the same device")
    if not x.is_contiguous() or not gate.is_contiguous():
        raise ValueError("x and gate must be contiguous")
    return x.shape[1] // hc_count


def torch_authority_hc_gate_mix(
    x: torch.Tensor,
    gate: torch.Tensor,
    hc_count: int = HC_COUNT,
) -> torch.Tensor:
    """Byte authority copied from the current Qwen4Exp XPU fallback."""
    hidden_size = _validate_inputs(x, gate, hc_count)
    mixed = torch.sigmoid(
        gate.float().unflatten(-1, (hc_count, hidden_size))
    ) * x.float().unflatten(-1, (hc_count, hidden_size))
    return mixed.mean(dim=-2).to(x.dtype)


def exact_staged_hc_gate_mix(
    x: torch.Tensor,
    gate: torch.Tensor,
    hc_count: int = HC_COUNT,
) -> torch.Tensor:
    """Elide only the standalone input/output cast materializations.

    Multiplying FP32 sigmoid output by BF16 ``x`` promotes ``x`` to FP32 in
    the multiply kernel.  Supplying a fresh BF16 ``out`` tensor to the FP32
    mean preserves FP32 reduction and performs the final conversion in the
    reduction kernel.  The later XPU gate must prove both transformations are
    byte-identical under eager execution and graph replay before integration.
    """
    hidden_size = _validate_inputs(x, gate, hc_count)
    sigmoid_fp32 = torch.sigmoid(gate.float().unflatten(-1, (hc_count, hidden_size)))
    # The mixed tensor remains FP32 through ordinary Torch type promotion;
    # only the separate x.float() materialization is removed.
    mixed_fp32 = sigmoid_fp32 * x.unflatten(-1, (hc_count, hidden_size))
    if mixed_fp32.dtype != torch.float32:
        raise RuntimeError("implicit gate-mix promotion did not produce FP32")
    output = torch.empty(
        (x.shape[0], hidden_size),
        dtype=x.dtype,
        device=x.device,
    )
    # ``out`` folds only the final FP32->BF16 conversion into Torch's mean.
    torch.mean(mixed_fp32, dim=-2, out=output)
    return output


__all__ = [
    "HC_COUNT",
    "HIDDEN_SIZE",
    "HYPER_HIDDEN_SIZE",
    "exact_staged_hc_gate_mix",
    "torch_authority_hc_gate_mix",
]
