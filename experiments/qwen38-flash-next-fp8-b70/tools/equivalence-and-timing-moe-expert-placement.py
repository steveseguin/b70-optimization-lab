#!/usr/bin/env python3
"""Bit-exactness and timing of the per-expert base-table MoE path (Q38 placement) on one card.

Random block-FP8 expert weights [128, N, K]; routing draws fresh local experts every call.
Reference: resident weights, kernel without table. Test: resident/host split with a table
(host rows are pinned + UVA). Outputs must be bit-identical; then per-launch event timing
for (a) all-resident-with-table, (b) half host-resident with a routing that never hits host
rows, (c) half host-resident with routing that hits host rows every call."""
import os, sys, time
os.environ.setdefault("VLLM_TUNED_CONFIG_FOLDER", "/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/configs/moe-m1-w13-n32")
os.environ.setdefault("Q38_MOE_GEMM_EVENT_TIMING", "1")
import torch
from vllm.platforms import current_platform
from vllm.model_executor.layers.fused_moe.fused_moe import fused_experts
from vllm.model_executor.layers.fused_moe.config import fp8_w8a8_moe_quant_config
from vllm import q38_timing as q38
from vllm import q38_expert_placement as place

device = torch.device("xpu:0"); torch.xpu.set_device(device)
E_LOCAL, E_GLOBAL, K, N, TOPK, BLK = 128, 512, 2560, 640, 10, 128
fp8 = current_platform.fp8_dtype(); gd = torch.Generator(device=device).manual_seed(11)
def bq(w):
    e, r, c = w.shape; wb = w.view(e, r // BLK, BLK, c // BLK, BLK)
    amax = wb.abs().amax(dim=(2, 4), keepdim=True).clamp_min(1e-6); scale = amax / torch.finfo(fp8).max
    return (wb / scale).clamp(-torch.finfo(fp8).max, torch.finfo(fp8).max).to(fp8).view(e, r, c).contiguous(), scale.view(e, r // BLK, c // BLK).float().contiguous()
w1q, w1s = bq(torch.randn(E_LOCAL, 2 * N, K, generator=gd, device=device) / K ** 0.5)
w2q, w2s = bq(torch.randn(E_LOCAL, K, N, generator=gd, device=device) / N ** 0.5)
qc = fp8_w8a8_moe_quant_config(w1_scale=w1s, w2_scale=w2s, block_shape=[BLK, BLK])
em = torch.full((E_GLOBAL,), -1, dtype=torch.int32); em[:E_LOCAL] = torch.arange(E_LOCAL, dtype=torch.int32); em = em.to(device)
x = torch.randn(1, K, generator=gd, device=device).to(torch.bfloat16)
tw = torch.full((1, TOPK), 1.0 / TOPK, device=device)
def ids(local_pool):
    loc = local_pool[torch.randperm(len(local_pool), generator=gd, device=device)[:3]]
    rem = torch.randint(E_LOCAL, E_GLOBAL, (TOPK - 3,), generator=gd, device=device)
    return torch.cat([loc, rem]).unsqueeze(0).to(torch.int32)
def with_table(w, host_rows):
    resident, host, table = place._split(w, host_rows)
    resident._q38_base_table = table; resident._q38_host_storage = host
    return resident
hot = torch.arange(0, 64, device=device); cold = torch.arange(64, 128, device=device); allp = torch.arange(0, 128, device=device)
# 1. exactness: same routing, reference vs table (no host rows) vs table (half host rows)
routes = [ids(allp) for _ in range(32)]
ref = [fused_experts(x, w1q, w2q, tw, r, global_num_experts=E_GLOBAL, expert_map=em, quant_config=qc).clone() for r in routes]
w1t0, w2t0 = with_table(w1q, []), with_table(w2q, [])
w1t, w2t = with_table(w1q, list(range(64, 128))), with_table(w2q, list(range(64, 128)))
for tag, (a, b) in (("table-no-host", (w1t0, w2t0)), ("table-half-host", (w1t, w2t))):
    out = [fused_experts(x, a, b, tw, r, global_num_experts=E_GLOBAL, expert_map=em, quant_config=qc) for r in routes]
    same = all(torch.equal(o, r) for o, r in zip(out, ref)); print(f"EXACT {tag}: bit-identical on 32 routings = {same}")
    assert same, tag
# 2. timing (events): reference, table with hot-only routing, table with cold-hitting routing
def timed(tag, a, b, pool, n=96):
    for _ in range(10): fused_experts(x, a, b, tw, ids(pool), global_num_experts=E_GLOBAL, expert_map=em, quant_config=qc)
    torch.xpu.synchronize(); q38.snapshot_and_clear()
    for _ in range(n): fused_experts(x, a, b, tw, ids(pool), global_num_experts=E_GLOBAL, expert_map=em, quant_config=qc)
    acc = q38.snapshot_and_clear(); print(f"TIMING {tag}:", {k: round(1e3 * v / n, 4) for k, v in acc.items() if not k.endswith('_n')}, "ms per launch")
timed("reference resident (no table)", w1q, w2q, allp)
timed("table, all resident", w1t0, w2t0, allp)
timed("table, half host, routing hits resident only", w1t, w2t, hot)
timed("table, half host, routing hits host every call", w1t, w2t, cold)
print("DONE")
