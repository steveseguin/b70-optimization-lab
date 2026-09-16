#!/usr/bin/env python3
"""CPU checks for the latent-upsampler gate adapter, against the real LatentUpsampler class.

No comfy import (that would discover devices); the class is loaded by path with
torch.nn as its `operations`. XPU-only paths (timed/graph stand-ins) must refuse
cleanly on CPU; the structural checks, fingerprinting and restore run for real.
"""
import importlib.util, sys, types
from pathlib import Path
import torch, torch.nn as nn
sys.path.insert(0, str(Path(__file__).resolve().parent))
SRC = Path('/home/steve/src/ComfyUI-ltx25-baseline/comfy/ldm/lightricks/latent_upsampler.py')
spec = importlib.util.spec_from_file_location('latent_upsampler', SRC)
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
# The capture helpers import comfy and the shard patcher at module load; stub
# only the names they bind at import so no device discovery happens here.
for name in ('comfy', 'comfy.ldm', 'comfy.ldm.lightricks', 'comfy.ldm.lightricks.av_model',
             'comfy.patcher_extension', 'ltx_layer_shard'):
    sys.modules.setdefault(name, types.ModuleType(name))
sys.modules['comfy.ldm.lightricks.av_model'].__file__ = str(SRC.parent / 'av_model.py')
for n_ in ('CallbacksMP', 'WrappersMP'):
    setattr(sys.modules['comfy.patcher_extension'], n_, object)
for n_ in ('CACHE_KEY', 'KEY', 'LTXLayerShardedPatcher', '_BlockRoute', '_forward_transfers', '_verify_placement'):
    setattr(sys.modules['ltx_layer_shard'], n_, object)
import ltx_graph_upsampler as a

ops = types.SimpleNamespace(Conv2d=nn.Conv2d, Conv3d=nn.Conv3d, GroupNorm=nn.GroupNorm)
model = mod.LatentUpsampler(ops, in_channels=8, mid_channels=32, num_blocks_per_stage=1, dims=3)
model.eval()
holder = types.SimpleNamespace(model=model)
x = torch.randn(1, 8, 2, 4, 4)
with torch.no_grad():
    ref = model(x)
assert ref.shape == (1, 8, 2, 8, 8), ref.shape

# 1. Structural acceptance of the real class; rejection of a wrong class and of hooks.
assert a.upsampler_of(holder) is model
try:
    a.upsampler_of(types.SimpleNamespace(model=nn.Linear(2, 2))); raise SystemExit('accepted a Linear')
except RuntimeError as e:
    assert 'LatentUpsampler' in str(e)
h = model.final_conv.register_forward_hook(lambda m, i, o: o)
try:
    a.upsampler_of(holder); raise SystemExit('accepted a hooked module')
except RuntimeError as e:
    assert 'hooks' in str(e)
h.remove(); a.upsampler_of(holder)

# 2. Fingerprint is stable across calls and changes when a weight moves.
f1 = a.param_fingerprint(model); assert f1 == a.param_fingerprint(model)
w = model.final_conv.weight; model.final_conv.weight = nn.Parameter(w.detach().clone())
assert a.param_fingerprint(model) != f1

# 3. XPU-only stand-ins refuse on CPU with a device message, leaving forward unshadowed.
for timed in (True, False):
    try:
        a.install(holder, timed=timed); raise SystemExit('installed on CPU')
    except RuntimeError as e:
        assert 'not resident on an XPU' in str(e), e
    assert 'forward' not in vars(model)

# 4. Restore removes a manually placed stand-in and refuses a foreign one.
original = model.forward
class Fake(a.TimedForward):
    def __init__(self, owner, original):
        self.owner, self.original, self.device, self.seconds = owner, original, torch.device('cpu'), []

    def __call__(self, *args, **kwargs):      # no XPU sync on CPU
        return self.original(*args, **kwargs)
model.forward = Fake(model, original)
with torch.no_grad():
    out = model(x)
assert torch.equal(out, ref)
a.restore(holder, original)
assert 'forward' not in vars(model) and callable(model.forward)
model.forward = lambda z: z
try:
    a.restore(holder, original); raise SystemExit('restored a foreign stand-in')
except RuntimeError as e:
    assert 'Unexpected upsampler forward' in str(e)
del model.forward
with torch.no_grad():
    assert torch.equal(model(x), ref)
print('ltx_graph_upsampler CPU checks: 4/4 passed')
