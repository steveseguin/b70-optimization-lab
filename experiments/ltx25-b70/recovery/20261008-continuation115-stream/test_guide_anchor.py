"""CPU tests (packet115): the guide anchor against the sealed native nodes (LTXVAddLatentGuide,
LTXVCropGuides, get_keyframe_idxs from the packet-114 nodes_lt.py, compiled by cpu_native_lt.py),
the guide file format, GuideGuard, the mixed anchor's stage-A-only latent guard, and the
stage-B-only conditioning guard admission. Torch on CPU only; no device is touched."""
import hashlib
import sys
import tempfile
import types
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import torch  # noqa: E402
import cpu_native_lt  # noqa: E402
import latent_anchor as la  # noqa: E402
import stream_contract as c  # noqa: E402

SOURCE = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-114/source')
NODES_LT_SHA = '09ddb30d42244d64ae72e9c64261d1a6b4c512afe0570372222c43dbebd64243'   # unchanged since 111
NATIVE = cpu_native_lt.load(SOURCE)
VAE = types.SimpleNamespace(downscale_index_formula=(8, 32, 32))


def rand(shape, seed):
    return torch.randn(shape, generator=torch.Generator().manual_seed(seed), dtype=torch.float32)


def cond(seed=0):
    return [[rand([1, 16, 32], seed), {'frame_rate': 24.0}]]


def metadata(t):
    return {'object_id': id(t), 'storage_id': int(t.untyped_storage().data_ptr()), 'shape': list(t.shape),
            'dtype': str(t.dtype), 'device': str(t.device), 'contiguous': t.is_contiguous()}


def native(which):
    cls = NATIVE['LTXVAddLatentGuide' if which == 'guide' else 'LTXVCropGuides']
    return lambda **kw: cls.execute(**kw).result


class SealedNative(unittest.TestCase):
    def test_source_is_the_pinned_file(self):
        self.assertEqual(hashlib.sha256((SOURCE / 'comfy_extras/nodes_lt.py').read_bytes()).hexdigest(), NODES_LT_SHA)

    def test_token_counts_positions_and_mask(self):
        """What the gate's graphs will feed the transformer: +2 latent frames per stage, guide tokens at pixel
        frames -16..-1, a zero mask on them, strength 1.0 (no GuideAttentionMask is built at 1.0)."""
        for frames in c.FRAME_CHOICES:
            g = c.geometry(frames)
            for stage in ('A', 'B'):
                lat = {'samples': rand(g['stage_shapes'][stage], 1)}
                guide = rand(c.GUIDE_ANCHOR_PARTS[0 if stage == 'A' else 1][1], 2)
                pos, neg, out = native('guide')(positive=cond(), negative=cond(), vae=VAE, latent=lat,
                                                guiding_latent={'samples': guide}, latent_idx=c.GUIDE_LATENT_IDX,
                                                strength=1.0)
                shape = g['guided_stage_shapes'][stage]
                self.assertEqual(list(out['samples'].shape), shape)
                self.assertEqual(shape[2] * shape[3] * shape[4], g['guided_stage_tokens'][stage])
                self.assertEqual(out['noise_mask'].reshape(-1).tolist(), [1.0] * g['temporal_latents'] + [0.0, 0.0])
                self.assertTrue(torch.equal(out['samples'][:, :, -2:], guide))
                self.assertTrue(torch.equal(out['samples'][:, :, :-2], lat['samples']))
                kf = pos[0][1]['keyframe_idxs']
                self.assertEqual(list(kf.shape), [1, 3, 2 * shape[3] * shape[4], 2])
                self.assertEqual(sorted(set(kf[0, 0, :, 0].tolist())), [-16, -8])     # start pixel frames
                self.assertEqual(sorted(set(kf[0, 0, :, 1].tolist())), [-8, 0])       # end pixel frames
                entries = pos[0][1]['guide_attention_entries']
                self.assertEqual([(e['strength'], e['pixel_mask']) for e in entries], [(1.0, None)])
                self.assertEqual(NATIVE['get_keyframe_idxs'](pos, out['samples'].shape)[1], 2)
                cp, cn, cropped = native('crop')(positive=pos, negative=neg, latent=out)
                self.assertTrue(torch.equal(cropped['samples'], lat['samples']))
                self.assertIsNone(cp[0][1]['keyframe_idxs'])
                self.assertFalse(cropped['samples'].is_contiguous())      # a view; the guard accepts it by shape


class GuideFile(unittest.TestCase):
    def test_bytes_split_roundtrip(self):
        for frames in c.FRAME_CHOICES:
            g = c.geometry(frames)
            a, b = rand(g['stage_shapes']['A'], 3), rand(g['stage_shapes']['B'], 4)
            raw = la.anchor_bytes(torch, a, b, frames, 'guide')
            self.assertEqual(len(raw), 81920)
            pa, pb = la.split(torch, raw, 'guide')
            s = g['latent_anchor_slot']
            self.assertTrue(torch.equal(pa, a[:, :, s - 1:s + 1]) and torch.equal(pb, b[:, :, s - 1:s + 1]))
            latent = la.anchor_bytes(torch, a, b, frames, 'mixed')
            self.assertEqual(latent, la.anchor_bytes(torch, a, b, frames, 'latent'))
            la_a, la_b = la.split(torch, latent, 'mixed')                      # the last slot is the second guide slot
            self.assertTrue(torch.equal(la_a, pa[:, :, 1:2]) and torch.equal(la_b, pb[:, :, 1:2]))
            with tempfile.TemporaryDirectory() as tmp:
                meta = la.write_anchor(Path(tmp), 'stream115-s00000004', raw, frames, 'guide')
                self.assertEqual((meta['kind'], meta['bytes'], meta['slots'], meta['latent_idx']),
                                 ('guide', 81920, [s - 1, s], -2))
                self.assertTrue(meta['path'].endswith('.guide.f32'))
                self.assertEqual(la.read_anchor(meta['path'], meta['sha256'], 'guide'), raw)
                with self.assertRaises(la.LatentAnchorError):
                    la.read_anchor(meta['path'], meta['sha256'], 'latent')     # wrong size for the kind
                mixed = la.write_anchor(Path(tmp), 'stream115-s00000005', latent, frames, 'mixed')
                self.assertEqual((mixed['kind'], mixed['bytes']), ('mixed', 40960))
                with self.assertRaises(la.LatentAnchorError):
                    la.write_anchor(Path(tmp), 'x', latent, frames, 'guide')
                with self.assertRaises(la.LatentAnchorError):
                    la.write_anchor(Path(tmp), 'y', raw, frames, 'frame')


class Guard(unittest.TestCase):
    def setUp(self):
        self.g = c.geometry(49)
        self.guard = la.GuideGuard(torch=torch, tensor_metadata=metadata, get_keyframe_idxs=NATIVE['get_keyframe_idxs'],
                                   frames=49)
        self.parts = (rand(c.GUIDE_ANCHOR_PARTS[0][1], 5), rand(c.GUIDE_ANCHOR_PARTS[1][1], 6))
        self.name = 'stream115-s00000002'

    def guide(self, stage, **kw):
        args = dict(request_id=self.name, positive=cond(), negative=cond(), vae=VAE,
                    latent={'samples': rand(self.g['stage_shapes'][stage], 7)},
                    guide={'samples': self.parts[0 if stage == 'A' else 1]}, strength=1.0,
                    native_call=native('guide'))
        args.update(kw)
        return self.guard.run_guide(stage, **args)

    def crop(self, stage, guided, **kw):
        pos, neg, out = guided
        args = dict(request_id=self.name, positive=pos, negative=neg, latent=out, native_call=native('crop'))
        args.update(kw)
        return self.guard.run_crop(stage, **args)

    def test_happy_path_order_and_receipts(self):
        self.guard.begin_request(self.name, 'a' * 64, self.parts)
        ga = self.guide('A')
        ca = self.crop('A', ga)
        self.assertEqual(list(ca[2]['samples'].shape), self.g['stage_shapes']['A'])
        gb = self.guide('B')
        self.crop('B', gb)
        self.assertEqual(self.guard.finish_request(self.name), self.parts)
        rows = self.guard.drain(self.name)
        self.assertEqual([(r['event'], r.get('stage')) for r in rows],
                         [('begin', None), ('guide', 'A'), ('crop', 'A'), ('guide', 'B'), ('crop', 'B'), ('finish', None)])
        guide_rows = [r for r in rows if r['event'] == 'guide']
        self.assertEqual([r['guide_tokens'] for r in guide_rows], [32, 128])
        self.assertEqual([r['stage_tokens'] for r in guide_rows], [144, 576])

    def test_refusals_latch(self):
        cases = [
            lambda: self.guide('B'),                                                     # order
            lambda: self.guide('A', guide={'samples': self.parts[1]}),                   # wrong part
            lambda: self.guide('A', strength=0.5),
            lambda: self.guide('A', latent={'samples': rand(self.g['stage_shapes']['A'], 7),
                                            'noise_mask': torch.ones(1, 1, 7, 1, 1)}),  # already masked
            lambda: self.guide('A', positive=self.guide_once()[0]),                       # guides twice
            lambda: self.crop('A', (cond(), cond(), {'samples': rand(self.g['stage_shapes']['A'], 1)})),
        ]
        for case in cases:
            self.guard = la.GuideGuard(torch=torch, tensor_metadata=metadata,
                                       get_keyframe_idxs=NATIVE['get_keyframe_idxs'], frames=49)
            self.guard.begin_request(self.name, 'a' * 64, self.parts)
            with self.assertRaises(la.LatentAnchorError):
                case()
            self.assertIsNotNone(self.guard.failed)
        self.guard = la.GuideGuard(torch=torch, tensor_metadata=metadata,
                                   get_keyframe_idxs=NATIVE['get_keyframe_idxs'], frames=49)
        self.guard.begin_request(self.name, 'a' * 64, self.parts)
        self.crop('A', self.guide('A'))
        with self.assertRaises(la.LatentAnchorError):
            self.guard.finish_request(self.name)                                          # B never ran

    def guide_once(self):
        return native('guide')(positive=cond(), negative=cond(), vae=VAE,
                               latent={'samples': rand(self.g['stage_shapes']['A'], 9)},
                               guiding_latent={'samples': self.parts[0]}, latent_idx=-2, strength=1.0)

    def test_guide_pin_reads_the_tail(self):
        out = rand(self.g['guided_stage_shapes']['B'], 3)
        out[:, :, -2:] = self.parts[1]
        d = la.pin_diagnostic(torch, out, self.parts[1], tail=True)
        self.assertTrue(d['bytes_equal'])
        self.assertFalse(la.pin_diagnostic(torch, out, self.parts[1])['bytes_equal'])


class MixedGuards(unittest.TestCase):
    def test_latent_guard_stage_a_only(self):
        import test_latent_anchor as tla
        ns, _ = tla.native_namespace()
        guard = la.LatentConditionGuard(tensor_metadata=metadata, get_noise_mask=ns['get_noise_mask'], frames=49)
        g = c.geometry(49)
        parts = (rand(c.LATENT_ANCHOR_PARTS[0][1], 1), rand(c.LATENT_ANCHOR_PARTS[1][1], 2))
        guard.begin_request('stream115-s00000001', 'a' * 64, parts, stages=('A',))
        guard.run_stage('A', request_id='stream115-s00000001', latent={'samples': rand(g['stage_shapes']['A'], 3)},
                        anchor={'samples': parts[0]}, strength=1.0)
        with self.assertRaises(la.LatentAnchorError):
            guard.run_stage('B', request_id='stream115-s00000001', latent={'samples': rand(g['stage_shapes']['B'], 4)},
                            anchor={'samples': parts[1]}, strength=1.0)
        guard = la.LatentConditionGuard(tensor_metadata=metadata, get_noise_mask=ns['get_noise_mask'], frames=49)
        guard.begin_request('stream115-s00000002', 'a' * 64, parts, stages=('A',))
        guard.run_stage('A', request_id='stream115-s00000002', latent={'samples': rand(g['stage_shapes']['A'], 3)},
                        anchor={'samples': parts[0]}, strength=1.0)
        self.assertEqual(guard.finish_request('stream115-s00000002'), parts)
        with self.assertRaises(la.LatentAnchorError):
            la.LatentConditionGuard(tensor_metadata=metadata, get_noise_mask=ns['get_noise_mask'],
                                    frames=49).begin_request('x', 'a' * 64, parts, stages=('B',))

    def test_conditioning_guard_first_stage_is_derived_and_bounded(self):
        import ast
        text = (HERE / 'conditioning_guard.py').read_text()
        tree = ast.parse(text)
        guard = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'ConditioningStageGuard')
        begin = next(n for n in guard.body if isinstance(n, ast.FunctionDef) and n.name == 'begin_request')
        self.assertEqual([a.arg for a in begin.args.kwonlyargs], ['anchor', 'expected_anchor_sha256', 'first_stage'])
        self.assertEqual(ast.unparse(begin.args.kw_defaults[-1]), "'A'")
        body = ast.unparse(begin)
        self.assertIn("need(first_stage in ('A', 'B')", body)
        self.assertIn('self.next_stage = first_stage', body)
        run = ast.unparse(next(n for n in guard.body if isinstance(n, ast.FunctionDef) and n.name == 'run_stage'))
        self.assertIn("self.next_stage = 'B' if stage == 'A' else 'done'", run)


if __name__ == '__main__':
    unittest.main()
