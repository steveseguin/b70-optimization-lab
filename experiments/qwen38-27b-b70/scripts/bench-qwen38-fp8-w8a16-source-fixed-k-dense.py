#!/usr/bin/env python3
"""Dense row-invariance and latency gate for the R137 source selector."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from pathlib import Path

import torch


SHAPES = {
    "gdn_in_proj_qkvz": (5120, 8192),
    "gdn_out_proj": (3072, 5120),
    "attn_qkv_proj": (5120, 7168),
    "attn_o_proj": (3072, 5120),
    "mlp_gate_up_proj": (5120, 17408),
    "mlp_down_proj": (8704, 5120),
}
REGISTERED_MS = [1, 2, 4, 8, 16, 32, 64, 128, 168, 200, 224, 250, 256, 300, 512]
PERMUTATION_MS = [2, 63, 64, 65, 127, 128, 129, 168, 200, 256, 511, 512]
TIMED_MS = [2, 4, 8, 16, 32, 64, 128, 168, 256, 512]


def gemm(a: torch.Tensor, weight: torch.Tensor, scale: torch.Tensor) -> torch.Tensor:
    return torch.ops._xpu_C.fp8_gemm_w8a16(a, weight, scale, None)


def digest(tensor: torch.Tensor) -> str:
    data = tensor.detach().contiguous().view(torch.uint8).cpu().numpy().tobytes()
    return hashlib.sha256(data).hexdigest()


def max_abs(a: torch.Tensor, b: torch.Tensor) -> float:
    return float((a.float() - b.float()).abs().max().item())


def time_us(fn, warmups: int, iterations: int, repeats: int) -> dict:
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
        "samples_us": samples,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shape", choices=sorted(SHAPES), required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260902)
    parser.add_argument("--max-m", type=int, default=512)
    parser.add_argument("--warmups", type=int, default=10)
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--skip-timing", action="store_true")
    args = parser.parse_args()

    if args.max_m != 512:
        raise SystemExit("R137 is preregistered for exactly M=1..512")

    import vllm_xpu_kernels._xpu_C  # noqa: F401

    if not torch.xpu.is_available():
        raise SystemExit("XPU is required")
    reference = json.loads(args.reference.read_text())
    k, n = SHAPES[args.shape]
    if reference.get("K") != k or reference.get("N") != n:
        raise SystemExit("reference shape does not match --shape")

    device = torch.device("xpu:0")
    gen = torch.Generator(device="cpu").manual_seed(args.seed)
    weight_nk = (torch.randn((n, k), generator=gen) * 0.05).to(
        torch.float8_e4m3fn
    ).to(device)
    weight = weight_nk.t()
    scale = (
        torch.rand((k // 128, n // 128), generator=gen) * 0.02 + 0.005
    ).to(torch.float32).to(device).contiguous()
    a_full = torch.randn((args.max_m, k), generator=gen).to(torch.float16).to(device)

    largest = gemm(a_full, weight, scale)
    torch.xpu.synchronize()
    largest_row0 = digest(largest[:1])
    prefix_failures = []
    repeat_failures = []
    registered_output_sha256 = {}
    registered_row0_sha256 = {}

    for m in range(1, args.max_m + 1):
        print(f"R137_DENSE before shape={args.shape} M={m}", flush=True)
        output = largest if m == args.max_m else gemm(a_full[:m], weight, scale)
        repeated = gemm(a_full[:m], weight, scale)
        torch.xpu.synchronize()
        expected = largest[:m]
        if not torch.equal(output, expected):
            prefix_failures.append({"m": m, "max_abs": max_abs(output, expected)})
        if not torch.equal(repeated, output):
            repeat_failures.append({"m": m, "max_abs": max_abs(repeated, output)})
        if m in REGISTERED_MS:
            registered_output_sha256[str(m)] = digest(output)
            registered_row0_sha256[str(m)] = digest(output[:1])
        print(f"R137_DENSE after shape={args.shape} M={m}", flush=True)

    permutation_failures = []
    for m in PERMUTATION_MS:
        perm = torch.randperm(m, generator=gen).to(device)
        permuted = gemm(a_full[:m][perm], weight, scale)
        restored = permuted[torch.argsort(perm)]
        torch.xpu.synchronize()
        if not torch.equal(restored, largest[:m]):
            permutation_failures.append(
                {"m": m, "max_abs": max_abs(restored, largest[:m])}
            )

    padded_source = torch.zeros((200, k), dtype=torch.float16, device=device)
    padded_source[:168].copy_(a_full[:168])
    padded = gemm(padded_source, weight, scale)
    direct168 = gemm(a_full[:168], weight, scale)
    torch.xpu.synchronize()
    padding_exact = bool(torch.equal(padded[:168], direct168))

    reference_outputs = reference["output_sha256_by_m"]
    reference_rows = reference["row0_sha256_by_m"]
    cross_output_failures = {
        m: {"candidate": value, "reference": reference_outputs.get(m)}
        for m, value in registered_output_sha256.items()
        if value != reference_outputs.get(m)
    }
    cross_row0_failures = {
        m: {"candidate": value, "reference": reference_rows.get(m)}
        for m, value in registered_row0_sha256.items()
        if value != reference_rows.get(m)
    }

    timings = {}
    if not args.skip_timing:
        for m in TIMED_MS:
            timings[str(m)] = time_us(
                lambda m=m: gemm(a_full[:m], weight, scale),
                args.warmups,
                args.iterations,
                args.repeats,
            )

    report = {
        "schema": "neural.download.qwen38-fp8-w8a16-source-fixed-k-dense.v1",
        "classification": "source-selector-operator-gate",
        "shape": args.shape,
        "K": k,
        "N": n,
        "m_range": [1, args.max_m],
        "device": torch.xpu.get_device_name(0),
        "torch": torch.__version__,
        "seed": args.seed,
        "largest_row0_sha256": largest_row0,
        "all_dense_prefix_exact": not prefix_failures,
        "dense_prefix_failures": prefix_failures,
        "all_dense_repeat_exact": not repeat_failures,
        "dense_repeat_failures": repeat_failures,
        "permutation_ms": PERMUTATION_MS,
        "all_permutations_exact": not permutation_failures,
        "permutation_failures": permutation_failures,
        "padding_168_to_200_exact": padding_exact,
        "padding_168_to_200_max_abs": max_abs(padded[:168], direct168),
        "registered_output_sha256": registered_output_sha256,
        "registered_row0_sha256": registered_row0_sha256,
        "all_registered_outputs_match_r134_m32": not cross_output_failures,
        "registered_output_mismatches": cross_output_failures,
        "all_registered_rows_match_r134_m32": not cross_row0_failures,
        "registered_row0_mismatches": cross_row0_failures,
        "latency_us": timings,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1, sort_keys=True))
    print(json.dumps(report, sort_keys=True), flush=True)
    return 0 if all(
        [
            report["all_dense_prefix_exact"],
            report["all_dense_repeat_exact"],
            report["all_permutations_exact"],
            report["padding_168_to_200_exact"],
            report["all_registered_outputs_match_r134_m32"],
            report["all_registered_rows_match_r134_m32"],
        ]
    ) else 2


if __name__ == "__main__":
    raise SystemExit(main())
