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
        patch.object(q, 'STAGE', self.root / 'stage2').start()
        patch.object(q, 'COORD', self.root / 'coordination').start()
        patch.object(q, 'PROC', self.root / 'proc').start()
        boot_path = self.root / 'boot_id'
        boot_path.write_text('2cba7160-0000-0000-0000-000000000000\n')
        patch.object(q, 'BOOT_ID_PATH', boot_path).start()
        patch.object(q, 'library_path', return_value='/literal/libraries').start()
        patch.object(q, 'plan_job', return_value={'plan': 'passed'}).start()
        patch.object(q, 'check_pins', return_value={'passed': True}).start()
        self.events = []
        self.queue.event = lambda kind, **kw: self.events.append((kind, kw))

    def sleep(self, seconds):
        self.assertGreaterEqual(seconds, 0, 'negative sleep')
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
        with patch.object(q.subprocess, 'Popen') as popen:
            popen.return_value.poll.return_value = 13
            self.assertEqual(q.Backend().execute(['mock', '--unit=screen-one'], self.root / 'run.log'), 13)

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


class DrainSpacingTests(QueueTestCase):
    def setUp(self):
        super().setUp()
        self.clock[0] = 100.0
        self.teardown = q.STAGE / 'screen/v3/teardown-state.json'
        self.teardown.parent.mkdir(parents=True)
        self.write([self.job()])
        self.backend.after = lambda: (self.root / 'STOP-A').touch()

    def drain(self, completed=90.0):
        q.save(self.teardown, dict(boot_id=q.BOOT_ID_PATH.read_text().strip(),
                                  drained=True, completed_monotonic=completed))

    def start_time(self):
        self.assertEqual(self.queue.run(), 0)
        self.assertEqual(len(self.backend.runs), 1)
        return self.clock[0] - self.backend.duration

    def waits(self):
        return [row for kind, row in self.events if kind == 'WAIT-DRAIN-SPACING']

    def test_recent_teardown_waits_until_completed_plus_61(self):
        self.drain()
        before = self.teardown.read_bytes()
        self.assertEqual(self.start_time(), 151.0)
        self.assertEqual(self.waits(), [dict(name='one', wait_seconds=51.0, until_monotonic=151.0)])
        self.assertEqual(self.teardown.read_bytes(), before)

    def test_old_teardown_does_not_wait(self):
        self.drain(completed=0.0)
        self.assertEqual(self.start_time(), 100.0)
        self.assertEqual(self.waits(), [])

    def test_other_boot_does_not_wait(self):
        self.drain()
        row = json.loads(self.teardown.read_text())
        row['boot_id'] = '2cba7160-1111-1111-1111-111111111111'
        q.save(self.teardown, row)
        self.assertEqual(self.start_time(), 100.0)
        self.assertEqual(self.waits(), [])

    def test_undrained_keeps_existing_path(self):
        self.drain()
        row = json.loads(self.teardown.read_text())
        row['drained'] = False
        q.save(self.teardown, row)
        self.assertEqual(self.start_time(), 100.0)
        self.assertEqual(self.waits(), [])

    def test_missing_state_keeps_existing_path(self):
        self.assertEqual(self.start_time(), 100.0)
        self.assertEqual(self.waits(), [])

    def test_invalid_state_adds_no_spacing(self):
        for content in ('{', '[]', 'null', '42'):
            with self.subTest(content=content):
                self.teardown.write_text(content)
                self.assertEqual(q.drain_spacing_deadline(), 0.0)
        for completed in (None, True, '90', -1, float('inf'), float('nan'), 10**400):
            with self.subTest(completed=completed):
                self.drain(completed=completed)
                self.assertEqual(q.drain_spacing_deadline(), 0.0)
        with patch.object(Path, 'read_text', side_effect=PermissionError('unreadable')):
            self.assertEqual(q.drain_spacing_deadline(), 0.0)

    def test_pause_during_wait_prevents_start(self):
        self.drain()
        def sleep(seconds):
            self.sleep(seconds)
            if (self.root / 'PAUSE-A').exists():
                self.assertEqual(self.backend.runs, [])
                (self.root / 'STOP-A').touch()
            else:
                (self.root / 'PAUSE-A').touch()
        self.queue.sleep = sleep
        self.assertEqual(self.queue.run(), 0)
        self.assertEqual(self.backend.runs, [])
        self.assertFalse(self.queue.active.exists())

    def test_stop_during_wait_prevents_start(self):
        self.drain()
        self.queue.sleep = lambda _: (self.root / 'STOP-A').touch()
        self.assertEqual(self.queue.run(), 0)
        self.assertEqual(self.backend.runs, [])

    def test_signal_during_wait_prevents_start(self):
        self.drain()
        self.queue.sleep = lambda _: setattr(self.queue, 'stopped', True)
        self.assertEqual(self.queue.run(), 0)
        self.assertEqual(self.backend.runs, [])

    def test_fault_during_wait_prevents_start(self):
        self.drain()
        self.backend.guard = lambda: q.require(self.clock[0] < 101.0, 'fault count changed')
        with self.assertRaisesRegex(ValueError, 'fault count changed'):
            self.queue.run()
        self.assertEqual(self.backend.runs, [])
        self.assertFalse(self.queue.active.exists())

    def test_latch_during_wait_prevents_start(self):
        self.drain()
        self.backend.guards = lambda lane: q.Backend.guards(self.backend, lane)
        with patch.object(q, 'COORD', self.root):
            self.queue.sleep = lambda _: (self.teardown.parent / 'fault-old-A.json').touch()
            with self.assertRaisesRegex(ValueError, 'fault latch'):
                self.queue.run()
        self.assertEqual(self.backend.runs, [])

    def test_latest_teardown_extends_spacing(self):
        self.drain()
        def sleep(seconds):
            self.sleep(seconds)
            if self.clock[0] == 110.0:
                self.drain(completed=110.0)
        self.queue.sleep = sleep
        self.assertEqual(self.start_time(), 171.0)
        self.assertEqual([r['wait_seconds'] for r in self.waits()], [51.0, 61.0])

    def test_slow_guard_and_logging_never_cause_negative_sleep(self):
        self.drain(completed=39.5)
        original_event = self.queue.event
        def event(kind, **values):
            original_event(kind, **values)
            if kind == 'WAIT-DRAIN-SPACING':
                self.clock[0] += 1.0
        self.queue.event = event
        self.backend.guard = lambda: self.clock.__setitem__(0, self.clock[0] + .1)
        self.assertGreaterEqual(self.start_time(), 100.5)

    def test_final_guard_teardown_update_is_rechecked(self):
        self.drain(completed=0.0)
        calls = []
        def guard():
            calls.append(self.clock[0])
            if len(calls) == 3:  # preflight, spacing, final launch guard
                self.drain(completed=100.0)
        self.backend.guard = guard
        self.assertEqual(self.start_time(), 161.0)

    def test_guard_outlasts_remaining_spacing(self):
        self.drain(completed=39.5)
        self.backend.guard = lambda: self.clock.__setitem__(0, self.clock[0] + .3)
        self.assertGreaterEqual(self.start_time(), 100.5)
        self.assertEqual(self.waits(), [])

    def test_pause_from_final_guard_prevents_start(self):
        self.drain(completed=0.0)
        calls = []
        def guard():
            calls.append(self.clock[0])
            if len(calls) == 3:
                (self.root / 'PAUSE-A').touch()
        self.backend.guard = guard
        self.queue.sleep = lambda _: (self.root / 'STOP-A').touch()
        self.assertEqual(self.queue.run(), 0)
        self.assertEqual(self.backend.runs, [])
        self.assertFalse(self.queue.active.exists())

    def test_queue_edit_during_wait_discards_old_job(self):
        self.drain()
        def sleep(seconds):
            # The spacing waiter must not retain the queue's edit lock.
            with q.lock(self.root / 'edit-A.lock', nonblocking=True):
                self.write([self.job('replacement')])
            self.sleep(seconds)
        self.queue.sleep = sleep
        self.assertEqual(self.start_time(), 151.0)
        self.assertEqual(self.done()[0]['job']['name'], 'replacement')

    def test_wait_is_bounded_when_teardown_keeps_changing(self):
        self.drain()
        def sleep(seconds):
            self.sleep(seconds)
            self.drain(completed=self.clock[0])
        self.queue.sleep = sleep
        with self.assertRaisesRegex(ValueError, 'spacing wait timed out'):
            self.queue.run()
        self.assertEqual(self.clock[0], 100.0 + q.DRAIN_WAIT_LIMIT)
        self.assertEqual(self.backend.runs, [])
        self.assertFalse(self.queue.active.exists())


class LiveWindowTests(QueueTestCase):
    def setUp(self):
        super().setUp()
        self.clock[0] = 100.0
        self.teardown = q.STAGE / 'screen/v3/teardown-state.json'
        self.teardown.parent.mkdir(parents=True)
        q.COORD.mkdir()
        self.boot = q.BOOT_ID_PATH.read_text().strip()
        self.write([self.job()])
        self.backend.after = lambda: setattr(self.queue, 'stopped', True)

    def owner(self, lane='B', scope=None, marker=True):
        owner = dict(pid=12345, start_ticks=50, boot_id=self.boot,
                     lane=lane, scope=scope or 'lane-' + lane)
        proc = q.PROC / '12345'
        proc.mkdir(parents=True, exist_ok=True)
        (proc / 'stat').write_text('12345 (name with ) spaces) S ' + '0 ' * 18 + '50\n')
        if marker:
            q.save(q.COORD / f'active-lane-{lane}.json', owner)
        q.save(self.teardown, dict(boot_id=self.boot, drained=False,
                                  pid=12345, chain_reservation=owner))
        return owner

    def release(self):
        (q.COORD / 'active-lane-B.json').unlink(missing_ok=True)
        (q.COORD / 'active-lane-A.json').unlink(missing_ok=True)
        q.save(self.teardown, dict(boot_id=self.boot, drained=True,
                                  completed_monotonic=self.clock[0]))

    def start_time(self):
        self.assertEqual(self.queue.run(), 0)
        self.assertEqual(len(self.backend.runs), 1)
        return self.clock[0] - self.backend.duration

    def test_a_waits_for_live_b_then_61_seconds_after_drain(self):
        self.owner()
        def sleep(seconds):
            self.sleep(seconds)
            if self.clock[0] == 300.0:  # longer than the spacing-only budget
                self.release()
        self.queue.sleep = sleep
        self.assertEqual(self.start_time(), 361.0)
        self.assertEqual([kind for kind, _ in self.events],
                         ['WAIT-OTHER-LANE-LIVE', 'WAIT-DRAIN-SPACING', 'START', 'DONE', 'STOP'])

    def test_live_drain_owner_without_marker_waits(self):
        self.owner(marker=False)
        self.queue.sleep = lambda seconds: (self.sleep(seconds), self.release() if self.clock[0] == 101.0 else None)
        self.assertEqual(self.start_time(), 162.0)

    def test_v3_pid_only_drain_waits(self):
        self.owner(marker=False)
        q.save(self.teardown, dict(boot_id=self.boot, drained=False, pid=12345))
        self.assertIsNotNone(q.live_window_blocker('A'))
        self.assertIsNotNone(q.live_window_blocker('B'))

    def test_marker_only_waits_before_drain_exists_and_after_drain(self):
        self.owner()
        self.teardown.unlink()
        self.assertIsNotNone(q.live_window_blocker('A'))
        q.save(self.teardown, dict(boot_id=self.boot, drained=True, completed_monotonic=0))
        self.assertIsNotNone(q.live_window_blocker('A'))

    def test_b_is_not_delayed_by_live_a_exactness(self):
        self.owner('A')
        job = dict(self.job(), lane='B')
        (self.root / 'queue-B.txt').write_text(json.dumps(job) + '\n')
        self.queue = q.Queue(self.root, 'B', self.backend, now=lambda: self.clock[0], sleep=self.sleep)
        self.queue.event = lambda kind, **kw: self.events.append((kind, kw))
        self.assertEqual(self.start_time(), 100.0)
        self.assertNotIn('WAIT-OTHER-LANE-LIVE', [kind for kind, _ in self.events])

    def test_other_live_combinations_refused_by_wrapper_wait(self):
        for owner_lane, scope, arriving in [('A', 'whole-host', 'B'),
                                            ('A', 'lane-A', 'A'), ('B', 'lane-B', 'B')]:
            with self.subTest(owner_lane=owner_lane, scope=scope, arriving=arriving):
                self.owner(owner_lane, scope)
                self.assertIsNotNone(q.live_window_blocker(arriving))

    def test_b_does_not_get_unmatched_a_exception(self):
        self.owner('A')
        q.save(q.COORD / 'active-lane-A.json', dict(pid=999))
        self.assertIsNotNone(q.live_window_blocker('B'))

    def test_pause_during_live_wait_no_start(self):
        self.owner()
        def sleep(seconds):
            self.sleep(seconds)
            if (self.root / 'PAUSE-A').exists():
                self.assertEqual(self.backend.runs, [])
                (self.root / 'STOP-A').touch()
            else:
                (self.root / 'PAUSE-A').touch()
        self.queue.sleep = sleep
        self.assertEqual(self.queue.run(), 0)
        self.assertEqual(self.backend.runs, [])
        self.assertFalse(self.queue.active.exists())

    def test_stop_and_signal_during_live_wait_no_start(self):
        self.owner()
        for signal_stop in (False, True):
            with self.subTest(signal=signal_stop):
                self.queue.stopped = False
                (self.root / 'STOP-A').unlink(missing_ok=True)
                self.queue.sleep = lambda _: (setattr(self.queue, 'stopped', True) if signal_stop
                                              else (self.root / 'STOP-A').touch())
                self.assertEqual(self.queue.run(), 0)
                self.assertEqual(self.backend.runs, [])
                self.assertFalse(self.queue.active.exists())

    def test_fault_during_live_wait_halts(self):
        self.owner()
        self.backend.guard = lambda: q.require(self.clock[0] < 101.0, 'fault count changed')
        with self.assertRaisesRegex(ValueError, 'fault count changed'):
            self.queue.run()
        self.assertEqual(self.backend.runs, [])
        self.assertFalse(self.queue.active.exists())

    def test_latch_during_live_wait_halts(self):
        self.owner()
        self.backend.guards = lambda lane: q.Backend.guards(self.backend, lane)
        self.queue.sleep = lambda _: (self.teardown.parent / 'fault-old-A.json').touch()
        with self.assertRaisesRegex(ValueError, 'fault latch'):
            self.queue.run()
        self.assertEqual(self.backend.runs, [])
        self.assertFalse(self.queue.active.exists())

    def test_dead_b_keeps_existing_guards_and_wrapper_path(self):
        self.owner()
        (q.PROC / '12345/stat').unlink()
        before = self.teardown.read_bytes()
        self.assertIsNone(q.live_window_blocker('A'))
        self.backend.guards = lambda lane: q.Backend.guards(self.backend, lane)
        # Queue has never guarded the other lane's stale marker; frozen wrapper
        # remains responsible. Simulate that refusal, without a real launch.
        self.backend.rc, self.backend.duration = 7, 2
        self.assertEqual(self.queue.run(), 1)
        self.assertEqual(self.done()[0]['outcome'], 'REFUSED-fast')
        self.assertEqual(self.teardown.read_bytes(), before)
        self.assertTrue((q.COORD / 'active-lane-B.json').exists())
        self.assertNotIn('WAIT-OTHER-LANE-LIVE', [kind for kind, _ in self.events])

    def test_pid_reuse_and_zombies_keep_existing_path(self):
        self.owner()
        stat = q.PROC / '12345/stat'
        for state, ticks in [('Z', 50), ('X', 50), ('S', 51)]:
            with self.subTest(state=state, ticks=ticks):
                stat.write_text('12345 (name) ' + state + ' ' + '0 ' * 18 + str(ticks))
                self.assertIsNone(q.live_window_blocker('A'))

    def test_other_boot_or_drained_record_without_marker_does_not_wait(self):
        self.owner(marker=False)
        for changes in [dict(boot_id='other'), dict(drained=True)]:
            self.owner(marker=False)
            row = json.loads(self.teardown.read_text())
            q.save(self.teardown, {**row, **changes})
            self.assertIsNone(q.live_window_blocker('A'))

    def test_invalid_records_keep_existing_path(self):
        for value in ['{', '[]', 'null', '{"pid":true}', '{"pid":-1}']:
            (q.COORD / 'active-lane-B.json').write_text(value)
            self.teardown.write_text(value)
            self.assertIsNone(q.live_window_blocker('A'))
        with patch.object(Path, 'read_text', side_effect=PermissionError('unreadable')):
            self.assertIsNone(q.live_window_blocker('A'))

    def test_live_wait_bounded_without_inflight(self):
        self.owner()
        with patch.object(q, 'LIVE_WAIT_LIMIT', 5):
            with self.assertRaisesRegex(ValueError, 'other lane live wait timed out'):
                self.queue.run()
        self.assertEqual(self.clock[0], 105.0)
        self.assertEqual(self.backend.runs, [])
        self.assertFalse(self.queue.active.exists())

    def test_slow_live_logging_clamps_sleep_and_still_times_out(self):
        self.owner()
        original = self.queue.event
        def event(kind, **values):
            original(kind, **values)
            if kind == 'WAIT-OTHER-LANE-LIVE':
                self.clock[0] += 6
        self.queue.event = event
        with patch.object(q, 'LIVE_WAIT_LIMIT', 5):
            with self.assertRaisesRegex(ValueError, 'other lane live wait timed out'):
                self.queue.run()
        self.assertEqual(self.backend.runs, [])
        self.assertFalse(self.queue.active.exists())

    def test_final_guard_live_b_is_rechecked(self):
        calls = []
        def guard():
            calls.append(self.clock[0])
            if len(calls) == 3:
                self.owner()
        self.backend.guard = guard
        self.queue.sleep = lambda seconds: (self.sleep(seconds), self.release() if self.clock[0] == 101.0 else None)
        self.assertEqual(self.start_time(), 162.0)
        self.assertIn('WAIT-OTHER-LANE-LIVE', [kind for kind, _ in self.events])

    def test_live_b_arriving_during_spacing_is_rechecked(self):
        q.save(self.teardown, dict(boot_id=self.boot, drained=True, completed_monotonic=90))
        def sleep(seconds):
            self.sleep(seconds)
            if self.clock[0] == 110.0:
                self.owner()
            elif self.clock[0] == 120.0:
                self.release()
        self.queue.sleep = sleep
        self.assertEqual(self.start_time(), 181.0)
        self.assertIn('WAIT-OTHER-LANE-LIVE', [kind for kind, _ in self.events])

    def test_queue_edit_during_live_wait_discards_old_job(self):
        self.owner()
        def sleep(seconds):
            with q.lock(self.root / 'edit-A.lock', nonblocking=True):
                self.write([self.job('replacement')])
            self.sleep(seconds)
            if self.clock[0] == 101.0:
                self.release()
        self.queue.sleep = sleep
        self.assertEqual(self.start_time(), 162.0)
        self.assertEqual(self.done()[0]['job']['name'], 'replacement')


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


class LaneLatchTests(unittest.TestCase):
    """Real admission guards with temporary latches and a fake fault counter."""

    BOOT = '2cba7160-0000-0000-0000-000000000000'

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.latches = self.root / 'screen/v3'
        self.latches.mkdir(parents=True)
        for name in ('STAGE', 'COORD'):
            patcher = patch.object(q, name, self.root)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.backend = q.Backend()
        patcher = patch.object(self.backend, 'faults', return_value=q.BASE)
        self.counter = patcher.start()
        self.addCleanup(patcher.stop)

    def latch(self, lane=None, name=None):
        path = self.latches / (name or f'fault-{self.BOOT}{"-" + lane if lane else ""}.json')
        path.write_text(json.dumps(dict(boot_id=self.BOOT, reason='screen failed or interrupted')))
        self.addCleanup(lambda: self.assertTrue(path.exists(), 'latch was removed'))
        return path

    def assert_both_stop(self, reason):
        for lane in ('A', 'B'):
            with self.subTest(lane=lane), self.assertRaisesRegex(ValueError, reason):
                self.backend.guards(lane)

    def test_lane_a_latch_allows_b_only_when_count_unchanged(self):
        path = self.latch('A')
        before = path.read_bytes()
        self.assertEqual(self.backend.guards('B'), q.BASE)
        with self.assertRaisesRegex(ValueError, 'fault latch'):
            self.backend.guards('A')
        self.assertEqual(path.read_bytes(), before)

    def test_lane_b_latch_allows_a_only(self):
        self.latch('B')
        self.assertEqual(self.backend.guards('A'), q.BASE)
        with self.assertRaisesRegex(ValueError, 'fault latch'):
            self.backend.guards('B')

    def test_third_fault_stops_both_even_after_backend_restart(self):
        self.latch('A')
        self.assertEqual(self.backend.guards('B'), q.BASE)
        self.counter.return_value = 3
        self.assert_both_stop('kernel fault count')
        with patch.object(q.Backend, 'faults', return_value=3):
            for lane in ('A', 'B'):
                with self.assertRaisesRegex(ValueError, 'kernel fault count'):
                    q.Backend().guards(lane)

    def test_fault_change_without_latch_still_stops_both(self):
        for count in (1, 3):
            self.counter.return_value = count
            self.assert_both_stop('kernel fault count')

    def test_laneless_latch_stops_both(self):
        self.latch()
        self.assert_both_stop('fault latch')

    def test_ambiguous_or_other_boot_latches_remain_global(self):
        for name in ('fault-old-B.json', f'fault-{self.BOOT}-C.json',
                     f'fault-{self.BOOT}-B.json.tmp',
                     'fault-ffffffff-0000-0000-0000-000000000000-B.json'):
            stage = self.root / name
            self.latches = stage / 'screen/v3'
            self.latches.mkdir(parents=True)
            with self.subTest(name=name), patch.object(q, 'STAGE', stage):
                path = self.latch(name=name)
                self.assert_both_stop('fault latch')
                self.assertTrue(path.exists())

    def test_two_lane_latches_stop_both(self):
        self.latch('A')
        self.latch('B')
        self.assert_both_stop('fault latch')

    def test_unreadable_fault_counter_stops_both(self):
        self.latch('A')
        for count in (None, '2', 2.0, True):
            with self.subTest(count=count):
                self.counter.return_value = count
                self.assert_both_stop('kernel fault count')
        for error in (ValueError('journal unavailable'), PermissionError('journal unreadable'),
                      subprocess.TimeoutExpired('journalctl', 30)):
            self.counter.side_effect = error
            for lane in ('A', 'B'):
                with self.assertRaises(type(error)):
                    self.backend.guards(lane)

    def test_other_lane_latch_does_not_bypass_dead_owner(self):
        self.latch('A')
        marker = self.root / 'active-lane-B.json'
        marker.write_text(json.dumps(dict(pid=12345)))
        with patch.object(q.os, 'kill', side_effect=ProcessLookupError()):
            with self.assertRaisesRegex(ValueError, 'dead owner'):
                self.backend.guards('B')
        self.assertTrue(marker.exists())


if __name__ == '__main__':
    unittest.main()
