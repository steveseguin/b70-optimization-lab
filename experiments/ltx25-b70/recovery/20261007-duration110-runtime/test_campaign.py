#!/usr/bin/env python3
"""Offline campaign lifecycle controls. Every endpoint/signal/sleep is stubbed."""
import asyncio
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import AsyncMock, Mock, patch

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))
spec = importlib.util.spec_from_file_location('resolution_campaign_review', HERE / 'campaign.py')
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)


def idle():
    return {'queue_running': 0, 'queue_pending': 0, 'preview_pending': 0,
            'preview_failures': 0, 'pipeline': {'running': 0, 'stages': {}}, 'fault': False}


class Clock:
    def __init__(self): self.now = 0
    def monotonic(self): return self.now
    def sleep(self, seconds): self.now += seconds


class CampaignControls(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.run = self.root / 'server'; self.run.mkdir()
        plan_path = HERE.parent / '20261007-duration110-plan/candidate-plan.json'
        self.plan = json.loads(plan_path.read_text())['plan']
        self.fake_client = NS(run=self.run, root=self.root, full_schedule=True,
            contract={'runtime_manifest_sha256': 'b' * 64, 'plan_path': str(plan_path),
                      'server_identity_sha256': 'c' * 64},
            contract_sha='a' * 64, identity={'pid': 123456789}, plan=self.plan,
            execute=AsyncMock(return_value={'passed': True}))
        with patch.object(C.request_client, 'Client', return_value=self.fake_client):
            self.c = C.Campaign(self.root / 'contract.json', 'a' * 64, 'b' * 64)
        self.output = io.StringIO()
        self.clock = Clock()
        self.patches = [patch.object(C, 'call', side_effect=AssertionError('No live endpoint allowed')),
                        patch.object(C.os, 'kill', side_effect=AssertionError('No real signal allowed')),
                        patch.object(C.time, 'sleep', self.clock.sleep),
                        patch.object(C.time, 'monotonic', self.clock.monotonic),
                        patch.object(C, 'emit', lambda *a: None)]
        for p in self.patches: p.start()

    def tearDown(self):
        if self.c.lock_fd is not None:
            C.os.close(self.c.lock_fd); self.c.lock_fd = None
        for p in reversed(self.patches): p.stop()
        self.tmp.cleanup()

    def status(self):
        return {'active': None, 'halted': None, 'state': idle()}

    def test_default_plan_has_zero_calls_signals_or_client_construction(self):
        with patch.object(sys, 'argv', ['campaign.py']), patch.object(C, 'Campaign') as cls, \
                contextlib.redirect_stdout(self.output):
            C.main()
        result = json.loads(self.output.getvalue())
        self.assertEqual((result['status'], result['model_requests'], result['server_actions']), ('plan-only', 0, 0))
        cls.assert_not_called(); C.call.assert_not_called(); C.os.kill.assert_not_called()

    def test_exact_57_requests_and_memory_phase_barriers(self):
        self.c.wait_idle = Mock(return_value=self.status())
        self.c.status = Mock(return_value=self.status())
        self.c.check_identity = Mock()
        log = []
        async def execute(name): log.append(('request', name))
        self.fake_client.execute = AsyncMock(side_effect=execute)
        def action_call(path, body=None, **kw):
            log.append(('action', body['action']))
            return {'passed': True, 'action': body['action']}
        with patch.object(C, 'call', side_effect=action_call): result = asyncio.run(self.c.execute())
        setup = C.schedule.build_schedule()['schedule']['rows']
        expected = [r['name'] for r in setup[:2]] + [r['name'] for r in self.plan['requests'][:20]]
        expected += [r['name'] for r in setup[2:]] + [r['name'] for r in self.plan['requests'][20:]]
        self.assertEqual(result['requests'], expected)
        self.assertEqual(len(expected), 57); self.assertEqual(len(set(expected)), 57)
        for capture_index in (3, 5):
            row = setup[capture_index]
            self.assertEqual(log[log.index(('action', row['admission_action'])) + 1], ('request', row['name']))
            self.assertEqual(log[log.index(('request', row['name'])) + 1], ('action', row['retirement_action']))
        self.assertEqual(log[log.index(('action', 'admit-decode')) + 1], ('request', setup[7]['name']))
        candidate_names = [r['name'] for r in self.plan['requests'][20:34]]
        candidate_begin = log.index(('request', candidate_names[0]))
        self.assertEqual(log[candidate_begin:candidate_begin+14], [('request', n) for n in candidate_names])
        self.assertEqual(log[candidate_begin+14], ('action', 'verify-candidate'))
        native_names = [r['name'] for r in self.plan['requests'][:20]]
        native_begin = log.index(('request', native_names[0]))
        self.assertEqual(log[native_begin:native_begin+21], [('request', native_names[0]),
            ('action', 'verify-first-native')] + [('request', n) for n in native_names[1:]])
        self.assertEqual(log[native_begin+21], ('action', 'verify-native'))
        for phase,action in [('timed-fast','verify-fast-timed')]:
            names=[r['name'] for r in self.plan['requests'] if r['phase']==phase]
            self.assertEqual(len(names),14)
            begin=log.index(('request',names[0]))
            self.assertEqual(log[begin:begin+14],[('request',n) for n in names])
            self.assertEqual(log[begin+14],('action',action))
        self.assertNotIn(('action', 'verify-timed'), log)
        self.assertNotIn('transport_trace',result)
        self.assertNotIn('diagnostic_valid',result)
        self.assertEqual(result['actions'], ['before-native', 'verify-first-native', 'verify-native', 'start-optimized',
                         'admit-capture0', 'retire-capture0-tails', 'admit-capture1',
                         'retire-capture1-tails', 'admit-decode', 'verify-candidate',
                         'start-timing', 'verify-fast-timed'])
        self.assertLess(log.index(('action', 'verify-native')), log.index(('action', 'start-optimized')))
        self.assertLess(log.index(('action', 'verify-candidate')), log.index(('action', 'start-timing')))
        C.os.kill.assert_not_called()

    def test_first_native_refusal_stops_before_second_native_without_retry(self):
        self.c.wait_idle = Mock(return_value=self.status())
        self.c.status = Mock(return_value=self.status()); self.c.check_identity = Mock()
        called=[]
        def action(path,body=None,**kw):
            called.append(body['action'])
            return {'passed': body['action']!='verify-first-native', 'action':body['action']}
        with patch.object(C,'call',side_effect=action):
            with self.assertRaisesRegex(ValueError,'Phase action did not pass'):
                asyncio.run(self.c.execute())
        self.assertEqual(called,['before-native','verify-first-native'])
        self.assertEqual(self.c.requests[-1],self.plan['requests'][0]['name'])
        self.assertEqual(len(self.c.requests),3)  # two setup plus the first native
        self.assertNotIn(self.plan['requests'][1]['name'],self.c.requests)
        self.assertEqual(self.fake_client.execute.await_count,3)
        C.os.kill.assert_not_called()

    def test_missing_first_native_receipt_stops_before_second(self):
        self.c.wait_idle = Mock(return_value=self.status())
        self.c.status = Mock(return_value=self.status()); self.c.check_identity = Mock()
        def action(path,body=None,**kw):
            if body['action']=='verify-first-native':return {'action':body['action']}
            return {'passed':True,'action':body['action']}
        with patch.object(C,'call',side_effect=action):
            with self.assertRaisesRegex(ValueError,'Phase action did not pass'):
                asyncio.run(self.c.execute())
        self.assertEqual(len(self.c.requests),3)
        self.assertNotIn('verify-first-native',self.c.actions)
        self.assertNotIn(self.plan['requests'][1]['name'],self.c.requests)
        C.os.kill.assert_not_called()

    def test_lost_first_native_barrier_response_is_never_retried(self):
        self.c.wait_idle=Mock(return_value=self.status())
        self.c.status=Mock(return_value=self.status());self.c.check_identity=Mock()
        called=[]
        def action(path,body=None,**kw):
            called.append(body['action'])
            if body['action']=='verify-first-native':raise TimeoutError('uncertain barrier response')
            return {'passed':True,'action':body['action']}
        with patch.object(C,'call',side_effect=action):
            with self.assertRaisesRegex(TimeoutError,'uncertain barrier'):
                asyncio.run(self.c.execute())
        self.assertEqual(called,['before-native','verify-first-native'])
        self.assertEqual(len(self.c.requests),3)
        self.assertNotIn(self.plan['requests'][1]['name'],self.c.requests)
        C.os.kill.assert_not_called()

    def test_model_failure_preserves_original_error(self):
        async def execute():
            self.c.owns_campaign = True
            raise RuntimeError('original model fault')
        self.c.execute = execute
        self.c.graceful_stop = Mock(side_effect=RuntimeError('GPU fault latched; preserve server'))
        with patch.object(C, 'Campaign', return_value=self.c), \
                patch.object(sys, 'argv', ['campaign.py', '--run']), \
                patch.object(C.signal, 'signal'), contextlib.redirect_stdout(self.output):
            with self.assertRaises(SystemExit): C.main()
        result = json.loads((self.run / 'resolution-campaign-result.json').read_text())
        self.assertIn('original model fault', result['error'])
        C.os.kill.assert_not_called()

    def test_failed_request_is_not_retried_and_stops_sequence(self):
        self.c.wait_idle = Mock(return_value=self.status()); self.c.status = Mock(return_value=self.status())
        self.fake_client.execute.side_effect = RuntimeError('request failed')
        with self.assertRaisesRegex(RuntimeError, 'request failed'): asyncio.run(self.c.execute())
        self.assertEqual(self.fake_client.execute.await_count, 1)
        self.assertEqual(self.c.requests, [])
        self.assertTrue(self.c.owns_campaign)

    def test_duplicate_invocation_cannot_stop_or_overwrite_receipts(self):
        (self.run / 'resolution-campaign-started.json').write_text('{}')
        with patch.object(C, 'Campaign', return_value=self.c), \
                patch.object(sys, 'argv', ['campaign.py', '--run']), \
                patch.object(C.signal, 'signal'), patch.object(C.request_client, 'write_new') as write, \
                contextlib.redirect_stdout(self.output):
            with self.assertRaises(SystemExit): C.main()
        self.c.lock_fd = None  # main closed the real temporary lock descriptor.
        self.assertFalse(self.c.owns_campaign)
        C.os.kill.assert_not_called(); C.call.assert_not_called(); write.assert_not_called()

    def test_missing_preview_or_busy_work_never_counts_as_idle(self):
        self.assertTrue(C.is_idle(idle()))
        for mutate in (lambda s: s.pop('preview_pending'), lambda s: s.pop('preview_failures'),
                       lambda s: s.update(queue_running=1), lambda s: s.update(preview_pending=1),
                       lambda s: s['pipeline'].update(running=1),
                       lambda s: s['pipeline']['stages'].update(sample={'queued_indices':[7], 'jobs':[]})):
            value = idle(); mutate(value); self.assertFalse(C.is_idle(value))

    def stop_fixture(self):
        self.c.owns_campaign = True
        self.c.lock_fd = C.os.open(self.run / 'test-lock', C.os.O_CREAT | C.os.O_RDWR, 0o600)
        self.c.status = Mock(return_value=self.status())
        self.c.check_identity = Mock()

    def test_graceful_stop_signals_once_after_two_idle_observations(self):
        self.stop_fixture()
        real_exists = Path.exists
        def exists(path): return False if str(path).startswith('/proc/') else real_exists(path)
        with patch.object(C.os, 'kill') as kill, patch.object(Path, 'exists', exists):
            result = self.c.graceful_stop()
            self.assertTrue(result['stopped'])
            kill.assert_called_once_with(123456789, C.signal.SIGINT)
            self.assertGreaterEqual(self.c.status.call_count, 2)
            with self.assertRaisesRegex(ValueError, 'one-shot'): self.c.graceful_stop()
            self.assertEqual(kill.call_count, 1)

    def test_fault_changed_pid_and_unresolved_work_never_signal(self):
        self.stop_fixture()
        (self.root / 'FAULT.json').write_text('{}')
        with self.assertRaisesRegex(RuntimeError, 'fault'): self.c.graceful_stop()
        C.os.kill.assert_not_called()
        (self.root / 'FAULT.json').unlink()
        self.c.stop_attempted = False
        self.c.check_identity.side_effect = RuntimeError('PID reused')
        with self.assertRaisesRegex(RuntimeError, 'PID reused'): self.c.graceful_stop()
        C.os.kill.assert_not_called()
        self.c.stop_attempted = False; self.c.check_identity.side_effect = None
        value = self.status(); value['state']['queue_running'] = 1
        self.c.status.return_value = value
        with self.assertRaises(TimeoutError): self.c.graceful_stop()
        C.os.kill.assert_not_called()

    def test_stop_timeout_never_escalates_or_resends_signal(self):
        self.stop_fixture()
        real_exists = Path.exists
        def exists(path): return True if str(path).startswith('/proc/') else real_exists(path)
        with patch.object(C.os, 'kill') as kill, patch.object(Path, 'exists', exists):
            with self.assertRaisesRegex(TimeoutError, 'no escalation'): self.c.graceful_stop()
            kill.assert_called_once_with(123456789, C.signal.SIGINT)
        self.assertGreaterEqual(self.clock.now, 185)
        self.assertFalse((self.run / 'resolution-stopped.json').exists())

    def test_main_success_retains_quiescent_application_without_stop_or_signal(self):
        async def execute():
            self.c.owns_campaign = True
            return {'passed': True, 'requests': ['completed-screen']}
        self.c.execute = execute
        self.c.wait_idle = Mock(return_value=self.status())
        self.c.graceful_stop = Mock(side_effect=AssertionError('Successful app must remain running'))
        with patch.object(C, 'Campaign', return_value=self.c), \
                patch.object(sys, 'argv', ['campaign.py', '--run']), \
                patch.object(C.signal, 'signal'), contextlib.redirect_stdout(self.output):
            C.main()
        result = json.loads((self.run / 'resolution-campaign-result.json').read_text())
        self.assertTrue(result['passed'])
        self.assertEqual(result['application'], {'running': True, 'available_for_reuse': True,
                                                'final_status': self.status()})
        self.assertFalse(result['stop']['stopped'])
        self.c.wait_idle.assert_called_once_with()
        self.c.graceful_stop.assert_not_called()
        C.os.kill.assert_not_called()
        self.assertFalse((self.run / 'resolution-stop-intent.json').exists())
        self.assertFalse((self.run / 'resolution-stopped.json').exists())

    def test_failed_final_observation_preserves_application_for_coordinator(self):
        async def execute():
            self.c.owns_campaign = True
            return {'passed': True}
        self.c.execute = execute
        self.c.wait_idle = Mock(side_effect=RuntimeError('final state unavailable'))
        self.c.graceful_stop = Mock(side_effect=AssertionError('Unproven state must not signal'))
        with patch.object(C, 'Campaign', return_value=self.c), \
                patch.object(sys, 'argv', ['campaign.py', '--run']), \
                patch.object(C.signal, 'signal'), contextlib.redirect_stdout(self.output):
            with self.assertRaises(SystemExit):
                C.main()
        result = json.loads((self.run / 'resolution-campaign-result.json').read_text())
        self.assertFalse(result['passed'])
        self.assertTrue(result['application']['requires_coordinator'])
        self.assertFalse(result['stop']['stopped'])
        self.c.graceful_stop.assert_not_called()
        C.os.kill.assert_not_called()

    def test_first_sigterm_during_failure_closeout_does_not_interrupt_existing_stop(self):
        handlers = {}
        def register(sig, fn): handlers[sig] = fn
        async def execute():
            self.c.owns_campaign = True
            raise RuntimeError('failed request')
        self.c.execute = execute
        def stop():
            handlers[C.signal.SIGTERM](C.signal.SIGTERM, None)
            return {'stopped': True, 'pid': 123456789}
        self.c.graceful_stop = Mock(side_effect=stop)
        with patch.object(C, 'Campaign', return_value=self.c), \
                patch.object(sys, 'argv', ['campaign.py', '--run']), \
                patch.object(C.signal, 'signal', side_effect=register), \
                contextlib.redirect_stdout(self.output):
            with self.assertRaises(SystemExit) as raised:
                C.main()
            self.assertEqual(raised.exception.code, 1)
        self.c.graceful_stop.assert_called_once()
        self.assertTrue((self.run / 'resolution-campaign-result.json').exists())
        C.os.kill.assert_not_called()


if __name__ == '__main__': unittest.main()
