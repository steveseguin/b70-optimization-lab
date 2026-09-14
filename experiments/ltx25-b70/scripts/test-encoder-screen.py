#!/usr/bin/env python3
"""CPU-only client boundary tests. No HTTP calls, server actions or GPU work."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('screen', Path(__file__).with_name('run-encoder-screen.py'))
screen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(screen)


class ClientGates(unittest.TestCase):
    def setUp(self):
        self.base = json.loads((screen.LANE / 'data/speed-resident-split-api.json').read_text())

    def test_schedule_bound_and_initialization_separation(self):
        rows = screen.schedule()
        screen.validate_schedule(rows)
        self.assertEqual(len({r['run'] for r in rows}), 25)
        self.assertEqual(sum(r['initialization'] for r in rows), 5)
        self.assertEqual([r['fixture'] for r in rows[:5]], ['boat', 'boat', 'marble', 'bird', 'boat'])
        for invalid in [rows[:-1], rows + [rows[0]], list(reversed(rows))]:
            with self.assertRaises(RuntimeError):
                screen.validate_schedule(invalid)

    def test_graph_preserves_quality_and_forces_diagnostic_dependency(self):
        good = screen.expected_graph(self.base, 'combined')
        screen.validate_graph(good, self.base, 'combined')
        changes = [('356', 'width', 16), ('356', 'length', 9),
                   ('365', 'frame_rate', 12), ('365', 'positive', ['364', 0]),
                   ('404', 'sigmas', '1,0'), ('420', 'placement', 'single')]
        for node, field, value in changes:
            bad = copy.deepcopy(good)
            bad[node]['inputs'][field] = value
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                screen.validate_graph(bad, self.base, 'combined')

    def test_identity_rejects_endpoint_process_and_artifact_mismatch(self):
        kw = dict(packet=Path('/packet'), manifest_sha='manifest', server_run=Path('/run'),
                  ticks='123', boot='boot', model_sha='model', args_sha='args',
                  extensions={'helper': 'hash'}, launcher_sha='launcher', torch_version='torch')
        identity = dict(pid=101, proc_start_ticks='123', boot_id='boot', source_commit=screen.PIN,
            source_packet_manifest_sha256='manifest', source_packet_path='/packet', encoder_run_dir='/run',
            extension_sha256s={'helper': 'hash'}, launcher_sha256='launcher',
            model_verification_sha256='model', server_args_sha256='args', torch='torch')
        screen.validate_identity_values(identity, identity, **kw)
        for field in screen.IDENTITY_FIELDS:
            bad = {**identity, field: 'changed'}
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                screen.validate_identity_values(identity, bad, **kw)
        for field in ['ticks', 'boot', 'model_sha', 'args_sha', 'launcher_sha', 'torch_version', 'manifest_sha']:
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                screen.validate_identity_values(identity, identity, **{**kw, field: 'changed'})

    def test_candidate_placement_rechecks_individual_tensor_records(self):
        records = [{'name': str(i), 'bytes': 2, 'device': 'xpu:2', 'dtype': 'torch.bfloat16',
                    'kind': 'rmsnorm' if i < 289 else 'scalar', 'shape': [1]} for i in range(337)]
        records[0]['bytes'] = 1539680 - 336 * 2
        records[0]['shape'] = [records[0]['bytes'] // 2]
        good = {'schema': 'ltx.encoder-placement.v1', 'stage': 'post_encode',
            'run_name': 'run', 'encoder_variant': 'small_state', 'passed': True, 'failures': [],
            'server_identity_sha256': 'identity', 'model_verification_sha256': 'model',
            'inspection': {'small_state': {'rmsnorm_count': 289, 'scalar_count': 48,
                'total_bytes': 1539680, 'records': records}, 'accounting': {
                'patcher_small_state_option': True, 'crop_option': False, 'small_buffers_loaded': True,
                'model_small_state_policy': True, 'is_dynamic': False, 'reported_loaded_weight_bytes': 1539680}}}
        screen.validate_placement(good, 'run', 'small_state', 'identity', 'model')
        for key, value in [('device', 'cpu'), ('dtype', 'torch.float16'), ('name', '1'), ('bytes', 10)]:
            bad = copy.deepcopy(good)
            bad['inspection']['small_state']['records'][0][key] = value
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                screen.validate_placement(bad, 'run', 'small_state', 'identity', 'model')

    def test_unload_rechecks_registered_ownership_device_and_accounting(self):
        state = {'parameters': {'records': [{'name': 'weight', 'dtype': 'torch.bfloat16',
                 'shape': [1], 'bytes': 2, 'owner_id': 1, 'device': 'cpu'}]},
                 'buffers': {'records': []}, 'accounting': {'offload_device': 'cpu',
                 'reported_loaded_weight_bytes': 0, 'reported_offload_buffer_bytes': 0,
                 'marked_modules': [], 'small_buffers_loaded': False, 'model_small_state_policy': False}}
        before = {'generation': 3, 'encoder_variant': 'small_state'}
        after = {'generation': 4, 'encoder_variant': 'combined'}
        good = {'schema': 'ltx.encoder-unload.v1', 'passed': True, 'failures': [],
                'old_generation': 3, 'new_generation': 4, 'old_variant': 'small_state',
                'new_variant': 'combined', 'server_identity_sha256': 'id',
                'model_verification_sha256': 'model', 'before': copy.deepcopy(state), 'after': state}
        screen.validate_unload(good, before, after, 'id', 'model')
        for key, value in [('owner_id', 2), ('device', 'xpu:2'), ('dtype', 'torch.float16')]:
            bad = copy.deepcopy(good)
            bad['after']['parameters']['records'][0][key] = value
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                screen.validate_unload(bad, before, after, 'id', 'model')
        bad = copy.deepcopy(good)
        bad['after']['accounting']['reported_loaded_weight_bytes'] = 2
        with self.assertRaises(RuntimeError):
            screen.validate_unload(bad, before, after, 'id', 'model')


class SimulatedCampaign(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.packet, self.server = self.root / 'packet', self.root / 'server'
        (self.packet / 'graphs').mkdir(parents=True)
        self.server.mkdir()
        self.identity = {key: 'fixture' for key in screen.IDENTITY_FIELDS}
        self.identity['pid'] = 101
        self.write(self.server / 'server-identity.json', self.identity)
        base = json.loads((screen.LANE / 'data/speed-resident-split-api.json').read_text())
        for variant in set(screen.ARMS):
            self.write(self.packet / 'graphs' / (variant + '.json'), screen.expected_graph(base, variant))
        for fixture, (reference, seed) in screen.REFERENCES.items():
            g = copy.deepcopy(base)
            for node in ('338', '339'):
                g[node]['inputs']['noise_seed'] = seed
            g['364']['inputs']['text'] = fixture
            self.write(self.root / 'requests' / reference / 'prompt.json', g)
            p = self.root / 'output/validation' / reference / 'tensors.safetensors'
            p.parent.mkdir(parents=True)
            p.write_bytes(b'protected reference')
        self.requests = []
        self.comparisons = []
        self.fail_at = None
        self.patches = [patch.object(screen, 'ROOT', self.root),
            patch.object(screen, 'identity_binding', return_value=(self.identity, {})),
            patch.object(screen, 'run_subprocess', side_effect=self.fake_process),
            patch.object(screen.retention, 'snapshot', return_value={'cpu_test': True}),
            patch.object(screen.retention, 'validate_capture', return_value={'cpu_test': True}),
            patch.object(screen, 'validate_placement'),
            patch.object(screen, 'validate_unload'),
            patch.object(screen.retention, 'sha', wraps=screen.retention.sha)]
        # The production client records common-file hash; root supplies the file.
        for handle in self.patches:
            handle.start()

    def tearDown(self):
        for handle in reversed(self.patches):
            handle.stop()
        self.temp.cleanup()

    def write(self, path, obj):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(obj))

    def fake_process(self, command, log, timeout):
        log.write_text('CPU simulation only')
        if command[1].endswith('profile-clip.py'):
            run = command[2]
            self.requests.append(run)
            generation = (len(self.requests) - 1) // 5 + 1
            variant = screen.ARMS[generation - 1]
            self.write(self.server / f'components-{generation:02d}-split-{variant}.json', {
                'generation': generation, 'encoder_variant': variant, 'placement': 'split',
                'model_verification_sha256': self.identity['model_verification_sha256']})
            if generation > 1 and len(self.requests) % 5 == 1:
                self.write(self.server / f'encoder-unload-{generation-1:02d}-to-{generation:02d}.json', {})
            request = self.root / 'requests' / run
            graph = json.loads(Path(command[command.index('--graph') + 1]).read_text())
            graph['414']['inputs']['run_name'] = run
            graph['75']['inputs']['filename_prefix'] = run + '/preview'
            self.write(request / 'prompt.json', graph)
            self.write(request / 'identity.json', self.identity)
            self.write(request / 'profile.json', {'preview_ready_seconds': 7.0})
            self.write(request / 'history.json', {'outputs': {'75': {'images': [
                {'type': 'output', 'subfolder': run, 'filename': 'preview_00001_.mp4'}]}}})
            self.write(self.server / ('encoder-placement-' + run + '.json'), {})
            for relative in [Path('output/validation') / run / 'tensors.safetensors',
                             Path('output') / run / 'preview_00001_.mp4']:
                p = self.root / relative
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(b'CPU simulated output')
        else:
            reference, run = command[2:4]
            self.comparisons.append(run)
            if len(self.comparisons) == self.fail_at:
                raise RuntimeError('simulated exactness failure')
            self.write(Path(command[-1]), {'status': 'passed', 'comparisons': {
                key: {'bitwise_equal': True} for key in ('images', 'video_latent', 'audio_latent', 'waveform')}})

    def test_finite_campaign_compares_initializations_and_prunes_only_owned_passes(self):
        screen.run_screen(self.packet, 'manifest', self.server)
        self.assertEqual(len(self.requests), 25)
        self.assertEqual(self.requests, self.comparisons)
        progress = json.loads((self.root / screen.CAMPAIGN / 'progress.json').read_text())
        self.assertEqual(progress['status'], 'passed')
        self.assertFalse(progress['speed_promotion'])
        self.assertEqual(len(progress['retained_outputs']), 3)
        for reference, seed in screen.REFERENCES.values():
            self.assertEqual((self.root / 'output/validation' / reference / 'tensors.safetensors').read_bytes(), b'protected reference')
        for run in self.requests:
            self.assertFalse((self.root / 'output/validation' / run / 'tensors.safetensors').exists())

    def test_first_failure_halts_without_retry_and_preserves_failed_outputs(self):
        self.fail_at = 2
        with self.assertRaisesRegex(RuntimeError, 'simulated'):
            screen.run_screen(self.packet, 'manifest', self.server)
        self.assertEqual(len(self.requests), 2)
        failed = self.requests[-1]
        self.assertTrue((self.root / 'output/validation' / failed / 'tensors.safetensors').exists())
        self.assertTrue((self.root / 'output' / failed / 'preview_00001_.mp4').exists())
        progress = json.loads((self.root / screen.CAMPAIGN / 'progress.json').read_text())
        self.assertEqual(progress['status'], 'failed')

    def test_next_preflight_failure_preserves_prior_passed_status(self):
        calls = []
        def gated(*args):
            calls.append(args)
            if len(calls) == 4:
                raise RuntimeError('simulated next preflight failure')
            return self.identity, {}
        with patch.object(screen, 'identity_binding', side_effect=gated):
            with self.assertRaisesRegex(RuntimeError, 'next preflight'):
                screen.run_screen(self.packet, 'manifest', self.server)
        self.assertEqual(len(self.requests), 1)
        progress = json.loads((self.root / screen.CAMPAIGN / 'progress.json').read_text())
        self.assertEqual(progress['rows'][0]['status'], 'passed')
        self.assertEqual(progress['failure_stage'], 'preflight')
        self.assertIsNone(progress['failed_run'])
        self.assertEqual(progress['attempted_run'], screen.schedule()[1]['run'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
