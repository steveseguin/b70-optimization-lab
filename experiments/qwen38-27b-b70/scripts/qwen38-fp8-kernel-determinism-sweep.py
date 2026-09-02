#!/usr/bin/env python3
"""Repeat-determinism sweep of the production XPU GEMMs across M.

Operator diagnostic only. For every per-rank TP2 W8A16 shape, and for the FP16
lm_head matmul that the checkpoint actually uses (lm_head.weight has no FP8
scale), call the kernel five times on identical inputs for M = 1..512 and record
every M at which the outputs are not bitwise identical. Also records the FP16
lm_head row-invariance classes across M, since the W8A16 lm_head row of the main
census does not represent the production head.
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
}
BLOCK = 128
M_SWEEP = sorted(set(list(range(1, 65)) + list(range(64, 513, 8)) + [59, 96, 100, 120, 200, 250, 255, 256, 257, 300, 384, 500, 512]))


def gemm(a, w_fp8, scales_t):
    return torch.ops._xpu_C.fp8_gemm_w8a16(a, w_fp8.t(), scales_t, None)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260902)
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()
    import vllm  # noqa: F401
    import vllm._xpu_ops  # noqa: F401
    import vllm_xpu_kernels._xpu_C  # noqa: F401  (registers _xpu_C ops)

    device = torch.device("xpu:0")
    gen = torch.Generator(device="cpu").manual_seed(args.seed)
    report = {
        "schema": "neural.download.qwen38-fp8-kernel-determinism-sweep.v1",
        "repeats_per_M": args.repeats,
        "M_sweep": M_SWEEP,
        "w8a16": {},
    }
    a_full = torch.randn((512, 8704), generator=gen, device="cpu").to(torch.float16).to(device)
    for name, (k, n) in GEMMS.items():
        w = (torch.randn((n, k), generator=gen, device="cpu") * 0.05).to(torch.float8_e4m3fn).to(device)
        s = (torch.rand((k // BLOCK, n // BLOCK), generator=gen, device="cpu") * 0.02 + 0.005).to(torch.float32).to(device).contiguous()
        nondet = {}
        for m in M_SWEEP:
            x = a_full[:m, :k].contiguous()
            ref = gemm(x, w, s)
            worst = 0.0
            bad = 0
            for _ in range(args.repeats - 1):
                out = gemm(x, w, s)
                if not torch.equal(out, ref):
                    bad += 1
                    worst = max(worst, float((out.float() - ref.float()).abs().max().item()))
            if bad:
                nondet[m] = {"nonidentical_repeats": bad, "max_abs": worst}
        report["w8a16"][name] = {"nondeterministic_M": nondet, "nondeterministic_M_count": len(nondet)}
        print(f"[sweep] {name}: nondeterministic M = {sorted(nondet)}", flush=True)
        del w, s
        torch.xpu.synchronize()
        torch.xpu.empty_cache()

    # Production FP16 lm_head path: F.linear(hidden, weight) with weight [N, K].
    k, n = 5120, 124160
    w16 = (torch.randn((n, k), generator=gen, device="cpu") * 0.02).to(torch.float16).to(device)
    head_nondet = {}
    row0 = {}
    for m in M_SWEEP:
        x = a_full[:m, :k].contiguous()
        ref = torch.nn.functional.linear(x, w16)
        bad = 0
        worst = 0.0
        for _ in range(args.repeats - 1):
            out = torch.nn.functional.linear(x, w16)
            if not torch.equal(out, ref):
                bad += 1
                worst = max(worst, float((out.float() - ref.float()).abs().max().item()))
        if bad:
            head_nondet[m] = {"nonidentical_repeats": bad, "max_abs": worst}
        row0[m] = ref[0:1].clone()
    classes: dict[str, list[int]] = {}
    import hashlib
    for m in M_SWEEP:
        key = hashlib.sha256(row0[m].contiguous().view(torch.uint8).cpu().numpy().tobytes()).hexdigest()
        classes.setdefault(key, []).append(m)
    report["fp16_lm_head_linear"] = {
        "shape_per_rank": {"K": k, "N": n},
        "nondeterministic_M": head_nondet,
        "row0_invariance_classes_by_M": sorted(classes.values(), key=lambda ms: ms[0]),
    }
    print(f"[sweep] fp16 lm_head: nondeterministic M = {sorted(head_nondet)}; classes = {report['fp16_lm_head_linear']['row0_invariance_classes_by_M']}", flush=True)
    args.out.write_text(json.dumps(report, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
