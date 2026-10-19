import freeze_safe
freeze_safe.install()
"""CPU children only; exercise the native transport's actual stop/close methods."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import common as C
import conditions as K
import tp2_worker as W


def held(root):
    with (root / 'teardown.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        return False


class RefusalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.out = self.root / 'run'
        self.out.mkdir()
        self.prior = dict(boot_id=K.Teardown(self.out).boot, drained=False,
                          output='other-lane-A/K2', pid=987654)
        C.save(self.root / 'teardown-state.json', self.prior)

    def test_all_admission_errors_stop_under_lock_and_preserve_previous_record(self):
        cases = [self.prior, '{broken-json', dict(self.prior, drained=True)]
        for prior in cases:
            with self.subTest(prior=prior):
                path = self.root / 'teardown-state.json'
                path.write_text(prior if isinstance(prior, str) else json.dumps(prior))
                before = path.read_bytes()
                events = []
                test = self
                class Transport:
                    def stop(self, reason):
                        test.assertTrue(held(test.root)); events.append('stop')
                    def close(self, success):
                        test.assertTrue(held(test.root)); test.assertFalse(success)
                        events.append('exit')
                gate = lambda output, **kw: K.Teardown(output, root=self.root, **kw)
                with patch.object(W, 'Teardown', side_effect=gate):
                    with self.assertRaises((ValueError, KeyError)):
                        W.drain(Transport(), self.out, True)
                self.assertEqual(events, ['stop', 'exit'])
                self.assertEqual(path.read_bytes(), before)
                record = C.read(self.out / 'teardown.json')
                self.assertFalse(record['drained'])
                self.assertTrue(record['own_ranks_exited'])
                self.assertTrue(record['reason'])
                self.assertFalse(held(self.root))

    def test_receipt_io_error_cannot_prevent_cooperative_stop(self):
        calls = []
        class Transport:
            def stop(self, reason): calls.append('stop')
            def close(self, success): calls.append('close')
        gate = lambda output, **kw: K.Teardown(output, root=self.root, **kw)
        with patch.object(W, 'Teardown', side_effect=gate), patch.object(K, 'save', side_effect=OSError('disk full')):
            with self.assertRaisesRegex(ValueError, 'previous teardown incomplete'):
                W.drain(Transport(), self.out, True)
        self.assertEqual(calls, ['stop', 'close'])
        self.assertFalse(held(self.root))

    def test_bounded_drain_failure_keeps_original_refusal_and_false_record(self):
        test = self
        class Transport:
            def stop(self, reason): test.assertTrue(held(test.root))
            def close(self, success):
                test.assertTrue(held(test.root))
                raise TimeoutError('rank retained after bounded drain')
        gate = lambda output, **kw: K.Teardown(output, root=self.root, **kw)
        with patch.object(W, 'Teardown', side_effect=gate):
            with self.assertRaisesRegex(ValueError, 'previous teardown incomplete'):
                W.drain(Transport(), self.out, False, 'original worker failure')
        record = C.read(self.out / 'teardown.json')
        self.assertFalse(record['drained'])
        self.assertIn('bounded drain', record['stop_error'])
        self.assertFalse(held(self.root))

    def test_refused_worker_exits_and_real_stop_pipe_drains_only_its_two_children(self):
        # This subprocess is a CPU worker. Its two fake ranks poll the same
        # stop descriptor without consuming the byte, like pipeline_cancel_check.
        script = r'''
import fcntl, os, subprocess, sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, sys.argv[1])
import freeze_safe
freeze_safe.install()
import common as C, conditions as K, tp2_worker as W
sys.path.insert(0, str(C.P56))
import pipeline
root = Path(sys.argv[2]); output = root / 'run'
r, w = os.pipe()
t = pipeline.Transport.__new__(pipeline.Transport)
t.children = [subprocess.Popen([sys.executable, '-B', '-c',
    'import select,sys; select.select([int(sys.argv[1])],[],[])', str(r)], pass_fds=(r,), stdin=subprocess.DEVNULL) for _ in range(2)]
t.out = output; t.closed = False; t.stop_sent = False
t.stop_read = r; t.stop_write = w; t.failure_hook = lambda reason: None
t.mapping = SimpleNamespace(close=lambda: None)
t.shared_path = root / 'shared'; t.shared_path.touch()
t.sockets = []; t.logs = []; t.check = lambda: None
original_stop = t.stop
original_close = t.close
def under_lock():
    with (root / 'teardown.lock').open('a') as lock:
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: return
        raise AssertionError('stop/wait outside flock')
def stop(reason):
    under_lock(); return original_stop(reason)
def close(success):
    under_lock(); return original_close(success)
t.stop = stop; t.close = close
W.Teardown = lambda output, **kw: K.Teardown(output, root=root, **kw)
try:
    W.drain(t, output, True)
except ValueError:
    assert t.closed and all(p.poll() == 0 for p in t.children)
    C.save(root / 'worker-exit.json', dict(own_children_exited=True, closed=t.closed))
    sys.exit(1)
raise AssertionError('refusal disappeared')
'''
        # A third, unrelated CPU child must remain alive. Cleanup only via its
        # own pipe; this test sends no process signals at all.
        r, w = os.pipe()
        other = subprocess.Popen([sys.executable, '-B', '-c',
            'import select,sys; select.select([int(sys.argv[1])],[],[])', str(r)], pass_fds=(r,), stdin=subprocess.DEVNULL)
        try:
            start = time.process_time()
            result = freeze_safe.run([sys.executable, '-B', '-c', script, str(C.HERE), str(self.root)],
                                    capture_output=True, text=True, timeout=15, stdin=subprocess.DEVNULL)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertLess(time.process_time() - start, 10)
            self.assertIsNone(other.poll())
            self.assertTrue(C.read(self.root / 'worker-exit.json')['own_children_exited'])
            self.assertEqual(C.read(self.root / 'teardown-state.json'), self.prior)
            receipt = C.read(self.out / 'teardown.json')
            self.assertFalse(receipt['drained'])
            self.assertIn('previous teardown incomplete', receipt['reason'])
            self.assertEqual(C.read(self.out / 'ownership.json')['retained_pids'], [])
        finally:
            os.write(w, b'!'); freeze_safe.wait(other,timeout=5)
            os.close(r); os.close(w)


if __name__ == '__main__':
 import resource
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));unittest.main()
