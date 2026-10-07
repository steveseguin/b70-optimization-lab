#!/usr/bin/env python3
"""CPU controls; never delegate to the real sealed launcher."""
import errno
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import types
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('progress_overlay', HERE / 'launch_with_progress_lock.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class OverlayTests(unittest.TestCase):
    def setUp(self):
        import tqdm.std
        self.cls = tqdm.std.tqdm
        self.original = self.cls.refresh
        self.temp = tempfile.TemporaryDirectory(prefix='ltx-overlay-test-')
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.cls.refresh = self.original
        self.temp.cleanup()

    def test_installed_overlay_releases_lock_and_cannot_reapply(self):
        before = m.SOURCE.read_bytes()
        evidence = m.install()
        self.assertEqual(evidence['source_sha256'], m.SOURCE_SHA)
        lock = threading.Lock()
        def fail():
            raise OSError(errno.ENOSPC, 'synthetic full disk')
        fake = types.SimpleNamespace(disable=False, _lock=lock, display=fail)
        with self.assertRaises(OSError) as raised:
            self.cls.refresh(fake)
        self.assertEqual(raised.exception.errno, errno.ENOSPC)
        self.assertTrue(lock.acquire(timeout=0.1))
        lock.release()
        with self.assertRaisesRegex(RuntimeError, 'Loaded refresh differs'):
            m.install()
        self.assertEqual(m.SOURCE.read_bytes(), before)

    def test_foreign_loaded_function_rejected(self):
        self.cls.refresh = lambda *args: True
        with self.assertRaisesRegex(RuntimeError, 'Loaded refresh differs'):
            m.install()

    def test_candidate_hash_tamper_refused(self):
        with mock.patch.object(m, 'CANDIDATE_SHA', '0' * 64):
            with self.assertRaisesRegex(RuntimeError, 'Hash mismatch'):
                m.install()
        self.assertIs(self.cls.refresh, self.original)

    def test_source_hash_tamper_refused(self):
        with mock.patch.object(m, 'SOURCE_SHA', '0' * 64):
            with self.assertRaisesRegex(RuntimeError, 'Hash mismatch'):
                m.install()

    def test_pinned_launcher_and_arguments(self):
        args = ['--packet', str(m.PACKET), '--manifest-sha256', m.MANIFEST_SHA,
                '--run-name', 'encoder-server-size-98-two-way-w2-b1-p1-dxpu2-s256x256']
        self.assertEqual(m.validate_launcher(m.PACKET / 'launch/serve-encoder.py', args).packet, m.PACKET)
        with self.assertRaisesRegex(RuntimeError, 'Only sealed'):
            m.validate_launcher(self.root / 'serve-encoder.py', args)
        args[1] = '/tmp/unpinned'
        with self.assertRaisesRegex(RuntimeError, 'arguments differ'):
            m.validate_launcher(m.PACKET / 'launch/serve-encoder.py', args)
        with mock.patch.object(m, 'LAUNCHER_SHA', '0' * 64):
            with self.assertRaisesRegex(RuntimeError, 'Hash mismatch'):
                m.validate_launcher(m.PACKET / 'launch/serve-encoder.py', args)

    def test_fake_launcher_receives_overlay_in_same_process(self):
        m.install()
        launch = self.root / 'serve-encoder.py'
        sibling = self.root / 'synthetic_local_module.py'
        sibling.write_text('VALUE = 42\n')
        out = self.root / 'observed.json'
        launch.write_text('import os, sys, json, tqdm, synthetic_local_module\n'
                         'from pathlib import Path\n'
                         'Path(sys.argv[1]).write_text(json.dumps([os.getpid(), '
                         'tqdm.tqdm.refresh.__code__.co_filename, synthetic_local_module.VALUE, __name__]))\n')
        with mock.patch.object(sys, 'argv', list(sys.argv)), mock.patch.object(sys, 'path', list(sys.path)):
            m.delegate(launch, [str(out)])
        self.assertEqual(json.loads(out.read_text()), [os.getpid(), str(HERE / 'refresh.candidate.py'), 42, '__main__'])

    def test_receipt_exclusive_and_symlink_refusal(self):
        path = self.root / 'receipt.json'
        sha = m.write_receipt(path, {'test': True})
        self.assertEqual(sha, m.digest(path.read_bytes()))
        with self.assertRaisesRegex(RuntimeError, 'already exists'):
            m.write_receipt(path, {'test': False})
        link = self.root / 'linked'
        link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, 'ancestor is a symlink'):
            m.write_receipt(link / 'new.json', {})
        self.assertFalse((self.root / 'new.json').exists())

    def test_receipt_failure_prevents_delegation(self):
        args = ['--receipt', str(self.root / 'receipt.json'), str(m.PACKET / 'launch/serve-encoder.py'),
                '--packet', str(m.PACKET), '--manifest-sha256', m.MANIFEST_SHA,
                '--run-name', 'encoder-server-size-98-two-way-w2-b1-p1-dxpu2-s256x256']
        with mock.patch.object(m, 'write_receipt', side_effect=OSError(errno.ENOSPC, 'full')), mock.patch.object(m, 'delegate') as delegate:
            with self.assertRaises(OSError):
                m.main(args)
            delegate.assert_not_called()


if __name__ == '__main__':
    unittest.main(verbosity=2)
