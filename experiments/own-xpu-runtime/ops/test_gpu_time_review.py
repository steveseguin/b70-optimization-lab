#!/usr/bin/env python3
"""CPU-only accounting regression tests; journals and systemctl are mocked."""
import contextlib
import datetime as dt
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import gpu_time_review as review


BEGIN = dt.datetime(2026, 10, 17, 12, tzinfo=dt.timezone.utc)
NOW = BEGIN + dt.timedelta(hours=1)


def minute(n):
    return BEGIN + dt.timedelta(minutes=n)


class Clock(dt.datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW


def journal(n, message):
    return f'{minute(n).isoformat()} host systemd[1000]: {message}'


class ReviewTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'lane-queue').mkdir()
        for lane in 'AB':
            (self.root / 'lane-queue' / f'events-{lane}.jsonl').write_text('')
        self.ops = patch.object(review, 'OPS', self.root)
        self.ops.start()
        self.addCleanup(self.ops.stop)

    def events(self, lane, rows):
        path = self.root / 'lane-queue' / f'events-{lane}.jsonl'
        path.write_text(''.join(json.dumps(dict(utc=minute(n).isoformat(), lane=lane,
                                               event=kind, name=name)) + '\n'
                                for n, kind, name in rows))

    def test_union_does_not_hide_lane_b_gap(self):
        self.events('A', [(0, 'START', 'a'), (59, 'DONE', 'a')])
        self.events('B', [(0, 'START', 'b1'), (20, 'DONE', 'b1'),
                          (41, 'START', 'b2'), (59, 'DONE', 'b2')])
        # b2's unit has already disappeared from the available journal.
        lines = '\n'.join([
            journal(0, 'Started screen-a.service - A.'),
            journal(0, 'Started screen-b1.service - B.'),
            journal(20, 'screen-b1.service: Deactivated successfully.'),
            journal(20, 'screen-b1.service: Consumed 1s CPU time.'),
            journal(59, 'screen-a.service: Deactivated successfully.'),
        ])

        def run(cmd, **kwargs):
            if cmd[0] == 'journalctl':
                return subprocess.CompletedProcess(cmd, 0, lines, '')
            if cmd[0] == 'systemctl':
                self.fail('Durable queue evidence should avoid systemctl here')
            return subprocess.CompletedProcess(cmd, 0, '', '')

        output = io.StringIO()
        with patch.object(review.subprocess, 'run', side_effect=run), \
             patch.object(review.dt, 'datetime', Clock), \
             patch.object(review, 'device_evidence', return_value=(
                 [(minute(0), minute(59), 'screen-a.service', 'device'),
                  (minute(0), minute(20), 'screen-b1.service', 'device'),
                  (minute(41), minute(59), 'screen-b2.service', 'device')], {}, [], [])), \
             patch.object(review, 'SCRATCH', str(self.root)), \
             patch.object(review, 'REPO', str(self.root)), \
             patch('sys.argv', ['gpu_time_review.py', '--hours', '1']), \
             contextlib.redirect_stdout(output):
            review.main()
        text = output.getvalue()
        self.assertIn('Device units in flight (union, excl. pure waiters): 0.98 h = 98%', text)
        self.assertIn('Lane A (cards 0+1) busy/held: 0.98 h = 98%', text)
        self.assertIn('Lane B (cards 2+3) busy/held: 0.63 h = 63%', text)
        self.assertIn('12:20-12:41 UTC  21 min', text)
        self.assertEqual(text.count('screen-a.service'), 1)  # no duplicate listing
        for section in ('Idle gaps > 5 min (no device', 'Device units:',
                        'Codex jobs', 'Commits in window:', 'Record floor unavailable:'):
            self.assertIn(section, text)

    def test_affinity_and_fixed_lane_classification(self):
        for affinity, expected in [('0-3,16-19', 'A'), ('4-7 20-23', 'B'),
                                   ('4 5 6 7 20 21 22 23', 'B'),
                                   ('', None), ('0-31', None), ('garbage', None)]:
            with self.subTest(affinity=affinity), patch.object(
                    review.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, affinity)) as run:
                self.assertEqual(review.unit_lane('screen-old.service', {}), expected)
                self.assertEqual(run.call_args.args[0], ['systemctl', '--user', 'show',
                    'screen-old.service', '--property=CPUAffinity', '--value'])
        with patch.object(review.subprocess, 'run', side_effect=AssertionError('unexpected command')):
            for unit in ('packet70-chain.service', 'packet80-chain.service',
                         'packet84-chain-resume.service', 'p61x-chain.service',
                         'packet58-onecard-k1.service'):
                self.assertEqual(review.unit_lane(unit, {}), 'A')
            self.assertEqual(review.unit_lane('screen-old.service', {'screen-old.service': 'B'}), 'B')

    def test_terminal_events_and_unfinished_start(self):
        kinds = ['DONE', 'REFUSED-fast', 'FAILED', 'FAILED-status',
                 'FAILED-postflight', 'REPORT-FAILED']
        rows = []
        for i, kind in enumerate(kinds):
            rows.extend([(i * 2, 'START', kind), (i * 2 + 1, kind, kind)])
        rows.extend([(20, 'START', 'live'), (25, 'START', 'lost')])
        self.events('A', rows)
        with (self.root / 'lane-queue/events-A.jsonl').open('a') as stream:
            stream.write('{partial\n')
        notes = set()
        with patch.object(review, 'active', side_effect=lambda u: u == 'screen-live.service'):
            spans, lanes = review.queue_events(NOW, notes)
        self.assertEqual(len(spans), 7)
        self.assertEqual(spans[-1], (minute(20), NOW, 'screen-live.service', 'still active'))
        self.assertEqual(lanes['screen-live.service'], 'A')
        self.assertTrue(any('end unknown' in n for n in notes))
        self.assertTrue(any('malformed' in n for n in notes))

    def test_journal_failed_and_still_active(self):
        lines = '\n'.join([
            journal(-5, 'Started packet80-chain.service - chain.'),
            journal(10, "packet80-chain.service: Failed with result 'exit-code'."),
            journal(10, 'packet80-chain.service: Consumed 1s CPU time.'),
            journal(30, 'Started packet58-onecard-k1.service - onecard.'),
        ])
        with patch.object(review.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, lines)), \
             patch.object(review, 'active', return_value=True), \
             patch.object(review.dt, 'datetime', Clock):
            spans, now = review.parse(1)
        self.assertEqual(now, NOW)
        self.assertEqual(spans[0], (minute(-5), minute(10), 'packet80-chain.service', 'failed'))
        self.assertEqual(spans[1][-1], 'still active')

    def test_clipping_union_and_gap_threshold(self):
        seconds, gaps = review.accounting([(minute(-20), minute(10)),
                                           (minute(5), minute(20)),
                                           (minute(25), minute(40)),
                                           (minute(46), minute(80))], BEGIN, NOW)
        self.assertEqual(seconds, 49 * 60)
        self.assertEqual(gaps, [(minute(40), minute(46))])
        self.assertEqual(review.accounting([], BEGIN, NOW), (0, [(BEGIN, NOW)]))

    def test_waiters_excluded_and_unknown_lane_disclosed(self):
        intervals = [(BEGIN, NOW, 'p58-after-p57.service', 'ok'),
                     (minute(10), minute(20), 'screen-unattributed.service', 'ok')]
        output = io.StringIO()
        with patch.object(review, 'parse', return_value=(intervals, NOW)), \
             patch.object(review, 'queue_events', return_value=([], {})), \
             patch.object(review, 'unit_lane', return_value=None), \
             patch.object(review, 'device_evidence', return_value=(intervals, {}, [], [])), \
             patch.object(review.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '')), \
             patch.object(review, 'SCRATCH', str(self.root)), \
             patch.object(review, 'REPO', str(self.root)), \
             patch('sys.argv', ['gpu_time_review.py', '--hours', '1']), \
             contextlib.redirect_stdout(output):
            review.main()
        text = output.getvalue()
        self.assertIn('union, excl. pure waiters): 0.17 h = 17%', text)
        self.assertIn('Lane A (cards 0+1) busy/held: 0.00 h = 0%', text)
        self.assertIn('Lane B (cards 2+3) busy/held: 0.00 h = 0%', text)
        self.assertIn('Unassigned units count only in the combined union', text)

    def test_wait_category_subtracts_busy_and_unions_duplicates(self):
        self.assertEqual(review.subtract([(minute(10), minute(40)),
                                          (minute(15), minute(30))],
                                         [(minute(0), minute(20)),
                                          (minute(25), minute(30))]),
                         [(minute(20), minute(25)), (minute(30), minute(40))])


if __name__ == '__main__':
    unittest.main()
