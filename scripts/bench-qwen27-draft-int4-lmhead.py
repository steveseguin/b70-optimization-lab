#!/usr/bin/env python3
"""Microbench the Qwen27 draft INT4 LM-head primitive on XPU.

This is diagnostic only. It benchmarks the current exact draft-head backend
shape used by the Qwen27 record lane:

  hidden [rows, 5120] x packed W4 [5120, 248320] -> dense logits -> argmax

It does not claim endpoint throughput and does not change model quality. Its
purpose is to define the baseline that any future fused W4A16 top-ID kernel
must beat.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


def parse_rows(value: str) -> list[int]:
    rows: list[int] = []
    for part in value.split(","):
        part = part.strip()
        if part:
            rows.append(int(part))
    if not rows:
        raise argparse.ArgumentTypeError("expected at least one row count")
    return rows


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    idx = (len(ordered) - 1) * q
    lo = int(idx)
    hi = min(lo + 1, len(ordered) - 1)
    frac = idx - lo
    return ordered[lo] * (1 - frac) + ordered[hi] * frac


def summarize(times: list[float]) -> dict[str, float | int]:
    return {
        "count": len(times),
        "median_ms": statistics.median(times),
        "mean_ms": statistics.mean(times),
        "p10_ms": percentile(times, 0.10),
        "p90_ms": percentile(times, 0.90),
        "min_ms": min(times),
        "max_ms": max(times),
        "stdev_ms": statistics.stdev(times) if len(times) > 1 else 0.0,
    }


def bench(
    *,
    name: str,
    fn: Callable[[], Any],
    torch: Any,
    warmup: int,
    iterations: int,
) -> dict[str, Any]:
    try:
        for _ in range(warmup):
            fn()
        torch.xpu.synchronize()
        times: list[float] = []
        for _ in range(iterations):
            start = time.perf_counter()
            fn()
            torch.xpu.synchronize()
            times.append((time.perf_counter() - start) * 1000.0)
        return {"name": name, **summarize(times)}
    except Exception as exc:  # noqa: BLE001 - keep incompatibility in output.
        return {"name": name, "error": repr(exc)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=parse_rows, default=parse_rows("1,2,3,4"))
    parser.add_argument("--hidden", type=int, default=5120)
    parser.add_argument("--vocab", type=int, default=248320)
    parser.add_argument("--group-size", type=int, default=128)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--iterations", type=int, default=80)
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--device", default="xpu")
    parser.add_argument("--output-json")
    args = parser.parse_args()

    import torch
    import vllm_xpu_kernels._xpu_C  # noqa: F401

    if args.device.startswith("xpu"):
        torch.xpu.set_device(0)
    if args.hidden % args.group_size != 0:
        raise ValueError("--group-size must divide --hidden")
    if args.group_size % 8 != 0:
        raise ValueError("--group-size must be divisible by 8")

    generator = torch.Generator(device=args.device)
    generator.manual_seed(args.seed)
    packed_k = args.hidden // 8
    num_groups = args.hidden // args.group_size

    # Match VLLM_XPU_DRAFT_LM_HEAD_INT4 layout:
    # qweight is a transposed view with logical shape [K/8, vocab].
    packed_storage = torch.randint(
        0,
        2**31 - 1,
        (args.vocab, packed_k),
        device=args.device,
        generator=generator,
        dtype=torch.int32,
    ).contiguous()
    qweight_t = packed_storage.t()
    scales = (
        torch.rand(
            (num_groups, args.vocab),
            device=args.device,
            generator=generator,
            dtype=torch.float32,
        )
        * 0.05
        + 1.0e-4
    ).to(torch.bfloat16).contiguous()
    qzeros = torch.tensor([8], dtype=torch.int8, device=args.device)

    output: dict[str, Any] = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": (
            "Diagnostic current-backend Qwen27 draft INT4 LM-head microbench; "
            "not an endpoint throughput result."
        ),
        "torch": torch.__version__,
        "shape": {
            "hidden": args.hidden,
            "vocab": args.vocab,
            "group_size": args.group_size,
            "packed_k": packed_k,
            "num_groups": num_groups,
            "rows": args.rows,
        },
        "warmup": args.warmup,
        "iterations": args.iterations,
        "results": [],
    }
    top1_op = getattr(torch.ops._xpu_C, "int4_gemm_w4a16_top1", None)

    for rows in args.rows:
        hidden = torch.randn(
            (rows, args.hidden),
            device=args.device,
            generator=generator,
            dtype=torch.bfloat16,
        ).contiguous()

        def gemm_only():
            return torch.ops._xpu_C.int4_gemm_w4a16(
                hidden,
                qweight_t,
                None,
                scales,
                qzeros,
                args.group_size,
                None,
            )

        def gemm_argmax():
            logits = gemm_only()
            return logits.argmax(dim=-1)

        def top1_only():
            return top1_op(
                hidden,
                qweight_t,
                scales,
                qzeros,
                args.group_size,
                None,
            )

        backends = [
            bench(
                name="int4_gemm_w4a16_dense_logits",
                fn=gemm_only,
                torch=torch,
                warmup=args.warmup,
                iterations=args.iterations,
            ),
            bench(
                name="int4_gemm_w4a16_dense_logits_argmax",
                fn=gemm_argmax,
                torch=torch,
                warmup=args.warmup,
                iterations=args.iterations,
            ),
        ]
        correctness: dict[str, Any]
        if top1_op is not None:
            try:
                dense_logits = gemm_only()
                dense_ids = dense_logits.argmax(dim=-1)
                dense_values = dense_logits.gather(1, dense_ids[:, None]).squeeze(1)
                top_ids, top_values = top1_only()
                torch.xpu.synchronize()
                id_match = torch.equal(dense_ids, top_ids)
                value_abs_diff = (dense_values.float() - top_values.float()).abs()
                correctness = {
                    "top1_available": True,
                    "id_match_all": bool(
                        id_match.item() if hasattr(id_match, "item") else id_match
                    ),
                    "dense_ids": dense_ids.cpu().tolist(),
                    "top1_ids": top_ids.cpu().tolist(),
                    "max_value_abs_diff": float(value_abs_diff.max().cpu().item()),
                    "mean_value_abs_diff": float(value_abs_diff.mean().cpu().item()),
                }
            except Exception as exc:  # noqa: BLE001 - keep exact failure.
                correctness = {
                    "top1_available": True,
                    "top1_correctness_error": repr(exc),
                }
            backends.append(
                bench(
                    name="int4_gemm_w4a16_top1_experimental",
                    fn=top1_only,
                    torch=torch,
                    warmup=args.warmup,
                    iterations=args.iterations,
                )
            )
        else:
            correctness = {"top1_available": False}

        row_result = {
            "rows": rows,
            "correctness": correctness,
            "backends": backends,
        }
        output["results"].append(row_result)
        print(json.dumps(row_result, indent=2))

    if args.output_json:
        path = Path(args.output_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
