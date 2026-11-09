# Reference dumps for the attention fixture package (A1 sparse_attn core,
# A2 compressor pooling, A3 indexer scoring/topk/candidates, A4 window idxs).
# Semantics from official inference/{model,kernel}.py (DeepSeek-V4.1-Flash-1017, MIT).
import numpy as np
import torch
import torch.nn.functional as F

D = "/tmp"
torch.manual_seed(0xD544)

# ---------- A1: sparse_attn core (direct-softmax reference of the online-softmax kernel)
b, m, h, d, n, topk = 1, 6, 4, 32, 20, 8
q = torch.randn(b, m, h, d, dtype=torch.float32) * 0.8
kv = torch.randn(b, n, d, dtype=torch.float32) * 0.8
sink = torch.randn(h, dtype=torch.float32) * 0.5
scale = d ** -0.5
idxs = torch.randint(0, n, (b, m, topk), dtype=torch.int32)
idxs[0, 1, 5:] = -1          # partial row
idxs[0, 3, :] = -1           # all-invalid row -> zero output (kernel convention)
idxs[0, 4] = torch.arange(topk) - 3  # duplicates + near-front rows

def sparse_ref(q, kv, sink, idxs, scale, dt):
    q, kv, sink = q.to(dt), kv.to(dt), sink.to(dt)
    o = torch.zeros(b, m, h, d, dtype=dt)
    for t in range(m):
        for hh in range(h):
            valid = idxs[0, t][idxs[0, t] >= 0].long()
            if valid.numel() == 0:
                continue
            s = (kv[0, valid] @ q[0, t, hh]) * scale
            logits = torch.cat([s, sink[hh].view(1)])
            p = torch.softmax(logits, dim=-1)[:-1]
            o[0, t, hh] = (p.unsqueeze(-1) * kv[0, valid]).sum(0)
    return o

for tag, dt in (("f64", torch.float64), ("f32", torch.float32)):
    sparse_ref(q, kv, sink, idxs, scale, dt).cpu().numpy().astype(getattr(np, "float" + tag[1:])).tofile(f"{D}/attn_o_{tag}.bin")
q.numpy().tofile(f"{D}/attn_q.bin"); kv.numpy().tofile(f"{D}/attn_kv.bin")
sink.numpy().tofile(f"{D}/attn_sink.bin"); idxs.numpy().astype(np.int32).tofile(f"{D}/attn_idxs.bin")

# ---------- A2: compressor pooling (ratio=2 prefill) + RMSNorm
hd, ratio, L = 48, 2, 8
kvv = torch.randn(L, hd, dtype=torch.float32)
sco = torch.randn(L, hd, dtype=torch.float32) * 1.5
nw = torch.randn(hd, dtype=torch.float32).abs() + 0.3
eps = 1e-20
def compress(kvv, sco, nw, dt):
    kv, sc = kvv.to(dt).view(L // ratio, ratio, hd), sco.to(dt).view(L // ratio, ratio, hd)
    pooled = (kv * sc.softmax(dim=1)).sum(1)
    v = pooled.square().mean(-1, keepdim=True)
    return pooled * torch.rsqrt(v + eps) * nw.to(dt)
for tag, dt in (("f64", torch.float64), ("f32", torch.float32)):
    compress(kvv, sco, nw, dt).cpu().numpy().astype(getattr(np, "float" + tag[1:])).tofile(f"{D}/comp_y_{tag}.bin")
kvv.numpy().tofile(f"{D}/comp_kv.bin"); sco.numpy().tofile(f"{D}/comp_score.bin"); nw.numpy().tofile(f"{D}/comp_nw.bin")

# ---------- A3: indexer scoring + causal mask + topk + candidate blocks
m3, H, dk, T, topk3 = 5, 4, 16, 40, 8
q3 = torch.randn(m3, H, dk, dtype=torch.float32)
k3 = torch.randn(T, dk, dtype=torch.float32)
w3 = torch.randn(m3, H, dtype=torch.float32).abs() * 0.4
ratio3 = 2
score = torch.einsum("mhd,td->mht", q3, k3).relu() * w3.unsqueeze(-1)
score = score.sum(1)                       # [m, T]
compress_lens = (torch.arange(1, m3 + 1) * 3 // ratio3).unsqueeze(-1)  # arbitrary-ish lens
score_m = score.masked_fill(torch.arange(T) >= compress_lens, -torch.inf)
tk = min(topk3, m3 * 3 // ratio3)
top = score_m.topk(tk, dim=-1, sorted=False).indices.sort(dim=-1).values
idx3 = torch.where(top < compress_lens, top + 7, -1).int()   # offset=7
# candidates: block_size 4, topk_blocks 3, pin last block
def select_candidate_blocks(logits, lens, topk_blocks, block_size):
    width = logits.size(-1)
    s = F.pad(logits, (0, -width % block_size), value=-torch.inf)
    s = s.unflatten(-1, (-1, block_size)).amax(-1)
    nb = s.size(-1)
    last = (lens - 1) // block_size
    s = s.masked_fill(torch.arange(nb) == last, torch.inf)
    topb = s.topk(min(topk_blocks, nb), dim=-1)
    keep = torch.zeros_like(s, dtype=torch.bool).scatter_(-1, topb.indices, topb.values > -torch.inf)
    return keep.repeat_interleave(block_size, -1)[..., :width]
cand = select_candidate_blocks(score_m, compress_lens, 3, 4)
q3.numpy().tofile(f"{D}/idx_q.bin"); k3.numpy().tofile(f"{D}/idx_k.bin"); w3.numpy().tofile(f"{D}/idx_w.bin")
score_m.numpy().tofile(f"{D}/idx_score.bin"); idx3.numpy().astype(np.int32).tofile(f"{D}/idx_topk.bin")
cand.numpy().astype(np.uint8).tofile(f"{D}/idx_cand.bin")
compress_lens.numpy().astype(np.int64).tofile(f"{D}/idx_lens.bin")

# ---------- A4: window topk idxs (pure int; prefill + decode ring cases)
def window_idxs(win, bsz, seqlen, start_pos):
    if start_pos == 0:
        end = torch.arange(seqlen).unsqueeze(1)
        i = (end - win + 1).clamp(0) + torch.arange(min(seqlen, win))
        i = torch.where(i > end, -1, i)
    else:
        oldest = start_pos % win + 1
        i = torch.cat([torch.arange(oldest, win), torch.arange(oldest)])
        i = torch.where(i > start_pos, -1, i)
    return i.int()
for tag, (win, sl, sp) in {"p_s3w5": (5, 3, 0), "p_s10w4": (4, 10, 0), "d_p7w4": (4, 1, 7), "d_p3w4": (4, 1, 3)}.items():
    window_idxs(win, 1, sl, sp).numpy().astype(np.int32).tofile(f"{D}/win_{tag}.bin")
print("wrote A1 sparse_attn, A2 compressor, A3 indexer, A4 window idxs")
