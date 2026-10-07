"""CPU-only lifecycle tests: every process, device and service action is mocked."""
from contextlib import ExitStack, contextmanager
import json
import errno
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import durable_v3_host_runner as runner


def profile():
    return {'rung': {'tp': 2, 'mem': .95, 'max_model_len': 262144, 'batched': 832,
        'seqs': 1, 'mtp': 5, 'draft_int4': True, 'fa_verify_rows': True,
        'prefix_cache': 'align', 'image': runner.IMAGE, 'shortlist': '/pinned/list',
        'overlay': [], 'extra_env': [], 'env': [], 'serve_arg': []},
        'overlay_sha256': {'a': 'fixed'}, 'reference_sha256': 'fixed', 'guard_sha256': 'fixed'}


def strict_result():
    return {'schema': 'neural.download.strict-attempt-output-comparison.v1',
        'comparison': {'exact_prompts': 12, 'total_prompts': 12, 'complete_token_arrays_exact': True},
        'qualification': {'all_workload_and_canary_gates_passed': True, 'strict_pair_qualified': True}}


def development_result(passed=True):
    return {'schema': 'durable-pilot-summary.v3', 'protocol': 'durable-context-r3',
        'answer_generation': dict(runner.ANSWER_GENERATION),
        'ingestion_generation': dict(runner.INGESTION_GENERATION),
        'stage': 'development', 'development_gate_passed': passed,
        'quality_gate_passed': True, 'complete_planned_matrix': True, 'campaign_clean': True,
        'expected_trials': 6, 'observed_trials': 6}


class PureTests(unittest.TestCase):
    def test_strict_requires_all_qualification_flags(self):
        self.assertTrue(runner.strict_passed(strict_result()))
        for section, key in [('comparison', 'complete_token_arrays_exact'),
                             ('qualification', 'all_workload_and_canary_gates_passed'),
                             ('qualification', 'strict_pair_qualified')]:
            result = strict_result(); result[section][key] = False
            self.assertFalse(runner.strict_passed(result))
        result = strict_result(); result['schema'] = 'other'
        self.assertFalse(runner.strict_passed(result))

    def test_development_gate_requires_native_complete_clean_six(self):
        self.assertTrue(runner.development_passed(development_result()))
        for key, value in [('schema', 'durable-pilot-summary.v1'), ('protocol', 'r1'),
                           ('stage', 'holdout'), ('observed_trials', 5), ('expected_trials', 18),
                           ('quality_gate_passed', False), ('campaign_clean', False),
                           ('complete_planned_matrix', False), ('development_gate_passed', False)]:
            result = development_result(); result[key] = value
            self.assertFalse(runner.development_passed(result))

    def test_development_generation_requires_exact_keys_values_and_types(self):
        for field, key, value in [('answer_generation', 'enable_thinking', 1),
                                  ('answer_generation', 'enable_thinking', False),
                                  ('answer_generation', 'reasoning_effort', 'high'),
                                  ('answer_generation', 'max_tokens', 8192.0),
                                  ('ingestion_generation', 'enable_thinking', 0),
                                  ('ingestion_generation', 'max_tokens', 8192)]:
            result = development_result(); result[field][key] = value
            self.assertFalse(runner.development_passed(result))
        result = development_result(); result['answer_generation']['extra'] = True
        self.assertFalse(runner.development_passed(result))
        result = development_result(); del result['ingestion_generation']
        self.assertFalse(runner.development_passed(result))

    def test_profile_is_immutable_image_and_single_sequence(self):
        self.assertIn(runner.IMAGE, runner.profile_args(profile()))
        for key, value in [('image', 'mutable:latest'), ('seqs', 2), ('mtp', 1)]:
            altered = profile(); altered['rung'][key] = value
            with self.assertRaises(ValueError): runner.profile_args(altered)

    def test_pid_reuse_and_zombie_are_not_protected_owner(self):
        original = {'start_ticks': '123'}
        self.assertTrue(runner.same_process(original, {'start_ticks': '123', 'state': 'S'}))
        self.assertFalse(runner.same_process(original, {'start_ticks': '124', 'state': 'S'}))
        self.assertFalse(runner.same_process(original, {'start_ticks': '123', 'state': 'Z'}))
        self.assertFalse(runner.same_process(original, None))

    def test_process_identity_handles_spaces_in_comm(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); proc = root / '5'; proc.mkdir()
            (proc / 'stat').write_text('5 (a process) S ' + ' '.join(['0'] * 18 + ['789', '0']))
            (proc / 'cmdline').write_bytes(b'bash\0supervise.sh\0')
            self.assertEqual(runner.process_identity(5, root)['start_ticks'], '789')

    def test_added_runtime_dependency_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            launch = Path(directory) / 'launch.json'; launch.write_text('{}')
            config = {'hostname': runner.socket.gethostname(), 'previous_revision': {'artifacts': {}},
                'protected_launch': str(launch), 'dependency_sha256': {str(launch): runner.sha(launch)}}
            with patch.object(runner, 'dependencies', return_value={**config['dependency_sha256'], 'added.py': 'hash'}):
                with self.assertRaisesRegex(RuntimeError, 'inventory'): runner.verify_dependencies(config)

    def test_health_env_cannot_skip_collective_or_assertions(self):
        env = runner.health_env()
        self.assertEqual(env['XCCL_NPROC'], '2')
        self.assertEqual(env['XPU_HEALTH_SKIP_XCCL'], '0')
        self.assertEqual(env['PHYSICAL_DEVICES'], '0,1')
        self.assertEqual(env['PYTHONOPTIMIZE'], '')

    def test_release_rejects_busy_prior_units(self):
        with patch.object(runner, 'conflicting_processes', return_value=[]), \
             patch.object(runner, 'read_command', return_value=SimpleNamespace(stdout='ctx-durable-r2.service loaded active running old')):
            self.assertIn('prior protected', runner.release_reason({}))

    def test_release_allows_stopped_prior_quality_failure(self):
        for state in ('failed failed', 'inactive dead'):
            with patch.object(runner, 'conflicting_processes', return_value=[]), \
                 patch.object(runner, 'read_command', return_value=SimpleNamespace(
                     stdout='ctx-durable-r2.service loaded ' + state)) as inspect:
                self.assertIsNone(runner.release_reason({}))
                self.assertIn('ctx-durable-r2.service', inspect.call_args.args[0])



class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(); self.addCleanup(self.directory.cleanup)
        self.out = Path(self.directory.name)
        identity = profile()
        self.config = {'schema': 'durable-host-queue.v3', 'protocol': 'durable-context-r3', 'server_args': runner.profile_args(identity), 'port': 18196,
            'answer_generation': dict(runner.ANSWER_GENERATION),
            'ingestion_generation': dict(runner.INGESTION_GENERATION),
            'model': 'test-model', 'max_wait_seconds': 1,
            'expected_launch_identity': {k: identity[k] for k in ('overlay_sha256', 'reference_sha256', 'guard_sha256')}}
        runner.atomic(self.out / 'queue.json', self.config)
        runner.atomic(self.out / 'status.json', {'phase': 'prepared'})
        self.held = set(); self.calls = []; self.stop_count = 0; self.starts = 0
        self.fail_command = None; self.fail_stop = False; self.fail_ready = False
        self.strict_qualified = True; self.dev_passed = True; self.full_dev_passed = True
        self.fail_cleanup_lock = False; self.cleanup_lock_failed = False
        self.stack = ExitStack(); self.addCleanup(self.stack.close)
        def patched(name, value): self.stack.enter_context(patch.object(runner, name, value))
        @contextmanager
        def lock(path):
            self.assertNotIn(path, self.held, 'nested flock would conflict')
            if (self.fail_cleanup_lock and path == runner.MODEL_LOCK and self.starts
                    and 'pilot' in self.calls and not self.cleanup_lock_failed):
                self.cleanup_lock_failed = True
                raise BlockingIOError('model lock stolen')
            self.held.add(path)
            try: yield
            finally: self.held.remove(path)
        patched('file_lock', lock)
        patched('verify_dependencies', lambda config: None)
        patched('fault_check', lambda config, out: None)
        patched('release_reason', lambda config: None)
        def available(*args): self.assertIn(runner.STAGE_LOCK, self.held)
        patched('load_helper', lambda: SimpleNamespace(check_available=available))
        def resource(*args):
            self.assertIn(runner.MODEL_LOCK, self.held); self.assertIn(runner.STAGE_LOCK, self.held)
        patched('resource_check', resource)
        testcase = self
        class Server:
            def __init__(self, out, config):
                testcase.starts += 1
                testcase.assertIn(runner.MODEL_LOCK, testcase.held)
                testcase.assertNotIn(runner.STAGE_LOCK, testcase.held)
                self.out = out / 'server'; self.out.mkdir()
                runner.atomic(self.out / 'launch.json', identity)
            def wait_ready(self, out):
                if testcase.fail_ready: raise RuntimeError('startup failed')
            def stop(self):
                testcase.stop_count += 1
                if testcase.fail_stop: raise RuntimeError('STOP not confirmed')
                return {'stop_confirmed': True}
        patched('OwnedServer', Server)
        def command(args, name, out, config, **kwargs):
            self.calls.append(name)
            self.assertIn(runner.HOST_LOCK, self.held)
            if name.endswith('health'):
                self.assertIn(runner.STAGE_LOCK, self.held)
                self.assertIn(runner.MODEL_LOCK, self.held)
                self.assertEqual(kwargs['env'], runner.health_env())
            elif name.startswith('strict'):
                self.assertIn(runner.MODEL_LOCK, self.held)
            else:
                self.assertNotIn(runner.MODEL_LOCK, self.held)
            if name == self.fail_command: raise RuntimeError(name + ' failure')
            if name == 'strict-compare':
                result = strict_result(); result['qualification']['strict_pair_qualified'] = self.strict_qualified
                runner.atomic(out / 'strict-comparison.json', result)
            if name == 'development':
                target = out / 'development'; target.mkdir()
                runner.atomic(target / 'summary.json', development_result(self.full_dev_passed))
            if name.startswith('extract-'):
                target = out / ('extraction-' + name.removeprefix('extract-')); target.mkdir()
                runner.atomic(target / 'result.json', {'gate_passed': self.dev_passed})
        patched('monitored_command', command)
        patched('STOP_REQUESTED', False)
        patched('status', self.write_status)

    def write_status(self, out, phase, **details):
        runner.atomic(out / 'status.json', {'phase': phase, **details})

    def phase(self): return json.loads((self.out / 'status.json').read_text())['phase']

    def test_success_lock_order_and_single_server(self):
        runner.execute(self.out)
        self.assertEqual(self.starts, 1); self.assertEqual(self.stop_count, 1)
        self.assertEqual(self.phase(), 'completed')
        self.assertEqual(self.calls, ['preflight-health', 'strict', 'strict-compare',
            'extract-report', 'extract-dispatch', 'development', 'pilot', 'postflight-health'])
        self.assertTrue((self.out / 'cards-released.json').exists())

    def test_dev_failure_preserves_stop_receipt_and_never_runs_holdout(self):
        self.fail_command = 'extract-report'
        with self.assertRaisesRegex(RuntimeError, 'extract-report'): runner.execute(self.out)
        self.assertEqual(self.phase(), 'failed'); self.assertEqual(self.stop_count, 1)
        self.assertNotIn('pilot', self.calls); self.assertNotIn('postflight-health', self.calls)
        self.assertTrue((self.out / 'server-stop.json').exists())
        self.assertTrue((self.out / 'cards-released.json').exists())

    def test_full_development_failure_never_runs_holdout(self):
        self.full_dev_passed = False
        with self.assertRaisesRegex(RuntimeError, 'full development quality'): runner.execute(self.out)
        self.assertIn('development', self.calls); self.assertNotIn('pilot', self.calls)
        self.assertEqual(self.stop_count, 1)
        self.assertTrue((self.out / 'development/summary.json').exists())

    def test_startup_failure_stops_once(self):
        self.fail_ready = True
        with self.assertRaisesRegex(RuntimeError, 'startup failed'): runner.execute(self.out)
        self.assertEqual(self.stop_count, 1); self.assertNotIn('strict', self.calls)

    def test_failed_strict_gate_does_not_reach_development(self):
        self.strict_qualified = False
        with self.assertRaisesRegex(RuntimeError, 'strict standing-reference'): runner.execute(self.out)
        self.assertNotIn('extract-report', self.calls); self.assertEqual(self.stop_count, 1)

    def test_failed_development_gate_does_not_reach_holdout(self):
        self.dev_passed = False
        with self.assertRaisesRegex(RuntimeError, 'development gate failed'): runner.execute(self.out)
        self.assertNotIn('pilot', self.calls); self.assertEqual(self.stop_count, 1)

    def test_stop_failure_never_retries_stop_or_health(self):
        self.fail_stop = True
        with self.assertRaisesRegex(RuntimeError, 'STOP not confirmed'): runner.execute(self.out)
        self.assertEqual(self.stop_count, 1); self.assertEqual(self.phase(), 'cleanup-failed')
        self.assertNotIn('postflight-health', self.calls)

    def test_cleanup_lock_conflict_still_requests_one_stop(self):
        self.fail_cleanup_lock = True
        with self.assertRaisesRegex(BlockingIOError, 'model lock stolen'): runner.execute(self.out)
        self.assertEqual(self.stop_count, 1); self.assertEqual(self.phase(), 'cleanup-failed')
        self.assertTrue((self.out / 'server-stop.json').exists())

    def test_postflight_failure_is_terminal_failed(self):
        self.fail_command = 'postflight-health'
        with self.assertRaisesRegex(RuntimeError, 'postflight-health'): runner.execute(self.out)
        self.assertEqual(self.phase(), 'failed'); self.assertEqual(self.stop_count, 1)

    def test_drift_prevents_any_launch(self):
        with patch.object(runner, 'verify_dependencies', side_effect=RuntimeError('source drift')):
            with self.assertRaisesRegex(RuntimeError, 'source drift'): runner.execute(self.out)
        self.assertEqual(self.starts, 0); self.assertEqual(self.calls, [])
        self.assertEqual(self.phase(), 'failed')

    def test_marker_rechecked_after_coordinator_lock(self):
        @contextmanager
        def racing_lock(path):
            self.held.add(path)
            if path == runner.HOST_LOCK: runner.atomic(self.out / 'execution-started.json', {'other': True})
            try: yield
            finally: self.held.remove(path)
        with patch.object(runner, 'file_lock', racing_lock):
            with self.assertRaisesRegex(RuntimeError, 'already executed'): runner.execute(self.out)
        self.assertEqual(self.starts, 0)


class PortHandoffTests(unittest.TestCase):
    def test_transient_port_teardown_waits_without_device_actions(self):
        helper = SimpleNamespace(check_available=Mock(side_effect=[
            OSError(errno.EADDRINUSE, 'teardown'), None]))
        with patch.object(runner.time, 'sleep') as sleep, patch.object(runner, 'fault_check') as faults:
            runner.wait_available({'port': 18196}, Path('/unused'), helper)
        self.assertEqual(helper.check_available.call_count, 2)
        sleep.assert_called_once_with(3)
        faults.assert_called_once()

    def test_persistent_port_and_unrelated_errors_fail_closed(self):
        helper = SimpleNamespace(check_available=Mock(side_effect=OSError(errno.EADDRINUSE, 'occupied')))
        with patch.object(runner.time, 'monotonic', side_effect=[0, 181]):
            with self.assertRaisesRegex(RuntimeError, 'did not release'):
                runner.wait_available({'port': 18196}, Path('/unused'), helper)
        helper.check_available.side_effect = OSError(errno.EACCES, 'not allowed')
        with self.assertRaises(OSError):
            runner.wait_available({'port': 18196}, Path('/unused'), helper)



class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.prior = self.root / 'previous'; self.prior.mkdir()
        (self.prior / 'server').mkdir()
        self.boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        runner.atomic(self.prior / 'queue.json', {'boot_id': self.boot, 'prepared_at': '2026-10-07T00:00:00Z'})
        runner.atomic(self.prior / 'status.json', {'phase': 'failed'})
        (self.prior / 'lifecycle.jsonl').write_text('preserved evidence\n')
        state = {'boot_id': self.boot, 'stop_confirmed': True, 'owner_pid': 4,
                 'container_id': 'old', 'image_id': runner.IMAGE}
        runner.atomic(self.prior / 'server-stop.json', state)
        runner.atomic(self.prior / 'server/state.json', state)
        runner.atomic(self.prior / 'server/launch.json', profile())
        runner.atomic(self.prior / 'cards-released.json', {'verified': True})

    def test_fresh_revision_prepare_is_passive_and_preserves_receipts(self):
        stack = ExitStack(); self.addCleanup(stack.close)
        for lock in ('HOST_LOCK', 'MODEL_LOCK', 'STAGE_LOCK'):
            stack.enter_context(patch.object(runner, lock, self.root / lock))
        stack.enter_context(patch.object(runner.socket, 'gethostname', return_value='steve-TURIND8-2L2T'))
        stack.enter_context(patch.object(runner, 'dependencies', return_value={'frozen': 'hash'}))
        stack.enter_context(patch.object(runner, 'release_reason', return_value=None))
        stack.enter_context(patch.object(runner, 'load_helper', return_value=SimpleNamespace(check_available=Mock())))
        stack.enter_context(patch.object(runner, 'resource_check'))
        stack.enter_context(patch.object(runner, 'fault_check'))
        launch = self.prior / 'server/launch.json'; out = self.root / 'new'
        with patch.object(runner, 'monitored_command') as commands, patch.object(runner, 'OwnedServer') as servers:
            result = runner.prepare(out, self.prior, launch)
            commands.assert_not_called(); servers.assert_not_called()
        self.assertEqual(result['schema'], 'durable-host-queue.v3')
        self.assertEqual(result['protocol'], 'durable-context-r3')
        self.assertEqual(result['fault_baseline_at'], '2026-10-07T00:00:00Z')
        self.assertNotIn('previous_prelaunch_failure', result)
        for path, digest in result['previous_revision']['artifacts'].items():
            self.assertEqual(runner.sha(path), digest)
        self.assertEqual(json.loads((out / 'status.json').read_text())['phase'], 'prepared')

    def test_previous_boot_or_missing_release_refused(self):
        runner.previous_receipts(self.prior)
        runner.atomic(self.prior / 'cards-released.json', {'verified': False})
        with self.assertRaisesRegex(RuntimeError, 'consistent stop'): runner.previous_receipts(self.prior)
        runner.atomic(self.prior / 'cards-released.json', {'verified': True})
        state = json.loads((self.prior / 'server-stop.json').read_text()); state['boot_id'] = 'other'
        runner.atomic(self.prior / 'server-stop.json', state)
        with self.assertRaisesRegex(RuntimeError, 'different boot'): runner.previous_receipts(self.prior)

    def test_failed_status_links_existing_results(self):
        out = self.root / 'results'; (out / 'development').mkdir(parents=True)
        runner.atomic(out / 'development/summary.json', development_result(False))
        runner.status(out, 'failed', error='development gate failed')
        result = json.loads((out / 'status.json').read_text())
        self.assertEqual(result['available_results']['development'], str(out / 'development/summary.json'))


if __name__ == '__main__': unittest.main()
