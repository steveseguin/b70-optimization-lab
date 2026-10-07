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
    data.update(output_size='640x384', frame_count=49, run_name='synthetic-cpu', server_identity_sha256='a'*64)
    return data


class GateControls(unittest.TestCase):
    def window(self):
        return fixture('text-window-probe-*.json')

    def freeze(self):
        d = fixture('sampler-capture-freeze-*.json')
        d['placement'] = 'two-way20-28'
        d['sampler_workers'] = d['coverage']['workers'] = 2
        c = d['chain_check']
        c['chains_checked'] = c['chains_passed'] = 4
        for row in c['rows']:
            row['blocks'] = list(range(20)) if row['device'] == 'xpu:0' else list(range(20,48))
            for shape in row['shapes']:
                shape[0][1] = {64:420, 256:1680}[shape[0][1]]
                shape[1][1] = 51
        return d

    def decode(self):
        d = fixture('decode-probe-*.json')
        d['references'] = 'none (speed only)'
        d['xpu:2_free_after_build'] = [8*G.GIB, 'mem_get_info']
        d['rows'] = [{'seed': 980000+i, 'output_size': '640x384',
                      'references': 'none (speed only)',
                      'video_latent_shape': [1,128,7,12,20], 'audio_latent_shape':[1,8,51,16],
                      'frame_count':49, 'passed': True,
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
        d['sampler_workers'] = d['coverage']['workers'] = 2
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

    def test_coverage_rejects_wrong_worker_names_count_and_routes(self):
        good = fixture('sampler-capture-coverage-*-cover.json')
        for mutate in (
                lambda d: d.update(worker_names=['ltx-sample-0', 'ltx-sample-0']),
                lambda d: d.update(sampler_workers=1),
                lambda d: d['coverage'].update(workers=1),
                lambda d: d['coverage'].update(routes=47),
                lambda d: d['coverage'].update(incomplete_routes=['missing-worker-1'])):
            d = copy.deepcopy(good)
            mutate(d)
            with self.assertRaises(RuntimeError):
                self.check('coverage', d)

    def test_freeze_requires_four_distinct_worker_device_chains(self):
        good = self.freeze()
        self.assertTrue(self.check('freeze', good)['passed'])
        # Retaining aggregate counts cannot hide one missing chain.
        d = copy.deepcopy(good)
        d['chain_check']['rows'].pop()
        with self.assertRaisesRegex(RuntimeError, 'replay incomplete'):
            self.check('freeze', d)
        # Two threads and two devices are insufficient if one pair is duplicated.
        d = copy.deepcopy(good)
        d['chain_check']['rows'][1] = copy.deepcopy(d['chain_check']['rows'][0])
        with self.assertRaisesRegex(RuntimeError, 'worker/device set'):
            self.check('freeze', d)
        # Each worker must cover both cards, not two unrelated device workers.
        d = copy.deepcopy(good)
        for i, row in enumerate(d['chain_check']['rows']):
            row['thread'] = 100+i
        with self.assertRaisesRegex(RuntimeError, 'worker/device set'):
            self.check('freeze', d)

    def test_freeze_requires_fresh_floor_and_no_missing_residents(self):
        d = self.freeze()
        d['free_bytes']['xpu:0'] = G.GIB
        with self.assertRaisesRegex(RuntimeError, 'below floor'):
            self.check('freeze', d)
        d = self.freeze()
        d['residents_missing'] = [['LTXAV','xpu:0']]
        with self.assertRaisesRegex(RuntimeError, 'residence'):
            self.check('freeze', d)

    def test_frame_identity_is_required_for_all_setup_receipts(self):
        for kind, make in (('window', self.window), ('freeze', self.freeze), ('decode', self.decode)):
            for bad in (None, 25, 49.0, True):
                with self.subTest(kind=kind, frame_count=bad):
                    d = make()
                    if bad is None:
                        d.pop('frame_count')
                    else:
                        d['frame_count'] = bad
                    with self.assertRaises(RuntimeError):
                        self.check(kind, d)

    def test_every_decoder_row_requires49_frames_and_both_latent_shapes(self):
        for key, bad in (('frame_count', None), ('frame_count', 25), ('frame_count', 49.0),
                         ('frame_count', True), ('video_latent_shape', [1,128,4,12,20]),
                         ('audio_latent_shape', [1,8,26,16])):
            with self.subTest(key=key, value=bad):
                d = self.decode()
                if bad is None:
                    d['rows'][-1].pop(key)
                else:
                    d['rows'][-1][key] = bad
                with self.assertRaises(RuntimeError):
                    self.check('decode', d)

    def test_decoder_build_requires8GiB_but_probe_retains2GiB_floor(self):
        d = self.decode()
        d['xpu:2_free_after_build'] = [8*G.GIB, 'mem_get_info']
        d['xpu:2_free_after_probe'] = [2*G.GIB, 'mem_get_info']
        self.assertTrue(self.check('decode', d)['passed'])
        for key in ('xpu:2_free_after_build', 'xpu:2_free_after_probe'):
            bad = copy.deepcopy(d)
            bad[key][0] -= 1
            with self.assertRaisesRegex(RuntimeError, 'memory not admitted'):
                self.check('decode', bad)

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

    def test_decode_equal_empty_objects_are_not_tensor_evidence(self):
        d = self.decode()
        d['rows'][0]['native'] = d['rows'][0]['replica'] = {}
        with self.assertRaisesRegex(RuntimeError, 'Missing decoder tensor hashes'):
            self.check('decode', d)


if __name__ == '__main__':
    unittest.main(verbosity=2)
