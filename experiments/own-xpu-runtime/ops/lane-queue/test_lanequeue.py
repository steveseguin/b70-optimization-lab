"""CPU-only regression tests. No systemd, journal, model or device calls."""
import json
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import lanequeue as q


class FakeBackend:
    def __init__(self, clock):
        self.clock = clock
        self.runs = []
        self.rc = 0
        self.duration = 11
        self.after = lambda: None
        self.guard = lambda: None
        self.result = 'success'
        self.fault_count = q.BASE

    def guards(self, lane):
        self.guard()
        return self.faults()

    def faults(self):
        return self.fault_count

    def review(self, job, directory):
        return str(directory / 'fresh-review.json')

    def execute(self, cmd, log):
        self.runs.append(cmd)
        self.clock[0] += self.duration
        self.after()
        return self.rc

    def status(self, name, receipt):
        return dict(Result=self.result, ExecMainStatus=str(self.rc), source='mock')


class QueueTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.clock = [0.0]
        self.backend = FakeBackend(self.clock)
        self.queue = q.Queue(self.root, 'A', self.backend, now=lambda: self.clock[0], sleep=self.sleep)
        self.addCleanup(patch.stopall)
        patch.object(q, 'library_path', return_value='/literal/libraries').start()
        patch.object(q, 'plan_job', return_value={'plan': 'passed'}).start()
        self.events = []
        self.queue.event = lambda kind, **kw: self.events.append((kind, kw))

    def sleep(self, seconds):
        self.clock[0] += seconds
        if self.clock[0] > 1000:
            self.fail('unbounded waiter')

    def job(self, name='one', **kw):
        return dict(name=name, lane='A', argv=['/usr/bin/true'], review=None, **kw)

    def write(self, rows):
        (self.root / 'queue-A.txt').write_text(''.join(json.dumps(r) + '\n' for r in rows))

    def done(self):
        return [json.loads(s) for s in (self.root / 'done-A.txt').read_text().splitlines()]


class Tests(QueueTestCase):
    def test_env_closed_and_all_unit_properties(self):
        cmd = q.command(self.job(), None, self.root / 'receipt', '/lib/test')
        at = cmd.index('-i')
        self.assertEqual(cmd[at + 1:at + 4], ['PATH=/usr/bin:/bin', 'OMP_NUM_THREADS=2', 'LD_LIBRARY_PATH=/lib/test'])
        self.assertEqual(cmd[at + 4:], ['/usr/bin/true'])
        for prop in ('Restart=no', 'SendSIGKILL=no', 'KillMode=process', 'ExitType=cgroup', 'TimeoutStopSec=infinity', 'Nice=0', 'CPUAffinity=0-3 16-19'):
            self.assertIn('--property=' + prop, cmd)
        self.assertIn('--wait', cmd)
        with self.assertRaisesRegex(ValueError, 'coordinator-script-only'):
            q.validate(self.job(env_extra={'P49_LDP': 'bad'}), 'A')

    def test_coordinator_extras_only_setenv(self):
        script = self.root / 'coordinator.sh'
        script.write_text('exit 0\n')
        job = dict(name='coord', lane='B', script=str(script), env_extra={'P49_LDP': '{P49_LDP}'})
        q.validate(job, 'B')
        cmd = q.command(job, None, self.root / 'exit', '/lib/x')
        self.assertIn('--setenv=P49_LDP=/lib/x', cmd)
        self.assertIn('_coordinator', cmd)
        self.assertEqual(cmd[-1], 'P49_LDP')
        self.assertIn('4-7,20-23', cmd)

    def test_gc_unit_uses_durable_receipt_without_waiter(self):
        backend = q.Backend()
        receipt = self.root / 'exit.json'
        q.save(receipt, {'Result': 'success', 'ExecMainStatus': '0'})
        with patch.object(q.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, 'LoadState=not-found\n', '')) as run:
            status = backend.status('gone', receipt)
        self.assertEqual(status['Result'], 'success')
        self.assertEqual(status['source'], 'ExecStopPost')
        self.assertEqual(run.call_count, 1)
        self.assertNotIn('list-units', run.call_args.args[0])

    def test_gc_missing_receipt_is_not_success(self):
        with patch.object(q.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, '', '')):
            self.assertEqual(q.Backend().status('gone', self.root / 'missing')['Result'], 'unavailable')

    def test_rc_preserved_and_refused_fast_stops(self):
        self.write([self.job(), self.job('two')])
        self.backend.rc, self.backend.duration = 7, 2
        self.assertEqual(self.queue.run(), 1)
        self.assertEqual(len(self.backend.runs), 1)
        row = self.done()[0]
        self.assertEqual(row['rc'], 7)
        self.assertEqual(row['outcome'], 'REFUSED-fast')
        self.assertEqual(row['duration_seconds'], 2)
        self.assertEqual(q.read_queue(self.root, 'A'), [self.job('two')])
        with self.assertRaisesRegex(ValueError, 'previous job failed'):
            self.queue.run()

    def test_execute_captures_returncode(self):
        with patch.object(q.subprocess, 'run', return_value=subprocess.CompletedProcess([], 13)):
            self.assertEqual(q.Backend().execute(['mock'], self.root / 'run.log'), 13)

    def test_device_failure_stops(self):
        self.write([self.job(), self.job('two')])
        self.backend.rc = 1
        self.assertEqual(self.queue.run(), 1)
        self.assertEqual(self.done()[0]['outcome'], 'FAILED')
        self.assertEqual(len(self.backend.runs), 1)

    def test_status_failure_stops_even_with_zero_rc(self):
        self.write([self.job()])
        self.backend.result = 'signal'
        self.assertEqual(self.queue.run(), 1)
        self.assertEqual(self.done()[0]['outcome'], 'FAILED-status')

    def test_stale_marker_and_live_marker_never_removed(self):
        with patch.object(q, 'COORD', self.root), patch.object(q, 'STAGE', self.root), patch.object(q.Backend, 'faults', return_value=2):
            marker = self.root / 'active-lane-A.json'
            marker.write_text(json.dumps({'pid': 12345}))
            for side, state in ((ProcessLookupError(), 'dead'), (None, 'live')):
                with patch.object(q.os, 'kill', side_effect=side):
                    with self.assertRaisesRegex(ValueError, state + ' owner'):
                        q.Backend().guards('A')
                self.assertTrue(marker.exists())

    def test_latch_retained(self):
        latch = self.root / 'screen/v3/fault-old-B.json'
        latch.parent.mkdir(parents=True)
        latch.write_text('{}')
        with patch.object(q, 'COORD', self.root), patch.object(q, 'STAGE', self.root), patch.object(q.Backend, 'faults', return_value=2):
            with self.assertRaisesRegex(ValueError, 'fault latch'):
                q.Backend().guards('A')
        self.assertTrue(latch.exists())

    def test_fault_change_prevents_launch(self):
        self.write([self.job()])
        self.backend.guard = lambda: q.require(False, 'fault count changed')
        with self.assertRaisesRegex(ValueError, 'fault count changed'):
            self.queue.run()
        self.assertEqual(self.backend.runs, [])

    def test_fault_change_after_exit_stops(self):
        self.write([self.job(), self.job('two')])
        self.backend.after = lambda: setattr(self.backend, 'guard', lambda: q.require(False, 'fault count changed'))
        self.assertEqual(self.queue.run(), 1)
        self.assertEqual(self.done()[0]['outcome'], 'FAILED-postflight')
        self.assertEqual(len(self.backend.runs), 1)

    def test_pause_then_stop_no_launch(self):
        self.write([self.job()])
        (self.root / 'PAUSE-A').touch()
        self.queue.sleep = lambda _: (self.root / 'STOP-A').touch()
        self.assertEqual(self.queue.run(), 0)
        self.assertEqual(self.backend.runs, [])

    def test_stop_after_job_does_not_wait_gap(self):
        self.write([self.job(), self.job('two')])
        self.backend.after = lambda: (self.root / 'STOP-A').touch()
        self.assertEqual(self.queue.run(), 0)
        self.assertEqual(self.clock[0], 11)
        self.assertEqual(len(self.backend.runs), 1)

    def test_pause_resume_reorder_and_append_at_boundary(self):
        first, second, third = self.job(), self.job('two'), self.job('three')
        self.write([first, second])
        starts = []
        def after():
            starts.append(self.clock[0] - self.backend.duration)
            if len(starts) == 1:
                self.write([third, first, second])
                (self.root / 'PAUSE-A').touch()
            elif len(starts) == 3:
                (self.root / 'STOP-A').touch()
        self.backend.after = after
        def sleep(seconds):
            self.sleep(seconds)
            if self.clock[0] >= 30:
                (self.root / 'PAUSE-A').unlink(missing_ok=True)
        self.queue.sleep = sleep
        self.assertEqual(self.queue.run(), 0)
        self.assertEqual([r['job']['name'] for r in self.done()], ['one', 'three', 'two'])
        self.assertGreaterEqual(starts[1] - starts[0], 101)
        self.assertGreaterEqual(starts[2] - starts[1], 101)

    def test_inflight_blocks_restart(self):
        self.queue.active.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'unfinished driver record'):
            self.queue.run()
        self.assertEqual(self.backend.runs, [])

    def test_changed_inflight_is_not_overwritten(self):
        job = self.job()
        changed = dict(job, argv=['/usr/bin/false'])
        self.write([changed])
        with self.assertRaisesRegex(ValueError, 'inflight job was edited'):
            self.queue.finish(job, {})
        self.assertEqual(q.read_queue(self.root, 'A'), [changed])

    def test_library_parser_never_executes_shell(self):
        patch.stopall()
        path = self.root / 'env'
        path.write_text("export P49_LDP='/one:/two'\n")
        self.assertEqual(q.library_path(path), '/one:/two')
        path.write_text('P49_LDP=$(touch /bad)\n')
        with self.assertRaises(ValueError):
            q.library_path(path)

    def test_patterns_match_authority_and_ignore_deleted(self):
        fault, deleted = q.fault_patterns()
        self.assertTrue(fault.search('Timed out job'))
        self.assertTrue(fault.search('Fault response'))
        self.assertTrue(deleted.search('coredump has been deleted'))

    def test_closed_environment_in_real_plan_call(self):
        patch.stopall()
        script = self.root / 'plan.py'
        script.write_text("import argparse\np=argparse.ArgumentParser()\np.add_argument('--plan', action='store_true')\n")
        job = self.job()
        job['argv'] = ['/usr/bin/python3', '-B', str(script), '--authorized-device-window', '--fault-review', '{REVIEW}']
        calls = []
        def invoke(argv, **kw):
            calls.append((argv, kw))
            return subprocess.CompletedProcess(argv, 0, '{}', '')
        q.plan_job(job, '/lib/approved', invoke)
        self.assertEqual(calls[0][1]['env'], q.closed_env('/lib/approved'))
        self.assertNotIn('--authorized-device-window', calls[0][0])
        self.assertNotIn('--fault-review', calls[0][0])
        self.assertEqual(calls[0][0][-1], '--plan')

    def test_existing_output_and_stop_refuse_plan(self):
        patch.stopall()
        script = self.root / 'plan.py'
        script.write_text("p.add_argument('--plan')\n")
        output = self.root / 'output'
        job = self.job()
        job['argv'] = ['/usr/bin/python3', '-B', str(script), '--output', str(output)]
        for existing in (output, self.root / 'STOP'):
            existing.touch()
            with self.assertRaises(ValueError), patch.object(q.subprocess, 'run') as run:
                q.plan_job(job, '/lib')
                run.assert_not_called()
            existing.unlink()

    def test_plan_checks_later_lines_after_bad_line(self):
        self.write([self.job()])
        path = self.root / 'queue-A.txt'
        path.write_text('bad json\n' + path.read_text())
        with patch.object(q, 'cpu_setup'), patch.object(q.sys, 'argv', ['lanequeue.py', 'plan', '--lane', 'A', '--directory', str(self.root)]), patch('sys.stdout', new_callable=io.StringIO) as output:
            self.assertEqual(q.main(), 1)
        rows = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['plan'], 'FAILED')
        self.assertEqual(rows[1]['plan'], 'passed')

    def test_review_placeholder_and_post_review_pause(self):
        job = self.job()
        job['argv'] += ['--fault-review', '{REVIEW}']
        job['review'] = str(Path(q.__file__))
        self.write([job])
        def review(job, directory):
            (directory / 'STOP-A').touch()
            return '/fresh/review'
        self.backend.review = review
        self.assertEqual(self.queue.run(), 0)
        self.assertEqual(self.backend.runs, [])
        cmd = q.command(job, '/fresh/review', self.root / 'receipt', '/lib')
        self.assertIn('/fresh/review', cmd)
        self.assertNotIn('{REVIEW}', cmd)

    def test_duplicate_driver_lock_refuses(self):
        with q.lock(self.root / 'driver-A.lock'):
            with self.assertRaises(BlockingIOError):
                self.queue.run()
        self.assertEqual(self.backend.runs, [])

    def test_restart_observes_remaining_cooldown(self):
        import time
        self.write([self.job()])
        self.queue.done.write_text(json.dumps(dict(job=self.job('old'), outcome='DONE', end_unix=time.time() - 20)) + '\n')
        self.backend.after = lambda: (self.root / 'STOP-A').touch()
        self.assertEqual(self.queue.run(), 0)
        self.assertGreaterEqual(self.clock[0] - self.backend.duration, 69)

    def test_stoppost_receipt_helper_cpu_only(self):
        path = self.root / 'exit.json'
        with patch.object(q.sys, 'argv', ['lanequeue.py', '_receipt', str(path)]), patch.dict(q.os.environ, {'SERVICE_RESULT': 'success', 'EXIT_CODE': 'exited', 'EXIT_STATUS': '0'}, clear=True):
            self.assertEqual(q.main(), 0)
        self.assertEqual(json.loads(path.read_text()), {'Result': 'success', 'ExecMainStatus': '0'})

    def test_quick_plan_checks_all_outputs_and_readonly_seal(self):
        patch.stopall()
        directory = self.root / 'quick'
        directory.mkdir()
        (directory / 'common.py').touch()
        script = directory / 'run.py'
        script.write_text("p.add_argument('--plan')\n")
        (directory / 'quick_seal.py').write_text("p.add_argument('--verify')\n")
        jobs = directory / 'jobs-A.txt'
        jobs.write_text('one|a|b|c|d|1\ntwo|a|b|c|d|1\n')
        job = self.job()
        job['argv'] = ['/usr/bin/python3', '-B', str(script), '--jobs', str(jobs)]
        calls = []
        def invoke(argv, **kw):
            calls.append(argv)
            return subprocess.CompletedProcess(argv, 0, '{}', '')
        q.plan_job(job, '/lib', invoke)
        self.assertEqual(calls[0][-1], '--verify')
        (directory / 'evidence/two').mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, 'quick output directory already exists'):
            q.plan_job(job, '/lib', invoke)
        self.assertEqual(len(calls), 2)

    def test_shell_plan_is_never_executed(self):
        patch.stopall()
        script = self.root / 'coordinator.sh'
        script.write_text('# mentions --plan but ignores it\nexit 0\n')
        with patch.object(q.subprocess, 'run') as run:
            result = q.plan_job(dict(script=str(script), name='coord'), '/lib', run)
        self.assertIn('unsupported', result['plan'])
        run.assert_not_called()


class ReportFailureTests(QueueTestCase):
    def setUp(self):
        super().setUp()
        self.stage = self.root / 'stage2'
        self.shared = self.stage / 'screen/v3'
        self.shared.mkdir(parents=True)
        self.coord = self.root / 'coordination'
        self.coord.mkdir()
        patch.object(q, 'STAGE', self.stage).start()
        patch.object(q, 'COORD', self.coord).start()
        self.output = self.root / 'output'
        self.output.mkdir()
        self.proofs = {
            self.output / 'window.json': dict(passed=True, device_executed=True),
            self.output / 'packet77-report-failure.json': dict(device_failure=False),
            self.output / 'lane-coordination.json': dict(released_before_report=True),
            self.shared / 'teardown-state.json': dict(drained=True),
        }
        for path, row in self.proofs.items():
            q.save(path, row)
        self.first = self.job()
        self.first['argv'] += ['--output', str(self.output)]
        self.write([self.first, self.job('two')])
        self.backend.rc = 1
        self.backend.result = 'exit-code'
        # Exercise real marker/latch guards, with only the journal mocked.
        self.backend.guards = lambda lane: q.Backend.guards(self.backend, lane)

    def assert_stops(self):
        self.assertEqual(self.queue.run(), 1)
        self.assertEqual(self.done()[0]['outcome'], 'FAILED')
        self.assertEqual(len(self.backend.runs), 1)
        self.assertEqual(q.read_queue(self.root, 'A'), [self.job('two')])
        self.assertNotIn('REPORT-FAILED', [kind for kind, _ in self.events])
        with self.assertRaisesRegex(ValueError, 'previous job failed'):
            self.queue.run()

    def test_report_failure_continues_different_job_and_records_alert(self):
        # Exercise actual durable events in a temporary queue, never live files.
        self.queue.event = q.Queue.event.__get__(self.queue)
        def after():
            if len(self.backend.runs) == 2:
                self.backend.rc, self.backend.result = 0, 'success'
                (self.root / 'STOP-A').touch()
        self.backend.after = after
        with patch('sys.stdout', new_callable=io.StringIO):
            self.assertEqual(self.queue.run(), 0)
        rows = self.done()
        self.assertEqual([r['outcome'] for r in rows], ['REPORT-FAILED', 'DONE'])
        self.assertEqual([r['job']['name'] for r in rows], ['one', 'two'])
        self.assertEqual(rows[0]['rc'], 1)
        self.assertEqual(rows[0]['faults_start'], rows[0]['faults_end'])
        self.assertEqual(rows[0]['report_failure_evidence']['output'], str(self.output))
        self.assertEqual(len(self.backend.runs), 2)
        self.assertEqual(self.clock[0], 112)  # 11 + 90-second gap + 11
        events = [json.loads(s) for s in (self.root / 'events-A.jsonl').read_text().splitlines()]
        self.assertIn('REPORT-FAILED', [r['event'] for r in events])
        self.assertTrue(any(r['event'] == 'ALERT' and 'no retry' in r['reason'] for r in events))

    def test_coordination_passed_is_alternative_release_proof(self):
        q.save(self.output / 'lane-coordination.json', dict(passed=True))
        self.backend.after = lambda: (self.root / 'STOP-A').touch()
        self.assertEqual(self.queue.run(), 0)
        self.assertEqual(self.done()[0]['outcome'], 'REPORT-FAILED')

    def test_each_required_boolean_is_strict(self):
        for path, row in self.proofs.items():
            for key in row:
                for value in (None, 0, 1, 'true', 'false', not row[key]):
                    with self.subTest(file=path.name, key=key, value=value):
                        q.save(path, {**row, key: value})
                        with self.assertRaises(ValueError):
                            q.report_failure_evidence(self.first)
                q.save(path, {k: v for k, v in row.items() if k != key})
                with self.assertRaises(ValueError):
                    q.report_failure_evidence(self.first)
                q.save(path, row)

    def test_missing_malformed_and_nonobject_receipts_fail_closed(self):
        for path, row in self.proofs.items():
            with self.subTest(file=path.name, case='missing'):
                path.unlink()
                with self.assertRaises((ValueError, OSError)):
                    q.report_failure_evidence(self.first)
            for contents in ('{', '[]', 'null', 'true', '42', '"text"'):
                with self.subTest(file=path.name, contents=contents):
                    path.write_text(contents)
                    with self.assertRaises(ValueError):
                        q.report_failure_evidence(self.first)
            q.save(path, row)

    def test_unreadable_receipt_fails_closed(self):
        with patch.object(Path, 'read_text', side_effect=PermissionError('unreadable')):
            with self.assertRaises(PermissionError):
                q.report_failure_evidence(self.first)

    def test_conflicting_report_receipts_stop(self):
        q.save(self.output / 'another-report-failure.json', dict(device_failure=True))
        self.assert_stops()

    def test_failed_device_window_stops(self):
        q.save(self.output / 'window.json', dict(passed=False, device_executed=True))
        self.assert_stops()

    def test_device_not_executed_stops(self):
        q.save(self.output / 'window.json', dict(passed=True, device_executed=False))
        self.assert_stops()

    def test_missing_report_failure_stops(self):
        (self.output / 'packet77-report-failure.json').unlink()
        self.assert_stops()

    def test_unreleased_lane_stops(self):
        q.save(self.output / 'lane-coordination.json', dict(passed=False, released_before_report=False))
        self.assert_stops()

    def test_undrained_teardown_stops(self):
        q.save(self.shared / 'teardown-state.json', dict(drained=False))
        self.assert_stops()

    def test_changed_kernel_fault_count_stops(self):
        self.backend.after = lambda: setattr(self.backend, 'fault_count', q.BASE + 1)
        self.assert_stops()

    def test_count_compared_with_job_start_even_if_backend_guards_pass(self):
        self.backend.guards = lambda lane: self.backend.fault_count
        self.backend.after = lambda: setattr(self.backend, 'fault_count', q.BASE + 1)
        self.assert_stops()

    def test_unreadable_kernel_journal_stops(self):
        def after():
            self.backend.faults = lambda: q.require(False, 'journal unavailable')
        self.backend.after = after
        self.assert_stops()

    def test_new_fault_latch_on_either_lane_stops(self):
        self.backend.after = lambda: (self.shared / 'fault-other-B.json').touch()
        self.assert_stops()

    def test_active_marker_even_dangling_symlink_stops(self):
        self.backend.after = lambda: (self.coord / 'active-lane-A.json').symlink_to(self.root / 'absent')
        self.assert_stops()

    def test_other_lane_marker_does_not_block_report_failure(self):
        (self.coord / 'active-lane-B.json').write_text('{}')
        self.backend.after = lambda: (self.root / 'STOP-A').touch()
        self.assertEqual(self.queue.run(), 0)
        self.assertEqual(self.done()[0]['outcome'], 'REPORT-FAILED')

    def test_no_output_path_does_not_guess_or_search(self):
        self.write([self.job(), self.job('two')])
        self.assert_stops()

    def test_report_failure_not_applied_to_zero_rc_bad_status(self):
        self.backend.rc = 0
        self.assertEqual(self.queue.run(), 1)
        self.assertEqual(self.done()[0]['outcome'], 'FAILED-status')

    def test_report_failure_can_finish_in_under_ten_seconds(self):
        self.backend.duration = 2
        self.backend.after = lambda: (self.root / 'STOP-A').touch()
        self.assertEqual(self.queue.run(), 0)
        self.assertEqual(self.done()[0]['outcome'], 'REPORT-FAILED')

    def test_restart_allows_report_failed_but_keeps_gap_and_no_replay(self):
        self.queue.done.write_text(json.dumps(dict(job=self.first, outcome='REPORT-FAILED',
                                                 end_unix=100)) + '\n')
        with patch.object(q.time, 'time', return_value=120):
            with self.assertRaisesRegex(ValueError, 'no automatic replay'):
                self.queue.run()
        self.assertEqual(self.clock[0], 70)
        self.assertEqual(self.backend.runs, [])
        self.write([self.job('two')])
        self.backend.rc, self.backend.result = 0, 'success'
        self.backend.after = lambda: (self.root / 'STOP-A').touch()
        with patch.object(q.time, 'time', return_value=120):
            self.assertEqual(self.queue.run(), 0)
        self.assertEqual([r['job']['name'] for r in self.done()], ['one', 'two'])


if __name__ == '__main__':
    unittest.main()
