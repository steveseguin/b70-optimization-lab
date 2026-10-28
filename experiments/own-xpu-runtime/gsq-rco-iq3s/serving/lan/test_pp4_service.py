"""CPU HTTP admission and signal tests for the PP4-only 262K service wrapper."""
import http.client
import json
from pathlib import Path
import signal
import tempfile
import threading
import unittest
from unittest import mock

import pp4_backend as backend
import pp4_service as pp4

S = pp4.S
CHAT = S.CHAT.Chat()


class HttpAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        output = Path(self.tmp.name)
        (output / 'requests').mkdir()
        plan = dict(output=str(output), vocab=248320, context=262144, max_new=8,
                    evidence_floor_bytes=0, grace_seconds=10, speculative_depth=3,
                    full_trace_required=False, ring_trace_limit=100000,
                    request_sha256='a' * 64)
        self.engine = backend.Engine(plan, {}, {})
        self.engine.guard = mock.Mock()
        self.state = S.State()
        self.state.phase = 'ready'
        self.state.faults = []

        def fault(error):
            self.state.faults.append(error)
            self.state.phase = 'halted'

        self.state.fault = fault
        handler = pp4.make_handler(self.state, self.engine, CHAT, None)
        self.server = S.Server(('127.0.0.1', 0), handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.shutdown)

    def post(self, stream):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_address[1], timeout=10)
        body = {'messages': [{'role': 'user', 'content': 'x'}], 'max_tokens': 9, 'stream': stream}
        connection.request('POST', '/v1/chat/completions', json.dumps(body), {'Content-Type': 'application/json'})
        response = connection.getresponse()
        return response.status, response.getheader('Content-Type'), response.read()

    def test_over_cap_client_request_is_400_without_engine_or_halt(self):
        with mock.patch.object(backend.rolling, 'reset') as reset, \
             mock.patch.object(backend.bridge, 'drive') as drive:
            for stream in (False, True):
                with self.subTest(stream=stream):
                    code, content_type, raw = self.post(stream)
                    self.assertEqual(code, 400)
                    self.assertEqual(content_type, 'application/json')
                    self.assertIn('PP4 plan limit 8', json.loads(raw)['error']['message'])
        reset.assert_not_called()
        drive.assert_not_called()
        self.assertEqual(self.engine.count, 0)
        self.assertEqual(self.state.phase, 'ready')
        self.assertEqual(self.state.faults, [])
        self.assertEqual(self.state.waiting, 0)

    def test_active_sigterm_cancels_drive_and_drains_to_clean_terminal(self):
        self.engine.guard.signal_stop = threading.Event()
        self.engine.guard.failed = None
        self.engine.lock.acquire()  # model a request still in long prefill
        pp4.cooperative_stop(self.state, self.engine, signal.SIGTERM)
        self.assertEqual(self.state.phase, 'stopping')
        self.assertTrue(self.state.stop.is_set())
        self.assertTrue(self.engine.guard.signal_stop.is_set())
        self.engine.guard.failed = 'coordinator signal stop'
        pp4.handle_fault(self.state, self.engine, self.state.faults, RuntimeError('coordinator signal stop'))
        self.assertEqual(self.state.faults, [])
        processes = []
        for index in range(4):
            process = mock.Mock(pid=1000 + index)
            process.poll.return_value = 1  # native cooperative-stop status observed in run-4
            processes.append((index, process))
        self.engine.guard.tracked_processes = processes
        self.engine.guard.thread.is_alive.return_value = False
        result = self.engine.close(True)
        self.assertEqual({key: result[key] for key in
                          ('passed', 'error', 'cooperative_cancellation', 'live_pids', 'returncodes')},
                         dict(passed=True, error=None, cooperative_cancellation=True,
                              live_pids=[], returncodes={'0': 1, '1': 1, '2': 1, '3': 1}))
        self.assertEqual(pp4.exit_status(self.state.faults, result), 0)
        terminal = json.loads((Path(self.tmp.name) / 'terminal.json').read_text())
        self.assertTrue(terminal['passed'])
        self.assertIsNone(terminal['error'])

    def test_original_fault_is_not_masked_by_later_cancellation(self):
        original = RuntimeError('original native failure')
        self.engine.guard.failed = 'original native failure'
        pp4.handle_fault(self.state, self.engine, self.state.faults, original)
        self.assertEqual(self.state.faults, [original])
        self.assertEqual(self.state.phase, 'halted')
        self.engine.guard.tracked_processes = []
        self.engine.guard.thread.is_alive.return_value = False
        result = self.engine.close(False, reason=repr(original))
        self.assertFalse(result['passed'])
        self.assertEqual(result['error'], 'original native failure')
        self.assertTrue((Path(self.tmp.name) / 'incident.json').exists())


if __name__ == '__main__':
    unittest.main()
