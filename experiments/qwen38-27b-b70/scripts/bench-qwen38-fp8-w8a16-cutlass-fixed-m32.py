#!/usr/bin/env python3
"""Operator gate for the Xe2 CUTLASS block-FP8 fixed-M32 kernel.

The candidate reuses the pinned vllm-xpu-kernels grouped GEMM implementation
with one logical expert and pins its existing 32x64 output-tile policy for all
M. The oneDNN dense W8A16 operator is the latency and numerical control.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path

import torch


SHAPES = {
    "attn_o_proj": (3072, 5120),
    "attn_qkv_proj": (5120, 7168),
}
M_VALUES = [1, 2, 4, 8, 16, 32, 64, 128, 168, 200, 224, 250, 256, 300, 512]
TIMED_M_VALUES = [1, 4, 32, 168, 256]


def digest(tensor: torch.Tensor) -> str:
    data = tensor.detach().contiguous().view(torch.uint8).cpu().numpy().tobytes()
    return hashlib.sha256(data).hexdigest()


def max_abs(a: torch.Tensor, b: torch.Tensor) -> float:
    return float((a.float() - b.float()).abs().max().item())


def mean_abs(a: torch.Tensor, b: torch.Tensor) -> float:
    return float((a.float() - b.float()).abs().mean().item())


def time_us(fn, warmups: int, iterations: int, repeats: int) -> dict:
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


def one_dnn(a, weight, scale):
    return torch.ops._xpu_C.fp8_gemm_w8a16(a, weight, scale, None)


def cutlass(a, weight_e, scale_e, rows, out):
    m, k = a.shape
    n = out.shape[1]
    return torch.ops._xpu_C.cutlass_grouped_gemm_interface(
        a,
        None,
        weight_e,
        scale_e,
        None,
        out,
        rows,
        n,
        k,
        1,
    )


def geomean(values) -> float:
    return math.exp(sum(math.log(value) for value in values) / len(values))


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
        "schema": "neural.download.qwen38-fp8-w8a16-cutlass-fixed-m32.v1",
        "classification": "operator-diagnostic-only",
        "environment": {
            "device": torch.xpu.get_device_name(0),
            "torch": torch.__version__,
            "seed": args.seed,
        },
        "candidate": {
            "implementation": "Xe2 CUTLASS grouped BLOCK_FP8 with one expert",
            "fixed_policy": "w8a16_policy_m_32",
            "tile_mnk": [32, 64, 32],
            "scale_group": [128, 128],
        },
        "m_values": M_VALUES,
        "timed_m_values": TIMED_M_VALUES,
        "shapes": {},
    }

    for name, (k, n) in SHAPES.items():
        weight_nk = (torch.randn((n, k), generator=gen) * 0.05).to(
            torch.float8_e4m3fn
        )
        weight = weight_nk.t().contiguous().to(device)
        weight_e = weight.unsqueeze(0)
        scale = (
            torch.rand((k // 128, n // 128), generator=gen) * 0.02 + 0.005
        ).to(torch.float32).to(device).contiguous()
        scale_e = scale.unsqueeze(0)
        a_full = torch.randn((max(M_VALUES), k), generator=gen).to(
            torch.float16
        ).to(device)

        outputs = {}
        controls = {}
        for m in M_VALUES:
            a = a_full[:m].contiguous()
            rows = torch.tensor([m], dtype=torch.int32, device=device)
            out = torch.empty((m, n), dtype=torch.float16, device=device)
            outputs[m] = cutlass(a, weight_e, scale_e, rows, out)
            controls[m] = one_dnn(a, weight, scale)
        torch.xpu.synchronize()

        row_classes = {}
        for m, out in outputs.items():
            row_classes.setdefault(digest(out[:1]), []).append(m)

        prefix = outputs[max(M_VALUES)]
        prefix_exact = {str(m): bool(torch.equal(out, prefix[:m])) for m, out in outputs.items()}
        numeric = {
            str(m): {
                "max_abs_vs_oneDNN": max_abs(outputs[m], controls[m]),
                "mean_abs_vs_oneDNN": mean_abs(outputs[m], controls[m]),
            }
            for m in M_VALUES
        }

        perm_m = 200
        perm = torch.randperm(perm_m, generator=gen).to(device)
        perm_rows = torch.tensor([perm_m], dtype=torch.int32, device=device)
        perm_out = torch.empty((perm_m, n), dtype=torch.float16, device=device)
        permuted = cutlass(
            a_full[:perm_m][perm].contiguous(),
            weight_e,
            scale_e,
            perm_rows,
            perm_out,
        )

        repeat_out = torch.empty((perm_m, n), dtype=torch.float16, device=device)
        repeated = cutlass(
            a_full[:perm_m].contiguous(),
            weight_e,
            scale_e,
            perm_rows,
            repeat_out,
        )

        pad_m = 168
        padded_m = 200
        padded_a = torch.randn((padded_m, k), generator=gen).to(torch.float16).to(device)
        padded_a[:pad_m].copy_(a_full[:pad_m])
        padded_rows = torch.tensor([padded_m], dtype=torch.int32, device=device)
        padded_out = torch.empty((padded_m, n), dtype=torch.float16, device=device)
        padded = cutlass(
            padded_a,
            weight_e,
            scale_e,
            padded_rows,
            padded_out,
        )
        torch.xpu.synchronize()

        latency = {}
        ratios = []
        for m in TIMED_M_VALUES:
            a = a_full[:m].contiguous()
            rows = torch.tensor([m], dtype=torch.int32, device=device)
            out = torch.empty((m, n), dtype=torch.float16, device=device)
            candidate_timing = time_us(
                lambda a=a, rows=rows, out=out: cutlass(
                    a, weight_e, scale_e, rows, out
                ),
                args.warmups,
                args.iterations,
                args.repeats,
            )
            control_timing = time_us(
                lambda a=a: one_dnn(a, weight, scale),
                args.warmups,
                args.iterations,
                args.repeats,
            )
            ratio = candidate_timing["median_us"] / control_timing["median_us"]
            ratios.append(ratio)
            latency[str(m)] = {
                "cutlass": candidate_timing,
                "oneDNN": control_timing,
                "ratio": ratio,
            }

        shape_result = {
            "K": k,
            "N": n,
            "row0_classes_by_m": sorted(row_classes.values(), key=lambda x: x[0]),
            "row_invariant": len(row_classes) == 1,
            "exact_vs_m512_prefix_by_m": prefix_exact,
            "permutation_m200_exact": bool(torch.equal(permuted, outputs[perm_m][perm])),
            "permutation_m200_max_abs": max_abs(permuted, outputs[perm_m][perm]),
            "repeat_m200_exact": bool(torch.equal(repeated, outputs[perm_m])),
            "repeat_m200_max_abs": max_abs(repeated, outputs[perm_m]),
            "random_pad_content_m168_exact": bool(torch.equal(padded[:pad_m], outputs[pad_m])),
            "random_pad_content_m168_max_abs": max_abs(padded[:pad_m], outputs[pad_m]),
            "numeric_vs_oneDNN_by_m": numeric,
            "latency_us": latency,
            "latency_geomean_ratio": geomean(ratios),
            "latency_worst_ratio": max(ratios),
        }
        report["shapes"][name] = shape_result
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=1, sort_keys=True))
        print(f"[cutlass-fixed-m32] {name}: {shape_result}", flush=True)

        del outputs, controls, a_full, weight, weight_e, scale, scale_e
        torch.xpu.synchronize()
        torch.xpu.empty_cache()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
