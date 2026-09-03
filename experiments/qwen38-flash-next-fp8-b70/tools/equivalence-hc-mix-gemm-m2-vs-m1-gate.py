#!/usr/bin/env python3
"""Rare-flip search: hyperconnection mix GEMMs at M=2 versus M=1 (BF16, oneDNN).

The Flash-Next hyperconnection mix runs two unquantized BF16 linears per
block: down_block_inject [M,10240] x [10240,352] and up [M,320] x [320,10240]
(TP4 identical on every rank). Runs F.linear as ReplicatedLinear does, with
torch.backends.mkldnn.deterministic, on a two-row batch and on each row
alone for many random draws, and counts trials with any bit difference.
A rare flip here explains an MTP1 verification step diverging from MTP0 at
one layer after dozens of exact ones.

    equivalence-hc-mix-gemm-m2-vs-m1-gate.py --out <json> [--trials 300]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys


def refuse_active_model_server() -> None:
    out = subprocess.run(["ps", "-eo", "args"], capture_output=True, text=True).stdout
    if any(("EngineCore" in l or "Worker_TP" in l or "vllm serve" in l) for l in out.splitlines()):
        sys.exit("refusing to run beside a model server")


SHAPES = [
    ("hc-down-block-inject", 10240, 352),
    ("hc-up", 320, 10240),
    ("hc-down-no-inject", 10240, 320),
    ("gdn-in_proj_ba", 2560, 24),
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True)
    ap.add_argument("--trials", type=int, default=300)
    ap.add_argument("--rows", type=int, default=2)
    ap.add_argument("--seed", type=int, default=20260903)
    args = ap.parse_args()
    refuse_active_model_server()
    import torch
    import torch.nn.functional as F
    torch.backends.mkldnn.deterministic = True
    device = torch.device("xpu:0")
    torch.xpu.set_device(device)
    g = torch.Generator(device="cpu").manual_seed(args.seed)
    shapes_out = []
    for label, K, N in SHAPES:
        w = (torch.randn(N, K, generator=g) * (1.0 / K ** 0.5)).to(torch.bfloat16).to(device)
        flips, first_flip, max_abs, unrepeatable = 0, None, 0.0, 0
        for t in range(args.trials):
            x = torch.randn(args.rows, K, generator=g).to(torch.bfloat16).to(device)
            batched = F.linear(x, w); batched2 = F.linear(x, w)
            singles = torch.cat([F.linear(x[i:i + 1], w) for i in range(args.rows)], 0)
            torch.xpu.synchronize()
            if not torch.equal(batched, batched2):
                unrepeatable += 1
            if not torch.equal(batched, singles):
                flips += 1
                d = (batched.float() - singles.float()).abs()
                max_abs = max(max_abs, float(d.max()))
                if first_flip is None:
                    first_flip = {"trial": t, "elements_differing": int((d > 0).sum()),
                                  "rows_differing": [int(i) for i in range(args.rows) if bool((d[i] > 0).any())]}
        rec = {"label": label, "K": K, "N": N, "trials": args.trials, "trials_with_flip": flips,
               "unrepeatable_trials": unrepeatable, "max_abs_diff": max_abs, "first_flip": first_flip}
        shapes_out.append(rec)
        print(json.dumps(rec))
    result = {"schema_version": 1, "classification": "b70_bf16_hc_mix_gemm_m2_vs_m1_rare_flip_search",
              "torch": torch.__version__, "device": torch.xpu.get_device_name(0), "mkldnn_deterministic": True,
              "seed": args.seed, "rows": args.rows, "shapes": shapes_out,
              "all_bit_identical": all(s["trials_with_flip"] == 0 for s in shapes_out)}
    with open(args.out, "w") as f:
        json.dump(result, f, indent=2)
    print("ALL_BIT_IDENTICAL" if result["all_bit_identical"] else "FLIPS_FOUND")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
