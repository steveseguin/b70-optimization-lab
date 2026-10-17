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
import a367_glue01 as c
w = c.w

def samples():
    result = []
    for i in range(48):
        phase = 'baseline' if i == 0 else 'loading' if i < 3 else 'plateau' if i <= 44 else 'shutdown'
        available = (120000000 if i == 0 else 80000000 if phase != 'shutdown' else 110000000) * 1024
        result.append({'monotonic': 100 + i * 0.5, 'attribution_monotonic': 100 + i * 0.5, 'unix': 1000 + i * 0.5, 'phase': phase, 'mem_total_bytes': 130000000 * 1024, 'mem_available_bytes': available, 'host_pressure_bytes': 130000000 * 1024 - available, 'gpu_active_bytes': None, 'ranks': {str(r): {'pid': 400 + r, 'rss_bytes': 1024 ** 3} for r in range(4)}, 'cgroups': [{'path': '/mock/memory.current', 'memory_current_bytes': 50000000000}]})
    return result

class Base(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='a367-glue01-cpu-')
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        local = patch.object(c, 'LOCAL_SCRATCH', self.root / 'local-scratch')
        local.start()
        self.addCleanup(local.stop)

class Math(Base):

    def test_units(self):
        self.assertEqual(c.meminfo('MemTotal: 200 kB\nMemAvailable: 123 kB\nGPUActive: 7 kB')['GPUActive'], 7168)
        self.assertNotIn('GPUActive', c.meminfo('MemTotal: 200 kB\nMemAvailable: 123 kB'))

    def test_missing_host_fields(self):
        with self.assertRaisesRegex(ValueError, 'missing'):
            c.meminfo('MemTotal: 200 kB')

    def test_decline_not_absolute_pressure_or_rss_sum(self):
        result = c.summarize(samples())
        self.assertEqual(result['observed_need_kib'], 40000000)
        self.assertEqual(result['sample_count'], 48)

    def test_sub_kib_rounds_up(self):
        rows = samples()
        rows[1]['mem_available_bytes'] -= 1
        self.assertEqual(c.summarize(rows)['observed_need_kib'], 40000001)

    def test_incomplete_plateau(self):
        rows = samples()
        rows[43]['phase'] = rows[44]['phase'] = 'shutdown'
        with self.assertRaisesRegex(ValueError, '20s'):
            c.summarize(rows)

    def test_gap_is_rejected(self):
        rows = samples()
        rows[2]['monotonic'] += 2
        with self.assertRaisesRegex(ValueError, 'sampling gap'):
            c.summarize(rows)

    def test_rank_unknown_never_zero(self):
        rows = samples()
        rows[4]['ranks']['3'] = None
        with self.assertRaisesRegex(ValueError, 'rank RSS'):
            c.summarize(rows)

    def test_cgroup_unknown(self):
        rows = samples()
        rows[4]['cgroups'][0]['memory_current_bytes'] = None
        with self.assertRaisesRegex(ValueError, 'cgroup'):
            c.summarize(rows)

    def test_total_change(self):
        rows = samples()
        rows[2]['mem_total_bytes'] += 1024
        with self.assertRaisesRegex(ValueError, 'MemTotal changed'):
            c.summarize(rows)

    def test_shadow_optional(self):
        self.assertGreater(c.summarize(samples())['observed_need_bytes'], 0)

    def test_session_scoped_proc_sampler(self):
        proc = self.root / 'proc'
        proc.mkdir()
        (proc / 'meminfo').write_text('MemTotal: 200 kB\nMemAvailable: 123 kB\nGPUActive: 7 kB')
        cg = self.root / 'cgroup'
        (cg / 'mock').mkdir(parents=True)
        (cg / 'mock/memory.current').write_text('4321')
        for i in range(5):
            p = proc / str(400 + i)
            p.mkdir()
            (p / 'comm').write_text(f'VLLM::Worker_TP{(i if i < 4 else 0)}_EP{i}')
            (p / 'cmdline').write_bytes(b'worker\x00')
            (p / 'status').write_text('VmRSS: 17 kB\n')
            (p / 'cgroup').write_text('0::/mock\n')
        with patch.object(c.os, 'getsid', side_effect=lambda pid: 999 if pid < 404 else 1):
            row = c.attribution(999, proc, cg)
        self.assertEqual(row['ranks']['0']['rss_bytes'], 17 * 1024)
        self.assertEqual(row['cgroups'][0]['memory_current_bytes'], 4321)
        memory = c.snapshot(999, proc, cg)
        self.assertEqual(memory['gpu_active_bytes'], 7 * 1024)
        self.assertIsNone(memory['driver_shadow_bytes'])

    def test_sampler_reads_worker_cmdline_once(self):
        proc = self.root / 'proc'
        proc.mkdir()
        (proc / 'meminfo').write_text('MemTotal: 200 kB\nMemAvailable: 123 kB')
        cg = self.root / 'cgroup'
        (cg / 'mock').mkdir(parents=True)
        (cg / 'mock/memory.current').write_text('1')
        for i in range(4):
            p = proc / str(600 + i)
            p.mkdir()
            (p / 'comm').write_text('VLLM::Worker_TP\n')
            (p / 'cmdline').write_bytes(f'VLLM::Worker_TP{i}_EP{i}\x00'.encode())
            (p / 'status').write_text('VmRSS: 5 kB\n')
            (p / 'cgroup').write_text('0::/mock\n')
        q = proc / '610'
        q.mkdir()
        (q / 'comm').write_text('icpx\n')
        (q / 'cmdline').write_bytes(b'icpx\x00')
        (q / 'status').write_text('VmRSS: 1 kB\n')
        (q / 'cgroup').write_text('0::/mock\n')
        with patch.object(c.os, 'getsid', return_value=999):
            first = c.attribution(999, proc, cg)
            self.assertEqual({k: v['pid'] for k, v in first['ranks'].items()}, {str(i): 600 + i for i in range(4)})

            def no_cmdline(path, *a, **k):
                raise AssertionError('cmdline re-read: ' + str(path))
            with patch.object(Path, 'read_bytes', no_cmdline):
                second = c.attribution(999, proc, cg)
        self.assertEqual({k: v['rss_bytes'] for k, v in second['ranks'].items()}, {str(i): 5 * 1024 for i in range(4)})

    def test_sampler_skips_process_exiting_during_scan(self):
        proc = self.root / 'proc'
        proc.mkdir()
        (proc / 'meminfo').write_text('MemTotal: 200 kB\nMemAvailable: 123 kB')
        cg = self.root / 'cgroup'
        (cg / 'mock').mkdir(parents=True)
        (cg / 'mock/memory.current').write_text('1')
        for i in range(2):
            p = proc / str(500 + i)
            p.mkdir()
            (p / 'comm').write_text(f'VLLM::Worker_TP{i}_EP{i}')
            (p / 'cmdline').write_bytes(b'worker\x00')
            (p / 'status').write_text('VmRSS: 9 kB\n')
            (p / 'cgroup').write_text('0::/mock\n')

        def getsid(pid):
            if pid == 500:
                raise ProcessLookupError(3, 'No such process')
            return 999
        with patch.object(c.os, 'getsid', side_effect=getsid):
            row = c.attribution(999, proc, cg)
        self.assertIsNone(row['ranks']['0'])
        self.assertEqual(row['ranks']['1']['rss_bytes'], 9 * 1024)

    def test_output_path_too_long_for_ipc_refused(self):
        long_root = '/mnt/raid-models/bench-results/' + 'x' * 80
        with self.assertRaisesRegex(ValueError, 'too long for vLLM ipc'):
            c.main(['--plan', '--arm', 'control', '--output', long_root])
        ok_root = Path('/mnt/raid-models/bench-results/a367-20261016T135036Z')
        with patch.object(c, 'LOCAL_SCRATCH', Path('/home/steve/.cache/a367-scratch')):
            rpc = c.command_and_environment(ok_root)[1]['VLLM_RPC_BASE_PATH']
        self.assertEqual(rpc, '/home/steve/.cache/a367-scratch/a367-20261016T135036Z/rpc')
        self.assertLessEqual(len(rpc) + 37, c.RPC_PATH_MAX)

    def test_scratch_caches_on_local_scratch_not_output(self):
        out = Path('/mnt/raid-models/bench-results/a367-20261016T142901Z')
        env = c.command_and_environment(out)[1]
        local = str(c.scratch_dir(out))
        for key in ('HF_HOME', 'HUGGINGFACE_HUB_CACHE', 'VLLM_CACHE_ROOT', 'TORCHINDUCTOR_CACHE_DIR', 'TRITON_CACHE_DIR', 'XDG_CACHE_HOME', 'TMPDIR', 'VLLM_RPC_BASE_PATH'):
            self.assertTrue(env[key].startswith(local + '/'), key)
        self.assertEqual(env['TORCH_TRACE'], str(out / 'torch-trace'))
        self.assertFalse(any((str(out / 'scratch') in v for v in env.values())))

    def test_load_budget_matches_preregistration(self):
        reg = w.read(c.REG)
        self.assertEqual(c.LOAD_BUDGET, reg['load_and_plateau_seconds'])
        self.assertEqual(c.PLATEAU, reg['ready_plateau_seconds'])
        self.assertEqual(c.LOAD_BUDGET, 1800)

    def test_missing_rss_reported_unknown(self):
        self.assertEqual(c.meminfo_status('Name: mock\n'), {})

class Lifecycle(Base):

    def run_mock(self, fail=None, orphan_delay=0, rc=0, traced=False):
        root = self.root / 'run'
        root.mkdir()
        (c.scratch_dir(root) / 'rpc').mkdir(parents=True)
        w.write(root / 'identity.json', {'mock': True})
        events = []
        ticks = [100.0]
        state = {'signal_at': None}

        class Thread:
            ident = None

            def start(self):
                self.ident = 1

            def join(self, *a):
                if fail == 'late_fault' and state['signal_at'] is not None:
                    watch.failed = 'late watcher failure'

            def is_alive(self):
                return False

        class Watch:
            failed = None
            stop = __import__('threading').Event()
            thread = Thread()

            def poll(self):
                events.append(('journal', ticks[0]))

        class Child:
            pid = 999
            returncode = rc

            def poll(self):
                return rc if state['signal_at'] is not None else None

            def send_signal(self, sig):
                events.append(('signal', sig, ticks[0]))
                state['signal_at'] = ticks[0]

        def sample(pid):
            ticks[0] += 0.0001
            row = copy.deepcopy(samples()[0 if pid is None else 4])
            row['monotonic'] = ticks[0]
            row['attribution_monotonic'] = ticks[0]
            return row
        stop = c.Stop(root)
        sampler = c.Sampler(root, stop, lambda: None, sample)
        sampler.thread = Thread()
        sampler.attribution.thread = Thread()
        sampler.budget.thread = Thread()
        sampler.live_thread = Thread()
        watch = Watch()

        def launch(*a, **kw):
            events.append(('launch', ticks[0]))
            self.assertTrue(sampler.rows and sampler.rows[0]['phase'] == 'baseline')
            self.assertEqual(watch.thread.ident, 1)
            if fail == 'launch':
                raise OSError('mock launch failed')
            return Child()

        def sleep(seconds):
            ticks[0] += seconds
            if not sampler.done.is_set():
                sampler.take()
            if fail == 'fault' and ticks[0] >= 101:
                watch.failed = 'mock kernel fault'
            if fail == 'memory' and ticks[0] >= 101:
                sampler.failed = 'mock memory reserve crossed'

        def readiness():
            if fail == 'ready':
                raise ValueError('mock readiness failed')
            return ticks[0] >= 101

        def client(*args, **kwargs):
            events.append(('client', ticks[0]))
            if fail == 'client':
                raise ValueError('mock client failure')
            if fail == 'stalled_client':

                class StalledClient:
                    pid = 43

                    def poll(self):
                        return 1 if ticks[0] > 500 else None
                kwargs['clients'].append(StalledClient())
                stop.request('2700s client wall budget exceeded')
                return {'attempted': True, 'returncode': None}
            sampler.phase = 'generation'
            sleep(1)
            return {'attempted': True, 'returncode': 0}

        def compare(root):
            events.append(('compare', ticks[0]))
            return {'exact': fail != 'mismatch', 'class_balanced_median_tok_s': 1.0}

        def control(cmd, **kw):
            events.append(('trace_control', cmd[1], ticks[0]))
            return type('Result', (), {'returncode': 0, 'stdout': '', 'stderr': f'Session {c.trace_session(root)} is paused'})()
        trace = c.TraceControl(root, control) if traced else None
        with patch.object(c.time, 'monotonic', side_effect=lambda: ticks[0]):
            code = c.lifecycle(root, ['MOCK'], {}, sampler, stop, watch, launch=launch, is_ready=readiness, clock=lambda: ticks[0], sleep=sleep, process_rows=lambda: [], mock=True, run_client=client, check_result=compare, owners_gone=lambda pid: state['signal_at'] is not None and ticks[0] >= state['signal_at'] + orphan_delay)
        return (code, events, w.read(root / 'glue01-run.json'), root)

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

    def test_loading_checks_memory_failure_independently_of_live_file_thread(self):
        code, events, receipt, _ = self.run_mock(fail='memory')
        self.assertEqual(code, 1)
        self.assertIn('memory', receipt['failure'])
        self.assertFalse(receipt['client']['attempted'])
        self.assertEqual(len([e for e in events if e[0] == 'signal']), 1)

    def test_failed_readiness_stops_once(self):
        code, events, receipt, root = self.run_mock(fail='ready')
        self.assertEqual(code, 1)
        self.assertEqual(len([e for e in events if e[0] == 'signal']), 1)

    def test_launch_exception_cleanup(self):
        code, events, receipt, root = self.run_mock(fail='launch')
        self.assertEqual(code, 1)
        self.assertFalse(c.scratch_dir(root).exists())
        self.assertFalse(any((e[0] == 'signal' for e in events)))

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
        stop.attach(child)
        stop.request('second request')
        self.assertEqual(sent, [signal.SIGINT])

    def test_independent_memory_watchdog_requests_stop(self):
        stop = c.Stop(self.root)
        row = samples()[0]
        row['mem_available_bytes'] = 1
        sampler = c.Sampler(self.root, stop, lambda: None, lambda pid: row)
        sampler.done = type('Event', (), {'wait': __import__('unittest').mock.Mock(side_effect=[False, True])})()
        sampler.run()
        self.assertIn('reserve', sampler.failed)
        with self.assertRaisesRegex(ValueError, 'reserve'):
            sampler.check_live()
        sampler.done = type('Event', (), {'is_set': __import__('unittest').mock.Mock(side_effect=[False, True]), 'wait': lambda *a: None})()
        sampler.run_live()
        self.assertIn('memory/admission watcher', stop.reason)
        self.assertFalse((self.root / 'samples.jsonl').exists())
        self.assertEqual(len(sampler.rows), 1)

    def test_memory_guard_latches_once(self):
        stop = c.Stop(self.root)
        row = samples()[0]
        row['mem_available_bytes'] = 1
        sampler = c.Sampler(self.root, stop, lambda: None, lambda pid: row)
        with self.assertRaisesRegex(ValueError, 'reserve'):
            sampler.take()

    def test_client_failure_stops_server_once(self):
        code, events, receipt, root = self.run_mock(fail='client')
        self.assertEqual(code, 1)
        self.assertEqual(len([e for e in events if e[0] == 'signal']), 1)
        self.assertTrue(receipt['gap_complete'])

    def test_mismatch_is_finding_after_clean_teardown(self):
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
        signal_time = next((e[2] for e in events if e[0] == 'signal'))
        self.assertTrue(any((signal_time + 305 <= e[1] < 500 for e in events if e[0] == 'journal')))
        self.assertTrue((root / 'client-incomplete.json').exists())
        self.assertEqual(len([e for e in events if e[0] == 'signal']), 1)

class SamplerHardening(Base):

    def test_sample_persistence_failure_retains_scratch(self):
        case = Lifecycle('test_launch_exception_cleanup')
        case.setUp()
        try:

            def fail_copy(sampler):
                sampler.writer.finish()
                raise OSError('copy failed')
            with patch.object(c.Sampler, 'persist', fail_copy):
                code, _, receipt, root = case.run_mock()
            self.assertEqual(code, 1)
            self.assertIn('copy failed', receipt['failure'])
            self.assertTrue(c.scratch_dir(root).exists())
            self.assertTrue((root / 'scratch-retained.json').exists())
        finally:
            case.doCleanups()

    def test_sampler_path_has_no_output_io_even_with_blocked_writer(self):
        import threading
        entered, release = (threading.Event(), threading.Event())
        local = c.scratch_dir(self.root)
        local.mkdir(parents=True)

        def open_file(path):
            entered.set()
            release.wait(5)
            return path.open('x')
        stop = c.Stop(self.root)
        sampler = c.Sampler(self.root, stop, lambda: None, lambda pid: samples()[0])
        sampler.writer = c.SampleWriter(local / 'samples.jsonl', open_file=open_file)
        sampler.writer.start()
        self.assertTrue(entered.wait(1))
        try:
            with patch.object(Path, 'open', side_effect=AssertionError('sampler file I/O')):
                for i in range(20):
                    sampler.take()
            self.assertEqual(len(sampler.rows), 20)
        finally:
            release.set()
            sampler.persist()
        persisted = [json.loads(line) for line in (self.root / 'samples.jsonl').read_text().splitlines()]
        self.assertEqual(persisted, sampler.rows)
        self.assertTrue(w.read(self.root / 'samples-persistence.json')['equals_in_memory_rows'])

    def test_optional_reference_without_trace_directory_has_zero_budget(self):
        budget = c.WriteBudget(self.root / 'absent', c.Stop(self.root), __import__('threading').Event())
        self.assertEqual(budget.take(), 0)

    def test_attribution_published_during_memory_read_is_used_next_time(self):
        stop = c.Stop(self.root)
        sampler = c.Sampler(self.root, stop, lambda: None)
        old = {'attribution_monotonic': 10, 'ranks': {}, 'cgroups': []}
        new = {'attribution_monotonic': 12, 'ranks': {}, 'cgroups': []}
        sampler.attribution.latest = old

        def sample(pid):
            row = samples()[0]
            row['monotonic'] = 11
            sampler.attribution.latest = new
            return row
        sampler.sample = sample
        self.assertEqual(sampler.take()['attribution_monotonic'], 10)

    def test_budget_soft_stop_and_post_drain_measure(self):
        stop = c.Stop(self.root)
        budget = c.WriteBudget(self.root, stop, __import__('threading').Event())
        (self.root / 'a').write_bytes(b'abcd')
        self.assertEqual(budget.take(), 4)
        with patch.object(budget, 'measure', return_value=8 * 2 ** 30):
            with self.assertRaisesRegex(ValueError, 'soft stop'):
                budget.take()

    def test_stale_and_future_attribution_fails_plateau(self):
        for age in (2.001, -0.001):
            rows = samples()
            rows[4]['attribution_monotonic'] = rows[4]['monotonic'] - age
            with self.subTest(age=age), self.assertRaisesRegex(ValueError, 'attribution'):
                c.summarize(rows)
        rows = samples()
        rows[4]['attribution_monotonic'] -= 2
        c.summarize(rows)

    def test_attribution_timestamp_precedes_blocking_scan(self):
        proc = self.root / 'proc'
        proc.mkdir()
        ticks = [10.0]
        p = proc / '1'
        p.mkdir()
        (p / 'comm').write_text('python')
        (p / 'cgroup').write_text('0::/mock')
        cg = self.root / 'cg'
        (cg / 'mock').mkdir(parents=True)
        (cg / 'mock/memory.current').write_text('100')
        original = Path.read_text

        def read(path, *args, **kwargs):
            if path.name == 'memory.current':
                ticks[0] = 20.0
            return original(path, *args, **kwargs)
        with patch.object(c.os, 'getsid', return_value=999), patch.object(c.time, 'monotonic', side_effect=lambda: ticks[0]), patch.object(Path, 'read_text', read):
            row = c.attribution(999, proc, cg)
        self.assertEqual(row['attribution_monotonic'], 10.0)
        self.assertEqual(ticks[0], 20.0)

    def test_blocked_attribution_cannot_delay_memory_samples(self):
        import threading
        entered, release = (threading.Event(), threading.Event())

        def scan(pid):
            entered.set()
            release.wait(5)
            return {'attribution_monotonic': time.monotonic(), 'ranks': {}, 'cgroups': []}

        def memory(pid):
            row = samples()[0]
            row['monotonic'] = time.monotonic()
            return row
        stop = c.Stop(self.root)
        checks = []
        sampler = c.Sampler(self.root, stop, lambda: checks.append(time.monotonic()), memory, scan)
        sampler.take()
        sampler.attribution.thread.start()
        self.assertTrue(entered.wait(1))
        sampler.thread.start()
        sampler.live_thread.start()
        try:
            time.sleep(1.65)
            self.assertGreaterEqual(len(sampler.rows), 4)
            self.assertGreaterEqual(len(checks), 3)
            gaps = [b['monotonic'] - a['monotonic'] for a, b in zip(sampler.rows, sampler.rows[1:])]
            self.assertLess(max(gaps), 1.0)
            self.assertIsNone(stop.reason)
        finally:
            sampler.done.set()
            release.set()
            sampler.thread.join(2)
            sampler.attribution.thread.join(2)
            sampler.live_thread.join(2)

    def test_sampler_live_stale_plateau_trips(self):
        row = samples()[4]
        row['attribution_monotonic'] -= 2.1
        stop = c.Stop(self.root)
        sampler = c.Sampler(self.root, stop, lambda: None, lambda pid: row)
        sampler.phase = 'plateau'
        with self.assertRaisesRegex(ValueError, 'attribution'):
            sampler.take()
