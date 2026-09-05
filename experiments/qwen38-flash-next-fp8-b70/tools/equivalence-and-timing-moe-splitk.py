#!/usr/bin/env python3
"""Deterministic split-K Triton MoE (VLLM_XPU_MOE_SPLIT_K) against the stock kernel on one B70:
same synthetic block-FP8 MoE as the M=2/M=1 gates (E=128 local of 512, K=2560, N=640, top-k 10),
per M in (1, 2, 4): stock output and time, then each split factor's output (bit-equality and max
abs diff against stock, and repeat-determinism) and time. `fused_experts` only, no collectives.
    equivalence-and-timing-moe-splitk.py --config-folder <dir> --out <json> [--splits 2,4,5,8,10,20]
"""
from __future__ import annotations
import argparse, json, os, statistics, subprocess, sys, time

def refuse_active_model_server() -> None:
    out = subprocess.run(["ps", "-eo", "args"], capture_output=True, text=True).stdout
    if any(("EngineCore" in l or "Worker_TP" in l or "vllm serve" in l) for l in out.splitlines()):
        sys.exit("refusing to run beside a model server")

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config-folder", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--iters", type=int, default=200); ap.add_argument("--seed", type=int, default=20260903)
    ap.add_argument("--splits", default="2,4,5,8,10,20"); ap.add_argument("--ms", default="1,2,4")
    args = ap.parse_args(); refuse_active_model_server()
    os.environ["VLLM_TUNED_CONFIG_FOLDER"] = args.config_folder
    os.environ.pop("VLLM_XPU_MOE_SPLIT_K", None)
    import torch
    torch.backends.mkldnn.deterministic = True
    from vllm.platforms import current_platform
    assert current_platform.is_xpu()
    import vllm._custom_ops  # noqa: F401
    from vllm.model_executor.layers.fused_moe.fused_moe import fused_experts
    from vllm.model_executor.layers.fused_moe.config import fp8_w8a8_moe_quant_config
    device = torch.device("xpu:0"); torch.xpu.set_device(device)
    E_LOCAL, E_GLOBAL, K, N, TOPK, BLK = 128, 512, 2560, 640, 10, 128
    g = torch.Generator(device="cpu").manual_seed(args.seed)
    fp8 = current_platform.fp8_dtype()
    def block_quant(w):
        e, r, c = w.shape
        wb = w.view(e, r // BLK, BLK, c // BLK, BLK)
        amax = wb.abs().amax(dim=(2, 4), keepdim=True).clamp_min(1e-6)
        scale = amax / torch.finfo(fp8).max
        q = (wb / scale).clamp(-torch.finfo(fp8).max, torch.finfo(fp8).max).to(fp8)
        return q.view(e, r, c), scale.view(e, r // BLK, c // BLK).to(torch.float32)
    w1q, w1s = block_quant(torch.randn(E_LOCAL, 2 * N, K, generator=g) * (1.0 / K ** 0.5))
    w2q, w2s = block_quant(torch.randn(E_LOCAL, K, N, generator=g) * (1.0 / N ** 0.5))
    w1q, w1s, w2q, w2s = (t.to(device) for t in (w1q, w1s, w2q, w2s))
    expert_map = torch.full((E_GLOBAL,), -1, dtype=torch.int32); expert_map[:E_LOCAL] = torch.arange(E_LOCAL, dtype=torch.int32)
    expert_map = expert_map.to(device)
    quant = fp8_w8a8_moe_quant_config(w1_scale=w1s, w2_scale=w2s, block_shape=[BLK, BLK])
    def timed(fn, iters):
        for _ in range(20): fn()
        ts = []
        for _ in range(iters):
            t0 = time.perf_counter(); fn(); ts.append(1e3 * (time.perf_counter() - t0))
        return dict(mean_ms=statistics.mean(ts), median_ms=statistics.median(ts), min_ms=min(ts), max_ms=max(ts))
    results = {}
    for M in (int(m) for m in args.ms.split(",")):
        x = torch.randn(M, K, generator=g).to(torch.bfloat16).to(device)
        router = torch.randn(M, E_GLOBAL, generator=g).to(device)
        # route into the local experts so every row hits real work (EP-like: ~TOPK local hits per row)
        router[:, E_LOCAL:] -= 100.0
        tw, ti = torch.topk(torch.softmax(router.float(), dim=-1), TOPK, dim=-1)
        tw = (tw / tw.sum(dim=-1, keepdim=True)).to(torch.float32); ti = ti.to(torch.int32)
        def run():
            out = fused_experts(x, w1q, w2q, tw, ti, global_num_experts=E_GLOBAL, expert_map=expert_map, quant_config=quant)
            torch.xpu.synchronize(); return out
        os.environ.pop("VLLM_XPU_MOE_SPLIT_K", None)
        ref = run().clone(); ref2 = run().clone()
        row = {"stock": dict(timed(run, args.iters), repeat_equal=bool(torch.equal(ref, ref2)))}
        print(M, "stock", json.dumps(row["stock"]), flush=True)
        for S in (int(s) for s in args.splits.split(",")):
            os.environ["VLLM_XPU_MOE_SPLIT_K"] = str(S)
            o1 = run().clone(); o2 = run().clone()
            d = (o1.float() - ref.float()).abs()
            r = dict(timed(run, args.iters), bit_equal_to_stock=bool(torch.equal(o1, ref)), repeat_equal=bool(torch.equal(o1, o2)),
                     max_abs_diff=float(d.max()), mean_abs_diff=float(d.mean()), ref_max_abs=float(ref.float().abs().max()),
                     mismatch_elements=int((o1 != ref).sum()), elements=int(ref.numel()))
            row[f"split{S}"] = r; print(M, f"split{S}", json.dumps(r), flush=True)
        os.environ.pop("VLLM_XPU_MOE_SPLIT_K", None)
        results[f"M{M}"] = row
    json.dump({"schema_version": 1, "classification": "b70_triton_block_fp8_moe_splitk_equivalence_timing", "config_folder": args.config_folder,
               "iters": args.iters, "seed": args.seed, "shape": dict(E_LOCAL=E_LOCAL, E_GLOBAL=E_GLOBAL, K=K, N=N, TOPK=TOPK, block=BLK),
               "results": results}, open(args.out, "w"), indent=1)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
