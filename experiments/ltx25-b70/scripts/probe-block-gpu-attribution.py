"""Where does a graph-replayed LTX block actually spend its GPU time?

XPU graph events cannot be profiled, so attribution is by skip-differencing:
capture the 48-block chain with one component disabled and subtract. Shapes are
held constant so the comparison is like-for-like; outputs are meaningless.
"""
import json, time, importlib.util
import torch
import torch.nn.functional as F

spec = importlib.util.spec_from_file_location(
    'probe', '/home/steve/llm-optimizations/experiments/ltx25-b70/scripts/probe-xpugraph-block.py')
b = importlib.util.module_from_spec(spec)
exec(compile(open(spec.origin).read().replace('main()\n', '', 1), spec.origin, 'exec'), b.__dict__)

torch.use_deterministic_algorithms(True, warn_only=False)
torch.manual_seed(0)
DT, V, A = torch.bfloat16, b.V_DIM, b.A_DIM
MV, MA, MT, N, DEV = b.M_V, b.M_A, b.M_TXT, b.BLOCKS, 'xpu:0'
b.DEV = DEV

_ORIG_ATTN_FORWARD = b.Attn.forward

def _patched_attn_forward(self, x, ctx):
    S = Flexible.SKIP
    B, Nq, _ = x.shape
    q = F.rms_norm(self.to_q(x), (self.heads * self.dh,), self.q_norm)
    k = F.rms_norm(self.to_k(ctx), (self.heads * self.dh,), self.k_norm)
    v = self.to_v(ctx)
    q = q.view(B, Nq, self.heads, self.dh).transpose(1, 2)
    k = k.view(B, ctx.shape[1], self.heads, self.dh).transpose(1, 2)
    v = v.view(B, ctx.shape[1], self.heads, self.dh).transpose(1, 2)
    if 'rope' not in S:
        q = torch.cat((q[..., : self.dh // 2] * 0.5 - q[..., self.dh // 2:] * 0.5,
                       q[..., self.dh // 2:] * 0.5 + q[..., : self.dh // 2] * 0.5), dim=-1)
        k = torch.cat((k[..., : self.dh // 2] * 0.5 - k[..., self.dh // 2:] * 0.5,
                       k[..., self.dh // 2:] * 0.5 + k[..., : self.dh // 2] * 0.5), dim=-1)
    if 'sdpa' in S:
        o = v if v.shape[2] == q.shape[2] else v[:, :, :1].expand(-1, -1, q.shape[2], -1)
    else:
        o = F.scaled_dot_product_attention(q, k, v)
    o = o.transpose(1, 2).reshape(B, Nq, self.heads * self.dh)
    if 'gate' not in S:
        gate = torch.sigmoid(self.to_gate(x)).unsqueeze(-1)
        o = (o.view(B, Nq, self.heads, self.dh) * gate).reshape(B, Nq, self.heads * self.dh)
    if 'proj_out' in S:
        return o[..., : self.to_out.out_features] if o.shape[-1] >= self.to_out.out_features else o
    return self.to_out(o)

b.Attn.forward = _patched_attn_forward


class Flexible(b.Block):
    """The same block with individual components switchable off."""
    SKIP = set()
    def forward(self, vx, ax, vctx, actx, vts, ats):
        S = self.SKIP
        norm = (lambda t, d: t) if 'norm' in S else (lambda t, d: F.rms_norm(t, (d,)))
        if 'attn' not in S:
            sh, sc = self.vtab[0] + vts, self.vtab[1] + vts
            vn = norm(vx, V) * (1 + sc) + sh
            vx = vx.addcmul(self.attn1(vn, vn), self.vtab[2] + vts)
            vx = vx + self.attn2(norm(vx, V), vctx)
            an = norm(ax, A) * (1 + (self.atab[1] + ats)) + (self.atab[0] + ats)
            ax = ax.addcmul(self.aattn1(an, an) if hasattr(self, 'aattn1') else self.audio_attn1(an, an),
                            self.atab[2] + ats)
            ax = ax + self.audio_attn2(norm(ax, A), actx)
            vs, asc = norm(vx, V), norm(ax, A)
            vx = vx.addcmul(self.a2v(vs, asc), self.ca_v[4] + vts)
            ax = ax.addcmul(self.v2a(asc, vs), self.ca_a[4] + ats)
        if 'ff' not in S:
            h = F.gelu(self.ff.up(norm(vx, V) * (1 + (self.vtab[4] + vts)) + (self.vtab[3] + vts)),
                       approximate='tanh')
            vx = vx.addcmul(self.ff.down(h), self.vtab[5] + vts)
            ah = F.gelu(self.audio_ff.up(norm(ax, A)), approximate='tanh')
            ax = ax.addcmul(self.audio_ff.down(ah), self.atab[5] + ats)
        return vx, ax

def timed(skip):
    Flexible.SKIP = set(skip)
    torch.manual_seed(0)
    blk = Flexible().eval()
    vx = torch.randn(1, MV, V, dtype=DT, device=DEV); ax = torch.randn(1, MA, A, dtype=DT, device=DEV)
    ctx = (torch.randn(1, MT, V, dtype=DT, device=DEV), torch.randn(1, MT, A, dtype=DT, device=DEV),
           torch.randn(1, 1, V, dtype=DT, device=DEV), torch.randn(1, 1, A, dtype=DT, device=DEV))
    def run():
        v, a = vx, ax
        for _ in range(N):
            v, a = blk(v, a, *ctx)
        return v, a
    with torch.xpu.device(DEV):
        st = torch.xpu.Stream(device=DEV); st.wait_stream(torch.xpu.current_stream(DEV))
        with torch.xpu.stream(st), torch.no_grad():
            for _ in range(3): run()
        torch.xpu.current_stream(DEV).wait_stream(st); torch.xpu.synchronize(DEV)
        g = torch.xpu.XPUGraph()
        with torch.no_grad(), torch.xpu.graph(g, stream=torch.xpu.Stream(device=DEV)):
            run()
        torch.xpu.synchronize(DEV)
        for _ in range(3): g.replay()
        torch.xpu.synchronize(DEV); t0 = time.perf_counter()
        for _ in range(5): g.replay()
        torch.xpu.synchronize(DEV)
    ms = (time.perf_counter() - t0) / 5 * 1e3
    del blk, g
    torch.xpu.empty_cache()
    return round(ms, 3)

full = timed([])
no_sdpa = timed(['sdpa'])
no_rope = timed(['rope'])
no_gate = timed(['gate'])
no_ff = timed(['ff'])
no_attn = timed(['attn'])
no_norm = timed(['norm'])
empty = 0.0  # both disabled leaves a passthrough; the graph is legitimately empty
res = {'blocks': N, 'full_chain_ms': full, 'per_block_ms': round(full / N, 4),
       'variants': {'no_feedforward': no_ff, 'no_attention': no_attn,
                    'no_norms': no_norm, 'no_sdpa': no_sdpa,
                    'no_rope': no_rope, 'no_gate': no_gate},
       'attribution_ms': {
           'feedforward': round(full - no_ff, 2),
           'attention_block': round(full - no_attn, 2),
           'norms_and_elementwise': round(full - no_norm, 2),
           'sdpa_only': round(full - no_sdpa, 2),
           'rope_only': round(full - no_rope, 2),
           'attention_gate_only': round(full - no_gate, 2),
           },
       'attribution_pct': {
           'feedforward': round(100 * (full - no_ff) / full, 1),
           'attention_block': round(100 * (full - no_attn) / full, 1),
           'norms_and_elementwise': round(100 * (full - no_norm) / full, 1),
           'sdpa_only': round(100 * (full - no_sdpa) / full, 1),
           'rope_only': round(100 * (full - no_rope) / full, 1),
           'attention_gate_only': round(100 * (full - no_gate) / full, 1)}}
# weight-read roofline for the same chain
bytes_per_block = 737.5 * 2**20
res['weight_bytes_GB'] = round(bytes_per_block * N / 1e9, 2)
res['roofline_ms_at_537GBps'] = round(bytes_per_block * N / 537e9 * 1e3, 2)
res['above_roofline'] = round(full / res['roofline_ms_at_537GBps'], 2)
print(json.dumps(res, indent=2))
