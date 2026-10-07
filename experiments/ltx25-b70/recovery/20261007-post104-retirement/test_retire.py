#!/usr/bin/env python3
"""Synthetic52-file controls only; no actual run proof, endpoint or device access."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('post104_retire', Path(__file__).with_name('retire.py'))
M = importlib.util.module_from_spec(spec); spec.loader.exec_module(M)


class Controls(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory(); self.addCleanup(t.cleanup); self.top = Path(t.name)
        self.root = self.top / 'artifacts'; self.root.mkdir(); self.data = self.top / 'data'; self.data.mkdir()
        for key, value in [('ROOT', self.root), ('DATA', self.data), ('RUNS', copy.deepcopy(M.RUNS))]:
            p = patch.object(M, key, value); p.start(); self.addCleanup(p.stop)
        self.identities, self.proofs = {}, {}
        for num, (lane, cfg) in enumerate(M.RUNS.items()):
            run = self.root / cfg['run']; run.mkdir(); closeout = self.data / cfg['closeout']; closeout.mkdir()
            identity = {'pid': 900000000+num, 'proc_start_ticks': '123', 'boot_id': 'synthetic',
                        'source_packet_manifest_sha256': cfg['manifest']}
            M.exclusive_json(run / 'server-identity.json', identity)
            cfg['identity'] = M.fp(run / 'server-identity.json')['sha256']; self.identities[lane] = identity
            old = lane == '101c'
            M.exclusive_json(closeout / ('resolution-stop-intent.json' if old else 'controlled-reload-stop-intent.json'),
                {'schema': 'ltx.resolution-graceful-stop.v1' if old else 'ltx.controlled-application-reload.v1',
                 'identity': identity, 'signal': 'SIGINT', 'time_unix': 1})
            M.exclusive_json(closeout / ('resolution-stopped.json' if old else 'controlled-reload-stopped.json'),
                {'schema': 'ltx.controlled-application-reload-stopped.v1', 'gone_unix': 2, 'pid': identity['pid'],
                 'hard_kill': False, 'gone': True, 'fault_latched': False})
            self.proofs[lane] = {'executions': {}, 'raw_hashes': {}, 'evidence': {}}
        for lane, candidate, keeper, fixture in M.selection():
            for name in (candidate, keeper):
                path = M.archive(name)
                if not path.exists():
                    path.parent.mkdir(parents=True); path.write_bytes(('whole-archive-' + fixture).encode())
                self.proofs[lane]['raw_hashes'][str(path)] = M.fp(path)['sha256']
                self.proofs[lane]['executions'][name] = {'name': name, 'fixture': fixture, 'prompt_id': name,
                    'tensors': {k: {'sha256': fixture, 'dtype': 'torch.float32', 'shape': [1]}
                                for k in ('images', 'video_latent', 'audio_latent', 'waveform')}}
        p = patch.object(M, 'reconstruct_lane', side_effect=lambda lane: self.proofs[lane])
        self.reconstruction = p.start(); self.addCleanup(p.stop)
        self.plan = M.build_plan(); self.plan_path = self.top / 'plan.json'
        M.exclusive_json(self.plan_path, self.plan); self.digest = M.fp(self.plan_path)['sha256']

    def result(self, mode='apply'):
        return self.top / (mode + '.json')

    def operate(self, mode='apply'):
        return M.operate(mode, self.plan_path, self.digest, self.result(mode))

    def test_fixed_scope_and_real_roundtrip(self):
        rows = self.plan['retire']; self.assertEqual(len(rows), 52)
        self.assertEqual([sum(r['lane'] == k for r in rows) for k in M.RUNS], [16, 16, 20])
        self.assertEqual(len({r['retained']['path'] for r in rows}), 16)
        self.assertFalse(any('resolution-full-' in r['candidate']['path'] for r in rows))
        self.assertFalse(any('native-' in r['candidate']['path'] for r in rows if r['lane'] == '104'))
        self.operate(); self.assertEqual(self.reconstruction.call_count, 6)
        self.assertEqual(M.read_json(self.result())['status'], 'completed')
        self.assertTrue(all(not Path(r['candidate']['path']).exists() for r in rows))
        self.assertTrue(all(M.fp(r['retained']['path']) == r['retained'] for r in rows))
        events = [json.loads(v) for v in self.result().with_name('apply.json.events.jsonl').read_text().splitlines()]
        self.assertEqual([r['phase'] for r in events], ['file-intent', 'file-completed'] * 52)
        with patch.object(M, 'storage_admission', return_value={'admitted': True}):
            self.operate('restore')
        for row in rows:
            a, b = M.fp(row['candidate']['path']), M.fp(row['retained']['path'])
            self.assertEqual(a['sha256'], b['sha256']); self.assertEqual(a['st_nlink'], 1)
            self.assertNotEqual(a['st_ino'], b['st_ino'])
        self.assertIn('revalidation still required', M.read_json(self.result('restore'))['proof_status'])

    def test_reject_one_live_lane_before_any_proof_or_output(self):
        with patch.object(M.Path, 'exists', autospec=True, side_effect=lambda p:
                          True if str(p) == '/proc/900000002' else os.path.exists(p)):
            self.reconstruction.reset_mock()
            with self.assertRaisesRegex(RuntimeError, 'PID still exists: 104'):
                M.build_plan()
            self.reconstruction.assert_not_called()
            with self.assertRaisesRegex(RuntimeError, 'PID still exists'):
                self.operate()
        self.assertFalse(self.result().exists())

    def test_actual_stop_schemas_reject_bad_old_timestamp_and_new_identity(self):
        lane = M.RUNS['101c']; path = self.data / lane['closeout'] / 'resolution-stopped.json'
        value = M.read_json(path); value['gone_unix'] = 0; path.write_bytes(M.canonical(value))
        with self.assertRaisesRegex(RuntimeError, '101c stop timestamps'):
            M.build_plan()
        value['gone_unix'] = 2; path.write_bytes(M.canonical(value))
        path = self.data / M.RUNS['104']['closeout'] / 'controlled-reload-stop-intent.json'
        value = M.read_json(path); value['identity']['pid'] += 1; path.write_bytes(M.canonical(value))
        with self.assertRaisesRegex(RuntimeError, 'stop intent differs'):
            M.build_plan()

    def test_failure_in_any_lane_prevents_all_unlinks(self):
        def fail_last(lane):
            if lane == '104':
                raise RuntimeError('sealed fast proof mismatch')
            return self.proofs[lane]
        self.reconstruction.side_effect = fail_last
        with self.assertRaisesRegex(RuntimeError, 'sealed fast proof'):
            self.operate()
        self.assertTrue(all(Path(r['candidate']['path']).exists() for r in self.plan['retire']))
        self.assertFalse(self.result().with_name('apply.json.intent.json').exists())

    def test_raw_hash_and_whole_file_checks(self):
        row = self.plan['retire'][0]
        Path(row['candidate']['path']).write_bytes(b'wrong full archive despite same tensors')
        with self.assertRaisesRegex(RuntimeError, 'archive differs from full proof'):
            self.operate()
        for kind in ('candidate', 'retained'):
            Path(row[kind]['path']).write_bytes(b'identical replacement wrong proof')
        with self.assertRaisesRegex(RuntimeError, 'archive differs from full proof'):
            M.build_plan()

    def test_missing_last_archive_refuses_before_first_intent(self):
        Path(self.plan['retire'][-1]['candidate']['path']).unlink()
        with self.assertRaisesRegex(RuntimeError, 'missing path'):
            self.operate()
        self.assertFalse(self.result().with_name('apply.json.intent.json').exists())
        self.assertTrue(Path(self.plan['retire'][0]['candidate']['path']).exists())

    def test_tensor_metadata_mismatch_refuses_even_if_archives_equal(self):
        lane, name, _, _ = M.selection()[0]
        self.proofs[lane]['executions'][name]['tensors']['images']['sha256'] = 'wrong-tensor'
        with self.assertRaisesRegex(RuntimeError, 'execution differs'):
            self.operate()
        self.assertFalse(self.result().with_name('apply.json.intent.json').exists())

    def test_hardlinks_symlinks_and_inode_drift_refused(self):
        row = self.plan['retire'][0]; path = Path(row['candidate']['path']); alias = self.top / 'alias'
        os.link(path, alias)
        with self.assertRaisesRegex(RuntimeError, 'nlink1'):
            self.operate()
        alias.unlink(); alias.symlink_to(path)
        with self.assertRaisesRegex(RuntimeError, 'symlink'):
            M.fp(alias)
        data = path.read_bytes(); path.unlink(); path.write_bytes(data)
        with self.assertRaisesRegex(RuntimeError, 'exact plan changed'):
            self.operate()

    def test_unknown_path_and_false_digest_refused(self):
        with self.assertRaisesRegex(RuntimeError, 'plan SHA'):
            M.operate('apply', self.plan_path, '0'*64, self.result())
        plan = copy.deepcopy(self.plan); plan['retire'][0]['candidate']['path'] = str(self.top / 'unrelated')
        self.plan_path.write_bytes(M.canonical(plan))
        with self.assertRaisesRegex(RuntimeError, 'restoration mapping'):
            M.checked_plan(self.plan_path, M.fp(self.plan_path)['sha256'])
        plan = copy.deepcopy(self.plan); plan['retire'][0]['retained']['path'] = plan['retire'][1]['retained']['path']
        self.plan_path.write_bytes(M.canonical(plan))
        with self.assertRaisesRegex(RuntimeError, 'restoration mapping'):
            M.checked_plan(self.plan_path, M.fp(self.plan_path)['sha256'])

    def test_new_fault_and_retained_mutation_refuse(self):
        fault = self.root / M.RUNS['102']['run'] / 'FAULT.json'; fault.write_text('{}')
        with self.assertRaisesRegex(RuntimeError, 'fault'):
            self.operate()
        fault.unlink()
        Path(self.plan['retire'][0]['retained']['path']).write_bytes(b'changed')
        with self.assertRaisesRegex(RuntimeError, 'archive differs'):
            self.operate()

    def test_partial_unlink_keeps_map_and_prefix_receipt(self):
        calls = []; original = M.unlink_exact
        def fail_second(record):
            calls.append(record)
            if len(calls) == 2:
                raise OSError('synthetic I/O failure')
            original(record)
        with patch.object(M, 'unlink_exact', side_effect=fail_second):
            with self.assertRaises(OSError):
                self.operate()
        result = M.read_json(self.result()); self.assertEqual(result['status'], 'incomplete-no-automatic-retry')
        self.assertEqual(len(result['completed']), 1)
        intent = M.read_json(self.result().with_name('apply.json.intent.json'))
        self.assertEqual(intent['plan'], self.plan)
        self.assertEqual(len(self.result().with_name('apply.json.events.jsonl').read_text().splitlines()), 3)

    def test_restore_space_and_overwrite_refused(self):
        self.operate()
        with patch.object(M, 'storage_admission', side_effect=RuntimeError('space refused')):
            with self.assertRaisesRegex(RuntimeError, 'space refused'):
                self.operate('restore')
        self.assertFalse(self.result('restore').with_name('restore.json.intent.json').exists())
        path = Path(self.plan['retire'][0]['candidate']['path']); path.write_bytes(b'preserve')
        with self.assertRaisesRegex(RuntimeError, 'destination exists'):
            self.operate('restore')
        self.assertEqual(path.read_bytes(), b'preserve')

    def test_partial_restore_is_not_cleaned_up_or_retried(self):
        self.operate()
        def partial(row):
            Path(row['candidate']['path']).write_bytes(b'partial'); raise OSError('copy failure')
        with patch.object(M, 'storage_admission', return_value={'admitted': True}), patch.object(M, 'restore_one', side_effect=partial):
            with self.assertRaisesRegex(OSError, 'copy failure'):
                self.operate('restore')
        self.assertEqual(Path(self.plan['retire'][0]['candidate']['path']).read_bytes(), b'partial')
        self.assertEqual(M.read_json(self.result('restore'))['status'], 'incomplete-no-automatic-retry')

    def test_storage_budget_uses_actual_destination_and50gib_floor(self):
        def inspect(path, floor, writes):
            self.assertEqual(path, self.root / 'output/validation'); self.assertEqual(floor, 50*1024**3)
            self.assertEqual(writes, 52*4096 + 16*1024**2)
            return {'admitted': False}
        with patch.object(M, 'load', return_value=types.SimpleNamespace(inspect_destination=inspect)):
            with self.assertRaisesRegex(RuntimeError, 'admission refused'):
                M.storage_admission(self.plan['retire'])

    def test_unchanged_gate_dispatch_and_summary_schema_for_each_lane(self):
        # Real reconstruction wrapper, synthetic sealed modules/receipts; the
        # gate itself is not replaced in operations and is pinned before import.
        real = importlib.util.module_from_spec(spec); spec.loader.exec_module(real)
        for lane, cfg in M.RUNS.items():
            packet = self.root / cfg['packet']; components = packet / 'resolution/components'; components.mkdir(parents=True)
            source = {'plan': {}}; source['plan_sha256'] = hashlib.sha256(M.canonical(source['plan'])).hexdigest()
            M.exclusive_json(packet / 'resolution/candidate-plan.json', source); cfg['plan'] = source['plan_sha256']
            files = {}
            for name in ('reference_gate.py', 'candidate_gate.py'):
                path = components / name; path.write_text('# fixture pinned gate\n'); files['resolution/components/'+name] = M.fp(path)['sha256']
            M.exclusive_json(packet / 'manifest.json', {'files': files}); cfg['manifest'] = M.fp(packet / 'manifest.json')['sha256']
            run = self.root / cfg['run']; count = 10 if lane == '104' else 3
            native = {'status': 'reference_verified', 'executions': [{'name': 'native'+str(i)} for i in range(2*count)],
                      'four_tensor_repeat_pairs_exact': count, 'evidence_sha256': {}}
            candidate = {'four_tensor_exact_clips': count, 'executions': [], 'evidence_sha256': {}}
            timed = {'four_tensor_exact_clips': 10, 'executions': [], 'evidence_sha256': {},
                     'runtime_manifest_sha256': cfg['manifest'], 'server_identity_sha256': cfg['identity']}
            docs = {'same-size-native-references.json': native, 'same-size-candidate-check.json': candidate, 'same-size-timed.json': timed}
            if lane == '104': docs['same-size-timed-fast.json'] = dict(timed, marker='fast fixture')
            campaign = {'passed': True, 'requests': [str(i) for i in range(cfg['requests'])],
                        'timed_receipt': str(run / 'same-size-timed.json'), 'fast_timed_receipt': str(run / 'same-size-timed-fast.json')}
            docs['resolution-campaign-result.json'] = campaign
            for name, doc in docs.items(): M.exclusive_json(run / name, doc)
            summary = {'schema': cfg['summary_schema'], 'fault_latched': False, 'native_executions': count*2,
                'candidate_exact_clips': count, 'packet_manifest_sha256': cfg['manifest'], 'runtime_manifest_sha256': cfg['manifest'],
                'run': str(run), 'control_exact_clips': 10, 'fast_exact_clips': 10, 'timed_exact_clips': 10,
                'files': {str(run / name): {'sha256': M.fp(run / name)['sha256']} for name in docs}}
            M.exclusive_json(self.data / cfg['closeout'] / 'summary.json', summary)
            calls = []
            def verify(*args):
                calls.append(args)
                return docs['same-size-timed-fast.json' if lane == '104' else 'same-size-timed.json']
            with patch.object(real, 'ROOT', self.root), patch.object(real, 'DATA', self.data), patch.object(real, 'RUNS', M.RUNS), patch.object(real, 'load', return_value=types.SimpleNamespace(_verify=verify)):
                real.reconstruct_lane(lane)
                self.assertEqual(len(calls), 1); self.assertEqual(calls[0][4], 'timed-fast' if lane == '104' else 'timed')
                self.assertEqual(len(calls[0]), 9 if lane == '104' else 7)
                if lane == '104':
                    self.assertEqual(calls[0][7], run / 'same-size-timed.json')
                    self.assertEqual(calls[0][8], M.fp(run / 'same-size-timed.json')['sha256'])
                summary_path = self.data / cfg['closeout'] / 'summary.json'
                original_summary = summary_path.read_bytes()
                changed = copy.deepcopy(summary)
                changed['files'][str(run / 'same-size-native-references.json')]['sha256'] = '0'*64
                summary_path.write_bytes(M.canonical(changed))
                with self.assertRaisesRegex(RuntimeError, 'closeout evidence binding'):
                    real.reconstruct_lane(lane)
                summary_path.write_bytes(original_summary)
                (components / 'candidate_gate.py').write_text('# changed source\n')
                with self.assertRaisesRegex(RuntimeError, 'verifier source differs'):
                    real.reconstruct_lane(lane)


if __name__ == '__main__':
    unittest.main()
