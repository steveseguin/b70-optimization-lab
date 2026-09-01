#!/usr/bin/env python3
"""Exact staged Qwen4Exp HC combine+norm cast-elision candidate.

This experiment-local module deliberately mirrors the current XPU Torch
fallback.  It does not replace sigmoid, reduction, rsqrt, multiplication, or
the materialized BF16 boundary between combine and normalization.  Its sole
runtime treatment is to hoist the immutable
``1.0 + norm_weight.float()`` affine out of every decode invocation.

The narrow treatment gives us a trustworthy first rung for a later exact HC
fusion.  More aggressive Triton implementations are not used here: retained
component evidence shows that their arithmetic is not byte-identical to the
Torch authority.
"""

from __future__ import annotations

import torch


HC_COUNT = 4
HIDDEN_SIZE = 2560
HYPER_HIDDEN_SIZE = HC_COUNT * HIDDEN_SIZE


def _validate_runtime_inputs(
    residual: torch.Tensor,
    block_output: torch.Tensor,
    injection_logits: torch.Tensor,
    norm_weight: torch.Tensor | None = None,
    norm_affine_fp32: torch.Tensor | None = None,
    *,
    hc_count: int,
) -> int:
    if residual.dtype != torch.bfloat16:
        raise TypeError("residual must be BF16")
    if block_output.dtype != residual.dtype or injection_logits.dtype != residual.dtype:
        raise TypeError("all dynamic HC inputs must share BF16 dtype")
    if residual.ndim != 2 or residual.shape[0] != 1:
        raise ValueError("the frozen component candidate requires residual [1,D]")
    if hc_count != HC_COUNT:
        raise ValueError(f"the frozen component candidate requires hc_count={HC_COUNT}")
    if residual.shape[1] != HYPER_HIDDEN_SIZE:
        raise ValueError(
            f"the frozen component candidate requires D={HYPER_HIDDEN_SIZE}"
        )
    hidden_size = residual.shape[1] // hc_count
    if block_output.shape != (1, hidden_size):
        raise ValueError(f"block_output must be [1,{hidden_size}]")
    if injection_logits.shape != (1, hc_count):
        raise ValueError(f"injection_logits must be [1,{hc_count}]")
    for name, tensor in (
        ("residual", residual),
        ("block_output", block_output),
        ("injection_logits", injection_logits),
    ):
        if not tensor.is_contiguous():
            raise ValueError(f"{name} must be contiguous")
        if tensor.device != residual.device:
            raise ValueError("all dynamic HC inputs must share one device")
    if norm_weight is not None:
        if norm_weight.shape != (residual.shape[1],):
            raise ValueError("norm_weight must have one value per HC element")
        if norm_weight.dtype != torch.bfloat16:
            raise TypeError("norm_weight must be BF16")
        if norm_weight.device != residual.device or not norm_weight.is_contiguous():
            raise ValueError("norm_weight must be contiguous on the input device")
    if norm_affine_fp32 is not None:
        if norm_affine_fp32.shape != (residual.shape[1],):
            raise ValueError("norm_affine_fp32 must have one value per HC element")
        if norm_affine_fp32.dtype != torch.float32:
            raise TypeError("norm_affine_fp32 must be FP32")
        if (
            norm_affine_fp32.device != residual.device
            or not norm_affine_fp32.is_contiguous()
        ):
            raise ValueError("norm_affine_fp32 must be contiguous on the input device")
    return hidden_size


def build_exact_norm_affine(norm_weight: torch.Tensor) -> torch.Tensor:
    """Create the immutable affine using the authority's exact operations."""
    if norm_weight.dtype != torch.bfloat16 or norm_weight.ndim != 1:
        raise TypeError("norm_weight must be a one-dimensional BF16 tensor")
    if norm_weight.numel() != HYPER_HIDDEN_SIZE or not norm_weight.is_contiguous():
        raise ValueError(
            f"norm_weight must be contiguous with {HYPER_HIDDEN_SIZE} elements"
        )
    return (1.0 + norm_weight.float()).contiguous()


def validate_exact_norm_affine(
    norm_weight: torch.Tensor, norm_affine_fp32: torch.Tensor
) -> None:
    """Fail closed if a cached affine does not equal the Torch authority."""
    expected = build_exact_norm_affine(norm_weight)
    if (
        norm_affine_fp32.dtype != torch.float32
        or norm_affine_fp32.shape != expected.shape
        or norm_affine_fp32.device != expected.device
        or not norm_affine_fp32.is_contiguous()
        or not torch.equal(norm_affine_fp32, expected)
    ):
        raise ValueError("cached norm affine differs from 1 + weight.float()")


def torch_authority_hc_combine_norm(
    residual: torch.Tensor,
    block_output: torch.Tensor,
    injection_logits: torch.Tensor,
    norm_weight: torch.Tensor,
    eps: float,
    hc_count: int = HC_COUNT,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Byte authority copied from the current Qwen4Exp XPU Torch fallback."""
    hidden_size = _validate_runtime_inputs(
        residual,
        block_output,
        injection_logits,
        norm_weight=norm_weight,
        hc_count=hc_count,
    )
    injection = 2.0 * torch.sigmoid(injection_logits.float() / hc_count)
    combined_fp32 = residual.float().unflatten(-1, (hc_count, hidden_size))
    combined_fp32 = combined_fp32 + block_output.float().unsqueeze(
        -2
    ) * injection.unsqueeze(-1)

    # This materialization is a semantic boundary, not an optimization target.
    combined = combined_fp32.flatten(-2).to(residual.dtype)
    grouped = combined.float().unflatten(-1, (hc_count, hidden_size))
    variance = grouped.square().mean(dim=-1, keepdim=True)
    normalized = grouped * torch.rsqrt(variance + eps)
    normalized = normalized.flatten(-2) * (1.0 + norm_weight.float())
    return combined, normalized.to(residual.dtype)


def exact_staged_hc_combine_norm(
    residual: torch.Tensor,
    block_output: torch.Tensor,
    injection_logits: torch.Tensor,
    norm_affine_fp32: torch.Tensor,
    eps: float,
    hc_count: int = HC_COUNT,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Run the exact candidate with only the immutable affine cast elided."""
    hidden_size = _validate_runtime_inputs(
        residual,
        block_output,
        injection_logits,
        norm_affine_fp32=norm_affine_fp32,
        hc_count=hc_count,
    )

    # Preserve Torch sigmoid, division, scaling, and operation order exactly.
    injection = 2.0 * torch.sigmoid(injection_logits.float() / hc_count)
    combined_fp32 = residual.float().unflatten(-1, (hc_count, hidden_size))
    combined_fp32 = combined_fp32 + block_output.float().unsqueeze(
        -2
    ) * injection.unsqueeze(-1)

    # Preserve the checkpoint-visible BF16 rounding and reload before RMSNorm.
    combined = combined_fp32.flatten(-2).to(residual.dtype)
    grouped = combined.float().unflatten(-1, (hc_count, hidden_size))
    variance = grouped.square().mean(dim=-1, keepdim=True)
    normalized = grouped * torch.rsqrt(variance + eps)

    # norm_affine_fp32 is exactly 1.0 + norm_weight.float(), built and checked
    # once before graph capture. No dynamic arithmetic has changed.
    normalized = normalized.flatten(-2) * norm_affine_fp32
    return combined, normalized.to(residual.dtype)


__all__ = [
    "HC_COUNT",
    "HIDDEN_SIZE",
    "HYPER_HIDDEN_SIZE",
    "build_exact_norm_affine",
    "exact_staged_hc_combine_norm",
    "torch_authority_hc_combine_norm",
    "validate_exact_norm_affine",
]
