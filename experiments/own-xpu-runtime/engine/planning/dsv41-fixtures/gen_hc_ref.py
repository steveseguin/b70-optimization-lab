# Reference dump for the HC-Sinkhorn fixture.
# Semantics transcribed from the official inference/kernel.py
# hc_split_sinkhorn_kernel (DeepSeek-V4.1-Flash-1017, MIT).
# Real blk.0.hc_attn_scale/base from the verified GGUF; seeded mixes.
import numpy as np
import torch
from gguf import GGUFReader

SHARD = "/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/UD-IQ2_XXS/DeepSeek-V4.1-Flash-1017-UD-IQ2_XXS-00002-of-00006.gguf"
OUT = "/tmp/hc_ref"

r = GGUFReader(SHARD)
ts = {t.name: t for t in r.tensors}
scale = torch.from_numpy(np.array(ts["blk.0.hc_attn_scale.weight"].data, dtype=np.float32))  # [3]
base  = torch.from_numpy(np.array(ts["blk.0.hc_attn_base.weight"].data, dtype=np.float32))   # [24]
print("scale", tuple(scale.shape), scale.dtype, "base", tuple(base.shape))

hc, iters, eps = 4, 20, 1e-6
torch.manual_seed(0xD541)
n = 64
mixes32 = torch.randn(n, (2 + hc) * hc, dtype=torch.float32) * 2.0

def sinkhorn(mixes, scale, base, dt):
    m = mixes.to(dt); s = scale.to(dt); b = base.to(dt)
    pre  = torch.sigmoid(m[:, :hc] * s[0] + b[:hc]) + eps
    post = 2 * torch.sigmoid(m[:, hc:2*hc] * s[1] + b[hc:2*hc])
    comb = (m[:, 2*hc:] * s[2] + b[2*hc:]).view(n, hc, hc)
    comb = torch.softmax(comb, dim=-1) + eps
    comb = comb / (comb.sum(-2, keepdim=True) + eps)
    for _ in range(iters - 1):
        comb = comb / (comb.sum(-1, keepdim=True) + eps)
        comb = comb / (comb.sum(-2, keepdim=True) + eps)
    return pre, post, comb

for tag, dt in (("f64", torch.float64), ("f32", torch.float32)):
    pre, post, comb = sinkhorn(mixes32, scale, base, dt)
    pre.detach().cpu().numpy().astype(getattr(np, "float" + tag[1:])).tofile(f"{OUT}_pre_{tag}.bin")
    post.detach().cpu().numpy().astype(getattr(np, "float" + tag[1:])).tofile(f"{OUT}_post_{tag}.bin")
    comb.detach().cpu().numpy().astype(getattr(np, "float" + tag[1:])).tofile(f"{OUT}_comb_{tag}.bin")

mixes32.numpy().tofile(f"{OUT}_mixes.bin")
scale.numpy().tofile(f"{OUT}_scale.bin")
base.numpy().tofile(f"{OUT}_base.bin")
print("wrote", OUT, "n=64 hc=4 iters=20 eps=1e-6")
