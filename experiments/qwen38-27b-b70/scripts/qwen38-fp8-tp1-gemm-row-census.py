#!/usr/bin/env python3
"""One-card (TP1) W8A16 GEMM row-invariance census for Qwen3.8-27B FP8.

Operator diagnostic only; never a speed or quality claim.

On one B70 MTP depths 1 and 3 match no-MTP output exactly but depths 4 and 5
change three answers. A depth-d verify step runs every GEMM on d+1 rows while
no-MTP decode runs one row. This asks the production kernel directly, with
random data of the full-width (TP1) shapes: is every row r of gemm(A[:M])
bitwise equal to gemm(A[r:r+1]) for M = 1..16? The TP2 per-rank shapes are
included for contrast.

Run inside the lane image with one GPU, e.g.

  docker run --rm --workdir /tmp --device /dev/dri:/dev/dri --group-add render \
    --ipc=host --shm-size=2g --memory 8g --entrypoint python3 \
    -e ONEAPI_DEVICE_SELECTOR=level_zero:0 -e VLLM_TARGET_DEVICE=xpu \
    -v $PWD/experiments/qwen38-27b-b70/scripts:/work:ro -v $OUT:/out \
    <image> /work/qwen38-fp8-tp1-gemm-row-census.py --out /out/census.json
"""

from __future__ import annotations

import argparse
import json
import platform
from pathlib import Path

import torch

BLOCK = 128
# (K, N) from config.json: hidden 5120, intermediate 17408, 24 q heads x 256
# (+ gate), 4 kv heads x 256, GDN 16 k heads x 128 and 48 v heads x 128.
TP1 = {
    "gdn_in_proj_qkvz": (5120, 16384),
    "gdn_out_proj": (6144, 5120),
    "attn_qkv_proj": (5120, 14336),
    "attn_o_proj": (6144, 5120),
    "mlp_gate_up_proj": (5120, 34816),
    "mlp_down_proj": (17408, 5120),
}
TP2 = {
    "gdn_in_proj_qkvz": (5120, 8192),
    "gdn_out_proj": (3072, 5120),
    "attn_qkv_proj": (5120, 7168),
    "attn_o_proj": (3072, 5120),
    "mlp_gate_up_proj": (5120, 17408),
    "mlp_down_proj": (8704, 5120),
}
MAX_M = 16


def gemm(a, w_fp8, scales_t):
    return torch.ops._xpu_C.fp8_gemm_w8a16(a, w_fp8.t(), scales_t, None)


def census(k: int, n: int, device, gen) -> dict:
    w = (torch.randn((n, k), generator=gen) * 0.05).to(torch.float8_e4m3fn).to(device)
    s = (torch.rand((k // BLOCK, n // BLOCK), generator=gen) * 0.02 + 0.005).to(
        torch.float32).to(device).contiguous()
    a = torch.randn((MAX_M, k), generator=gen).to(torch.float16).to(device)
    single = [gemm(a[r:r + 1].contiguous(), w, s) for r in range(MAX_M)]
    by_m = {}
    for m in range(1, MAX_M + 1):
        out = gemm(a[:m].contiguous(), w, s)
        rows = [bool(torch.equal(out[r:r + 1], single[r])) for r in range(m)]
        worst = max(float((out[r:r + 1].float() - single[r].float()).abs().max())
                    for r in range(m))
        by_m[m] = {"all_rows_equal_single_row": all(rows),
                   "rows_equal": rows, "max_abs": worst}
    # Float32 dequantized reference: catches a strategy that is invariant but wrong.
    w_deq = w.float() * s.t().repeat_interleave(BLOCK, 0).repeat_interleave(BLOCK, 1)
    ref = a.float() @ w_deq.t()
    got = gemm(a.contiguous(), w, s).float()
    rel = float(((got - ref).abs().max() / ref.abs().max()).item())
    return {"shape": {"K": k, "N": n}, "by_M": by_m,
            "max_rel_err_vs_float32_reference": rel,
            "M_matching_single_row": [m for m, v in by_m.items()
                                      if v["all_rows_equal_single_row"]]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260915)
    args = parser.parse_args()
    import vllm  # noqa: F401
    import vllm._xpu_ops  # noqa: F401
    import vllm_xpu_kernels._xpu_C  # noqa: F401

    device = torch.device("xpu:0")
    gen = torch.Generator(device="cpu").manual_seed(args.seed)
    report = {
        "schema": "neural.download.qwen38-fp8-tp1-gemm-row-census.v1",
        "classification": "operator-diagnostic-only",
        "environment": {"device": torch.xpu.get_device_properties(0).name,
                        "torch": torch.__version__,
                        "vllm": getattr(vllm, "__version__", None),
                        "python": platform.python_version(), "seed": args.seed},
        "tp1": {}, "tp2": {},
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    for label, shapes in (("tp1", TP1), ("tp2", TP2)):
        for name, (k, n) in shapes.items():
            report[label][name] = census(k, n, device, gen)
            torch.xpu.empty_cache()
            args.out.write_text(json.dumps(report, indent=1, sort_keys=True))
            print(f"[{label}] {name}: M matching single row = "
                  f"{report[label][name]['M_matching_single_row']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
