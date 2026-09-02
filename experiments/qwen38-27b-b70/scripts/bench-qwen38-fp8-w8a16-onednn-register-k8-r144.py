#!/usr/bin/env python3
"""Gate the R144 oneDNN register-interleaved K8 reduction."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
from pathlib import Path

import torch


SHAPES = {
    "attn_qkv_proj": (5120, 7168),
    "mlp_gate_up_proj": (5120, 17408),
}
M_VALUES = [1, 2, 4, 8, 16, 32, 64, 128, 168, 200, 256, 512]
TIMED_MS = [2, 64, 128, 168, 256]


def digest(tensor: torch.Tensor) -> str:
    data = tensor.detach().contiguous().view(torch.uint8).cpu().numpy().tobytes()
    return hashlib.sha256(data).hexdigest()


def max_abs(a: torch.Tensor, b: torch.Tensor) -> float:
    return float((a.float() - b.float()).abs().max().item())


def timed_us(fn, warmups: int, iterations: int, repeats: int) -> dict:
    for _ in range(warmups):
        fn()
    torch.xpu.synchronize()
    samples = []
    stream = torch.xpu.current_stream()
    for _ in range(repeats):
        start = torch.xpu.Event(enable_timing=True)
        end = torch.xpu.Event(enable_timing=True)
        start.record(stream)
        for _ in range(iterations):
            fn()
        end.record(stream)
        end.synchronize()
        samples.append(start.elapsed_time(end) * 1000.0 / iterations)
    return {
        "median_us": statistics.median(samples),
        "min_us": min(samples),
        "max_us": max(samples),
        "max_min_ratio": max(samples) / min(samples),
        "samples_us": samples,
    }


def gemm(a, weight, scale):
    return torch.ops._xpu_C.fp8_gemm_w8a16(a, weight, scale, None)


def make_inputs(name: str, k: int, n: int, seed: int, device):
    shape_index = list(SHAPES).index(name)
    gen = torch.Generator(device="cpu").manual_seed(seed + shape_index * 1000)
    weight_nk = (torch.randn((n, k), generator=gen) * 0.05).to(
        torch.float8_e4m3fn
    ).to(device)
    weight = weight_nk.t()
    scale = (
        torch.rand((k // 128, n // 128), generator=gen) * 0.02 + 0.005
    ).to(torch.float32).to(device).contiguous()
    a_full = torch.randn((max(M_VALUES), k), generator=gen).to(
        torch.float16
    ).to(device)
    return gen, weight_nk, weight, scale, a_full


def save_report(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("natural", "candidate"), required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--reference-dir", type=Path, required=True)
    parser.add_argument("--natural-json", type=Path)
    parser.add_argument("--seed", type=int, default=20260902)
    parser.add_argument("--warmups", type=int, default=10)
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()

    if args.mode == "candidate" and args.natural_json is None:
        parser.error("--natural-json is required in candidate mode")
    if args.mode == "natural" and os.environ.get("GEMM_KERNEL"):
        raise SystemExit("natural mode requires GEMM_KERNEL to be unset")
    if args.mode == "candidate" and not os.environ.get("GEMM_KERNEL"):
        raise SystemExit("candidate mode requires GEMM_KERNEL")

    import vllm_xpu_kernels._xpu_C  # noqa: F401

    if not torch.xpu.is_available():
        raise SystemExit("XPU is required")
    device = torch.device("xpu:0")
    natural_report = None
    if args.natural_json:
        natural_report = json.loads(args.natural_json.read_text())
    args.reference_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "schema": "neural.download.qwen38-fp8-w8a16-onednn-register-k8-r144.v1",
        "classification": "operator-diagnostic-only",
        "mode": args.mode,
        "environment": {
            "device": torch.xpu.get_device_name(0),
            "torch": torch.__version__,
            "seed": args.seed,
            "gemm_kernel_override": os.environ.get("GEMM_KERNEL"),
        },
        "reference": "Concatenated natural oneDNN M1 rows saved by natural mode.",
        "m_values": M_VALUES,
        "timed_m_values": TIMED_MS,
        "shapes": {},
    }

    for name, (k, n) in SHAPES.items():
        gen, weight_nk, weight, scale, a_full = make_inputs(
            name, k, n, args.seed, device
        )
        reference_path = args.reference_dir / f"{name}-natural-m1-rows.pt"

        if args.mode == "natural":
            reference = torch.cat(
                [gemm(a_full[row : row + 1], weight, scale) for row in range(512)],
                dim=0,
            )
            torch.xpu.synchronize()
            torch.save(reference.cpu(), reference_path)
        else:
            reference = torch.load(
                reference_path, map_location="cpu", weights_only=True
            ).to(device)

        outputs = {m: gemm(a_full[:m], weight, scale) for m in M_VALUES}
        torch.xpu.synchronize()

        latency = {}
        for m in TIMED_MS:
            timing = timed_us(
                lambda m=m: gemm(a_full[:m], weight, scale),
                args.warmups,
                args.iterations,
                args.repeats,
            )
            if natural_report is not None:
                natural_median = natural_report["shapes"][name]["latency_us"][
                    str(m)
                ]["median_us"]
                timing["ratio_vs_natural"] = timing["median_us"] / natural_median
            latency[str(m)] = timing

        exact_reference = {
            str(m): bool(torch.equal(outputs[m], reference[:m]))
            for m in M_VALUES
        }
        max_abs_reference = {
            str(m): max_abs(outputs[m], reference[:m]) for m in M_VALUES
        }

        shape_result = {
            "K": k,
            "N": n,
            "reference_path": str(reference_path),
            "reference_m512_sha256": digest(reference),
            "output_sha256_by_m": {
                str(m): digest(outputs[m]) for m in M_VALUES
            },
            "exact_vs_natural_m1_rows_by_m": exact_reference,
            "max_abs_vs_natural_m1_rows_by_m": max_abs_reference,
            "all_exact_vs_natural_m1_rows": all(exact_reference.values()),
            "all_exact_vs_m512_prefix": all(
                torch.equal(outputs[m], outputs[512][:m]) for m in M_VALUES
            ),
            "latency_us": latency,
        }

        if args.mode == "candidate":
            perm_m = 128
            perm = torch.randperm(perm_m, generator=gen).to(device)
            permuted = gemm(a_full[:perm_m][perm].contiguous(), weight, scale)
            repeated = gemm(a_full[:perm_m], weight, scale)
            padded_a = torch.randn((200, k), generator=gen).to(
                torch.float16
            ).to(device)
            padded_a[:168].copy_(a_full[:168])
            padded = gemm(padded_a, weight, scale)
            torch.xpu.synchronize()
            shape_result.update(
                {
                    "permutation_m128_exact": bool(
                        torch.equal(permuted, reference[:perm_m][perm])
                    ),
                    "permutation_m128_max_abs": max_abs(
                        permuted, reference[:perm_m][perm]
                    ),
                    "repeat_m128_exact": bool(
                        torch.equal(repeated, outputs[perm_m])
                    ),
                    "repeat_m128_max_abs": max_abs(repeated, outputs[perm_m]),
                    "random_pad_content_m168_exact": bool(
                        torch.equal(padded[:168], reference[:168])
                    ),
                    "random_pad_content_m168_max_abs": max_abs(
                        padded[:168], reference[:168]
                    ),
                }
            )

        report["shapes"][name] = shape_result
        save_report(args.out, report)
        print(f"[r144:{args.mode}] {name}: {shape_result}", flush=True)

        del outputs, reference, a_full, weight, weight_nk, scale
        torch.xpu.synchronize()
        torch.xpu.empty_cache()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
