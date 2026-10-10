"""CPU timing, freshness, failure and parent-path tests for packet128."""
import ast
import os
from pathlib import Path
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import run_storage as s
import integration


def require(ok, why):
    if not ok:
        raise RuntimeError(why)


class BackgroundTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.run = self.root / 'run'
        self.run.mkdir()
        self.own = s.OwnWrites(self.root, self.run, 'stream131')
        self.bg = s.BackgroundOwnWrites(self.own)
        self.addCleanup(self.bg.close)
        self.free = 100 * s.GIB
        self.mock = patch.object(s.shutil, 'disk_usage', side_effect=lambda _: SimpleNamespace(free=self.free))
        self.mock.start()
        self.addCleanup(self.mock.stop)

    def check(self):
        return self.bg.check(3*s.GIB, require)

    def test_default_is_exact_parent_path(self):
        self.assertEqual(s.launch_scan_mode({}), 'request')
        ctx = SimpleNamespace(storage_account=self.own, run_write_allowance=3*s.GIB,
                              session=SimpleNamespace(require=require))
        before = self.own.scans
        integration.Runtime.storage_check(ctx)
        self.assertEqual(self.own.scans, before + 1)

    def test_invalid_mode_refused(self):
        for value in ('', 'cached', 'BACKGROUND', 1, None):
            with self.assertRaises(ValueError):
                s.launch_scan_mode({'LTX_STORAGE_SCAN_MODE': value})

    def test_no_filesystem_walk_on_request_path_and_timing(self):
        self.bg.refresh()
        # A slow 150-ms walk is forbidden entirely, not merely hidden by a timing threshold.
        def forbidden(*a, **k):
            time.sleep(.15)
            raise AssertionError('request walked filesystem')
        with patch.object(self.own, 'allocated_bytes', side_effect=forbidden), \
             patch.object(s.os, 'scandir', side_effect=forbidden), \
             patch.object(s.os, 'stat', side_effect=forbidden):
            start = time.monotonic()
            for _ in range(100):
                self.check()
            elapsed = time.monotonic() - start
        self.assertLess(elapsed, .15, elapsed)
        self.assertEqual(self.own.scans, 1)

    def test_all_runtime_checks_use_cached_candidate(self):
        self.bg.refresh()
        self.bg.thread = SimpleNamespace(is_alive=lambda: False, join=lambda _: None)
        ctx = SimpleNamespace(storage_account=self.own, storage_background=self.bg,
                              storage_scan_mode='background', run_write_allowance=3*s.GIB,
                              session=SimpleNamespace(require=require))
        with patch.object(self.own, 'allocated_bytes', side_effect=AssertionError('walk')):
            for mutate in (True, False, True, True, False):
                row = integration.Runtime.storage_check(ctx, mutate=mutate)
                self.assertEqual(row['scan_mode'], 'background')

    def test_global_reserve_still_checked_every_call(self):
        self.bg.refresh()
        self.free = 50*s.GIB
        self.check()
        self.free -= 1
        with self.assertRaisesRegex(RuntimeError, '50 GiB reserve'):
            self.check()

    def test_headroom_is_more_conservative_than_allowance(self):
        self.bg.refresh()
        with self.bg.lock:
            self.bg.sample['consumed_bytes'] = 3*s.GIB - s.PENDING_WRITE_BYTES
        self.check()
        self.bg.sample['consumed_bytes'] += 1
        with self.assertRaisesRegex(RuntimeError, 'pending-write headroom'):
            self.check()

    def test_stale_sample_refused(self):
        self.bg.refresh()
        self.bg.sample['scan_start'] -= 2
        with self.assertRaisesRegex(RuntimeError, 'stale'):
            self.check()

    def test_scan_start_defines_age_not_completion(self):
        clock = iter((0.0, 2.0, 2.0))
        self.bg.clock = lambda: next(clock)
        self.bg.refresh()
        with self.assertRaisesRegex(RuntimeError, 'stale'):
            self.check()

    def test_scan_failure_sticky_even_after_success(self):
        self.bg.refresh()
        with patch.object(self.own, 'allocated_bytes', side_effect=RuntimeError('bad inode')):
            self.bg.refresh()
        self.bg.refresh()
        with self.assertRaisesRegex(RuntimeError, 'bad inode'):
            self.check()

    def test_missing_sample_refused(self):
        self.bg.completed_epoch = 0
        with self.assertRaisesRegex(RuntimeError, 'sample missing'):
            self.check()

    def test_blocked_periodic_scan_does_not_hold_request_lock(self):
        self.bg.refresh()
        entered, release = threading.Event(), threading.Event()
        def blocked():
            entered.set()
            release.wait(2)
            return 0
        with patch.object(self.own, 'allocated_bytes', side_effect=blocked):
            thread = threading.Thread(target=self.bg.refresh)
            thread.start()
            try:
                self.assertTrue(entered.wait(1))
                self.check()
            finally:
                release.set()
                thread.join(2)

    def test_completed_write_epoch_must_be_scanned(self):
        self.bg.start()
        (self.run/'new').write_bytes(b'x'*32768)
        self.bg.published()
        self.assertGreaterEqual(self.check()['consumed_bytes'], 32768)
        self.assertEqual(self.bg.completed_epoch, self.bg.requested_epoch)

    def test_in_place_growth_seen_on_helper(self):
        f = self.run/'log'
        f.write_bytes(b'x'*4096)
        self.bg.start()
        first = self.check()['consumed_bytes']
        with f.open('ab') as out:
            out.write(b'x'*32768)
        self.bg.published()
        self.assertGreaterEqual(self.check()['consumed_bytes']-first, 32768)

    def test_symlink_error_propagates_from_helper(self):
        self.bg.start()
        (self.run/'bad').symlink_to(self.root/'absent')
        self.bg.published()
        with self.assertRaisesRegex(RuntimeError, 'symlink'):
            self.check()

    def test_preview_notification_follows_atomic_publication(self):
        src = Path(integration.__file__).read_text()
        fn = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name=='_commit_preview')
        text = ast.get_source_segment(src, fn)
        self.assertLess(text.index('write_record_atomic('), text.index('storage_background.published()'))
        self.assertNotIn('storage_background.check', text)

    def test_no_stream_helper_before_qualification(self):
        src = Path(integration.__file__).read_text()
        self.assertEqual(src.count('self.storage_background.start()'), 1)
        self.assertLess(src.index("if not verdict['passed']:"), src.index('self.storage_background.start()'))

    def test_preview_fsync_already_separate_fifo(self):
        import stream_preview
        src = Path(stream_preview.__file__).read_text()
        self.assertIn("target=self._loop", src)
        self.assertIn('info = self.save_fn(job)', src)
        self.assertIn('record = self.commit_fn(job, record)', src)
        self.assertIn('os.fsync(fd)', src)
        self.assertIn('_rename_exclusive(tmp, final)', src)


    def test_initial_scan_failure_is_sticky_without_retry(self):
        with patch.object(self.own, 'allocated_bytes', side_effect=RuntimeError('initial scan failed')) as spy:
            self.bg.start()
            self.assertEqual(spy.call_count, 1)
            self.assertFalse(self.bg.thread.is_alive())
            with self.assertRaisesRegex(RuntimeError, 'initial scan failed'):
                self.check()

    def test_completed_epoch_timeout_fails_closed(self):
        self.bg.refresh()
        self.bg.published()
        with patch.object(self.bg.lock, 'wait_for', return_value=False):
            with self.assertRaisesRegex(RuntimeError, 'completion timeout'):
                self.check()

    def test_free_space_is_observed_after_epoch_wait(self):
        self.bg.refresh()
        def complete_then_drop(*args, **kwargs):
            self.free = 49*s.GIB
            return True
        with patch.object(self.bg.lock, 'wait_for', side_effect=complete_then_drop):
            with self.assertRaisesRegex(RuntimeError, '50 GiB reserve'):
                self.check()
