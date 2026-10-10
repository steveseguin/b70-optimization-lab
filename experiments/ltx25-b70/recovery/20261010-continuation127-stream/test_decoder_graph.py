"""CPU tests (packet116): the decoder-graph experiment (stream_decoder_graph.py) on the SEALED NA diffusion
decoder and the REAL eager na3d / RMS-RoPE backends (cpu_decoder.py), with a CPU fake of the XPU graph API.

What CPU can show: the bounded caches return the bytes the original code computes (every NA mask group of
the real 49- and 97-frame stream geometry, and whole decodes of a small decoder with the real architecture,
fp32 and bf16, tiled into many mask groups); a cache miss can never happen inside a capture; the capture
proofs refuse a graph that differs from eager or ignores its inputs; the noise cache only serves a fresh
seed-0 generator; the controller is thread-confined, bounded and freezable; outside graph_decode() every
shadow is the original code path. What CPU cannot show: that torch.xpu graph capture of these kernels
replays bit-identically on the B70 (the live qualification decides).
"""
import ast
import hashlib
import json
import threading
import unittest
from pathlib import Path
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cpu_decoder  # noqa: E402
import stream_decoder_graph as dgm  # noqa: E402

torch, DM, NA = cpu_decoder.load()


def bits(t):
    return t.detach().contiguous().view(torch.uint8).numpy().tobytes()


def latent(seed, frames=3, dtype=torch.float32):
    return torch.randn(1, 128, frames, 2, 2, generator=torch.Generator().manual_seed(seed)).to(dtype)


def stream_groups(frames):
    """Every (rel_bounds) mask group the eager na3d builds for the real decoder at a stream geometry."""
    geo = {49: [(9, 8, 8), (9, 16, 16), (17, 16, 16), (33, 32, 32), (49, 64, 64)],
           97: [(15, 8, 8), (15, 16, 16), (29, 16, 16), (57, 32, 32), (97, 64, 64)],
           121: [(18, 8, 8), (18, 16, 16), (35, 16, 16), (69, 32, 32), (121, 64, 64)]}[frames]
    kernels = [(3, 7, 7), (3, 7, 7), (3, 5, 5), (3, 5, 5), (11, 11, 11)]
    groups = []
    for dims, kernel in zip(geo, kernels):
        ks = [min(k, d) for k, d in zip(kernel, dims)]
        bounds = [NA._window_bounds(d, k, False) for d, k in zip(dims, ks)]
        tiles = NA._pick_tiles(list(dims), ks)
        seen = {}
        for t0 in range(0, dims[0], tiles[0]):
            t1 = min(t0 + tiles[0], dims[0])
            for h0 in range(0, dims[1], tiles[1]):
                h1 = min(h0 + tiles[1], dims[1])
                for w0 in range(0, dims[2], tiles[2]):
                    w1 = min(w0 + tiles[2], dims[2])
                    rel = []
                    for (a, b), (st, en) in zip(((t0, t1), (h0, h1), (w0, w1)), bounds):
                        r0 = st[a]
                        rel.append((tuple(s - r0 for s in st[a:b]), tuple(e - r0 for e in en[a:b])))
                    seen[tuple(rel)] = True
        groups.extend(seen)
    return groups


class Controller:
    """A DecoderGraph on a fresh tiny VAE with the fake backend, installed."""
    def __init__(self, dtype=torch.float32, backend=None, seed=0):
        self.vae = cpu_decoder.tiny_vae(seed, dtype)
        self.backend = backend or cpu_decoder.FakeBackend(torch)
        self.helpers = cpu_decoder.graph_helpers()
        self.ctl = dgm.DecoderGraph(torch, DM, NA, self.vae.decoder, self.helpers, backend=self.backend)
        self.originals = (DM.rope_inv_freqs, NA._group_mask)
        self.receipt = self.ctl.install()

    def close(self):
        DM.rope_inv_freqs, NA._group_mask = self.originals
        for name in dgm.SHADOWED:
            vars(self.vae.decoder).pop(name, None)

    def eager(self, z):
        with torch.inference_mode():
            return self.vae.decode(z)

    def graph(self, z):
        with torch.inference_mode(), self.ctl.graph_decode():
            return self.vae.decode(z)


class MaskCache(unittest.TestCase):
    """The per-axis cache reproduces na.py `_group_mask` bytes on every group of the real stream geometry."""
    def test_every_stream_group_is_byte_identical(self):
        c = Controller()
        try:
            for frames in (49, 97):
                groups = stream_groups(frames)
                self.assertGreater(len(groups), 30)
                before = len(c.ctl.axis.entries)
                c.ctl.local.active = True
                c.ctl.owner_thread = threading.get_ident()
                try:
                    for rel in groups:
                        for dtype in (torch.bfloat16,):
                            want = c.originals[1](rel, dtype, torch.device('cpu'))
                            got = c.ctl._cached_group_mask(rel, dtype, torch.device('cpu'))
                            self.assertEqual(want.shape, got.shape)
                            self.assertTrue(torch.equal(want.view(torch.int16), got.view(torch.int16)))
                            del want, got
                finally:
                    c.ctl.local.active = False
                added = len(c.ctl.axis.entries) - before
                self.assertLessEqual(len(c.ctl.axis.entries), 2 * 21)
                self.assertGreater(added, 0)
            sizes = [len(k[0]) * max(k[1]) for k in c.ctl.axis.entries]
            self.assertLessEqual(max(sizes), dgm.AXIS_MAX_ELEMENTS)
            self.assertLessEqual(len(c.ctl.axis.entries), dgm.AXIS_MAX_ENTRIES)
        finally:
            c.close()

    def test_121_frame_geometry_fits_the_bounds_of_one_server(self):
        """Packet117: a 121-frame server (one geometry per server) stays within the cache bounds, byte-identical."""
        c = Controller()
        try:
            c.ctl.local.active = True
            c.ctl.owner_thread = threading.get_ident()
            try:
                for rel in stream_groups(121):
                    want = c.originals[1](rel, torch.bfloat16, torch.device('cpu'))
                    got = c.ctl._cached_group_mask(rel, torch.bfloat16, torch.device('cpu'))
                    self.assertTrue(torch.equal(want.view(torch.int16), got.view(torch.int16)))
                    del want, got
            finally:
                c.ctl.local.active = False
            sizes = [len(k[0]) * max(k[1]) for k in c.ctl.axis.entries]
            self.assertLessEqual(len(c.ctl.axis.entries), dgm.AXIS_MAX_ENTRIES)
            self.assertLessEqual(max(sizes), dgm.AXIS_MAX_ELEMENTS)
            self.assertGreater(len(c.ctl.axis.entries), 0)
        finally:
            c.close()

    def test_bounds_refuse_overflow(self):
        c = Controller()
        try:
            c.ctl.owner_thread = threading.get_ident()
            big = (tuple(range(64)), tuple(range(100, 164)))       # 64 x 163 elements
            with self.assertRaises(dgm.DecoderGraphRefusal):
                c.ctl.axis.get((big[0], big[1], 'cpu'), lambda: None, size=64 * 163)
            for i in range(dgm.ROPE_MAX_ENTRIES):
                c.ctl.rope.get(('k', i), lambda: i)
            with self.assertRaises(dgm.DecoderGraphRefusal):
                c.ctl.rope.get(('k', 'one more'), lambda: 0)
            self.assertEqual(c.ctl.rope.summary()['entries'], dgm.ROPE_MAX_ENTRIES)
        finally:
            c.close()


class Exactness(unittest.TestCase):
    """Whole decodes: uncached eager == graph capture == graph replay, byte for byte."""
    def setUp(self):
        self.budget = NA.NA_SCORE_BUDGET
        NA.NA_SCORE_BUDGET = 2 ** 12          # many tiles and mask groups at the small geometry

    def tearDown(self):
        NA.NA_SCORE_BUDGET = self.budget

    def run_dtype(self, dtype):
        pristine = cpu_decoder.tiny_vae(0, dtype)
        with torch.inference_mode():
            want = [pristine.decode(latent(s, dtype=dtype)) for s in (1, 2, 3)]
        c = Controller(dtype)
        try:
            self.assertEqual(bits(c.eager(latent(1, dtype=dtype))), bits(want[0]))     # installed, inactive
            first = c.graph(latent(1, dtype=dtype))                                    # captures
            self.assertEqual(c.ctl.signatures(), {'forward_pre_diffusion': 1, 'forward_diff_step': 1})
            self.assertEqual(len(c.ctl.captures), 2)
            again = c.graph(latent(1, dtype=dtype))                                    # replays
            other = c.graph(latent(2, dtype=dtype))                                    # replays, new inputs
            third = c.graph(latent(3, dtype=dtype))
            for got, ref in ((first, want[0]), (again, want[0]), (other, want[1]), (third, want[2])):
                self.assertEqual(got.dtype, ref.dtype)
                self.assertEqual(bits(got), bits(ref))
            self.assertEqual(len(c.ctl.captures), 2)
            self.assertEqual(c.ctl.replays, {'forward_pre_diffusion': 3, 'forward_diff_step': 3})
            self.assertEqual(c.ctl.noise.summary()['entries'], 1)
            self.assertEqual(c.ctl.rope.summary()['entries'], 2)         # rope_split (4, 6, 6): dims 4 and 6
            self.assertGreater(c.ctl.axis.summary()['entries'], 4)
            self.assertEqual(c.eager(latent(3, dtype=dtype)).dtype, want[2].dtype)
            self.assertEqual(bits(c.eager(latent(3, dtype=dtype))), bits(want[2]))   # eager path untouched
            for cap in c.ctl.captures:
                self.assertTrue(any(row['moved'] for row in cap['sensitivity']), cap)
        finally:
            c.close()

    def test_fp32(self):
        self.run_dtype(torch.float32)

    def test_bf16(self):
        self.run_dtype(torch.bfloat16)

    def test_no_original_host_builder_runs_inside_capture_or_replay(self):
        c = Controller()
        calls = {'mask': 0, 'rope': 0, 'in_capture': 0}
        orig_axis = c.ctl._axis_bool
        orig_rope = c.ctl.installed['rope_inv_freqs']._ltx116_original

        def axis(*a):
            calls['mask'] += 1
            calls['in_capture'] += int(c.backend.capturing_now)
            return orig_axis(*a)
        c.ctl._axis_bool = axis
        try:
            c.graph(latent(1))
            after_capture = dict(calls)
            c.graph(latent(2))
            c.graph(latent(3))
            self.assertEqual(calls['in_capture'], 0)
            self.assertEqual(calls['mask'], after_capture['mask'])          # replays build nothing on the host
            self.assertEqual(c.ctl.axis.summary()['refused'], [])
            self.assertEqual(c.ctl.rope.summary()['misses'], 2)
        finally:
            c.close()


class Refusals(unittest.TestCase):
    def test_cache_miss_during_capture_is_refused_and_the_graph_reset(self):
        backend = cpu_decoder.FakeBackend(torch)
        c = Controller(backend=backend)
        real = backend.capture_call

        def clearing(graph, device, pool, stream, body):
            c.ctl.axis.entries.clear()             # as if the reference had not populated the cache
            c.ctl.rope.entries.clear()
            return real(graph, device, pool, stream, body)
        backend.capture_call = clearing
        try:
            with self.assertRaises(dgm.DecoderGraphRefusal) as ctx:
                c.graph(latent(1))
            self.assertIn('during graph capture', str(ctx.exception))
            self.assertFalse(c.ctl.capturing)
            refused = c.ctl.axis.summary()['refused'] + c.ctl.rope.summary()['refused']
            self.assertTrue(refused)
        finally:
            c.close()

    def test_graph_that_differs_from_eager_is_refused(self):
        c = Controller(backend=cpu_decoder.FakeBackend(torch, tamper=True))
        try:
            with self.assertRaises(dgm.DecoderGraphRefusal) as ctx:
                c.graph(latent(1))
            self.assertIn('differs from eager execution', str(ctx.exception))
            self.assertEqual(c.ctl.captures, [])
        finally:
            c.close()

    def test_inert_graph_is_refused(self):
        c = Controller(backend=cpu_decoder.FakeBackend(torch, inert=True))
        try:
            with self.assertRaises(dgm.DecoderGraphRefusal) as ctx:
                c.graph(latent(1))
            self.assertIn('no input moves', str(ctx.exception))
        finally:
            c.close()

    def test_noise_needs_a_fresh_seed0_generator(self):
        c = Controller()
        try:
            z = c.vae.per_channel_statistics.un_normalize(latent(1))
            c.ctl.owner_thread = threading.get_ident()
            for gen in (torch.Generator().manual_seed(1), None):
                with torch.inference_mode(), c.ctl.graph_decode():
                    with self.assertRaises(dgm.DecoderGraphRefusal):
                        c.vae.decoder(z, generator=gen)
            advanced = torch.Generator().manual_seed(0)
            torch.randn(3, generator=advanced)
            with torch.inference_mode(), c.ctl.graph_decode():
                with self.assertRaises(dgm.DecoderGraphRefusal):
                    c.vae.decoder(z, generator=advanced)
            self.assertEqual(c.ctl.noise.summary()['entries'], 0)
        finally:
            c.close()

    def test_freeze_refuses_new_signatures_and_cache_entries(self):
        budget = NA.NA_SCORE_BUDGET
        NA.NA_SCORE_BUDGET = 2 ** 12
        c = Controller()
        try:
            c.graph(latent(1))
            c.ctl.freeze()
            c.graph(latent(2))                       # same signature: replay is allowed
            with self.assertRaises(dgm.DecoderGraphRefusal) as ctx:
                c.graph(latent(1, frames=4))         # a new geometry after the freeze
            self.assertIn('frozen', str(ctx.exception))
            self.assertEqual(c.ctl.signatures(), {'forward_pre_diffusion': 1, 'forward_diff_step': 1})
        finally:
            c.close()
            NA.NA_SCORE_BUDGET = budget

    def test_one_geometry_and_the_signature_bound(self):
        c = Controller()
        try:
            c.graph(latent(1, frames=2))
            with self.assertRaises(dgm.DecoderGraphRefusal) as ctx:
                c.graph(latent(1, frames=3))          # one stream geometry per server: the noise cache holds one
            self.assertIn('noise cache is full', str(ctx.exception))
        finally:
            c.close()
        saved = dgm.NOISE_MAX_ENTRIES
        dgm.NOISE_MAX_ENTRIES = 3
        c = Controller()
        try:
            for frames in (2, 3):
                c.graph(latent(1, frames=frames))
            with self.assertRaises(dgm.DecoderGraphRefusal) as ctx:
                c.graph(latent(1, frames=4))
            self.assertIn('reached 2 signatures', str(ctx.exception))
        finally:
            c.close()
            dgm.NOISE_MAX_ENTRIES = saved

    def test_thread_confinement_and_inactive_shadows(self):
        c = Controller()
        try:
            c.graph(latent(1))                       # binds the controller to this thread
            seen = {}

            def other():
                try:
                    with c.ctl.graph_decode():
                        pass
                except dgm.DecoderGraphRefusal as error:
                    seen['refused'] = str(error)
                misses = c.ctl.axis.misses
                with torch.inference_mode():
                    seen['eager'] = bits(c.vae.decode(latent(2)))      # original path on another thread
                seen['axis_untouched'] = c.ctl.axis.misses == misses
            t = threading.Thread(target=other)
            t.start()
            t.join(120)
            self.assertIn('bound to the decode thread', seen['refused'])
            pristine = cpu_decoder.tiny_vae(0)
            with torch.inference_mode():
                self.assertEqual(seen['eager'], bits(pristine.decode(latent(2))))
            self.assertTrue(seen['axis_untouched'])
        finally:
            c.close()

    def test_check_detects_removed_wrappers_and_double_install(self):
        c = Controller()
        try:
            c.ctl.check()
            with self.assertRaises(dgm.DecoderGraphRefusal):
                c.ctl.install()
            saved = NA._group_mask
            NA._group_mask = c.originals[1]
            with self.assertRaises(dgm.DecoderGraphRefusal):
                c.ctl.check()
            NA._group_mask = saved
            vars(c.vae.decoder).pop('forward_diff_step')
            with self.assertRaises(dgm.DecoderGraphRefusal):
                with c.ctl.graph_decode():
                    pass
        finally:
            c.close()

    def test_configuration_guards(self):
        vae = cpu_decoder.tiny_vae(0)
        helpers = cpu_decoder.graph_helpers()
        vae.decoder.model_output_type = 'v'
        with self.assertRaises(dgm.DecoderGraphRefusal):
            dgm.DecoderGraph(torch, DM, NA, vae.decoder, helpers, backend=cpu_decoder.FakeBackend(torch))
        vae = cpu_decoder.tiny_vae(0)
        vae.decoder.register_forward_hook(lambda *a: None)
        with self.assertRaises(dgm.DecoderGraphRefusal):
            dgm.DecoderGraph(torch, DM, NA, vae.decoder, helpers, backend=cpu_decoder.FakeBackend(torch))
        with self.assertRaises(dgm.DecoderGraphRefusal):
            dgm.DecoderGraph(torch, DM, NA, torch.nn.Linear(2, 2), helpers)


class Pins(unittest.TestCase):
    def test_pinned_sources(self):
        self.assertEqual(hashlib.sha256(cpu_decoder.NA_FILE.read_bytes()).hexdigest(), dgm.NA_EAGER_SHA256)
        receipt = json.loads(Path('/home/steve/ltx25-upstream99-dependencies/receipt.json').read_text())
        self.assertIn(dgm.NA_EAGER_SHA256, json.dumps(receipt))
        self.assertEqual(str(cpu_decoder.NA_FILE), dgm.NA_EAGER_PATH)
        manifest = json.loads((cpu_decoder.SEALED.parent / 'manifest.json').read_text())
        self.assertEqual(manifest['files'][dgm.DECODER_SOURCE_PATH],
                         hashlib.sha256(cpu_decoder.DECODER_FILE.read_bytes()).hexdigest())

    def test_xpu_backend_uses_device_context_shared_pool_and_explicit_stream(self):
        tree = ast.parse((HERE / 'stream_decoder_graph.py').read_text())
        backend = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'XPUBackend')
        methods = {n.name: ast.unparse(n) for n in backend.body if isinstance(n, ast.FunctionDef)}
        self.assertIn('torch.xpu.device(device), torch.no_grad(), torch.xpu.graph(graph, pool=pool, stream=stream)',
                      methods['capture_call'])
        self.assertIn('torch.xpu.synchronize(device)', methods['replay'])
        self.assertIn('graph_pool_handle', methods['pool'])

    def test_runtime_installs_with_source_pins_and_dispatch_proof(self):
        tree = ast.parse((HERE / 'integration.py').read_text())
        runtime = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Runtime')
        method = next(n for n in runtime.body if isinstance(n, ast.FunctionDef) and n.name == '_install_decoder_graph')
        text = ast.unparse(method)
        # Packet117: the dispatch proof moved into _na3d_route, shared with the cone installer.
        route = ast.unparse(next(n for n in runtime.body if isinstance(n, ast.FunctionDef) and n.name == '_na3d_route'))
        for needle in ("self.manifest['files'][dg_mod.DECODER_SOURCE_PATH]", 'dg_mod.NA_EAGER_SHA256',
                       'self._na3d_route(torch, na, decoder)', 'router=router', 'dg.install()',
                       "self.write('stream-decoder-graph-install.json'", 'na3d_route=route'):
            self.assertIn(needle, text)
        for needle in ("registry.get_implementation('na3d'", 'dg_mod.na_route(impl, na,', 'dg_mod.ROUTER_SOURCE_PATH'):
            self.assertIn(needle, route)
        self.assertLess(text.index('self._na3d_route('), text.index('dg.install()'))
        self.assertLess(route.index("registry.get_implementation('na3d'"), route.index('dg_mod.na_route('))
        cone = ast.unparse(next(n for n in runtime.body if isinstance(n, ast.FunctionDef) and n.name == '_install_cone'))
        for needle in ('self._na3d_route(torch, na, decoder)', 'sad.DECODER_SOURCE_SHA256', 'decoder_graph=self.decoder_graph',
                       'cone.install()', "self.write('stream-anchor-decode-install.json'"):
            self.assertIn(needle, cone)
        prepare = ast.unparse(next(n for n in runtime.body if isinstance(n, ast.FunctionDef) and n.name == 'prepare'))
        # The cone sits over the decoder-graph shadow: the decoder graph is installed first.
        self.assertLess(prepare.index('self._install_decoder_graph(torch)'), prepare.index('self._install_cone(torch)'))

    def test_outer_wrapper_receipt_and_check(self):
        c = Controller()
        try:
            self.assertEqual(c.ctl.receipt()['outer'], [])
            shadow = c.ctl.installed['shadows']['forward_diff_step']

            class Outer:
                inner = shadow

                def __call__(self, *a):
                    return self.inner(*a)
            outer = Outer()
            with self.assertRaises(dgm.DecoderGraphRefusal):
                c.ctl.register_outer('forward_diff_step', outer)        # not yet the decoder attribute
            c.vae.decoder.forward_diff_step = outer
            with self.assertRaises(dgm.DecoderGraphRefusal):
                c.ctl.check()                                          # unregistered wrapper
            c.ctl.register_outer('forward_diff_step', outer)
            c.ctl.check()
            self.assertEqual(c.ctl.receipt()['outer'], ['forward_diff_step'])
            outer.inner = object()
            with self.assertRaises(dgm.DecoderGraphRefusal):
                c.ctl.check()                                          # the wrapper no longer wraps the shadow
        finally:
            c.close()



PACKET116 = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-116')
LAB_NODE = PACKET116 / 'source/custom_nodes/ltx_na_axis_decode_lab/__init__.py'


class AxisRouterInstall(unittest.TestCase):
    """Packet116b: the live server installs ltx_na_axis_router.AxisRouter over comfy_kitchen's eager na3d
    attribute when ComfyUI imports the whitelisted custom node `ltx_na_axis_decode_lab` (its module code runs
    initialize() because the launcher sets LTX_ENCODER_RUN_DIR). This test runs that sealed node file the same
    way (stubbing only `nodes`, `comfy.sd` by their sealed file paths and encoder_diagnostics._context), then
    checks that the decoder-graph installer accepts the router, that the caches still sit on the path, and that
    every refusal case refuses."""
    def setUp(self):
        import os
        import tempfile
        import types
        self.saved_modules = {k: sys.modules.get(k) for k in ('nodes', 'comfy.sd', 'encoder_diagnostics',
                                                              'ltx_na_axis_router', 'ltx_na_axis_decode_lab')}
        self.saved_env = {k: os.environ.get(k) for k in ('LTX_ENCODER_RUN_DIR', 'LTX_ENCODER_IDENTITY_SHA256')}
        self.saved_path = list(sys.path)
        self.eager = sys.modules['comfy_kitchen.backends.eager']
        self.saved_na3d = self.eager.na3d
        self.saved_globals = (DM.rope_inv_freqs, NA._group_mask, NA.na3d)
        self.tmp = tempfile.TemporaryDirectory()
        run = Path(self.tmp.name) / 'encoder-server-test'
        run.mkdir()
        (run / 'server-identity.json').write_text('{"test": true}\n')
        ident = hashlib.sha256((run / 'server-identity.json').read_bytes()).hexdigest()
        os.environ.update(LTX_ENCODER_RUN_DIR=str(run), LTX_ENCODER_IDENTITY_SHA256=ident)
        nodes = types.ModuleType('nodes')
        nodes.__file__ = str(PACKET116 / 'source/nodes.py')

        class VAEDecode:
            def decode(self, vae, samples):
                return (vae.decode(samples['samples']),)
        nodes.VAEDecode = VAEDecode
        sd = types.ModuleType('comfy.sd')
        sd.__file__ = str(PACKET116 / 'source/comfy/sd.py')
        diag = types.ModuleType('encoder_diagnostics')
        diag._context = lambda: (run, {'server_identity_sha256': ident})
        sys.modules.update({'nodes': nodes, 'comfy.sd': sd, 'encoder_diagnostics': diag})
        sys.modules.pop('ltx_na_axis_router', None)
        sys.path.insert(0, str(PACKET116 / 'source/scripts'))
        self.node = cpu_decoder._exec_file('ltx_na_axis_decode_lab', LAB_NODE)     # runs initialize()
        self.router_module = sys.modules['ltx_na_axis_router']
        self.router = self.eager.na3d.__self__
        self.probe = torch.zeros((1, 2, 2, 2, 1, 64), dtype=torch.bfloat16)

    def tearDown(self):
        import os
        self.eager.na3d = self.saved_na3d
        DM.rope_inv_freqs, NA._group_mask, NA.na3d = self.saved_globals
        for k, v in self.saved_modules.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
        for k, v in self.saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        sys.path[:] = self.saved_path
        self.tmp.cleanup()

    def impl(self):
        from comfy_kitchen.registry import registry
        p = self.probe
        return registry.get_implementation('na3d', kwargs={'q': p, 'k': p, 'v': p, 'kernel_size': [1, 1, 1],
                                                           'is_causal': [False] * 3, 'scale': 1.0})

    def digest(self, path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()

    def test_live_install_path_is_accepted_and_changes_no_cache_owner(self):
        self.assertIn('LTXNAAxisDecode', self.node.NODE_CLASS_MAPPINGS)
        self.assertEqual(type(self.router).__name__, 'AxisRouter')
        impl = self.impl()
        self.assertIs(impl, self.router.wrapper)                       # what the live 116 refused
        route, router = dgm.na_route(impl, NA, self.digest)
        self.assertIs(router, self.router)
        self.assertEqual(route['route'], 'axis-router-original')
        self.assertEqual(route['router_original'], 'comfy_kitchen.backends.eager.na.na3d')
        self.assertEqual(self.digest(self.router_module.__file__), dgm.ROUTER_SHA256)
        manifest = json.loads((PACKET116 / 'manifest.json').read_text())
        self.assertEqual(manifest['files'][dgm.ROUTER_SOURCE_PATH], dgm.ROUTER_SHA256)
        self.assertEqual(manifest['files']['source/scripts/ltx_na_axis_candidate.py'], dgm.ROUTER_CANDIDATE_SHA256)
        # The router wraps only the backend attribute: the module functions the caches wrap are untouched.
        self.assertIs(NA.na3d, self.saved_globals[2])
        self.assertIs(NA._group_mask, self.saved_globals[1])
        self.assertIs(DM.rope_inv_freqs, self.saved_globals[0])
        self.assertIs(self.router.original, NA.na3d)
        # Without the router the same probe resolves to the plain eager route.
        self.eager.na3d = self.saved_na3d
        self.assertEqual(dgm.na_route(self.impl(), NA, self.digest)[0]['route'], 'eager')

    def test_graph_decodes_through_the_router_are_exact_and_use_the_caches(self):
        budget = NA.NA_SCORE_BUDGET
        NA.NA_SCORE_BUDGET = 2 ** 12
        pristine = cpu_decoder.tiny_vae(0)
        with torch.inference_mode():
            want = [pristine.decode(latent(s)) for s in (1, 2)]   # also through the router (no scope)
        route, router = dgm.na_route(self.impl(), NA, self.digest)
        vae = cpu_decoder.tiny_vae(0)
        ctl = dgm.DecoderGraph(torch, DM, NA, vae.decoder, cpu_decoder.graph_helpers(),
                               backend=cpu_decoder.FakeBackend(torch), router=router)
        ctl.install()
        try:
            with torch.inference_mode(), ctl.graph_decode():
                first = vae.decode(latent(1))
            with torch.inference_mode(), ctl.graph_decode():
                second = vae.decode(latent(2))
            self.assertEqual(bits(first), bits(want[0]))
            self.assertEqual(bits(second), bits(want[1]))
            self.assertGreater(ctl.axis.summary()['misses'], 0)       # the router's original route hit the cache
            self.assertEqual(ctl.router_checks, 2)
            self.assertEqual(ctl.receipt()['na_router'], 'axis-router-original')
            self.router.validate()
            # An active router scope (any mode) on the decode thread refuses the graph decode.
            for mode in ('original', 'axis-cache'):
                with self.assertRaises(dgm.DecoderGraphRefusal) as ctx:
                    with self.router.scope(mode, 'stream127-test'):
                        with torch.inference_mode(), ctl.graph_decode():
                            vae.decode(latent(1))
                self.assertIn('scope is active', str(ctx.exception))
        finally:
            NA.NA_SCORE_BUDGET = budget
            DM.rope_inv_freqs, NA._group_mask = self.saved_globals[:2]
            for name in dgm.SHADOWED:
                vars(vae.decoder).pop(name, None)

    def test_refusals(self):
        impl = self.impl()
        with self.assertRaises(dgm.DecoderGraphRefusal):
            dgm.na_route(impl, NA, lambda path: '0' * 64)             # router source differs from the pin
        with self.assertRaises(dgm.DecoderGraphRefusal):
            dgm.na_route(lambda *a, **k: None, NA, self.digest)       # some other dispatch
        with self.router.scope('original', 'stream127-test') as receipt:
            with self.assertRaises(dgm.DecoderGraphRefusal):
                dgm.na_route(impl, NA, self.digest)                   # scope active at install
            receipt['calls'].append({'status': 'completed'})          # let the scope close cleanly
        saved = self.router.original
        self.router.original = lambda *a, **k: None
        try:
            with self.assertRaises((dgm.DecoderGraphRefusal, RuntimeError)):
                dgm.na_route(impl, NA, self.digest)                   # router no longer wraps the pinned na3d
        finally:
            self.router.original = saved
        self.router.validate()


if __name__ == '__main__':
    unittest.main()
