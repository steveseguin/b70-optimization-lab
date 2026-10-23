"""Mock-only safety checks. Never calls services, HTTP, journals or device code."""
from contextlib import ExitStack
import importlib.util
import json
from pathlib import Path
import subprocess
import os
import stat
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

import window as W
import passive_device_holders as H


class WindowSafety(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.queue = self.root / 'queue'
        self.queue.mkdir()
        for lane in ('A', 'B'):
            (self.queue / f'PAUSE-{lane}').write_text('original ' + lane + '\n')
            (self.queue / f'queue-{lane}.txt').write_text('')
        (self.queue / 'events-A.jsonl').write_text('')
        self.output = self.root / 'evidence'
        self.w = W.Window(self.output, '20261023-restore24')
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(W, 'QUEUE', self.queue))

    def setup_execute(self):
        self.stack.enter_context(patch.object(W, 'check', return_value=dict(name=W.JOB, lane='A')))
        self.stack.enter_context(patch.object(W, 'sha', return_value='mock-sha'))
        self.stack.enter_context(patch.object(W, 'endpoint_idle'))
        self.stack.enter_context(patch.object(W, 'faults_clear'))
        self.stack.enter_context(patch.object(W, 'require_safe_stop'))
        self.stack.enter_context(patch.object(W, 'require_drained', return_value={'mock': True}))
        self.stack.enter_context(patch.object(W, 'active', return_value=False))
        real_read = Path.read_text
        def read(path, *args, **kwargs):
            if str(path) == '/proc/meminfo':
                return 'MemAvailable: 120000000 kB\n'
            if str(path) == '/proc/sys/kernel/random/boot_id':
                return 'mock-boot\n'
            return real_read(path, *args, **kwargs)
        self.stack.enter_context(patch.object(Path, 'read_text', read))
        def command(argv, **kwargs):
            if 'plan' in argv:
                return subprocess.CompletedProcess(argv, 0, '{"plan":"passed"}\n', '')
            return subprocess.CompletedProcess(argv, 0, '', '')
        self.cmd = self.stack.enter_context(patch.object(W, 'command', side_effect=command))
        self.restore = self.stack.enter_context(patch.object(W.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)))

    def test_success_restores_once_after_drained_and_rearms_exact_pause(self):
        self.setup_execute()
        def watch():
            (self.queue / 'queue-A.txt').write_text('')
            return dict(event='DONE', name=W.JOB)
        with patch.object(self.w, 'watch', side_effect=watch):
            self.w.execute()
        self.assertEqual(self.restore.call_count, 1)
        self.assertEqual((self.queue / 'PAUSE-A').read_text(), 'original A\n')
        self.assertEqual((self.queue / 'PAUSE-B').read_text(), 'original B\n')
        self.assertFalse((self.queue / 'STOP-A').exists())
        self.assertTrue((self.output / 'STOP-A.archived').exists())
        self.assertTrue(json.loads((self.output / 'window-result.json').read_text())['passed'])

    def test_fault_never_restores_and_retains_stop(self):
        self.setup_execute()
        with patch.object(self.w, 'watch', side_effect=RuntimeError('GPU fault')):
            with self.assertRaisesRegex(RuntimeError, 'GPU fault'):
                self.w.execute()
        self.restore.assert_not_called()
        self.assertTrue((self.queue / 'STOP-A').exists())
        self.assertEqual((self.queue / 'PAUSE-B').read_text(), 'original B\n')
        self.assertFalse(json.loads((self.output / 'window-result.json').read_text())['passed'])

    def test_postflight_failure_never_restores(self):
        self.setup_execute()
        def watch():
            (self.queue / 'queue-A.txt').write_text('')
            return dict(event='DONE', name=W.JOB)
        with patch.object(self.w, 'watch', side_effect=watch), patch.object(W, 'require_drained', side_effect=[{}, RuntimeError('owner remains')]):
            with self.assertRaisesRegex(RuntimeError, 'owner remains'):
                self.w.execute()
        self.restore.assert_not_called()
        self.assertTrue((self.queue / 'STOP-A').exists())

    def test_active_runner_stop_timeout_retains_latches(self):
        self.w.pause_a = (self.queue / 'PAUSE-A').read_bytes()
        self.w.pause_b = (self.queue / 'PAUSE-B').read_bytes()
        with patch.object(W, 'active', return_value=True), patch.object(W.time, 'monotonic', side_effect=[0, 901]):
            with self.assertRaisesRegex(RuntimeError, 'did not drain'):
                self.w.stop_boundary()
        self.assertTrue((self.queue / 'STOP-A').exists())
        self.assertEqual((self.queue / 'PAUSE-B').read_text(), 'original B\n')

    def test_event_cursor_keeps_fast_start_and_partial_line(self):
        path = self.queue / 'events-A.jsonl'
        path.write_text('{"event":"OLD"}\n')
        self.w.offset = path.stat().st_size
        with path.open('a') as f:
            f.write('{"event":"START"}\n{"event":"DO')
        self.assertEqual(self.w.next_events(), [{'event': 'START'}])
        with path.open('a') as f:
            f.write('NE"}\n')
        self.assertEqual(self.w.next_events(), [{'event': 'DONE'}])

    def test_existing_stop_is_never_removed(self):
        self.w.pause_a = (self.queue / 'PAUSE-A').read_bytes()
        self.w.pause_b = (self.queue / 'PAUSE-B').read_bytes()
        (self.queue / 'STOP-A').write_text('external incident\n')
        with patch.object(W, 'active', return_value=False):
            self.w.stop_boundary()
        self.assertFalse(self.w.stop_owned)
        self.assertEqual((self.queue / 'STOP-A').read_text(), 'external incident\n')

    def test_watch_accepts_actual_admission_wait_events_then_done(self):
        names = ('WAIT-HOST-ADMISSION', 'WAIT-OTHER-LANE-LIVE', 'WAIT-DRAIN-SPACING', 'START', 'DONE')
        events = [dict(event=name, name=W.JOB) for name in names]
        with patch.object(self.w, 'next_events', side_effect=[[event] for event in events]), \
             patch.object(self.w, 'log'), patch.object(W, 'faults_clear'), \
             patch.object(W, 'active', return_value=True), patch.object(W.time, 'sleep') as sleep:
            self.assertEqual(self.w.watch(), events[-1])
        self.assertEqual(self.w.events, events)
        self.assertEqual(sleep.call_count, 4)

    def test_watch_failure_events_are_terminal_even_without_job_name(self):
        for kind in W.TERMINAL_EVENTS:
            for named in (True, False):
                with self.subTest(event=kind, named=named):
                    row = dict(event=kind)
                    if named:
                        row['name'] = W.JOB
                    with patch.object(self.w, 'next_events', return_value=[row]), \
                         patch.object(self.w, 'log'), patch.object(W, 'faults_clear'), \
                         patch.object(W, 'active') as active, patch.object(W.time, 'sleep') as sleep:
                        with self.assertRaisesRegex(RuntimeError, 'lane stopped or failed'):
                            self.w.watch()
                    active.assert_not_called()
                    sleep.assert_not_called()

    def test_watch_rejects_unregistered_event_name(self):
        with patch.object(self.w, 'next_events', return_value=[dict(event='WAIT-HOST', name=W.JOB)]), \
             patch.object(self.w, 'log'), patch.object(W, 'faults_clear'), patch.object(W.time, 'sleep') as sleep:
            with self.assertRaisesRegex(RuntimeError, 'row did not succeed'):
                self.w.watch()
        sleep.assert_not_called()

    def test_foreign_stop_blocks_success_restore(self):
        self.setup_execute()
        def watch():
            (self.queue / 'queue-A.txt').write_text('')
            (self.queue / 'STOP-A').write_text('another coordinator incident\n')
            return dict(event='DONE', name=W.JOB)
        with patch.object(self.w, 'watch', side_effect=watch):
            with self.assertRaisesRegex(RuntimeError, 'foreign STOP-A'):
                self.w.execute()
        self.restore.assert_not_called()
        self.assertEqual((self.queue / 'STOP-A').read_text(), 'another coordinator incident\n')

    def test_replaced_owned_stop_blocks_success_restore(self):
        self.setup_execute()
        def watch():
            (self.queue / 'queue-A.txt').write_text('')
            return dict(event='DONE', name=W.JOB)
        original = self.w.stop_boundary
        def stop_and_replace():
            original()
            path = self.queue / 'STOP-A'
            path.unlink()
            path.write_text('new incident while draining\n')
        with patch.object(self.w, 'watch', side_effect=watch), patch.object(self.w, 'stop_boundary', side_effect=stop_and_replace):
            with self.assertRaisesRegex(RuntimeError, 'STOP-A changed externally'):
                self.w.execute()
        self.restore.assert_not_called()
        self.assertEqual((self.queue / 'STOP-A').read_text(), 'new incident while draining\n')

    def test_modified_owned_stop_bytes_refuse_even_same_inode(self):
        self.output.mkdir()
        self.w.pause_a = (self.queue / 'PAUSE-A').read_bytes()
        self.w.pause_b = (self.queue / 'PAUSE-B').read_bytes()
        with patch.object(W, 'active', return_value=False):
            self.w.stop_boundary()
        (self.queue / 'STOP-A').write_text('new reason\n')
        with self.assertRaisesRegex(RuntimeError, 'STOP-A changed externally'):
            self.w.archive_owned_stop()
        self.assertEqual((self.queue / 'STOP-A').read_text(), 'new reason\n')

    def test_preflight_refusal_writes_nothing(self):
        with patch.object(W, 'check', side_effect=RuntimeError('outstanding queue')):
            with self.assertRaisesRegex(RuntimeError, 'outstanding queue'):
                self.w.execute()
        self.assertFalse(self.output.exists())
        self.assertFalse((self.queue / 'STOP-A').exists())

    def test_restore_failure_is_never_retried(self):
        self.setup_execute()
        self.restore.return_value = subprocess.CompletedProcess([], 1)
        def watch():
            (self.queue / 'queue-A.txt').write_text('')
            return dict(event='DONE', name=W.JOB)
        with patch.object(self.w, 'watch', side_effect=watch):
            with self.assertRaisesRegex(RuntimeError, 'restore failed'):
                self.w.execute()
        self.assertEqual(self.restore.call_count, 1)
        self.assertTrue((self.queue / 'STOP-A').exists())


class PassiveOwnership(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.drm, self.proc = root / 'drm', root / 'proc'
        self.drm.mkdir(); self.proc.mkdir()
        dev = root / 'pci-device'
        dev.mkdir(); (dev / 'vendor').write_text('0x8086\n')
        node = self.drm / 'renderD128'
        node.mkdir(); (node / 'device').symlink_to(dev); (node / 'dev').write_text('226:128\n')
        self.fdroot = self.proc / '123' / 'fd'
        self.fdroot.mkdir(parents=True)

    def test_empty_passes_without_opening_any_device(self):
        row = H.scan(self.drm, self.proc, expected_devices=1)
        self.assertTrue(row['passed'])
        self.assertEqual(row['device_opens'], 0)

    def test_other_uid_permission_error_fails_closed(self):
        original = Path.iterdir
        def iterdir(path):
            if path == self.fdroot:
                raise PermissionError('mock other uid unreadable')
            return original(path)
        with patch.object(Path, 'iterdir', iterdir):
            row = H.scan(self.drm, self.proc, expected_devices=1)
        self.assertFalse(row['passed'])
        self.assertIn('unreadable', row['errors'][0])

    def test_holder_fails_even_if_descriptor_path_is_unusual(self):
        fd = self.fdroot / '8'; fd.write_text('mock')
        original = Path.stat
        def stat_fd(path, *args, **kwargs):
            if path == fd:
                return SimpleNamespace(st_mode=stat.S_IFCHR, st_rdev=os.makedev(226, 128))
            return original(path, *args, **kwargs)
        with patch.object(Path, 'stat', stat_fd):
            row = H.scan(self.drm, self.proc, expected_devices=1)
        self.assertFalse(row['passed'])
        self.assertEqual(row['holders'], [dict(pid=123, fd='8', node='renderD128')])

    def test_vanished_process_is_not_an_unreadable_owner(self):
        original = Path.iterdir
        def iterdir(path):
            if path == self.fdroot:
                raise FileNotFoundError('vanished')
            return original(path)
        with patch.object(Path, 'iterdir', iterdir):
            row = H.scan(self.drm, self.proc, expected_devices=1)
        self.assertTrue(row['passed'])

    def test_missing_card_refuses(self):
        row = H.scan(self.drm, self.proc)
        self.assertFalse(row['passed'])
        self.assertIn('expected 4 Intel devices', row['errors'][0])


if __name__ == '__main__':
    unittest.main()
