"""CPU tests (packet122): the decoder-graph pool cap (stream_decoder_graph.DecoderGraph pool_cap_bytes) on the SEALED
NA diffusion decoder and the REAL eager na3d / RMS-RoPE backends (cpu_decoder.py), with a CPU fake of the XPU graph
API whose memory counter grows by a set amount per capture.

What CPU shows: without a cap the controller behaves as packet 117 (both methods captured, same replays and outputs);
with a cap, methods are captured in first-call order while the measured growth of the captures already made is below
the cap, a capped method runs the ORIGINAL method eagerly inside the graph scope with the same caches, its graph-mode
decode is byte-identical to the uncached eager decode (fp32 and bf16), the cone over a capped forward_diff_step
shadow still equals the full decode's last frame, the signature bound and the freeze apply to capped entries, and
the receipts name the captured and capped methods. What CPU cannot show: the real pool sizes on xpu:3 (the 121-frame
dg1 launch measures them; the 9 GiB floor stays the stop rule).
"""
import threading
import unittest
from pathlib import Path
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cpu_decoder  # noqa: E402
import stream_anchor_decode as sad  # noqa: E402
import stream_decoder_graph as dgm  # noqa: E402
import test_anchor_decode as tad  # noqa: E402  (Budget, latent, file_digest; shares the loaded modules)

torch, DM, NA = cpu_decoder.load()
KITCHEN = sys.modules['comfy_kitchen']
GB = 10 ** 9


def bits(t):
    return t.detach().contiguous().view(torch.uint8).numpy().tobytes()


def latent(seed, frames=3, dtype=torch.float32):
    return torch.randn(1, 128, frames, 2, 2, generator=torch.Generator().manual_seed(seed)).to(dtype)


class MemoryBackend(cpu_decoder.FakeBackend):
    """FakeBackend whose reserved-bytes counter grows by `growth` per capture (pool + warm-up, as measured)."""

    def __init__(self, torch_module, growth=3 * GB):
        super().__init__(torch_module)
        self.growth, self.reserved = growth, 10 * GB

    def capture_call(self, graph, device, pool, stream, body):
        out = super().capture_call(graph, device, pool, stream, body)
        self.reserved += self.growth
        return out

    def memory(self, device):
        return {'allocated_bytes': self.reserved // 2, 'reserved_bytes': self.reserved}


class Capped:
    def __init__(self, cap, dtype=torch.float32, growth=3 * GB, seed=0):
        self.vae = cpu_decoder.tiny_vae(seed, dtype)
        self.backend = MemoryBackend(torch, growth)
        self.ctl = dgm.DecoderGraph(torch, DM, NA, self.vae.decoder, cpu_decoder.graph_helpers(),
                                    backend=self.backend, pool_cap_bytes=cap)
        self.originals = (DM.rope_inv_freqs, NA._group_mask)
        self.ctl.install()

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


class PoolCap(unittest.TestCase):
    def test_no_cap_is_packet117(self):
        c = Capped(None)
        try:
            want = [c.eager(latent(s)) for s in (1, 2, 3)]
            got = [c.graph(latent(s)) for s in (1, 2, 3)]
            self.assertEqual([bits(x) for x in want], [bits(x) for x in got])
            self.assertEqual([r['method'] for r in c.ctl.captures], ['forward_pre_diffusion', 'forward_diff_step'])
            self.assertEqual(c.ctl.replays, {'forward_pre_diffusion': 2, 'forward_diff_step': 2})
            pool = c.ctl.pool_receipt()
            self.assertEqual((pool['cap_bytes'], pool['captured'], pool['capped']),
                             (None, ['forward_diff_step', 'forward_pre_diffusion'], []))
            self.assertEqual(pool['growth_bytes'], 6 * GB)
            self.assertFalse(c.ctl.cap_reached())
            self.assertEqual(c.ctl.receipt()['pool'], pool)
        finally:
            c.close()

    def run_capped(self, dtype):
        c = Capped(1 * GB, dtype)
        try:
            want = [c.eager(latent(s, dtype=dtype)) for s in (4, 5, 6)]
            got = [c.graph(latent(s, dtype=dtype)) for s in (4, 5, 6)]
            self.assertEqual([bits(x) for x in want], [bits(x) for x in got])
            self.assertEqual([r['method'] for r in c.ctl.captures], ['forward_pre_diffusion'])
            self.assertEqual(c.ctl.signatures(), {'forward_pre_diffusion': 1, 'forward_diff_step': 1})
            self.assertEqual(c.ctl.replays, {'forward_pre_diffusion': 2, 'forward_diff_step': 0})
            self.assertEqual(c.ctl.capped_calls, {'forward_pre_diffusion': 0, 'forward_diff_step': 3})
            pool = c.ctl.pool_receipt()
            self.assertEqual((pool['cap_bytes'], pool['growth_bytes'], pool['captured'], pool['capped']),
                             (1 * GB, 3 * GB, ['forward_pre_diffusion'], ['forward_diff_step']))
            self.assertEqual(c.ctl.capped[0]['growth_at_decision'], 3 * GB)
            self.assertEqual(len(c.backend.captures), 1)
        finally:
            c.close()

    def test_cap_keeps_the_second_method_eager_fp32(self):
        self.run_capped(torch.float32)

    def test_cap_keeps_the_second_method_eager_bf16(self):
        self.run_capped(torch.bfloat16)

    def test_a_cap_above_the_growth_captures_both(self):
        c = Capped(8 * GB)
        try:
            for s in (7, 8):
                self.assertEqual(bits(c.eager(latent(s))), bits(c.graph(latent(s))))
            self.assertEqual(c.ctl.pool_receipt()['captured'], ['forward_diff_step', 'forward_pre_diffusion'])
            self.assertEqual(c.ctl.pool_receipt()['capped'], [])
        finally:
            c.close()

    def test_the_first_method_is_always_captured(self):
        c = Capped(int(0.25 * GB), growth=0)          # no growth measured: the cap is never reached
        try:
            c.graph(latent(9))
            self.assertEqual(c.ctl.pool_receipt()['captured'], ['forward_diff_step', 'forward_pre_diffusion'])
        finally:
            c.close()

    def test_freeze_and_signature_bound_apply_to_capped_entries(self):
        c = Capped(1 * GB)
        try:
            c.graph(latent(10, frames=3))
            c.ctl.freeze()
            self.assertEqual(bits(c.eager(latent(11, frames=3))), bits(c.graph(latent(11, frames=3))))
            with self.assertRaises(dgm.DecoderGraphRefusal):
                c.graph(latent(12, frames=5))               # a new geometry after the freeze: refused, not eager
        finally:
            c.close()
        # The per-method signature bound is the same require for captured and capped entries (one code path).
        self.assertLess(Path(dgm.__file__).read_text().index('MAX_SIGNATURES_PER_METHOD,'),
                        Path(dgm.__file__).read_text().index('if ctl.cap_reached():'))

    def test_capped_method_uses_the_caches_and_never_runs_outside_the_scope(self):
        c = Capped(1 * GB)
        try:
            c.graph(latent(16))
            entries = (len(c.ctl.rope.entries), len(c.ctl.axis.entries), len(c.ctl.noise.entries))
            c.ctl.freeze()
            c.graph(latent(17))                             # frozen caches: any miss would raise
            self.assertEqual(entries, (len(c.ctl.rope.entries), len(c.ctl.axis.entries), len(c.ctl.noise.entries)))
            before = dict(c.ctl.capped_calls)
            c.eager(latent(18))                             # outside graph_decode: the original path, no counters
            self.assertEqual(before, c.ctl.capped_calls)
            done = []
            t = threading.Thread(target=lambda: done.append(bits(c.eager(latent(19)))))
            t.start()
            t.join()
            self.assertEqual(done, [bits(c.eager(latent(19)))])
        finally:
            c.close()

    def test_configuration_guards(self):
        vae = cpu_decoder.tiny_vae(0, torch.float32)
        for bad in (0, -1, 1.5, '1', True):
            with self.assertRaises(dgm.DecoderGraphRefusal):
                dgm.DecoderGraph(torch, DM, NA, vae.decoder, cpu_decoder.graph_helpers(),
                                 backend=MemoryBackend(torch), pool_cap_bytes=bad)


class ConeOverCappedShadow(unittest.TestCase):
    """The cone sits over the forward_diff_step shadow; with that method capped the cone is unchanged."""

    def test_graph_and_eager_cone_equal_the_full_last_frame(self):
        vae = cpu_decoder.tiny_vae(6, torch.float32)
        dg = dgm.DecoderGraph(torch, DM, NA, vae.decoder, cpu_decoder.graph_helpers(), backend=MemoryBackend(torch),
                              pool_cap_bytes=1 * GB)
        originals = (DM.rope_inv_freqs, NA._group_mask)
        dg.install()
        cone = sad.ConeAnchorDecode(torch, DM, NA, vae.decoder, KITCHEN, tad.file_digest, decoder_graph=dg)
        cone.install()
        try:
            z = tad.latent(51, 7)
            with tad.Budget(mlp=1024), torch.inference_mode():
                full = vae.decode(z)
                with dg.graph_decode(), cone.cone_decode():
                    graph_cone = vae.decode(z)              # captures pre-diffusion; the cone step runs eagerly
                with dg.graph_decode():
                    graph_full = vae.decode(z)              # forward_diff_step: capped (eager, cached)
                with dg.graph_decode(), cone.cone_decode():
                    graph_cone2 = vae.decode(z)
            last = full.shape[2] - 1
            self.assertEqual(bits(full), bits(graph_full))
            self.assertEqual(bits(full[:, :, last]), bits(graph_cone[:, :, last]))
            self.assertEqual(bits(graph_cone), bits(graph_cone2))
            self.assertEqual(dg.pool_receipt()['capped'], ['forward_diff_step'])
            self.assertEqual(dg.receipt()['outer'], ['forward_diff_step'])
            dg.check()
            cone.check()
        finally:
            DM.rope_inv_freqs, NA._group_mask = originals
            for name in dgm.SHADOWED:
                vars(vae.decoder).pop(name, None)


if __name__ == '__main__':
    unittest.main()
