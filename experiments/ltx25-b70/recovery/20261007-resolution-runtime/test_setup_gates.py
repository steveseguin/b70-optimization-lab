"""Actual historical receipt schemas; modified values are synthetic CPU controls."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('tested_setup_gates', HERE / 'setup_gates.py')
G = importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)
DATA = HERE.parents[1] / 'data/upstream-99b/two-way-w2-b1-p1-dxpu2-s256x256'


def fixture(pattern):
    matches = list(DATA.glob(pattern))
    assert len(matches) == 1, matches
    data = json.loads(matches[0].read_text())
    data.update(output_size='640x384', run_name='synthetic-cpu', server_identity_sha256='a'*64)
    return data


class GateControls(unittest.TestCase):
    def window(self):
        return fixture('text-window-probe-*.json')

    def freeze(self):
        d = fixture('sampler-capture-freeze-*.json')
        d['sampler_workers'] = d['coverage']['workers'] = 1
        c = d['chain_check']
        thread = c['rows'][0]['thread']
        c['rows'] = [r for r in c['rows'] if r['thread'] == thread]
        c['chains_checked'] = c['chains_passed'] = 2
        for row in c['rows']:
            for shape in row['shapes']:
                shape[0][1] = {64:240, 256:960}[shape[0][1]]
        return d

    def decode(self):
        d = fixture('decode-probe-*.json')
        d['references'] = 'none (speed only)'
        d['rows'] = [{'seed': 980000+i, 'output_size': '640x384',
                      'video_latent_shape': [1,128,4,12,20], 'passed': True,
                      'cards_bytewise_equal': True, 'replica_matches_native': True,
                      'native': {'images_sha256': 'b'*64, 'waveform_sha256': 'c'*64},
                      'replica': {'images_sha256': 'b'*64, 'waveform_sha256': 'c'*64}}
                     for i in range(10)]
        return d

    def check(self, kind, data):
        return getattr(G, 'validate_' + kind)(data, 'synthetic-cpu', 'a'*64)

    def test_window_actual_schema_and_closeness_negative(self):
        d = self.window()
        self.assertTrue(self.check('window', d)['passed'])
        d['rows'][0]['mean_rel'] = .1
        with self.assertRaisesRegex(RuntimeError, 'closeness'):
            self.check('window', d)

    def test_window_successful_prompt_does_not_override_negative_verdict(self):
        d = self.window()
        d.update(passed=False, outcome='window-not-close')
        with self.assertRaisesRegex(RuntimeError, 'did not qualify'):
            self.check('window', d)

    def test_coverage_worker_and_unfinished_pipeline(self):
        d = fixture('sampler-capture-coverage-*-cover.json')
        d['sampler_workers'] = d['coverage']['workers'] = 1
        self.assertTrue(self.check('coverage', d)['passed'])
        d['pipeline_running'] = 1
        with self.assertRaisesRegex(RuntimeError, 'quiescence'):
            self.check('coverage', d)

    def test_freeze_requires_same_size_eager_repeat_chain(self):
        d = self.freeze()
        self.assertTrue(self.check('freeze', d)['passed'])
        for field, bad in (('shapes', [[[1,256,4096],[1,26,2048]], [[1,64,4096],[1,26,2048]]]),
                           ('replay_equals_repeat', [True,False])):
            changed = copy.deepcopy(d)
            changed['chain_check']['rows'][0][field] = bad
            with self.assertRaisesRegex(RuntimeError, 'stage chain'):
                self.check('freeze', changed)

    def test_freeze_requires_fresh_floor_and_no_missing_residents(self):
        d = self.freeze()
        d['free_bytes']['xpu:0'] = G.GIB
        with self.assertRaisesRegex(RuntimeError, 'below floor'):
            self.check('freeze', d)
        d = self.freeze()
        d['residents_missing'] = [['LTXAV','xpu:0']]
        with self.assertRaisesRegex(RuntimeError, 'residence'):
            self.check('freeze', d)

    def test_decode_internal_probe_not_reference_parity(self):
        d = self.decode()
        result = self.check('decode', d)
        self.assertTrue(result['passed'])
        self.assertFalse(result['same_size_reference_comparison'])
        self.assertFalse(result['output_parity_claimed'])
        d['rows'][0]['replica']['images_sha256'] = 'd'*64
        with self.assertRaisesRegex(RuntimeError, 'tensors differ'):
            self.check('decode', d)

    def test_decode_negative_and_below_floor(self):
        d = self.decode()
        d['passed'] = False
        with self.assertRaisesRegex(RuntimeError, 'did not pass'):
            self.check('decode', d)
        d = self.decode()
        d['xpu:2_free_after_probe'][0] = G.GIB
        with self.assertRaisesRegex(RuntimeError, 'memory not admitted'):
            self.check('decode', d)


if __name__ == '__main__':
    unittest.main(verbosity=2)
