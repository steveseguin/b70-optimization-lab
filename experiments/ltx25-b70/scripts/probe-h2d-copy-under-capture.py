"""Is a host->device copy of per-call host data safe inside an XPU graph capture?

The LTX decoder builds its attention masks with torch.tensor(starts, device=...)
on every call. If that copy is recorded against a host buffer that is freed after
capture, replay reads freed memory and the result silently differs from eager.
"""
import json, gc
import torch

DEV = 'xpu:0'
res = {}

def cap(fn, dev=DEV):
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

def replay(g, dev=DEV):
    with torch.xpu.device(dev):
        g.replay(); torch.xpu.synchronize(dev)

# ---- case A: host->device copy of a fresh Python list inside capture ----
VALUES = list(range(64))
def from_host_list():
    t = torch.tensor(VALUES, device=DEV)          # H2D of per-call host data
    return (t * 2).clone()

eager_a = from_host_list().cpu()
gA, outA = cap(from_host_list)
replay(gA)
res['A_host_list_copy'] = {
    'capture_matches_eager': bool(torch.equal(outA.cpu(), eager_a)),
}
# churn host memory the way a real workload would, then replay again
junk = [bytearray(1 << 16) for _ in range(256)]
del junk; gc.collect()
_ = [torch.tensor(list(range(64))) for _ in range(256)]
replay(gA)
res['A_host_list_copy']['stable_after_host_churn'] = bool(torch.equal(outA.cpu(), eager_a))

# ---- case B: the same values already resident on the device ----
resident = torch.tensor(VALUES, device=DEV)
def from_resident():
    return (resident * 2).clone()
eager_b = from_resident().cpu()
gB, outB = cap(from_resident)
replay(gB)
res['B_device_resident'] = {'capture_matches_eager': bool(torch.equal(outB.cpu(), eager_b))}
junk = [bytearray(1 << 16) for _ in range(256)]; del junk; gc.collect()
replay(gB)
res['B_device_resident']['stable_after_host_churn'] = bool(torch.equal(outB.cpu(), eager_b))

# ---- case C: does the captured H2D track a LATER change to the host list? ----
# If replay re-reads live host memory, mutating VALUES would change the output.
VALUES[0] = 999
replay(gA)
res['C_replay_tracks_host_mutation'] = bool(not torch.equal(outA.cpu(), eager_a))
print(json.dumps(res, indent=2))
