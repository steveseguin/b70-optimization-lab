#!/usr/bin/env python3
"""Prove first-row shape invariance for the patched XPU Gemma RMSNorm path."""

from __future__ import annotations

import argparse
import json
import os

TREATMENT_ENV = "VLLM_XPU_QWEN_GEMMA_RMSNORM_PACKED_SERIAL_EXACT"
os.environ[TREATMENT_ENV] = "1"

import torch

from vllm.config import VllmConfig, set_current_vllm_config
from vllm.model_executor.layers.layernorm import GemmaRMSNorm


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="xpu:0")
    parser.add_argument("--hidden-size", type=int, default=5120)
    parser.add_argument("--trials", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20260828)
    args = parser.parse_args()

    if args.hidden_size <= 0 or args.trials <= 0:
        parser.error("--hidden-size and --trials must be positive")

    torch.manual_seed(args.seed)
    with set_current_vllm_config(VllmConfig()):
        layer = GemmaRMSNorm(args.hidden_size).to(args.device)
    with torch.no_grad():
        layer.weight.uniform_(-0.25, 0.25)

    plain_bad = 0
    fused_bad = 0
    residual_bad = 0
    native_plain_bad = 0
    native_fused_bad = 0
    native_residual_bad = 0
    plain_max_abs = 0.0
    fused_max_abs = 0.0
    residual_max_abs = 0.0

    with torch.no_grad():
        for _ in range(args.trials):
            row = torch.randn(
                1, args.hidden_size, device=args.device, dtype=torch.float16
            )
            other = torch.randn_like(row)
            os.environ[TREATMENT_ENV] = "0"
            native_single = layer.forward_native(row)
            os.environ[TREATMENT_ENV] = "1"
            single = layer.forward_xpu(row)
            packed = layer.forward_xpu(torch.cat((row, other), dim=0))[0:1]
            delta = (single - packed).abs().max().item()
            plain_max_abs = max(plain_max_abs, delta)
            plain_bad += int(not torch.equal(single, packed))
            native_plain_bad += int(not torch.equal(native_single, single))

            residual = torch.randn_like(row)
            other_residual = torch.randn_like(row)
            os.environ[TREATMENT_ENV] = "0"
            native_out, native_residual = layer.forward_native(row, residual)
            os.environ[TREATMENT_ENV] = "1"
            single_out, single_residual = layer.forward_xpu(row, residual)
            packed_out, packed_residual = layer.forward_xpu(
                torch.cat((row, other), dim=0),
                torch.cat((residual, other_residual), dim=0),
            )
            out_delta = (single_out - packed_out[0:1]).abs().max().item()
            residual_delta = (
                single_residual - packed_residual[0:1]
            ).abs().max().item()
            fused_max_abs = max(fused_max_abs, out_delta)
            residual_max_abs = max(residual_max_abs, residual_delta)
            fused_bad += int(not torch.equal(single_out, packed_out[0:1]))
            residual_bad += int(
                not torch.equal(single_residual, packed_residual[0:1])
            )
            native_fused_bad += int(not torch.equal(native_out, single_out))
            native_residual_bad += int(
                not torch.equal(native_residual, single_residual)
            )

    result = {
        "schema": "neural.download.qwen38-gemma-rmsnorm-packed-serial-proof.v1",
        "device": args.device,
        "dtype": "float16",
        "hidden_size": args.hidden_size,
        "trials": args.trials,
        "plain_bad": plain_bad,
        "fused_bad": fused_bad,
        "residual_bad": residual_bad,
        "native_plain_bad": native_plain_bad,
        "native_fused_bad": native_fused_bad,
        "native_residual_bad": native_residual_bad,
        "plain_max_abs": plain_max_abs,
        "fused_max_abs": fused_max_abs,
        "residual_max_abs": residual_max_abs,
        "passed": plain_bad == fused_bad == residual_bad == 0,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
