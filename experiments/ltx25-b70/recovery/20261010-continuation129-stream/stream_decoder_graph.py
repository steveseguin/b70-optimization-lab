"""Packet116: graph replay of the NA diffusion video decoder with bounded caches (LTX_DECODER_GRAPH=1).

EXPERIMENT under the owner authorization of 2026-10-08 ("you can try the caching ... try what you
want"): bounded caches inside the decoder, always gated by byte identity against the uncached
eager decode. Nothing here runs unless the server was launched with LTX_DECODER_GRAPH=1.

Why the decoder could not be captured before (notes/vae-graph-capture-blocked-01.md):

1. `NADiffusionDecoder.forward` draws `x_t` from a generator: a capture would bake one sample.
2. `NeighborhoodAttention3D.forward` calls `rope_inv_freqs` every forward, which builds the
   inverse frequencies in float64 ON THE CPU (the B70 has no fp64) and copies them to the
   device: a host-to-device copy, which a graph records as a pointer to freed host memory.
3. The eager na3d backend (comfy_kitchen/backends/eager/na.py `_group_mask`) builds its window
   masks from host lists with `torch.tensor(starts/ends, device=...)` and reads
   `int(en.max())` back to the host, per axis, per geometry group, per call.

What this module does, and why each step is exact:

- Caches (device-resident, keyed by shape and device, bounded, populated only OUTSIDE capture):
  - `rope_inv_freqs(dim, base, device)`: the ORIGINAL function is called once per key and its
    device tensor kept. Same function, same inputs: the same bytes.
  - the per-axis window matrix `(kj >= st) & (kj < en)` of `_group_mask`, keyed by the
    (starts, ends) tuples and the device, built with the original expressions
    (`torch.tensor`, `torch.arange(int(en.max()))`). The rest of `_group_mask` (the 6-D
    broadcast, `zeros`, `masked_fill_(finfo.min)`) is re-issued on every call exactly as the
    original writes it; tests compare it with the original on every stream geometry.
  - the decoder noise: `CausalDiffusionVAE.decode` seeds a FRESH generator with 0 on every
    decode and draws `torch.randn(pixel_shape, dtype, device, generator)` once. The shadowed
    forward checks that the generator it receives is in exactly the fresh seed-0 state, draws
    once per (shape, dtype, device) with it and keeps the tensor; later decodes reuse it.
- Graphs: `forward_pre_diffusion` and `forward_diff_step` (pure; one call each per decode at
  `default_num_inference_steps = 1`) are captured as in packet 22/26 (`ltx_graph_vae.py`):
  static input mirrors, eager reference on the same bits, warm-up on a side stream, capture into
  ONE shared pool on the decoder's device under the sampler's exclusive CAPTURE_LOCK, the
  result copied into a buffer allocated outside the capture, then three proofs (input
  sensitivity, replay reproducibility, replay == eager reference bit for bit). A cache miss
  while capturing raises before any host copy can be recorded. After the qualification verdict
  `freeze()` refuses any new signature or cache entry.
- Modes are thread-confined: only the decode thread, inside `graph_decode()`, sees the caches
  and graphs. Outside it every shadow delegates to the original function or method, so the
  uncached eager decode (the reference) is the unchanged packet115 code path.

The qualification (integration.Runtime._decode_job) decodes each graph-chain chunk twice, the
uncached eager decode first, and requires byte-identical images; the gate then requires every
chain to equal the eager chain. A mismatch latches the server (no fallback) and writes a latch
file that makes the launcher refuse LTX_DECODER_GRAPH=1 until an owner archives it.

Packet117: `register_outer(name, wrapper)` lets the cone-restricted anchor decode (stream_anchor_decode.py)
sit OVER the forward_diff_step shadow; `check()` then requires the decoder attribute to be that wrapper and
the wrapper's `inner` to be this controller's shadow. Nothing else changes (caches, graphs, proofs, bounds;
at 121 frames the stream geometry needs more mask entries, still within AXIS_MAX_ENTRIES).

Packet119: `pool_cap_bytes` (LTX_DECODER_GRAPH_POOL_CAP_GB; None = packet 117 behaviour). The two methods are
captured in first-call order (forward_pre_diffusion, then forward_diff_step); a method whose first call comes
when the measured reserved growth of the captures already made (memory_after - memory_before of each capture:
its pool segments plus its warm-up) has reached the cap is not captured: it becomes a CappedEntry for that
signature and runs the ORIGINAL method eagerly inside the graph_decode scope, with the same bounded caches,
for the life of the server. Exactness: the eager method with the caches is what every capture is proven
against (the capture's eager reference runs with the caches active), and the qualification's graph chain still
decodes every chunk twice (uncached eager, then this graph/capped decode) and requires byte-identical images.
The signature bounds and the freeze apply to capped entries exactly as to captured ones (one key per method;
a new key after the freeze is refused). Why a cap helps: at 121 frames the forward_diff_step capture would
hold its pool and its warm-up transient on xpu:3 next to the eager cone transient (the 2026-10-09 dg1 run
missed the 9 GiB decode floor by 76 MB); the capped stage-5 runs in the default stream's cached blocks that
the qualification's uncached eager decodes already reserved.

Torch is imported by the caller and passed in; this module imports nothing device-related.
"""
import contextlib
import hashlib
import threading
import time

SCHEMA = 'ltx.stream116.decoder-graph.v1'
METHODS = ('forward_pre_diffusion', 'forward_diff_step')
SHADOWED = ('forward',) + METHODS
MAX_SIGNATURES_PER_METHOD = 2      # the fixed stream geometry needs one; a second would mean a drifting key
ROPE_MAX_ENTRIES = 8               # rope_split (16, 24, 24) at base 10000 needs 2 per device
AXIS_MAX_ENTRIES = 64              # 19 (49 frames) / 21 (97 frames) / see tests (121 frames) per device
AXIS_MAX_ELEMENTS = 4096           # largest stream entry: 16 x 26 = 416 booleans
NOISE_MAX_ENTRIES = 1              # one stream geometry per server
LATCH_NAME = 'decoder-graph-116-refused.json'
# Pinned sources of the code the caches and graphs cover (checked by the runtime at install):
# the sealed decoder module and the eager na3d backend of the upstream-99 dependency overlay.
DECODER_SOURCE_PATH = 'source/comfy/ldm/lightricks/vae/na_diffusion_decoder.py'
NA_EAGER_PATH = '/home/steve/ltx25-upstream99-dependencies/site-packages/comfy_kitchen/backends/eager/na.py'
NA_EAGER_SHA256 = '4f1d82fe02af995d395969667f6cfd8d10635c3144eec8ca78fe37c103803995'   # = receipt.json
# Packet116b: on the live server the whitelisted custom node `ltx_na_axis_decode_lab` (na_axis_decode_node.py)
# installs `ltx_na_axis_router.AxisRouter` at import, which replaces the eager BACKEND attribute
# `comfy_kitchen.backends.eager.na3d` with its bound `_dispatch`. Outside an `LTXNAAxisDecode` scope (its
# ContextVar is None) `_dispatch` calls `router.original`, the pinned eager `na.na3d` itself, whose module
# globals (`_group_mask`) are what the mask cache wraps. The router never touches `na.na3d`, `na._group_mask`
# or `rope_inv_freqs`; its axis-cache candidate (a sandboxed copy) is used only inside such a scope, which the
# stream server never opens. 116b accepts exactly that router, pinned by source hash, in its no-scope route.
ROUTER_SOURCE_PATH = 'source/scripts/ltx_na_axis_router.py'
ROUTER_SHA256 = '1fe42fe9cc52fc957ef9bb3d8de070f2aefb3cb320b12d090146ad04f420b2a7'
ROUTER_CANDIDATE_SHA256 = 'd2907c1ee764fbb344db08851e19a67f0fd2144256d5451f0d15a9382dc08b6a'


class DecoderGraphRefusal(RuntimeError):
    pass


def na_route(impl, na_module, digest, modules=None):
    """Packet116b: classify comfy_kitchen's na3d resolution on the decoder's device.

    Accepted: (1) the pinned eager `na.na3d` itself (route 'eager'); (2) the lab's AxisRouter wrapper, pinned
    by source hash, whose `original` is that same function and whose scope is unset (route
    'axis-router-original'). Returns (route receipt, router or None); anything else raises."""
    import sys as _sys
    modules = _sys.modules if modules is None else modules
    if impl is getattr(na_module, 'na3d', None):
        require(getattr(impl, '__module__', None) == na_module.__name__ and getattr(impl, '__name__', None) == 'na3d',
                'Eager na3d identity differs')
        return {'route': 'eager', 'callable': '%s.%s' % (impl.__module__, impl.__name__)}, None
    router = getattr(impl, '__self__', None)
    cls = type(router)
    require(router is not None and cls.__name__ == 'AxisRouter' and
            getattr(impl, '__func__', None) is getattr(cls, '_dispatch', None),
            'na3d does not dispatch to the eager backend or the pinned NA axis router (%r)' % (impl,))
    module = modules.get(cls.__module__)
    require(module is not None and getattr(module, 'AxisRouter', None) is cls and
            digest(module.__file__) == ROUTER_SHA256, 'NA axis router source differs from the pinned router')
    require(getattr(module, 'ORIGINAL_SHA', None) == NA_EAGER_SHA256 and
            getattr(module, 'CANDIDATE_SHA', None) == ROUTER_CANDIDATE_SHA256, 'NA axis router pins differ')
    require(router.source is na_module and router.original is na_module.na3d and router.wrapper == impl and
            router.eager.na3d == impl, 'NA axis router does not wrap the pinned eager na3d')
    router.validate()
    require(router._mode.get() is None, 'NA axis router scope is active at install')
    return {'route': 'axis-router-original', 'router_module': cls.__module__,
            'router_sha256': ROUTER_SHA256, 'router_candidate_sha256': ROUTER_CANDIDATE_SHA256,
            'router_original': '%s.%s' % (router.original.__module__, router.original.__name__),
            'scope_at_install': None,
            'rule': 'every graph-mode decode requires the router scope unset and router.validate(); the router '
                    'then calls the pinned eager na3d (the cached _group_mask path); the axis-cache candidate '
                    'is never reached'}, router


def require(ok, why):
    if not ok:
        raise DecoderGraphRefusal(why)


class BoundedCache:
    """Insert-only cache with an entry bound. Misses are refused while capturing or frozen."""

    def __init__(self, name, max_entries, owner):
        self.name, self.max_entries, self.owner = name, max_entries, owner
        self.entries = {}
        self.hits = self.misses = 0
        self.refused = []

    def get(self, key, build, size=None):
        value = self.entries.get(key)
        if value is not None:
            self.hits += 1
            return value
        why = self.owner.miss_refusal(self.name)
        if why is None and len(self.entries) >= self.max_entries:
            why = '%s cache is full (%d entries)' % (self.name, self.max_entries)
        if why is None and size is not None and size > AXIS_MAX_ELEMENTS:
            why = '%s cache entry of %d elements exceeds %d' % (self.name, size, AXIS_MAX_ELEMENTS)
        if why is not None:
            self.refused.append({'key': repr(key)[:300], 'reason': why})
            raise DecoderGraphRefusal(why)
        value = build()
        self.entries[key] = value
        self.misses += 1
        return value

    def summary(self):
        return {'entries': len(self.entries), 'max_entries': self.max_entries, 'hits': self.hits,
                'misses': self.misses, 'refused': list(self.refused)}


class XPUBackend:
    """The torch.xpu calls the capture needs (the server's backend; tests pass a fake)."""

    def __init__(self, torch):
        self.torch = torch

    def device_context(self, device):
        return self.torch.xpu.device(device)

    def synchronize(self, device):
        self.torch.xpu.synchronize(device)

    def new_stream(self, device):
        return self.torch.xpu.Stream(device=device)

    def pool(self, device):
        return self.torch.xpu.graph_pool_handle()

    def new_graph(self):
        return self.torch.xpu.XPUGraph()

    def warmup(self, device, fn, iterations):
        torch = self.torch
        with torch.xpu.device(device):
            stream = torch.xpu.Stream(device=device)
            stream.wait_stream(torch.xpu.current_stream(device))
            with torch.xpu.stream(stream), torch.no_grad():
                for _ in range(iterations):
                    fn()
            torch.xpu.current_stream(device).wait_stream(stream)
            torch.xpu.synchronize(device)

    def capture_call(self, graph, device, pool, stream, body):
        """Record body() into graph (explicit device context, shared pool, explicit stream)."""
        torch = self.torch
        with torch.xpu.device(device), torch.no_grad(), torch.xpu.graph(graph, pool=pool, stream=stream):
            return body()

    def capturing(self):
        fn = getattr(self.torch.xpu, 'is_current_stream_capturing', None)
        return bool(fn()) if callable(fn) else False

    def replay(self, graph, device):
        with self.torch.xpu.device(device):
            graph.replay()
            self.torch.xpu.synchronize(device)

    def reset(self, graph):
        graph.reset()

    def memory(self, device):
        index = self.torch.device(device).index
        return {'allocated_bytes': int(self.torch.xpu.memory_allocated(index)),
                'reserved_bytes': int(self.torch.xpu.memory_reserved(index))}


class Entry:
    def __init__(self, key, graph, flat, output):
        self.key, self.graph, self.flat, self.output = key, graph, flat, output
        self.replays = 0


class CappedEntry:
    """Packet119: a signature of a method the pool cap kept out of the graph pool (runs eagerly, cached)."""

    def __init__(self, key, growth_at_decision, cap):
        self.key, self.growth_at_decision, self.cap = key, growth_at_decision, cap
        self.replays = 0
        self.capped = True


class GraphedMethod:
    """Graph-backed stand-in for one pure decoder method (packet 26 proof, shared pool, freeze)."""

    def __init__(self, ctl, name, original):
        self.ctl, self.name, self.original = ctl, name, original
        self.entries = {}

    def __call__(self, *args, **kwargs):
        ctl = self.ctl
        if not ctl.active():
            return self.original(*args, **kwargs)
        h = ctl.helpers
        key = (self.name, h.describe(args, self.name + '.args'), h.describe(kwargs, self.name + '.kwargs'))
        entry = self.entries.get(key)
        if entry is None:
            require(not ctl.frozen, '%s: decoder graph captures are frozen; a new signature is refused' % self.name)
            require(len(self.entries) < MAX_SIGNATURES_PER_METHOD,
                    '%s reached %d signatures; the key tracks something that is not a real input'
                    % (self.name, len(self.entries)))
            if ctl.cap_reached():
                # Packet119: the pool cap is reached; this signature stays eager (with the caches) for good.
                entry = self.entries[key] = CappedEntry(key, ctl.pool_growth, ctl.pool_cap)
                ctl.capped.append({'method': self.name,
                                   'signature_sha256': hashlib.sha256(repr(key).encode()).hexdigest(),
                                   'growth_at_decision': ctl.pool_growth, 'cap_bytes': ctl.pool_cap})
            else:
                ctl.lock.acquire_exclusive()
                try:
                    entry = self._capture(args, kwargs, key)
                finally:
                    ctl.lock.release_exclusive()
                record = ctl.captures[-1]
                ctl.pool_growth += max(0, record['memory_after']['reserved_bytes'] -
                                       record['memory_before']['reserved_bytes'])
                entry.replays += 1
                # The output lives in this graph's static buffer; the next replay overwrites it.
                return entry.output.clone()
        if getattr(entry, 'capped', False):
            # Packet119: a capped signature: the original method, eagerly, with the caches of this scope.
            entry.replays += 1
            ctl.capped_calls[self.name] += 1
            return self.original(*args, **kwargs)
        incoming = []
        h.walk(args, incoming, self.name + '.args')
        h.walk(kwargs, incoming, self.name + '.kwargs')
        require(len(incoming) == len(entry.flat), 'Argument tensor count changed for ' + self.name)
        ctl.lock.acquire_shared()
        try:
            for buffer, value in zip(entry.flat, incoming):
                if buffer is not value:
                    h.fill_static(buffer, value)
            ctl.backend.replay(entry.graph, ctl.device)
        finally:
            ctl.lock.release_shared()
        ctl.replays[self.name] += 1
        entry.replays += 1
        # The output lives in this graph's static buffer; the next replay overwrites it.
        return entry.output.clone()

    def _capture(self, args, kwargs, key):
        ctl, h, torch, b = self.ctl, self.ctl.helpers, self.ctl.torch, self.ctl.backend
        started = time.monotonic()
        memory_before = b.memory(ctl.device)
        static_args = h.mirror(args, h.static_like)
        static_kwargs = h.mirror(kwargs, h.static_like)
        flat = []
        h.walk(static_args, flat, self.name + '.args')
        h.walk(static_kwargs, flat, self.name + '.kwargs')
        probe = []
        h.walk(args, probe, self.name + '.args')
        h.walk(kwargs, probe, self.name + '.kwargs')
        require(len(flat) == len(probe) and flat, 'Static mirror lost or gained a tensor for ' + self.name)
        snapshot = [t.clone() for t in flat]

        def restore():
            for buffer, value in zip(flat, snapshot):
                h.fill_static(buffer, value)

        # Eager reference of the same method on the same bits (caches active: misses allowed here).
        with torch.no_grad():
            reference = self.original(*h.mirror(args, lambda t: t.clone()), **h.mirror(kwargs, lambda t: t.clone()))
        require(isinstance(reference, torch.Tensor), self.name + ' did not return a single tensor')
        reference = reference.clone()
        b.warmup(ctl.device, lambda: self.original(*static_args, **static_kwargs), h.WARMUP_ITERATIONS)
        restore()
        static_output = torch.empty_like(reference)        # outside the capture: replay lands here
        graph = b.new_graph()
        if ctl.pool is None:
            ctl.pool = b.pool(ctl.device)
            ctl.stream = b.new_stream(ctl.device)
        def body():
            out = self.original(*static_args, **static_kwargs)
            static_output.copy_(out)
            return out

        ctl.capturing = True
        try:
            produced = b.capture_call(graph, ctl.device, ctl.pool, ctl.stream, body)
        except BaseException:
            # An abandoned capture leaves the device recording (the 2026-09-15 incident): tear the
            # partial graph down and drain before re-raising. No retry.
            try:
                b.reset(graph)
            except BaseException:
                pass
            b.synchronize(ctl.device)
            raise
        finally:
            ctl.capturing = False
        b.synchronize(ctl.device)
        require(isinstance(produced, torch.Tensor) and produced.shape == reference.shape and
                produced.dtype == reference.dtype, self.name + ' capture changed the output shape or dtype')
        restore()
        b.replay(graph, ctl.device)
        baseline = static_output.clone()
        sensitivity = []
        for position, buffer in enumerate(flat):
            if not buffer.is_floating_point():
                sensitivity.append({'input': position, 'moved': None, 'note': 'not perturbed: non-floating'})
                continue
            restore()
            buffer.add_(1.0)
            b.replay(graph, ctl.device)
            sensitivity.append({'input': position, 'shape': list(buffer.shape), 'dtype': str(buffer.dtype),
                                'moved': not bitwise_equal(torch, static_output, baseline)})
        restore()
        b.replay(graph, ctl.device)
        require(bitwise_equal(torch, static_output, baseline),
                self.name + ' replay is not reproducible after restoring its inputs')
        require(any(row['moved'] for row in sensitivity),
                self.name + ' captured a graph no input moves; sensitivity=' + repr(sensitivity))
        require(bitwise_equal(torch, static_output, reference),
                self.name + ' graph replay differs from eager execution; refuse graph mode')
        entry = Entry(key, graph, flat, static_output)
        self.entries[key] = entry
        ctl.captures.append({'method': self.name, 'signature_sha256': hashlib.sha256(repr(key).encode()).hexdigest(),
                             'mirrored_tensors': len(flat), 'output_shape': list(static_output.shape),
                             'output_dtype': str(static_output.dtype), 'sensitivity': sensitivity,
                             'memory_before': memory_before, 'memory_after': b.memory(ctl.device),
                             'seconds': round(time.monotonic() - started, 6)})
        return entry


def bitwise_equal(torch, a, b):
    if a.dtype != b.dtype or a.shape != b.shape:
        return False
    if a.dtype in (torch.bfloat16, torch.float16):
        return torch.equal(a.view(torch.int16), b.view(torch.int16))
    if a.dtype == torch.float32:
        return torch.equal(a.view(torch.int32), b.view(torch.int32))
    return torch.equal(a, b)


class _Shadow:
    """Instance attribute that shadows a decoder method; delegates unless the controller is active."""

    def __init__(self, ctl, name, original, active_fn):
        self.ctl, self.name, self.original, self.active_fn = ctl, name, original, active_fn

    def __call__(self, *args, **kwargs):
        if not self.ctl.active():
            return self.original(*args, **kwargs)
        return self.active_fn(*args, **kwargs)


class DecoderGraph:
    """Caches, shadows and graphs for ONE resident NADiffusionDecoder on one device."""

    def __init__(self, torch, decoder_module, na_module, decoder, helpers, backend=None, lock=None, router=None,
                 pool_cap_bytes=None):
        require(type(decoder).__name__ == 'NADiffusionDecoder', 'Expected the native NA diffusion decoder')
        require(int(decoder.default_inference_timesteps.shape[0]) == 1 and decoder.model_output_type == 'x0',
                'Decoder graph assumes the single-step x0 decoder configuration')
        state = tuple(decoder.parameters()) + tuple(decoder.buffers())
        require(state and len({t.device for t in state}) == 1, 'Decoder state must live on one device')
        for module in decoder.modules():
            require(not (module._forward_hooks or module._forward_pre_hooks or module._backward_hooks),
                    'Decoder graph does not support module hooks')
        for name in SHADOWED:
            require(name not in vars(decoder), 'Decoder method already shadowed: ' + name)
        require(getattr(decoder_module, 'NADiffusionDecoder', None) is type(decoder),
                'Decoder module is not the decoder class\'s module')
        for fn, module in (('rope_inv_freqs', decoder_module), ('_group_mask', na_module), ('na3d', na_module)):
            require(callable(getattr(module, fn, None)), 'Native function missing: ' + fn)
        self.torch, self.decoder, self.helpers = torch, decoder, helpers
        self.decoder_module, self.na_module = decoder_module, na_module
        self.device = state[0].device
        self.backend = backend if backend is not None else XPUBackend(torch)
        self.lock = lock if lock is not None else helpers.CAPTURE_LOCK
        self.local = threading.local()
        self.owner_thread = None
        self.frozen = False
        self.capturing = False
        self.pool = self.stream = None
        self.captures = []
        self.replays = {name: 0 for name in METHODS}
        self.decodes = {'graph': 0, 'eager': 0}
        self.rope = BoundedCache('rope_inv_freqs', ROPE_MAX_ENTRIES, self)
        self.axis = BoundedCache('na_axis_masks', AXIS_MAX_ENTRIES, self)
        self.noise = BoundedCache('noise', NOISE_MAX_ENTRIES, self)
        self.originals = {}
        self.installed = None
        self.router = router            # packet116b: the accepted NA axis router (None = plain eager dispatch)
        self.router_checks = 0
        self.outer = {}                 # packet117: name -> wrapper installed over this controller's shadow
        # Packet119: the capture-time pool cap (None = packet 117: every method is captured).
        require(pool_cap_bytes is None or (type(pool_cap_bytes) is int and pool_cap_bytes > 0),
                'The decoder-graph pool cap is a positive byte count or None')
        self.pool_cap = pool_cap_bytes
        self.pool_growth = 0            # sum of the captures' reserved growth (memory_after - memory_before)
        self.capped = []                # the signatures the cap kept eager
        self.capped_calls = {name: 0 for name in METHODS}

    # -- state ------------------------------------------------------------------
    def cap_reached(self):
        """Packet119: True when a new signature must stay eager (the captures already made reached the cap)."""
        return self.pool_cap is not None and self.pool_growth >= self.pool_cap

    def pool_receipt(self):
        """Packet119: the pool cap, the measured growth, the captured and the capped methods."""
        captured = sorted({c['method'] for c in self.captures})
        return {'cap_bytes': self.pool_cap, 'growth_bytes': self.pool_growth, 'captured': captured,
                'capped': sorted({c['method'] for c in self.capped}), 'capped_calls': dict(self.capped_calls),
                'rule': 'methods are captured in first-call order while the reserved growth of the captures already '
                        'made is below the cap; a capped method runs eagerly with the same caches for good'
                        if self.pool_cap is not None else 'no cap (packet 117: every method is captured)'}

    def active(self):
        return getattr(self.local, 'active', False) and threading.get_ident() == self.owner_thread

    def miss_refusal(self, name):
        if self.frozen:
            return '%s cache is frozen after qualification; a new entry is refused' % name
        if self.capturing or self.backend.capturing():
            return '%s cache miss during graph capture (it would record a host copy); refused' % name
        return None

    @contextlib.contextmanager
    def graph_decode(self):
        """Decode thread only: caches and graphs are live inside this block."""
        require(self.installed is not None, 'Decoder graph is not installed')
        if self.owner_thread is None:
            self.owner_thread = threading.get_ident()
        require(threading.get_ident() == self.owner_thread, 'Decoder graph is bound to the decode thread')
        require(not getattr(self.local, 'active', False), 'Re-entrant graph decode')
        self.check()
        if self.router is not None:
            # The router must take its original (eager, cached-mask) route for this whole decode.
            self.router.validate()
            require(self.router._mode.get() is None, 'NA axis router scope is active on the decode thread')
            self.router_checks += 1
        self.local.active = True
        try:
            yield self
        finally:
            self.local.active = False
        self.decodes['graph'] += 1

    def note_eager(self):
        self.decodes['eager'] += 1

    def freeze(self):
        self.frozen = True

    # -- installation -------------------------------------------------------------
    def install(self):
        require(self.installed is None, 'Decoder graph installed twice')
        dm, na, dec = self.decoder_module, self.na_module, self.decoder
        orig_rope, orig_mask = dm.rope_inv_freqs, na._group_mask
        for fn in (orig_rope, orig_mask):
            require(not getattr(fn, '_ltx116_decoder_graph', False), 'Native function already wrapped')
        ctl = self

        def rope_inv_freqs(dim, base=10000.0, device=None):
            if not ctl.active():
                return orig_rope(dim, base, device=device)
            key = (int(dim), float(base), str(ctl.torch.device(device) if device is not None else None))
            return ctl.rope.get(key, lambda: orig_rope(dim, base, device=device))

        def _group_mask(rel_bounds, dtype, device):
            if not ctl.active():
                return orig_mask(rel_bounds, dtype, device)
            return ctl._cached_group_mask(rel_bounds, dtype, device)

        rope_inv_freqs._ltx116_decoder_graph = _group_mask._ltx116_decoder_graph = True
        rope_inv_freqs._ltx116_original = orig_rope
        _group_mask._ltx116_original = orig_mask
        dm.rope_inv_freqs, na._group_mask = rope_inv_freqs, _group_mask
        self.originals = {'forward': dec.forward, 'forward_pre_diffusion': dec.forward_pre_diffusion,
                          'forward_diff_step': dec.forward_diff_step}
        graphed = {name: GraphedMethod(self, name, self.originals[name]) for name in METHODS}
        shadows = {'forward': _Shadow(self, 'forward', self.originals['forward'], self._forward)}
        for name in METHODS:
            shadows[name] = _Shadow(self, name, self.originals[name], graphed[name])
        for name, shadow in shadows.items():
            setattr(dec, name, shadow)
        self.graphed = graphed
        self.installed = {'rope_inv_freqs': rope_inv_freqs, '_group_mask': _group_mask, 'shadows': shadows}
        return self.receipt()

    def register_outer(self, name, wrapper):
        """Packet117: accept exactly one wrapper over the shadow of `name` (its `inner` must be the shadow)."""
        inst = self.installed
        require(inst is not None and name in inst['shadows'] and name not in self.outer and
                getattr(wrapper, 'inner', None) is inst['shadows'][name] and vars(self.decoder).get(name) is wrapper,
                'Outer wrapper must sit directly over this controller\'s shadow')
        self.outer[name] = wrapper

    def _attribute_ok(self, name, shadow):
        current = vars(self.decoder).get(name)
        outer = self.outer.get(name)
        if outer is None:
            return current is shadow
        return current is outer and outer.inner is shadow

    def check(self):
        inst = self.installed
        require(inst is not None and self.decoder_module.rope_inv_freqs is inst['rope_inv_freqs'] and
                self.na_module._group_mask is inst['_group_mask'] and
                all(self._attribute_ok(n, s) for n, s in inst['shadows'].items()),
                'Decoder graph wrappers were replaced or removed')

    # -- the cached pieces ------------------------------------------------------------
    def _axis_bool(self, starts, ends, device):
        """The original per-axis expressions of na.py `_group_mask`, once per key, outside capture."""
        torch = self.torch
        st = torch.tensor(starts, device=device)
        en = torch.tensor(ends, device=device)
        kj = torch.arange(int(en.max()), device=device)
        return (kj[None, :] >= st[:, None]) & (kj[None, :] < en[:, None])

    def _cached_group_mask(self, rel_bounds, dtype, device):
        """na.py `_group_mask` with the per-axis matrices from the cache; every remaining line is the
        original's (tests compare the result with the original on every stream geometry)."""
        torch = self.torch
        bools = []
        for starts, ends in rel_bounds:
            key = (tuple(starts), tuple(ends), str(device))
            bools.append(self.axis.get(key, lambda s=starts, e=ends: self._axis_bool(s, e, device),
                                       size=len(starts) * max(ends)))
        visible = (bools[0][:, None, None, :, None, None]
                   & bools[1][None, :, None, None, :, None]
                   & bools[2][None, None, :, None, None, :])
        nq = visible.shape[0] * visible.shape[1] * visible.shape[2]
        nk = visible.shape[3] * visible.shape[4] * visible.shape[5]
        mask = torch.zeros((nq, nk), dtype=dtype, device=device)
        mask.masked_fill_(~visible.reshape(nq, nk), torch.finfo(dtype).min)
        return mask.reshape(1, 1, nq, nk)

    def _fresh_seed0_state(self, device):
        gen = self.torch.Generator(device=device)
        gen.manual_seed(0)
        return gen.get_state()

    def _forward(self, z, generator=None, drop_leading_frame=True, pad_trailing=True):
        """NADiffusionDecoder.forward at one x0 step, with the seed-0 noise from the cache."""
        torch, dec = self.torch, self.decoder
        require(generator is not None and generator.initial_seed() == 0 and
                torch.equal(generator.get_state(), self._fresh_seed0_state(z.device)),
                'Decoder noise generator is not a fresh seed-0 generator; the cached noise would differ')
        require(int(dec.default_inference_timesteps.shape[0]) == 1 and dec.model_output_type == 'x0',
                'Decoder configuration changed')
        context = dec.forward_pre_diffusion(z, drop_leading_frame=drop_leading_frame, pad_trailing=pad_trailing)
        batch, t5, h5, w5, _ = context.shape
        pixel_shape = (batch, dec.out_channels, t5, h5 * dec.patch_size, w5 * dec.patch_size)
        key = (pixel_shape, str(z.dtype), str(z.device))
        x_t = self.noise.get(key, lambda: torch.randn(pixel_shape, dtype=z.dtype, device=z.device,
                                                      generator=generator))
        timesteps = dec.default_inference_timesteps.to(z.device)
        t_now = timesteps[0].expand(batch)
        return dec.forward_diff_step(context, x_t, t_now)    # x0 at the single (last) step

    # -- receipts -------------------------------------------------------------------
    def signatures(self):
        return {name: len(self.graphed[name].entries) for name in METHODS} if self.installed else {}

    def receipt(self):
        return {'schema': SCHEMA, 'device': str(self.device), 'installed': self.installed is not None,
                'frozen': self.frozen, 'methods': list(METHODS), 'signatures': self.signatures(),
                'captured_graphs': len(self.captures), 'replays': dict(self.replays),
                'decodes': dict(self.decodes),
                'caches': {'rope_inv_freqs': self.rope.summary(), 'na_axis_masks': self.axis.summary(),
                           'noise': self.noise.summary()},
                'bounds': {'signatures_per_method': MAX_SIGNATURES_PER_METHOD, 'rope_entries': ROPE_MAX_ENTRIES,
                           'axis_entries': AXIS_MAX_ENTRIES, 'axis_elements': AXIS_MAX_ELEMENTS,
                           'noise_entries': NOISE_MAX_ENTRIES},
                'pool_shared': True, 'pool': self.pool_receipt(), 'na_router': None if self.router is None else 'axis-router-original',
                'router_checks': self.router_checks, 'outer': sorted(self.outer),
                'captures': [dict(c) for c in self.captures]}
