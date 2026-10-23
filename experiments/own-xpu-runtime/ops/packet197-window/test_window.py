"""Dry interception tests: no HTTP, service, privileged command or device execution."""
from contextlib import ExitStack
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import window as W
import restore_guard as R
S = W.S


class LifecycleWindow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.queue = self.root / 'queue'; self.queue.mkdir()
        self.output = self.root / 'worker'; self.review = self.root / 'fault-review.json'
        self.evidence = self.root / 'window'
        self.stack = ExitStack(); self.addCleanup(self.stack.close)
        for key, value in [('QUEUE', self.queue), ('OUTPUT', self.output), ('REVIEW', self.review)]:
            self.stack.enter_context(patch.object(W, key, value))
        for lane in ('A', 'B'):
            (self.queue / f'PAUSE-{lane}').write_text('original ' + lane + '\n')
            (self.queue / f'queue-{lane}.txt').write_text('')
        self.w = W.Window(self.evidence, '20261023-restore26')
        self.w.pause = {l:(self.queue / f'PAUSE-{l}').read_bytes() for l in ('A', 'B')}
        self.ids = ['fresh-a', 'fresh-b', 'resume-a', 'append-a', 'append-repeat', 'append-fresh', 'fresh-a-reference', 'fresh-b-repeat']
        self.plan = dict(expected_request_ids=self.ids, host_required_available_bytes=1, planned_write_bytes=1, disk_floor_bytes=27_000_000_000,
                         nice=19, cpu_affinity='8-15,24-31', worker_argv=['/usr/bin/python3', '-B', 'worker-mock'],
                         fault_review_command=['/usr/bin/python3', '-B', 'review-mock', '--output', str(self.review)])

    def good_terminal(self):
        return dict(passed=True, device_executed=True, native_process_count=1, model_loads=1, child_still_running=False,
                    safe_to_exit=True, devices_drained=True, completed_requests=self.ids,
                    correctness={k:True for k in W.CORRECTNESS})

    def setup_execute(self):
        self.stack.enter_context(patch.object(W, 'check', return_value=dict(plan=self.plan, worker_sha256='mock-sha')))
        self.stack.enter_context(patch.object(W, 'plan', return_value=self.plan))
        self.stack.enter_context(patch.object(W, 'clear'))
        self.stack.enter_context(patch.object(S, 'sha', return_value='mock-sha'))
        self.stack.enter_context(patch.object(S, 'endpoint_idle'))
        self.stack.enter_context(patch.object(S, 'require_safe_stop'))
        self.stack.enter_context(patch.object(S, 'require_drained', return_value=dict(mock=True)))
        self.stack.enter_context(patch.object(S, 'active', return_value=False))
        self.stack.enter_context(patch.object(W.H, 'verify'))
        def command(argv, **kwargs):
            if 'review-mock' in argv: self.review.write_text('{}')
            return subprocess.CompletedProcess(argv, 0, '', '')
        self.cmd = self.stack.enter_context(patch.object(S, 'command', side_effect=command))
        self.restore = self.stack.enter_context(patch.object(W.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)))

    def test_success_has_one_start_and_one_restore(self):
        self.setup_execute()
        with patch.object(self.w, 'watch', return_value=self.good_terminal()): self.w.execute()
        launches = [c.args[0] for c in self.cmd.call_args_list if c.args[0][0] == 'systemd-run']
        self.assertEqual(len(launches), 1)
        self.assertIn('--property=KillMode=process', launches[0])
        self.assertIn('--property=SendSIGKILL=no', launches[0])
        self.assertEqual(self.restore.call_count, 1)
        self.assertEqual((self.queue / 'PAUSE-A').read_bytes(), self.w.pause['A'])
        self.assertEqual((self.queue / 'PAUSE-B').read_bytes(), self.w.pause['B'])
        self.assertFalse((self.queue / 'STOP-A').exists())

    def test_failed_worker_never_restores(self):
        self.setup_execute(); self.output.mkdir()
        with patch.object(self.w, 'watch', side_effect=RuntimeError('request exactness failed')):
            with self.assertRaisesRegex(RuntimeError, 'request exactness failed'): self.w.execute()
        self.restore.assert_not_called()
        self.assertTrue((self.queue / 'STOP-A').exists()); self.assertTrue((self.output / 'STOP').exists())

    def test_postflight_unknown_owner_never_restores(self):
        self.setup_execute()
        with patch.object(self.w, 'watch', return_value=self.good_terminal()), \
             patch.object(S, 'require_drained', side_effect=[{}, RuntimeError('unknown owner')]):
            with self.assertRaisesRegex(RuntimeError, 'unknown owner'): self.w.execute()
        self.restore.assert_not_called()

    def test_external_stop_not_removed_or_overwritten(self):
        self.evidence.mkdir()
        stop = self.queue / 'STOP-A'; stop.write_text('external incident\n')
        with patch.object(S, 'active', return_value=False): self.w.incident()
        self.assertEqual(stop.read_text(), 'external incident\n')
        with patch.object(S, 'faults_clear'):
            with self.assertRaisesRegex(RuntimeError, 'incident latch'): W.clear()

    def test_active_incident_sends_only_one_main_term_never_group(self):
        self.evidence.mkdir(); self.w.launched = True
        with patch.object(S, 'require_safe_stop'), patch.object(S, 'active', return_value=True), \
             patch.object(S, 'command', return_value=subprocess.CompletedProcess([], 0, '', '')) as cmd, \
             patch.object(W.time, 'monotonic', side_effect=[0, 901, 0, 901]):
            for _ in range(2):
                with self.assertRaisesRegex(RuntimeError, 'retained after drain'): self.w.incident()
        self.assertEqual(cmd.call_count, 1)
        self.assertEqual(cmd.call_args.args[0], ['systemctl', '--user', 'kill', '--kill-whom=main', '--signal=SIGTERM', W.UNIT + '.service'])

    def test_terminal_requires_all_exactness_and_drain_fields(self):
        self.output.mkdir()
        mutations = [('model_loads', 2), ('native_process_count', True), ('devices_drained', False),
                     ('completed_requests', self.ids[:-1]), ('correctness', {k:k != 'B_repeat' for k in W.CORRECTNESS})]
        for key, value in mutations:
            with self.subTest(key=key):
                row = self.good_terminal(); row[key] = value
                (self.output / 'worker.json').write_text(json.dumps(row))
                with self.assertRaises(RuntimeError): W.terminal(self.plan)

    def test_watch_accepts_complete_success_after_active_to_inactive(self):
        self.output.mkdir(); (self.output / 'worker.json').write_text(json.dumps(self.good_terminal()))
        (self.queue / 'PAUSE-A').unlink()
        with patch.object(W, 'clear'), patch.object(W.time, 'sleep'), \
             patch.object(W, 'status', side_effect=[dict(ActiveState='active'), dict(ActiveState='inactive', Result='success', ExecMainStatus='0')]), \
             patch.object(S, 'active', side_effect=AssertionError('watch must sample status only once')):
            self.assertEqual(self.w.watch(self.plan)['completed_requests'], self.ids)

    def test_inactive_missing_terminal_receipt_has_bounded_rereads(self):
        (self.queue / 'PAUSE-A').unlink()
        with patch.object(W, 'clear'), patch.object(W.time, 'sleep') as sleep, \
             patch.object(W, 'status', return_value=dict(ActiveState='inactive', Result='success', ExecMainStatus='0')):
            with self.assertRaisesRegex(RuntimeError, 'receipt unavailable'): self.w.watch(self.plan)
        self.assertEqual(sleep.call_count, 2)

    def test_failed_unit_never_accepted_even_with_success_receipt(self):
        self.output.mkdir(); (self.output / 'worker.json').write_text(json.dumps(self.good_terminal()))
        (self.queue / 'PAUSE-A').unlink()
        with patch.object(W, 'clear'), patch.object(W, 'status', return_value=dict(ActiveState='failed', Result='exit-code', ExecMainStatus='1')):
            with self.assertRaisesRegex(RuntimeError, 'unit did not succeed'): self.w.watch(self.plan)

    def test_preflight_refusal_has_no_files_or_actions(self):
        with patch.object(W, 'check', side_effect=RuntimeError('not ready')), patch.object(S, 'command') as cmd:
            with self.assertRaisesRegex(RuntimeError, 'not ready'): self.w.execute()
        self.assertFalse(self.evidence.exists()); cmd.assert_not_called()

    def test_changed_pause_does_not_prevent_incident_stop_or_mask_original_error(self):
        self.setup_execute(); self.output.mkdir()
        def fail(*args):
            (self.queue / 'PAUSE-B').write_text('external pause\n')
            raise RuntimeError('original worker fault')
        with patch.object(self.w, 'watch', side_effect=fail):
            with self.assertRaisesRegex(RuntimeError, 'original worker fault'): self.w.execute()
        self.restore.assert_not_called()
        self.assertTrue((self.queue / 'STOP-A').exists()); self.assertTrue((self.output / 'STOP').exists())
        self.assertEqual((self.queue / 'PAUSE-B').read_text(), 'external pause\n')
        result = json.loads((self.evidence / 'window-result.json').read_text())
        self.assertEqual(result['error'], 'original worker fault')
        self.assertEqual(json.loads((self.evidence / 'final-latch-check.json').read_text())['original_error'], 'original worker fault')

    def test_changed_pause_still_allows_single_main_stop(self):
        self.evidence.mkdir(); self.w.launched = True
        (self.queue / 'PAUSE-B').write_text('external pause\n')
        with patch.object(S, 'require_safe_stop'), patch.object(S, 'active', side_effect=[True, False, False]), \
             patch.object(S, 'command', return_value=subprocess.CompletedProcess([], 0, '', '')) as cmd:
            self.w.incident()
        self.assertEqual(cmd.call_count, 1)
        self.assertIn('--kill-whom=main', cmd.call_args.args[0])
        self.assertEqual((self.queue / 'PAUSE-B').read_text(), 'external pause\n')

    def test_restore_adapter_routes_validation_child_through_same_guard(self):
        original_argv = list(W.sys.argv)
        self.addCleanup(setattr, W.sys, 'argv', original_argv)
        def execute_parent(path, **kwargs):
            self.assertEqual(Path(path), W.H.RESTORE)
            subprocess.run(['/usr/bin/python3', str(W.H.PARENT / 'validate.py'), '--base', 'http://mock', '--kind', 'vllm'])
        with patch.object(W.H, 'verify'), patch.object(W, 'clear'), patch.object(R.runpy, 'run_path', side_effect=execute_parent), \
             patch.object(subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as run:
            R.main(['20261023-restore26'])
        command = run.call_args.args[0]
        self.assertEqual(command[3:], ['--validate', '--base', 'http://mock', '--kind', 'vllm'])
        self.assertEqual(Path(command[2]), Path(R.__file__).resolve())

    def test_inherited_operation_guard_sees_p197_output_stop(self):
        original_argv = list(W.sys.argv)
        self.addCleanup(setattr, W.sys, 'argv', original_argv)
        self.output.mkdir()
        def execute_parent(path, **kwargs):
            (self.output / 'STOP').write_text('external owner stop\n')
            # The inherited sources perform this exact import before operations.
            from window import faults_clear
            faults_clear()
            self.fail('request admitted after packet197 STOP')
        with patch.object(W.H, 'verify'), patch.object(S, 'faults_clear'), \
             patch.object(R.runpy, 'run_path', side_effect=execute_parent):
            with self.assertRaisesRegex(RuntimeError, 'incident latch'):
                R.main(['--validate', '--base', 'http://mock'])


if __name__ == '__main__': unittest.main()
