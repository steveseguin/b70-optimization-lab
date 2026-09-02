#!/usr/bin/env python3
"""Follow-up to the kernel batch-invariance census: bucket boundary and anomaly checks.

Operator diagnostic only. Re-tests (1) whether real rows of a padded W8A16 GEMM
depend on pad contents (seen once for attn_qkv at M=256), separating true data
dependence from nondeterminism by repeating each call; (2) position invariance at
the candidate decode bucket sizes 16, 24, 32, 40, 48; (3) repeat determinism at
M=256/512.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch

GEMMS = {
    "gdn_in_proj_qkvz": (5120, 8192),
    "gdn_out_proj": (3072, 5120),
    "attn_qkv_proj": (5120, 7168),
    "attn_o_proj": (3072, 5120),
    "mlp_gate_up_proj": (5120, 17408),
    "mlp_down_proj": (8704, 5120),
    "lm_head": (5120, 124160),
}
BLOCK = 128


def gemm(a, w_fp8, scales_t):
    return torch.ops._xpu_C.fp8_gemm_w8a16(a, w_fp8.t(), scales_t, None)


def max_abs(a, b):
    return float((a.float() - b.float()).abs().max().item())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260902)
    args = parser.parse_args()
    import vllm  # noqa: F401
    import vllm._xpu_ops  # noqa: F401

    device = torch.device("xpu:0")
    gen = torch.Generator(device="cpu").manual_seed(args.seed)
    report = {"schema": "neural.download.qwen38-fp8-kernel-batch-invariance-census-followup.v1"}
    for name, (k, n) in GEMMS.items():
        w = (torch.randn((n, k), generator=gen, device="cpu") * 0.05).to(torch.float8_e4m3fn).to(device)
        s = (torch.rand((k // BLOCK, n // BLOCK), generator=gen, device="cpu") * 0.02 + 0.005).to(torch.float32).to(device).contiguous()
        a_full = torch.randn((512, k), generator=gen, device="cpu").to(torch.float16).to(device)
        entry = {}
        # (1) pad-content dependence with repeats
        real_m = 31
        pad_dep = {}
        for bucket in (64, 128, 256, 512):
            variants = []
            for trial in range(3):
                pad = torch.randn((bucket, k), generator=gen, device="cpu").to(torch.float16).to(device)
                pad[:real_m] = a_full[:real_m]
                outs = [gemm(pad, w, s)[:real_m].clone() for _ in range(3)]
                variants.append(outs)
            repeat_ok = all(torch.equal(v[0], v[i]) for v in variants for i in (1, 2))
            content_ok = all(torch.equal(variants[0][0], v[0]) for v in variants[1:])
            pad_dep[bucket] = {
                "repeat_deterministic": repeat_ok,
                "real_rows_independent_of_pad_contents": content_ok,
                "max_abs_across_pad_contents": max(max_abs(variants[0][0], v[0]) for v in variants[1:]),
            }
        entry["pad_content_dependence_M31"] = pad_dep
        # (2) position invariance at candidate decode buckets
        pos = {}
        for m in (16, 24, 32, 40, 48, 56, 59, 64):
            x = a_full[:m].contiguous()
            out_x = gemm(x, w, s)
            ok = True
            worst = 0.0
            for _ in range(3):
                perm = torch.randperm(m, generator=gen).to(device)
                out_p = gemm(x[perm].contiguous(), w, s)
                ok = ok and bool(torch.equal(out_p, out_x[perm]))
                worst = max(worst, max_abs(out_p, out_x[perm]))
            pos[m] = {"permutation_invariant_3_perms": ok, "max_abs": worst}
        entry["position_invariance"] = pos
        # (3) determinism at large M
        entry["repeat_deterministic_large_M"] = {
            m: bool(torch.equal(gemm(a_full[:m].contiguous(), w, s), gemm(a_full[:m].contiguous(), w, s)))
            for m in (256, 512)
        }
        # (4) class membership of M=32 and M=48 relative to M=2 and M=16
        base2 = gemm(a_full[:2].contiguous(), w, s)[0:1]
        base16 = gemm(a_full[:16].contiguous(), w, s)[0:1]
        entry["row0_class_vs_M2_and_M16"] = {
            m: {
                "equals_M2": bool(torch.equal(gemm(a_full[:m].contiguous(), w, s)[0:1], base2)),
                "equals_M16": bool(torch.equal(gemm(a_full[:m].contiguous(), w, s)[0:1], base16)),
            }
            for m in (9, 10, 11, 12, 16, 20, 24, 32, 40, 48, 56)
        }
        report[name] = entry
        print(f"[followup] {name}: pos32={pos[32]['permutation_invariant_3_perms']} pos48={pos[48]['permutation_invariant_3_perms']} pad256={pad_dep[256]}", flush=True)
        del w, s, a_full
        torch.xpu.synchronize()
        torch.xpu.empty_cache()
    args.out.write_text(json.dumps(report, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
