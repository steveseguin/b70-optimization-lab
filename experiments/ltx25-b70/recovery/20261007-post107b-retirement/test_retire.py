#!/usr/bin/env python3
"""Synthetic40-file controls only; no actual run proof, endpoint or device access."""
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

spec = importlib.util.spec_from_file_location('post107b_retire', Path(__file__).with_name('retire.py'))
M = importlib.util.module_from_spec(spec); spec.loader.exec_module(M)


class Controls(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory(); self.addCleanup(t.cleanup); self.top = Path(t.name)
        self.root = self.top / 'artifacts'; self.root.mkdir(); self.data = self.top / 'data'; self.data.mkdir()
        for key, value in [('ROOT', self.root), ('DATA', self.data), ('RUNS', copy.deepcopy(M.RUNS))]:
            p = patch.object(M, key, value); p.start(); self.addCleanup(p.stop)
        p = patch.object(M, 'process_exists', return_value=False); p.start(); self.addCleanup(p.stop)
        self.identities, self.proofs = {}, {}
        for num, (lane, cfg) in enumerate(M.RUNS.items()):
            run = self.root / cfg['run']; run.mkdir(); closeout = self.data / cfg['closeout']; closeout.mkdir()
            identity = {'pid': cfg['pid'], 'proc_start_ticks': cfg['start_ticks'], 'boot_id': cfg['boot_id'],
                        'source_packet_manifest_sha256': cfg['manifest']}
            M.exclusive_json(run / 'server-identity.json', identity)
            cfg['identity'] = M.fp(run / 'server-identity.json')['sha256']; self.identities[lane] = identity
            old = False
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
        self.basis = {'keepers': {keeper: {'record': M.fp(M.archive(keeper)),
            'execution': copy.deepcopy(self.proofs[lane]['executions'][keeper])}
            for lane, _, keeper, _ in M.selection()}, 'evidence': {}}
        p = patch.object(M, 'keeper_basis', side_effect=lambda: self.basis)
        self.keeper_mock = p.start(); self.addCleanup(p.stop)
        self.plan = M.build_plan(); self.plan_path = self.top / 'plan.json'
        M.exclusive_json(self.plan_path, self.plan); self.digest = M.fp(self.plan_path)['sha256']

    def result(self, mode='apply'):
        return self.top / (mode + '.json')

    def operate(self, mode='apply'):
        return M.operate(mode, self.plan_path, self.digest, self.result(mode))

    def test_fixed_scope_and_real_roundtrip(self):
        rows = self.plan['retire']; self.assertEqual(len(rows), 40)
        self.assertEqual([sum(r['lane'] == k for r in rows) for k in M.RUNS], [40])
        self.assertEqual(len({r['retained']['path'] for r in rows}), 10)
        self.assertFalse(any('resolution-full-' in r['candidate']['path'] for r in rows))
        self.assertFalse({r['candidate']['path'] for r in rows}.intersection(M.protected_anchors()))
        self.assertEqual(len(M.protected_anchors()), 36)
        self.operate(); self.assertEqual(self.reconstruction.call_count, 2)
        self.assertEqual(M.read_json(self.result())['status'], 'completed')
        self.assertTrue(all(not Path(r['candidate']['path']).exists() for r in rows))
        self.assertTrue(all(M.fp(r['retained']['path']) == r['retained'] for r in rows))
        events = [json.loads(v) for v in self.result().with_name('apply.json.events.jsonl').read_text().splitlines()]
        self.assertEqual([r['phase'] for r in events], ['file-intent', 'file-completed'] * 40)
        with patch.object(M, 'storage_admission', return_value={'admitted': True}):
            self.operate('restore')
        for row in rows:
            a, b = M.fp(row['candidate']['path']), M.fp(row['retained']['path'])
            self.assertEqual(a['sha256'], b['sha256']); self.assertEqual(a['st_nlink'], 1)
            self.assertNotEqual(a['st_ino'], b['st_ino'])
        self.assertIn('revalidation still required', M.read_json(self.result('restore'))['proof_status'])

    def test_live107b_refuses_before_any_proof_or_output(self):
        with patch.object(M, 'process_exists', return_value=True) as exists:
            self.reconstruction.reset_mock()
            with self.assertRaisesRegex(RuntimeError, 'PID still exists:107b'):
                M.build_plan()
            self.reconstruction.assert_not_called()
            exists.assert_called_with(3362949)
            with self.assertRaisesRegex(RuntimeError, 'PID still exists'):
                self.operate()
        self.assertFalse(self.result().exists())

    def test_exact_pid_start_boot_and_controlled_stop_required(self):
        cfg = M.RUNS['107b']; path = self.root / cfg['run'] / 'server-identity.json'
        original = path.read_bytes()
        for key, value in [('pid', 3362950), ('proc_start_ticks', 'wrong'), ('boot_id', 'other-boot')]:
            identity = json.loads(original); identity[key] = value; path.write_bytes(M.canonical(identity))
            cfg['identity'] = M.fp(path)['sha256']
            with self.assertRaisesRegex(RuntimeError, 'PID/start/boot differs'):
                M.build_plan()
        path.write_bytes(original); cfg['identity'] = M.fp(path)['sha256']
        stop = self.data / cfg['closeout'] / 'controlled-reload-stopped.json'
        value = M.read_json(stop); value['hard_kill'] = True; stop.write_bytes(M.canonical(value))
        with self.assertRaisesRegex(RuntimeError, 'unclean controlled stop'):
            M.build_plan()

    def test_failure_in_any_lane_prevents_all_unlinks(self):
        def fail_last(lane):
            if lane == '107b':
                raise RuntimeError('sealed final control proof mismatch')
            return self.proofs[lane]
        self.reconstruction.side_effect = fail_last
        with self.assertRaisesRegex(RuntimeError, 'sealed final control proof'):
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
        fault = self.root / M.RUNS['107b']['run'] / 'FAULT.json'; fault.write_text('{}')
        with self.assertRaisesRegex(RuntimeError, 'fault'):
            self.operate()
        fault.unlink()
        Path(self.plan['retire'][0]['retained']['path']).write_bytes(b'changed')
        with self.assertRaisesRegex(RuntimeError, 'keeper changed'):
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
            self.assertEqual(writes, 40*4096 + 16*1024**2)
            return {'admitted': False}
        with patch.object(M, 'load', return_value=types.SimpleNamespace(inspect_destination=inspect)):
            with self.assertRaisesRegex(RuntimeError, 'admission refused'):
                M.storage_admission(self.plan['retire'])

    def test_unchanged107b_fast_dispatch_and_source_summary_pins(self):
        # Exercise real wrapper with pinned synthetic sources and a fake proof
        # body. This performs no actual run reads, hashes or process inspection.
        real = importlib.util.module_from_spec(spec); spec.loader.exec_module(real)
        cfg = M.RUNS['107b']; packet = self.root / cfg['packet']; components = packet / 'resolution/components'
        components.mkdir(parents=True)
        source = {'plan': {}}; source['plan_sha256'] = hashlib.sha256(M.canonical(source['plan'])).hexdigest()
        M.exclusive_json(packet / 'resolution/candidate-plan.json', source); cfg['plan'] = source['plan_sha256']
        files = {}
        for name in ('reference_gate.py', 'candidate_gate.py'):
            path = components / name; path.write_text('# fixture pinned gate\n'); files['resolution/components/'+name] = M.fp(path)['sha256']
        cfg['candidate_gate_sha256'] = files['resolution/components/candidate_gate.py']
        M.exclusive_json(packet / 'manifest.json', {'files': files}); cfg['manifest'] = M.fp(packet / 'manifest.json')['sha256']
        run = self.root / cfg['run']
        native = {'status': 'reference_verified', 'executions': [{'name': 'native'+str(i)} for i in range(20)],
                  'four_tensor_repeat_pairs_exact': 10, 'evidence_sha256': {}}
        candidate = {'four_tensor_exact_clips': 10, 'executions': [], 'evidence_sha256': {}}
        common = {'four_tensor_exact_clips': 10, 'executions': [], 'evidence_sha256': {},
                  'runtime_manifest_sha256': cfg['manifest'], 'server_identity_sha256': cfg['identity']}
        fast = dict(common, status='timed_fast_verified')
        docs = {'same-size-native-references.json': native, 'same-size-candidate-check.json': candidate,
                'same-size-timed-fast.json': fast}
        docs['resolution-campaign-result.json'] = {'passed': True, 'requests': [str(i) for i in range(57)],
                'fast_timed_receipt': str(run / 'same-size-timed-fast.json')}
        for name, doc in docs.items(): M.exclusive_json(run / name, doc)
        cfg['final_fast_receipt_sha256'] = M.fp(run / 'same-size-timed-fast.json')['sha256']
        summary = {'schema': cfg['summary_schema'], 'fault_latched': False, 'native_executions': 20,
            'candidate_exact_clips': 10, 'runtime_manifest_sha256': cfg['manifest'], 'run': str(run),
            'requests_completed': 57, 'full_proof_rebuilt': True, 'fast_exact_clips': 10,
            'files': {str(run / name): {'sha256': M.fp(run / name)['sha256']} for name in docs}}
        summary_path = self.data / cfg['closeout'] / 'summary.json'; M.exclusive_json(summary_path, summary)
        cfg['closeout_sha256'] = M.fp(summary_path)['sha256']
        proof_path = self.data / 'sparse107b-post-completion-proof.json'
        postproof = {'schema': 'ltx.sparse107b.post-completion-proof.v1', 'passed': True,
            'runtime_manifest_sha256': cfg['manifest'],
            'verifier': str(components / 'candidate_gate.py'), 'verifier_sha256': cfg['candidate_gate_sha256'],
            'fast_receipt_sha256': cfg['final_fast_receipt_sha256']}
        M.exclusive_json(proof_path, postproof); cfg['postproof_sha256'] = M.fp(proof_path)['sha256']
        calls = []
        def verify(*args):
            calls.append(args)
            return fast
        with patch.object(real, 'ROOT', self.root), patch.object(real, 'DATA', self.data), patch.object(real, 'RUNS', M.RUNS), patch.object(real, 'load', return_value=types.SimpleNamespace(verify_fast_receipt=verify)):
            real.reconstruct_lane('107b')
            self.assertEqual(calls, [(run / 'same-size-timed-fast.json', cfg['final_fast_receipt_sha256'])])
            original_summary = summary_path.read_bytes(); changed = copy.deepcopy(summary)
            changed['files'][str(run / 'same-size-native-references.json')]['sha256'] = '0'*64
            summary_path.write_bytes(M.canonical(changed))
            with self.assertRaisesRegex(RuntimeError, 'banked closeout/proof digest'):
                real.reconstruct_lane('107b')
            with patch.dict(cfg, {'closeout_sha256': M.fp(summary_path)['sha256']}):
                with self.assertRaisesRegex(RuntimeError, 'closeout evidence binding'):
                    real.reconstruct_lane('107b')
            summary_path.write_bytes(original_summary)
            original_proof = proof_path.read_bytes(); postproof['passed'] = False
            proof_path.write_bytes(M.canonical(postproof))
            with self.assertRaisesRegex(RuntimeError, 'banked closeout/proof digest'):
                real.reconstruct_lane('107b')
            with patch.dict(cfg, {'postproof_sha256': M.fp(proof_path)['sha256']}):
                with self.assertRaisesRegex(RuntimeError, 'banked proof binding'):
                    real.reconstruct_lane('107b')
            proof_path.write_bytes(original_proof)
            with patch.dict(cfg, {'final_fast_receipt_sha256': '0'*64}):
                with self.assertRaisesRegex(RuntimeError, 'known final fast receipt'):
                    real.reconstruct_lane('107b')
            with patch.dict(cfg, {'candidate_gate_sha256': '0'*64}):
                with self.assertRaisesRegex(RuntimeError, 'exact107b gate source'):
                    real.reconstruct_lane('107b')
            (components / 'candidate_gate.py').write_text('# changed source\n')
            with self.assertRaisesRegex(RuntimeError, 'verifier source differs'):
                real.reconstruct_lane('107b')

    def test_real_keeper_basis_pins_completion_and_no_retired_input_reads(self):
        real = importlib.util.module_from_spec(spec); spec.loader.exec_module(real)
        # Only ten keeper files exist in this provenance fixture; historical
        # candidate paths deliberately do not exist and must never be opened.
        prior_rows = []
        for phase in ('native-p2', 'candidate-check', 'timed-fast', 'timed'):
            for i, fixture in enumerate(M.FIXTURES):
                keeper = M.KEEPER_PREFIX + 'native-p1-' + fixture
                name = M.KEEPER_PREFIX + (phase + '-' + fixture if phase == 'native-p2' else f'{phase}-{i+4:02d}')
                entry = self.basis['keepers'][keeper]
                prior_rows.append({'fixture': fixture, 'candidate': {'path': str(M.archive(name))},
                    'retained': entry['record'], 'retained_execution': entry['execution']})
        prior = {'schema': 'ltx.post105.fixed-duplicate-retirement.v1', 'retire': prior_rows}
        pp = self.data / 'post105-retirement-plan.json'; rp = self.data / 'post105-retirement-receipt.json'
        M.exclusive_json(pp, prior)
        receipt = {'schema': prior['schema'], 'mode': 'apply', 'status': 'completed', 'error': None,
            'plan_sha256': M.fp(pp)['sha256'], 'completed': [r['candidate']['path'] for r in prior_rows]}
        M.exclusive_json(rp, receipt)
        with patch.object(real, 'ROOT', self.root), patch.object(real, 'DATA', self.data), \
             patch.object(real, 'KEEPER_PLAN_SHA', M.fp(pp)['sha256']), \
             patch.object(real, 'KEEPER_RECEIPT_SHA', M.fp(rp)['sha256']):
            result = real.keeper_basis()
            self.assertEqual(result['keepers'], self.basis['keepers'])
            self.assertFalse(any(Path(r['candidate']['path']).exists() for r in prior_rows))
            original = rp.read_bytes(); receipt['status'] = 'incomplete-no-automatic-retry'
            rp.write_bytes(M.canonical(receipt))
            with self.assertRaisesRegex(RuntimeError, 'basis digest'):
                real.keeper_basis()
            with patch.object(real, 'KEEPER_RECEIPT_SHA', M.fp(rp)['sha256']):
                with self.assertRaisesRegex(RuntimeError, 'retirement incomplete'):
                    real.keeper_basis()
            rp.write_bytes(original)
            entry = next(iter(result['keepers'].values())); path = Path(entry['record']['path'])
            value = path.read_bytes(); path.unlink(); path.write_bytes(value)
            with self.assertRaisesRegex(RuntimeError, 'keeper changed'):
                real.keeper_basis()

    def test_keeper_basis_drift_refuses_apply_and_restore_before_intent(self):
        original = copy.deepcopy(self.basis)
        self.basis['evidence']['unexpected'] = {'sha256': '0'*64}
        with self.assertRaisesRegex(RuntimeError, 'keeper basis changed'):
            self.operate()
        self.assertFalse(self.result().with_name('apply.json.intent.json').exists())
        self.basis.clear(); self.basis.update(original); self.operate()
        self.basis['evidence']['unexpected'] = {'sha256': '0'*64}
        with self.assertRaisesRegex(RuntimeError, 'keeper basis changed'):
            self.operate('restore')
        self.assertFalse(self.result('restore').with_name('restore.json.intent.json').exists())


if __name__ == '__main__':
    unittest.main()
