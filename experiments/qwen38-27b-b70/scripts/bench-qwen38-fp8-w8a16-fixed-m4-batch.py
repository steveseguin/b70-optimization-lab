#!/usr/bin/env python3
"""Screen a broadcast-weight oneDNN batch of fixed four-row W8A16 GEMMs."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from pathlib import Path

import torch


SHAPES = {
    "attn_o_proj": (3072, 5120),
    "attn_qkv_proj": (5120, 7168),
}
BATCHES = [1, 2, 8, 16, 32, 42, 50, 56, 63, 64]
TIMED_BATCHES = [1, 8, 32, 64]
FIXED_M = 4


def gemm(a, weight, scale):
    return torch.ops._xpu_C.fp8_gemm_w8a16(a, weight, scale, None)


def digest(tensor: torch.Tensor) -> str:
    return hashlib.sha256(
        tensor.detach().contiguous().view(torch.uint8).cpu().numpy().tobytes()
    ).hexdigest()


def max_abs(a, b) -> float:
    return float((a.float() - b.float()).abs().max().item())


def sequential(a_flat, batch, weight, scale):
    return torch.cat(
        [
            gemm(a_flat[i * FIXED_M : (i + 1) * FIXED_M], weight, scale)
            for i in range(batch)
        ],
        dim=0,
    )


def time_us(fn, warmups, iterations, repeats):
    for _ in range(warmups):
        fn()
    torch.xpu.synchronize()
    values = []
    stream = torch.xpu.current_stream()
    for _ in range(repeats):
        start = torch.xpu.Event(enable_timing=True)
        end = torch.xpu.Event(enable_timing=True)
        start.record(stream)
        for _ in range(iterations):
            fn()
        end.record(stream)
        end.synchronize()
        values.append(start.elapsed_time(end) * 1000.0 / iterations)
    return {
        "median_us": statistics.median(values),
        "min_us": min(values),
        "max_us": max(values),
        "samples_us": values,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260902)
    parser.add_argument("--warmups", type=int, default=10)
    parser.add_argument("--iterations", type=int, default=30)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()

    import vllm_xpu_kernels._xpu_C  # noqa: F401

    if not torch.xpu.is_available():
        raise SystemExit("XPU is required")
    device = torch.device("xpu:0")
    gen = torch.Generator(device="cpu").manual_seed(args.seed)
    report = {
        "schema": "neural.download.qwen38-fp8-w8a16-fixed-m4-batch.v1",
        "classification": "operator-diagnostic-only",
        "environment": {
            "device": torch.xpu.get_device_name(0),
            "torch": torch.__version__,
            "seed": args.seed,
        },
        "fixed_m": FIXED_M,
        "batches": BATCHES,
        "shapes": {},
    }

    for name, (k, n) in SHAPES.items():
        weight_nk = (
            torch.randn((n, k), generator=gen, device="cpu") * 0.05
        ).to(torch.float8_e4m3fn).to(device)
        weight = weight_nk.t()
        scale = (
            torch.rand((k // 128, n // 128), generator=gen, device="cpu")
            * 0.02
            + 0.005
        ).to(torch.float32).to(device).contiguous()
        a_full = torch.randn(
            (max(BATCHES) * FIXED_M, k), generator=gen, device="cpu"
        ).to(torch.float16).to(device)

        item = {"K": k, "N": n}
        try:
            outputs = {
                batch: gemm(
                    a_full[: batch * FIXED_M].reshape(batch, FIXED_M, k),
                    weight,
                    scale,
                ).reshape(batch * FIXED_M, n)
                for batch in BATCHES
            }
            torch.xpu.synchronize()

            row0_classes = {}
            for batch, out in outputs.items():
                row0_classes.setdefault(digest(out[:1]), []).append(batch)

            reference_by_batch = {
                batch: sequential(a_full, batch, weight, scale)
                for batch in BATCHES
            }
            exact_vs_sequential = {
                str(batch): bool(torch.equal(outputs[batch], reference_by_batch[batch]))
                for batch in BATCHES
            }
            max_abs_vs_sequential = {
                str(batch): max_abs(outputs[batch], reference_by_batch[batch])
                for batch in BATCHES
            }

            perm = torch.randperm(32 * FIXED_M, generator=gen).to(device)
            natural32 = outputs[32]
            permuted32 = gemm(
                a_full[: 32 * FIXED_M][perm].reshape(32, FIXED_M, k),
                weight,
                scale,
            ).reshape(32 * FIXED_M, n)
            repeat16 = gemm(
                a_full[: 16 * FIXED_M].reshape(16, FIXED_M, k), weight, scale
            ).reshape(16 * FIXED_M, n)

            timings = {}
            for batch in TIMED_BATCHES:
                a = a_full[: batch * FIXED_M].contiguous()
                timings[str(batch)] = {
                    "batched": time_us(
                        lambda a=a, batch=batch: gemm(
                            a.reshape(batch, FIXED_M, k), weight, scale
                        ),
                        args.warmups,
                        args.iterations,
                        args.repeats,
                    ),
                    "natural_flattened": time_us(
                        lambda a=a: gemm(a, weight, scale),
                        args.warmups,
                        args.iterations,
                        args.repeats,
                    ),
                    "sequential_m4": time_us(
                        lambda a=a, batch=batch: [
                            gemm(
                                a[i * FIXED_M : (i + 1) * FIXED_M],
                                weight,
                                scale,
                            )
                            for i in range(batch)
                        ],
                        args.warmups,
                        args.iterations,
                        args.repeats,
                    ),
                }
                timings[str(batch)]["ratio_vs_natural"] = (
                    timings[str(batch)]["batched"]["median_us"]
                    / timings[str(batch)]["natural_flattened"]["median_us"]
                )
                timings[str(batch)]["ratio_vs_sequential_m4"] = (
                    timings[str(batch)]["batched"]["median_us"]
                    / timings[str(batch)]["sequential_m4"]["median_us"]
                )

            item.update(
                {
                    "executed": True,
                    "row0_classes_by_batch": sorted(
                        row0_classes.values(), key=lambda values: values[0]
                    ),
                    "row0_invariant_across_batches": len(row0_classes) == 1,
                    "exact_vs_sequential_m4_by_batch": exact_vs_sequential,
                    "max_abs_vs_sequential_m4_by_batch": max_abs_vs_sequential,
                    "permutation_invariant_B32": bool(
                        torch.equal(permuted32, natural32[perm])
                    ),
                    "permutation_max_abs_B32": max_abs(
                        permuted32, natural32[perm]
                    ),
                    "repeat_deterministic_B16": bool(
                        torch.equal(repeat16, outputs[16])
                    ),
                    "latency_us": timings,
                }
            )
        except Exception as exc:  # noqa: BLE001
            item.update(
                {
                    "executed": False,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
        report["shapes"][name] = item
        print(f"[fixed-m4-batch] {name}: {item}", flush=True)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=1, sort_keys=True))
        del weight_nk, weight, scale, a_full
        torch.xpu.synchronize()
        torch.xpu.empty_cache()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
