"""CPU subprocess protocol tests. The mock never imports native/device code."""
import subprocess
import sys
import tempfile
import time
import unittest

from client import NativeFront, encode_request


MOCK = r'''
import json, sys, time
mode = sys.argv[1]
def event(**row): print(json.dumps(row), flush=True)
limit = 1 if mode == 'limit' else 10
event(event='ready', protocol='ownrt.request-front.v1', model_loads=1, experimental=True,
      context=4095 if mode == 'geometry' else 4096, vocab=248064, max_requests=limit)
completed = 0
for line in sys.stdin:
    if line == 'QUIT\n':
        event(event='stopped', reason='quit', safe_to_exit=True, completed_requests=completed)
        sys.exit(0)
    _, rid, cap, restore, save, ids = line.rstrip('\n').split('\t')
    if mode == 'fatal':
        event(event='fatal', error='mock engine fault')
        sys.exit(1)
    event(event='request-start', id=rid)
    if mode == 'stall': time.sleep(20)
    if mode == 'eof': sys.exit(0)
    event(event='token', id=('foreign' if mode == 'foreign' else rid),
          index=(1 if mode == 'index' else 0), token_id=17)
    event(event='request-complete', id=rid,
          result=('outside/result.json' if mode == 'path' else 'requests/'+rid+'/result.json'),
          generated_tokens=2 if mode == 'count' else 1, owner_resident=True,
          request_quiesced=False if mode == 'busy' else True)
    completed += 1
    if completed == limit:
        event(event='stopped', reason='request-limit', safe_to_exit=True, completed_requests=completed)
        sys.exit(0)
'''


class ClientTests(unittest.TestCase):
    def owner(self, mode='ok', timeout=2):
        log = tempfile.TemporaryFile()
        proc = subprocess.Popen([sys.executable, '-u', '-c', MOCK, mode],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log)
        def cleanup():
            # This is exclusively the CPU mock, never a native/device owner.
            if proc.poll() is None:
                proc.terminate()
            proc.wait(timeout=3)
            proc.stdin.close()
            proc.stdout.close()
            log.close()
        self.addCleanup(cleanup)
        front = NativeFront(proc, context=4096, vocab=248064, max_requests=1 if mode == 'limit' else 10,
                            request_timeout=timeout)
        self.addCleanup(front.selector.close)
        return front

    def test_sequential_owner_and_graceful_quit(self):
        front = self.owner()
        pid = front.process.pid
        self.assertEqual(front.ready['model_loads'], 1)
        for rid, restore, save in [('a', None, 's1'), ('b', None, None), ('c', 's1', 's2')]:
            observed = []
            row = front.request(rid, [1, 2, 3], 8, restore=restore, save=save, on_token=observed.append)
            self.assertEqual(row['tokens'], [17])
            self.assertEqual(observed, [17])
            self.assertEqual(front.process.pid, pid)
        self.assertTrue(front.close()['safe_to_exit'])
        self.assertEqual(front.state, 'closed')

    def test_duplicate_refused_without_poisoning_owner(self):
        front = self.owner()
        front.request('a', [2], 1)
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            front.request('a', [2], 1)
        self.assertEqual(front.state, 'ready')
        front.close()

    def test_bad_frames_refused_before_submission(self):
        for patch in ({'request_id': '../x'}, {'request_id': 'a\nb'}, {'save': 's.lock'},
                      {'tokens': [True]}, {'tokens': [-1]}, {'tokens': [20]},
                      {'tokens': []}, {'max_new': 513}, {'max_new': True},
                      {'context': 2}, {'restore': 'a', 'save': 'a'}):
            args = dict(request_id='a', tokens=[1, 2], max_new=2, context=32, vocab=20)
            args.update(patch)
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                encode_request(**args)

    def test_protocol_failures_halt_all_later_requests(self):
        for mode in ('fatal', 'foreign', 'index', 'path', 'eof', 'count', 'busy'):
            with self.subTest(mode=mode):
                front = self.owner(mode)
                with self.assertRaises(RuntimeError):
                    front.request('a', [1, 2], 2)
                self.assertEqual(front.state, 'halted')
                with self.assertRaisesRegex(RuntimeError, 'not ready'):
                    front.request('b', [1, 2], 2)

    def test_request_limit_drains_without_quit(self):
        front = self.owner('limit')
        front.request('a', [1], 1)
        self.assertEqual(front.state, 'draining')
        with self.assertRaisesRegex(RuntimeError, 'not ready'):
            front.request('b', [1], 1)
        self.assertEqual(front.close()['reason'], 'request-limit')

    def test_readiness_geometry_must_match(self):
        with self.assertRaisesRegex(RuntimeError, 'admission mismatch'):
            self.owner('geometry')

    def test_timeout_keeps_owner_for_incident_drain(self):
        front = self.owner('stall', timeout=.05)
        with self.assertRaises(TimeoutError):
            front.request('a', [1, 2], 2)
        self.assertIsNone(front.process.poll())
        self.assertEqual(front.state, 'halted')
        with self.assertRaisesRegex(RuntimeError, 'coordinator'):
            front.close()

    def test_buffered_completion_cannot_outlive_request_deadline(self):
        front = self.owner(timeout=.04)
        with self.assertRaises(TimeoutError):
            front.request('a', [1], 1, on_token=lambda _: time.sleep(.06))
        self.assertEqual(front.state, 'halted')


if __name__ == '__main__':
    unittest.main()
