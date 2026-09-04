#!/usr/bin/env python3
"""Wall-clock timing of the Triton block-FP8 fused MoE at M=1 versus M=2 (XPU).

Same construction as the M=2/M=1 equivalence gate (E=128 local experts with an
expert map over 512 global, K=2560, N=640, top-k 10, block-FP8 [128,128]) under
the tuned config folder given; times `fused_experts` alone (no collectives) with
device synchronizes, so the kernel-side cost of the second row can be separated
from the in-server MoE sub-block cost.

    timing-moe-m2-vs-m1-fused-experts.py --config-folder <dir> --out <json>
"""
from __future__ import annotations
import argparse, json, os, statistics, subprocess, sys, time


def refuse_active_model_server() -> None:
    out = subprocess.run(["ps", "-eo", "args"], capture_output=True, text=True).stdout
    if any(("EngineCore" in l or "Worker_TP" in l or "vllm serve" in l) for l in out.splitlines()):
        sys.exit("refusing to run beside a model server")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config-folder", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--iters", type=int, default=200)
    ap.add_argument("--seed", type=int, default=20260903)
    args = ap.parse_args()
    refuse_active_model_server()
    os.environ["VLLM_TUNED_CONFIG_FOLDER"] = args.config_folder
    import torch
    torch.backends.mkldnn.deterministic = True
    from vllm.platforms import current_platform
    assert current_platform.is_xpu()
    import vllm._custom_ops  # noqa: F401  (registers the platform dispatch of the custom ops)
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
    # EP-style expert map: this rank owns global experts 0..127.
    expert_map = torch.full((E_GLOBAL,), -1, dtype=torch.int32); expert_map[:E_LOCAL] = torch.arange(E_LOCAL, dtype=torch.int32)
    expert_map = expert_map.to(device)
    quant = fp8_w8a8_moe_quant_config(w1_scale=w1s, w2_scale=w2s, block_shape=[BLK, BLK])
    results = {}
    for M in (1, 2, 4):
        x = torch.randn(M, K, generator=g).to(torch.bfloat16).to(device)
        router = torch.randn(M, E_GLOBAL, generator=g).to(device)
        tw, ti = torch.topk(torch.softmax(router.float(), dim=-1), TOPK, dim=-1)
        tw = (tw / tw.sum(dim=-1, keepdim=True)).to(torch.float32); ti = ti.to(torch.int32)
        def run():
            out = fused_experts(x, w1q, w2q, tw, ti, global_num_experts=E_GLOBAL, expert_map=expert_map, quant_config=quant)
            torch.xpu.synchronize(); return out
        for _ in range(20): run()
        times = []
        for _ in range(args.iters):
            t0 = time.perf_counter(); run(); times.append(1e3 * (time.perf_counter() - t0))
        results[f"M{M}"] = {"mean_ms": statistics.mean(times), "median_ms": statistics.median(times), "min_ms": min(times), "max_ms": max(times), "p90_ms": sorted(times)[int(0.9 * len(times))], "local_expert_slots": int((expert_map[ti.long()] >= 0).sum())}
        print(M, json.dumps(results[f"M{M}"]))
    json.dump({"schema_version": 1, "classification": "b70_triton_block_fp8_moe_m_timing", "config_folder": args.config_folder, "iters": args.iters, "results": results}, open(args.out, "w"), indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
