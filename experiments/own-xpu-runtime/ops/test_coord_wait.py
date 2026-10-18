"""Temporary files and mocked systemctl only; no live queues or services."""
import io
import json
from pathlib import Path
import subprocess
import signal
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import coord_wait as c


class CoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.addCleanup(patch.stopall)
        patch.object(c, 'DIRECTORY', self.root).start()
        self.systemctl = patch.object(c, '_systemctl', side_effect=AssertionError('unexpected service access')).start()
        self.alert = patch.object(c, 'alert').start()

    def events(self, rows, lane='A'):
        path = self.root / f'events-{lane}.jsonl'
        path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        return path

    def test_ready_boolean_and_precedence(self):
        path = self.root / 'READY.json'
        for row, expected in [({'ready_for_device': True}, True), ({'ready': True}, True),
                              ({'ready_for_device': False, 'ready': True}, False),
                              ({'ready_for_device': None, 'ready': True}, False),
                              ({'ready': 1}, False), ({'ready': 'true'}, False),
                              ({'ready_for_device': 'false'}, False),
                              ({}, False), ([], False), (True, False)]:
            with self.subTest(row=row):
                path.write_text(json.dumps(row))
                self.assertIs(c.ready(path), expected)

    def test_ready_missing_malformed_and_unreadable(self):
        path = self.root / 'READY.json'
        self.assertFalse(c.ready(path))
        for data in (b'{', b'\xff'):
            path.write_bytes(data)
            self.assertFalse(c.ready(path))
        with patch.object(Path, 'read_text', side_effect=PermissionError):
            self.assertFalse(c.ready(path))

    def test_wait_exact_job_lane_offset_and_terminal_types(self):
        for event in c.TERMINAL:
            with self.subTest(event=event):
                wanted = dict(event=event, name='target', lane='A', receipt='proof.json')
                self.events([dict(event='DONE', name='target'),
                             dict(event='START', name='target'),
                             dict(event='DONE', name='target-other'),
                             dict(event='DONE', name='target', lane='B'), wanted])
                result = c.wait_event('A', 'target', 1, time.monotonic() + 10)
                self.assertEqual(result, wanted)
        self.systemctl.assert_not_called()

    def test_wait_partial_line_then_append(self):
        path = self.events([dict(event='START', name='target')])
        with path.open('a') as stream:
            stream.write('{"event":"REFUSED-PREDEVICE","name":"target"')
        def append(_):
            with path.open('a') as stream:
                stream.write('}\n')
        with patch.object(c, 'driver_alive', return_value=True), patch.object(c.time, 'sleep', side_effect=append):
            row = c.wait_event('A', 'target', 0, time.monotonic() + 10)
        self.assertEqual(row['event'], 'REFUSED-PREDEVICE')

    def test_wait_missing_log_can_be_created(self):
        with patch.object(c, 'driver_alive', return_value=True), patch.object(c.time, 'sleep',
                side_effect=lambda _: self.events([dict(event='DONE', name='target')])):
            self.assertEqual(c.wait_event('A', 'target', 0, time.monotonic() + 10)['event'], 'DONE')

    def test_wait_deadline_and_capped_sleep(self):
        clock = [10.0]
        sleeps = []
        def sleep(seconds):
            sleeps.append(seconds)
            clock[0] += seconds
        with patch.object(c, 'driver_alive', return_value=True), \
             patch.object(c.time, 'monotonic', side_effect=lambda: clock[0]), \
             patch.object(c.time, 'sleep', side_effect=sleep):
            with self.assertRaises(TimeoutError):
                c.wait_event('A', 'target', 0, 12.5, poll=2)
        self.assertEqual(sleeps, [2, .5])
        self.alert.assert_called_once()

    def test_dead_driver_fails_promptly_but_terminal_event_wins(self):
        with patch.object(c, 'driver_alive', return_value=False) as alive:
            with self.assertRaises(c.DriverUnavailable):
                c.wait_event('A', 'target', 0, time.monotonic() + 10)
            alive.assert_called_once()
            self.events([dict(event='FAILED', name='target')])
            self.assertEqual(c.wait_event('A', 'target', 0, time.monotonic() + 10)['event'], 'FAILED')
            alive.assert_called_once()

    def test_invalid_offsets_deadlines_and_log_records(self):
        for offset in (-1, True, 1.5):
            with self.assertRaises(ValueError):
                c.wait_event('A', 'job', offset, time.monotonic() + 10)
        for deadline in (None, float('inf'), float('nan'), True):
            with self.assertRaises(ValueError):
                c.wait_event('A', 'job', 0, deadline)
        path = self.events([])
        with self.assertRaisesRegex(ValueError, 'offset'):
            c.wait_event('A', 'job', 1, time.monotonic() + 10)
        for text in ('{bad}\n', '[]\n'):
            path.write_text(text)
            with self.assertRaises(ValueError):
                c.wait_event('A', 'job', 0, time.monotonic() + 10)

    def test_event_log_truncation_and_replacement_fail(self):
        for replace in (False, True):
            path = self.events([dict(event='START', name='job')])
            def change(_):
                if replace:
                    path.unlink()
                path.write_text('')
            with patch.object(c, 'driver_alive', return_value=True), patch.object(c.time, 'sleep', side_effect=change):
                with self.assertRaisesRegex(ValueError, 'replaced or truncated'):
                    c.wait_event('A', 'job', 0, time.monotonic() + 10)

    def test_driver_alive_matches_active_lane_units(self):
        self.systemctl.side_effect = None
        for output, expected in [('lanequeue-A49.service loaded active running Driver\n', True),
                                 ('lanequeue-A.service loaded active running Driver\n', True),
                                 ('lanequeue-B49.service loaded active running Driver\n', False),
                                 ('lanequeue-A49.service loaded failed failed Driver\n', False),
                                 ('', False)]:
            self.systemctl.return_value = subprocess.CompletedProcess([], 0, output, '')
            self.alert.reset_mock()
            self.assertIs(c.driver_alive('A'), expected)
            self.assertEqual(self.alert.call_count, int(not expected))

    def test_driver_status_error_alerts(self):
        for failure in (OSError(), subprocess.TimeoutExpired('systemctl', 5),
                        subprocess.CalledProcessError(1, 'systemctl')):
            self.systemctl.side_effect = failure
            self.assertFalse(c.driver_alive('B'))
        self.assertEqual(self.alert.call_count, 3)

    def test_systemctl_is_bounded_and_has_closed_stdin(self):
        with patch.object(c.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as run:
            # Exercise the actual adapter without ever invoking a service.
            SYSTEMCTL('list-units', timeout=.3)
        self.assertEqual(run.call_args.kwargs['timeout'], .3)
        self.assertIs(run.call_args.kwargs['stdin'], subprocess.DEVNULL)
        self.assertTrue(run.call_args.kwargs['check'])

    def test_hold_success_and_exception_cleanup(self):
        for exception in (None, ValueError('body failed'), KeyboardInterrupt()):
            with self.subTest(exception=exception):
                try:
                    with c.hold(['A', 'B'], 'smoke', time.monotonic() + 10) as held:
                        self.assertEqual((self.root / 'PAUSE-A').read_text(), held.text)
                        self.assertEqual((self.root / 'PAUSE-B').read_text(), held.text)
                        if exception is not None:
                            raise exception
                except BaseException as caught:
                    self.assertIs(caught, exception)
                self.assertFalse((self.root / 'PAUSE-A').exists())
                self.assertFalse((self.root / 'PAUSE-B').exists())

    def test_hold_preserves_existing_pause_and_rolls_back_partial_acquisition(self):
        (self.root / 'PAUSE-B').write_text('someone else\n')
        with self.assertRaises(FileExistsError):
            with c.hold(['A', 'B'], 'smoke', time.monotonic() + 10):
                self.fail('must not enter')
        self.assertFalse((self.root / 'PAUSE-A').exists())
        self.assertEqual((self.root / 'PAUSE-B').read_text(), 'someone else\n')

    def test_hold_preserves_replacement_even_with_same_reason(self):
        with c.hold(['A'], 'smoke', time.monotonic() + 10):
            (self.root / 'PAUSE-A').write_text('smoke\n')
        self.assertEqual((self.root / 'PAUSE-A').read_text(), 'smoke\n')

    def test_hold_freezes_only_explicit_units_and_thaws_own_units(self):
        self.systemctl.side_effect = lambda *args, **kw: subprocess.CompletedProcess(
            [], 0, 'frozen\n' if 'codex-others.service' in args else 'running\n', '')
        with c.hold(['B'], 'smoke', time.monotonic() + 10) as held:
            self.assertFalse(held.freeze('codex-others.service'))
            self.assertTrue(held.freeze('codex-ours.service'))
            self.assertTrue(held.freeze('codex-ours.service'))
            with self.assertRaises(ValueError):
                held.freeze('lanequeue-A.service')
        mutations = [call.args for call in self.systemctl.call_args_list if call.args[0] in ('freeze', 'thaw')]
        self.assertEqual(mutations, [('freeze', 'codex-ours.service'), ('thaw', 'codex-ours.service')])

    def test_hold_deadline_releases_resources_while_body_waits(self):
        self.systemctl.side_effect = lambda *a, **kw: subprocess.CompletedProcess([], 0, 'running\n', '')
        released = threading.Event()
        original = c._Hold._expire
        def expire(held):
            try:
                original(held)
            finally:
                released.set()
        with patch.object(c._Hold, '_expire', expire):
            with self.assertRaises(TimeoutError):
                with c.hold(['B'], 'smoke', time.monotonic() + .1) as held:
                    held.freeze('codex-ours.service')
                    self.assertTrue(released.wait(2), 'watchdog did not run')
                    self.assertFalse((self.root / 'PAUSE-B').exists())
                    self.systemctl.assert_any_call('thaw', 'codex-ours.service')

    def test_expired_hold_never_acquires(self):
        with self.assertRaises(TimeoutError):
            with c.hold(['A'], 'too late', time.monotonic() - 1):
                self.fail('expired hold entered')
        self.assertFalse((self.root / 'PAUSE-A').exists())

    def test_sigterm_unwinds_and_restores_handler(self):
        previous = signal.getsignal(signal.SIGTERM)
        self.systemctl.side_effect = lambda *a, **kw: subprocess.CompletedProcess([], 0, 'running\n', '')
        with self.assertRaises(SystemExit) as caught:
            with c.hold(['B'], 'smoke', time.monotonic() + 10) as held:
                held.freeze('codex-ours.service')
                signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)
        self.assertEqual(caught.exception.code, 128 + signal.SIGTERM)
        self.assertIs(signal.getsignal(signal.SIGTERM), previous)
        self.assertFalse((self.root / 'PAUSE-B').exists())
        self.systemctl.assert_any_call('thaw', 'codex-ours.service')

    def test_pause_write_failure_leaves_no_partial_pause(self):
        with patch.object(c.os, 'fsync', side_effect=OSError('write failed')):
            with self.assertRaises(OSError):
                with c.hold(['A'], 'smoke', time.monotonic() + 10):
                    self.fail('write failed but hold entered')
        self.assertFalse(list(self.root.iterdir()))

    def test_failed_wait_unwinds_hold(self):
        with patch.object(c, 'driver_alive', return_value=False):
            with self.assertRaises(c.DriverUnavailable):
                deadline = time.monotonic() + 10
                with c.hold(['B'], 'waiting for A', deadline):
                    c.wait_event('A', 'job', 0, deadline)
        self.assertFalse((self.root / 'PAUSE-B').exists())

    def test_freeze_timeout_still_thaws_on_error(self):
        def invoke(*args, **kw):
            if args[0] == 'freeze':
                raise subprocess.TimeoutExpired('freeze', 5)
            return subprocess.CompletedProcess([], 0, 'running\n', '')
        self.systemctl.side_effect = invoke
        with self.assertRaises(subprocess.TimeoutExpired):
            with c.hold(['A'], 'smoke', time.monotonic() + 10) as held:
                held.freeze('codex-ours.service')
        self.systemctl.assert_any_call('thaw', 'codex-ours.service')
        self.assertFalse((self.root / 'PAUSE-A').exists())

    def test_thaw_error_does_not_skip_remaining_cleanup(self):
        def invoke(*args, **kw):
            if args == ('thaw', 'codex-two.service'):
                raise OSError('failed')
            return subprocess.CompletedProcess([], 0, 'running\n', '')
        self.systemctl.side_effect = invoke
        with self.assertRaises(c.CleanupError):
            with c.hold(['A', 'B'], 'smoke', time.monotonic() + 10) as held:
                held.freeze('codex-one.service')
                held.freeze('codex-two.service')
        self.systemctl.assert_any_call('thaw', 'codex-one.service')
        self.assertFalse((self.root / 'PAUSE-A').exists())
        self.assertFalse((self.root / 'PAUSE-B').exists())
        self.alert.assert_called_once()

    def test_alert_is_local_stderr(self):
        with patch('sys.stderr', new_callable=io.StringIO) as stderr:
            ALERT('no driver')
        self.assertEqual(stderr.getvalue(), 'ALERT: no driver\n')


SYSTEMCTL = c._systemctl
ALERT = c.alert

if __name__ == '__main__':
    unittest.main()
