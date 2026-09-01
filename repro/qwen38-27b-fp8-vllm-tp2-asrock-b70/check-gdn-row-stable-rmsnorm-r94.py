#!/usr/bin/env python3
"""Bounded operator gate for the R94 Qwen GDN row-stable RMSNorm."""

import json

import torch

from vllm.model_executor.layers.layernorm import RMSNormGated
from vllm.model_executor.layers.mamba.gdn.qwen_gdn_linear_attn import (
    _xpu_qwen_gdn_row_stable_rmsnorm_gated,
)


def main() -> None:
    if not torch.xpu.is_available():
        raise RuntimeError("XPU is required")

    torch.manual_seed(9401)
    device = torch.device("xpu:0")
    x = torch.randn((19, 128), device=device, dtype=torch.float16) * 0.25
    z = torch.randn((19, 128), device=device, dtype=torch.float16) * 0.25
    weight = torch.randn((128,), device=device, dtype=torch.float16) * 0.1 + 1.0
    epsilon = 1e-6

    batch = _xpu_qwen_gdn_row_stable_rmsnorm_gated(x, z, weight, epsilon)
    isolated = _xpu_qwen_gdn_row_stable_rmsnorm_gated(
        x[7:8].contiguous(), z[7:8].contiguous(), weight, epsilon
    )
    row_invariant = torch.equal(batch[7], isolated[0])
    if not row_invariant:
        raise AssertionError("selected row changed when embedded in a larger batch")

    reference = RMSNormGated.forward_static(
        x,
        z,
        weight,
        epsilon,
        x.dtype,
        group_size=None,
        norm_before_gate=True,
        activation="silu",
    )
    max_abs_error = float((batch.float() - reference.float()).abs().max().item())
    torch.testing.assert_close(batch, reference, rtol=2e-3, atol=2e-3)

    unsupported_shape_failed_closed = False
    try:
        _xpu_qwen_gdn_row_stable_rmsnorm_gated(
            x[:, :127].contiguous(),
            z[:, :127].contiguous(),
            weight[:127].contiguous(),
            epsilon,
        )
    except RuntimeError:
        unsupported_shape_failed_closed = True
    if not unsupported_shape_failed_closed:
        raise AssertionError("unsupported shape did not fail closed")

    print(
        json.dumps(
            {
                "schema": "neural.download.qwen38-r94-operator-gate.v1",
                "status": "pass",
                "device": torch.xpu.get_device_name(0),
                "dtype": str(x.dtype),
                "rows": 19,
                "width": 128,
                "selected_row": 7,
                "selected_row_bitwise_invariant": row_invariant,
                "reference_max_abs_error": max_abs_error,
                "unsupported_shape_failed_closed": unsupported_shape_failed_closed,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
