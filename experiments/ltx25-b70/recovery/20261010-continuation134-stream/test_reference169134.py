"""Offline checks of frozen169 hashes against exact verdict-bound source snapshots."""
import hashlib
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
VERDICT_SHA = '4eeb3b603c9497f3105ccca65ffce0aeab29ceacedcf97067a33eb07b26bd08a'


class Reference169(unittest.TestCase):
    def setUp(self):
        self.reference = json.loads((HERE / 'reference-frame-qualification-hashes.json').read_text())
        self.variant = self.reference['variants']['169/two-way20-28/frame']
        raw = (HERE / 'reference-frame-169-provenance.json').read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), self.variant['source_provenance_sha256'])
        self.provenance = json.loads(raw)
        self.verdict = self.decode_source(self.provenance['verdict'])

    def decode_source(self, source):
        raw = source['raw_utf8'].encode()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), source['sha256'])
        return json.loads(raw)

    def test_frozen_source_verdict_identity_and_success(self):
        self.assertEqual(self.provenance['verdict']['sha256'], VERDICT_SHA)
        self.assertEqual(self.variant['source_verdict_sha256'], VERDICT_SHA)
        self.assertEqual(self.variant['source_verdict'], self.provenance['verdict']['path'])
        self.assertEqual(self.variant['source_packet'], '123b')
        self.assertIs(self.verdict['passed'], True)
        self.assertEqual((self.verdict['frames'], self.verdict['placement'], self.verdict['anchor']),
                         (169, 'two-way20-28', 'frame'))
        self.assertEqual(self.verdict['decoder_graph'], 0)
        self.assertEqual(self.verdict['server_options']['display_device'], 'xpu:3')
        self.assertEqual(len(self.verdict['exact_replay']), 3)
        self.assertTrue(all(r['all_identical'] for r in self.verdict['exact_replay']))

    def test_receipt_and_decode_snapshots_match_verdict_bindings(self):
        self.assertEqual(len(self.provenance['records']), 6)
        root = Path(self.variant['source_verdict']).parent
        for key, source in self.provenance['records'].items():
            category, name = key.split('/')
            record = self.decode_source(source)
            binding = self.verdict[category][name]
            self.assertEqual({k: source[k] for k in ('path', 'sha256')}, binding)
            self.assertEqual(Path(source['path']).parent, root / 'receipts')
            self.assertEqual(record['run_name'], name)
            self.assertEqual(record['frames'], 169)

    def test_each_reference_hash_reconstructs_from_bound_records(self):
        self.assertEqual(len(self.variant['chunks']), 3)
        for k, wanted in enumerate(self.variant['chunks']):
            name = 'stream123b-qeager-c%06d' % k
            r = self.decode_source(self.provenance['records']['receipts/' + name])
            d = self.decode_source(self.provenance['records']['decode_records/' + name])
            actual = {key: r['tensors'][key]['sha256'] for key in
                      ('video_latent', 'audio_latent', 'stage_a_latent')}
            actual.update({key: d['tensors'][key]['sha256'] for key in ('images', 'waveform')})
            actual.update(last_frame=d['last_frame_sha256'], anchor_file=r['anchor_out']['sha256'],
                          source_run_name=name)
            self.assertEqual(wanted, actual)
            capture = self.verdict['captures'][name]
            for key in ('video_latent', 'audio_latent', 'images', 'waveform'):
                self.assertEqual(actual[key], capture['tensors'][key])
            self.assertEqual(actual['anchor_file'], actual['last_frame'])
            self.assertEqual(actual['last_frame'], capture['last_frame_sha256'])

    def test_inherited_reference_variants_preserved(self):
        old = json.loads((HERE.parent / '20261010-continuation133b-stream' /
                          'reference-frame-qualification-hashes.json').read_text())
        for key, value in old['variants'].items():
            self.assertEqual(self.reference['variants'][key], value)
        self.assertEqual(set(self.reference['variants']) - set(old['variants']), {'169/two-way20-28/frame'})


if __name__ == '__main__':
    unittest.main()
