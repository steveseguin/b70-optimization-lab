"""CPU test helper (packet116): the SEALED NA diffusion decoder and the REAL eager na3d / RMS-RoPE backends,
loaded without ComfyUI, comfy_kitchen's package import or any device.

- `source/comfy/ldm/lightricks/vae/na_diffusion_decoder.py` of the sealed 115 packet is executed as the module
  `comfy.ldm.lightricks.vae.na_diffusion_decoder` (its own file name, so tracebacks point at it);
- its imports are satisfied by small stubs, except the parts that decide numerics:
  `get_timestep_embedding` is compiled from the sealed `comfy/ldm/lightricks/model.py` and `processor` from the
  sealed `causal_video_autoencoder.py` (AST extraction, original file names); the conv `Encoder` is a stub
  (the decoder never calls it);
- `comfy_kitchen.na3d` is the dependency overlay's eager `backends/eager/na.py` (loaded as
  `comfy_kitchen.backends.eager.na`, the module whose `_group_mask` the decoder-graph cache wraps) and
  `comfy_kitchen.rms_rope_` its eager `backends/eager/rope.py`, with the real `_rope_utils.py`; the backend
  registry is a stub (CPU dispatch would select these eager functions anyway);
- `comfy.model_management.supports_fp64` returns False, as on the B70, so `rope_inv_freqs` takes its CPU
  float64 path and copies the result to the (CPU) device, exactly the code path the cache keeps.

Nothing here touches torch.xpu.
"""
import ast
import importlib.util
from pathlib import Path
import sys
import types

SEALED = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-115/source')
KITCHEN = Path('/home/steve/ltx25-upstream99-dependencies/site-packages/comfy_kitchen')
DECODER_FILE = SEALED / 'comfy/ldm/lightricks/vae/na_diffusion_decoder.py'
NA_FILE = KITCHEN / 'backends/eager/na.py'
ROPE_FILE = KITCHEN / 'backends/eager/rope.py'
_LOADED = None


def _module(name, package=False):
    mod = sys.modules.get(name)
    if mod is None:
        mod = types.ModuleType(name)
        if package:
            mod.__path__ = []
        sys.modules[name] = mod
    return mod


def _exec_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _extract(path, names, namespace):
    tree = ast.parse(Path(path).read_text())
    body = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names]
    assert sorted(n.name for n in body) == sorted(names), names
    exec(compile(ast.Module(body=body, type_ignores=[]), str(path), 'exec'), namespace)
    return namespace


def load():
    """(torch, decoder module, eager na module). Idempotent per process."""
    global _LOADED
    if _LOADED is not None:
        return _LOADED
    import math
    import torch
    from torch import nn
    # comfy stubs
    for name in ('comfy', 'comfy.ldm', 'comfy.ldm.lightricks', 'comfy.ldm.lightricks.vae'):
        _module(name, package=True)
    mm = _module('comfy.model_management')
    mm.supports_fp64 = lambda device=None: False          # the B70 has no fp64
    sys.modules['comfy'].model_management = mm
    model = _module('comfy.ldm.lightricks.model')
    ns = {'torch': torch, 'math': math}
    _extract(SEALED / 'comfy/ldm/lightricks/model.py', ['get_timestep_embedding'], ns)
    model.get_timestep_embedding = ns['get_timestep_embedding']
    cva = _module('comfy.ldm.lightricks.vae.causal_video_autoencoder')
    ns = {'torch': torch, 'nn': nn}
    _extract(SEALED / 'comfy/ldm/lightricks/vae/causal_video_autoencoder.py', ['processor'], ns)
    cva.processor = ns['processor']

    class Encoder(nn.Module):        # never called by the decoder
        def __init__(self, **kwargs):
            super().__init__()
    cva.Encoder = Encoder
    # comfy_kitchen: the REAL registry, constraints and eager na/rope files; the eager backend package is a
    # stub module holding na3d (what comfy_kitchen/backends/eager/__init__.py exports), registered under
    # 'eager' with the eager na3d call rule, so dispatch goes registry -> backend attribute, as on the server
    # (and through the NA axis router once a test installs it over that attribute).
    kitchen = _module('comfy_kitchen', package=True)
    kitchen.__path__ = [str(KITCHEN)]
    _module('comfy_kitchen.backends', package=True)
    eager = _module('comfy_kitchen.backends.eager', package=True)
    _exec_file('comfy_kitchen.exceptions', KITCHEN / 'exceptions.py')
    constraints = _exec_file('comfy_kitchen.constraints', KITCHEN / 'constraints.py')
    registry_mod = _exec_file('comfy_kitchen.registry', KITCHEN / 'registry.py')
    _exec_file('comfy_kitchen._rope_utils', KITCHEN / '_rope_utils.py')
    rope = _exec_file('comfy_kitchen.backends.eager.rope', ROPE_FILE)
    na = _exec_file('comfy_kitchen.backends.eager.na', NA_FILE)
    eager.na3d = na.na3d
    registry = registry_mod.registry
    registry._priority = ['eager']
    registry.register('eager', eager, {'na3d': constraints.FunctionConstraints(
        default_devices=frozenset({'cpu', 'cuda', 'xpu'}), call_rules=(constraints.na3d_common_call_rule,))})

    def na3d(q, k, v, kernel_size, is_causal=None, scale=None):
        if isinstance(kernel_size, int):
            kernel_size = [kernel_size] * 3
        if is_causal is None:
            is_causal = [False, False, False]
        kwargs = {'q': q, 'k': k, 'v': v, 'kernel_size': list(kernel_size), 'is_causal': list(is_causal),
                  'scale': scale}
        return registry.get_implementation('na3d', kwargs=kwargs)(**kwargs)      # as na.py _op_na3d
    kitchen.na3d = na3d
    kitchen.rms_rope_ = rope.rms_rope_
    decoder = _exec_file('comfy.ldm.lightricks.vae.na_diffusion_decoder', DECODER_FILE)
    _LOADED = (torch, decoder, na)
    return _LOADED


TINY_DECODER = dict(in_channels=128, out_channels=3, patch_size=2, head_dim=16,
                    stage_channels=(128, 64, 32, 32, 16), stage_depths=(1, 1, 1, 1, 2))


def tiny_vae(seed=0, dtype=None):
    """A CausalDiffusionVAE whose decoder has the real architecture (kernels, upsamples, pads) at small
    widths, random weights (seeded), and nonzero channel statistics."""
    torch, dm, _na = load()
    config = {'decoder': dict(TINY_DECODER, stage_kernels=[[3, 7, 7], [3, 7, 7], [3, 5, 5], [3, 5, 5], [11, 11, 11]],
                              upsamples=[[[1, 2, 2], 2], [[2, 1, 1], 2], [[2, 2, 2], 1], [[2, 2, 2], 2]],
                              stage5_kernel=[11, 11, 11], timestep_scale_multiplier=1000.0,
                              default_num_inference_steps=1),
              'model_output_type': 'x0'}
    gen = torch.Generator().manual_seed(seed)
    vae = dm.CausalDiffusionVAE(config=config)
    with torch.no_grad():
        for p in vae.parameters():
            p.copy_(torch.randn(p.shape, generator=gen) * 0.2)
        for name, b in vae.per_channel_statistics.named_buffers():
            b.copy_(torch.rand(b.shape, generator=gen) + 0.5)
    vae.eval()
    if dtype is not None:
        vae.to(dtype)
    return vae


GRAPH_CAPTURE_FILE = SEALED / 'scripts/ltx_graph_capture.py'
HELPER_FUNCTIONS = ('attribute_names', '_has_attributes', '_is_plain_instance', 'require', 'walk', 'mirror',
                    'describe', 'contains_tensor', 'static_like', 'fill_static')


def graph_helpers():
    """The sealed ltx_graph_capture helpers the decoder graph reuses (walk, mirror, describe, static_like,
    fill_static, CaptureReplayLock, WARMUP_ITERATIONS), compiled from the sealed file without its device-
    and ComfyUI-bound module imports."""
    import copy
    import threading
    import types as _types
    torch = load()[0]
    tree = ast.parse(GRAPH_CAPTURE_FILE.read_text())
    ns = {'torch': torch, 'copy': copy, 'threading': threading, '_types': _types}
    consts = [n for n in tree.body if isinstance(n, ast.Assign) and len(n.targets) == 1 and
              isinstance(n.targets[0], ast.Name) and n.targets[0].id in ('SCALARS', 'OPAQUE', 'WARMUP_ITERATIONS')]
    assert len(consts) == 3
    body = consts + [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and
                     n.name in HELPER_FUNCTIONS + ('CaptureReplayLock',)]
    exec(compile(ast.Module(body=body, type_ignores=[]), str(GRAPH_CAPTURE_FILE), 'exec'), ns)
    helpers = types.SimpleNamespace(**{k: ns[k] for k in HELPER_FUNCTIONS + ('WARMUP_ITERATIONS',)})
    helpers.CAPTURE_LOCK = ns['CaptureReplayLock']()
    return helpers


class FakeGraph:
    def __init__(self):
        self.body = None
        self.resets = 0
        self.replays = 0

    def replay(self):
        self.replays += 1
        self.body()

    def reset(self):
        self.resets += 1


class FakeBackend:
    """CPU stand-in for XPUBackend: a 'graph' re-runs the recorded body on the same static buffers, which is
    what a correct graph does. `tamper` perturbs the replayed output (a graph that differs from eager);
    `inert` makes replay ignore its inputs (a stale graph)."""

    def __init__(self, torch, tamper=False, inert=False):
        self.torch, self.tamper, self.inert = torch, tamper, inert
        self.capturing_now = False
        self.captures = []
        self.syncs = 0

    def device_context(self, device):
        import contextlib
        return contextlib.nullcontext()

    def synchronize(self, device):
        self.syncs += 1

    def new_stream(self, device):
        return 'stream'

    def pool(self, device):
        return 'pool'

    def new_graph(self):
        return FakeGraph()

    def warmup(self, device, fn, iterations):
        with self.torch.no_grad():
            for _ in range(iterations):
                fn()

    def capture_call(self, graph, device, pool, stream, body):
        assert pool == 'pool' and stream == 'stream'
        self.capturing_now = True
        try:
            with self.torch.no_grad():
                out = body()
        finally:
            self.capturing_now = False
        def replay_body():
            if self.inert:
                return                       # a stale graph: replay writes nothing
            with self.torch.no_grad():
                result = body()
            if self.tamper:                  # a graph whose replay differs from eager: perturb its static output
                cell = body.__closure__[body.__code__.co_freevars.index('static_output')]
                cell.cell_contents.view(-1)[0:1].add_(1.0)
            return result
        graph.body = replay_body
        self.captures.append(graph)
        return out

    def capturing(self):
        return self.capturing_now

    def replay(self, graph, device):
        graph.replay()

    def reset(self, graph):
        graph.reset()

    def memory(self, device):
        return {'allocated_bytes': 0, 'reserved_bytes': 0}
