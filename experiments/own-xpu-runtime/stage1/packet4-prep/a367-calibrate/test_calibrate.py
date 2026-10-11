"""Standard-library CPU tests. No Torch, native imports, devices or model launch."""
import copy
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

import a367_calibrate_load as c
import derive_floor as d
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
        self.temp = tempfile.TemporaryDirectory(prefix='a367-calibrate-cpu-')
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

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
                 'previous_teardown_completed_unix': now-306, 'purpose': 'a367-calibrate-load',
                 'calibration_preregistration_sha256': w.sha(c.REG), 'calibration_seal_sha256': w.sha(c.SEAL)}
        return owner, health, now, output

    def admit(self, owner, health, now, output, **kw):
        with patch.object(w.socket, 'gethostname', return_value='steve-b70s'):
            c.verify_admission(owner, health, 'test-boot', now, output,
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

    def test_default_floor_stays_unreachable(self):
        with self.assertRaisesRegex(ValueError, 'floor'):
            self.admit(*self.admission(), available=116_384_560)

    def test_exception_needs_exact_sealed_owner_sentence(self):
        a = self.admission()
        a[0]['calibration_memory_exception'] = {'approved': False, 'approved_by': 'owner',
            'minimum_mem_available_kib': 116_000_000, 'owner_approval_text': ''}
        with self.assertRaisesRegex(ValueError, 'exact owner'):
            self.admit(*a, available=116_384_560)
        a[0]['calibration_memory_exception'].update(approved=True,
            owner_approval_text=c.calibration_approval_text(116_000_000))
        self.admit(*a, available=116_384_560)
        with self.assertRaisesRegex(ValueError, 'floor'):
            self.admit(*a, available=115_999_999)

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
        for field in ('purpose', 'calibration_preregistration_sha256', 'calibration_seal_sha256', 'preregistration_sha256'):
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
        self.assertEqual(env['OMP_NUM_THREADS'], '2')
        self.assertIn('TORCH_TRACE', env)
        self.assertNotIn('NEOReadDebugKeys', env)
        self.assertNotIn('EnableDeferBacking', env)
        self.assertNotIn('--worker-cls', actual)
        self.assertNotIn('--enforce-eager', actual)
        # All literal server-relevant exports from the derived recipe must match.
        for name, value in re.findall(r'^export ([A-Z_0-9]+)=([^\n]+)$', derived, re.M):
            if name.startswith(('VLLM_', 'CCL_', 'FI_', 'PYTORCH_', 'ZE_')) and '$' not in value:
                # earlier SERIAL_SPEC_DECODE=1 is immediately overwritten by =0
                if name == 'VLLM_XPU_GDN_SERIAL_SPEC_DECODE' and value == '1':
                    continue
                self.assertEqual(env.get(name), value.strip('"'), name)

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
        root = self.root / 'run'; root.mkdir(); (root / 'scratch/rpc').mkdir(parents=True)
        w.write(root / 'identity.json', {'mock': True})
        events = []; ticks = [100.0]; state = {'signal_at': None}
        class Thread:
            ident = None
            def start(self): self.ident = 1
            def join(self, *a): pass
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
        with patch.object(c.time, 'monotonic', side_effect=lambda: ticks[0]):
            code = c.lifecycle(root, ['MOCK'], {}, sampler, stop, watch, launch=launch, is_ready=readiness,
                clock=lambda: ticks[0], sleep=sleep, process_rows=lambda: [], mock=True,
                owners_gone=lambda pid: state['signal_at'] is not None and ticks[0] >= state['signal_at'] + orphan_delay)
        return code, events, w.read(root / 'calibration.json'), root

    def test_graceful_order_and_gap(self):
        code, events, receipt, root = self.run_mock(orphan_delay=2)
        self.assertEqual(code, 0, receipt)
        signals = [e for e in events if e[0] == 'signal']
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0][1], signal.SIGINT)
        self.assertGreaterEqual(signals[0][2], 121)
        self.assertGreaterEqual(events[-1][1], signals[0][2] + 2 + 305)
        self.assertEqual(receipt['generation_requests'], 0)
        self.assertIs(receipt['mock'], True)
        self.assertFalse((root / 'scratch').exists())

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
        self.assertFalse((root / 'scratch').exists())
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


class Derivation(Base):
    def fixture(self):
        run = self.root / 'measurement'; run.mkdir()
        # Synthetic receipts exercise validation only, never retained as native evidence.
        rows = samples()
        (run / 'samples.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
        for filename, value in [('environment.json', {'passed': True}), ('owner-window.json', {}), ('payload.json', {})]:
            w.write(run / filename, value)
        command, env = c.command_and_environment(run.resolve())
        identity = {'schema': 'own-xpu-runtime.packet4.a367-calibration-identity.v1',
                    'recipe': 'A367', 'mock': False, 'minimum_mem_available_kib': 120_000_000, 'host': 'steve-b70s', 'boot_id': 'TEST-ONLY',
                    'preregistration_sha256': w.sha(c.REG), 'seal_sha256': w.sha(c.SEAL),
                    'command': command, 'environment': env, 'identity_deltas': w.read(c.REG)['identity_deltas'],
                    'audit_sha256': w.sha(run/'environment.json'), 'owner_sha256': w.sha(run/'owner-window.json'),
                    'payload_sha256': w.sha(run/'payload.json')}
        w.write(run / 'identity.json', identity)
        receipt = {'schema': 'own-xpu-runtime.packet4.a367-calibration.v1', 'passed': True, 'mock': False,
                   'failure': None, 'ready': True, 'clean_exit': True, 'gap_complete': True, 'generation_requests': 0,
                   'summary': c.summarize(rows), 'identity_sha256': w.sha(run/'identity.json'),
                   'samples_sha256': w.sha(run/'samples.jsonl')}
        w.write(run / 'calibration.json', receipt)
        w.write(run / 'stop.json', {'all_owners_gone': True, 'returncode': 0, 'completed_unix': 1000,
                                   'next_launch_not_before_unix': 1305})
        receipt['stop_sha256'] = w.sha(run/'stop.json')
        w.write(run/'calibration.json', receipt)
        return run

    def test_formula_and_pending_receipt(self):
        run = self.fixture()
        result = d.derive(run)
        self.assertEqual(result['proposed_minimum_mem_available_kib'], 60_388_608)
        before = w.sha(w.REVISION_DOC)
        out = self.root / 'proposal'
        digest = d.write_proposal(result, out)
        pending = w.read(out / 'admission-revision.pending.json')
        self.assertIs(pending['approved'], False)
        self.assertEqual(pending['owner_approval_text'], '')
        self.assertEqual(pending['revision_document_sha256'], digest)
        self.assertEqual(w.sha(w.REVISION_DOC), before)
        document = (out / 'MEMORY-ADMISSION-REVISION.proposed.md').read_text()
        self.assertEqual(re.findall(r'^proposed_minimum_mem_available_kib: (\d+)$', document, re.M), ['60388608'])
        self.assertEqual((out / 'owner-approval-sentence.txt').read_text().strip(), w.approval_text(60_388_608, digest))

    def test_failed_attempt8_refused(self):
        run = self.fixture(); r = w.read(run/'calibration.json')
        r.update(schema='neural.download.screen1b-calibration-load.v1', ready=False)
        w.write(run/'calibration.json', r)
        with self.assertRaisesRegex(ValueError, 'not an A367'):
            d.derive(run)

    def test_tampered_samples(self):
        run = self.fixture()
        with (run/'samples.jsonl').open('a') as stream: stream.write('{}\n')
        with self.assertRaisesRegex(ValueError, 'hash differs'):
            d.derive(run)

    def test_incomplete_receipts(self):
        run = self.fixture(); base = w.read(run/'calibration.json')
        for field, value in [('mock', True), ('ready', False), ('clean_exit', False), ('gap_complete', False), ('generation_requests', 1)]:
            receipt = dict(base); receipt[field] = value
            w.write(run/'calibration.json', receipt)
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'incomplete'):
                d.derive(run)

    def test_changed_runtime(self):
        run = self.fixture(); ident = w.read(run/'identity.json')
        ident['environment']['EnableDeferBacking'] = '0'
        w.write(run/'identity.json', ident)
        with self.assertRaisesRegex(ValueError, 'runtime command'):
            d.derive(run)

    def test_summary_must_recompute(self):
        run = self.fixture(); receipt = w.read(run/'calibration.json'); receipt['summary']['observed_need_kib'] = 1
        w.write(run/'calibration.json', receipt)
        with self.assertRaisesRegex(ValueError, 'recompute'):
            d.derive(run)


if __name__ == '__main__':
    unittest.main()
