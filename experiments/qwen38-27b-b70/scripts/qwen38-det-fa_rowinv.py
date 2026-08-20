import json, torch
from vllm_xpu_kernels.flash_attn_interface import flash_attn_varlen_func
DEV="xpu:0"
QH, KVH, HD, BS = 12, 2, 256, 64
kv = 296
lb = (kv + BS - 1)//BS
g = torch.Generator(device="cpu").manual_seed(777)
nb = lb + 3
order = torch.randperm(nb, generator=g)
k = torch.randn(nb, BS, KVH, HD, dtype=torch.float16, device=DEV)
v = torch.randn(nb, BS, KVH, HD, dtype=torch.float16, device=DEV)
bt = torch.zeros(1, lb, dtype=torch.int32, device=DEV)
bt[0].copy_(order[:lb].to(torch.int32).to(DEV))
# packed 6-row verifier call (causal): row i attends to kv-6+i+1 keys
q6 = torch.randn(6, QH, HD, dtype=torch.float16, device=DEV)
cu6 = torch.tensor([0, 6], dtype=torch.int32, device=DEV)
sk6 = torch.full((1,), kv, dtype=torch.int32, device=DEV)
o6 = torch.empty_like(q6)
flash_attn_varlen_func(q6, k, v, 6, cu6, kv, seqused_k=sk6, softmax_scale=HD**-0.5, causal=True, block_table=bt, out=o6, is_mix_batch=False)
torch.xpu.synchronize()
# row 5 alone: attends to all kv keys (causal last row)
q1 = q6[5:6].clone()
cu1 = torch.tensor([0, 1], dtype=torch.int32, device=DEV)
o1 = torch.empty_like(q1)
flash_attn_varlen_func(q1, k, v, 1, cu1, kv, seqused_k=sk6, softmax_scale=HD**-0.5, causal=True, block_table=bt, out=o1, is_mix_batch=False)
torch.xpu.synchronize()
eq = torch.equal(o6[5:6], o1)
md = float((o6[5:6].float()-o1.float()).abs().max())
print(json.dumps({"fa_row5_packed6_vs_solo_bitwise": bool(eq), "max_abs_diff": md}))
