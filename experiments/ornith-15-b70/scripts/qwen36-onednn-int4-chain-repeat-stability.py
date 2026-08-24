#!/usr/bin/env python3
"""Check cross-stream repeat stability around a Qwen3.5 oneDNN INT4 GEMM.

The oneDNN primitive uses its own SYCL stream.  This diagnostic deliberately
places a PyTorch producer before it and a PyTorch consumer after it, without
host synchronization between the three operations.  Treatment enables the
kernel's explicit input and completion event dependencies.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import torch

import vllm_xpu_kernels
import vllm_xpu_kernels._xpu_C  # noqa: F401


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20260824)
    parser.add_argument("--treatment", action="store_true")
    return parser.parse_args()


def digest(tensor: torch.Tensor) -> str:
    raw = tensor.detach().contiguous().cpu().view(torch.uint8).numpy().tobytes()
    return hashlib.sha256(raw).hexdigest()


def main() -> None:
    args = parse_args()
    if args.treatment:
        os.environ["VLLM_XPU_ONEDNN_INT4_COMPLETION_BARRIER"] = "1"
    else:
        os.environ.pop("VLLM_XPU_ONEDNN_INT4_COMPLETION_BARRIER", None)

    torch.xpu.set_device(0)
    torch.manual_seed(args.seed)
    device = "xpu:0"
    hidden = 2048
    group_size = 128
    zero_point = torch.tensor([8], dtype=torch.int8, device=device)
    rows = []

    # Representative Qwen3.5 dense projections: shared gate/up and GDN qkvz.
    for batch_size, output_size in ((1, 1024), (64, 1024), (64, 12288)):
        base = torch.randn(batch_size, hidden, dtype=torch.float16, device=device)
        packed = torch.randint(
            -(2**31),
            2**31 - 1,
            (hidden // 8, output_size),
            dtype=torch.int32,
        )
        weight = packed.t().contiguous().t().to(device)
        scales = torch.rand(
            hidden // group_size,
            output_size,
            dtype=torch.float16,
            device=device,
        )

        def invoke(
            base: torch.Tensor = base,
            weight: torch.Tensor = weight,
            scales: torch.Tensor = scales,
        ) -> torch.Tensor:
            # Both surrounding pointwise ops run on PyTorch's current stream.
            produced = torch.tanh(base)
            projected = torch.ops._xpu_C.int4_gemm_w4a16(
                produced,
                weight,
                None,
                scales,
                zero_point,
                group_size,
                None,
                args.treatment,
            )
            return torch.nn.functional.silu(projected)

        invoke()
        torch.xpu.synchronize()
        outputs = []
        hashes = []
        for _ in range(args.repeats):
            output = invoke()
            torch.xpu.synchronize()
            outputs.append(output.detach().cpu())
            hashes.append(digest(output))
        reference = outputs[0].float()
        max_abs = max(
            float((output.float() - reference).abs().max())
            for output in outputs[1:]
        )
        row = {
            "batch_size": batch_size,
            "input_size": hidden,
            "output_size": output_size,
            "repeats": args.repeats,
            "unique_output_sha256": len(set(hashes)),
            "all_outputs_bit_identical": len(set(hashes)) == 1,
            "max_abs_drift_from_first": max_abs,
        }
        rows.append(row)
        print(json.dumps(row), flush=True)
        del base, packed, weight, scales, outputs
        torch.xpu.empty_cache()

    result = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "synthetic_current_shape_onednn_int4_chain_repeat_stability",
        "device": torch.xpu.get_device_name(0),
        "seed": args.seed,
        "treatment": args.treatment,
        "input_dependency": args.treatment,
        "completion_barrier": args.treatment,
        "vllm_xpu_kernels_file": vllm_xpu_kernels.__file__,
        "operator_schema": str(torch.ops._xpu_C.int4_gemm_w4a16._schemas),
        "rows": rows,
        "notes": [
            "Fixed tensors were reused for every repeat.",
            "No host synchronization occurs between producer, GEMM, and consumer.",
            "This does not establish full-model determinism, quality, or throughput.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
