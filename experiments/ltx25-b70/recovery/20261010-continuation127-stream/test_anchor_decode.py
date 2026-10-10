"""CPU tests (packet117): the cone-restricted anchor decode (stream_anchor_decode.py) on the SEALED NA diffusion
decoder and the REAL eager na3d / RMS-RoPE backends (cpu_decoder.py).

What CPU shows: (1) the re-implemented stage-5 step with nothing skipped is byte-identical to the sealed
forward_diff_step (fp32 and bf16, many na3d tiles and mask groups), so the re-implementation is faithful; (2)
the cone step's last frame equals the full step's last frame byte for byte through the native decode path,
at several lengths, with na3d tiles, context_proj/SwiGLU chunks and qkv/proj chunks all being skipped (the
qkv chunk literal is exercised through a copy of the sealed module with a smaller literal); (3) every call the
cone issues is a call of the full step with the same shape, in the same order; (4) the cone intervals at the
real 49/97/121 stream geometry equal a brute-force dependency propagation through the na3d windows; (5) the
cone sits over the decoder-graph shadow and the graph-mode cone decode equals the eager one; (6) refusals.
What CPU cannot show: that XPU kernels keep row independence for these shapes (the per-chunk byte check and
the qualification gate decide on the B70).
"""
import ast
import hashlib
import importlib.util
import threading
import types
import unittest
from pathlib import Path
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cpu_decoder  # noqa: E402
import stream_anchor_decode as sad  # noqa: E402
import stream_decoder_graph as dgm  # noqa: E402

torch, DM, NA = cpu_decoder.load()
KITCHEN = sys.modules['comfy_kitchen']


def bits(t):
    return t.detach().contiguous().view(torch.uint8).numpy().tobytes()


def file_digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def latent(seed, frames, dtype=torch.float32):
    return torch.randn(1, 128, frames, 2, 2, generator=torch.Generator().manual_seed(seed)).to(dtype)


def step_inputs(vae, z):
    """What NADiffusionDecoder.forward hands to forward_diff_step (the native decode's own inputs)."""
    dec = vae.decoder
    x = vae.per_channel_statistics.un_normalize(z)
    context = dec.forward_pre_diffusion(x)
    batch, t5, h5, w5, _ = context.shape
    gen = torch.Generator(device=z.device)
    gen.manual_seed(0)
    x_t = torch.randn((batch, dec.out_channels, t5, h5 * dec.patch_size, w5 * dec.patch_size), dtype=z.dtype,
                      device=z.device, generator=gen)
    t = dec.default_inference_timesteps.to(z.device)[0].expand(batch)
    return context, x_t, t


class Budget:
    """Small na3d score budget (many tiles and mask groups) and, optionally, a small MLP token chunk."""
    def __init__(self, score=2 ** 12, mlp=None):
        self.score, self.mlp = score, mlp

    def __enter__(self):
        self.saved = (NA.NA_SCORE_BUDGET, DM.MLP_TOKEN_CHUNK)
        NA.NA_SCORE_BUDGET = self.score
        if self.mlp is not None:
            DM.MLP_TOKEN_CHUNK = self.mlp
        return self

    def __exit__(self, *exc):
        NA.NA_SCORE_BUDGET, DM.MLP_TOKEN_CHUNK = self.saved


def small_qkv_module():
    """A copy of the SEALED decoder module whose qkv/proj chunk literal (2 ** 25) is (2 ** 13), so the tiny
    decoder also splits its qkv/proj calls into frame chunks; everything else is the sealed text."""
    text = cpu_decoder.DECODER_FILE.read_text()
    old = 'chunk = max(1, (2 ** 25) // max(h * w * self.dim, 1))'
    assert text.count(old) == 1
    text = text.replace(old, 'chunk = max(1, (2 ** 13) // max(h * w * self.dim, 1))')
    spec = importlib.util.spec_from_loader('na_decoder_small_qkv', loader=None)
    mod = importlib.util.module_from_spec(spec)
    mod.__file__ = str(cpu_decoder.DECODER_FILE)
    mod.__package__ = 'comfy.ldm.lightricks.vae'
    exec(compile(text, str(cpu_decoder.DECODER_FILE), 'exec'), mod.__dict__)
    return mod


class Faithful(unittest.TestCase):
    """keep_all=True: the re-implementation equals the sealed forward_diff_step byte for byte."""
    def run_case(self, dtype, frames):
        vae = cpu_decoder.tiny_vae(1, dtype)
        step = sad.ConeStep(torch, DM, NA, KITCHEN)
        with Budget(mlp=1024), torch.inference_mode():
            context, x_t, t = step_inputs(vae, latent(3, frames, dtype))
            want = vae.decoder.forward_diff_step(context, x_t, t)
            got = step(vae.decoder, context.clone(), x_t.clone(), t, keep_all=True)
        self.assertEqual(want.shape, got.shape)
        self.assertEqual(bits(want), bits(got))

    def test_fp32(self):
        for frames in (3, 5):
            self.run_case(torch.float32, frames)

    def test_bf16(self):
        self.run_case(torch.bfloat16, 5)


class ConeExact(unittest.TestCase):
    """The cone's last frame equals the full decode's last frame through the native decode path."""
    def decode_pair(self, vae, z, module=DM, budget=None):
        step = sad.ConeStep(torch, module, NA, KITCHEN)
        calls = []
        dec = vae.decoder
        original = type(dec).forward_diff_step
        with budget or Budget(mlp=1024), torch.inference_mode():
            full = vae.decode(z)
            dec.forward_diff_step = lambda context, x_t, t: step(dec, context, x_t, t)
            try:
                cone = vae.decode(z)
            finally:
                del dec.forward_diff_step
            self.assertIs(type(dec).forward_diff_step, original)
        return full, cone, step

    def check_last(self, full, cone, step, skipped=True):
        self.assertEqual(full.shape, cone.shape)
        last = full.shape[2] - 1
        self.assertEqual(bits(full[:, :, last]), bits(cone[:, :, last]))
        plan = next(iter(step.plans.values()))
        if skipped:
            self.assertGreater(plan.need[0][0], 0)                   # the cone really leaves frames out
            self.assertNotEqual(bits(full[:, :, 0]), bits(cone[:, :, 0]))
            self.assertLess(plan.calls['na3d_tile']['kept'], plan.calls['na3d_tile']['total'])
        return plan

    def test_fp32_lengths(self):
        for frames in (3, 5, 7):
            vae = cpu_decoder.tiny_vae(2, torch.float32)
            full, cone, step = self.decode_pair(vae, latent(10 + frames, frames))
            plan = self.check_last(full, cone, step, skipped=frames >= 5)
            if frames >= 5:
                self.assertLess(plan.calls['mlp']['kept'], plan.calls['mlp']['total'])
                self.assertLess(plan.calls['context_proj']['kept'], plan.calls['context_proj']['total'])

    def test_bf16(self):
        vae = cpu_decoder.tiny_vae(3, torch.bfloat16)
        full, cone, step = self.decode_pair(vae, latent(21, 7, torch.bfloat16))
        self.check_last(full, cone, step)

    def test_qkv_and_proj_chunks_are_skipped_too(self):
        mod = small_qkv_module()
        saved = sad.QKV_ELEMENT_BUDGET
        sad.QKV_ELEMENT_BUDGET = 2 ** 13
        try:
            vae = cpu_decoder.tiny_vae(4, torch.float32)
            # Run the sealed-copy module's methods on this decoder instance (same weights, smaller qkv chunk).
            dec = vae.decoder
            for name in ('forward_pre_diffusion', 'forward_diff_step', 'forward'):
                setattr(dec, name, types.MethodType(getattr(mod.NADiffusionDecoder, name), dec))
            for block in list(dec.diff_blocks) + [b for s in dec.det_stages for b in s]:
                block.attn.forward = types.MethodType(mod.NeighborhoodAttention3D.forward, block.attn)
            step = sad.ConeStep(torch, mod, NA, KITCHEN)
            with Budget(mlp=1024), torch.inference_mode():
                z = latent(31, 7)
                full = vae.decode(z)
                inner = dec.forward_diff_step
                dec.forward_diff_step = lambda context, x_t, t: step(dec, context, x_t, t)
                try:
                    cone = vae.decode(z)
                finally:
                    dec.forward_diff_step = inner
            plan = self.check_last(full, cone, step)
            self.assertLess(plan.calls['qkv']['kept'], plan.calls['qkv']['total'])
            self.assertLess(plan.calls['proj']['kept'], plan.calls['proj']['total'])
        finally:
            sad.QKV_ELEMENT_BUDGET = saved


class SameCalls(unittest.TestCase):
    """Every call of the cone is a call of the full step: same op, same shapes, same order."""
    def test_cone_calls_are_a_subsequence_of_the_full_calls(self):
        vae = cpu_decoder.tiny_vae(5, torch.float32)
        full_calls, cone_calls = [], []
        with Budget(mlp=1024), torch.inference_mode():
            context, x_t, t = step_inputs(vae, latent(41, 7))
            sad.ConeStep(torch, DM, NA, KITCHEN, tracer=lambda *c: full_calls.append(c))(
                vae.decoder, context.clone(), x_t.clone(), t, keep_all=True)
            sad.ConeStep(torch, DM, NA, KITCHEN, tracer=lambda *c: cone_calls.append(c))(
                vae.decoder, context.clone(), x_t.clone(), t)
        self.assertLess(len(cone_calls), len(full_calls))
        it = iter(full_calls)
        self.assertTrue(all(any(c == f for f in it) for c in cone_calls))
        self.assertEqual(cone_calls[0], full_calls[0])               # conv_in_x_t on the whole tensor
        self.assertEqual(cone_calls[-1], full_calls[-1])             # norm_out + conv_out on the whole tensor
        ops = {c[0] for c in cone_calls}
        self.assertTrue({'qkv', 'rms_rope_', 'na3d_tile', 'proj', 'mlp', 'context_proj'} <= ops)


class Geometry(unittest.TestCase):
    """The cone at the real stream geometry, against a brute-force propagation through the na3d windows."""
    def brute(self, length, depth=8, kernel=11):
        starts, ends = NA._window_bounds(length, min(kernel, length), False)
        need = {length - 1}
        out = [sorted(need)]
        for _ in range(depth):
            need = {j for q in need for j in range(starts[q], ends[q])}
            out.append(sorted(need))
        return out[::-1]

    def test_stream_geometry(self):
        expect_first = {49: 3, 97: 51, 121: 75}
        for frames in (49, 97, 121):
            plan = sad.ConePlan(frames, 64, 64, 256, (11, 11, 11), 8, NA._window_bounds, NA._pick_tiles,
                                DM.MLP_TOKEN_CHUNK)
            brute = self.brute(frames)
            self.assertEqual([list(range(lo, hi)) for lo, hi in plan.need], brute)
            self.assertEqual(plan.need[0], (expect_first[frames], frames))
            self.assertEqual(plan.chunks, {'context_proj': 16, 'qkv': 32, 'proj': 32, 'mlp': 16})
            receipt = plan.receipt()
            tiles = receipt['calls']['na3d_tile']
            self.assertEqual(tiles['total'], 8 * (-(-frames // plan.tiles[0])) * (64 // plan.tiles[1]) *
                             (64 // plan.tiles[2]))
            if frames == 97:
                self.assertEqual(plan.tiles, [13, 8, 16])
                self.assertLess(tiles['kept_fraction'], 0.36)
            if frames == 121:
                self.assertLess(tiles['kept_fraction'], 0.27)

    def test_every_dependency_row_is_computed(self):
        """For each block, every frame the cone needs lies in a kept chunk / tile (no needed row is skipped)."""
        for frames in (49, 97, 121):
            plan = sad.ConePlan(frames, 64, 64, 256, (11, 11, 11), 8, NA._window_bounds, NA._pick_tiles,
                                DM.MLP_TOKEN_CHUNK)
            for block in range(1, 9):
                for op, cone in (('context_proj', plan.need[block - 1]), ('qkv', plan.need[block - 1]),
                                 ('proj', plan.need[block]), ('mlp', plan.need[block])):
                    step = plan.chunks[op]
                    kept = set()
                    for t0 in range(0, frames, step):
                        if sad.hits(t0, min(t0 + step, frames), cone):
                            kept.update(range(t0, min(t0 + step, frames)))
                    self.assertTrue(set(range(*cone)) <= kept, (frames, block, op))

    def test_interval_refuses_gaps(self):
        with self.assertRaises(sad.ConeRefusal):
            sad.interval({1, 2, 4}, 10)


class OverDecoderGraph(unittest.TestCase):
    """The cone over the decoder-graph shadow: install order, check(), graph-mode == eager cone == full."""
    def make(self, dtype=torch.float32):
        vae = cpu_decoder.tiny_vae(6, dtype)
        dg = dgm.DecoderGraph(torch, DM, NA, vae.decoder, cpu_decoder.graph_helpers(),
                              backend=cpu_decoder.FakeBackend(torch))
        originals = (DM.rope_inv_freqs, NA._group_mask)
        dg.install()
        cone = sad.ConeAnchorDecode(torch, DM, NA, vae.decoder, KITCHEN, file_digest, decoder_graph=dg)
        cone.install()
        return vae, dg, cone, originals

    def close(self, vae, originals):
        DM.rope_inv_freqs, NA._group_mask = originals
        for name in dgm.SHADOWED:
            vars(vae.decoder).pop(name, None)

    def test_graph_and_eager_cone_equal_the_full_last_frame(self):
        vae, dg, cone, originals = self.make()
        try:
            dg.check()
            cone.check()
            z = latent(51, 7)
            with Budget(mlp=1024), torch.inference_mode():
                full = vae.decode(z)                                   # inactive shadows: the sealed path
                with cone.cone_decode():
                    eager_cone = vae.decode(z)
                with dg.graph_decode():
                    graph_full = vae.decode(z)                        # captures both methods here
                with dg.graph_decode(), cone.cone_decode():
                    graph_cone = vae.decode(z)                        # replay pre-diffusion + cone step
            last = full.shape[2] - 1
            self.assertEqual(bits(full), bits(graph_full))
            self.assertEqual(bits(full[:, :, last]), bits(eager_cone[:, :, last]))
            self.assertEqual(bits(eager_cone), bits(graph_cone))
            self.assertEqual(cone.steps, 2)
            self.assertEqual(dg.signatures(), {'forward_pre_diffusion': 1, 'forward_diff_step': 1})
            self.assertEqual(dg.receipt()['outer'], ['forward_diff_step'])
        finally:
            self.close(vae, originals)

    def test_check_detects_a_replaced_cone(self):
        vae, dg, cone, originals = self.make()
        try:
            vae.decoder.forward_diff_step = dg.installed['shadows']['forward_diff_step']
            with self.assertRaises(dgm.DecoderGraphRefusal):
                dg.check()
            with self.assertRaises(sad.ConeRefusal):
                cone.check()
        finally:
            self.close(vae, originals)

    def test_register_outer_refusals(self):
        vae, dg, cone, originals = self.make()
        try:
            with self.assertRaises(dgm.DecoderGraphRefusal):
                dg.register_outer('forward_diff_step', cone.shadow)           # twice
            with self.assertRaises(dgm.DecoderGraphRefusal):
                dg.register_outer('forward_pre_diffusion', cone.shadow)       # not over that shadow
        finally:
            self.close(vae, originals)


class Install(unittest.TestCase):
    def test_eager_install_scope_and_refusals(self):
        vae = cpu_decoder.tiny_vae(7, torch.float32)
        dec = vae.decoder
        with self.assertRaises(sad.ConeRefusal):
            sad.ConeAnchorDecode(torch, DM, NA, dec, KITCHEN, lambda path: '0' * 64)
        cone = sad.ConeAnchorDecode(torch, DM, NA, dec, KITCHEN, file_digest)
        receipt = cone.install()
        try:
            self.assertEqual(receipt['over'], 'sealed method')
            with self.assertRaises(sad.ConeRefusal):
                cone.install()
            z = latent(61, 5)
            with Budget(mlp=1024), torch.inference_mode():
                plain = vae.decode(z)                                  # inactive: the original method
                with cone.cone_decode():
                    coned = vae.decode(z)
            self.assertEqual(bits(plain[:, :, -1]), bits(coned[:, :, -1]))
            self.assertEqual(cone.steps, 1)
            failures = []

            def other():
                try:
                    with cone.cone_decode():
                        pass
                except sad.ConeRefusal as error:
                    failures.append(str(error))
            th = threading.Thread(target=other)
            th.start()
            th.join()
            self.assertTrue(failures and 'decode thread' in failures[0])
            with self.assertRaises(sad.ConeRefusal):                   # a scope that runs no step is refused
                with cone.cone_decode():
                    pass
            self.assertEqual(len(cone.receipt()['plans']), 1)
        finally:
            vars(dec).pop('forward_diff_step', None)

    def test_pins(self):
        self.assertEqual(file_digest(cpu_decoder.DECODER_FILE), sad.DECODER_SOURCE_SHA256)
        self.assertEqual(file_digest(cpu_decoder.NA_FILE), sad.NA_EAGER_SHA256)
        self.assertEqual(sad.NA_EAGER_SHA256, dgm.NA_EAGER_SHA256)
        self.assertEqual(sad.DECODER_SOURCE_PATH, dgm.DECODER_SOURCE_PATH)
        text = cpu_decoder.DECODER_FILE.read_text()
        self.assertEqual(text.count('chunk = max(1, (2 ** 25) // max(h * w * self.dim, 1))'), 1)
        self.assertEqual(sad.QKV_ELEMENT_BUDGET, 2 ** 25)
        tree = ast.parse(Path(sad.__file__).read_text())
        names = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        self.assertNotIn('xpu', names)                                # no device API in the module


if __name__ == '__main__':
    unittest.main()
