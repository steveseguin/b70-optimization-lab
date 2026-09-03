#!/usr/bin/env python3
"""Rare-flip search: XPU torch fallbacks of the hyperconnection ops at M=2 vs M=1.

On XPU the Qwen4Exp hyperconnection ops (grouped Gemma RMSNorm, combine+norm,
gate mix, SiLU) run plain torch code whose reductions (`mean` over the 2560-wide
groups, `mean` over the 4 streams) let the backend choose a reduction order
from the whole tensor shape. Calls the overlay's own implementation functions (the XPU branch is the torch fallback) on a
two-row batch and on each row alone for many random draws and counts trials
with any bit difference per op.

    equivalence-hc-torch-fallback-m2-vs-m1-gate.py --out <json> [--trials 2000]
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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True)
    ap.add_argument("--trials", type=int, default=2000)
    ap.add_argument("--rows", type=int, default=2)
    ap.add_argument("--seed", type=int, default=20260903)
    args = ap.parse_args()
    refuse_active_model_server()
    import torch
    from vllm.models.qwen4_exp.amd.ops import hc
    torch.backends.mkldnn.deterministic = True
    device = torch.device("xpu:0")
    torch.xpu.set_device(device)
    g = torch.Generator(device="cpu").manual_seed(args.seed)
    HC, D, LORA = 4, 2560, 320
    weight = (torch.randn(HC * D, generator=g) * 0.1).to(torch.bfloat16).to(device)
    eps = 1e-6
    M = args.rows

    def ops(name):
        def draw(shape, scale=1.0):
            return (torch.randn(*shape, generator=g) * scale).to(torch.bfloat16).to(device)
        if name == "grouped_gemma_rmsnorm":
            x = draw((M, HC * D))
            return lambda s: hc._grouped_gemma_rmsnorm(x[s], weight, eps, HC)
        if name == "hc_combine_norm":
            res, blk, inj = draw((M, HC * D)), draw((M, D)), draw((M, HC), 5.0)
            return lambda s: torch.cat(hc._hc_combine_norm(res[s], blk[s], inj[s], weight, eps, HC), dim=-1)
        if name == "hc_gate_mix":
            x, gate = draw((M, HC * D)), draw((M, HC * D))
            return lambda s: hc._hc_gate_mix(x[s], gate[s], HC)
        if name == "hc_silu":
            x = draw((M, LORA))
            return lambda s: hc._hc_silu(x[s], HC)
        raise KeyError(name)

    names = ["grouped_gemma_rmsnorm", "hc_combine_norm", "hc_gate_mix", "hc_silu"]
    results = []
    for name in names:
        flips, first, elems = 0, None, 0
        for t in range(args.trials):
            f = ops(name)
            batched = f(slice(None))
            singles = torch.cat([f(slice(i, i + 1)) for i in range(M)], dim=0)
            torch.xpu.synchronize()
            elems += batched.numel()
            if not torch.equal(batched, singles):
                flips += 1
                if first is None:
                    d = (batched.float() - singles.float()).abs()
                    first = {"trial": t, "elements_differing": int((d > 0).sum()), "max_abs_diff": float(d.max()),
                             "rows_differing": [int(i) for i in range(M) if bool((d[i] > 0).any())]}
        rec = {"op": name, "trials": args.trials, "elements": elems, "trials_with_flip": flips, "first_flip": first}
        results.append(rec)
        print(json.dumps(rec))
    out = {"schema_version": 1, "classification": "b70_xpu_hc_torch_fallback_m2_vs_m1_rare_flip_search",
           "torch": torch.__version__, "device": torch.xpu.get_device_name(0), "seed": args.seed, "rows": M,
           "ops": results, "all_bit_identical": all(r["trials_with_flip"] == 0 for r in results)}
    with open(args.out, "w") as f:
        json.dump(out, f, indent=2)
    print("ALL_BIT_IDENTICAL" if out["all_bit_identical"] else "FLIPS_FOUND")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
