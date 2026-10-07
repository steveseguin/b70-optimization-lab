#!/usr/bin/env python3
"""CPU-only synthetic files; never loads run evidence or touches real artifacts."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('retire103', Path(__file__).with_name('retire103.py'))
M = importlib.util.module_from_spec(spec); spec.loader.exec_module(M)


class RetirementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.top = Path(self.temp.name); self.root = self.top / 'artifacts'; self.root.mkdir()
        self.run = self.root / 'run'; self.run.mkdir()
        self.closeout = self.top / 'closeout'; self.closeout.mkdir()
        self.packet = self.root / 'packet'; self.packet.mkdir()
        for key, value in [('ROOT', self.root), ('RUN', self.run), ('CLOSEOUT', self.closeout), ('PACKET', self.packet)]:
            p = patch.object(M, key, value); p.start(); self.addCleanup(p.stop)
        self.identity = {'pid': 999999999, 'proc_start_ticks': '123', 'boot_id': 'fixture',
                         'source_packet_manifest_sha256': M.MANIFEST_SHA}
        M.exclusive_json(self.run / 'server-identity.json', self.identity)
        p = patch.object(M, 'IDENTITY_SHA', M.fp(self.run / 'server-identity.json')['sha256']); p.start(); self.addCleanup(p.stop)
        M.exclusive_json(self.closeout / 'controlled-reload-stop-intent.json',
            {'schema': 'ltx.controlled-application-reload.v1', 'identity': self.identity, 'signal': 'SIGINT'})
        M.exclusive_json(self.closeout / 'controlled-reload-stopped.json',
            {'schema': 'ltx.controlled-application-reload-stopped.v1', 'pid': self.identity['pid'],
             'gone': True, 'hard_kill': False, 'fault_latched': False})
        self.rows, executions = [], []
        for i in range(44):
            name = M.PREFIX + f'timed-{i:02d}'
            fixture = M.FIXTURES[(i-4) % 10]
            self.rows.append({'phase': 'timed', 'name': name, 'expected_emitted_fixture': fixture,
                              'timing_scope': 'bounded-continuity' if i >= 14 else 'initial'})
            executions.append({'name': name, 'fixture': fixture, 'tensors': {'images': {'sha256': fixture}},
                'prompt_id': f'prompt-{i}', 'emitted_index': i-4, 'parity_status': 'four-tensors-exact'})
            if i >= 4:
                path = M.archive(name); path.parent.mkdir(parents=True)
                path.write_bytes(('archive-' + fixture).encode())
        self.source = {'requests': self.rows}; self.proof = {'executions': executions,
            'evidence_sha256': {str(M.archive(r['name'])): M.fp(M.archive(r['name']))['sha256'] for r in self.rows[4:]}}
        p = patch.object(M, 'reconstruct_proof', side_effect=lambda: (self.source, self.proof, self.identity, {}))
        self.reconstruct = p.start(); self.addCleanup(p.stop)
        self.plan = M.build_plan(); self.plan_path = self.top / 'plan.json'
        M.exclusive_json(self.plan_path, self.plan); self.digest = M.fp(self.plan_path)['sha256']

    def receipt(self, name='apply'):
        return self.top / (name + '.json')

    def operate(self, mode='apply'):
        M.operate(mode, self.plan_path, self.digest, self.receipt(mode))

    def test_exact_thirty_map_and_full_reconstruction_before_apply(self):
        self.assertEqual(len(self.plan['retire']), 30)
        self.assertEqual(len({r['retained']['path'] for r in self.plan['retire']}), 10)
        self.operate()
        self.assertEqual(self.reconstruct.call_count, 2)
        self.assertTrue(all(not Path(r['candidate']['path']).exists() for r in self.plan['retire']))
        self.assertTrue(all(Path(r['retained']['path']).exists() for r in self.plan['retire']))
        result = M.read_json(self.receipt())
        self.assertEqual(result['status'], 'completed')
        events = [json.loads(l) for l in self.receipt().with_name('apply.json.events.jsonl').read_text().splitlines()]
        self.assertEqual([e['phase'] for e in events], ['file-intent', 'file-completed'] * 30)
        self.assertEqual(M.read_json(self.receipt().with_name('apply.json.intent.json'))['plan'], self.plan)

    def test_real_copy_roundtrip_no_hardlinks_no_overwrite(self):
        self.operate()
        with patch.object(M, 'storage_admission', return_value={'admitted': True}):
            self.operate('restore')
        for row in self.plan['retire']:
            actual = M.fp(row['candidate']['path']); keep = M.fp(row['retained']['path'])
            self.assertEqual(actual['sha256'], row['candidate']['sha256'])
            self.assertEqual(actual['st_nlink'], 1)
            self.assertNotEqual(actual['st_ino'], keep['st_ino'])
        self.assertIn('revalidation remains required', M.read_json(self.receipt('restore'))['proof_status'])
        with self.assertRaisesRegex(RuntimeError, 'already exists'):
            M.operate('restore', self.plan_path, self.digest, self.receipt('again'))
        self.assertFalse(self.receipt('again').exists())

    def test_whole_file_difference_refuses_even_if_tensor_receipt_equal(self):
        Path(self.plan['retire'][0]['candidate']['path']).write_bytes(b'changed archive header')
        with self.assertRaisesRegex(RuntimeError, 'archive differs'):
            self.operate()
        self.assertFalse(self.receipt().exists())
        self.assertTrue(all(Path(r['candidate']['path']).exists() for r in self.plan['retire']))

    def test_proof_hash_binding_refuses_equal_postproof_replacement(self):
        row = self.plan['retire'][0]
        for kind in ('candidate', 'retained'):
            Path(row[kind]['path']).write_bytes(b'same new bytes, wrong proof')
        with self.assertRaisesRegex(RuntimeError, 'reconstructed proof'):
            self.operate()
        self.assertFalse(self.receipt().exists())

    def test_nlink_and_symlink_refused(self):
        path = Path(self.plan['retire'][0]['candidate']['path'])
        alias = self.top / 'alias'; os.link(path, alias)
        with self.assertRaisesRegex(RuntimeError, 'nlink1'):
            self.operate()
        alias.unlink(); alias.symlink_to(path)
        with self.assertRaisesRegex(RuntimeError, 'symlink'):
            M.fp(alias)

    def test_nonregular_file_refused_without_blocking(self):
        path = self.top / 'pipe'; os.mkfifo(path)
        with self.assertRaisesRegex(RuntimeError, 'regular'):
            M.fp(path)

    def test_changed_stat_even_same_bytes_refused(self):
        path = Path(self.plan['retire'][0]['candidate']['path'])
        data = path.read_bytes(); path.unlink(); path.write_bytes(data)
        with self.assertRaisesRegex(RuntimeError, 'plan changed'):
            self.operate()
        self.assertFalse(self.receipt().exists())

    def test_live_pid_or_wrong_stop_identity_refused_before_output(self):
        with patch.object(M.Path, 'exists', autospec=True, side_effect=lambda p: True if str(p) == '/proc/999999999' else os.path.exists(p)):
            with self.assertRaisesRegex(RuntimeError, 'PID still exists'):
                self.operate()
        self.assertFalse(self.receipt().exists())
        stop = self.closeout / 'controlled-reload-stopped.json'
        value = M.read_json(stop); value['pid'] += 1; stop.write_bytes(M.canonical(value))
        with self.assertRaisesRegex(RuntimeError, 'unclean stop'):
            self.operate()

    def test_fault_refused(self):
        (self.run / 'resolution-halt.json').write_text('{}')
        with self.assertRaisesRegex(RuntimeError, 'fault/halt'):
            self.operate()
        self.assertFalse(self.receipt().exists())

    def test_digest_mapping_and_fixture_refused(self):
        with self.assertRaisesRegex(RuntimeError, 'plan SHA'):
            M.operate('apply', self.plan_path, '0'*64, self.receipt())
        changed = copy.deepcopy(self.plan)
        changed['retire'][0]['restore']['destination'] = str(self.top / 'unrelated')
        self.plan_path.write_bytes(M.canonical(changed))
        with self.assertRaisesRegex(RuntimeError, 'restore mapping'):
            M.checked_plan(self.plan_path, M.fp(self.plan_path)['sha256'])
        self.rows[14]['expected_emitted_fixture'] = 'marble'
        with self.assertRaisesRegex(RuntimeError, 'continuity fixture'):
            M.build_plan()

    def test_partial_unlink_failure_has_intent_and_receipt_no_retry(self):
        original = M.unlink_exact
        calls = []
        def fail_second(record):
            calls.append(record)
            if len(calls) == 2:
                raise OSError('synthetic refusal')
            return original(record)
        with patch.object(M, 'unlink_exact', side_effect=fail_second):
            with self.assertRaisesRegex(OSError, 'synthetic refusal'):
                self.operate()
        result = M.read_json(self.receipt())
        self.assertEqual(result['status'], 'incomplete-no-automatic-retry')
        self.assertEqual(len(result['completed']), 1)
        self.assertTrue(Path(self.plan['retire'][1]['candidate']['path']).exists())
        events = self.receipt().with_name('apply.json.events.jsonl').read_text().splitlines()
        self.assertEqual(len(events), 3)

    def test_restore_space_refusal_and_existing_destination_no_writes(self):
        self.operate()
        with patch.object(M, 'storage_admission', side_effect=RuntimeError('space refused')):
            with self.assertRaisesRegex(RuntimeError, 'space refused'):
                self.operate('restore')
        self.assertFalse(self.receipt('restore').exists())
        self.assertFalse(self.receipt('restore').with_name('restore.json.intent.json').exists())
        path = Path(self.plan['retire'][0]['candidate']['path']); path.write_bytes(b'keep me')
        with self.assertRaisesRegex(RuntimeError, 'destination already exists'):
            self.operate('restore')
        self.assertEqual(path.read_bytes(), b'keep me')

    def test_partial_restore_preserved_no_silent_cleanup(self):
        self.operate()
        def partial(row):
            Path(row['candidate']['path']).write_bytes(b'partial')
            raise OSError('synthetic write failure')
        with patch.object(M, 'storage_admission', return_value={'admitted': True}), patch.object(M, 'restore_one', side_effect=partial):
            with self.assertRaisesRegex(OSError, 'write failure'):
                self.operate('restore')
        self.assertEqual(Path(self.plan['retire'][0]['candidate']['path']).read_bytes(), b'partial')
        self.assertEqual(M.read_json(self.receipt('restore'))['status'], 'incomplete-no-automatic-retry')

    def test_immediate_recheck_blocks_replaced_file(self):
        row = self.plan['retire'][0]
        Path(row['candidate']['path']).write_bytes(b'replaced')
        with self.assertRaisesRegex(RuntimeError, 'candidate changed'):
            M.unlink_exact(row['candidate'])
        self.assertTrue(Path(row['candidate']['path']).exists())

    def test_changed_verifier_refused_before_import(self):
        components = self.packet / 'resolution/components'; components.mkdir(parents=True)
        for name in ('candidate_gate.py', 'reference_gate.py'):
            (components / name).write_text('raise AssertionError("must not import")\n')
        manifest = {'files': {'resolution/components/' + name: '0'*64 for name in ('candidate_gate.py', 'reference_gate.py')}}
        M.exclusive_json(self.packet / 'manifest.json', manifest)
        with patch.object(M, 'MANIFEST_SHA', M.fp(self.packet / 'manifest.json')['sha256']):
            # The only proof mock is bypassed for the actual source-pinning control.
            actual_module = importlib.util.module_from_spec(spec); spec.loader.exec_module(actual_module)
            with patch.object(actual_module, 'PACKET', self.packet), patch.object(actual_module, 'MANIFEST_SHA', M.MANIFEST_SHA):
                with self.assertRaisesRegex(RuntimeError, 'sealed verifier changed'):
                    actual_module.reconstruct_proof()

    def test_fsync_and_exclusive_control_files(self):
        with patch.object(M.os, 'fsync', wraps=os.fsync) as fsync:
            M.exclusive_json(self.top / 'durable.json', {'test': True})
            self.assertGreaterEqual(fsync.call_count, 2)
        with self.assertRaises(FileExistsError):
            M.exclusive_json(self.top / 'durable.json', {'overwritten': True})


if __name__ == '__main__':
    unittest.main()
