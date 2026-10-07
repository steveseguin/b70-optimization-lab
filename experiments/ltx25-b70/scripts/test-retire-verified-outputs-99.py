#!/usr/bin/env python3
"""Synthetic CPU-only controls; all deletion targets are disposable /tmp files."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location('retire99', Path(__file__).with_name('retire-verified-outputs-99.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class Retirement(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ltx-retire99-test-')
        self.root = Path(self.tmp.name)
        self.server = self.root / 'server'
        self.out = self.root / 'receipts'
        self.server.mkdir(); self.out.mkdir()
        self.identity = {'pid': 2147483647, 'proc_start_ticks': '123', 'boot_id': 'synthetic',
                         'source_packet_manifest_sha256': 'a' * 64, 'model_verification_sha256': 'b' * 64}
        self.put(self.server / 'server-identity.json', self.identity)
        self.prereg = self.root / 'fixtures.json'
        self.put(self.prereg, {'fixtures': [{'id': 'boat', 'reference': 'protected-boat'}]})
        self.make_request('protected-boat')
        self.capture('protected-boat')
        rows = []
        for i in range(3):
            name = f'arm99-{i:02d}'
            self.make_request(name); self.capture(name)
            self.put(self.out / (name + '-parity.json'), {'status': 'passed',
                     'comparisons': {k: {'bitwise_equal': True, 'same_layout': True} for k in m.KEYS},
                     'executions': [{'name': 'protected-boat'}, {'name': name}]})
            rows.append({'prompt': name, 'index': i, 'emitted_index': i, 'emitted_fixture': 'boat',
                         'reference': 'protected-boat', 'fill': False, 'exact': True,
                         'parity_status': 'passed', 'duplicate': False})
        self.throughput = self.out / 'throughput.json'
        self.result = {'schema': 'ltx.throughput-fixtures-96.v1', 'all_exact': True, 'emission_sequence_ok': True, 'exit_code': 0,
                       'emission_problems': [], 'shape_problems': [], 'references_from': str(self.prereg),
                       'prefix': 'arm99', 'server_run': str(self.server), 'fixture_count': 1,
                       'count': 3, 'rows': rows, 'fixture_order': ['boat'] * 3, 'sampler_depth': 0,
                       'decode_depth': 0, 'expected_clips': 3, 'distinct_clips_emitted': 3}
        self.put(self.throughput, self.result)
        self.process = mock.patch.object(m, 'process_exists', return_value=False)
        self.process.start()

    def tearDown(self):
        self.process.stop(); self.tmp.cleanup()

    def put(self, path, obj):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(obj))

    def make_request(self, name):
        folder = self.root / 'requests' / name
        prompt = {'fixture': 'boat'}
        objects = {'prompt': prompt, 'identity': self.identity,
                   'submission': {'prompt_id': name}, 'result': {'prompt_id': name},
                   'history': {'prompt': [0, name, prompt], 'status': {
                       'status_str': 'success', 'completed': True, 'messages': []}}}
        for key, value in objects.items():
            self.put(folder / (key + '.json'), value)

    def capture(self, name):
        path = self.raw(name)
        path.parent.mkdir(parents=True)
        path.write_bytes(b'synthetic matching archive, never an actual model')
        self.put(path.parent / 'summary.json', {'deterministic_enabled': True,
                 'deterministic_warn_only': False, 'tensors': {k: {'finite': True} for k in m.KEYS}})
        (path.parent / 'preview.mp4').write_bytes(b'preserve preview')

    def raw(self, name):
        return self.root / 'output/validation' / name / 'tensors.safetensors'

    def plan(self):
        return m.build_plan(self.root, self.throughput)

    def saved_plan(self):
        path = self.out / 'plan.json'
        m.sync_json(path, self.plan())
        return path, m.fingerprint(path)['sha256']

    def apply(self, path, digest):
        m.apply_plan(path, digest, self.out / 'applied.json')

    def test_real_packet97_success_shape_without_exit_code(self):
        # Use the actual retained 13-prompt/3-fill/10-emission success schema,
        # not a success object fabricated to mirror the retirement helper.
        source = Path(__file__).resolve().parents[1] / 'data/place-97/two-way-w2-b1-p1-dxpu2/f97-twowayw2b1p1dxpu2-probe-throughput.json'
        actual = json.loads(source.read_text())
        self.assertNotIn('exit_code', actual)
        self.assertEqual((actual['count'], actual['expected_clips']), (13, 10))
        self.assertEqual(len([r for r in actual['rows'] if r['fill']]), 3)
        actual['server_run'] = str(self.server)
        actual['references_from'] = str(self.prereg)
        fixtures = []
        for row in actual['rows']:
            name = row['prompt']
            self.make_request(name); self.capture(name)
            if row['fill']:
                continue
            reference = row['reference']
            fixtures.append({'id': row['emitted_fixture'], 'reference': reference})
            self.make_request(reference); self.capture(reference)
            self.put(self.out / (name + '-parity.json'), {'status': 'passed',
                     'comparisons': {k: {'bitwise_equal': True, 'same_layout': True} for k in m.KEYS},
                     'executions': [{'name': reference}, {'name': name}]})
        self.put(self.prereg, {'fixtures': fixtures})
        self.put(self.throughput, actual)
        plan = self.plan()
        self.assertEqual(len(plan['keep_first_per_fixture']), 10)
        self.assertEqual(plan['retire'], [])
        self.assertEqual(plan['validation']['completed_prompts'], 13)
        self.assertEqual(plan['validation']['exact_emitted_clips'], 10)
        # Missing exit_code does not override any structural failure.
        actual['rows'][-1]['exact'] = False
        self.put(self.throughput, actual)
        with self.assertRaisesRegex(RuntimeError, 'nonexact row'):
            self.plan()

    def test_optional_exit_code_still_refuses_failure_and_wrong_type(self):
        for exit_code in (1, -1, None, False, '0'):
            with self.subTest(exit_code=exit_code):
                self.put(self.throughput, {**self.result, 'exit_code': exit_code})
                with self.assertRaisesRegex(RuntimeError, 'failed/incomplete'):
                    self.plan()
        missing = dict(self.result); missing.pop('exit_code')
        self.put(self.throughput, missing)
        self.assertEqual(len(self.plan()['retire']), 2)

    def test_plan_never_deletes_keeps_first_and_reference(self):
        plan = self.plan()
        self.assertEqual(len(plan['keep_first_per_fixture']), 1)
        self.assertEqual(len(plan['retire']), 2)
        self.assertEqual(plan['keep_first_per_fixture'][0]['candidate']['path'], str(self.raw('arm99-00')))
        self.assertTrue(all(self.raw(n).exists() for n in ('protected-boat', 'arm99-00', 'arm99-01', 'arm99-02')))

    def test_apply_only_duplicates_preserves_all_other_files(self):
        before = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        path, digest = self.saved_plan()
        self.apply(path, digest)
        removed = {self.raw('arm99-01'), self.raw('arm99-02')}
        for p, data in before.items():
            if p in removed:
                self.assertFalse(p.exists())
            else:
                self.assertEqual(p.read_bytes(), data)
        receipt = json.loads((self.out / 'applied.json').read_text())
        self.assertEqual(receipt['status'], 'completed')
        self.assertEqual(len(receipt['deleted']), 2)
        self.assertTrue((self.out / 'applied.json.intent.json').exists())
        events = (self.out / 'applied.json.events.jsonl').read_text().splitlines()
        self.assertEqual(len(events), 2)
        self.assertTrue(all(json.loads(row)['phase'] == 'deleted' for row in events))
        with self.assertRaises(RuntimeError):
            self.apply(path, digest)

    def test_live_pid_refuses_before_any_archive_read(self):
        with mock.patch.object(m, 'process_exists', return_value=True), mock.patch.object(m, 'fingerprint', wraps=m.fingerprint) as fp:
            with self.assertRaisesRegex(RuntimeError, 'PID still exists'):
                self.plan()
            self.assertFalse(any(str(c.args[0]).endswith('.safetensors') for c in fp.call_args_list))

    def test_failed_incomplete_nooracle_and_sequence_refuse(self):
        mutations = [{'all_exact': False}, {'exit_code': 1}, {'references_from': None},
                     {'emission_sequence_ok': False}, {'count': 4}, {'expected_clips': 2}]
        for change in mutations:
            with self.subTest(change=change):
                self.put(self.throughput, {**self.result, **change})
                with self.assertRaises(RuntimeError): self.plan()
        self.assertTrue(self.raw('arm99-02').exists())

    def test_whole_archive_mismatch_refuses_even_passing_parity(self):
        self.raw('arm99-02').write_bytes(b'different archive')
        with self.assertRaisesRegex(RuntimeError, 'whole candidate archive differs'):
            self.plan()

    def test_symlink_and_hardlink_refused(self):
        target = self.raw('arm99-02')
        target.unlink(); target.symlink_to(self.raw('protected-boat'))
        with self.assertRaisesRegex(RuntimeError, 'symlink'):
            self.plan()
        target.unlink(); os.link(self.raw('protected-boat'), target)
        with self.assertRaisesRegex(RuntimeError, 'regular unlinked'):
            self.plan()

    def test_reference_name_and_parity_keys_protected(self):
        bad = copy.deepcopy(self.result)
        bad['rows'][1]['reference'] = 'arm99-00'
        self.put(self.throughput, bad)
        with self.assertRaisesRegex(RuntimeError, 'reference binding'):
            self.plan()
        self.put(self.throughput, self.result)
        p = self.out / 'arm99-01-parity.json'
        value = json.loads(p.read_text()); value['comparisons'] = {}
        self.put(p, value)
        with self.assertRaisesRegex(RuntimeError, 'parity receipt incomplete'):
            self.plan()

    def test_plan_hash_and_bound_evidence_tampering_refused(self):
        path, digest = self.saved_plan()
        with self.assertRaisesRegex(RuntimeError, 'plan hash mismatch'):
            self.apply(path, '0' * 64)
        self.put(self.root / 'requests/arm99-02/result.json', {'prompt_id': 'forged'})
        with self.assertRaisesRegex(RuntimeError, 'request ID binding'):
            self.apply(path, digest)
        self.assertTrue(self.raw('arm99-01').exists())

    def test_candidate_changes_after_plan_refuse(self):
        path, digest = self.saved_plan()
        self.raw('arm99-02').write_bytes(b'changed')
        with self.assertRaises(RuntimeError): self.apply(path, digest)
        self.assertTrue(self.raw('arm99-01').exists())

    def test_reference_rechecked_immediately_before_unlink(self):
        path, digest = self.saved_plan()
        original = m.sync_json
        def mutate_after_intent(p, value):
            original(p, value)
            if str(p).endswith('.intent.json'):
                self.raw('protected-boat').write_bytes(b'changed after full revalidation')
        with mock.patch.object(m, 'sync_json', side_effect=mutate_after_intent):
            with self.assertRaisesRegex(RuntimeError, 'reference changed immediately'):
                self.apply(path, digest)
        self.assertTrue(self.raw('arm99-01').exists())
        self.assertEqual(json.loads((self.out / 'applied.json').read_text())['status'], 'incomplete-no-automatic-retry')

    def test_intent_storage_failure_prevents_all_deletion(self):
        path, digest = self.saved_plan()
        with mock.patch.object(m, 'sync_json', side_effect=OSError('synthetic ENOSPC')):
            with self.assertRaises(OSError): self.apply(path, digest)
        self.assertTrue(self.raw('arm99-01').exists())

    def test_fault_and_nonfinite_and_cached_requests_refused(self):
        (self.root / 'FAULT.json').write_text('{}')
        with self.assertRaisesRegex(RuntimeError, 'fault evidence'):
            self.plan()
        (self.root / 'FAULT.json').unlink()
        p = self.root / 'requests/arm99-01/history.json'
        value = json.loads(p.read_text()); value['status']['messages'] = [['execution_cached', {'nodes': ['414']}]]
        self.put(p, value)
        with self.assertRaisesRegex(RuntimeError, 'cached/failed'):
            self.plan()
        value['status']['messages'] = []; self.put(p, value)
        p = self.raw('arm99-01').parent / 'summary.json'
        value = json.loads(p.read_text()); value['tensors']['images']['finite'] = False; self.put(p, value)
        with self.assertRaisesRegex(RuntimeError, 'nonfinite'):
            self.plan()


if __name__ == '__main__':
    unittest.main(verbosity=2)
