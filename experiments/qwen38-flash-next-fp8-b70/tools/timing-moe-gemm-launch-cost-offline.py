#!/usr/bin/env python3
"""Fixed vs per-expert cost of one Triton MoE GEMM launch (GPU events): empty-kernel launch, then M=1 with 0/1/2/5/10 local expert hits (w13-n32 map, one B70, serving env)."""
import os, statistics
os.environ["VLLM_TUNED_CONFIG_FOLDER"] = "/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/configs/moe-m1-w13-n32"
os.environ["Q38_MOE_GEMM_EVENT_TIMING"] = "1"
import torch, triton, triton.language as tl
from vllm.platforms import current_platform
import vllm._custom_ops
import vllm.q38_timing as q38
from vllm.model_executor.layers.fused_moe.fused_moe import fused_experts
from vllm.model_executor.layers.fused_moe.config import fp8_w8a8_moe_quant_config
device = torch.device("xpu:0"); torch.xpu.set_device(device)
@triton.jit
def _empty(x_ptr, n, BLOCK: tl.constexpr):
    pid = tl.program_id(0)
    offs = pid * BLOCK + tl.arange(0, BLOCK)
    tl.store(x_ptr + offs, tl.zeros((BLOCK,), dtype=tl.float32), mask=offs < n)
x = torch.empty(400 * 64, device=device, dtype=torch.float32)
def ev(fn, n=50):
    for _ in range(10): fn()
    torch.xpu.synchronize(); ts = []
    for _ in range(n):
        s = torch.xpu.Event(enable_timing=True); e = torch.xpu.Event(enable_timing=True); s.record(); fn(); e.record(); torch.xpu.synchronize(); ts.append(s.elapsed_time(e))
    return round(statistics.median(ts), 4)
print("empty triton kernel, 1 program:", ev(lambda: _empty[(1,)](x, 64, BLOCK=64)), "ms")
print("empty triton kernel, 400 programs:", ev(lambda: _empty[(400,)](x, 400 * 64, BLOCK=64)), "ms")
print("empty triton kernel, 4000 programs:", ev(lambda: _empty[(4000,)](x, 400 * 64, BLOCK=64)), "ms")
E_LOCAL, E_GLOBAL, K, N, TOPK, BLK = 128, 512, 2560, 640, 10, 128
fp8 = current_platform.fp8_dtype(); gd = torch.Generator(device=device).manual_seed(1)
def bq(w):
    e, r, c = w.shape; wb = w.view(e, r // BLK, BLK, c // BLK, BLK)
    amax = wb.abs().amax(dim=(2, 4), keepdim=True).clamp_min(1e-6); scale = amax / torch.finfo(fp8).max
    return (wb / scale).clamp(-torch.finfo(fp8).max, torch.finfo(fp8).max).to(fp8).view(e, r, c).contiguous(), scale.view(e, r // BLK, c // BLK).float().contiguous()
w1q,w1s=bq(torch.randn(E_LOCAL,2*N,K,generator=gd,device=device)/K**0.5); w2q,w2s=bq(torch.randn(E_LOCAL,K,N,generator=gd,device=device)/N**0.5)
quant=fp8_w8a8_moe_quant_config(w1_scale=w1s, w2_scale=w2s, block_shape=[BLK,BLK])
em = torch.full((E_GLOBAL,), -1, dtype=torch.int32); em[:E_LOCAL] = torch.arange(E_LOCAL, dtype=torch.int32); em = em.to(device)
xin = torch.randn(1, K, device=device).to(torch.bfloat16)
for hits in (0, 1, 2, 5, 10):
    ids = list(range(hits)) + list(range(E_LOCAL, E_LOCAL + TOPK - hits))
    ti = torch.tensor([ids], dtype=torch.int32, device=device); tw = torch.full((1, TOPK), 1.0 / TOPK, device=device)
    for _ in range(10): fused_experts(xin, w1q, w2q, tw, ti, global_num_experts=E_GLOBAL, expert_map=em, quant_config=quant)
    torch.xpu.synchronize(); q38.snapshot_and_clear()
    n = 40
    for _ in range(n): fused_experts(xin, w1q, w2q, tw, ti, global_num_experts=E_GLOBAL, expert_map=em, quant_config=quant)
    acc = q38.snapshot_and_clear()
    print(f"M=1 local hits={hits}:", {k: round(1e3 * v / n, 4) for k, v in acc.items() if not k.endswith('_n')}, "ms per launch")
