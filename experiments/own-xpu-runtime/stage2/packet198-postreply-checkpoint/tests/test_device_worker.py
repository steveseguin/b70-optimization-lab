"""CPU-only checks of the actual fixed worker; device exec is always intercepted."""
import importlib.util
import io
import json
import resource
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

P = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('p198_worker_test', P / 'device_worker.py')
W = importlib.util.module_from_spec(spec); spec.loader.exec_module(W)


class WorkerTests(unittest.TestCase):
    def test_production_argv_single_owner(self):
        argv = W.native_argv()
        self.assertEqual(argv[:3], ['/usr/bin/ionice', '-c3', str(P / 'build/device/own-rt-iq3')])
        for key, value in {'--cache-cap': 'max', '--cache-bytes': '21552729600', '--context': '4096',
                           '--cards': '1', '--card': '0', '--max-new': '512', '--native-nice': '0',
                           '--request-front-max-requests': '8', '--wait-seconds': '600'}.items():
            self.assertEqual(argv.count(key), 1)
            self.assertEqual(argv[argv.index(key) + 1], value)
        for flag in ('--mini', '--pipeline-mini', '--input', '--suite-inputs', '--checkpoint-save', '--expert-gateup'):
            self.assertNotIn(flag, argv)

    def test_actual_launch_function_intercept(self):
        env = W.parent_modules()['native_env'].environment('A')
        calls = []
        sentinel = object()
        def popen(argv, **kwargs):
            calls.append((argv, kwargs)); return sentinel
        result = W.start_owner(W.native_argv(), env, io.BytesIO(), popen=popen)
        self.assertIs(result, sentinel)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], W.native_argv())
        self.assertEqual(calls[0][1]['env'], env)
        self.assertEqual(calls[0][1]['stdin'], W.subprocess.PIPE)
        self.assertNotIn('preexec_fn', calls[0][1])

    def test_finite_address_limit_refuses_before_launch(self):
        env = W.parent_modules()['native_env'].environment('A')
        module = W.parent_modules()['exec_limits']
        with patch.object(module.resource, 'getrlimit', return_value=(4*1024**3, 4*1024**3)), \
                patch.object(W.subprocess, 'Popen') as popen:
            with self.assertRaisesRegex(ValueError, 'finite RLIMIT_AS'):
                W.start_owner(W.native_argv(), env, io.BytesIO())
            popen.assert_not_called()

    def test_argv_drift_refuses_before_launch(self):
        env = W.parent_modules()['native_env'].environment('A')
        argv = W.native_argv() + ['--mini']
        with patch.object(W.subprocess, 'Popen') as popen:
            with self.assertRaisesRegex(ValueError, 'argv drift'):
                W.start_owner(argv, env, io.BytesIO())
            popen.assert_not_called()

    def test_canonical_fixture_identity(self):
        a, b, turn, reference, oracle = W.fixtures()
        self.assertEqual(len(a), 87); self.assertEqual(len(turn), 126)
        self.assertEqual(len(a) + 256 + len(turn), 469)
        self.assertGreaterEqual(len(reference['incident-retrospective']['tokens']), 384)
        self.assertEqual(reference['incident-retrospective']['tokens'][:128], oracle[:128])
        self.assertTrue(b)

    def test_bounded_journal_runner(self):
        with patch.object(W.subprocess, 'run') as run:
            W.bounded_journal_run(['journal-fixture'], capture_output=True, text=True)
            self.assertEqual(run.call_args.kwargs['timeout'], 15)
            self.assertEqual(run.call_args.kwargs['stdin'], W.subprocess.DEVNULL)

    def test_guard_timeout_stops_intake_and_signals_once(self):
        child = unittest.mock.Mock()
        child.poll.return_value = None
        record = dict(stop_reasons=[])
        incident = W.IncidentStop(record, lambda: child)
        def failed_read(): raise W.subprocess.TimeoutExpired('journalctl-fixture', 15)
        self.assertFalse(W.guarded_poll(failed_read, incident))
        self.assertTrue(record['stop_reasons'])
        self.assertFalse(W.guarded_poll(failed_read, incident))
        incident('coordinator signal')
        child.send_signal.assert_called_once_with(W.signal.SIGTERM)
        self.assertEqual(record['incident_sigterm_count'], 1)
        child.kill.assert_not_called()

    def run_lifecycle(self, corrupt=False, halt_control=False, wrong_release=False):
        a, b, turn, reference, oracle = W.fixtures()
        calls, controls, guards = [], [], []
        with tempfile.TemporaryDirectory(prefix='p198-worker-test-') as temporary:
            output = Path(temporary)
            class Front:
                state = 'ready'
                pending = None
                def request(front, name, tokens, cap, **options):
                    self.assertEqual(front.state, 'ready')
                    self.assertNotIn('save', options)
                    calls.append(dict(id=name, tokens=tokens, cap=cap, options=options))
                    if name.startswith('append'): result = list(range(128))
                    elif name.startswith('fresh-b'): result = reference['decision-memo']['tokens'][:128]
                    elif name == 'resume-a': result = reference['incident-retrospective']['tokens'][256:384]
                    else: result = reference['incident-retrospective']['tokens'][:cap]
                    if corrupt: result = result[:-1] + [(result[-1]+1) % W.VOCAB]
                    d = output / 'owner/requests' / name; d.mkdir(parents=True)
                    cached = 342 if options.get('restore') else 0
                    W.save(d / 'result.json', dict(passed=True, tokens=result,
                        request_front_scope='experimental-postreply-owner-v2', session_reuse=bool(options.get('restore')),
                        cached_tokens=cached, checkpoint=dict(restore=dict(saved_prefix_length=cached))))
                    W.save(d / 'reset.json', dict(cached_tokens=0))
                    front.state = 'awaiting-disposition'; front.pending = name
                    return dict(tokens=result, completion=dict(save_pending=True))

                def disposition(front, operation, saving):
                    event = dict(event='checkpoint-saved' if saving else 'request-released', operation_id=operation,
                                 request_id=front.pending, request_disposed=True, request_quiesced=True,
                                 final_request=len(calls)==8)
                    front.pending = None; front.state = 'draining' if len(calls)==8 else 'ready'
                    if wrong_release and len(calls)==8: event['final_request'] = False
                    return event

                def save(front, operation, checkpoint, tokens):
                    expected = calls[-1]['tokens'] + W.read(output / 'owner/requests' / calls[-1]['id'] / 'result.json')['tokens']
                    if calls[-1]['id']=='resume-a':
                        expected = a + reference['incident-retrospective']['tokens'][:384]
                    self.assertEqual(tokens, expected)  # Resume must include the saved 256-token segment.
                    controls.append(dict(operation=operation, checkpoint=checkpoint, tokens=tokens))
                    d = output / 'checkpoints' / checkpoint; d.mkdir(parents=True)
                    W.save(d / 'manifest.json', dict(label='experimental-postreply-front', contract='v1.2+p198',
                        qualified_by=dict(device_gates=[]), engine=dict(binary_sha256=W.sha(P / 'build/device/own-rt-iq3')),
                        blobs=[dict(name='state')]))
                    (d / 'state.bin').write_bytes(b'fixture-state'); (d / 'tokens.bin').write_bytes(b'fixture-tokens')
                    event = front.disposition(operation, True); event['manifest_sha256']=W.sha(d/'manifest.json')
                    receipt = output/'owner/operations'/operation; receipt.mkdir(parents=True)
                    W.save(receipt/'save.json', event)
                    return event

                def release(front, operation):
                    controls.append(dict(operation=operation))
                    return front.disposition(operation, False)

            def guard():
                guards.append((len(calls), len(controls)))
                if halt_control and len(guards)==3: raise RuntimeError('fault before postreply save')
            if corrupt:
                with self.assertRaisesRegex(ValueError, 'A parent prefix mismatch'):
                    W.lifecycle(Front(), output, guard, lambda rows: None)
                self.assertEqual(len(calls), 1); self.assertFalse(controls)
            elif halt_control:
                with self.assertRaisesRegex(RuntimeError, 'fault before postreply save'):
                    W.lifecycle(Front(), output, guard, lambda rows: None)
                self.assertEqual(len(calls), 1); self.assertFalse(controls)
            elif wrong_release:
                with self.assertRaisesRegex(ValueError, 'disposition identity'):
                    W.lifecycle(Front(), output, guard, lambda rows: None)
            else:
                correctness, states, events = W.lifecycle(Front(), output, guard, lambda rows: None)
                self.assertTrue(all(correctness.values()))
                self.assertEqual([r['id'] for r in calls], W.IDS)
                self.assertEqual([r['operation'] for r in controls], W.CONTROLS)
                self.assertEqual(len(guards), 32)
                self.assertEqual(sum(r['cap'] for r in calls), 1408)
                self.assertEqual(sum('checkpoint' in c for c in controls), 5)
                self.assertEqual(states['s3'], states['s4']); self.assertEqual(states['s4'], states['s5'])
                self.assertEqual(controls[2]['tokens'], a+reference['incident-retrospective']['tokens'][:384])
                stopped = dict(event='stopped', safe_to_exit=True, reason='request-limit', completed_requests=8,
                               completed_controls=8, discarded_pending=False, pending_request_id='')
                W.verify_stopped(stopped, events)
                for key,value in [('completed_controls',7),('discarded_pending',True),('reason','quit'),('pending_request_id','fresh-b-repeat')]:
                    with self.subTest(key=key), self.assertRaises(ValueError): W.verify_stopped(dict(stopped, **{key:value}), events)

    def test_eight_replies_then_five_saves_three_releases(self): self.run_lifecycle()
    def test_corruption_stops_before_first_save(self): self.run_lifecycle(corrupt=True)
    def test_fault_after_reply_prevents_save_and_next_request(self): self.run_lifecycle(halt_control=True)
    def test_final_release_identity_required(self): self.run_lifecycle(wrong_release=True)


if __name__ == '__main__': unittest.main()

