#!/usr/bin/env python3
"""Microbench Qwen27 GDN qkvz/ba projection packing on XPU.

This is diagnostic-only. It measures whether replacing the current two
AutoRound/INC W4A16 GDN input projections:

    in_proj_qkvz(hidden)
    in_proj_ba(hidden)

with one wider projection:

    in_proj_qkvzba(hidden)

has enough one-layer signal to justify a vLLM loader/forward patch. Shapes
match Qwen3.6 27B linear-attention layers:

    hidden = 5120
    qkvz output = 2 * (16 * 128) + 2 * (48 * 128) = 16384
    ba output = 2 * 48 = 96

The benchmark uses synthetic quantized weights with the same memory layout as
INCXPULinearMethod after process_weights_after_loading.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable


HIDDEN = 5120
KEY_HEADS = 16
VALUE_HEADS = 48
KEY_HEAD_DIM = 128
VALUE_HEAD_DIM = 128
GROUP_SIZE = 128
PACK_FACTOR = 8
QKVZ_OUT = 2 * (KEY_HEADS * KEY_HEAD_DIM) + 2 * (
    VALUE_HEADS * VALUE_HEAD_DIM
)
BA_OUT = 2 * VALUE_HEADS
PACKED_OUT = QKVZ_OUT + BA_OUT


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-prefix", default="/home/steve/src/vllm-xpu-kernels")
    parser.add_argument("--out", required=True)
    parser.add_argument("--device", default="xpu:0")
    parser.add_argument("--rows", default="1,2,4,8")
    parser.add_argument("--warmup", type=int, default=40)
    parser.add_argument("--iterations", type=int, default=300)
    parser.add_argument("--seed", type=int, default=20260707)
    return parser.parse_args()


def parse_rows(raw: str) -> list[int]:
    return [int(item.strip()) for item in raw.split(",") if item.strip()]


def sync(torch_mod: Any) -> None:
    torch_mod.xpu.synchronize()


def bench(
    *,
    torch_mod: Any,
    name: str,
    fn: Callable[[], Any],
    warmup: int,
    iterations: int,
) -> dict[str, Any]:
    for _ in range(warmup):
        fn()
    sync(torch_mod)
    t0 = time.perf_counter()
    for _ in range(iterations):
        fn()
    sync(torch_mod)
    us = (time.perf_counter() - t0) * 1_000_000.0 / iterations
    return {"name": name, "mean_us": us, "mean_ms": us / 1000.0}


def make_int4_weight(
    torch_mod: Any,
    *,
    k: int,
    n: int,
    device: str,
    generator: Any,
) -> Any:
    # Kernel wants logical [K_packed, N] with stride[0] == 1. vLLM creates this
    # by storing [N, K_packed] contiguous and transposing it.
    backing = torch_mod.randint(
        low=0,
        high=2**31 - 1,
        size=(n, k // PACK_FACTOR),
        device=device,
        generator=generator,
        dtype=torch_mod.int32,
    ).contiguous()
    return backing.t()


def main() -> None:
    args = parse_args()
    sys.path.insert(0, args.candidate_prefix)

    import torch
    import vllm_xpu_kernels._xpu_C as xpu_c  # noqa: F401

    generator = torch.Generator(device=args.device)
    generator.manual_seed(args.seed)
    rows = parse_rows(args.rows)

    qzeros = torch.tensor([8], device=args.device, dtype=torch.int8)

    def make_scales(n: int) -> Any:
        return (
            torch.rand(
                (HIDDEN // GROUP_SIZE, n),
                device=args.device,
                dtype=torch.bfloat16,
                generator=generator,
            )
            * 0.02
            + 0.001
        ).contiguous()

    # Use separate backing allocations for current-path weights, matching the
    # current modules. The packed-path weight is one contiguous output block.
    qkvz_qweight = make_int4_weight(
        torch, k=HIDDEN, n=QKVZ_OUT, device=args.device, generator=generator
    )
    ba_qweight = make_int4_weight(
        torch, k=HIDDEN, n=BA_OUT, device=args.device, generator=generator
    )
    packed_qweight = make_int4_weight(
        torch, k=HIDDEN, n=PACKED_OUT, device=args.device, generator=generator
    )
    qkvz_scales = make_scales(QKVZ_OUT)
    ba_scales = make_scales(BA_OUT)
    packed_scales = make_scales(PACKED_OUT)
    sync(torch)

    records: list[dict[str, Any]] = []
    for row_count in rows:
        hidden = torch.randn(
            (row_count, HIDDEN),
            device=args.device,
            dtype=torch.bfloat16,
            generator=generator,
        ).contiguous()

        def qkvz_only() -> Any:
            return torch.ops._xpu_C.int4_gemm_w4a16(
                hidden,
                qkvz_qweight,
                None,
                qkvz_scales,
                qzeros,
                GROUP_SIZE,
                None,
            )

        def ba_only() -> Any:
            return torch.ops._xpu_C.int4_gemm_w4a16(
                hidden,
                ba_qweight,
                None,
                ba_scales,
                qzeros,
                GROUP_SIZE,
                None,
            )

        def current_two_gemms() -> tuple[Any, Any]:
            return qkvz_only(), ba_only()

        def packed_one_gemm() -> Any:
            out = torch.ops._xpu_C.int4_gemm_w4a16(
                hidden,
                packed_qweight,
                None,
                packed_scales,
                qzeros,
                GROUP_SIZE,
                None,
            )
            # Keep the same slicing cost the endpoint would pay to feed the
            # current downstream code paths.
            return out[:, :QKVZ_OUT], out[:, QKVZ_OUT:]

        current_result = current_two_gemms()
        packed_result = packed_one_gemm()
        sync(torch)
        records.append(
            {
                "rows": row_count,
                "hidden": HIDDEN,
                "qkvz_out": QKVZ_OUT,
                "ba_out": BA_OUT,
                "packed_out": PACKED_OUT,
                "current_shapes": [
                    list(current_result[0].shape),
                    list(current_result[1].shape),
                ],
                "packed_shapes": [
                    list(packed_result[0].shape),
                    list(packed_result[1].shape),
                ],
                "qkvz_only": bench(
                    torch_mod=torch,
                    name="qkvz_only",
                    fn=qkvz_only,
                    warmup=args.warmup,
                    iterations=args.iterations,
                ),
                "ba_only": bench(
                    torch_mod=torch,
                    name="ba_only",
                    fn=ba_only,
                    warmup=args.warmup,
                    iterations=args.iterations,
                ),
                "current_two_gemms": bench(
                    torch_mod=torch,
                    name="current_two_gemms",
                    fn=current_two_gemms,
                    warmup=args.warmup,
                    iterations=args.iterations,
                ),
                "packed_one_gemm": bench(
                    torch_mod=torch,
                    name="packed_one_gemm",
                    fn=packed_one_gemm,
                    warmup=args.warmup,
                    iterations=args.iterations,
                ),
            }
        )
        current_ms = records[-1]["current_two_gemms"]["mean_ms"]
        packed_ms = records[-1]["packed_one_gemm"]["mean_ms"]
        records[-1]["packed_minus_current_ms"] = packed_ms - current_ms
        records[-1]["saved_ms_per_layer"] = current_ms - packed_ms
        records[-1]["projected_48_layer_saved_ms"] = (
            current_ms - packed_ms
        ) * 48.0
        records[-1]["speedup"] = current_ms / packed_ms if packed_ms else None

    out = {
        "classification": "diagnostic_microbench_not_endpoint_not_localmaxxing",
        "hypothesis": "pack Qwen27 GDN qkvz and ba input projections into one W4A16 GEMM",
        "candidate_module": getattr(xpu_c, "__file__", None),
        "env": {
            "ONEAPI_DEVICE_SELECTOR": os.environ.get("ONEAPI_DEVICE_SELECTOR"),
            "ZE_AFFINITY_MASK": os.environ.get("ZE_AFFINITY_MASK"),
            "LD_LIBRARY_PATH": os.environ.get("LD_LIBRARY_PATH"),
        },
        "shape": {
            "hidden": HIDDEN,
            "qkvz_out": QKVZ_OUT,
            "ba_out": BA_OUT,
            "packed_out": PACKED_OUT,
            "gdn_layers": 48,
            "group_size": GROUP_SIZE,
            "pack_factor": PACK_FACTOR,
        },
        "records": records,
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(json.dumps(out, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
