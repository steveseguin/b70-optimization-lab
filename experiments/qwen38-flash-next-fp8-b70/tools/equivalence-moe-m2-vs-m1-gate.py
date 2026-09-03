#!/usr/bin/env python3
"""Two-row versus one-row equivalence of the Triton block-FP8 fused MoE.

Builds a Flash-Next-shaped local MoE (E=128 experts per EP rank, K=2560,
N=640, top-k 10, block-FP8 [128,128] weights, dynamic block activation
quant) from a fixed seed, then runs vLLM's `fused_experts` on a two-row
batch and on each row alone under the tuned config folder given, and writes
the outputs so runs under different folders can be compared. Bit-identical
rows mean the kernel is M-invariant under that config; a difference between
folders at M=1 means the kernel's result depends on the tile config, which
matters because serving uses a W13 N=32 phase tile at M=1 only.

    equivalence-moe-m2-vs-m1-gate.py --config-folder <dir> --out <json> --save <pt>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys


def refuse_active_model_server() -> None:
    out = subprocess.run(["ps", "-eo", "args"], capture_output=True, text=True).stdout
    if any(("EngineCore" in l or "Worker_TP" in l or "vllm serve" in l) for l in out.splitlines()):
        sys.exit("refusing to run beside a model server")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config-folder", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--save", required=True)
    ap.add_argument("--seed", type=int, default=20260903)
    ap.add_argument("--rows", type=int, default=2)
    args = ap.parse_args()
    refuse_active_model_server()
    os.environ["VLLM_TUNED_CONFIG_FOLDER"] = args.config_folder
    import torch
    torch.backends.mkldnn.deterministic = True
    from vllm.model_executor.layers.fused_moe.fused_moe import fused_experts
    from vllm.model_executor.layers.fused_moe.config import fp8_w8a8_moe_quant_config
    from vllm.platforms import current_platform

    device = torch.device("xpu:0")
    torch.xpu.set_device(device)
    E, K, N, TOPK, BLK = 128, 2560, 640, 10, 128
    g = torch.Generator(device="cpu").manual_seed(args.seed)
    fp8 = current_platform.fp8_dtype()

    def block_quant(w: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        e, r, c = w.shape
        wb = w.view(e, r // BLK, BLK, c // BLK, BLK)
        amax = wb.abs().amax(dim=(2, 4), keepdim=True).clamp_min(1e-6)
        scale = amax / torch.finfo(fp8).max
        q = (wb / scale).clamp(-torch.finfo(fp8).max, torch.finfo(fp8).max).to(fp8)
        return q.view(e, r, c), scale.view(e, r // BLK, c // BLK).to(torch.float32)

    w1 = torch.randn(E, 2 * N, K, generator=g) * (1.0 / K ** 0.5)
    w2 = torch.randn(E, K, N, generator=g) * (1.0 / N ** 0.5)
    w1q, w1s = block_quant(w1)
    w2q, w2s = block_quant(w2)
    w1q, w1s, w2q, w2s = (t.to(device) for t in (w1q, w1s, w2q, w2s))
    x = (torch.randn(args.rows, K, generator=g)).to(torch.bfloat16).to(device)
    router = torch.randn(args.rows, E, generator=g).to(device)
    topk_weights, topk_ids = torch.topk(torch.softmax(router.float(), dim=-1), TOPK, dim=-1)
    topk_weights = (topk_weights / topk_weights.sum(dim=-1, keepdim=True)).to(torch.float32)
    topk_ids = topk_ids.to(torch.int32)
    quant = fp8_w8a8_moe_quant_config(w1_scale=w1s, w2_scale=w2s, block_shape=[BLK, BLK])

    def run(h, tw, ti):
        out = fused_experts(h, w1q, w2q, tw, ti, global_num_experts=E, quant_config=quant)
        torch.xpu.synchronize()
        return out.clone()

    batched = run(x, topk_weights, topk_ids)
    batched2 = run(x, topk_weights, topk_ids)
    singles = torch.cat([run(x[i:i + 1], topk_weights[i:i + 1], topk_ids[i:i + 1]) for i in range(args.rows)], dim=0)
    singles2 = torch.cat([run(x[i:i + 1], topk_weights[i:i + 1], topk_ids[i:i + 1]) for i in range(args.rows)], dim=0)
    diff = (batched.float() - singles.float()).abs()
    rel = diff / singles.float().abs().clamp_min(1e-6)
    sha = lambda t: hashlib.sha256(t.contiguous().cpu().view(torch.int16).numpy().tobytes()).hexdigest()
    result = {
        "schema_version": 1,
        "classification": "flash_next_triton_block_fp8_moe_m2_vs_m1_equivalence",
        "config_folder": args.config_folder, "seed": args.seed, "rows": args.rows,
        "shape": {"E": E, "K": K, "N": N, "topk": TOPK, "block": BLK},
        "device": torch.xpu.get_device_name(0),
        "batched_repeatable": bool(torch.equal(batched, batched2)),
        "single_repeatable": bool(torch.equal(singles, singles2)),
        "batched_equals_singles": bool(torch.equal(batched, singles)),
        "elements_differing": int((diff > 0).sum()), "max_abs_diff": float(diff.max()),
        "max_rel_diff": float(rel.max()), "mean_abs_diff": float(diff.mean()),
        "sha256_batched": sha(batched), "sha256_singles": sha(singles),
        "sha256_row0_single": sha(singles[0:1]),
    }
    torch.save({"batched": batched.cpu(), "singles": singles.cpu()}, args.save)
    with open(args.out, "w") as f:
        json.dump(result, f, indent=2)
    print(json.dumps({k: result[k] for k in ("config_folder", "batched_repeatable", "single_repeatable", "batched_equals_singles", "elements_differing", "max_abs_diff", "max_rel_diff", "sha256_row0_single")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
