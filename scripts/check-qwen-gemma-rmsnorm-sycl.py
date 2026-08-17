#!/usr/bin/env python3
"""Direct parity guard for the Qwen/Gemma FP16+FP32-weight XPU RMSNorm op."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import torch
import vllm_xpu_kernels._xpu_C  # noqa: F401


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def invoke(input_tensor: torch.Tensor, weight: torch.Tensor, epsilon: float) -> torch.Tensor:
    output = torch.empty_like(input_tensor, memory_format=torch.contiguous_format)
    torch.ops._xpu_C.qwen_gemma_rms_norm_f32_weight_out(
        input_tensor, weight, output, epsilon
    )
    return output


def case(
    hidden: int,
    heads: int,
    dtype: torch.dtype,
    device: torch.device,
    epsilon: float,
) -> dict:
    row = torch.randn((1, heads, hidden), dtype=dtype, device=device)
    weight = 1.0 + 0.05 * torch.randn(hidden, dtype=torch.float32, device=device)
    single = invoke(row, weight, epsilon)
    packed_input = row.repeat(4, 1, 1)
    packed = invoke(packed_input, weight, epsilon)
    packed_repeat = invoke(packed_input, weight, epsilon)

    # Exercise non-dense outer strides while retaining the required contiguous
    # hidden dimension. This matches Q/K views after compiler-visible slicing.
    backing = torch.empty((4, heads, hidden * 2), dtype=dtype, device=device)
    strided = backing[..., :hidden]
    strided.copy_(packed_input)
    strided_output = invoke(strided, weight, epsilon)

    reference = (
        packed_input.float()
        * torch.rsqrt(
            packed_input.float().square().mean(dim=-1, keepdim=True) + epsilon
        )
        * weight
    ).to(dtype)
    torch.xpu.synchronize(device)

    rows_equal = [torch.equal(packed[index], single[0]) for index in range(4)]
    repeat_equal = torch.equal(packed, packed_repeat)
    strided_equal = torch.equal(packed, strided_output)
    max_abs_reference = float((packed.float() - reference.float()).abs().max().item())
    return {
        "hidden": hidden,
        "heads": heads,
        "dtype": str(dtype),
        "single_vs_packed_rows_equal": rows_equal,
        "packed_repeat_equal": repeat_equal,
        "strided_outer_vs_contiguous_equal": strided_equal,
        "max_abs_vs_torch_reference": max_abs_reference,
        "passed": all(rows_equal)
        and repeat_equal
        and strided_equal
        and max_abs_reference <= 0.02,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", type=int, default=0)
    parser.add_argument("--seed", type=int, default=20260816)
    parser.add_argument("--epsilon", type=float, default=1e-6)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    torch.manual_seed(args.seed)
    device = torch.device(f"xpu:{args.device}")
    torch.xpu.set_device(device)
    module_path = Path(vllm_xpu_kernels._xpu_C.__file__).resolve()
    cases = [
        case(128, 4, torch.float16, device, args.epsilon),
        case(256, 3, torch.float16, device, args.epsilon),
        case(5120, 1, torch.float16, device, args.epsilon),
        case(5120, 1, torch.float32, device, args.epsilon),
    ]
    result = {
        "schema_version": 1,
        "classification": "direct_op_correctness_guard",
        "device": str(device),
        "seed": args.seed,
        "epsilon": args.epsilon,
        "module": str(module_path),
        "module_sha256": sha256(module_path),
        "cases": cases,
        "passed": all(item["passed"] for item in cases),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
