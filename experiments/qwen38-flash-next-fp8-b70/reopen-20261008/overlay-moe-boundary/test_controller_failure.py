"""Run the staged supervision/cleanup flow with CPU process and clock doubles."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import build_patch as builder
from test_staged_paths import staged_modules


class ControllerFailure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='moe-first-cause-')
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.root = Path(cls.tmp.name)
        with patch.dict(os.environ, SCREEN1B_MOE_BOUNDARY='1'):
            cls.stage = builder.stage(cls.root / 'package')

    def setUp(self):
        self.tmp_run = tempfile.TemporaryDirectory(dir=self.root)
        self.addCleanup(self.tmp_run.cleanup)
        self.run = Path(self.tmp_run.name)

    def supervise(self, initial, *, receipt_error=False, calibration_error=False):
        with staged_modules(self.stage, builder.REPO) as screen:
            now = [1000.0]
            signalled = []
            marker_at_signal = []
            clock = SimpleNamespace(time=lambda: now[0], monotonic=lambda: now[0],
                                    sleep=lambda seconds: now.__setitem__(0, now[0]+seconds))
            args = SimpleNamespace(mode='calibrate-load', port=19988, loading_ram_guard_gb=96)
            # Never sample live memory, walk /sys, contact HTTP or launch a process.
            sampler = SimpleNamespace(container_pid=None, phase='loading')
            watchdog = SimpleNamespace(reason=None, check=lambda: None, start=lambda: None, close=lambda: None)
            server = SimpleNamespace(poll=lambda: 1 if signalled else None)
            watcher = SimpleNamespace(poll=lambda: 0 if (self.run/'controller-exit.json').exists() else None)
            (self.run/'watcher.json').write_text(json.dumps({'status': 'post-exit gap complete'}))
            (self.run/'host-memory-samples.jsonl').write_text('')
            for name in ('config.json', 'model.safetensors.index.json'):
                (self.run/name).write_text('{}')

            def popen(command, **kwargs):
                if command[0] == 'docker':
                    self.assertEqual(command[1], 'run')
                    return server
                self.assertEqual(command[1], str(self.stage/'probe/watch_kernel.py'))
                return watcher

            def command(argv, **kwargs):
                self.assertEqual(argv[0], 'docker')
                if argv[1] == 'kill':
                    self.assertEqual(argv[2], '--signal=SIGINT')
                    signalled.append(argv)
                    receipt = self.run/'controller-first-failure.json'
                    marker_at_signal.append(json.loads(receipt.read_text()) if receipt.exists() else None)
                    return SimpleNamespace(returncode=0, stdout='', stderr='')
                self.assertEqual(argv[1:3], ['inspect', '--format'])
                fmt = argv[3]
                if fmt == '{{.State.Running}}':
                    output = 'false' if signalled else 'true'
                elif fmt == '{{json .State}}':
                    output = json.dumps({'ExitCode': 1, 'OOMKilled': False, 'Error': ''})
                elif fmt == '{{.State.Pid}}':
                    output = '42'
                else:
                    self.fail(argv)
                return SimpleNamespace(returncode=0, stdout=output, stderr='')

            real_stop = screen.DeferredStop
            real_write = screen.write_calibration
            original_open = Path.open
            def path_open(path, *a, **kw):
                if receipt_error and path.name == 'controller-first-failure.json' and a == ('x',):
                    raise PermissionError('synthetic receipt-write failure')
                return original_open(path, *a, **kw)

            def write_calibration(*a, **kw):
                if calibration_error:
                    raise OSError('synthetic calibration-write failure')
                return real_write(*a, **kw)

            # A successful readiness path reaches a cleanup-only error. No
            # model request is sent: these are in-memory HTTP response doubles.
            health = Mock(status=200)
            health.__enter__ = Mock(return_value=health)
            health.__exit__ = Mock(return_value=False)
            models = io.StringIO('{"data":[{"id":"qwen38-flash-next-fp8-tp4"}]}')
            stderr = io.StringIO()
            stdout = io.StringIO()
            mocks = dict(preflight=Mock(return_value=0), call=Mock(),
                         collect_observations=Mock(return_value={}), paired_observations=Mock(return_value={}),
                         boundary_watcher_clear=Mock(), check_live=Mock(side_effect=initial),
                         idle=Mock(), journal=Mock(return_value='benign journal'),
                         new_fault_lines=Mock(return_value=[]), validate_rank_receipts=Mock(return_value={'passed': True}),
                         MemoryWatchdog=Mock(return_value=watchdog), MODEL=self.run, time=clock,
                         DeferredStop=lambda run, name: real_stop(run, name, runner=command),
                         write_calibration=write_calibration)
            with patch.multiple(screen, **mocks), patch.object(screen.calibration, 'Sampler', return_value=sampler), \
                    patch.object(screen.subprocess, 'Popen', side_effect=popen), \
                    patch.object(screen.subprocess, 'run', side_effect=command), \
                    patch.object(screen.signal, 'signal', return_value=None), \
                    patch.object(screen.urllib.request, 'urlopen', side_effect=[health, models]), \
                    patch.object(Path, 'open', path_open), contextlib.redirect_stderr(stderr), \
                    contextlib.redirect_stdout(stdout):
                with self.assertRaises(BaseException) as caught:
                    screen.supervise_locked(args, self.run)
            self.assertEqual(len(signalled), 1)
            self.assertTrue((self.run/'controller-exit.json').exists())
            return caught.exception, marker_at_signal[0], stderr.getvalue()

    def test_first_exception_survives_unclean_exit_and_is_written_before_stop(self):
        initial = RuntimeError('synthetic startup gate refusal')
        caught, at_signal, log = self.supervise(initial)
        self.assertIs(caught, initial)
        self.assertEqual(at_signal['failure'], 'RuntimeError: synthetic startup gate refusal')
        self.assertEqual(at_signal['phase'], 'startup live checks')
        self.assertFalse(at_signal['stop_requested'])
        self.assertIn('synthetic startup gate refusal', at_signal['traceback'])
        self.assertIn('synthetic startup gate refusal', (self.run/'STOP').read_text())
        final = json.loads((self.run/'calibration-load.json').read_text())
        self.assertEqual(final['failure'], at_signal['failure'])
        self.assertEqual(final['cleanup_failure'], 'RuntimeError: Container exit was not clean')
        self.assertFalse(final['verdict']['passed'])
        self.assertTrue(json.loads((self.run/'controller-cleanup-failure.json').read_text())['secondary'])
        self.assertIn('controller_failure', log)

    def test_timeout_is_not_relabelled_as_unclean_container(self):
        initial = subprocess.TimeoutExpired(['journalctl', 'synthetic'], 3)
        caught, at_signal, _ = self.supervise(initial)
        self.assertIs(caught, initial)
        self.assertIn('TimeoutExpired', at_signal['failure'])

    def test_receipt_write_failure_keeps_original_and_still_signals_once(self):
        initial = RuntimeError('synthetic first failure')
        caught, at_signal, log = self.supervise(initial, receipt_error=True)
        self.assertIs(caught, initial)
        self.assertIsNone(at_signal)
        self.assertIn('synthetic first failure', log)
        self.assertIn('receipt unavailable', log)

    def test_calibration_write_failure_does_not_mask_first_exception(self):
        initial = RuntimeError('synthetic first failure')
        caught, _, log = self.supervise(initial, calibration_error=True)
        self.assertIs(caught, initial)
        self.assertIn('synthetic calibration-write failure', log)

    def test_cleanup_only_failure_is_primary(self):
        caught, at_signal, _ = self.supervise(None)
        self.assertEqual(str(caught), 'Container exit was not clean')
        self.assertIsNone(at_signal)
        self.assertFalse(json.loads((self.run/'controller-first-failure.json').read_text())['secondary'])
        self.assertEqual((self.run/'STOP').read_text(), 'controller completion\n')

    def test_existing_worker_stop_is_preserved_and_one_signal_sent(self):
        with staged_modules(self.stage, builder.REPO) as screen:
            stop_file = self.run/'STOP'
            stop_file.write_text('worker allocation refusal\n')
            before = stop_file.stat().st_mtime_ns
            runner = Mock(return_value=SimpleNamespace(returncode=0, stdout='true', stderr=''))
            stop = screen.DeferredStop(self.run, 'synthetic', runner=runner)
            stop.armed = True
            stop.request('controller later failure')
            stop.request('another later failure')
            self.assertEqual(stop_file.read_text(), 'worker allocation refusal\n')
            self.assertEqual(stop_file.stat().st_mtime_ns, before)
            self.assertEqual(stop.reason, 'worker allocation refusal')
            self.assertEqual(sum(c.args[0][1] == 'kill' for c in runner.call_args_list), 1)

    def test_stale_heartbeat_records_exact_evaluated_receipt(self):
        with staged_modules(self.stage, builder.REPO) as screen:
            receipt = dict(passed=True, new_fault_lines=[], updated_unix=999., read_started_unix=996.,
                           boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
            (self.run/'watcher.json').write_text(json.dumps(receipt))
            with patch.object(screen.time, 'time', return_value=1000.):
                with self.assertRaisesRegex(RuntimeError, 'stale: read_started_unix') as caught:
                    screen.boundary_watcher_clear(self.run)
            self.assertEqual(caught.exception.boundary_watcher_observation,
                             {'checked_unix': 1000., 'receipt': receipt})

    def test_benign_hogged_cpu_is_not_a_fault(self):
        with staged_modules(self.stage, builder.REPO) as screen:
            line = '2026-10-11T04:33:00+00:00 host kernel: workqueue: delayed_fput hogged CPU for >10000us 8 times'
            self.assertEqual(screen.new_fault_lines(line, 0), [])
            self.assertTrue(screen.new_fault_lines(line+'\n2026-10-11T04:34:00+00:00 host kernel: Fault response: Unsuccessful -ENOENT', 0))


if __name__ == '__main__':
    unittest.main()
