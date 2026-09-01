#!/usr/bin/env python3
"""Bounded operator gate for the R100 live-metadata GDN norm selector."""

import hashlib
import json

import torch

from vllm.model_executor.layers.layernorm import RMSNormGated
from vllm.model_executor.layers.mamba.gdn.qwen_gdn_linear_attn import (
    _xpu_qwen_gdn_row_stable_rmsnorm_gated,
    _xpu_qwen_gdn_runtime_selected_rmsnorm_gated_impl,
)


def tensor_sha256(tensor: torch.Tensor) -> str:
    payload = tensor.detach().contiguous().cpu().view(torch.uint8).numpy().tobytes()
    return hashlib.sha256(payload).hexdigest()


def main() -> None:
    if not torch.xpu.is_available():
        raise RuntimeError("XPU is required")

    torch.manual_seed(10001)
    device = torch.device("xpu:0")
    x = torch.randn((24, 128), device=device, dtype=torch.float16) * 0.25
    z = torch.randn((24, 128), device=device, dtype=torch.float16) * 0.25
    weight = torch.randn((128,), device=device, dtype=torch.float16) * 0.1 + 1.0
    epsilon = 1e-6

    single = _xpu_qwen_gdn_runtime_selected_rmsnorm_gated_impl(
        x, z, weight, epsilon, multi_request=False
    )
    multi = _xpu_qwen_gdn_runtime_selected_rmsnorm_gated_impl(
        x, z, weight, epsilon, multi_request=True
    )
    expected_predecessor_sha256 = (
        "d292fe39d8b63706fd1f8eac018edca846926ff80a3a85ae862a9dc81b35bed5"
    )
    single_sha256 = tensor_sha256(single)
    multi_sha256 = tensor_sha256(multi)
    if single_sha256 != expected_predecessor_sha256:
        raise AssertionError("single-request arm does not match R99")
    if multi_sha256 != expected_predecessor_sha256:
        raise AssertionError("multi-request arm does not match R97")

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
    single_max_abs_error = float(
        (single.float() - reference.float()).abs().max().item()
    )
    multi_max_abs_error = float(
        (multi.float() - reference.float()).abs().max().item()
    )
    torch.testing.assert_close(single, reference, rtol=2e-3, atol=2e-3)
    torch.testing.assert_close(multi, reference, rtol=2e-3, atol=2e-3)

    single_slot_invariant = []
    multi_slot_invariant = []
    for slot in range(8):
        row = 8 + slot
        isolated_single = _xpu_qwen_gdn_runtime_selected_rmsnorm_gated_impl(
            x[row : row + 1].contiguous(),
            z[row : row + 1].contiguous(),
            weight,
            epsilon,
            multi_request=False,
        )
        isolated_multi = _xpu_qwen_gdn_runtime_selected_rmsnorm_gated_impl(
            x[row : row + 1].contiguous(),
            z[row : row + 1].contiguous(),
            weight,
            epsilon,
            multi_request=True,
        )
        single_slot_invariant.append(torch.equal(single[row], isolated_single[0]))
        multi_slot_invariant.append(torch.equal(multi[row], isolated_multi[0]))
    if not all(single_slot_invariant) or not all(multi_slot_invariant):
        raise AssertionError("one or both selector arms are not row invariant")

    unsupported_shape_failed_closed = False
    try:
        _xpu_qwen_gdn_runtime_selected_rmsnorm_gated_impl(
            x[:, :127].contiguous(),
            z[:, :127].contiguous(),
            weight[:127].contiguous(),
            epsilon,
            multi_request=False,
        )
    except RuntimeError:
        unsupported_shape_failed_closed = True
    if not unsupported_shape_failed_closed:
        raise AssertionError("unsupported shape did not fail closed")

    missing_metadata_failed_closed = False
    try:
        _xpu_qwen_gdn_row_stable_rmsnorm_gated(
            x, z, weight, epsilon, "missing.layer"
        )
    except RuntimeError:
        missing_metadata_failed_closed = True
    if not missing_metadata_failed_closed:
        raise AssertionError("missing live metadata did not fail closed")

    print(
        json.dumps(
            {
                "schema": "neural.download.qwen38-r100-operator-gate.v1",
                "status": "pass",
                "device": torch.xpu.get_device_name(0),
                "dtype": str(x.dtype),
                "rows": 24,
                "width": 128,
                "expected_predecessor_sha256": expected_predecessor_sha256,
                "single_request_arm_sha256": single_sha256,
                "multi_request_arm_sha256": multi_sha256,
                "single_request_arm_matches_r99": True,
                "multi_request_arm_matches_r97": True,
                "single_request_row_slots_bitwise_invariant": (
                    single_slot_invariant
                ),
                "multi_request_row_slots_bitwise_invariant": multi_slot_invariant,
                "single_reference_max_abs_error": single_max_abs_error,
                "multi_reference_max_abs_error": multi_max_abs_error,
                "unsupported_shape_failed_closed": unsupported_shape_failed_closed,
                "missing_metadata_failed_closed": missing_metadata_failed_closed,
                "declared_launches": {
                    "single_request": {
                        "reduction_xblock": 8,
                        "reduction_num_warps": 2,
                        "reduction_num_stages": 1,
                        "pointwise_xblock": 1024,
                        "pointwise_num_warps": 4,
                        "pointwise_num_stages": 1,
                        "transcendentals": "libdevice",
                    },
                    "multi_request": {
                        "reduction_xblock": 1,
                        "reduction_num_warps": 2,
                        "pointwise_xblock": 256,
                        "pointwise_num_warps": 4,
                        "transcendentals": "triton",
                    },
                },
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
