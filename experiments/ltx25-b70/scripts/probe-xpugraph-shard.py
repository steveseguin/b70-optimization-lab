"""Two-device graph capture, matching the real LTX shard: blocks 0-20 on xpu:0,
blocks 21-47 on xpu:1, with one cross-device activation handoff between them."""
import json, time, importlib.util, sys
import torch

spec = importlib.util.spec_from_file_location('probe', __file__.replace('_shard_probe', '_probe'))
mod = importlib.util.module_from_spec(spec)
src = open(spec.origin).read().replace('main()\n', '', 1)
exec(compile(src, spec.origin, 'exec'), mod.__dict__)

torch.use_deterministic_algorithms(True, warn_only=False)
torch.manual_seed(0)
SPLIT = 21
res = {'split_index': SPLIT, 'devices': ['xpu:0', 'xpu:1']}

def build(dev):
    mod.DEV = dev
    b = mod.Block().eval()
    return b

b0, b1 = build('xpu:0'), build('xpu:1')
def inputs(dev):
    return (torch.randn(1, mod.M_V, mod.V_DIM, dtype=mod.DT, device=dev),
            torch.randn(1, mod.M_A, mod.A_DIM, dtype=mod.DT, device=dev),
            torch.randn(1, mod.M_TXT, mod.V_DIM, dtype=mod.DT, device=dev),
            torch.randn(1, mod.M_TXT, mod.A_DIM, dtype=mod.DT, device=dev),
            torch.randn(1, 1, mod.V_DIM, dtype=mod.DT, device=dev),
            torch.randn(1, 1, mod.A_DIM, dtype=mod.DT, device=dev))
vx0, ax0, vctx0, actx0, vts0, ats0 = inputs('xpu:0')
vctx1 = vctx0.to('xpu:1'); actx1 = actx0.to('xpu:1')
vts1 = vts0.to('xpu:1'); ats1 = ats0.to('xpu:1')

def half(block, vx, ax, vctx, actx, vts, ats, n):
    for _ in range(n):
        vx, ax = block(vx, ax, vctx, actx, vts, ats)
    return vx, ax

def eager_step(vx, ax):
    vx, ax = half(b0, vx, ax, vctx0, actx0, vts0, ats0, SPLIT)
    vx, ax = vx.to('xpu:1'), ax.to('xpu:1')
    vx, ax = half(b1, vx, ax, vctx1, actx1, vts1, ats1, 48 - SPLIT)
    return vx.to('xpu:0'), ax.to('xpu:0')

def sync():
    torch.xpu.synchronize('xpu:0'); torch.xpu.synchronize('xpu:1')

def timeit(fn, iters, warmup=2):
    with torch.no_grad():
        for _ in range(warmup): fn()
        sync(); t0 = time.perf_counter()
        for _ in range(iters): fn()
        sync()
    return (time.perf_counter() - t0) / iters

with torch.no_grad():
    ref = eager_step(vx0.clone(), ax0.clone())
res['eager_step_ms'] = round(timeit(lambda: eager_step(vx0.clone(), ax0.clone()), 5) * 1e3, 3)

# Static buffers: one set per device, plus the handoff buffers.
s_vx0, s_ax0 = vx0.clone(), ax0.clone()
mid_vx0 = torch.empty_like(vx0); mid_ax0 = torch.empty_like(ax0)
s_vx1 = torch.empty(1, mod.M_V, mod.V_DIM, dtype=mod.DT, device='xpu:1')
s_ax1 = torch.empty(1, mod.M_A, mod.A_DIM, dtype=mod.DT, device='xpu:1')
try:
    graphs = {}
    for tag, dev, fn in (('g0', 'xpu:0', lambda: half(b0, s_vx0, s_ax0, vctx0, actx0, vts0, ats0, SPLIT)),
                         ('g1', 'xpu:1', lambda: half(b1, s_vx1, s_ax1, vctx1, actx1, vts1, ats1, 48 - SPLIT))):
        with torch.xpu.device(dev):
            st = torch.xpu.Stream()
            st.wait_stream(torch.xpu.current_stream())
            with torch.xpu.stream(st), torch.no_grad():
                for _ in range(3): fn()
            torch.xpu.current_stream().wait_stream(st)
            torch.xpu.synchronize(dev)
            # torch.xpu.graph caches ONE class-level capture stream bound to the
            # first device it was used on. Capturing on a second device with that
            # stream records an empty graph (only a UserWarning). Supply an
            # explicit per-device capture stream and then prove it is non-empty.
            cap = torch.xpu.Stream(device=dev)
            g = torch.xpu.XPUGraph()
            with torch.no_grad(), torch.xpu.graph(g, stream=cap):
                out = fn()
            graphs[tag] = (g, out)
    res['capture'] = 'ok'
    # Non-emptiness proof: perturb the static input, replay, require the output to move.
    for tag, sv in (('g0', s_vx0), ('g1', s_vx1)):
        g, (ovx, _) = graphs[tag]
        before = ovx.clone()
        sv.add_(1.0)
        g.replay(); sync()
        if torch.equal(ovx.view(torch.int16), before.view(torch.int16)):
            raise RuntimeError('Captured graph ' + tag + ' is inert; replay ignored its input')
        sv.sub_(1.0)
        g.replay(); sync()
except Exception as e:
    res['capture'] = 'FAILED: ' + repr(e)
    print(json.dumps(res, indent=2)); sys.exit(0)

g0, (o_vx0, o_ax0) = graphs['g0']
g1, (o_vx1, o_ax1) = graphs['g1']

def replay_step():
    g0.replay()
    s_vx1.copy_(o_vx0); s_ax1.copy_(o_ax0)
    g1.replay()
    mid_vx0.copy_(o_vx1); mid_ax0.copy_(o_ax1)
    return mid_vx0, mid_ax0

s_vx0.copy_(vx0); s_ax0.copy_(ax0)
out = replay_step(); sync()
res['replay_step_ms'] = round(timeit(replay_step, 5) * 1e3, 3)
res['speedup'] = round(res['eager_step_ms'] / res['replay_step_ms'], 3)
res['replay_bit_equal_to_eager'] = {
    'video': bool(torch.equal(out[0].view(torch.int16), ref[0].view(torch.int16))),
    'audio': bool(torch.equal(out[1].view(torch.int16), ref[1].view(torch.int16)))}
res['handoff_copy_ms'] = round(timeit(lambda: (s_vx1.copy_(o_vx0), s_ax1.copy_(o_ax0)), 50) * 1e3, 4)
res['projected_11_step_sampler_s'] = {'eager': round(res['eager_step_ms'] * 11 / 1e3, 3),
                                      'replay': round(res['replay_step_ms'] * 11 / 1e3, 3)}
print(json.dumps(res, indent=2))
