"""Pre-START checks use only temporary queues and mocked CPU/device work."""
import json
from pathlib import Path
import subprocess
from unittest.mock import patch

import lanequeue as q
from test_lanequeue import QueueTestCase


class PrestartTests(QueueTestCase):
    def reviewed_job(self):
        job = self.job('packet58ae-combined-A')
        job['review'] = str(Path(q.__file__))
        job['argv'] += ['--fault-review', '{REVIEW}']
        return job

    def test_failed_review_receipted_pruned_and_next_job_runs(self):
        job = self.reviewed_job()
        dependent = self.job('dependent', depends_on=[job['name']])
        other = dict(self.job('cross-lane', depends_on=['dependent']), lane='B')
        self.write([job, dependent, self.job('independent')])
        (self.root / 'queue-B.txt').write_text(json.dumps(other) + '\n')
        self.backend.review = lambda *_: q.require(False, 'fresh fault review failed')
        self.backend.after = lambda: setattr(self.queue, 'stopped', True)
        # Use real durable events, not only the fixture's in-memory event list.
        self.queue.event = lambda *a, **kw: q.Queue.event(self.queue, *a, **kw)
        self.assertEqual(self.queue.run(), 0)
        self.assertEqual(len(self.backend.runs), 1)
        self.assertIn('--unit=screen-independent', self.backend.runs[0])
        rows = self.done()
        self.assertEqual([r['outcome'] for r in rows],
                         ['REFUSED-PREDEVICE', 'SKIPPED-DEPENDENCY', 'DONE'])
        refusal = rows[0]
        receipt = json.loads(Path(refusal['receipt']).read_text())
        self.assertEqual(receipt['reason'], 'fresh fault review failed')
        self.assertEqual(receipt['phase'], 'before-START')
        self.assertIs(receipt['launch_attempted'], False)
        self.assertIs(receipt['device_executed'], False)
        self.assertEqual(refusal['dropped_dependencies'], ['cross-lane', 'dependent'])
        self.assertEqual(q.read_queue(self.root, 'B'), [])
        events = [json.loads(line) for line in (self.root / 'events-A.jsonl').read_text().splitlines()]
        self.assertFalse(any(r['event'] == 'START' and r['name'] == job['name'] for r in events))
        self.assertTrue(any(r['event'] == 'REFUSED-PREDEVICE' and r['receipt'] == refusal['receipt'] for r in events))
        self.assertTrue(any(r['event'] == 'ALERT' and 'fresh fault review failed' in r['reason'] for r in events))
        self.assertFalse(self.queue.active.exists())

    def test_other_preparation_failures_continue(self):
        for target, failure in [('plan_job', ValueError('CPU plan failed')),
                                ('library_path', OSError('library file unavailable')),
                                ('check_pins', RuntimeError('unexpected CPU-check error')),
                                ('command', ValueError('invalid command'))]:
            with self.subTest(target=target):
                # Unique names preserve the completed-name replay guard.
                job = self.job(target)
                self.write([job, self.job(target + '-next')])
                self.queue.stopped = False
                self.backend.after = lambda: setattr(self.queue, 'stopped', True)
                original = getattr(q, target)
                calls = []
                def fail_once(*args, **kwargs):
                    calls.append(True)
                    if len(calls) == 1:
                        raise failure
                    return original(*args, **kwargs)
                with patch.object(q, target, side_effect=fail_once):
                    self.assertEqual(self.queue.run(), 0)
                self.assertEqual(self.done()[-2]['outcome'], 'REFUSED-PREDEVICE')
                self.assertIn('--unit=screen-' + target + '-next', self.backend.runs[-1])

    def test_review_timeout_is_an_explicit_refusal(self):
        self.write([self.reviewed_job()])
        with patch.object(self.backend, 'review', side_effect=subprocess.TimeoutExpired('review', 120)):
            self.assert_prestart_refusal('timed out')
        self.assertEqual(self.backend.runs, [])

    def test_missing_review_file_refuses_only_its_row(self):
        job = self.reviewed_job()
        job['review'] = str(self.root / 'missing-review.py')
        self.write([self.job('first'), job, self.job('last')])
        def after():
            if len(self.backend.runs) == 2:
                self.queue.stopped = True
        self.backend.after = after
        self.assertEqual(self.queue.run(), 0)
        self.assertEqual([r['outcome'] for r in self.done()], ['DONE', 'REFUSED-PREDEVICE', 'DONE'])
        self.assertEqual(self.done()[1]['reason'], 'review tool unavailable')
        self.assertIn('--unit=screen-first', self.backend.runs[0])
        self.assertIn('--unit=screen-last', self.backend.runs[1])

    def test_ambiguous_queue_identity_still_stops(self):
        self.write([self.job('duplicate'), self.job('duplicate')])
        with self.assertRaisesRegex(ValueError, 'duplicate job name'):
            self.queue.run()
        self.assertEqual(self.backend.runs, [])
        self.assertFalse(self.queue.done.exists())

    def test_fault_during_review_still_stops_without_dropping_row(self):
        job = self.reviewed_job()
        self.write([job, self.job('next')])
        def review(*_):
            self.backend.fault_count = q.BASE + 1
            raise ValueError('fresh fault review failed')
        self.backend.review = review
        with self.assertRaisesRegex(q.SafetyStop, 'kernel fault count'):
            self.queue.run()
        self.assertEqual(q.read_queue(self.root, 'A')[0], job)
        self.assertFalse(self.queue.done.exists())
        self.assertEqual(self.backend.runs, [])

    def test_guard_failure_is_not_swallowed_if_next_check_could_pass(self):
        self.write([self.job()])
        with patch.object(self.backend, 'guards', side_effect=[q.BASE, ValueError('journal unavailable'), q.BASE]):
            with self.assertRaisesRegex(q.SafetyStop, 'journal unavailable'):
                self.queue.run()
        self.assertFalse(self.queue.done.exists())
        self.assertEqual(self.backend.runs, [])

    def test_row_replaced_during_failed_review_is_not_dropped(self):
        self.write([self.reviewed_job()])
        def review(*_):
            self.write([self.job('replacement')])
            raise ValueError('fresh fault review failed')
        self.backend.review = review
        self.backend.after = lambda: setattr(self.queue, 'stopped', True)
        self.assertEqual(self.queue.run(), 0)
        self.assertEqual([r['job']['name'] for r in self.done()], ['replacement'])

    def test_restart_after_prestart_refusal_is_allowed(self):
        self.write([self.reviewed_job()])
        with patch.object(self.backend, 'review', side_effect=ValueError('review failed')):
            self.assert_prestart_refusal('review failed')
        self.queue.stopped = False
        self.write([self.job('new-job')])
        self.backend.after = lambda: setattr(self.queue, 'stopped', True)
        self.assertEqual(self.queue.run(), 0)
        self.assertEqual(self.done()[-1]['outcome'], 'DONE')
