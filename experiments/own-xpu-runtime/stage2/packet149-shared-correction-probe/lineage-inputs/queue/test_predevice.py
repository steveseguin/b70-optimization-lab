"""CPU-only admission/refusal regression; all queues, proc and receipts are fake."""
import json
from pathlib import Path
import subprocess
from unittest.mock import patch
import lanequeue as q
from test_lanequeue import QueueTestCase


class AdmissionTests(QueueTestCase):
    def setUp(self):
        super().setUp()
        q.PROC.mkdir()
        self.required = 4 * q.HOST_HEADROOM
        self.memory(self.required)

    def memory(self, available):
        (q.PROC / 'meminfo').write_text(f'MemAvailable: {available // 1024} kB\n')

    def test_wait_recovers_with_headroom_and_logs_shortfall(self):
        def sleep(seconds):
            self.sleep(seconds)
            if self.clock[0] == 3:
                self.memory(self.required + q.HOST_HEADROOM)
        self.queue.sleep = sleep
        self.assertTrue(self.queue.wait_host_admission(self.job(), self.required, 20))
        self.assertEqual(self.clock[0], 3)
        self.assertEqual(self.events[0][0], 'WAIT-HOST-ADMISSION')
        self.assertEqual(self.events[0][1]['shortfall_bytes'], q.HOST_HEADROOM)

    def test_timeout_never_starts_or_creates_inflight(self):
        self.write([self.job()])
        with patch.object(q, 'plan_job', return_value={'host_required_available_bytes': self.required}), patch.object(q, 'HOST_WAIT_LIMIT', 3):
            with self.assertRaisesRegex(ValueError, 'host admission wait timed out'):
                self.queue.run()
        self.assertEqual(self.clock[0], 3)
        self.assertFalse(self.queue.active.exists())
        self.assertEqual(self.backend.runs, [])

    def test_full_twenty_minute_budget_is_bounded(self):
        self.assertEqual(q.HOST_WAIT_LIMIT, 1200)
        self.queue.sleep = lambda seconds: self.clock.__setitem__(0, self.clock[0] + seconds)
        with self.assertRaisesRegex(ValueError, 'timed out'):
            self.queue.wait_host_admission(self.job(), self.required, q.HOST_WAIT_LIMIT)
        self.assertEqual(self.clock[0], 1200)

    def test_wait_reorder_is_preserved_before_launch(self):
        self.write([self.job()])
        def sleep(seconds):
            self.sleep(seconds)
            self.write([self.job('replacement')])
            self.memory(self.required + q.HOST_HEADROOM)
        self.queue.sleep = sleep
        self.backend.after = lambda: (self.root / 'STOP-A').touch()
        with patch.object(q, 'plan_job', return_value={'host_required_available_bytes': self.required}):
            self.assertEqual(self.queue.run(), 0)
        self.assertEqual(self.done()[0]['job']['name'], 'replacement')

    def test_pause_stop_and_signal_interrupt_wait(self):
        for flag in ('PAUSE-A', 'STOP-A', 'signal'):
            with self.subTest(flag=flag):
                def sleep(_):
                    if flag == 'signal':
                        self.queue.stopped = True
                    else:
                        (self.root / flag).touch()
                self.queue.sleep = sleep
                self.assertFalse(self.queue.wait_host_admission(self.job(), self.required, 20))
                self.queue.stopped = False
                (self.root / flag).unlink(missing_ok=True)

    def test_fault_or_latch_during_wait_stops(self):
        self.queue.sleep = lambda _: setattr(self.backend, 'guard', lambda: q.require(False, 'fault latch'))
        with self.assertRaisesRegex(ValueError, 'fault latch'):
            self.queue.wait_host_admission(self.job(), self.required, 20)

    def test_bad_meminfo_fails_closed(self):
        for text in ('', 'MemAvailable: -1 kB\n', 'MemAvailable: 4 MB\n'):
            (q.PROC / 'meminfo').write_text(text)
            with self.assertRaises(ValueError):
                q.mem_available()

    def test_requirement_plan_admission_and_packet_fallback(self):
        job = self.job(admission={'host_required_available_bytes': 123})
        self.assertEqual(q.host_requirement(job, {'plan': {'host_required_available_bytes': 456}}), 456)
        with self.assertRaises(ValueError):
            q.host_requirement(self.job(), {'scope': 'whole-host'})
        for value in (True, 0, -1, '123', 1.2):
            with self.assertRaises(ValueError):
                q.host_requirement(self.job(), {'host_required_available_bytes': value})
        script = self.root / 'runner.py'
        script.touch()
        q.save(self.root / 'memory-plan.json', {'budget': {'host_required_available_bytes': 789}})
        job['argv'] = ['/usr/bin/python3', '-B', str(script)]
        job.pop('admission')
        self.assertEqual(q.host_requirement(job, {}), 789)

    def test_actual_plan_output_supplies_requirement(self):
        script = self.root / 'runner.py'
        script.write_text("parser.add_argument('--plan')\n")
        job = self.job()
        job['argv'] = ['/usr/bin/python3', '-B', str(script)]
        # The shared fixture patches plan_job; recover its original function.
        original = self._plan_original
        invoke = lambda *a, **kw: subprocess.CompletedProcess([], 0, json.dumps(
            {'scope': 'whole-host', 'host_required_available_bytes': 118308908048}), '')
        self.assertEqual(original(job, '/lib', invoke)['host_required_available_bytes'], 118308908048)

    _plan_original = staticmethod(q.plan_job)

    def test_memory_rechecked_after_review_before_start(self):
        job = self.job()
        job['review'] = str(Path(q.__file__))
        job['argv'] += ['--fault-review', '{REVIEW}']
        self.write([job])
        self.memory(self.required + q.HOST_HEADROOM)
        self.backend.review = lambda *_: (self.memory(0), '/review')[1]
        with patch.object(q, 'plan_job', return_value={'host_required_available_bytes': self.required}), patch.object(q, 'HOST_WAIT_LIMIT', 2):
            with self.assertRaisesRegex(ValueError, 'host admission wait timed out'):
                self.queue.run()
        self.assertEqual(self.backend.runs, [])


class PredeviceTests(QueueTestCase):
    def setUp(self):
        super().setUp()
        self.output = self.root / 'output'
        self.output.mkdir()
        self.first = self.job('p131-B-smoke12')
        self.first['argv'] += ['--output', str(self.output)]
        self.proof = dict(passed=False, device_executed=False, error='unsafe identity path', child_still_running=False)
        q.save(self.output / 'window.json', self.proof)
        self.observation = dict(pids=[123], samples=3, device_fds=[], errors=[], live_pids=[])
        self.write([self.first, self.job('p131-B-0-control'), self.job('p132-independent')])
        self.backend.rc, self.backend.result = 1, 'exit-code'
        self.backend.guards = lambda lane: q.Backend.guards(self.backend, lane)
        self.backend.after = self.after

    def after(self):
        self.backend.device_observation = self.observation
        if len(self.backend.runs) == 2:
            self.backend.rc, self.backend.result = 0, 'success'
            (self.root / 'STOP-A').touch()

    def assert_stops(self):
        self.assertEqual(self.queue.run(), 1)
        self.assertEqual(len(self.backend.runs), 1)
        self.assertNotEqual(self.done()[0]['outcome'], 'REFUSED-PREDEVICE')
        self.assertEqual(len(q.read_queue(self.root, 'A')), 2)

    def test_refusal_drops_dependents_and_runs_independent(self):
        self.assertEqual(self.queue.run(), 0)
        self.assertEqual([r['outcome'] for r in self.done()], ['REFUSED-PREDEVICE', 'SKIPPED-DEPENDENCY', 'DONE'])
        self.assertEqual(self.done()[0]['dropped_dependencies'], ['p131-B-0-control'])
        self.assertEqual(len(self.backend.runs), 2)
        self.assertTrue(any(k == 'ALERT' and 'no retry' in v['reason'] for k, v in self.events))

    def test_cross_lane_and_transitive_dependencies(self):
        other = dict(self.job('other', depends_on=[self.first['name']]), lane='B')
        leaf = dict(self.job('leaf', depends_on=['other']), lane='B')
        independent = dict(self.job('p131b-independent'), lane='B')
        (self.root / 'queue-B.txt').write_text(''.join(json.dumps(r) + '\n' for r in (other, leaf, independent)))
        self.assertEqual(self.queue.run(), 0)
        self.assertEqual(q.read_queue(self.root, 'B'), [independent])
        self.assertEqual(len((self.root / 'done-B.txt').read_text().splitlines()), 2)

    def test_inflight_dependency_is_never_removed(self):
        other = dict(self.job('other', depends_on=[self.first['name']]), lane='B')
        (self.root / 'queue-B.txt').write_text(json.dumps(other) + '\n')
        q.save(self.root / 'inflight-B.json', {'job': other})
        with self.assertRaisesRegex(ValueError, 'already inflight'):
            self.queue.run()
        self.assertEqual(q.read_queue(self.root, 'B'), [other])
        self.assertTrue(self.queue.active.exists())

    def test_positive_device_receipt_even_nested_stops(self):
        child = self.output / 'K1a'
        child.mkdir()
        q.save(child / 'window.json', dict(passed=True, device_executed=True))
        self.assert_stops()

    def test_nested_refusal_is_not_a_whole_job_receipt(self):
        child = self.output / 'last-window'
        child.mkdir()
        (self.output / 'window.json').rename(child / 'window.json')
        self.assert_stops()

    def test_missing_receipt_stops(self):
        (self.output / 'window.json').unlink()
        self.assert_stops()

    def test_explicit_no_pin_or_model_load_receipt(self):
        q.save(self.output / 'window.json', dict(passed=False, reason='REFUSED: no pin or model load'))
        self.assertTrue(q.predevice_evidence(self.first, self.observation)['receipt_sha256'])

    def test_refusal_receipt_booleans_fail_closed(self):
        for key in ('device_executed', 'child_still_running'):
            for value in (True, 0, 1, None, 'false'):
                with self.subTest(key=key, value=value):
                    q.save(self.output / 'window.json', {**self.proof, key: value})
                    with self.assertRaises(ValueError):
                        q.predevice_evidence(self.first, self.observation)

    def test_conflicting_no_load_and_device_execution_stops(self):
        q.save(self.output / 'window.json', {**self.proof, 'device_executed': True,
                                          'reason': 'no pin or model load'})
        self.assert_stops()

    def test_newly_appended_independent_job_survives_completion(self):
        def after():
            self.after()
            if len(self.backend.runs) == 1:
                self.write([self.job('new-independent'), self.first, self.job('p131-B-control')])
        self.backend.after = after
        self.assertEqual(self.queue.run(), 0)
        self.assertEqual(self.done()[-1]['job']['name'], 'new-independent')

    def test_skipped_dependency_does_not_mask_older_lane_failure(self):
        self.queue.done.write_text('\n'.join(json.dumps(dict(job=self.job(name), outcome=outcome,
            end_unix=0)) for name, outcome in [('old', 'FAILED'), ('skip', 'SKIPPED-DEPENDENCY')]) + '\n')
        with self.assertRaisesRegex(ValueError, 'previous job failed'):
            self.queue.run()
        self.assertEqual(self.backend.runs, [])

    def test_malformed_receipt_stops(self):
        (self.output / 'window.json').write_text('[]')
        self.assert_stops()

    def test_unreadable_receipt_stops(self):
        with patch.object(q, 'predevice_evidence', side_effect=PermissionError('receipt unreadable')):
            self.assert_stops()

    def test_ambiguous_observations_reject(self):
        for key, value in (('device_fds', ['/dev/dri/renderD128']), ('errors', ['denied']),
                           ('live_pids', [123]), ('pids', []), ('samples', 0)):
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    q.predevice_evidence(self.first, {**self.observation, key: value})

    def test_observed_render_fd_stops(self):
        self.observation['device_fds'] = ['/dev/dri/renderD128']
        self.assert_stops()

    def test_marker_stops_and_is_preserved(self):
        q.COORD.mkdir()
        marker = q.COORD / 'active-lane-A.json'
        self.backend.after = lambda: (self.after(), q.save(marker, {'pid': 123}))
        self.assert_stops()
        self.assertTrue(marker.exists())

    def test_new_fault_count_stops(self):
        self.backend.after = lambda: (self.after(), setattr(self.backend, 'fault_count', 3))
        self.assert_stops()

    def test_even_other_lane_latch_stops_refusal_exception(self):
        shared = q.STAGE / 'screen/v3'
        shared.mkdir(parents=True)
        latch = shared / ('fault-' + q.BOOT_ID_PATH.read_text().strip() + '-B.json')
        self.backend.after = lambda: (self.after(), q.save(latch, {}))
        self.assert_stops()

    def test_undrained_teardown_stops(self):
        shared = q.STAGE / 'screen/v3'
        shared.mkdir(parents=True)
        self.backend.after = lambda: (self.after(), q.save(shared / 'teardown-state.json', {'drained': False}))
        self.assert_stops()

    def test_signal_exit_never_reclassified(self):
        self.backend.result = 'signal'
        self.assert_stops()

    def test_restart_after_refusal_allows_next_but_not_replay(self):
        self.backend.after = lambda: (self.after(), (self.root / 'STOP-A').touch())
        self.assertEqual(self.queue.run(), 0)
        (self.root / 'STOP-A').unlink()
        self.write([self.first])
        with self.assertRaisesRegex(ValueError, 'no automatic replay'):
            self.queue.run()


class ObservationTests(QueueTestCase):
    def task(self, pid, group, fd=None):
        path = q.PROC / str(pid)
        path.mkdir(parents=True)
        (path / 'cgroup').write_text('0::/user.slice/' + group + '\n')
        (path / 'fd').mkdir()
        if fd:
            (path / 'fd/4').symlink_to(fd)
        return path

    def test_tracks_unit_children_and_retains_closed_device_fd(self):
        first = self.task(111, 'screen-one.service')
        child = self.task(222, 'screen-one.service/subgroup', '/dev/dri/renderD128')
        self.task(333, 'screen-other.service', '/dev/dri/renderD129')
        obs = q.DeviceObservation('screen-one.service')
        obs.sample()
        (child / 'fd/4').unlink()
        (first / 'cgroup').write_text('0::/gone\n')
        (child / 'cgroup').write_text('0::/gone\n')
        obs.sample()
        self.assertEqual(obs.evidence(), dict(pids=[111, 222], samples=2,
            device_fds=['/dev/dri/renderD128'], errors=[], live_pids=[]))

    def test_unreadable_proc_cannot_be_negative_device_proof(self):
        obs = q.DeviceObservation('screen-one.service')
        obs.sample()
        self.assertTrue(obs.errors)
