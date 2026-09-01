#!/usr/bin/env python3
"""Bounded operator gate for the R101 profile-aware GDN selector."""

import hashlib
import json

import torch

from vllm.model_executor.layers.mamba.gdn.qwen_gdn_linear_attn import (
    _xpu_qwen_gdn_runtime_selected_rmsnorm_gated_impl,
)


def digest(tensor: torch.Tensor) -> str:
    data = tensor.detach().contiguous().cpu().view(torch.uint8).numpy().tobytes()
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    if not torch.xpu.is_available():
        raise RuntimeError("XPU is required")
    torch.manual_seed(10001)
    device = torch.device("xpu:0")
    x = torch.randn((24, 128), device=device, dtype=torch.float16) * 0.25
    z = torch.randn((24, 128), device=device, dtype=torch.float16) * 0.25
    weight = torch.randn((128,), device=device, dtype=torch.float16) * 0.1 + 1.0
    epsilon = 1e-6
    expected = "d292fe39d8b63706fd1f8eac018edca846926ff80a3a85ae862a9dc81b35bed5"

    single = _xpu_qwen_gdn_runtime_selected_rmsnorm_gated_impl(
        x, z, weight, epsilon, multi_request=False
    )
    multi = _xpu_qwen_gdn_runtime_selected_rmsnorm_gated_impl(
        x, z, weight, epsilon, multi_request=True
    )
    hashes = {"single": digest(single), "multi": digest(multi)}
    if any(value != expected for value in hashes.values()):
        raise AssertionError(f"selector arm identity mismatch: {hashes}")

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

    print(
        json.dumps(
            {
                "schema": "neural.download.qwen38-r101-operator-gate.v1",
                "status": "pass",
                "device": torch.xpu.get_device_name(0),
                "expected_predecessor_sha256": expected,
                "single_request_arm_sha256": hashes["single"],
                "multi_request_arm_sha256": hashes["multi"],
                "profile_fallback_gate": "server-startup lifecycle gate",
                "unsupported_shape_failed_closed": unsupported_shape_failed_closed,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
