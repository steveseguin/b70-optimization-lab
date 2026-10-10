"""CPU tests (packet116): latent anchor file, the slot-0 copy against the sealed native node, the guard,
and the -0.0 -> +0.0 blend diagnostic. Torch on CPU only; no device is touched."""
import ast
import hashlib
import sys
import tempfile
import textwrap
import types
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import torch  # noqa: E402
import latent_anchor as la  # noqa: E402
import stream_contract as c  # noqa: E402

NODES_LT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-113/source/'
                'comfy_extras/nodes_lt.py')
NODES_LT_SHA = '09ddb30d42244d64ae72e9c64261d1a6b4c512afe0570372222c43dbebd64243'   # conditioning_guard pin


def native_namespace():
    """get_noise_mask and LTXVImgToVideoInplace.execute compiled from the sealed source, nothing else."""
    raw = NODES_LT.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == NODES_LT_SHA
    tree = ast.parse(raw)
    gnm = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'get_noise_mask')
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'LTXVImgToVideoInplace')
    execute = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'execute')
    execute.decorator_list = []
    ns = {'torch': torch, 'io': types.SimpleNamespace(NodeOutput=lambda *v: v),
          'comfy': types.SimpleNamespace(utils=types.SimpleNamespace(common_upscale=None))}
    exec(compile(ast.Module(body=[gnm, execute], type_ignores=[]), str(NODES_LT), 'exec'), ns)
    return ns, ast.get_source_segment(raw.decode(), execute)


class StubVAE:
    """encode returns the anchor latent; downscale formula of the LTX video VAE."""
    downscale_index_formula = (8, 32, 32)

    def __init__(self, t):
        self.t = t

    def encode(self, pixels):
        return self.t


def latent(shape, seed):
    g = torch.Generator().manual_seed(seed)
    return {'samples': torch.randn(shape, generator=g, dtype=torch.float32)}


class Native(unittest.TestCase):
    def test_condition_is_the_native_node_without_the_encode(self):
        ns, source = native_namespace()
        # The four statements 114 keeps, verbatim in the sealed method.
        for line in ('samples = latent["samples"].clone()', 'samples[:, :, :t.shape[2]] = t',
                     'conditioning_latent_frames_mask = get_noise_mask(latent)',
                     'conditioning_latent_frames_mask[:, :, :t.shape[2]] = 1.0 - strength',
                     'return io.NodeOutput({"samples": samples, "noise_mask": conditioning_latent_frames_mask})'):
            self.assertIn(line, source)
        for frames in c.FRAME_CHOICES:
            g = c.geometry(frames)
            for stage, (_, part_shape) in zip(('A', 'B'), c.LATENT_ANCHOR_PARTS):
                lat = latent(g['stage_shapes'][stage], 1)
                anchor = latent(part_shape, 2)['samples']
                anchor.view(-1)[:5] = -0.0                      # signed zeros survive the copy
                h, w = part_shape[3] * 32, part_shape[4] * 32
                image = torch.zeros([1, h, w, 3])                 # image already at size: no resize call
                with torch.inference_mode():
                    native = ns['execute'](None, StubVAE(anchor), image, lat, 1.0)[0]
                    ours = la.condition(ns['get_noise_mask'], lat, anchor, 1.0)
                self.assertEqual(set(native), set(ours))
                for key in native:
                    self.assertTrue(torch.equal(native[key].view(torch.int32), ours[key].view(torch.int32)))
                self.assertEqual(list(ours['noise_mask'].shape), g['noise_mask_shape'])
                self.assertEqual(float(ours['noise_mask'][0, 0, 0]), 0.0)
                self.assertTrue(bool((ours['noise_mask'][0, 0, 1:] == 1).all()))
                self.assertTrue(torch.equal(lat['samples'][:, :, 1:], ours['samples'][:, :, 1:]))
                self.assertNotEqual(ours['samples'].untyped_storage().data_ptr(),
                                    lat['samples'].untyped_storage().data_ptr())


class FileFormat(unittest.TestCase):
    def test_bytes_split_roundtrip_and_slots(self):
        for frames in c.FRAME_CHOICES:
            g = c.geometry(frames)
            a = latent(g['stage_shapes']['A'], 3)['samples']
            b = latent(g['stage_shapes']['B'], 4)['samples']
            raw = la.anchor_bytes(torch, a, b, frames)
            self.assertEqual(len(raw), 40960)
            pa, pb = la.split(torch, raw)
            slot = g['latent_anchor_slot']
            self.assertTrue(torch.equal(pa, a[:, :, slot:slot + 1]))
            self.assertTrue(torch.equal(pb, b[:, :, slot:slot + 1]))
            self.assertEqual(raw[:8192], a[:, :, slot:slot + 1].contiguous().numpy().tobytes())
            pa[0, 0, 0, 0, 0] = 99.0                         # split owns its storage
            self.assertEqual(la.split(torch, raw)[0][0, 0, 0, 0, 0].item(), a[0, 0, slot, 0, 0].item())
            with self.assertRaises(la.LatentAnchorError):
                la.anchor_bytes(torch, b, a, frames)

    def test_write_read_verify(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            g = c.geometry(97)
            raw = la.anchor_bytes(torch, latent(g['stage_shapes']['A'], 5)['samples'],
                                  latent(g['stage_shapes']['B'], 6)['samples'], 97)
            out = la.write_anchor(d, 'stream116b-s00000003', raw, 97)
            self.assertEqual(out['path'], str(d / 'stream116b-s00000003.latent.f32'))
            self.assertEqual((out['kind'], out['bytes'], out['slot']), ('latent', 40960, 12))
            self.assertEqual([r['part'] for r in out['layout']], ['A', 'B'])
            self.assertEqual(la.read_anchor(out['path'], out['sha256']), raw)
            with self.assertRaises(FileExistsError):
                la.write_anchor(d, 'stream116b-s00000003', raw, 97)
            with self.assertRaises(la.LatentAnchorError):
                la.read_anchor(out['path'], 'f' * 64)
            bad = bytearray(raw)
            bad[0:4] = b'\x00\x00\xc0\x7f'                   # NaN
            with self.assertRaises(la.LatentAnchorError):
                la.write_anchor(d, 'stream116b-s00000004', bytes(bad), 97)
            with self.assertRaises(la.LatentAnchorError):
                la.write_anchor(d, 'stream116b-s00000005', raw[:-4], 97)


class PinDiagnostic(unittest.TestCase):
    def test_blend_turns_negative_zero_positive_and_the_diagnostic_says_so(self):
        """samplers.py:638-642 blend with mask 0: out*0 + anchor*1. A -0.0 anchor element can come back +0.0."""
        anchor = torch.tensor([[[[[-0.0, 1.5], [2.0, -3.25]]]]], dtype=torch.float32)
        model_out = torch.tensor([[[[[0.7, -0.2], [5.0, 1.0]]]]], dtype=torch.float32)
        mask = torch.zeros(1, 1, 1, 1, 1)
        blended = model_out * mask + anchor * (1 - mask)
        self.assertTrue(torch.signbit(anchor.view(-1)[0]))
        self.assertFalse(torch.signbit(blended.view(-1)[0]))
        self.assertTrue(torch.equal(blended, anchor))           # equal as values, not as bytes
        d = la.pin_diagnostic(torch, blended, anchor)
        self.assertEqual((d['bytes_equal'], d['differing_elements'], d['differing_all_signed_zero']), (False, 1, True))
        self.assertEqual((d['anchor_negative_zeros'], d['output_negative_zeros']), (1, 0))
        self.assertTrue(d['diagnostic_only'])
        same = la.pin_diagnostic(torch, anchor.clone(), anchor)
        self.assertTrue(same['bytes_equal'] and same['differing_all_signed_zero'])
        moved = anchor.clone()
        moved.view(-1)[1] = 1.25
        self.assertFalse(la.pin_diagnostic(torch, moved, anchor)['differing_all_signed_zero'])

    def test_diagnostic_reads_slot_zero_of_a_full_latent(self):
        g = c.geometry(49)
        out = latent(g['stage_shapes']['B'], 7)['samples']
        anchor = out[:, :, :1].clone()
        self.assertTrue(la.pin_diagnostic(torch, out, anchor)['bytes_equal'])


def metadata(t):
    return {'object_id': id(t), 'storage_id': int(t.untyped_storage().data_ptr()), 'shape': list(t.shape),
            'dtype': str(t.dtype), 'device': str(t.device), 'contiguous': t.is_contiguous()}


class Guard(unittest.TestCase):
    def setUp(self):
        ns, _ = native_namespace()
        self.guard = la.LatentConditionGuard(tensor_metadata=metadata, get_noise_mask=ns['get_noise_mask'], frames=49)
        g = c.geometry(49)
        self.parts = (latent(c.LATENT_ANCHOR_PARTS[0][1], 1)['samples'], latent(c.LATENT_ANCHOR_PARTS[1][1], 2)['samples'])
        self.a, self.b = latent(g['stage_shapes']['A'], 3), latent(g['stage_shapes']['B'], 4)

    def test_order_parts_and_finish(self):
        self.guard.begin_request('stream116b-s00000001', 'a' * 64, self.parts)
        with self.assertRaises(la.LatentAnchorError):
            self.guard.run_stage('B', request_id='stream116b-s00000001', latent=self.b,
                                 anchor={'samples': self.parts[1]}, strength=1.0)
        self.assertIsNotNone(self.guard.failed)

    def test_happy_path(self):
        self.guard.begin_request('stream116b-s00000001', 'a' * 64, self.parts)
        out_a = self.guard.run_stage('A', request_id='stream116b-s00000001', latent=self.a,
                                     anchor={'samples': self.parts[0]}, strength=1.0)
        self.assertTrue(torch.equal(out_a['samples'][:, :, :1], self.parts[0]))
        out_b = self.guard.run_stage('B', request_id='stream116b-s00000001', latent=self.b,
                                     anchor={'samples': self.parts[1]}, strength=1.0)
        self.assertTrue(torch.equal(out_b['samples'][:, :, :1], self.parts[1]))
        self.assertEqual(self.guard.finish_request('stream116b-s00000001'), self.parts)
        rows = self.guard.drain('stream116b-s00000001')
        self.assertEqual([r['event'] for r in rows], ['begin', 'stage', 'stage', 'finish'])
        with self.assertRaises(la.LatentAnchorError):
            self.guard.begin_request('stream116b-s00000001', 'a' * 64, self.parts)      # names are single use

    def test_refusals(self):
        cases = [
            lambda: self.guard.run_stage('A', request_id='stream116b-s00000001', latent=self.a,
                                         anchor={'samples': self.parts[1]}, strength=1.0),          # wrong part
            lambda: self.guard.run_stage('A', request_id='stream116b-s00000001', latent=self.a,
                                         anchor={'samples': self.parts[0]}, strength=0.5),          # strength
            lambda: self.guard.run_stage('A', request_id='stream116b-s00000001',
                                         latent=dict(self.a, noise_mask=torch.ones(1)),
                                         anchor={'samples': self.parts[0]}, strength=1.0),          # masked input
            lambda: self.guard.run_stage('A', request_id='stream116b-s00000001', latent=self.b,
                                         anchor={'samples': self.parts[0]}, strength=1.0),          # wrong stage shape
        ]
        for case in cases:
            ns, _ = native_namespace()
            self.guard = la.LatentConditionGuard(tensor_metadata=metadata, get_noise_mask=ns['get_noise_mask'],
                                                 frames=49)
            self.guard.begin_request('stream116b-s00000001', 'a' * 64, self.parts)
            with self.assertRaises(la.LatentAnchorError):
                case()
            self.assertIsNotNone(self.guard.failed)


if __name__ == '__main__':
    unittest.main()
