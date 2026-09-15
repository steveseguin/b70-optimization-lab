"""Design probe: 48 separate per-block graph replays (which the existing
set_model_patch_replace hook can drive directly) versus one graph covering all
48 block executions. Decides how invasive the integration has to be."""
import json, time, importlib.util, torch
spec = importlib.util.spec_from_file_location('probe', __file__.replace('_perblock_probe', '_probe'))
mod = importlib.util.module_from_spec(spec)
exec(compile(open(spec.origin).read().replace('main()\n', '', 1), spec.origin, 'exec'), mod.__dict__)
torch.use_deterministic_algorithms(True, warn_only=False)
torch.manual_seed(0)
DEV = 'xpu:0'
block = mod.Block().eval()
vx0 = torch.randn(1, mod.M_V, mod.V_DIM, dtype=mod.DT, device=DEV)
ax0 = torch.randn(1, mod.M_A, mod.A_DIM, dtype=mod.DT, device=DEV)
vctx = torch.randn(1, mod.M_TXT, mod.V_DIM, dtype=mod.DT, device=DEV)
actx = torch.randn(1, mod.M_TXT, mod.A_DIM, dtype=mod.DT, device=DEV)
vts = torch.randn(1, 1, mod.V_DIM, dtype=mod.DT, device=DEV)
ats = torch.randn(1, 1, mod.A_DIM, dtype=mod.DT, device=DEV)
N = mod.BLOCKS

def sync(): torch.xpu.synchronize(DEV)
def timeit(fn, iters, warmup=2):
    with torch.no_grad():
        for _ in range(warmup): fn()
        sync(); t0 = time.perf_counter()
        for _ in range(iters): fn()
        sync()
    return (time.perf_counter() - t0) / iters

def eager(vx, ax):
    for _ in range(N):
        vx, ax = block(vx, ax, vctx, actx, vts, ats)
    return vx, ax
with torch.no_grad():
    ref = eager(vx0.clone(), ax0.clone())
res = {'eager_step_ms': round(timeit(lambda: eager(vx0.clone(), ax0.clone()), 5) * 1e3, 3)}

# --- A: one graph over all 48 executions ---
sv, sa = vx0.clone(), ax0.clone()
st = torch.xpu.Stream(device=DEV); st.wait_stream(torch.xpu.current_stream())
with torch.xpu.stream(st), torch.no_grad():
    for _ in range(3): eager(sv.clone(), sa.clone())
torch.xpu.current_stream().wait_stream(st); sync()
gA = torch.xpu.XPUGraph()
with torch.no_grad(), torch.xpu.graph(gA, stream=torch.xpu.Stream(device=DEV)):
    oA = eager(sv, sa)
sv.copy_(vx0); sa.copy_(ax0); gA.replay(); sync()
res['single_graph_ms'] = round(timeit(gA.replay, 5) * 1e3, 3)
res['single_graph_bit_equal'] = bool(torch.equal(oA[0].view(torch.int16), ref[0].view(torch.int16))
                                     and torch.equal(oA[1].view(torch.int16), ref[1].view(torch.int16)))

# --- B: one captured block, replayed 48 times with input copies between ---
bv, ba = vx0.clone(), ax0.clone()
st2 = torch.xpu.Stream(device=DEV); st2.wait_stream(torch.xpu.current_stream())
with torch.xpu.stream(st2), torch.no_grad():
    for _ in range(3): block(bv.clone(), ba.clone(), vctx, actx, vts, ats)
torch.xpu.current_stream().wait_stream(st2); sync()
gB = torch.xpu.XPUGraph()
with torch.no_grad(), torch.xpu.graph(gB, stream=torch.xpu.Stream(device=DEV)):
    oBv, oBa = block(bv, ba, vctx, actx, vts, ats)
def per_block():
    bv.copy_(vx0); ba.copy_(ax0)
    for _ in range(N):
        gB.replay()
        bv.copy_(oBv); ba.copy_(oBa)
    return bv, ba
per_block(); sync()
res['per_block_graph_ms'] = round(timeit(per_block, 5) * 1e3, 3)
outv, outa = per_block(); sync()
res['per_block_bit_equal'] = bool(torch.equal(outv.view(torch.int16), ref[0].view(torch.int16))
                                  and torch.equal(outa.view(torch.int16), ref[1].view(torch.int16)))
res['single_graph_speedup'] = round(res['eager_step_ms'] / res['single_graph_ms'], 3)
res['per_block_speedup'] = round(res['eager_step_ms'] / res['per_block_graph_ms'], 3)
res['per_replay_overhead_us'] = round((res['per_block_graph_ms'] - res['single_graph_ms']) / N * 1e3, 1)
print(json.dumps(res, indent=2))
