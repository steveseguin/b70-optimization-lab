"""Offline: can an LTX-shaped transformer block be captured in an XPUGraph on
B70, is replay bit-exact, and how much dispatch cost does it remove?

One block with the checkpoint's real shapes (772 MB of BF16 state) is executed
48 times, which is exactly what one sampler step does: 48 distinct blocks, each
773 MB read from VRAM. Re-running one block re-reads the same 773 MB from VRAM
(far larger than any cache), so per-iteration memory traffic matches.

No ComfyUI, no checkpoint, no server. Weights are random: this measures time and
eager-vs-replay identity, not model outputs.
"""
import json, time, sys
import torch
import torch.nn.functional as F
from torch import nn

DEV = 'xpu:0'
DT = torch.bfloat16
V_DIM, A_DIM = 4096, 2048
V_HEADS, VD_HEAD = 32, 128
A_HEADS, AD_HEAD = 32, 64
M_V, M_A, M_TXT = 64, 26, 128
BLOCKS = 48

def lin(o, i, bias=True):
    return nn.Linear(i, o, bias=bias, dtype=DT, device=DEV)

class Attn(nn.Module):
    """Mirrors CrossAttention: q/k/v/out projections, q/k rms-norm, gate logits."""
    def __init__(self, qd, ctx, heads, dh):
        super().__init__()
        inner = heads * dh
        self.heads, self.dh = heads, dh
        self.to_q, self.to_k, self.to_v = lin(inner, qd), lin(inner, ctx), lin(inner, ctx)
        self.to_out = lin(qd, inner)
        self.q_norm = nn.Parameter(torch.ones(inner, dtype=DT, device=DEV))
        self.k_norm = nn.Parameter(torch.ones(inner, dtype=DT, device=DEV))
        self.to_gate = lin(heads, qd)

    def forward(self, x, ctx):
        B, N, _ = x.shape
        q = F.rms_norm(self.to_q(x), (self.heads * self.dh,), self.q_norm)
        k = F.rms_norm(self.to_k(ctx), (self.heads * self.dh,), self.k_norm)
        v = self.to_v(ctx)
        q = q.view(B, N, self.heads, self.dh).transpose(1, 2)
        k = k.view(B, ctx.shape[1], self.heads, self.dh).transpose(1, 2)
        v = v.view(B, ctx.shape[1], self.heads, self.dh).transpose(1, 2)
        # RoPE-shaped elementwise work on q and k (split-half rotation)
        q = torch.cat((q[..., : self.dh // 2] * 0.5 - q[..., self.dh // 2:] * 0.5,
                       q[..., self.dh // 2:] * 0.5 + q[..., : self.dh // 2] * 0.5), dim=-1)
        k = torch.cat((k[..., : self.dh // 2] * 0.5 - k[..., self.dh // 2:] * 0.5,
                       k[..., self.dh // 2:] * 0.5 + k[..., : self.dh // 2] * 0.5), dim=-1)
        o = F.scaled_dot_product_attention(q, k, v)
        o = o.transpose(1, 2).reshape(B, N, self.heads * self.dh)
        gate = torch.sigmoid(self.to_gate(x)).unsqueeze(-1)
        o = (o.view(B, N, self.heads, self.dh) * gate).reshape(B, N, self.heads * self.dh)
        return self.to_out(o)

class FF(nn.Module):
    def __init__(self, d, mult=4):
        super().__init__()
        self.up, self.down = lin(d * mult, d), lin(d, d * mult)
    def forward(self, x):
        return self.down(F.gelu(self.up(x), approximate='tanh'))

class Block(nn.Module):
    """Mirrors BasicAVTransformerBlock: 6 attentions, 2 feed-forwards, ada tables."""
    def __init__(self):
        super().__init__()
        self.attn1 = Attn(V_DIM, V_DIM, V_HEADS, VD_HEAD)
        self.attn2 = Attn(V_DIM, V_DIM, V_HEADS, VD_HEAD)
        self.audio_attn1 = Attn(A_DIM, A_DIM, A_HEADS, AD_HEAD)
        self.audio_attn2 = Attn(A_DIM, A_DIM, A_HEADS, AD_HEAD)
        self.a2v = Attn(V_DIM, A_DIM, A_HEADS, AD_HEAD)
        self.v2a = Attn(A_DIM, V_DIM, A_HEADS, AD_HEAD)
        self.ff, self.audio_ff = FF(V_DIM), FF(A_DIM)
        self.vtab = nn.Parameter(torch.randn(6, V_DIM, dtype=DT, device=DEV) * 0.02)
        self.atab = nn.Parameter(torch.randn(6, A_DIM, dtype=DT, device=DEV) * 0.02)
        self.ca_v = nn.Parameter(torch.randn(6, V_DIM, dtype=DT, device=DEV) * 0.02)
        self.ca_a = nn.Parameter(torch.randn(6, A_DIM, dtype=DT, device=DEV) * 0.02)

    def ada(self, table, ts, lo, hi):
        # Mirrors get_ada_values: slice the table and add the timestep embedding.
        return [table[i] + ts[..., : table.shape[1]] for i in range(lo, hi)]

    def forward(self, vx, ax, vctx, actx, vts, ats):
        sh, sc = self.ada(self.vtab, vts, 0, 2)
        vn = F.rms_norm(vx, (V_DIM,)) * (1 + sc) + sh
        g = self.ada(self.vtab, vts, 2, 3)[0]
        vx = vx.addcmul(self.attn1(vn, vn), g)
        vx = vx + self.attn2(F.rms_norm(vx, (V_DIM,)), vctx)

        ash, asc = self.ada(self.atab, ats, 0, 2)
        an = F.rms_norm(ax, (A_DIM,)) * (1 + asc) + ash
        ag = self.ada(self.atab, ats, 2, 3)[0]
        ax = ax.addcmul(self.audio_attn1(an, an), ag)
        ax = ax + self.audio_attn2(F.rms_norm(ax, (A_DIM,)), actx)

        an3 = F.rms_norm(ax, (A_DIM,))
        cs, csh = self.ada(self.ca_v, vts, 0, 2)
        vs = F.rms_norm(vx, (V_DIM,)) * (1 + cs) + csh
        acs, acsh = self.ada(self.ca_a, ats, 0, 2)
        asc2 = an3 * (1 + acs) + acsh
        vx = vx.addcmul(self.a2v(vs, asc2), self.ada(self.ca_v, vts, 4, 5)[0])
        ax = ax.addcmul(self.v2a(asc2, vs), self.ada(self.ca_a, ats, 4, 5)[0])

        msh, msc = self.ada(self.vtab, vts, 3, 5)
        vx = vx.addcmul(self.ff(F.rms_norm(vx, (V_DIM,)) * (1 + msc) + msh),
                        self.ada(self.vtab, vts, 5, 6)[0])
        amsh, amsc = self.ada(self.atab, ats, 3, 5)
        ax = ax.addcmul(self.audio_ff(F.rms_norm(ax, (A_DIM,)) * (1 + amsc) + amsh),
                        self.ada(self.atab, ats, 5, 6)[0])
        return vx, ax

def main():
    deterministic = '--deterministic' in sys.argv
    if deterministic:
        torch.use_deterministic_algorithms(True, warn_only=False)
    torch.manual_seed(0)
    block = Block().eval()
    state_bytes = sum(p.numel() * p.element_size() for p in block.parameters())
    res = {'deterministic': deterministic, 'block_state_MB': round(state_bytes / 2**20, 1),
           'blocks_per_step': BLOCKS, 'tokens': {'video': M_V, 'audio': M_A, 'text_context': M_TXT}}

    vx0 = torch.randn(1, M_V, V_DIM, dtype=DT, device=DEV)
    ax0 = torch.randn(1, M_A, A_DIM, dtype=DT, device=DEV)
    vctx = torch.randn(1, M_TXT, V_DIM, dtype=DT, device=DEV)
    actx = torch.randn(1, M_TXT, A_DIM, dtype=DT, device=DEV)
    vts = torch.randn(1, 1, V_DIM, dtype=DT, device=DEV)
    ats = torch.randn(1, 1, A_DIM, dtype=DT, device=DEV)

    def step(vx, ax):
        for _ in range(BLOCKS):
            vx, ax = block(vx, ax, vctx, actx, vts, ats)
        return vx, ax

    def timeit(fn, iters, warmup=2):
        with torch.no_grad():
            for _ in range(warmup): fn()
            torch.xpu.synchronize(DEV)
            t0 = time.perf_counter()
            for _ in range(iters): fn()
            torch.xpu.synchronize(DEV)
        return (time.perf_counter() - t0) / iters

    with torch.no_grad():
        eager_out = step(vx0.clone(), ax0.clone())
    res['eager_step_ms'] = round(timeit(lambda: step(vx0.clone(), ax0.clone()), 5) * 1e3, 3)

    # ---- graph capture ----
    static_vx, static_ax = vx0.clone(), ax0.clone()
    try:
        s = torch.xpu.Stream()
        s.wait_stream(torch.xpu.current_stream())
        with torch.xpu.stream(s), torch.no_grad():
            for _ in range(3):
                step(static_vx.clone(), static_ax.clone())
        torch.xpu.current_stream().wait_stream(s)
        torch.xpu.synchronize(DEV)

        g = torch.xpu.XPUGraph()
        with torch.no_grad(), torch.xpu.graph(g):
            out_vx, out_ax = step(static_vx, static_ax)
        res['capture'] = 'ok'
    except Exception as error:
        res['capture'] = 'FAILED: ' + repr(error)
        print(json.dumps(res, indent=2)); return

    static_vx.copy_(vx0); static_ax.copy_(ax0)
    g.replay(); torch.xpu.synchronize(DEV)
    res['replay_step_ms'] = round(timeit(lambda: g.replay(), 5) * 1e3, 3)
    res['speedup'] = round(res['eager_step_ms'] / res['replay_step_ms'], 3)

    bit = [torch.equal(a.view(torch.int16), b.view(torch.int16))
           for a, b in ((out_vx, eager_out[0]), (out_ax, eager_out[1]))]
    res['replay_bit_equal_to_eager'] = {'video': bool(bit[0]), 'audio': bool(bit[1])}
    static_vx.copy_(vx0); static_ax.copy_(ax0)
    prev = (out_vx.clone(), out_ax.clone())
    g.replay(); torch.xpu.synchronize(DEV)
    res['replay_repeatable'] = {'video': bool(torch.equal(out_vx.view(torch.int16), prev[0].view(torch.int16))),
                                'audio': bool(torch.equal(out_ax.view(torch.int16), prev[1].view(torch.int16)))}
    res['projected_11_step_sampler_s'] = {
        'eager': round(res['eager_step_ms'] * 11 / 1e3, 3),
        'replay': round(res['replay_step_ms'] * 11 / 1e3, 3)}
    print(json.dumps(res, indent=2))

main()
