#!/usr/bin/env python3
"""CPU-only regression for the isolated, exact installed tqdm refresh source."""
import ast
import errno
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import textwrap
import threading
import types
import unittest


HERE = Path(__file__).resolve().parent
IDENTITY = json.loads((HERE / 'identity.json').read_text())


def load_method(filename):
    namespace = {}
    exec(compile((HERE / filename).read_text(), filename, 'exec'), namespace)
    return namespace['refresh']


ORIGINAL = load_method('refresh.original.py')
CANDIDATE = load_method('refresh.candidate.py')


class Lock:
    def __init__(self, allow=True):
        self.allow = allow
        self.events = []
        self.raw = threading.Lock()

    def acquire(self, *args):
        self.events.append(('acquire', args))
        return self.raw.acquire(*args) if self.allow else False

    def release(self):
        self.events.append(('release',))
        self.raw.release()


def bar(lock=None, error=None, disabled=False):
    value = types.SimpleNamespace(disable=disabled, _lock=lock or Lock(), calls=0)

    def display():
        value.calls += 1
        if error is not None:
            raise error

    value.display = display
    return value


def other_thread_can_acquire(lock):
    outcome = []

    def worker():
        acquired = lock.raw.acquire(timeout=0.1)
        outcome.append(acquired)
        if acquired:
            lock.raw.release()

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join(timeout=2)
    if thread.is_alive():
        raise AssertionError('bounded CPU acquisition test did not finish')
    return outcome == [True]


class ProgressLockRegression(unittest.TestCase):
    def test_source_and_patch_binding(self):
        original = (HERE / 'std.py.original').read_bytes()
        self.assertEqual(hashlib.sha256(original).hexdigest(), IDENTITY['source_sha256'])
        tree = ast.parse(original)
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'tqdm')
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'refresh')
        lines = original.decode().splitlines(keepends=True)
        extracted = textwrap.dedent(''.join(lines[method.lineno - 1:method.end_lineno]))
        self.assertEqual(extracted, (HERE / 'refresh.original.py').read_text())
        self.assertEqual(hashlib.sha256((HERE / 'progress-lock.patch').read_bytes()).hexdigest(),
                         IDENTITY['patch_sha256'])
        # Apply to a disposable source copy, never the installed package.
        with tempfile.TemporaryDirectory(prefix='ltx-progress-lock-') as tmp:
            target = Path(tmp) / 'tqdm/std.py'
            target.parent.mkdir()
            target.write_bytes(original)
            result = subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-i',
                                     str(HERE / 'progress-lock.patch')], cwd=tmp,
                                    capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(),
                             IDENTITY['candidate_full_source_sha256'])
            patched_tree = ast.parse(target.read_bytes())
            patched_cls = next(n for n in patched_tree.body if isinstance(n, ast.ClassDef)
                               and n.name == 'tqdm')
            patched_method = next(n for n in patched_cls.body if isinstance(n, ast.FunctionDef)
                                  and n.name == 'refresh')
            patched_lines = target.read_text().splitlines(keepends=True)
            self.assertEqual(textwrap.dedent(''.join(
                patched_lines[patched_method.lineno - 1:patched_method.end_lineno])),
                (HERE / 'refresh.candidate.py').read_text())

    def test_original_reproduces_enospc_lock_leak(self):
        error = OSError(errno.ENOSPC, 'synthetic full disk')
        value = bar(error=error)
        try:
            with self.assertRaises(OSError) as caught:
                ORIGINAL(value)
            self.assertIs(caught.exception, error)
            self.assertFalse(other_thread_can_acquire(value._lock))
            self.assertEqual(value._lock.events, [('acquire', ())])
        finally:
            if value._lock.raw.locked():
                value._lock.raw.release()

    def test_candidate_enospc_releases_lock_and_next_refresh_works(self):
        error = OSError(errno.ENOSPC, 'synthetic full disk')
        value = bar(error=error)
        with self.assertRaises(OSError) as caught:
            CANDIDATE(value)
        self.assertIs(caught.exception, error)
        self.assertTrue(other_thread_can_acquire(value._lock))
        value.display = lambda: None
        self.assertIs(CANDIDATE(value), True)
        self.assertEqual(value._lock.events,
                         [('acquire', ()), ('release',), ('acquire', ()), ('release',)])

    def test_success_modes_match_original(self):
        for kwargs in ({}, {'nolock': True}, {'lock_args': (False,)},
                       {'lock_args': (True, 0.1)}, {'lock_args': ()}):
            with self.subTest(kwargs=kwargs):
                before, after = bar(), bar()
                self.assertEqual(ORIGINAL(before, **kwargs), CANDIDATE(after, **kwargs))
                self.assertEqual(before.calls, after.calls)
                self.assertEqual(before._lock.events, after._lock.events)
                self.assertFalse(after._lock.raw.locked())

    def test_rejected_nonblocking_acquire_does_not_display_or_release(self):
        for function in (ORIGINAL, CANDIDATE):
            value = bar(Lock(allow=False))
            self.assertIs(function(value, lock_args=(False,)), False)
            self.assertEqual(value.calls, 0)
            self.assertEqual(value._lock.events, [('acquire', (False,))])

    def test_disabled_uses_no_display_or_lock(self):
        for function in (ORIGINAL, CANDIDATE):
            value = bar(disabled=True)
            self.assertIsNone(function(value))
            self.assertEqual(value.calls, 0)
            self.assertEqual(value._lock.events, [])

    def test_nolock_exception_does_not_release_callers_lock(self):
        for function in (ORIGINAL, CANDIDATE):
            value = bar(error=OSError(errno.ENOSPC, 'synthetic full disk'))
            value._lock.raw.acquire()
            try:
                with self.assertRaises(OSError):
                    function(value, nolock=True, lock_args=(False,))
                self.assertTrue(value._lock.raw.locked())
                self.assertEqual(value._lock.events, [])
            finally:
                value._lock.raw.release()

    def test_acquired_lock_args_exception_releases_once(self):
        value = bar(error=OSError(errno.ENOSPC, 'synthetic full disk'))
        with self.assertRaises(OSError):
            CANDIDATE(value, lock_args=(False,))
        self.assertEqual(value._lock.events, [('acquire', (False,)), ('release',)])
        self.assertTrue(other_thread_can_acquire(value._lock))

    def test_baseexception_also_releases(self):
        value = bar(error=KeyboardInterrupt())
        with self.assertRaises(KeyboardInterrupt):
            CANDIDATE(value)
        self.assertTrue(other_thread_can_acquire(value._lock))

    def test_actual_tqdm_normal_rendering_matches(self):
        import tqdm
        self.assertEqual(tqdm.__version__, IDENTITY['version'])
        outputs = []
        for method in (ORIGINAL, CANDIDATE):
            class LocalBar(tqdm.tqdm):
                monitor_interval = 0
                refresh = method

            target = io.StringIO()
            with LocalBar(total=3, file=target, mininterval=0, miniters=1,
                          bar_format='{n_fmt}/{total_fmt}', disable=False,
                          dynamic_ncols=False) as progress:
                progress.update(1)
                progress.refresh()
                progress.update(2)
            outputs.append(target.getvalue())
        self.assertEqual(outputs[0], outputs[1])
        self.assertIn('3/3', outputs[1])


if __name__ == '__main__':
    unittest.main(verbosity=2)
