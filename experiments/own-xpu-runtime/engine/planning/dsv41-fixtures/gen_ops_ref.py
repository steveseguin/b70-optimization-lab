# Combined reference dumps: SwiGLU-clamp epilogue, engram gate, YaRN rope.
# Semantics from official inference/model.py (DeepSeek-V4.1-Flash-1017, MIT).
import math
import numpy as np
import torch

D = "/tmp"
torch.manual_seed(0xD543)

# --- 1) SwiGLU clamp epilogue (Expert.forward): silu(clamp(gate, max=10)) * clamp(up, +-10)
n, inter = 128, 2304
gate = torch.randn(n, inter, dtype=torch.float32) * 6.0   # exercises both clamp rails
up   = torch.randn(n, inter, dtype=torch.float32) * 6.0
for tag, dt in (("f64", torch.float64), ("f32", torch.float32)):
    g = gate.to(dt).clamp(max=10.0); u = up.to(dt).clamp(-10.0, 10.0)
    y = torch.nn.functional.silu(g) * u
    y.cpu().numpy().astype(getattr(np, "float" + tag[1:])).tofile(f"{D}/swiglu_y_{tag}.bin")
gate.numpy().tofile(f"{D}/swiglu_gate.bin"); up.numpy().tofile(f"{D}/swiglu_up.bin")

# --- 2) Engram gate (Engram.forward post-gather): normalized dot, signed-sqrt sigmoid
dim, hc = 5120, 4
B = 64
h = torch.randn(B, hc, dim, dtype=torch.float32) * 1.5
key = torch.randn(B, hc, dim, dtype=torch.float32) * 1.5
value = torch.randn(B, dim, dtype=torch.float32)
qw = torch.randn(hc, dim, dtype=torch.float32).abs() + 0.2
kw = torch.randn(hc, dim, dtype=torch.float32).abs() + 0.2
eps, clamp_value = 1e-20, 1e-6
mask = torch.ones(B, dtype=torch.bool); mask[5] = False; mask[40] = False

def engram_gate(h, key, value, qw, kw, mask, dt):
    h = h.to(dt); key = key.to(dt); value = value.to(dt)
    weight = qw.to(dt) * kw.to(dt)
    rstd = torch.rsqrt(h.square().mean(-1) + eps) * torch.rsqrt(key.square().mean(-1) + eps)
    dot = (h * weight * key).sum(-1) * rstd * dim**-0.5
    gate = torch.sigmoid(torch.copysign(dot.abs().clamp_min(clamp_value).sqrt(), dot))
    gate = torch.where(mask.view(-1, 1), gate, torch.zeros_like(gate))
    return h + gate.unsqueeze(-1) * value.unsqueeze(-2)

for tag, dt in (("f64", torch.float64), ("f32", torch.float32)):
    y = engram_gate(h, key, value, qw, kw, mask, dt)
    y.cpu().numpy().astype(getattr(np, "float" + tag[1:])).tofile(f"{D}/eng_y_{tag}.bin")
for nm, t in (("h", h), ("key", key), ("value", value), ("qw", qw), ("kw", kw)):
    t.numpy().tofile(f"{D}/eng_{nm}.bin")
mask.numpy().astype(np.uint8).tofile(f"{D}/eng_mask.bin")

# --- 3) YaRN rope table + rotation (precompute_freqs_cis / apply_rotary_emb)
rdim, seqlen, orig, base, factor, bf, bs = 64, 4096, 65536, 10000.0, 16.0, 32, 1
freqs = 1.0 / (base ** (torch.arange(0, rdim, 2, dtype=torch.float32) / rdim))
def corrected_dim(rot):
    return rdim * math.log(orig / (rot * 2 * math.pi)) / (2 * math.log(base))
low = max(math.floor(corrected_dim(bf)), 0)
high = min(math.ceil(corrected_dim(bs)), rdim - 1)
ramp = ((torch.arange(rdim // 2, dtype=torch.float32) - low) / max(high - low, 1e-3)).clamp(0, 1)
freqs64 = freqs.to(torch.float64) / factor * ramp + freqs.to(torch.float64) * (1 - ramp)
pos = torch.arange(seqlen, dtype=torch.float64)
fr = torch.outer(pos, freqs64)                       # [seqlen, rdim/2] angles
# dump as cos/sin f64
torch.cos(fr).numpy().tofile(f"{D}/rope_cos.bin")
torch.sin(fr).numpy().tofile(f"{D}/rope_sin.bin")
# rotation gate on random heads
h_, d_ = 3, 64
x = torch.randn(17, h_, rdim, dtype=torch.float32)   # [s, h, d] positions 0..16
xf = x.to(torch.float64).view(17, h_, rdim // 2, 2)
xc = torch.view_as_complex(xf.contiguous())
fsub = torch.polar(torch.ones_like(fr[:17]), fr[:17])
def rot(xc, f, inv):
    if inv: f = f.conj()
    return torch.view_as_real(xc * f.view(-1, 1, f.shape[-1])).flatten(-2)
for inv, tag in ((False, "fwd"), (True, "inv")):
    y = rot(xc, fsub, inv)
    y.numpy().tofile(f"{D}/rope_x_{tag}.bin")
x.numpy().tofile(f"{D}/rope_x.bin")
print("wrote swiglu(128x2304), engram-gate(64x4x5120), rope(64d 4096p + 17x3x64 rotations)")
