#!/usr/bin/env python3
"""Gate the R142 direct-grid K8-reduction W8A16 prototype."""

from __future__ import annotations

import argparse
import hashlib
import json
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


def one_dnn(a, weight, scale):
    return torch.ops._xpu_C.fp8_gemm_w8a16(a, weight, scale, None)


def candidate(a, weight_e, scale_e, rows, out):
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260902)
    parser.add_argument("--warmups", type=int, default=10)
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()

    import vllm_xpu_kernels._xpu_C  # noqa: F401

    if not torch.xpu.is_available():
        raise SystemExit("XPU is required")
    device = torch.device("xpu:0")
    gen = torch.Generator(device="cpu").manual_seed(args.seed)
    report = {
        "schema": "neural.download.qwen38-fp8-w8a16-k8-split-r142.v1",
        "classification": "operator-diagnostic-only",
        "environment": {
            "device": torch.xpu.get_device_name(0),
            "torch": torch.__version__,
            "seed": args.seed,
        },
        "candidate": {
            "tile_mnk": [16, 64, 512],
            "subgroup_layout_mnk": [1, 4, 8],
            "k_interleave": 64,
            "reduction_order": "ascending",
            "weight_layout": "production NT view [1,K,N], strides [*,1,K]",
        },
        "reference": (
            "Concatenated natural oneDNN M1 calls. R141 directly proved this "
            "equals the row-invariant forced source-M4 strategy on both shapes."
        ),
        "m_values": M_VALUES,
        "timed_m_values": TIMED_MS,
        "shapes": {},
    }

    for name, (k, n) in SHAPES.items():
        weight_nk = (torch.randn((n, k), generator=gen) * 0.05).to(
            torch.float8_e4m3fn
        ).to(device)
        weight = weight_nk.t()
        weight_e = weight.unsqueeze(0)
        scale = (
            torch.rand((k // 128, n // 128), generator=gen) * 0.02 + 0.005
        ).to(torch.float32).to(device).contiguous()
        scale_e = scale.unsqueeze(0)
        a_full = torch.randn((max(M_VALUES), k), generator=gen).to(
            torch.float16
        ).to(device)

        reference = torch.cat(
            [one_dnn(a_full[row : row + 1], weight, scale) for row in range(512)],
            dim=0,
        )
        outputs = {}
        controls = {}
        for m in M_VALUES:
            a = a_full[:m].contiguous()
            rows = torch.tensor([m], dtype=torch.int32, device=device)
            out = torch.empty((m, n), dtype=torch.float16, device=device)
            outputs[m] = candidate(a, weight_e, scale_e, rows, out)
            controls[m] = one_dnn(a, weight, scale)
        torch.xpu.synchronize()

        exact_reference = {
            str(m): bool(torch.equal(outputs[m], reference[:m]))
            for m in M_VALUES
        }
        max_abs_reference = {
            str(m): max_abs(outputs[m], reference[:m]) for m in M_VALUES
        }
        output_digests = {str(m): digest(outputs[m]) for m in M_VALUES}

        perm_m = 128
        perm = torch.randperm(perm_m, generator=gen).to(device)
        perm_rows = torch.tensor([perm_m], dtype=torch.int32, device=device)
        perm_out = torch.empty((perm_m, n), dtype=torch.float16, device=device)
        permuted = candidate(
            a_full[:perm_m][perm].contiguous(),
            weight_e,
            scale_e,
            perm_rows,
            perm_out,
        )

        repeat_out = torch.empty((perm_m, n), dtype=torch.float16, device=device)
        repeated = candidate(
            a_full[:perm_m].contiguous(),
            weight_e,
            scale_e,
            perm_rows,
            repeat_out,
        )

        pad_m = 168
        padded_m = 200
        padded_a = torch.randn((padded_m, k), generator=gen).to(
            torch.float16
        ).to(device)
        padded_a[:pad_m].copy_(a_full[:pad_m])
        padded_rows = torch.tensor([padded_m], dtype=torch.int32, device=device)
        padded_out = torch.empty(
            (padded_m, n), dtype=torch.float16, device=device
        )
        padded = candidate(
            padded_a, weight_e, scale_e, padded_rows, padded_out
        )
        torch.xpu.synchronize()

        latency = {}
        for m in TIMED_MS:
            a = a_full[:m].contiguous()
            rows = torch.tensor([m], dtype=torch.int32, device=device)
            out = torch.empty((m, n), dtype=torch.float16, device=device)
            candidate_timing = timed_us(
                lambda a=a, rows=rows, out=out: candidate(
                    a, weight_e, scale_e, rows, out
                ),
                args.warmups,
                args.iterations,
                args.repeats,
            )
            control_timing = timed_us(
                lambda a=a: one_dnn(a, weight, scale),
                args.warmups,
                args.iterations,
                args.repeats,
            )
            latency[str(m)] = {
                "candidate": candidate_timing,
                "oneDNN_natural": control_timing,
                "ratio": (
                    candidate_timing["median_us"]
                    / control_timing["median_us"]
                ),
            }

        shape_result = {
            "K": k,
            "N": n,
            "reference_m512_sha256": digest(reference),
            "candidate_sha256_by_m": output_digests,
            "exact_vs_natural_m1_rows_by_m": exact_reference,
            "max_abs_vs_natural_m1_rows_by_m": max_abs_reference,
            "all_exact_vs_natural_m1_rows": all(exact_reference.values()),
            "all_exact_vs_m512_prefix": all(
                torch.equal(outputs[m], outputs[512][:m]) for m in M_VALUES
            ),
            "permutation_m128_exact": bool(
                torch.equal(permuted, reference[:perm_m][perm])
            ),
            "repeat_m128_exact": bool(torch.equal(repeated, outputs[perm_m])),
            "random_pad_content_m168_exact": bool(
                torch.equal(padded[:pad_m], reference[:pad_m])
            ),
            "max_abs_vs_natural_oneDNN_batch_by_m": {
                str(m): max_abs(outputs[m], controls[m]) for m in M_VALUES
            },
            "latency_us": latency,
        }
        report["shapes"][name] = shape_result
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
        print(f"[r142] {name}: {shape_result}", flush=True)

        del outputs, controls, reference, a_full, weight, weight_e, weight_nk
        del scale, scale_e
        torch.xpu.synchronize()
        torch.xpu.empty_cache()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
