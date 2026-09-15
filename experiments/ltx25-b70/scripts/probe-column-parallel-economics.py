"""Honest economics of EXACT 2-way column parallelism for the LTX sampler.

Exactness forbids the Megatron column->row trick, because a row-parallel layer
needs a SUM across devices and that changes the reduction order. So every point
that reduces over the feature dimension -- every RMSNorm, every attention output
projection -- needs the full vector, i.e. a gather. And a gather cannot live
inside a per-device graph, so each gather also splits the captured chain into
another segment that must be replayed separately.

Measures: the production baseline, the ideal split with no communication, the
real cost of a gather, and the marginal cost of an extra graph replay.
"""
import json, time, importlib.util
import torch
import torch.nn.functional as F
from torch import nn

spec = importlib.util.spec_from_file_location(
    'probe', '/home/steve/llm-optimizations/experiments/ltx25-b70/scripts/probe-xpugraph-block.py')
base = importlib.util.module_from_spec(spec)
exec(compile(open(spec.origin).read().replace('main()\n', '', 1), spec.origin, 'exec'), base.__dict__)

torch.use_deterministic_algorithms(True, warn_only=False)
torch.manual_seed(0)
DT, V, A = torch.bfloat16, base.V_DIM, base.A_DIM
MV, MA, MT, N = base.M_V, base.M_A, base.M_TXT, base.BLOCKS
D0, D1 = 'xpu:0', 'xpu:1'
res = {'blocks': N, 'video_tokens': MV, 'audio_tokens': MA}

def sync(*d):
    for x in d: torch.xpu.synchronize(x)

def timeit(fn, iters, devs, warmup=3):
    with torch.no_grad():
        for _ in range(warmup): fn()
        sync(*devs); t0 = time.perf_counter()
        for _ in range(iters): fn()
        sync(*devs)
    return (time.perf_counter() - t0) / iters

def capture(fn, dev):
    with torch.xpu.device(dev):
        st = torch.xpu.Stream(device=dev); st.wait_stream(torch.xpu.current_stream(dev))
        with torch.xpu.stream(st), torch.no_grad():
            for _ in range(3): fn()
        torch.xpu.current_stream(dev).wait_stream(st); torch.xpu.synchronize(dev)
        g = torch.xpu.XPUGraph()
        with torch.no_grad(), torch.xpu.graph(g, stream=torch.xpu.Stream(device=dev)):
            out = fn()
        torch.xpu.synchronize(dev)
    return g, out

def make_block(dev, ways):
    """ways=1 is the production block; ways=2 owns half of every projection."""
    base.DEV = dev
    b = base.Block()
    if ways == 2:
        b.attn1 = base.Attn(V, V, base.V_HEADS // 2, base.VD_HEAD)
        b.attn2 = base.Attn(V, V, base.V_HEADS // 2, base.VD_HEAD)
        b.audio_attn1 = base.Attn(A, A, base.A_HEADS // 2, base.AD_HEAD)
        b.audio_attn2 = base.Attn(A, A, base.A_HEADS // 2, base.AD_HEAD)
        b.a2v = base.Attn(V, A, base.A_HEADS // 2, base.AD_HEAD)
        b.v2a = base.Attn(A, V, base.A_HEADS // 2, base.AD_HEAD)
        ff = base.FF(V); ff.up = nn.Linear(V, V * 4 // 2, dtype=DT, device=dev)
        ff.down = nn.Linear(V * 4 // 2, V, dtype=DT, device=dev); b.ff = ff
        aff = base.FF(A); aff.up = nn.Linear(A, A * 4 // 2, dtype=DT, device=dev)
        aff.down = nn.Linear(A * 4 // 2, A, dtype=DT, device=dev); b.audio_ff = aff
    return b.eval()

def chain(block, dev, n=N):
    vx = torch.randn(1, MV, V, dtype=DT, device=dev)
    ax = torch.randn(1, MA, A, dtype=DT, device=dev)
    ctx = (torch.randn(1, MT, V, dtype=DT, device=dev), torch.randn(1, MT, A, dtype=DT, device=dev),
           torch.randn(1, 1, V, dtype=DT, device=dev), torch.randn(1, 1, A, dtype=DT, device=dev))
    def run():
        v, a = vx, ax
        for _ in range(n):
            v, a = block(v, a, *ctx)
        return v, a
    return run

full = make_block(D0, 1)
res['full_block_MB'] = round(sum(p.numel() * p.element_size() for p in full.parameters()) / 2**20, 1)
g_full, _ = capture(chain(full, D0), D0)
res['A_production_serial_ms'] = round(timeit(g_full.replay, 5, (D0,)) * 1e3, 3)

half = {d: make_block(d, 2) for d in (D0, D1)}
res['half_block_MB'] = round(sum(p.numel() * p.element_size() for p in half[D0].parameters()) / 2**20, 1)
gh = {d: capture(chain(half[d], d), d)[0] for d in (D0, D1)}
def both():
    gh[D0].replay(); gh[D1].replay()
res['B_ideal_split_no_comms_ms'] = round(timeit(both, 5, (D0, D1)) * 1e3, 3)

# cost of one gather pair (each device receives the other's half of vx and ax)
hv = {d: torch.empty(1, MV, V // 2, dtype=DT, device=d) for d in (D0, D1)}
ha = {d: torch.empty(1, MA, A // 2, dtype=DT, device=d) for d in (D0, D1)}
sv = {d: torch.randn(1, MV, V // 2, dtype=DT, device=d) for d in (D0, D1)}
sa = {d: torch.randn(1, MA, A // 2, dtype=DT, device=d) for d in (D0, D1)}
def gather():
    hv[D0].copy_(sv[D1]); hv[D1].copy_(sv[D0])
    ha[D0].copy_(sa[D1]); ha[D1].copy_(sa[D0])
res['gather_pair_ms'] = round(timeit(gather, 100, (D0, D1)) * 1e3, 4)

# marginal cost of an extra graph replay: a gather splits the chain into segments
tiny = make_block(D0, 2)
g1 = capture(chain(tiny, D0, 1), D0)[0]
def r1():
    for _ in range(96): g1.replay()
def r2():
    for _ in range(192): g1.replay()
res['replay_overhead_us'] = round((timeit(r2, 3, (D0,)) - timeit(r1, 3, (D0,))) / 96 * 1e6, 1)

ideal, gp, ro = res['B_ideal_split_no_comms_ms'], res['gather_pair_ms'], res['replay_overhead_us']
res['projected'] = {}
for per_block in (4, 8, 12, 16):
    segments = per_block  # each gather ends a captured segment on each device
    comms = gp * per_block * N
    extra_replays = ro * 1e-3 * (segments - 1) * N * 2
    total = ideal + comms + extra_replays
    res['projected'][f'{per_block}_gathers_per_block'] = {
        'gather_ms': round(comms, 2), 'extra_replay_ms': round(extra_replays, 2),
        'total_ms': round(total, 2),
        'speedup_vs_production': round(res['A_production_serial_ms'] / total, 3)}
print(json.dumps(res, indent=2))
