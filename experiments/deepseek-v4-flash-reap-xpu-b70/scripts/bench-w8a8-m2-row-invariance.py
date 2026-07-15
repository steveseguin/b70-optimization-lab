#!/usr/bin/env python3
"""Check M=2 versus two M=1 calls for remaining K160 W8A8 linears."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch

from vllm.model_executor.layers.quantization.utils.fp8_utils import (
    per_token_group_quant_fp8,
)
from vllm.platforms import current_platform


# Standard target layers use the first shape for the TP4 shared-expert down
# projection.  The second shape is the MTP-only e_proj/h_proj family.
SHAPES = (
    (4096, 512, "target_shared_expert_down"),
    (4096, 4096, "mtp_e_proj_h_proj"),
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="xpu:0")
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    torch.xpu.set_device(args.device)
    device = torch.device(args.device)
    current_platform.import_kernels()
    rows = []

    for shape_index, (n, k, family) in enumerate(SHAPES):
        torch.manual_seed(20260715 + shape_index)
        x = torch.empty((2, k), device=device, dtype=torch.bfloat16)
        weight = torch.randn((n, k), device=device, dtype=torch.float32).to(
            torch.float8_e4m3fn
        )
        weight_scales = (
            torch.rand(
                (k // 128, n // 128), device=device, dtype=torch.float32
            )
            * 0.02
            + 0.002
        )

        def project(value: torch.Tensor) -> torch.Tensor:
            quantized, activation_scales = per_token_group_quant_fp8(
                value, 128, use_ue8m0=False
            )
            return torch.ops._xpu_C.fp8_gemm(
                quantized,
                weight.t(),
                torch.bfloat16,
                activation_scales,
                weight_scales,
                torch.Tensor(),
            )

        exact_epochs = 0
        mismatch_elements = 0
        maximum_abs_difference = 0.0
        for epoch in range(args.epochs):
            torch.manual_seed(20260715 + shape_index * 1000 + epoch)
            x.copy_(torch.randn_like(x).mul_(0.125 * (1 + epoch % 8)))
            separate = torch.cat((project(x[:1]), project(x[1:])), dim=0)
            together = project(x)
            torch.xpu.synchronize()
            difference = (separate.float() - together.float()).abs()
            mismatches = int(torch.count_nonzero(separate != together).item())
            exact_epochs += mismatches == 0
            mismatch_elements += mismatches
            maximum_abs_difference = max(
                maximum_abs_difference, float(difference.max().item())
            )

        rows.append(
            {
                "family": family,
                "shape": {"m": 2, "n": n, "k": k},
                "exact_epochs": exact_epochs,
                "epochs": args.epochs,
                "mismatch_elements": mismatch_elements,
                "maximum_abs_difference": maximum_abs_difference,
            }
        )

    result = {
        "schema_version": 1,
        "classification": "deepseek_v4_w8a8_m2_row_invariance",
        "device": args.device,
        "device_name": torch.xpu.get_device_name(device),
        "torch_version": torch.__version__,
        "rows": rows,
        "gate": {
            "passed": all(row["exact_epochs"] == row["epochs"] for row in rows),
            "purpose": (
                "Rule out M-dependent activation quantization or oneDNN FP8 "
                "GEMM arithmetic in K160 linears not selected for W8A16."
            ),
        },
    }
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n")
    return 0 if result["gate"]["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
