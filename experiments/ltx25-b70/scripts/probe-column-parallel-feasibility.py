"""Feasibility probe: does 2-way output-column parallelism across two B70s
actually speed up a graph-replayed LTX block, once the cross-device gathers are
paid for?

Each device owns HALF the output columns of every large projection and computes
its half with the full K reduction, which is the only split shown bit-identical
offline. Halves are concatenated on the owning device before any nonlinearity.
Everything is graph-captured per device, exactly as the landed packet does.
"""
import json, time, importlib.util
import torch
import torch.nn.functional as F
from torch import nn

spec = importlib.util.spec_from_file_location('probe', __file__.replace('colparallel_probe', 'xpugraph_probe'))
base = importlib.util.module_from_spec(spec)
exec(compile(open(spec.origin).read().replace('main()\n', '', 1), spec.origin, 'exec'), base.__dict__)

torch.use_deterministic_algorithms(True, warn_only=False)
torch.manual_seed(0)
DT, V, A = torch.bfloat16, base.V_DIM, base.A_DIM
MV, MA, MT = base.M_V, base.M_A, base.M_TXT
BLOCKS = base.BLOCKS
res = {'blocks_per_step': BLOCKS, 'tokens': {'video': MV, 'audio': MA, 'text': MT}}

def sync(*devs):
    for d in devs: torch.xpu.synchronize(d)

def timeit(fn, iters, devs, warmup=2):
    with torch.no_grad():
        for _ in range(warmup): fn()
        sync(*devs); t0 = time.perf_counter()
        for _ in range(iters): fn()
        sync(*devs)
    return (time.perf_counter() - t0) / iters

def capture(fn, dev):
    st = torch.xpu.Stream(device=dev); st.wait_stream(torch.xpu.current_stream(dev))
    with torch.xpu.stream(st), torch.no_grad():
        for _ in range(3): fn()
    torch.xpu.current_stream(dev).wait_stream(st); torch.xpu.synchronize(dev)
    g = torch.xpu.XPUGraph()
    with torch.no_grad(), torch.xpu.graph(g, stream=torch.xpu.Stream(device=dev)):
        out = fn()
    torch.xpu.synchronize(dev)
    return g, out

# ---------- Baseline: today's layout, one full block on one device ----------
base.DEV = 'xpu:0'
whole = base.Block().eval()
bytes_per_block = sum(p.numel() * p.element_size() for p in whole.parameters())
res['block_state_MB'] = round(bytes_per_block / 2**20, 1)
vx0 = torch.randn(1, MV, V, dtype=DT, device='xpu:0')
ax0 = torch.randn(1, MA, A, dtype=DT, device='xpu:0')
ctx = {d: (torch.randn(1, MT, V, dtype=DT, device=d), torch.randn(1, MT, A, dtype=DT, device=d),
           torch.randn(1, 1, V, dtype=DT, device=d), torch.randn(1, 1, A, dtype=DT, device=d))
       for d in ('xpu:0', 'xpu:1')}

sv, sa = vx0.clone(), ax0.clone()
def serial():
    vx, ax = sv, sa
    for _ in range(BLOCKS):
        vx, ax = whole(vx, ax, *ctx['xpu:0'])
    return vx, ax
g_ser, _ = capture(serial, 'xpu:0')
res['serial_one_device_ms'] = round(timeit(g_ser.replay, 5, ('xpu:0',)) * 1e3, 3)

# ---------- Column-parallel halves on two devices ----------
class HalfBlock(nn.Module):
    """Owns half the output columns of every projection in the block."""
    def __init__(self, dev):
        super().__init__()
        base.DEV = dev
        self.attn1 = base.Attn(V, V, base.V_HEADS // 2, base.VD_HEAD)
        self.attn2 = base.Attn(V, V, base.V_HEADS // 2, base.VD_HEAD)
        self.aattn1 = base.Attn(A, A, base.A_HEADS // 2, base.AD_HEAD)
        self.aattn2 = base.Attn(A, A, base.A_HEADS // 2, base.AD_HEAD)
        self.a2v = base.Attn(V, A, base.A_HEADS // 2, base.AD_HEAD)
        self.v2a = base.Attn(A, V, base.A_HEADS // 2, base.AD_HEAD)
        self.ff_up = nn.Linear(V, V * 4 // 2, dtype=DT, device=dev)
        self.ff_down = nn.Linear(V * 4 // 2, V, dtype=DT, device=dev)
        self.aff_up = nn.Linear(A, A * 4 // 2, dtype=DT, device=dev)
        self.aff_down = nn.Linear(A * 4 // 2, A, dtype=DT, device=dev)
        self.vtab = nn.Parameter(torch.randn(6, V, dtype=DT, device=dev) * 0.02)
        self.atab = nn.Parameter(torch.randn(6, A, dtype=DT, device=dev) * 0.02)

    def forward(self, vx, ax, vctx, actx, vts, ats):
        sh = self.vtab[0] + vts; sc = self.vtab[1] + vts
        vn = F.rms_norm(vx, (V,)) * (1 + sc) + sh
        vx = vx.addcmul(self.attn1(vn, vn), self.vtab[2] + vts)
        vx = vx + self.attn2(F.rms_norm(vx, (V,)), vctx)
        an = F.rms_norm(ax, (A,)) * (1 + (self.atab[1] + ats)) + (self.atab[0] + ats)
        ax = ax.addcmul(self.aattn1(an, an), self.atab[2] + ats)
        ax = ax + self.aattn2(F.rms_norm(ax, (A,)), actx)
        vs = F.rms_norm(vx, (V,)); asc = F.rms_norm(ax, (A,))
        vx = vx.addcmul(self.a2v(vs, asc), self.vtab[4] + vts)
        ax = ax.addcmul(self.v2a(asc, vs), self.atab[4] + ats)
        h = F.gelu(self.ff_up(F.rms_norm(vx, (V,)) * (1 + (self.vtab[4] + vts)) + (self.vtab[3] + vts)),
                   approximate='tanh')
        vx = vx.addcmul(self.ff_down(h), self.vtab[5] + vts)
        ah = F.gelu(self.aff_up(F.rms_norm(ax, (A,))), approximate='tanh')
        ax = ax.addcmul(self.aff_down(ah), self.atab[5] + ats)
        return vx, ax

halves = {d: HalfBlock(d).eval() for d in ('xpu:0', 'xpu:1')}
res['half_block_state_MB'] = round(sum(p.numel() * p.element_size()
                                       for p in halves['xpu:0'].parameters()) / 2**20, 1)
buf = {d: (torch.randn(1, MV, V, dtype=DT, device=d), torch.randn(1, MA, A, dtype=DT, device=d))
       for d in ('xpu:0', 'xpu:1')}

def half_chain(dev):
    def run():
        vx, ax = buf[dev]
        for _ in range(BLOCKS):
            vx, ax = halves[dev](vx, ax, *ctx[dev])
        return vx, ax
    return run

g0, o0 = capture(half_chain('xpu:0'), 'xpu:0')
g1, o1 = capture(half_chain('xpu:1'), 'xpu:1')
res['half_chain_xpu0_ms'] = round(timeit(g0.replay, 5, ('xpu:0',)) * 1e3, 3)
res['half_chain_xpu1_ms'] = round(timeit(g1.replay, 5, ('xpu:1',)) * 1e3, 3)

def both_concurrent():
    g0.replay(); g1.replay()
res['both_devices_concurrent_ms'] = round(timeit(both_concurrent, 5, ('xpu:0', 'xpu:1')) * 1e3, 3)
res['concurrency_factor'] = round(
    (res['half_chain_xpu0_ms'] + res['half_chain_xpu1_ms']) / res['both_devices_concurrent_ms'], 3)

# ---------- Cost of the per-block cross-device gathers ----------
gather_v = torch.empty(1, MV, V, dtype=DT, device='xpu:0')
gather_a = torch.empty(1, MA, A, dtype=DT, device='xpu:0')
src_v, src_a = buf['xpu:1']
def one_gather():
    gather_v.copy_(src_v); gather_a.copy_(src_a)
res['one_gather_pair_ms'] = round(timeit(one_gather, 50, ('xpu:0', 'xpu:1')) * 1e3, 4)
for per_block in (2, 4, 6):
    res[f'gathers_{per_block}_per_block_total_ms'] = round(
        res['one_gather_pair_ms'] * per_block * BLOCKS, 2)
res['projection'] = {
    'today_serial_ms': res['serial_one_device_ms'],
    'ideal_split_ms': round(res['both_devices_concurrent_ms'], 3),
    'with_4_gathers_per_block_ms': round(res['both_devices_concurrent_ms']
                                         + res['one_gather_pair_ms'] * 4 * BLOCKS, 3)}
print(json.dumps(res, indent=2))
