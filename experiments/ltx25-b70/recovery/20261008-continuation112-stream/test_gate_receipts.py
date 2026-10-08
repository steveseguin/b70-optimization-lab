"""CPU tests: qualification gate decisions, capture re-read, receipt schema and anchor files."""
import copy
import hashlib
import json
import math
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import qualification_gate as gate  # noqa: E402
import stream_contract as c  # noqa: E402
import stream_receipts as rec  # noqa: E402

PLAN = 'p' * 64
TENSORS = ('images', 'video_latent', 'audio_latent', 'waveform')


def h(*parts):
    return hashlib.sha256(repr(parts).encode()).hexdigest()


def receipt(params, frames, chunk_tensors, anchor_in=None, new_captures=0, routes=48, sigs=4, reused=False,
            text='t'):
    g = c.geometry(frames)
    name = c.run_name(params)
    k = params['chunk_index']
    return {
        'schema': rec.SCHEMA, 'run_name': name, 'prompt_id': 'pid-' + name, 'kind': params['kind'],
        'scene_id': params['scene_id'], 'chunk_index': k, 'seed': params['seed'], 'stream_seq': params['stream_seq'],
        'prompt_sha256': c.text_sha256(params['prompt']), 'frames': frames, 'reuse_text': params['reuse_text'],
        'plan_sha256': PLAN, 'qualification_id': c.qualification_id(frames), 'runtime_manifest_sha256': 'r' * 64,
        'server_identity_sha256': 's' * 64, 'committed': True,
        'tensors': {t: {'shape': g['tensor_shapes'][t], 'dtype': 'torch.float32', 'finite': True,
                        'sha256': chunk_tensors[t]} for t in TENSORS},
        'anchor_in': anchor_in,
        'anchor_out': {'sha256': chunk_tensors['anchor'], 'path': '/x/' + name + '.f32', 'bytes': c.ANCHOR_BYTES,
                       'frame_index': g['anchor_frame_index']},
        'delivery': rec.delivery(k, frames),
        'preview': {'path': '/out/' + name + '/preview_00001_.mp4', 'bytes': 1000},
        'capture': ({'path': '/out/validation/' + name + '/tensors.safetensors'}
                    if params['kind'] in c.CAPTURE_KINDS else None),
        'timing_ns': {key: 1 for key in rec.TIMING_KEYS},
        'sanity': {'finite': True, 'shapes': True, 'anchor_chain': True},
        'text': {'reused': reused, 'tensors': [{'sha256': h('text', text)}]},
        'graph': {'gate_mode': 'original' if params['kind'] == 'qualify-eager' else 'graph',
                  'routes': routes, 'new_captures': new_captures, 'signatures_per_route': sigs},
        'memory': {}, 'storage': {}}


def passing(frames=25, reuse=0):
    rows = c.qualification_params(frames, reuse)
    out, captures = [], {}
    for i, params in enumerate(rows):
        chain, k = divmod(i, 3)
        tensors = {t: h(t, k) for t in TENSORS}
        tensors['anchor'] = h('anchor', k)
        anchor_in = None if k == 0 else {'sha256': h('anchor', k - 1),
                                         'source_run_name': c.run_name(rows[i - 1]), 'path': '/x'}
        eager = chain == 0
        r = receipt(params, frames, tensors, anchor_in,
                    new_captures=(0 if eager else (96 if (chain, k) in ((1, 0), (1, 1)) else 0)),
                    routes=0 if eager else 48, sigs=0 if eager else 4,
                    reused=bool(params['reuse_text']), text=params['prompt'])
        out.append(r)
        captures[r['run_name']] = {'tensors': {t: tensors[t] for t in TENSORS}, 'last_frame_sha256': tensors['anchor']}
    return out, captures


class Gate(unittest.TestCase):
    def test_passes_when_all_identical(self):
        for reuse in (0, 1):
            receipts, captures = passing(reuse=reuse)
            verdict = gate.decide(receipts, captures, PLAN, 25, reuse)
            self.assertTrue(verdict['passed'], verdict['failures'])
            self.assertTrue(all(p['all_four_identical'] for p in verdict['exact_replay']))
            self.assertEqual(verdict['unique_video_frames_per_chain'], 25 + 24 + 24)

    def test_any_tensor_byte_difference_fails(self):
        for t in TENSORS:
            receipts, captures = passing()
            receipts[7]['tensors'][t]['sha256'] = h('different')
            captures[receipts[7]['run_name']]['tensors'][t] = h('different')
            verdict = gate.decide(receipts, captures, PLAN, 25, 0)
            self.assertFalse(verdict['passed'])
            self.assertTrue(any('differ at chunk 1' in f for f in verdict['failures']))

    def test_capture_file_must_agree_with_output_node(self):
        receipts, captures = passing()
        captures[receipts[2]['run_name']]['tensors']['waveform'] = h('other')
        self.assertFalse(gate.decide(receipts, captures, PLAN, 25, 0)['passed'])
        receipts, captures = passing()
        captures[receipts[2]['run_name']]['last_frame_sha256'] = h('other')
        self.assertFalse(gate.decide(receipts, captures, PLAN, 25, 0)['passed'])
        receipts, captures = passing()
        captures.pop(receipts[0]['run_name'])
        self.assertFalse(gate.decide(receipts, captures, PLAN, 25, 0)['passed'])

    def test_anchor_chain_must_use_own_predecessor(self):
        receipts, captures = passing()
        receipts[4]['anchor_in']['source_run_name'] = receipts[0]['run_name']
        self.assertFalse(gate.decide(receipts, captures, PLAN, 25, 0)['passed'])
        receipts, captures = passing()
        receipts[3]['anchor_in'] = {'sha256': h('x'), 'source_run_name': 'y'}
        self.assertFalse(gate.decide(receipts, captures, PLAN, 25, 0)['passed'])

    def test_replay_only_requests_must_not_capture(self):
        for index in (5, 6, 7, 8):
            receipts, captures = passing()
            receipts[index]['graph']['new_captures'] = 1
            self.assertFalse(gate.decide(receipts, captures, PLAN, 25, 0)['passed'])

    def test_eager_chain_must_not_see_routes_and_signature_ceiling(self):
        receipts, captures = passing()
        receipts[1]['graph']['routes'] = 48
        self.assertFalse(gate.decide(receipts, captures, PLAN, 25, 0)['passed'])
        receipts, captures = passing()
        for r in receipts[3:]:
            r['graph']['signatures_per_route'] = 9
        self.assertFalse(gate.decide(receipts, captures, PLAN, 25, 0)['passed'])

    def test_text_pattern_and_conditioning_identity(self):
        receipts, captures = passing(reuse=1)
        receipts[4]['text']['reused'] = False
        self.assertFalse(gate.decide(receipts, captures, PLAN, 25, 1)['passed'])
        receipts, captures = passing(reuse=1)
        receipts[7]['text']['tensors'] = [{'sha256': h('drift')}]
        verdict = gate.decide(receipts, captures, PLAN, 25, 1)
        self.assertFalse(verdict['passed'])
        self.assertFalse(verdict['text_reuse_bit_identity_evidence'])

    def test_wrong_count_or_order(self):
        receipts, captures = passing()
        self.assertFalse(gate.decide(receipts[:8], captures, PLAN, 25, 0)['passed'])
        receipts, captures = passing()
        receipts[3], receipts[6] = receipts[6], receipts[3]
        self.assertFalse(gate.decide(receipts, captures, PLAN, 25, 0)['passed'])


class CaptureReread(unittest.TestCase):
    def test_reads_safetensors_layout(self):
        frames = 25
        g = c.geometry(frames)
        header, offset, blobs = {}, 0, {}
        for i, name in enumerate(sorted(g['tensor_shapes'])):
            shape = g['tensor_shapes'][name]
            size = math.prod(shape) * 4
            blobs[name] = (bytes([i + 1]) * size)
            header[name] = {'dtype': 'F32', 'shape': shape, 'data_offsets': [offset, offset + size]}
            offset += size
        raw = json.dumps(header).encode()
        raw += b' ' * (-len(raw) % 8)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'tensors.safetensors'
            path.write_bytes(struct.pack('<Q', len(raw)) + raw + b''.join(blobs[n] for n in sorted(blobs)))
            result = gate.capture_tensor_hashes(path, frames)
        for name in g['tensor_shapes']:
            self.assertEqual(result['tensors'][name], hashlib.sha256(blobs[name]).hexdigest())
        frame = c.ANCHOR_BYTES
        self.assertEqual(result['last_frame_sha256'], hashlib.sha256(blobs['images'][24 * frame:25 * frame]).hexdigest())


class Receipts(unittest.TestCase):
    def sample(self, kind='stream', k=3):
        if kind == 'stream':
            params = c.stream_params(49, k, 'boat', 1, 'a' * 64 if k else '', 's')
            prev = dict(params, stream_seq=k - 1, chunk_index=k - 1)
        else:
            params = c.qualification_params(49, 0)[k]
            prev = dict(params, chunk_index=k - 1)
        tensors = {t: h(t) for t in TENSORS}
        tensors['anchor'] = h('a')
        anchor_in = {'sha256': 'a' * 64, 'source_run_name': c.run_name(prev), 'path': '/a'} if k else None
        return receipt(params, 49, tensors, anchor_in)

    def test_valid_stream_and_qualification(self):
        rec.validate_receipt(self.sample())
        rec.validate_receipt(self.sample(k=0))
        rec.validate_receipt(self.sample('qualify', 1))

    def test_schema_violations(self):
        bad = [
            lambda r: r['tensors'].pop('waveform'),
            lambda r: r['tensors']['images'].__setitem__('finite', False),
            lambda r: r['tensors']['images'].__setitem__('shape', [25, 256, 256, 3]),
            lambda r: r.__setitem__('anchor_in', None),
            lambda r: r['anchor_in'].__setitem__('source_run_name', 'stream112-s00000001'),
            lambda r: r.__setitem__('capture', {'path': '/x/tensors.safetensors'}),
            lambda r: r['delivery'].__setitem__('new_frames', 49),
            lambda r: r['timing_ns'].pop('preview_written'),
            lambda r: r['sanity'].__setitem__('anchor_chain', False),
            lambda r: r['preview'].__setitem__('path', 'relative.mp4'),
            lambda r: r['text'].__setitem__('reused', True),
            lambda r: r['graph'].__setitem__('gate_mode', 'original'),
        ]
        for mutate in bad:
            r = copy.deepcopy(self.sample())
            mutate(r)
            with self.assertRaises((ValueError, KeyError, TypeError)):
                rec.validate_receipt(r)

    def test_delivery(self):
        self.assertEqual(rec.delivery(0, 49)['new_frames'], 49)
        d = rec.delivery(5, 49)
        self.assertEqual((d['new_frames'], d['first_new_frame_index'], d['drop_leading_frames']), (48, 1, 1))
        self.assertEqual(rec.delivery(1, 25)['new_frames'], 24)


class AnchorFiles(unittest.TestCase):
    def test_roundtrip_and_refusals(self):
        raw = struct.pack('<f', 0.5) * (c.ANCHOR_BYTES // 4)
        with tempfile.TemporaryDirectory() as tmp:
            meta = rec.write_anchor(Path(tmp), 'stream112-s00000000', raw, 49)
            self.assertEqual(meta['frame_index'], 48)
            self.assertEqual(rec.read_anchor(meta['path'], meta['sha256']), raw)
            with self.assertRaises(ValueError):
                rec.read_anchor(meta['path'], 'b' * 64)
            with self.assertRaises(FileExistsError):
                rec.write_anchor(Path(tmp), 'stream112-s00000000', raw, 49)
            with self.assertRaises(ValueError):
                rec.write_anchor(Path(tmp), 'short', raw[:-4], 49)
            nan = struct.pack('<I', 0x7fc00000) + raw[4:]
            with self.assertRaises(ValueError):
                rec.write_anchor(Path(tmp), 'nan', nan, 49)
            link = Path(tmp) / 'link.f32'
            os.symlink(meta['path'], link)
            with self.assertRaises((ValueError, OSError)):
                rec.read_anchor(str(link), meta['sha256'])
            other = Path(tmp) / 'bad.f32'
            other.write_bytes(raw[:-4])
            with self.assertRaises(ValueError):
                rec.read_anchor(str(other), hashlib.sha256(raw[:-4]).hexdigest())


if __name__ == '__main__':
    unittest.main()
