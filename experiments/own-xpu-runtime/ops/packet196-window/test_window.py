"""CPU-only safety mocks; no services, privileges, journals, network or GPU work."""
from contextlib import ExitStack
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import window as W
S = W.S


class WindowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.queue = self.root / 'queue'; self.queue.mkdir()
        self.chain = self.root / 'chain'
        for lane in ('A', 'B'):
            (self.queue / f'PAUSE-{lane}').write_text('original ' + lane + '\n')
            (self.queue / f'queue-{lane}.txt').write_text('')
        self.stack = ExitStack(); self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(W, 'QUEUE', self.queue))
        self.stack.enter_context(patch.object(W, 'CHAIN_OUTPUT', self.chain))
        self.w = W.Window(self.root / 'evidence', '20261023-restore25')
        self.w.pause_a = (self.queue / 'PAUSE-A').read_bytes()
        self.w.pause_b = (self.queue / 'PAUSE-B').read_bytes()

    def setup_execute(self):
        self.stack.enter_context(patch.object(W, 'check', return_value=dict(boot='mock-boot', binding=dict(launcher_sha256='mock-sha'))))
        self.stack.enter_context(patch.object(S, 'sha', return_value='mock-sha'))
        self.stack.enter_context(patch.object(S, 'endpoint_idle'))
        self.stack.enter_context(patch.object(W, 'faults_clear'))
        self.stack.enter_context(patch.object(S, 'require_safe_stop'))
        self.stack.enter_context(patch.object(S, 'require_drained', return_value={'mock': True}))
        self.stack.enter_context(patch.object(S, 'active', return_value=False))
        self.stack.enter_context(patch.object(W, 'ensure_chain_stop_properties'))
        self.cmd = self.stack.enter_context(patch.object(S, 'command', return_value=subprocess.CompletedProcess([], 0, '', '')))
        self.restore = self.stack.enter_context(patch.object(W.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)))

    def test_success_launches_and_restores_once_preserving_pauses(self):
        self.setup_execute()
        with patch.object(self.w, 'watch', return_value=dict(windows=list(W.ORDER))):
            self.w.execute()
        launches = [c.args[0] for c in self.cmd.call_args_list if c.args[0][0] == '/usr/bin/bash']
        self.assertEqual(launches, [['/usr/bin/bash', W.LAUNCHER]])
        self.assertEqual(self.restore.call_count, 1)
        self.assertEqual((self.queue / 'PAUSE-A').read_bytes(), self.w.pause_a)
        self.assertEqual((self.queue / 'PAUSE-B').read_bytes(), self.w.pause_b)
        self.assertFalse((self.queue / 'STOP-A').exists())
        self.assertTrue(json.loads((self.w.output / 'window-result.json').read_text())['passed'])

    def test_chain_failure_never_restores(self):
        self.setup_execute(); self.chain.mkdir()
        with patch.object(self.w, 'watch', side_effect=RuntimeError('gate failed')):
            with self.assertRaisesRegex(RuntimeError, 'gate failed'):
                self.w.execute()
        self.restore.assert_not_called()
        self.assertTrue((self.queue / 'STOP-A').exists())
        self.assertTrue((self.chain / 'STOP').exists())

    def test_external_stop_preserved_and_blocks_requests(self):
        (self.queue / 'STOP-B').write_text('external incident\n')
        with patch.object(S, 'faults_clear'):
            with self.assertRaisesRegex(RuntimeError, 'incident STOP'):
                W.faults_clear()
        self.w.output.mkdir()
        with patch.object(S, 'active', return_value=False):
            self.w.stop_incident()
        self.assertEqual((self.queue / 'STOP-B').read_text(), 'external incident\n')

    def test_incident_signals_only_coordinator_main_once(self):
        self.w.output.mkdir(); self.chain.mkdir(); self.w.launch_attempted = True
        with patch.object(W, 'ensure_chain_stop_properties'), \
             patch.object(S, 'command', return_value=subprocess.CompletedProcess([], 0, '', '')) as cmd, \
             patch.object(S, 'active', return_value=True), \
             patch.object(W.time, 'monotonic', side_effect=[0, 901, 0, 901]):
            for _ in range(2):
                with self.assertRaisesRegex(RuntimeError, 'still active'):
                    self.w.stop_incident()
        self.assertEqual(cmd.call_count, 1)
        self.assertEqual(cmd.call_args.args[0], ['systemctl', '--user', 'kill', '--kill-whom=main', '--signal=SIGTERM', W.UNIT + '.service'])
        self.assertTrue((self.chain / 'STOP').exists())

    def test_launcher_refusal_not_retried_or_restored(self):
        self.setup_execute()
        def command(argv, **kwargs):
            return subprocess.CompletedProcess(argv, 4 if argv[0] == '/usr/bin/bash' else 0, '', '')
        self.cmd.side_effect = command
        with self.assertRaisesRegex(RuntimeError, 'launcher failed'):
            self.w.execute()
        self.restore.assert_not_called()
        self.assertEqual(sum(c.args[0][0] == '/usr/bin/bash' for c in self.cmd.call_args_list), 1)

    def test_postflight_refusal_blocks_restore(self):
        self.setup_execute()
        with patch.object(self.w, 'watch', return_value={}), patch.object(S, 'require_drained', side_effect=[{}, RuntimeError('unreadable owner')]):
            with self.assertRaisesRegex(RuntimeError, 'unreadable owner'):
                self.w.execute()
        self.restore.assert_not_called()

    def test_restore_failure_not_retried(self):
        self.setup_execute(); self.restore.return_value = subprocess.CompletedProcess([], 1)
        with patch.object(self.w, 'watch', return_value={}):
            with self.assertRaisesRegex(RuntimeError, 'restore failed'):
                self.w.execute()
        self.assertEqual(self.restore.call_count, 1)

    def test_reviewed_predevice_continuation_skips_all_endpoint_stop_requests(self):
        self.setup_execute()
        self.w.resume = self.root / 'review.json'
        preflight = dict(boot='mock-boot', binding=dict(launcher_sha256='mock-sha'),
                         resume_predevice=dict(endpoints_already_drained=True))
        with patch.object(W, 'check', return_value=preflight), patch.object(self.w, 'watch', return_value={}):
            self.w.execute()
        self.assertFalse(any('stop' in c.args[0] for c in self.cmd.call_args_list))
        self.assertEqual(sum(c.args[0][0] == '/usr/bin/bash' for c in self.cmd.call_args_list), 1)
        self.assertEqual(self.restore.call_count, 1)

    def resume_fixture(self):
        self.stack.enter_context(patch.object(W, 'HERE', self.root))
        failed = self.root / 'evidence/window-a'; failed.mkdir(parents=True)
        packet = self.root / 'packet'; packet.mkdir()
        launcher = self.root / 'launcher'; launcher.write_text('reviewed repair')
        self.stack.enter_context(patch.object(W, 'PACKET', packet))
        self.stack.enter_context(patch.object(W, 'LAUNCHER', launcher))
        self.stack.enter_context(patch.object(W, 'FAULT_REVIEW', packet / 'uncreated-fault.json'))
        self.resume_cmd = self.stack.enter_context(patch.object(S, 'command', return_value=subprocess.CompletedProcess([], 0, 'LoadState=not-found\nMainPID=0\n', '')))
        boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        docs = {
            'window-result.json': dict(passed=False, completed=[], stop_signalled=False, launch_attempted=True,
                                       retry=False, error='sealed chain launcher failed; no retry'),
            'preflight.json': dict(boot=boot, binding=dict(launcher_sha256='old-launcher', command_sha256='same-command')),
            'post-stop-drain.json': dict(privileged_passive_device_inventory=dict(passed=True, device_opens=0, holders=[], errors=[]), coordinator_guards_both_lanes=True),
        }
        for name, row in docs.items():
            (failed / name).write_text(json.dumps(row))
        (failed / 'launcher.log').write_text('2026-10-23T15:13:02Z p196-launch REFUSED: cannot establish endpoint state for qwen38-27b-fp8\n')
        (failed / 'STOP-A.archived').write_text('packet196 window halted 2026-10-23T15:13:02Z\n')
        for lane in ('A', 'B'):
            (failed / f'PAUSE-{lane}.before').write_bytes((self.queue / f'PAUSE-{lane}').read_bytes())
        (packet / 'READY-FOR-DEVICE.json').write_text(json.dumps(dict(chain_command_digest_sha256='same-command')))
        review = dict(schema='packet196.predevice-resume-review.v1', reviewed=True,
                      predevice_refusal='systemctl-is-active-rc4-inactive', chain_launched=False, stop_manually_archived=True,
                      boot_id=boot, previous_launcher_sha256='old-launcher', replacement_launcher_sha256=S.sha(launcher),
                      chain_command_sha256='same-command', prior_files_sha256={p.name:S.sha(p) for p in failed.iterdir()})
        path = self.root / 'review.json'; path.write_text(json.dumps(review))
        return failed, path

    def test_resume_review_accepts_only_pinned_unlaunched_refusal(self):
        failed, path = self.resume_fixture()
        row = W.resume_review(path)
        self.assertTrue(row['endpoints_already_drained'])
        self.assertEqual(row['original_window'], str(failed))

    def test_resume_wrong_provenance_refuses(self):
        failed, path = self.resume_fixture()
        (failed / 'launcher.log').write_text('new unrelated failure\n')
        with self.assertRaisesRegex(RuntimeError, 'provenance changed'):
            W.resume_review(path)

    def test_resume_external_stop_refuses_without_unlink(self):
        failed, path = self.resume_fixture()
        stop = self.queue / 'STOP-A'; stop.write_text('new incident\n')
        with self.assertRaisesRegex(RuntimeError, 'manually reviewed/archived'):
            W.resume_review(path)
        self.assertEqual(stop.read_text(), 'new incident\n')

    def test_resume_existing_chain_unit_refuses(self):
        failed, path = self.resume_fixture()
        self.resume_cmd.return_value = subprocess.CompletedProcess([], 0, 'LoadState=loaded\nMainPID=0\n', '')
        with self.assertRaisesRegex(RuntimeError, 'not a proven unlaunched'):
            W.resume_review(path)

    def setup_watch(self, rows, statuses):
        self.w.output.mkdir(); self.chain.mkdir()
        (self.chain / 'queue.json').write_text('{}')
        (self.queue / 'PAUSE-A').unlink()
        original = Path.read_text
        sequence = iter(rows)
        def read(path, *args, **kwargs):
            if path == self.chain / 'queue.json':
                return json.dumps(next(sequence))
            return original(path, *args, **kwargs)
        self.stack.enter_context(patch.object(Path, 'read_text', read))
        self.stack.enter_context(patch.object(W, 'faults_clear'))
        self.stack.enter_context(patch.object(W.time, 'sleep'))
        self.stack.enter_context(patch.object(W, 'chain_status', side_effect=statuses))
        self.stack.enter_context(patch.object(W, 'verify_gate', side_effect=lambda name, *a: dict(window=name)))
        self.active = self.stack.enter_context(patch.object(S, 'active', side_effect=AssertionError('watch must use one status sample')))

    def final(self):
        return dict(passed=True, completed=list(W.ORDER), running=None, finished_utc_ns=1)

    def inactive(self):
        return dict(ActiveState='inactive', Result='success', ExecMainStatus='0')

    def test_active_to_inactive_final_transition_is_success(self):
        self.setup_watch([self.final(), self.final()], [dict(ActiveState='active'), self.inactive()])
        result = self.w.watch('mock-boot', 'mock-build')
        self.assertEqual([r['window'] for r in result['windows']], list(W.ORDER))
        self.active.assert_not_called()

    def test_unit_exit_with_stale_queue_read_gets_bounded_metadata_reread(self):
        stale = dict(passed=False, completed=list(W.ORDER), running=None)
        self.setup_watch([stale, self.final()], [self.inactive(), self.inactive()])
        self.assertEqual(len(self.w.watch('mock-boot', 'mock-build')['windows']), 7)

    def test_inactive_unit_missing_final_receipt_eventually_refuses(self):
        rows = [dict(passed=False, completed=[], running=None)] * 3
        self.setup_watch(rows, [self.inactive()] * 3)
        with self.assertRaisesRegex(RuntimeError, 'without complete successful receipt'):
            self.w.watch('mock-boot', 'mock-build')

    def test_incomplete_passed_chain_refuses(self):
        self.setup_watch([dict(passed=True, completed=list(W.ORDER[:-1]), running=None, finished_utc_ns=1)], [])
        with self.assertRaisesRegex(RuntimeError, 'without complete seven-window'):
            self.w.watch('mock-boot', 'mock-build')

    def test_wrong_gate_order_refuses(self):
        self.setup_watch([dict(passed=False, completed=['K1b'])], [])
        with self.assertRaisesRegex(RuntimeError, 'registered prefix'):
            self.w.watch('mock-boot', 'mock-build')

    def test_terminal_chain_error_refuses_immediately(self):
        self.setup_watch([dict(passed=False, completed=['K1a'], error='GPU fault')], [])
        with self.assertRaisesRegex(RuntimeError, 'chain failure'):
            self.w.watch('mock-boot', 'mock-build')

    def test_queue_passed_cannot_override_failed_unit(self):
        self.setup_watch([self.final()], [dict(ActiveState='failed', Result='exit-code', ExecMainStatus='1')])
        with self.assertRaisesRegex(RuntimeError, 'unit failed'):
            self.w.watch('mock-boot', 'mock-build')


if __name__ == '__main__':
    unittest.main()
