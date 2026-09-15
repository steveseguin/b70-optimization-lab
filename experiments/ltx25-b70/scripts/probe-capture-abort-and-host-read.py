"""Does an exception inside an XPU graph capture leave the device usable, and
does tearing the partial graph down make the difference?

Staged, least-dangerous first. Stops at the first failure. No absurd allocation
is requested in the safe stages.
"""
import json
import torch

DEV = 'xpu:0'
res = {'stages': []}


def healthy(tag):
    """Exact tiny compute; proves the device still works after a stage."""
    x = torch.full((256, 256), 2.0, dtype=torch.float32, device=DEV)
    z = x @ torch.full((256, 256), 3.0, dtype=torch.float32, device=DEV)
    ok = torch.equal(z, torch.full((256, 256), 6.0 * 256, dtype=torch.float32, device=DEV))
    torch.xpu.synchronize(DEV)
    res['stages'].append({'stage': tag, 'device_healthy': bool(ok)})
    return ok


def capture(fn, teardown):
    graph = torch.xpu.XPUGraph()
    stream = torch.xpu.Stream(device=DEV)
    try:
        with torch.no_grad(), torch.xpu.graph(graph, stream=stream):
            fn()
        return 'captured', None
    except BaseException as error:
        if teardown:
            try:
                graph.reset()
            except BaseException:
                pass
            torch.xpu.synchronize(DEV)
        return 'raised', repr(error)[:160]


static = torch.randn(1024, 1024, device=DEV)

# Stage 0: baseline health
assert healthy('baseline')

# Stage 1: a clean capture works and replays
g = torch.xpu.XPUGraph()
with torch.no_grad(), torch.xpu.graph(g, stream=torch.xpu.Stream(device=DEV)):
    out = static * 2
g.replay(); torch.xpu.synchronize(DEV)
res['stages'].append({'stage': 'clean capture+replay', 'ok': bool(torch.equal(out, static * 2))})
assert healthy('after clean capture')

# Stage 2: a plain Python exception inside capture, WITH teardown
def boom():
    _ = static * 2
    raise RuntimeError('deliberate failure inside capture')
status, err = capture(boom, teardown=True)
res['stages'].append({'stage': 'exception inside capture (teardown)', 'status': status, 'error': err})
res['exception_teardown_left_device_healthy'] = healthy('after exception+teardown')

# Stage 3: the real failure mode -- a host read of tensor contents sizing a tensor
def host_read_sized():
    ends = (37, 41, 52)                      # the value IS already on the host
    en = torch.tensor(ends, device=DEV)      # recorded, not executed, during capture
    return torch.arange(int(en.max()), device=DEV)

eager_len = int(host_read_sized().shape[0])
res['eager_arange_length'] = eager_len
status, err = capture(host_read_sized, teardown=True)
res['stages'].append({'stage': 'host-read-sized arange inside capture', 'status': status, 'error': err})
res['host_read_device_healthy_after'] = healthy('after host-read capture')

# Stage 4: the fix -- read the value from the host tuple it already came from
def host_side_sized():
    ends = (37, 41, 52)
    return torch.arange(max(ends), device=DEV)

g2 = torch.xpu.XPUGraph()
try:
    with torch.no_grad(), torch.xpu.graph(g2, stream=torch.xpu.Stream(device=DEV)):
        fixed = host_side_sized()
    g2.replay(); torch.xpu.synchronize(DEV)
    res['stages'].append({'stage': 'host-side max(ends) inside capture', 'status': 'captured',
                          'length': int(fixed.shape[0]),
                          'matches_eager': int(fixed.shape[0]) == eager_len,
                          'values_exact': bool(torch.equal(fixed, torch.arange(max((37, 41, 52)), device=DEV)))})
except BaseException as error:
    res['stages'].append({'stage': 'host-side max(ends) inside capture', 'status': 'raised', 'error': repr(error)[:160]})
res['fix_device_healthy_after'] = healthy('after fixed capture')
print(json.dumps(res, indent=2))
