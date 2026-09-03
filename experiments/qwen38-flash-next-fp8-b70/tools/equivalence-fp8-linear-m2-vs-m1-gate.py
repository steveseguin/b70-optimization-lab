#!/usr/bin/env python3
"""Two-row versus one-row equivalence of the XPU block-FP8 linear path.

Reproduces exactly what `XPUFp8BlockScaledMMKernel.apply_weights` does for a
Flash-Next dense projection: dynamic per-token [1,128]-group FP8 activation
quantization (`per_token_group_quant_fp8`) followed by the oneDNN block-scaled
`torch.ops._xpu_C.fp8_gemm` with the [k_blocks, n_blocks] weight scale
layout, on the layer-0 GDN and attention projection shapes at TP4.  Runs a
two-row batch and each row alone and reports whether they are bit-identical.
A difference here means MTP1 verifier steps (M=2) cannot equal MTP0 (M=1)
through the dense FP8 projections, independent of the recurrent kernel.

    equivalence-fp8-linear-m2-vs-m1-gate.py --out <json> [--save <pt>]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys


def refuse_active_model_server() -> None:
    out = subprocess.run(["ps", "-eo", "args"], capture_output=True, text=True).stdout
    if any(("EngineCore" in l or "Worker_TP" in l or "vllm serve" in l) for l in out.splitlines()):
        sys.exit("refusing to run beside a model server")


# TP4 per-rank shapes (N, K) of the block-FP8 dense projections in this model.
SHAPES = [
    ("gdn-in_proj_qkvz", 4096, 2560),
    ("gdn-out_proj", 2560, 1536),
    ("attn-qkv_proj", 1792, 2560),
    ("attn-o_proj", 2560, 1536),
    ("shared-expert-gate_up", 320, 2560),
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True)
    ap.add_argument("--save")
    ap.add_argument("--seed", type=int, default=20260903)
    ap.add_argument("--rows", type=int, default=2)
    ap.add_argument("--trials", type=int, default=4, help="distinct activation draws per shape")
    ap.add_argument("--kernel-stage", default="/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70",
                    help="vllm_xpu_kernels stage directory the servers load (prepended to sys.path)")
    args = ap.parse_args()
    refuse_active_model_server()
    sys.path.insert(0, args.kernel_stage)
    import torch
    torch.backends.mkldnn.deterministic = True
    from vllm.model_executor.layers.quantization.utils.fp8_utils import per_token_group_quant_fp8
    from vllm.platforms import current_platform
    import vllm_xpu_kernels._xpu_C  # noqa: F401  (registers fp8_gemm)
    xpu_c_path = vllm_xpu_kernels._xpu_C.__file__
    assert xpu_c_path.startswith(args.kernel_stage), xpu_c_path

    device = torch.device("xpu:0")
    torch.xpu.set_device(device)
    BLK = 128
    fp8 = current_platform.fp8_dtype()
    g = torch.Generator(device="cpu").manual_seed(args.seed)
    sha = lambda t: hashlib.sha256(t.contiguous().cpu().view(torch.int16).numpy().tobytes()).hexdigest()

    def block_quant(w: torch.Tensor):
        n, k = w.shape
        nb, kb = -(-n // BLK), k // BLK
        pad = torch.zeros(nb * BLK, k)
        pad[:n] = w
        wb = pad.view(nb, BLK, kb, BLK)
        amax = wb.abs().amax(dim=(1, 3), keepdim=True).clamp_min(1e-6)
        scale = amax / torch.finfo(fp8).max
        q = (wb / scale).clamp(-torch.finfo(fp8).max, torch.finfo(fp8).max).to(fp8)
        return q.view(nb * BLK, k)[:n].contiguous(), scale.view(nb, kb).to(torch.float32)

    def gemm(x: torch.Tensor, wq: torch.Tensor, scale_kn: torch.Tensor) -> torch.Tensor:
        q_input, input_scale = per_token_group_quant_fp8(
            x, group_size=BLK, column_major_scales=False, dtype=fp8, use_ue8m0=False
        )
        out = torch.ops._xpu_C.fp8_gemm(
            q_input, wq.t(), torch.bfloat16, input_scale, scale_kn, torch.Tensor()
        )
        torch.xpu.synchronize()
        return out.clone()

    shapes_out, saved = [], {}
    all_equal = True
    for label, N, K in SHAPES:
        w = torch.randn(N, K, generator=g) * (1.0 / K ** 0.5)
        wq, ws = block_quant(w)
        # Mirror process_weights_after_loading for ragged N (N % 128 != 0).
        if N % BLK != 0:
            import math
            gn = math.gcd(N, BLK)
            col_start = torch.arange(N // gn) * gn
            ws = ws.index_select(0, torch.div(col_start, BLK, rounding_mode="floor")).contiguous()
        scale_kn = ws.t().contiguous().to(device)
        wq = wq.to(device)
        rec = {"label": label, "N": N, "K": K, "trials": []}
        for t in range(args.trials):
            x = torch.randn(args.rows, K, generator=g).to(torch.bfloat16).to(device)
            batched = gemm(x, wq, scale_kn)
            batched2 = gemm(x, wq, scale_kn)
            singles = torch.cat([gemm(x[i:i + 1], wq, scale_kn) for i in range(args.rows)], dim=0)
            singles2 = torch.cat([gemm(x[i:i + 1], wq, scale_kn) for i in range(args.rows)], dim=0)
            diff = (batched.float() - singles.float()).abs()
            rel = diff / singles.float().abs().clamp_min(1e-6)
            eq = bool(torch.equal(batched, singles))
            all_equal &= eq
            rec["trials"].append({
                "batched_repeatable": bool(torch.equal(batched, batched2)),
                "single_repeatable": bool(torch.equal(singles, singles2)),
                "batched_equals_singles": eq,
                "rows_differing": [int(i) for i in range(args.rows) if bool((diff[i] > 0).any())],
                "elements_differing": int((diff > 0).sum()),
                "max_abs_diff": float(diff.max()),
                "max_rel_diff": float(rel.max()),
                "sha256_batched": sha(batched), "sha256_singles": sha(singles),
            })
            if args.save and t == 0:
                saved[label] = {"x": x.cpu(), "batched": batched.cpu(), "singles": singles.cpu()}
        rec["all_trials_equal"] = all(tr["batched_equals_singles"] for tr in rec["trials"])
        shapes_out.append(rec)
        print(json.dumps({"label": label, "N": N, "K": K, "all_trials_equal": rec["all_trials_equal"],
                          "max_abs_diff": max(tr["max_abs_diff"] for tr in rec["trials"]),
                          "elements_differing": sum(tr["elements_differing"] for tr in rec["trials"])}))
    result = {
        "schema_version": 1,
        "classification": "b70_xpu_block_fp8_linear_m2_vs_m1_equivalence",
        "torch": torch.__version__, "device": torch.xpu.get_device_name(0),
        "kernel_stage": args.kernel_stage, "xpu_c_library": xpu_c_path,
        "mkldnn_deterministic": True, "seed": args.seed, "rows": args.rows, "trials": args.trials,
        "activation_quant": "per_token_group_quant_fp8 group 128, no ue8m0, row-major scales",
        "gemm_op": "torch.ops._xpu_C.fp8_gemm (oneDNN block-scaled)",
        "all_shapes_equal": all_equal, "shapes": shapes_out,
    }
    if args.save:
        torch.save(saved, args.save)
    with open(args.out, "w") as f:
        json.dump(result, f, indent=2)
    print("ALL_SHAPES_EQUAL" if all_equal else "SHAPES_DIFFER")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
