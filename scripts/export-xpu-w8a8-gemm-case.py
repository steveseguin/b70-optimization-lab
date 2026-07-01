#!/usr/bin/env python3
"""Export deterministic XPU W8A8 grouped-GEMM cases for oneDNN parity tests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import torch

import vllm_xpu_kernels._moe_C  # noqa: F401
from vllm_xpu_kernels.fused_moe_interface import (  # noqa: F401
    _normalize_int8_weight_scales,
)


DEFAULT_ROUTE_COUNTS = (
    "data/qwen36-quark-int8-routecapture6-layer9-r1-start0-64x4-counts-"
    "20260612aw.csv"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create model-shaped W8A8 grouped-GEMM inputs, run the current XPU "
            "kernel, and export raw buffers for oneDNN comparison."
        )
    )
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--route-counts-csv", default=DEFAULT_ROUTE_COUNTS)
    parser.add_argument("--route-index", type=int, default=0)
    parser.add_argument("--device", default="xpu")
    parser.add_argument("--seed", type=int, default=20260612)
    parser.add_argument("--num-experts", type=int, default=256)
    parser.add_argument("--hidden-size", type=int, default=2048)
    parser.add_argument("--inter-size", type=int, default=128)
    parser.add_argument("--dst-dtype", choices=("bf16", "fp16"), default="bf16")
    parser.add_argument(
        "--gemm",
        choices=("gemm1", "gemm2", "both"),
        default="both",
        help="Which Qwen MoE GEMM shape to export.",
    )
    return parser.parse_args()


def load_counts(path: Path, route_index: int, num_experts: int) -> list[int]:
    with path.open() as handle:
        rows = [
            [int(item) for item in line.strip().split(",") if item]
            for line in handle
            if line.strip()
        ]
    if not rows:
        raise ValueError(f"No route-count rows in {path}")
    counts = rows[route_index % len(rows)]
    if len(counts) != num_experts:
        raise ValueError(
            f"Route count width {len(counts)} does not match {num_experts}"
        )
    total = sum(counts)
    if total <= 0:
        raise ValueError("Route-count row has no routed tokens")
    return counts


def dtype_from_name(name: str) -> torch.dtype:
    if name == "bf16":
        return torch.bfloat16
    if name == "fp16":
        return torch.float16
    raise ValueError(name)


def tensor_checksum(tensor: torch.Tensor) -> float:
    return float(tensor.float().sum().item())


def write_tensor(path: Path, tensor: torch.Tensor) -> None:
    cpu = tensor.detach().contiguous().cpu()
    if cpu.dtype is torch.bfloat16:
        cpu.view(torch.uint16).numpy().tofile(path)
    else:
        cpu.numpy().tofile(path)


def write_meta(path: Path, values: dict[str, Any]) -> None:
    with path.open("w") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")


def make_case(
    *,
    name: str,
    out_dir: Path,
    counts: list[int],
    num_experts: int,
    k_dim: int,
    n_dim: int,
    dst_dtype: torch.dtype,
    device: str,
    seed: int,
) -> dict[str, Any]:
    total_tokens = sum(counts)
    generator = torch.Generator(device="cpu")
    generator.manual_seed(seed)

    cpu_a = torch.randint(
        -127,
        128,
        (total_tokens, k_dim),
        dtype=torch.int8,
        generator=generator,
    )
    cpu_b = torch.randint(
        -127,
        128,
        (num_experts, k_dim, n_dim),
        dtype=torch.int8,
        generator=generator,
    )
    cpu_a_scales = (
        torch.rand((total_tokens, 1), dtype=torch.float32, generator=generator)
        * 0.02
        + 0.001
    )
    cpu_b_scales = (
        torch.rand((num_experts, n_dim), dtype=torch.float32, generator=generator)
        * 0.02
        + 0.001
    )
    cpu_rows = torch.tensor(counts, dtype=torch.int32)

    a = cpu_a.to(device)
    b = cpu_b.to(device)
    a_scales = cpu_a_scales.to(device)
    b_scales = cpu_b_scales.to(device)
    rows = cpu_rows.to(device)
    out = torch.empty((total_tokens, n_dim), device=device, dtype=dst_dtype)

    torch.ops._xpu_C.cutlass_grouped_gemm_w8a8_int8_interface(
        ptr_A=a,
        ptr_A_scales=a_scales,
        ptr_B=b,
        ptr_B_scales=b_scales,
        ptr_bias=None,
        ptr_D=out,
        rows_per_expert=rows,
        N=n_dim,
        K=k_dim,
        num_experts=num_experts,
    )
    torch.xpu.synchronize()

    paths = {
        "a_path": f"{name}_A.s8.bin",
        "a_scales_path": f"{name}_A_scales.f32.bin",
        "b_path": f"{name}_B.s8.bin",
        "b_acb_path": f"{name}_B_acb.s8.bin",
        "b_scales_path": f"{name}_B_scales.f32.bin",
        "rows_path": f"{name}_rows.i32.bin",
        "xpu_out_path": f"{name}_xpu_out.{('bf16' if dst_dtype is torch.bfloat16 else 'fp16')}.bin",
        "xpu_out_f32_path": f"{name}_xpu_out.f32.bin",
    }
    write_tensor(out_dir / paths["a_path"], cpu_a)
    write_tensor(out_dir / paths["a_scales_path"], cpu_a_scales)
    write_tensor(out_dir / paths["b_path"], cpu_b)
    write_tensor(out_dir / paths["b_acb_path"], cpu_b.permute(0, 2, 1).contiguous())
    write_tensor(out_dir / paths["b_scales_path"], cpu_b_scales)
    write_tensor(out_dir / paths["rows_path"], cpu_rows)
    write_tensor(out_dir / paths["xpu_out_path"], out)
    write_tensor(out_dir / paths["xpu_out_f32_path"], out.float())

    meta = {
        "name": name,
        "num_experts": num_experts,
        "total_tokens": total_tokens,
        "k": k_dim,
        "n": n_dim,
        "dst_dtype": "bf16" if dst_dtype is torch.bfloat16 else "fp16",
        "weight_format": "abc",
        **paths,
    }
    write_meta(out_dir / f"{name}.meta", meta)

    return {
        **meta,
        "active_experts": sum(1 for count in counts if count),
        "xpu_output_checksum_f32": tensor_checksum(out),
        "a_checksum": int(cpu_a.to(torch.int32).sum().item()),
        "b_checksum": int(cpu_b.to(torch.int32).sum().item()),
        "a_scales_checksum": float(cpu_a_scales.sum().item()),
        "b_scales_checksum": float(cpu_b_scales.sum().item()),
    }


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    counts = load_counts(Path(args.route_counts_csv), args.route_index, args.num_experts)
    dst_dtype = dtype_from_name(args.dst_dtype)
    cases: list[dict[str, Any]] = []
    if args.gemm in ("gemm1", "both"):
        cases.append(
            make_case(
                name="gemm1",
                out_dir=out_dir,
                counts=counts,
                num_experts=args.num_experts,
                k_dim=args.hidden_size,
                n_dim=2 * args.inter_size,
                dst_dtype=dst_dtype,
                device=args.device,
                seed=args.seed + 1,
            )
        )
    if args.gemm in ("gemm2", "both"):
        cases.append(
            make_case(
                name="gemm2",
                out_dir=out_dir,
                counts=counts,
                num_experts=args.num_experts,
                k_dim=args.inter_size,
                n_dim=args.hidden_size,
                dst_dtype=dst_dtype,
                device=args.device,
                seed=args.seed + 2,
            )
        )

    manifest = {
        "route_counts_csv": args.route_counts_csv,
        "route_index": args.route_index,
        "counts_total": sum(counts),
        "num_experts": args.num_experts,
        "active_experts": sum(1 for count in counts if count),
        "device": args.device,
        "dst_dtype": args.dst_dtype,
        "cases": cases,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
