#!/usr/bin/env python3
"""Offline check of the load-time placement path (v5) on one card: create a fake MoE layer with
resident-sized parameters via prepare_layer, write every expert through row_view() the way the
loader does, then compare fused_experts outputs against a full resident reference tensor
(bit-identical) and report that the device parameter has the resident size."""
import os
os.environ.setdefault("VLLM_TUNED_CONFIG_FOLDER", "/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/configs/moe-m1-w13-n32")
import json, tempfile, torch
from vllm.platforms import current_platform
from vllm.model_executor.layers.fused_moe.fused_moe import fused_experts
from vllm.model_executor.layers.fused_moe.config import fp8_w8a8_moe_quant_config
from vllm import q38_expert_placement as place

device = torch.device("xpu:0"); torch.xpu.set_device(device)
E_LOCAL, E_GLOBAL, K, N, TOPK, BLK = 128, 512, 2560, 640, 10, 128
fp8 = current_platform.fp8_dtype(); gd = torch.Generator(device=device).manual_seed(5)
def bq(w):
    e, r, c = w.shape; wb = w.view(e, r // BLK, BLK, c // BLK, BLK)
    amax = wb.abs().amax(dim=(2, 4), keepdim=True).clamp_min(1e-6); scale = amax / torch.finfo(fp8).max
    return (wb / scale).clamp(-torch.finfo(fp8).max, torch.finfo(fp8).max).to(fp8).view(e, r, c).contiguous(), scale.view(e, r // BLK, c // BLK).float().contiguous()
w1q, w1s = bq(torch.randn(E_LOCAL, 2 * N, K, generator=gd, device=device) / K ** 0.5)
w2q, w2s = bq(torch.randn(E_LOCAL, K, N, generator=gd, device=device) / N ** 0.5)
qc = fp8_w8a8_moe_quant_config(w1_scale=w1s, w2_scale=w2s, block_shape=[BLK, BLK])
em = torch.full((E_GLOBAL,), -1, dtype=torch.int32); em[:E_LOCAL] = torch.arange(E_LOCAL, dtype=torch.int32); em = em.to(device)
cold = list(range(3, 128, 7))  # 18 cold experts
with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
    json.dump({"0": {"46": cold}}, f); path = f.name
place.PLACEMENT_PATH = path; place._PLACEMENT = None
import vllm.distributed as dist
dist.get_tensor_model_parallel_rank = lambda: 0
layer = torch.nn.Module(); layer.layer_name = "language_model.model.layers.46.mlp.experts"
layer.w13_weight = torch.nn.Parameter(torch.empty(E_LOCAL, 2 * N, K, dtype=fp8, device=device), requires_grad=False)
layer.w2_weight = torch.nn.Parameter(torch.empty(E_LOCAL, K, N, dtype=fp8, device=device), requires_grad=False)
place.prepare_layer(layer)
assert layer.w13_weight.shape[0] == E_LOCAL - len(cold), layer.w13_weight.shape
for e in range(E_LOCAL):  # the loader's per-expert writes
    place.row_view(layer.w13_weight, e).copy_(w1q[e]); place.row_view(layer.w2_weight, e).copy_(w2q[e])
torch.xpu.synchronize()
x = torch.randn(1, K, generator=gd, device=device).to(torch.bfloat16); tw = torch.full((1, TOPK), 1.0 / TOPK, device=device)
def ids():
    loc = torch.randperm(E_LOCAL, generator=gd, device=device)[:4]; rem = torch.randint(E_LOCAL, E_GLOBAL, (TOPK - 4,), generator=gd, device=device)
    return torch.cat([loc, rem]).unsqueeze(0).to(torch.int32)
routes = [ids() for _ in range(48)]
ref = [fused_experts(x, w1q, w2q, tw, r, global_num_experts=E_GLOBAL, expert_map=em, quant_config=qc).clone() for r in routes]
out = [fused_experts(x, layer.w13_weight, layer.w2_weight, tw, r, global_num_experts=E_GLOBAL, expert_map=em, quant_config=qc) for r in routes]
same = all(torch.equal(o, r) for o, r in zip(out, ref))
hit_cold = sum(int(any(int(e) in cold for e in r[0].tolist() if int(e) < E_LOCAL)) for r in routes)
print(f"LOADTIME PLACEMENT: resident rows {layer.w13_weight.shape[0]}/{E_LOCAL}, routings hitting cold experts {hit_cold}/48, bit-identical = {same}")
assert same
print("DONE")
