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
spec = importlib.util.spec_from_file_location('p197_worker_test', P / 'device_worker.py')
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

    def run_lifecycle(self, corrupt=False, halt=False):
        a, b, turn, reference, oracle = W.fixtures()
        calls, guards, progress = [], [], []
        with tempfile.TemporaryDirectory(prefix='p197-worker-test-') as temporary:
            output = Path(temporary)
            class Front:
                def request(self, name, tokens, cap, **options):
                    calls.append(dict(id=name, tokens=tokens, cap=cap, options=options))
                    if name.startswith('append'):
                        result = list(range(128))
                    elif name.startswith('fresh-b'):
                        result = reference['decision-memo']['tokens'][:128]
                    elif name == 'resume-a':
                        result = reference['incident-retrospective']['tokens'][256:384]
                    else:
                        result = reference['incident-retrospective']['tokens'][:cap]
                    if corrupt:
                        result = result[:-1] + [(result[-1] + 1) % W.VOCAB]
                    directory = output / 'owner/requests' / name; directory.mkdir(parents=True)
                    cached = 342 if options.get('restore') else 0
                    W.save(directory / 'result.json', dict(passed=True, tokens=result,
                        request_front_scope='experimental-warm-owner-v1', session_reuse=bool(options.get('restore')),
                        cached_tokens=cached, checkpoint=dict(restore=dict(saved_prefix_length=cached))))
                    W.save(directory / 'reset.json', dict(cached_tokens=0))
                    if options.get('save'):
                        folder = output / 'checkpoints' / options['save']; folder.mkdir(parents=True)
                        W.save(folder / 'manifest.json', dict(label='experimental-warm-front', contract='v1.2+p197',
                            qualified_by=dict(device_gates=[]), engine=dict(binary_sha256=W.sha(P / 'build/device/own-rt-iq3')),
                            blobs=[dict(name='state')]))
                        (folder / 'state.bin').write_bytes(b'fixture-state'); (folder / 'tokens.bin').write_bytes(b'fixture-tokens')
                    return dict(tokens=result, completion=dict(request_quiesced=True))
            def guard():
                guards.append(len(calls))
                if halt:
                    raise RuntimeError('injected stop before intake')
            if corrupt:
                with self.assertRaisesRegex(ValueError, 'A parent prefix mismatch'):
                    W.lifecycle(Front(), output, guard, lambda rows: progress.append(len(rows)))
                self.assertEqual(len(calls), 1)
            elif halt:
                with self.assertRaisesRegex(RuntimeError, 'stop before intake'):
                    W.lifecycle(Front(), output, guard, lambda rows: progress.append(len(rows)))
                self.assertEqual(calls, [])
            else:
                correctness, states = W.lifecycle(Front(), output, guard, lambda rows: progress.append(len(rows)))
                self.assertTrue(all(correctness.values()))
                self.assertEqual([row['id'] for row in calls], W.IDS)
                self.assertEqual(guards, [value for n in range(8) for value in (n, n+1)])
                self.assertEqual(progress, list(range(1,9)))
                self.assertEqual([row['cap'] for row in calls], [256,128,128,128,128,128,384,128])
                self.assertEqual(calls[3]['tokens'], a + reference['incident-retrospective']['tokens'][:256] + turn)
                self.assertEqual(calls[2]['options'], dict(restore='s1', save='s2'))
                self.assertEqual(states['s3'], states['s4']); self.assertEqual(states['s4'], states['s5'])

    def test_lifecycle_real_worker_eight_request_sequence(self): self.run_lifecycle()
    def test_corruption_stops_all_later_intake(self): self.run_lifecycle(corrupt=True)
    def test_stop_guard_prevents_first_request(self): self.run_lifecycle(halt=True)


if __name__ == '__main__': unittest.main()
