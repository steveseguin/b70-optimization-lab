"""CPU-only storage admission and historical packet150 replay. No real launches."""
import copy
import hashlib
import io
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
from unittest.mock import patch

import lanequeue as q
from test_lanequeue import QueueTestCase

REAL_PLAN = q.plan_job
FIXTURE = json.loads(Path(__file__).with_name('test_storage_packet150.json').read_text())


class StorageTests(QueueTestCase):
    def setUp(self):
        super().setUp()
        self.free = 40_000_000_000
        patch.object(q.shutil, 'disk_usage', side_effect=lambda _: SimpleNamespace(free=self.free)).start()

    def test_passing_boundary_and_one_byte_short(self):
        job = self.job(planned_write_bytes=5_500_000_000)
        self.free = 30_500_000_000
        row = q.storage_admission(job)
        self.assertTrue(row['passed'])
        self.assertEqual(row['required_free_bytes'], self.free)
        self.free -= 1
        with self.assertRaises(q.StorageRefusal) as caught:
            q.storage_admission(job)
        self.assertEqual(caught.exception.receipt['root_free_bytes'], self.free)
        self.assertIn('required_bytes=30500000000', str(caught.exception))

    def test_default_writes_and_explicit_view_count(self):
        job = self.job()
        self.assertEqual(q.storage_requirement(job)['planned_write_bytes'], 1_100_000_000)
        job['argv'] += ['--kind', 'bracket']
        row = q.storage_requirement(job)
        self.assertEqual(row['planned_write_bytes'], 5_500_000_000)
        self.assertIn('default', row['reservation_source'])
        job['argv'] += ['--views=7']
        self.assertEqual(q.storage_requirement(job)['planned_write_bytes'], 7_700_000_000)

    def test_proposal_and_packet_plan_reservations(self):
        job = self.job(planned_write_bytes=123)
        q.validate(job, 'A')
        self.assertEqual(q.storage_requirement(job, {'planned_write_bytes': 456})['planned_write_bytes'], 123)
        self.assertEqual(q.storage_requirement(self.job(), {'planned_write_bytes': 456})['planned_write_bytes'], 456)
        for value in (True, -1, '123', 1.5, None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                q.validate(self.job(planned_write_bytes=value), 'A')

    def test_sealed_per_packet_reservation_and_views(self):
        script = self.root / 'bracket_job.py'
        script.touch()
        screen = self.root / 'screen.py'
        screen.write_text("WRITES = {'tp2': 1200000000, 'onecard': 256 * 1024**2}\n")
        config = self.root / 'configs/split-bracket.json'
        config.parent.mkdir()
        q.save(config, {'views': [{}, {}, {}]})
        q.save(self.root / 'cpu-seal.json', {'sources': {
            str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (screen, config)}})
        job = self.job()
        job['argv'] = ['/usr/bin/python3', '-B', str(script), '--kind', 'bracket', '--variant', 'split']
        row = q.storage_requirement(job)
        self.assertEqual(row['planned_write_bytes'], 3_600_000_000)
        self.assertIn('sealed', row['reservation_source'])
        config.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'pin changed'):
            q.storage_requirement(job)

    def test_plan_uses_packet_reservation(self):
        script = self.root / 'plan.py'
        script.write_text("p.add_argument('--plan')\n")
        job = self.job()
        job['argv'] = ['/usr/bin/python3', '-B', str(script)]
        invoke = lambda *a, **kw: subprocess.CompletedProcess([], 0, '{"planned_write_bytes": 6000000000}', '')
        row = REAL_PLAN(job, '/lib', invoke)
        self.assertEqual(row['storage_admission']['planned_write_bytes'], 6_000_000_000)
        self.free = 30_000_000_000
        with self.assertRaises(q.StorageRefusal):
            REAL_PLAN(job, '/lib', invoke)

    def test_plan_cli_writes_receipt_and_checks_next_without_queue_edits(self):
        self.write([self.job('large', planned_write_bytes=20_000_000_000), self.job('small')])
        before = (self.root / 'queue-A.txt').read_bytes()
        with patch.object(q, 'plan_job', side_effect=REAL_PLAN), patch.object(q, 'cpu_setup'), \
             patch.object(q.sys, 'argv', ['lanequeue.py', 'plan', '--lane', 'A', '--directory', str(self.root)]), \
             patch('sys.stdout', new_callable=io.StringIO) as out:
            self.assertEqual(q.main(), 1)
        rows = [json.loads(line) for line in out.getvalue().splitlines()]
        self.assertEqual([r['event'] for r in rows if 'event' in r], ['REFUSED-PREDEVICE', 'ALERT'])
        self.assertEqual(rows[-1]['name'], 'small')
        self.assertTrue(rows[-1]['storage_admission']['passed'])
        receipt = json.loads(next(self.root.glob('*.plan-storage-refusal.json')).read_text())
        self.assertFalse(receipt['launch_attempted'])
        self.assertEqual(receipt['required_free_bytes'], 45_000_000_000)
        self.assertEqual((self.root / 'queue-A.txt').read_bytes(), before)

    def test_prestart_refusal_continues_and_skips_dependents(self):
        first = self.job('large', planned_write_bytes=20_000_000_000)
        self.write([first, self.job('dependent', depends_on=['large']), self.job('small')])
        self.backend.after = lambda: setattr(self.queue, 'stopped', True)
        with patch.object(q, 'plan_job', side_effect=REAL_PLAN):
            self.assertEqual(self.queue.run(), 0)
        self.assertEqual([r['outcome'] for r in self.done()], ['REFUSED-PREDEVICE', 'SKIPPED-DEPENDENCY', 'DONE'])
        self.assertEqual(len(self.backend.runs), 1)
        self.assertEqual([v['name'] for k, v in self.events if k == 'START'], ['small'])
        receipt = json.loads(Path(self.done()[0]['receipt']).read_text())
        self.assertFalse(receipt['device_executed'])
        self.assertEqual(receipt['root_free_bytes'], self.free)
        self.assertTrue(any(k == 'ALERT' and 'required_bytes=45000000000' in v['reason'] for k, v in self.events))

    def test_disk_rechecked_after_review(self):
        job = self.job(planned_write_bytes=5_500_000_000)
        job.update(review=str(Path(q.__file__)))
        job['argv'] += ['--fault-review', '{REVIEW}']
        self.write([job])
        def review(*args):
            self.free = 30_000_000_000
            return '/review'
        self.backend.review = review
        with patch.object(q, 'plan_job', side_effect=REAL_PLAN):
            self.assert_prestart_refusal('free-storage floor')
        self.assertEqual(self.backend.runs, [])


class StorageReplayTests(QueueTestCase):
    def setUp(self):
        super().setUp()
        patch.object(q.shutil, 'disk_usage', return_value=SimpleNamespace(free=40_000_000_000)).start()

    def replay(self, *, window=None, observation=None, text=None, result='exit-code'):
        historical = copy.deepcopy(FIXTURE['record'])
        self.assertEqual([r['event'] for r in FIXTURE['events']], ['START', 'REFUSED-fast', 'ALERT'])
        self.assertEqual(FIXTURE['exit_receipt']['ExecMainStatus'], '1')
        self.output = self.root / 'packet150-output'
        job = historical['job']
        # Preserve the actual refusal clocks, rc and PID observations; relocate
        # all paths into the fixture and substitute a fake command/plan/backend.
        job['lane'] = 'A'
        job['argv'] = ['/usr/bin/true', '--output', str(self.output)]
        job['review'] = None
        self.write([job, self.job('dependent', depends_on=[job['name']]), self.job('independent')])
        self.backend.duration = historical['duration_seconds']
        self.backend.rc, self.backend.result = historical['rc'], result
        self.backend.failure_text = lambda *args: FIXTURE['journal'] if text is None else text
        def after():
            self.backend.device_observation = historical['device_observation'] if observation is None else observation
            if len(self.backend.runs) == 1 and window is not None:
                (self.output / 'nested').mkdir(parents=True)
                q.save(self.output / 'nested/window.json', window)
            if len(self.backend.runs) == 2:
                self.backend.rc, self.backend.result = 0, 'success'
                self.queue.stopped = True
        self.backend.after = after
        return self.queue.run()

    def test_packet150_2344_refusal_replay_continues(self):
        self.assertEqual(self.replay(), 0)
        self.assertEqual([r['outcome'] for r in self.done()], ['REFUSED-PREDEVICE', 'SKIPPED-DEPENDENCY', 'DONE'])
        self.assertEqual(len(self.backend.runs), 2)
        receipt = json.loads(Path(self.done()[0]['predevice_evidence']['receipt']).read_text())
        self.assertIn('free-storage floor', receipt['refusal_text'])
        self.assertFalse(receipt['device_executed'])
        self.assertTrue(any(k == 'ALERT' and 'continuing' in v['reason'] for k, v in self.events))

    def test_storage_refusal_after_device_window_stops(self):
        self.assertEqual(self.replay(window={'device_executed': True, 'passed': False}), 1)
        self.assertEqual(len(self.backend.runs), 1)

    def test_storage_refusal_with_observed_device_stops(self):
        obs = {**FIXTURE['record']['device_observation'], 'device_fds': ['/dev/dri/renderD128']}
        self.assertEqual(self.replay(observation=obs), 1)

    def test_storage_refusal_with_live_child_stops(self):
        obs = {**FIXTURE['record']['device_observation'], 'live_pids': [1764582]}
        self.assertEqual(self.replay(observation=obs), 1)

    def test_unrelated_failure_and_signal_still_stop(self):
        self.assertEqual(self.replay(text='ValueError: unrelated problem'), 1)

    def test_signal_still_stops(self):
        self.assertEqual(self.replay(result='signal'), 1)

    def test_failure_journal_is_scoped_to_attempt(self):
        log = self.root / 'unit.log'
        log.write_text('manager status')
        with patch.object(q.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, 'refusal', '')) as run:
            text = q.Backend().failure_text('packet150', '2026-10-18T23:44:02Z', '2026-10-18T23:44:06Z', log)
        self.assertIn('refusal', text)
        self.assertIn('screen-packet150.service', run.call_args.args[0])
        self.assertIn('2026-10-18T23:44:02Z', run.call_args.args[0])
        self.assertIn('2026-10-18T23:44:06Z', run.call_args.args[0])
