"""Adapted from sealed calibration test_calibrate.py (5efca23e3).
Standard-library CPU tests. No Torch, native imports, devices or model launch."""
import copy
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import signal
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

import a367_replay as c
w = c.w


def samples():
    result = []
    for i in range(48):
        phase = 'baseline' if i == 0 else 'loading' if i < 3 else 'plateau' if i <= 44 else 'shutdown'
        available = (120_000_000 if i == 0 else 80_000_000 if phase != 'shutdown' else 110_000_000) * 1024
        result.append({'monotonic': 100 + i * .5, 'unix': 1000 + i * .5, 'phase': phase,
            'mem_total_bytes': 130_000_000 * 1024, 'mem_available_bytes': available,
            'host_pressure_bytes': 130_000_000 * 1024 - available, 'gpu_active_bytes': None,
            'ranks': {str(r): {'pid': 400 + r, 'rss_bytes': 1024**3} for r in range(4)},
            'cgroups': [{'path': '/mock/memory.current', 'memory_current_bytes': 50_000_000_000}]})
    return result


class Base(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='a367-replay-cpu-')
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        local = patch.object(c, 'LOCAL_SCRATCH', self.root / 'local-scratch')
        local.start()
        self.addCleanup(local.stop)

    def admission(self):
        now = time.time()
        stamp = time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(now - 2))
        health = {'schema': 'ltx.four-card-health.v1', 'passed': True, 'boot_id': 'test-boot',
                  'kernel': Path('/proc/sys/kernel/osrelease').read_text().strip(),
                  'start_utc': stamp, 'end_utc': stamp, 'device_count': 4,
                  'cards': [{'device': f'xpu:{r}', 'pass': True} for r in range(4)],
                  'journal_fault_lines_during_probe': [], 'fault_lines_earlier_this_boot': 0}
        hp = self.root / 'health.json'
        w.write(hp, health)
        output = self.root / 'run'
        owner = {'schema': 'own-xpu-runtime.packet4.owner-window.v1', 'authorized': True,
                 'boot_id': 'test-boot', 'host': 'steve-b70s', 'preregistration_sha256': w.sha(w.PREREG),
                 'health_path': str(hp), 'health_sha256': w.sha(hp), 'output': str(output),
                 'halt_resolved': True, 'pci_ids': ['0000:23:00.0', '0000:27:00.0', '0000:43:00.0', '0000:47:00.0'],
                 'firmware': 'test-only', 'issued_unix': now-10, 'expires_unix': now+3500,
                 'previous_teardown_completed_unix': now-306, 'purpose': 'a367-record-replay',
                 'replay_preregistration_sha256': w.sha(c.REG), 'replay_seal_sha256': w.sha(c.SEAL)}
        owner['replay_memory_exception'] = {'approved': True, 'approved_by': 'owner',
            'minimum_mem_available_kib': 114840824, 'owner_approval_text': c.replay_approval_text()}
        return owner, health, now, output

    def admit(self, owner, health, now, output, **kw):
        with patch.object(w.socket, 'gethostname', return_value='steve-b70s'):
            return c.verify_admission(owner, health, 'test-boot', now, output,
                               kw.get('rows', []), kw.get('faults', []), kw.get('available', 120_000_000))


class Admission(Base):
    def test_complete(self):
        self.admit(*self.admission())

    def test_execute_without_receipts_never_reaches_launcher(self):
        with patch.object(c.subprocess, 'Popen') as launch, self.assertRaisesRegex(ValueError, 'owner/health/payload'):
            c.main(['--execute', '--output', str(self.root / 'unused')])
        launch.assert_not_called()
        self.assertFalse((self.root / 'unused').exists())

    def test_no_owner(self):
        a = self.admission(); a[0]['authorized'] = False
        with self.assertRaisesRegex(ValueError, 'authorization'):
            self.admit(*a)

    def test_default_without_exception_refuses(self):
        a = self.admission(); del a[0]['replay_memory_exception']
        with self.assertRaisesRegex(ValueError, 'default refuses'):
            self.admit(*a)

    def test_exception_needs_exact_sealed_owner_sentence(self):
        a = self.admission()
        a[0]['replay_memory_exception'] = {'approved': False, 'approved_by': 'owner',
            'minimum_mem_available_kib': 114_840_824, 'owner_approval_text': ''}
        with self.assertRaisesRegex(ValueError, 'exact owner'):
            self.admit(*a, available=114_840_824)
        a[0]['replay_memory_exception'].update(approved=True,
            owner_approval_text=c.replay_approval_text(114_840_824))
        self.admit(*a, available=114_840_824)
        with self.assertRaisesRegex(ValueError, 'floor'):
            self.admit(*a, available=114_840_823)

    def test_halt(self):
        a = self.admission(); a[0]['halt_resolved'] = False
        with self.assertRaisesRegex(ValueError, 'halt'):
            self.admit(*a)

    def test_fault_marker(self):
        marker = self.root / 'FAULT.json'; marker.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'FAULT'):
            self.admit(*self.admission(), faults=[marker])

    def test_conflicting_owners(self):
        for name in ('ltx-stream', 'VLLM::Worker_TP0', 'ComfyUI'):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'process running'):
                self.admit(*self.admission(), rows=[(999, name, name)])

    def test_fresh_health_required(self):
        a = self.admission(); a[1]['end_utc'] = '2000-01-01 00:00:00 UTC'
        with self.assertRaisesRegex(ValueError, 'stale'):
            self.admit(*a)

    def test_failed_health_rank(self):
        a = self.admission(); a[1]['cards'][3]['pass'] = False
        with self.assertRaisesRegex(ValueError, 'rank coverage'):
            self.admit(*a)

    def test_earlier_boot_faults(self):
        a = self.admission(); a[1]['fault_lines_earlier_this_boot'] = 4
        with self.assertRaisesRegex(ValueError, 'earlier boot faults'):
            self.admit(*a)

    def test_gap(self):
        a = self.admission(); a[0]['previous_teardown_completed_unix'] = a[2] - 304
        with self.assertRaisesRegex(ValueError, '305-second'):
            self.admit(*a)

    def test_wrong_scope_and_seal(self):
        for field in ('purpose', 'replay_preregistration_sha256', 'replay_seal_sha256', 'preregistration_sha256'):
            a = self.admission(); a[0][field] = 'wrong'
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.admit(*a)

    def test_output_reuse(self):
        a = self.admission(); a[3].mkdir()
        with self.assertRaisesRegex(ValueError, 'output exists'):
            self.admit(*a)

    def test_window_binding(self):
        for field, value in [('boot_id', 'wrong'), ('host', 'wrong'), ('expires_unix', 0), ('health_sha256', 'wrong')]:
            a = self.admission(); a[0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.admit(*a)

    def test_fixture_receipt_cannot_admit_calibration(self):
        a = self.admission(); a[0]['admission_revision_sha256'] = 'pretend-approval'
        with self.assertRaisesRegex(ValueError, 'fixture revision'):
            self.admit(*a)


class HistoricalLatchAdmission(Base):
    @contextmanager
    def latches(self, entries, roots=None):
        # Virtual files only: no FAULT.json is created, edited or deleted.
        original_stat, original_read = Path.lstat, Path.read_bytes
        metadata = self.root.stat()
        def stat(path):
            return metadata if path in entries else original_stat(path)
        def read(path):
            if path not in entries:
                return original_read(path)
            value = entries[path]
            if isinstance(value, Exception):
                raise value
            return value
        with patch.object(w, 'FAULT_ROOTS', roots or (self.root,)), \
             patch.object(Path, 'lstat', stat), patch.object(Path, 'read_bytes', read):
            yield

    def test_prior_boot_archives_exempt_and_recorded(self):
        raw = b'{"boot_id": "prior-boot"}\n'
        entries = {self.root / segment / 'receipts/FAULT.json': raw
                   for segment in ('fault-archive', 'evidence', 'incident')}
        with self.latches(entries):
            receipt = self.admit(*self.admission(), faults=list(entries))
        self.assertEqual(receipt['boot_id'], 'test-boot')
        self.assertEqual(receipt['historical_fault_latches'], [
            {'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest(), 'boot_id': 'prior-boot'}
            for path in sorted(entries)])

    def test_current_boot_blocks_in_every_location(self):
        for directory in ('', 'evidence', 'fault-archive', 'incident', 'runs'):
            path = self.root / directory / 'FAULT.json'
            with self.subTest(directory=directory), self.latches({path: b'{"boot_id":"test-boot"}'}), \
                 self.assertRaisesRegex(ValueError, 'FAULT'):
                self.admit(*self.admission(), faults=[path])

    def test_prior_boot_top_level_blocks_even_when_root_is_evidence(self):
        root = self.root / 'evidence'
        path = root / 'FAULT.json'
        with self.latches({path: b'{"boot_id":"prior-boot"}'}, roots=(root,)), \
             self.assertRaisesRegex(ValueError, 'watched root'):
            self.admit(*self.admission(), faults=[path])

    def test_prior_boot_output_top_level_blocks(self):
        args = self.admission()
        path = args[3] / 'FAULT.json'
        with self.latches({path: b'{"boot_id":"prior-boot"}'}), \
             self.assertRaisesRegex(ValueError, 'watched root'):
            self.admit(*args, faults=[path])

    def test_missing_or_invalid_boot_blocks(self):
        path = self.root / 'evidence/FAULT.json'
        for raw in (b'{}', b'{"boot_id":null}', b'{"boot_id":""}', b'{"boot_id":" "}',
                    b'{"boot_id":123}', b'[]', b'{"boot_id":" test-boot "}'):
            with self.subTest(raw=raw), self.latches({path: raw}), \
                 self.assertRaisesRegex(ValueError, 'boot_id'):
                self.admit(*self.admission(), faults=[path])

    def test_unreadable_or_malformed_latch_blocks(self):
        path = self.root / 'evidence/FAULT.json'
        for raw in (PermissionError('denied'), b'not JSON', b'\xff'):
            with self.subTest(raw=raw), self.latches({path: raw}), \
                 self.assertRaisesRegex(ValueError, 'unreadable boot_id'):
                self.admit(*self.admission(), faults=[path])

    def test_prior_boot_outside_archive_segments_blocks(self):
        for directory in ('runs', 'evidence-copy', 'incident-20261011', 'fault-archive-old'):
            path = self.root / directory / 'FAULT.json'
            with self.subTest(directory=directory), self.latches({path: b'{"boot_id":"prior"}'}), \
                 self.assertRaisesRegex(ValueError, 'outside evidence/archive'):
                self.admit(*self.admission(), faults=[path])

    def test_archive_segment_above_watched_root_does_not_exempt(self):
        root = self.root / 'evidence/watched'
        path = root / 'runs/FAULT.json'
        with self.latches({path: b'{"boot_id":"prior"}'}, roots=(self.root, root)), \
             self.assertRaisesRegex(ValueError, 'outside evidence/archive'):
            self.admit(*self.admission(), faults=[path])

    def test_unknown_current_boot_cannot_exempt(self):
        with self.assertRaisesRegex(ValueError, 'current boot_id'):
            w.verify_fault_latches([], '', self.root / 'out')

    def test_same_latch_is_recorded_once(self):
        path = self.root / 'evidence/FAULT.json'
        with self.latches({path: b'{"boot_id":"prior"}'}):
            receipt = self.admit(*self.admission(), faults=[path, path])
        self.assertEqual(len(receipt['historical_fault_latches']), 1)

    def test_new_boot_uses_supplied_identity_without_hardcoded_boot(self):
        path = self.root / 'incident/FAULT.json'
        with self.latches({path: b'{"boot_id":"test-boot"}'}):
            receipt = w.verify_fault_latches([path], 'after-reboot', self.root / 'out')
        self.assertEqual(receipt['historical_fault_latches'][0]['boot_id'], 'test-boot')

    def test_discovery_keeps_nested_and_top_level_latches(self):
        path = self.root / 'evidence/FAULT.json'
        with patch.object(w, 'FAULT_ROOTS', (self.root,)), \
             patch.object(Path, 'rglob', return_value=iter([path])):
            found = c.fault_paths(self.root / 'out')
        self.assertEqual(set(found), {path, self.root / 'FAULT.json', self.root / 'out/FAULT.json'})

    def test_calibration_persists_both_admission_checks(self):
        owner, health, now, output = self.admission()
        owner_path = self.root / 'owner.json'
        payload_path = self.root / 'payload.json'
        w.write(owner_path, owner)
        w.write(payload_path, {})
        (self.root / 'data').mkdir()
        (self.root / 'data/runtime-stage-gdn-roundstate-v2-loadable.sha256').write_text('')
        receipt = {'boot_id': 'test-boot', 'historical_fault_latches': [
            {'path': '/mock/evidence/FAULT.json', 'boot_id': 'prior', 'sha256': 'a' * 64}]}
        with patch.object(c, 'command_and_environment', return_value=([], {'VLLM_RPC_BASE_PATH': '/s/rpc'})), \
             patch.object(c, 'verify_admission', return_value=receipt) as admission, \
             patch.object(c, 'verify_seals', return_value={'minimum_disk_free_bytes': 0}), \
             patch.object(c, 'fault_paths', return_value=[]), \
             patch.object(c, 'paths', return_value={'stage': self.root, 'model': self.root}), \
             patch.object(w, 'LANE', self.root), patch.object(c, 'HERE', self.root / 'packet'), \
             patch.object(w, 'processes', return_value=[]), \
             patch.object(w, 'verify_environment'), patch.object(w, 'verify_calibration_payload'), \
             patch.object(w, 'journal', return_value=''), patch.object(w.socket, 'socket'), \
             patch.object(c, 'verify_process_profile'), patch.object(c, 'verify_scratch_filesystem'), \
             patch.object(c, 'lifecycle', return_value=0):
            self.assertEqual(c.main(['--execute', '--output', str(output),
                '--owner-window', str(owner_path), '--health-receipt', owner['health_path'],
                '--payload-receipt', str(payload_path)]), 0)
        self.assertEqual(admission.call_count, 2)
        self.assertEqual(w.read(output / 'admission.json'), {'initial': receipt, 'final': receipt})
        audit = w.read(output / 'environment.json')
        self.assertIs(audit['passed'], True)
        self.assertEqual(audit['fault_latch_admission'], w.artifact(output / 'admission.json'))
        self.assertEqual(w.read(output / 'identity.json')['audit_sha256'], w.sha(output / 'environment.json'))


class Reconciliation(Base):
    def test_pinned_reconciliation_preserves_failed_historical_comparison(self):
        audit = {}
        payload = w.verify_calibration_reconciliation(w.read(w.PREREG), c.paths()['model'], audit)
        self.assertFalse(audit['historical_payload_receipt']['passed'])
        self.assertTrue(audit['calibration_reconciliation']['passed'])
        self.assertEqual(len(payload['files']), 144)

    def test_calibration_dependencies_exclude_fixture_only_inputs(self):
        p = c.verify_seals()
        self.assertEqual(sum(k.startswith('patches/') for k in p['calibration_repo_pins']), 75)
        for suffix in ('reference.py', 'test-receipt.json'):
            key = 'experiments/own-xpu-runtime/stage2/packet1b/' + suffix
            self.assertNotIn(key, p['calibration_repo_pins'])
            self.assertIn(key, p['repo_pins'])
        self.assertEqual(p['repo_pins']['experiments/own-xpu-runtime/stage2/packet1b/reference.py'],
                         '4e36c7c7890e7df428c7e1d10dc1b536d26ba18b8b7066c07f9dbdea2ff4909b')
        with self.assertRaisesRegex(ValueError, 'seal mismatch: .*stage2/packet1b/reference.py'):
            w.verify_repo()  # Fixture scope still refuses changed arithmetic.

    def test_missing_or_changed_reconciliation_pin_refused(self):
        for missing in (True, False):
            p = w.read(w.PREREG)
            name = p['calibration_reconciliation']['path']
            if missing:
                del p['calibration_repo_pins'][name]
            else:
                p['calibration_repo_pins'][name] = '0' * 64
            with self.subTest(missing=missing), self.assertRaises(ValueError):
                w.verify_calibration_reconciliation(p, c.paths()['model'], {})

    def test_reconciliation_semantics_cannot_waive_identity(self):
        p = w.read(w.PREREG)
        target = w.REPO / p['calibration_reconciliation']['path']
        original = w.read
        for key, value in [('historical_expected_sha256', '0'*64),
                           ('historical_actual_sha256', '0'*64),
                           ('revision', 'wrong'), ('model_root', '/nvme'),
                           ('file_differences', ['changed']), ('file_count_compared', 143),
                           ('passed', False), ('contract_equal', False)]:
            changed = original(target); changed[key] = value
            def reader(path):
                return changed if Path(path) == target else original(path)
            with self.subTest(key=key), patch.object(w, 'read', side_effect=reader), self.assertRaises(ValueError):
                w.verify_calibration_reconciliation(p, c.paths()['model'], {})

    def fresh(self):
        p = w.read(w.PREREG)
        payload = w.verify_calibration_reconciliation(p, c.paths()['model'], {})
        now = time.time()
        payload.update(started_unix=now-400, verified_unix=now-1)
        path = self.root / 'payload.json'
        w.write(path, payload)
        return p, payload, path, now

    def test_fresh_payload_accepted_and_owner_hash_required(self):
        p, payload, path, now = self.fresh()
        w.verify_calibration_payload(path, {'payload_sha256': w.sha(path)}, c.paths()['model'], p, now)
        with self.assertRaisesRegex(ValueError, 'owner payload pin'):
            w.verify_calibration_payload(path, {'payload_sha256': '0'*64}, c.paths()['model'], p, now)

    def test_fresh_payload_time_boundaries(self):
        p, payload, path, now = self.fresh()
        for age in (-1, 0, 3600, 3601):
            payload.update(started_unix=now-age-400, verified_unix=now-age)
            w.write(path, payload)
            if 0 <= age <= 3600:
                w.verify_calibration_payload(path, {'payload_sha256': w.sha(path)}, c.paths()['model'], p, now)
            else:
                with self.subTest(age=age), self.assertRaisesRegex(ValueError, 'fresh matched'):
                    w.verify_calibration_payload(path, {'payload_sha256': w.sha(path)}, c.paths()['model'], p, now)

    def test_fresh_payload_rejects_wrong_path_manifest_verifier_or_files(self):
        p, payload, path, now = self.fresh()
        for key, value in [('model_root', '/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8'),
                           ('manifest', {}), ('revision', 'wrong'), ('producer_sha256', '0'*64),
                           ('verifier_sha256', '0'*64), ('files', payload['files'][:-1]),
                           ('mismatches', ['changed']), ('passed', False),
                           ('all_files_sha256_verified', False)]:
            changed = copy.deepcopy(payload); changed[key] = value
            w.write(path, changed)
            with self.subTest(key=key), self.assertRaises(ValueError):
                w.verify_calibration_payload(path, {'payload_sha256': w.sha(path)}, c.paths()['model'], p, now)

    def test_new_source_path_is_the_only_source_override(self):
        self.assertEqual(str(c.paths()['source']), '/home/steve/src/vllm-flashnext-a367-clean-20261016')
        command, env = c.command_and_environment(self.root)
        self.assertEqual(env['PACKET4_SOURCE'], str(c.paths()['source']))
        self.assertIn(str(c.paths()['source']), env['PYTHONPATH'].split(':'))
        self.assertNotIn('--worker-cls', command)

    def test_old_approval_text_does_not_survive_reseal(self):
        owner = {'replay_memory_exception': {'approved': True, 'approved_by': 'owner',
                 'minimum_mem_available_kib': 114840824,
                 'owner_approval_text': c.replay_approval_text(114840824)}}
        real = w.sha
        with patch.object(w, 'sha', side_effect=lambda path: '0'*64 if path == c.SEAL else real(path)):
            with self.assertRaisesRegex(ValueError, 'exact owner approval'):
                c.replay_floor(owner)


class Math(Base):
    def test_units(self):
        self.assertEqual(c.meminfo('MemTotal: 200 kB\nMemAvailable: 123 kB\nGPUActive: 7 kB')['GPUActive'], 7168)
        self.assertNotIn('GPUActive', c.meminfo('MemTotal: 200 kB\nMemAvailable: 123 kB'))

    def test_missing_host_fields(self):
        with self.assertRaisesRegex(ValueError, 'missing'):
            c.meminfo('MemTotal: 200 kB')

    def test_decline_not_absolute_pressure_or_rss_sum(self):
        result = c.summarize(samples())
        self.assertEqual(result['observed_need_kib'], 40_000_000)
        self.assertEqual(result['sample_count'], 48)

    def test_sub_kib_rounds_up(self):
        rows = samples(); rows[1]['mem_available_bytes'] -= 1
        self.assertEqual(c.summarize(rows)['observed_need_kib'], 40_000_001)

    def test_incomplete_plateau(self):
        rows = samples(); rows[43]['phase'] = rows[44]['phase'] = 'shutdown'
        with self.assertRaisesRegex(ValueError, '20s'):
            c.summarize(rows)

    def test_gap_is_rejected(self):
        rows = samples(); rows[2]['monotonic'] += 2
        with self.assertRaisesRegex(ValueError, 'sampling gap'):
            c.summarize(rows)

    def test_rank_unknown_never_zero(self):
        rows = samples(); rows[4]['ranks']['3'] = None
        with self.assertRaisesRegex(ValueError, 'rank RSS'):
            c.summarize(rows)

    def test_cgroup_unknown(self):
        rows = samples(); rows[4]['cgroups'][0]['memory_current_bytes'] = None
        with self.assertRaisesRegex(ValueError, 'cgroup'):
            c.summarize(rows)

    def test_total_change(self):
        rows = samples(); rows[2]['mem_total_bytes'] += 1024
        with self.assertRaisesRegex(ValueError, 'MemTotal changed'):
            c.summarize(rows)

    def test_shadow_optional(self):
        self.assertGreater(c.summarize(samples())['observed_need_bytes'], 0)

    def test_session_scoped_proc_sampler(self):
        proc = self.root / 'proc'; proc.mkdir()
        (proc / 'meminfo').write_text('MemTotal: 200 kB\nMemAvailable: 123 kB\nGPUActive: 7 kB')
        cg = self.root / 'cgroup'; (cg / 'mock').mkdir(parents=True)
        (cg / 'mock/memory.current').write_text('4321')
        for i in range(5):
            p = proc / str(400 + i); p.mkdir()
            (p / 'comm').write_text(f'VLLM::Worker_TP{i if i < 4 else 0}_EP{i}')
            (p / 'cmdline').write_bytes(b'worker\0')
            (p / 'status').write_text('VmRSS: 17 kB\n')
            (p / 'cgroup').write_text('0::/mock\n')
        with patch.object(c.os, 'getsid', side_effect=lambda pid: 999 if pid < 404 else 1):
            row = c.snapshot(999, proc, cg)
        self.assertEqual(row['ranks']['0']['rss_bytes'], 17 * 1024)
        self.assertEqual(row['cgroups'][0]['memory_current_bytes'], 4321)
        self.assertEqual(row['gpu_active_bytes'], 7 * 1024)
        self.assertIsNone(row['driver_shadow_bytes'])

    def test_sampler_reads_worker_cmdline_once(self):
        # Replay b 2026-10-16: a cmdline read blocked on a loading worker's mmap lock (1.74 s gap).
        proc = self.root / 'proc'; proc.mkdir()
        (proc / 'meminfo').write_text('MemTotal: 200 kB\nMemAvailable: 123 kB')
        cg = self.root / 'cgroup'; (cg / 'mock').mkdir(parents=True)
        (cg / 'mock/memory.current').write_text('1')
        for i in range(4):
            p = proc / str(600 + i); p.mkdir()
            (p / 'comm').write_text('VLLM::Worker_TP\n')
            (p / 'cmdline').write_bytes(f'VLLM::Worker_TP{i}_EP{i}\0'.encode())
            (p / 'status').write_text('VmRSS: 5 kB\n')
            (p / 'cgroup').write_text('0::/mock\n')
        q = proc / '610'; q.mkdir()
        (q / 'comm').write_text('icpx\n'); (q / 'cmdline').write_bytes(b'icpx\0')
        (q / 'status').write_text('VmRSS: 1 kB\n'); (q / 'cgroup').write_text('0::/mock\n')
        with patch.object(c.os, 'getsid', return_value=999):
            first = c.snapshot(999, proc, cg)
            self.assertEqual({k: v['pid'] for k, v in first['ranks'].items()}, {str(i): 600 + i for i in range(4)})
            def no_cmdline(path, *a, **k):
                raise AssertionError('cmdline re-read: ' + str(path))
            with patch.object(Path, 'read_bytes', no_cmdline):
                second = c.snapshot(999, proc, cg)
        self.assertEqual({k: v['rss_bytes'] for k, v in second['ranks'].items()}, {str(i): 5 * 1024 for i in range(4)})

    def test_sampler_skips_process_exiting_during_scan(self):
        # 2026-10-16 attempt 2: getsid() on a just-exited host process raised ESRCH and tripped the watcher.
        proc = self.root / 'proc'; proc.mkdir()
        (proc / 'meminfo').write_text('MemTotal: 200 kB\nMemAvailable: 123 kB')
        cg = self.root / 'cgroup'; (cg / 'mock').mkdir(parents=True)
        (cg / 'mock/memory.current').write_text('1')
        for i in range(2):
            p = proc / str(500 + i); p.mkdir()
            (p / 'comm').write_text(f'VLLM::Worker_TP{i}_EP{i}')
            (p / 'cmdline').write_bytes(b'worker\0')
            (p / 'status').write_text('VmRSS: 9 kB\n')
            (p / 'cgroup').write_text('0::/mock\n')
        def getsid(pid):
            if pid == 500:
                raise ProcessLookupError(3, 'No such process')
            return 999
        with patch.object(c.os, 'getsid', side_effect=getsid):
            row = c.snapshot(999, proc, cg)
        self.assertIsNone(row['ranks']['0'])
        self.assertEqual(row['ranks']['1']['rss_bytes'], 9 * 1024)

    def test_output_path_too_long_for_ipc_refused(self):
        # 2026-10-16 attempt 1: a 121-char ipc path made the API server fail before workers started.
        long_root = '/mnt/raid-models/bench-results/' + 'x' * 80
        with self.assertRaisesRegex(ValueError, 'too long for vLLM ipc'):
            c.main(['--plan', '--output', long_root])
        ok_root = Path('/mnt/raid-models/bench-results/a367-20261016T135036Z')
        with patch.object(c, 'LOCAL_SCRATCH', Path('/home/steve/.cache/a367-scratch')):
            rpc = c.command_and_environment(ok_root)[1]['VLLM_RPC_BASE_PATH']
        self.assertEqual(rpc, '/home/steve/.cache/a367-scratch/a367-20261016T135036Z/rpc')
        self.assertLessEqual(len(rpc) + 37, c.RPC_PATH_MAX)

    def test_scratch_caches_on_local_scratch_not_output(self):
        # 2026-10-16 attempt 3: a shared Triton cache on the ntfs-3g output mount lost a published .llir.
        out = Path('/mnt/raid-models/bench-results/a367-20261016T142901Z')
        env = c.command_and_environment(out)[1]
        local = str(c.scratch_dir(out))
        for key in ('HF_HOME', 'HUGGINGFACE_HUB_CACHE', 'VLLM_CACHE_ROOT', 'TORCHINDUCTOR_CACHE_DIR',
                    'TRITON_CACHE_DIR', 'XDG_CACHE_HOME', 'TMPDIR', 'VLLM_RPC_BASE_PATH'):
            self.assertTrue(env[key].startswith(local + '/'), key)
        self.assertEqual(env['TORCH_TRACE'], str(out / 'torch-trace'))
        self.assertFalse(any(str(out / 'scratch') in v for v in env.values()))

    def test_load_budget_matches_preregistration(self):
        reg = w.read(c.REG)
        self.assertEqual(c.LOAD_BUDGET, reg['load_and_plateau_seconds'])
        self.assertEqual(c.PLATEAU, reg['ready_plateau_seconds'])
        self.assertEqual(c.LOAD_BUDGET, 1800)

    def test_missing_rss_reported_unknown(self):
        self.assertEqual(c.meminfo_status('Name: mock\n'), {})


class Identity(Base):
    def test_sealed_files(self):
        self.assertEqual(c.verify_seals()['patch_seal_members'], 75)

    def test_seal_tamper(self):
        with patch.object(w, 'sha', return_value='corrupted'), self.assertRaisesRegex(ValueError, 'seal mismatch'):
            c.verify_seals()

    def test_server_arguments_match_frozen_launcher(self):
        # Only the awk text transformation runs on CPU; never execute its shell output.
        tool = w.LANE / 'tools/launch-tp4-mtp1-4352-ple-only-a367-fullgraphdet-w13n32.sh'
        text = tool.read_text()
        awk = text.split("awk '\n", 1)[1].split("\n' \"$base\"", 1)[0]
        # Shell's standard single-quote splice inside the awk literal.
        awk = awk.replace("'\\''", "'")
        derived = subprocess.run(['awk', awk, str(w.LANE / 'tools/launch-tp4-ep4-eager-mtp0-long-context-base.sh')],
                                 check=True, capture_output=True, text=True).stdout
        expected_hash = re.search(r'^expected_derived=(\w+)$', text, re.M)[1]
        self.assertEqual(hashlib.sha256(derived.encode()).hexdigest(), expected_hash)
        block = derived.split('args=(\n', 1)[1].split('\n)', 1)[0]
        subst = {'model': str(c.paths()['model']), 'port': '19980', 'served_model_name': 'qwen38-flash-next-fp8-tp4',
                 'max_model_len': '4352', 'kv_cache_memory_bytes': '376569856'}
        for key, val in subst.items():
            block = block.replace('${' + key + '}', val)
        original = shlex.split(block) + ['--speculative-config', '{"method":"mtp","num_speculative_tokens":1}']
        actual, env = c.command_and_environment(self.root)
        self.assertEqual(actual[3:5], ['serve', str(c.paths()['model'])])
        # cudagraph-metrics is a valueless switch moved to the end by reconstruction.
        original.remove('--cudagraph-metrics')
        self.assertEqual(actual[4:-1], original)
        self.assertEqual(actual[-1], '--cudagraph-metrics')
        self.assertEqual(env['VLLM_XPU_ENABLE_XPU_GRAPH'], '1')
        self.assertEqual(env['OMP_NUM_THREADS'], '1')
        self.assertIn('TORCH_TRACE', env)
        self.assertNotIn('NEOReadDebugKeys', env)
        self.assertNotIn('EnableDeferBacking', env)
        self.assertNotIn('--worker-cls', actual)
        self.assertNotIn('--enforce-eager', actual)
        # Derive every export without evaluating the historical host-control shell.
        variables = dict(stage=str(c.paths()['stage']), vllm_src=str(c.paths()['source']),
                         PATH='/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin')
        declared = {'PYTHONPATH', 'HF_HOME', 'HUGGINGFACE_HUB_CACHE', 'VLLM_CACHE_ROOT',
                    'TORCHINDUCTOR_CACHE_DIR', 'TRITON_CACHE_DIR', 'XDG_CACHE_HOME',
                    'TMPDIR', 'VLLM_RPC_BASE_PATH'}
        exports = {}
        for name, value in re.findall(r'^export ([A-Z_0-9]+)=([^\n]+)$', derived, re.M):
            value = value.strip('"')
            value = re.sub(r'\$\{([^}]+)\}', lambda m: variables.get(m[1], m[0]), value)
            exports[name] = value
            variables[name] = value
        for name, value in exports.items():
            if name in declared or name.startswith('Q38_'):
                continue
            self.assertNotIn('$', value, name)
            self.assertEqual(env.get(name), value, name)
        extras = {'HOME', 'USER', 'LOGNAME', 'LANG', 'TORCH_TRACE',
                  'PACKET4_SOURCE', 'PACKET4_WINDOW', 'Q38_EXPERT_HOST_PLACEMENT'}
        self.assertEqual(set(env) - set(exports), extras)
        self.assertEqual(env['PYTHONPATH'].split(':')[-2:],
                         [str(c.paths()['stage']), str(c.paths()['source'])])
        with patch.dict(os.environ, {'OMP_NUM_THREADS': '99', 'NEOReadDebugKeys': '1',
                                    'VLLM_EVIL': '1', 'HOME': '/wrong', 'MKL_NUM_THREADS': '99'}):
            self.assertEqual(c.command_and_environment(self.root)[1], env)

    def test_only_readiness_gets(self):
        calls = []
        class Response:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *a): pass
            def read(self): return b'{"data":[{"id":"qwen38-flash-next-fp8-tp4"}]}'
        def get(url, **kw):
            calls.append(url); return Response()
        with patch.object(c.urllib.request, 'urlopen', side_effect=get):
            self.assertTrue(c.ready())
        self.assertEqual(calls, ['http://127.0.0.1:19980/health', 'http://127.0.0.1:19980/v1/models'])


class Lifecycle(Base):
    def run_mock(self, fail=None, orphan_delay=0, rc=0):
        root = self.root / 'run'; root.mkdir(); (c.scratch_dir(root) / 'rpc').mkdir(parents=True)
        w.write(root / 'identity.json', {'mock': True})
        events = []; ticks = [100.0]; state = {'signal_at': None}
        class Thread:
            ident = None
            def start(self): self.ident = 1
            def join(self, *a):
                if fail == 'late_fault' and state['signal_at'] is not None:
                    watch.failed = 'late watcher failure'
            def is_alive(self): return False
        class Watch:
            failed = None
            stop = __import__('threading').Event()
            thread = Thread()
            def poll(self): events.append(('journal', ticks[0]))
        class Child:
            pid = 999
            returncode = rc
            def poll(self): return rc if state['signal_at'] is not None else None
            def send_signal(self, sig):
                events.append(('signal', sig, ticks[0])); state['signal_at'] = ticks[0]
        def sample(pid):
            ticks[0] += .0001
            row = copy.deepcopy(samples()[0 if pid is None else 4])
            row['monotonic'] = ticks[0]
            return row
        stop = c.Stop(root)
        sampler = c.Sampler(root, stop, lambda: None, sample)
        sampler.thread = Thread()
        watch = Watch()
        def launch(*a, **kw):
            events.append(('launch', ticks[0]))
            self.assertTrue(sampler.rows and sampler.rows[0]['phase'] == 'baseline')
            self.assertEqual(watch.thread.ident, 1)
            if fail == 'launch': raise OSError('mock launch failed')
            return Child()
        def sleep(seconds):
            ticks[0] += seconds
            if not sampler.done.is_set():
                sampler.take()
            if fail == 'fault' and ticks[0] >= 101:
                watch.failed = 'mock kernel fault'
        def readiness():
            if fail == 'ready': raise ValueError('mock readiness failed')
            return ticks[0] >= 101
        def client(*args, **kwargs):
            events.append(('client', ticks[0]))
            if fail == 'client': raise ValueError('mock client failure')
            if fail == 'stalled_client':
                class StalledClient:
                    pid = 43
                    def poll(self): return 1 if ticks[0] > 500 else None
                kwargs['clients'].append(StalledClient())
                stop.request('2700s client wall budget exceeded')
                return {'attempted': True, 'returncode': None}
            sampler.phase = 'generation'
            sleep(1)
            return {'attempted': True, 'returncode': 0}
        def compare(root):
            events.append(('compare', ticks[0]))
            return {'exact': fail != 'mismatch', 'class_balanced_median_tok_s': 1.0}
        with patch.object(c.time, 'monotonic', side_effect=lambda: ticks[0]):
            code = c.lifecycle(root, ['MOCK'], {}, sampler, stop, watch, launch=launch, is_ready=readiness,
                clock=lambda: ticks[0], sleep=sleep, process_rows=lambda: [], mock=True,
                run_client=client, check_result=compare,
                owners_gone=lambda pid: state['signal_at'] is not None and ticks[0] >= state['signal_at'] + orphan_delay)
        return code, events, w.read(root / 'replay.json'), root

    def test_graceful_order_and_gap(self):
        code, events, receipt, root = self.run_mock(orphan_delay=2)
        self.assertEqual(code, 0, receipt)
        signals = [e for e in events if e[0] == 'signal']
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0][1], signal.SIGINT)
        self.assertGreaterEqual(signals[0][2], 121)
        self.assertGreaterEqual(events[-1][1], signals[0][2] + 2 + 305)
        self.assertTrue(receipt['client']['attempted'])
        self.assertTrue(receipt['comparison']['exact'])
        self.assertIs(receipt['mock'], True)
        self.assertFalse(c.scratch_dir(root).exists())

    def test_fault_never_succeeds(self):
        code, events, receipt, root = self.run_mock(fail='fault')
        self.assertEqual(code, 1)
        self.assertFalse(receipt['passed'])
        self.assertEqual(len([e for e in events if e[0] == 'signal']), 1)

    def test_failed_readiness_stops_once(self):
        code, events, receipt, root = self.run_mock(fail='ready')
        self.assertEqual(code, 1)
        self.assertEqual(len([e for e in events if e[0] == 'signal']), 1)

    def test_launch_exception_cleanup(self):
        code, events, receipt, root = self.run_mock(fail='launch')
        self.assertEqual(code, 1)
        self.assertFalse(c.scratch_dir(root).exists())
        self.assertFalse(any(e[0] == 'signal' for e in events))

    def test_nonzero_exit(self):
        code, events, receipt, root = self.run_mock(rc=1)
        self.assertEqual(code, 1)
        self.assertFalse(receipt['clean_exit'])

    def test_teardown_overrun_no_escalation(self):
        code, events, receipt, root = self.run_mock(orphan_delay=301)
        self.assertEqual(code, 1)
        self.assertTrue((root / 'teardown-incomplete.json').exists())
        self.assertEqual([e[1] for e in events if e[0] == 'signal'], [signal.SIGINT])

    def test_kernel_watcher_preserves_new_fault(self):
        boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        watch = w.Watch(self.root, 'clean kernel', boot)
        with patch.object(w, 'journal', return_value='xe: Fault response at address 123'), self.assertRaisesRegex(ValueError, 'new kernel fault'):
            watch.poll()
        self.assertTrue((self.root / 'FAULT.json').exists())

    def test_kernel_journal_error_fails_closed(self):
        boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        watch = w.Watch(self.root, 'clean kernel', boot)
        with patch.object(w, 'journal', side_effect=OSError('journal unavailable')):
            watch.run()
        self.assertIn('unavailable', watch.failed)
        self.assertTrue((self.root / 'STOP.json').exists())

    def test_stop_race_latches_before_launch(self):
        stop = c.Stop(self.root)
        stop.request('fault before Popen')
        sent = []
        child = type('Child', (), {'pid': 888, 'poll': lambda s: None, 'send_signal': lambda s, sig: sent.append(sig)})()
        stop.attach(child); stop.request('second request')
        self.assertEqual(sent, [signal.SIGINT])

    def test_independent_memory_watchdog_requests_stop(self):
        stop = c.Stop(self.root)
        row = samples()[0]; row['mem_available_bytes'] = 1
        sampler = c.Sampler(self.root, stop, lambda: None, lambda pid: row)
        sampler.done = type('Event', (), {'wait': __import__('unittest').mock.Mock(side_effect=[False, True])})()
        sampler.run()
        self.assertIn('reserve', sampler.failed)
        self.assertIn('memory/admission watcher', stop.reason)
        self.assertTrue((self.root / 'samples.jsonl').exists())

    def test_memory_guard_latches_once(self):
        stop = c.Stop(self.root)
        row = samples()[0]; row['mem_available_bytes'] = 1
        sampler = c.Sampler(self.root, stop, lambda: None, lambda pid: row)
        with self.assertRaisesRegex(ValueError, 'reserve'):
            sampler.take()



    def test_client_failure_stops_server_once(self):
        code, events, receipt, root = self.run_mock(fail='client')
        self.assertEqual(code, 1)
        self.assertEqual(len([e for e in events if e[0] == 'signal']), 1)
        self.assertTrue(receipt['gap_complete'])

    def test_mismatch_fails_after_clean_teardown(self):
        code, events, receipt, root = self.run_mock(fail='mismatch')
        self.assertEqual(code, 1)
        self.assertTrue(receipt['clean_exit'])
        self.assertFalse(receipt['comparison']['exact'])
        self.assertEqual(events[-1][0], 'compare')

    def test_fault_during_monitor_join_cannot_pass(self):
        code, events, receipt, root = self.run_mock(fail='late_fault')
        self.assertEqual(code, 1)
        self.assertIn('late watcher failure', receipt['failure'])

    def test_stalled_cpu_client_does_not_delay_gpu_exit_watch(self):
        code, events, receipt, root = self.run_mock(fail='stalled_client')
        self.assertEqual(code, 1)
        self.assertTrue(receipt['clean_exit'])
        self.assertTrue(receipt['gap_complete'])
        signal_time = next(e[2] for e in events if e[0] == 'signal')
        self.assertTrue(any(signal_time + 305 <= e[1] < 500 for e in events if e[0] == 'journal'))
        self.assertTrue((root / 'client-incomplete.json').exists())
        self.assertEqual(len([e for e in events if e[0] == 'signal']), 1)

class ClientPhase(Base):
    def run_client_mock(self, *, duration=2, rc=0, stopped=False, server_exit=False):
        ticks = [0.0]; events = []; signals = []
        sampler = type('Sampler', (), {'phase': 'plateau', 'failed': None})()
        watch = type('Watch', (), {'failed': None})()
        server = type('Server', (), {'pid': 42, 'poll': lambda _: 1 if server_exit else None,
                                     'send_signal': lambda _, sig: signals.append(sig)})()
        stop = c.Stop(self.root); stop.attach(server)
        if stopped: stop.request('pre-client stop')
        class Client:
            pid = 43
            returncode = None
            def poll(self):
                if ticks[0] >= 30 + duration: self.returncode = rc
                return self.returncode
        def launch(command, **kwargs):
            events.append((ticks[0], command, kwargs))
            return Client()
        def sleep(t): ticks[0] += t
        outcome = c.client_phase(self.root, sampler, stop, watch, server,
                                 launch=launch, clock=lambda: ticks[0], sleep=sleep)
        return outcome, events, signals, ticks[0]

    def test_once_after_full_record_sleep(self):
        result, events, signals, elapsed = self.run_client_mock()
        self.assertEqual(result['returncode'], 0)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0][0], 30)
        self.assertEqual(signals, [])
        self.assertEqual(events[0][1], c.client_command(self.root))

    def test_client_watchdog_latches_once_without_kill_or_waiting_for_cpu_client(self):
        result, events, signals, elapsed = self.run_client_mock(duration=9999)
        self.assertEqual(len(events), 1)
        self.assertEqual(signals, [signal.SIGINT])
        self.assertEqual(elapsed, 2730)
        self.assertIn('2700s', result['failure'])
        self.assertIsNone(result['returncode'])

    def test_nonzero_client_never_retried(self):
        result, events, signals, elapsed = self.run_client_mock(rc=1)
        self.assertEqual(result['returncode'], 1)
        self.assertEqual(len(events), 1)

    def test_stop_or_server_exit_before_client_refuses(self):
        for args in ({'stopped': True}, {'server_exit': True}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                self.run_client_mock(**args)

    def test_no_result_overwrite(self):
        (self.root / c.RESULT).write_text('{}')
        with self.assertRaisesRegex(ValueError, 'overwrite'):
            self.run_client_mock()

    def test_client_invocation_matches_record_shell(self):
        frozen = (c.REPRO / 'wait-and-run-client.sh').read_text()
        block = frozen.split('"$python" "$repo/scripts/', 1)[1].split(' > "$run_dir/', 1)[0]
        block = '"$python" "$repo/scripts/' + block
        block = block.replace('\\\n', ' ')
        variables = {'python': '/home/steve/.venvs/vllm-xpu/bin/python',
                     'repo': str(w.REPO), 'run_dir': str(self.root), 'port': str(w.PORT)}
        for key, value in variables.items():
            block = block.replace('${'+key+'}', value).replace('$'+key, value)
        expected = shlex.split(block)
        actual = c.client_command(self.root)[3:]
        self.assertEqual(actual[0], expected[0])
        self.assertEqual(actual[1], '-B')
        self.assertEqual(actual[2:], expected[1:])

    def test_process_profile_refuses_inherited_calibration_limits(self):
        with patch.object(c.os, 'getpriority', return_value=19), self.assertRaisesRegex(ValueError, 'nice0'):
            c.verify_process_profile()
        with patch.object(c.os, 'getpriority', return_value=0), \
             patch.object(c.os, 'sched_getaffinity', return_value={4}), \
             patch.object(c, 'online_cpus', return_value={0, 4}), self.assertRaisesRegex(ValueError, 'affinity'):
            c.verify_process_profile()
        with patch.object(c.os, 'getpriority', return_value=0), \
             patch.object(c.os, 'sched_getaffinity', return_value={0, 4}), \
             patch.object(c, 'online_cpus', return_value={0, 4}):
            c.verify_process_profile()

    def test_ext4_required(self):
        for fs in ('ext4', 'fuseblk'):
            with patch.object(c.subprocess, 'run', return_value=type('Result', (), {'stdout': fs})()):
                if fs == 'ext4': c.verify_scratch_filesystem()
                else:
                    with self.assertRaisesRegex(ValueError, 'ext4'): c.verify_scratch_filesystem()

    def test_stop_write_error_still_signals_once(self):
        signals = []
        stop = c.Stop(self.root)
        child = type('Child', (), {'pid': 42, 'poll': lambda _: None,
                                   'send_signal': lambda _, sig: signals.append(sig)})()
        stop.attach(child)
        with patch.object(w, 'write', side_effect=OSError('disk full')):
            stop.request('stop'); stop.request('again')
        self.assertEqual(signals, [signal.SIGINT])
        self.assertIn('disk full', stop.reason)

    def test_checker_accepts_slow_exact_result_and_reports_both_rates(self):
        record = w.read(w.REPO / w.read(c.REPRO / 'identity.json')['record']['performance_evidence'])
        record['summary']['class_balanced_tok_s_1_100_intervals_after_ttft']['median'] = 1.0
        w.write(self.root / c.RESULT, record)
        result = c.compare_result(self.root)
        self.assertTrue(result['exact'])
        self.assertEqual(result['class_balanced_median_tok_s'], 1.0)
        self.assertEqual(result['record_class_balanced_median_tok_s'], 46.854250)
        self.assertEqual(result['all_prompt_median_tok_s'], 46.322146702065716)
        record['output_sha256s'][0] = 'wrong'
        w.write(self.root / c.RESULT, record)
        (self.root / 'check-replay-result.log').unlink()
        self.assertFalse(c.compare_result(self.root)['exact'])



if __name__ == '__main__':
    unittest.main()
