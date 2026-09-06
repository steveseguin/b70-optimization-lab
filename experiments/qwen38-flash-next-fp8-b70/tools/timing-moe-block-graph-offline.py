#!/usr/bin/env python3
"""GPU-event time per Triton MoE GEMM launch on one B70 (Q38_MOE_GEMM_EVENT_TIMING hook, overlay dad52087+), 8 rotating block-FP8 weight sets, M=1/2, all-local vs EP-like routing. Needs the full serving env (stage PYTHONPATH, LD_LIBRARY_PATH, VLLM_TARGET_DEVICE=xpu, one card)."""
import os, sys, statistics
os.environ.setdefault("VLLM_TUNED_CONFIG_FOLDER", "/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/configs/moe-m1-w13-n32")
os.environ["Q38_MOE_GEMM_EVENT_TIMING"] = os.getenv("Q38_BENCH_EVENTS", "0")
import torch
from vllm.platforms import current_platform
import vllm._custom_ops
import vllm.q38_timing as q38
from vllm.model_executor.layers.fused_moe.fused_moe import fused_experts
from vllm.model_executor.layers.fused_moe.config import fp8_w8a8_moe_quant_config
device = torch.device("xpu:0"); torch.xpu.set_device(device)
E_LOCAL, E_GLOBAL, K, N, TOPK, BLK = 128, 512, 2560, 640, 10, 128
fp8 = current_platform.fp8_dtype(); gd = torch.Generator(device=device).manual_seed(1)
def bq(w):
    e, r, c = w.shape; wb = w.view(e, r // BLK, BLK, c // BLK, BLK)
    amax = wb.abs().amax(dim=(2, 4), keepdim=True).clamp_min(1e-6); scale = amax / torch.finfo(fp8).max
    return (wb / scale).clamp(-torch.finfo(fp8).max, torch.finfo(fp8).max).to(fp8).view(e, r, c).contiguous(), scale.view(e, r // BLK, c // BLK).float().contiguous()
import os
N_SETS = int(os.getenv("Q38_BENCH_SETS", "8"))  # 48 = one full rank of expert weights (server regime)
sets=[]
for _ in range(N_SETS):
    w1q,w1s=bq(torch.randn(E_LOCAL,2*N,K,generator=gd,device=device)/K**0.5); w2q,w2s=bq(torch.randn(E_LOCAL,K,N,generator=gd,device=device)/N**0.5)
    sets.append((w1q,w1s,w2q,w2s, fp8_w8a8_moe_quant_config(w1_scale=w1s, w2_scale=w2s, block_shape=[BLK,BLK])))
em = torch.full((E_GLOBAL,), -1, dtype=torch.int32); em[:E_LOCAL] = torch.arange(E_LOCAL, dtype=torch.int32); em = em.to(device)
g = torch.Generator(device="cpu").manual_seed(2)
import os
FRESH = os.getenv("Q38_BENCH_FRESH_ROUTING", "")
FILLER_GIB = float(os.getenv("Q38_BENCH_FILLER_GIB", "0"))
_FILLER = None
if N_SETS != 8:
    f, t = torch.xpu.mem_get_info(device)
    print(f"SETS {N_SETS} allocated; free now {f/2**30:.2f} GiB of {t/2**30:.2f} GiB")
if FILLER_GIB > 0:
    # Occupy VRAM so the expert weights + this filler approach the card's capacity (oversubscription probe).
    _FILLER = torch.empty(int(FILLER_GIB * 2**30), dtype=torch.uint8, device=device)
    _FILLER.fill_(1)
    torch.xpu.synchronize()
    f, t = torch.xpu.mem_get_info(device)
    print(f"FILLER {FILLER_GIB} GiB allocated; free now {f/2**30:.2f} GiB of {t/2**30:.2f} GiB")

import time
hits_per_call = int(os.getenv("Q38_BENCH_FRESH_ROUTING", "2"))
M = int(os.getenv("Q38_BENCH_M", "1"))
x = torch.randn(M, K, generator=g).to(torch.bfloat16).to(device)
tw = torch.full((M, TOPK), 1.0 / TOPK, device=device)
gd2 = torch.Generator(device=device).manual_seed(7)
def fresh_ids():
    rows = []
    for _ in range(M):
        loc = torch.randperm(E_LOCAL, generator=gd2, device=device)[:hits_per_call]
        rem = torch.randint(E_LOCAL, E_GLOBAL, (TOPK - hits_per_call,), generator=gd2, device=device)
        rows.append(torch.cat([loc, rem]))
    return torch.stack(rows).to(torch.int32)
ids = [fresh_ids() for _ in range(64)]
for i in range(20):
    s = sets[i % len(sets)]; fused_experts(x, s[0], s[2], tw, ids[i % 64], global_num_experts=E_GLOBAL, expert_map=em, quant_config=s[4])
torch.xpu.synchronize()
n = int(os.getenv("Q38_BENCH_N", "480"))
t0 = time.perf_counter()
for i in range(n):
    s = sets[i % len(sets)]; fused_experts(x, s[0], s[2], tw, ids[i % 64], global_num_experts=E_GLOBAL, expert_map=em, quant_config=s[4])
torch.xpu.synchronize(); t1 = time.perf_counter()
print(f"WALL M={M} hits={hits_per_call} events={os.environ['Q38_MOE_GEMM_EVENT_TIMING']}: {1e3*(t1-t0)/n:.4f} ms per fused_experts call (whole MoE block: align + 2 GEMMs + activation + sum), {n} calls")

# graph replay: capture 48 calls (one per layer, rotating weight sets) and replay
try:
    G = torch.xpu.XPUGraph()
    stream = torch.xpu.Stream()
    with torch.xpu.stream(stream):
        for i in range(8):
            s_ = sets[i % len(sets)]; fused_experts(x, s_[0], s_[2], tw, ids[i % 64], global_num_experts=E_GLOBAL, expert_map=em, quant_config=s_[4])
        torch.xpu.synchronize()
        with torch.xpu.graph(G, stream=stream):
            for i in range(48):
                s_ = sets[i % len(sets)]; fused_experts(x, s_[0], s_[2], tw, ids[i % 64], global_num_experts=E_GLOBAL, expert_map=em, quant_config=s_[4])
    torch.xpu.synchronize()
    for _ in range(3): G.replay()
    torch.xpu.synchronize(); t0=time.perf_counter()
    reps=20
    for _ in range(reps): G.replay()
    torch.xpu.synchronize(); t1=time.perf_counter()
    print(f"GRAPH M={M} hits={hits_per_call}: {1e3*(t1-t0)/reps:.3f} ms per replay of 48 MoE blocks = {1e3*(t1-t0)/reps/48:.4f} ms per block")
except Exception as e:
    print("GRAPH unavailable:", type(e).__name__, str(e)[:200])
