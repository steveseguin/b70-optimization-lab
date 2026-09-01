#!/usr/bin/env python3
"""Bounded operator gate for the R98 eight-row Qwen GDN RMSNorm."""

import json

import torch

from vllm.model_executor.layers.layernorm import RMSNormGated
from vllm.model_executor.layers.mamba.gdn.qwen_gdn_linear_attn import (
    _xpu_qwen_gdn_row_stable_rmsnorm_gated,
)


def main() -> None:
    if not torch.xpu.is_available():
        raise RuntimeError("XPU is required")

    torch.manual_seed(9801)
    device = torch.device("xpu:0")
    x = torch.randn((24, 128), device=device, dtype=torch.float16) * 0.25
    z = torch.randn((24, 128), device=device, dtype=torch.float16) * 0.25
    weight = torch.randn((128,), device=device, dtype=torch.float16) * 0.1 + 1.0
    epsilon = 1e-6

    full = _xpu_qwen_gdn_row_stable_rmsnorm_gated(x, z, weight, epsilon)
    slot_invariant = []
    for slot in range(8):
        row = 8 + slot
        isolated = _xpu_qwen_gdn_row_stable_rmsnorm_gated(
            x[row : row + 1].contiguous(),
            z[row : row + 1].contiguous(),
            weight,
            epsilon,
        )
        slot_invariant.append(torch.equal(full[row], isolated[0]))
    if not all(slot_invariant):
        raise AssertionError(f"row-slot invariance failed: {slot_invariant}")

    tail = _xpu_qwen_gdn_row_stable_rmsnorm_gated(
        x[:13].contiguous(), z[:13].contiguous(), weight, epsilon
    )
    tail_matches_full = torch.equal(tail, full[:13])
    if not tail_matches_full:
        raise AssertionError("masked tail block changed retained rows")

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
    max_abs_error = float((full.float() - reference.float()).abs().max().item())
    torch.testing.assert_close(full, reference, rtol=2e-3, atol=2e-3)

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
                "schema": "neural.download.qwen38-r98-operator-gate.v1",
                "status": "pass",
                "device": torch.xpu.get_device_name(0),
                "dtype": str(x.dtype),
                "rows": 24,
                "width": 128,
                "row_slots_bitwise_invariant": slot_invariant,
                "all_eight_row_slots_bitwise_invariant": all(slot_invariant),
                "tail_rows": 13,
                "tail_masking_matches_full_block": tail_matches_full,
                "reference_max_abs_error": max_abs_error,
                "unsupported_shape_failed_closed": unsupported_shape_failed_closed,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
