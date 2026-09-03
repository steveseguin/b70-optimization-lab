#!/usr/bin/env python3
"""Does a two-row BF16 GEMM on the B70 equal two one-row GEMMs, bit for bit?

The MTP1 verification step feeds two rows through every dense projection
that single-row decode feeds one row at a time. oneDNN selects kernels by
shape, so the per-row reduction order may differ between M=1 and M=2. This
gate multiplies the same rows through the same weights both ways at the
shapes the Flash-Next decode step uses (the layer-0 hyperconnection mix
K=10240 among them) with ``torch.backends.mkldnn.deterministic`` on, and
reports the largest absolute and relative difference per shape, plus whether
each shape is repeatable on its own. Runs on one card; refuses to run beside
a model server.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys

import torch

SHAPES = [
    # (K, N, label) : decode-step dense projections of the TP4 rank slice
    (10240, 10240, "hyperconnection-mix-K10240"),
    (2048, 5120, "hidden-to-qkv-like"),
    (5120, 2048, "o-proj-like"),
    (2048, 2048, "square-2048"),
    (2048, 640, "moe-w13-slice-N640"),
    (2048, 8192, "dense-up-8192"),
]


def refuse_active_model_server() -> None:
    out = subprocess.run(["ps", "-eo", "args"], capture_output=True, text=True).stdout
    if any(("EngineCore" in line or "Worker_TP" in line or "vllm serve" in line) for line in out.splitlines()):
        sys.exit("refusing to run beside a model server")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=20260903)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    refuse_active_model_server()
    torch.backends.mkldnn.deterministic = True
    device = torch.device("xpu:0")
    torch.xpu.set_device(device)
    g = torch.Generator(device="cpu").manual_seed(args.seed)
    results = []
    for K, N, label in SHAPES:
        w = (torch.randn(K, N, generator=g) * (1.0 / K**0.5)).to(torch.bfloat16).to(device)
        x2 = torch.randn(2, K, generator=g).to(torch.bfloat16).to(device)
        y2 = x2 @ w
        y_rows = torch.cat([x2[0:1] @ w, x2[1:2] @ w], dim=0)
        torch.xpu.synchronize()
        diff = (y2.float() - y_rows.float()).abs()
        rel = diff / y_rows.float().abs().clamp_min(1e-6)
        # self-repeatability of each path
        rep2 = all(torch.equal(x2 @ w, y2) for _ in range(args.repeats))
        rep1 = all(torch.equal(x2[0:1] @ w, y_rows[0:1]) for _ in range(args.repeats))
        torch.xpu.synchronize()
        results.append({
            "label": label, "K": K, "N": N,
            "bit_identical": bool(torch.equal(y2, y_rows)),
            "elements_differing": int((diff > 0).sum()),
            "max_abs_diff": float(diff.max()),
            "max_rel_diff": float(rel.max()),
            "mean_abs_diff": float(diff.mean()),
            "m2_repeatable": rep2, "m1_repeatable": rep1,
        })
        print(json.dumps(results[-1]))
    payload = {
        "schema_version": 1, "classification": "b70_bf16_gemm_m2_vs_m1_equivalence",
        "torch": torch.__version__, "device": torch.xpu.get_device_name(0),
        "mkldnn_deterministic": torch.backends.mkldnn.deterministic, "seed": args.seed,
        "shapes": results,
        "all_bit_identical": all(r["bit_identical"] for r in results),
    }
    with open(args.out, "w") as f:
        json.dump(payload, f, indent=2)
    print("all_bit_identical", payload["all_bit_identical"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
