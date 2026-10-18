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
        results = patch.object(review, 'RESULTS', self.root / 'results')
        results.start()
        self.addCleanup(results.stop)

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
                 'FAILED-postflight', 'REPORT-FAILED', 'REFUSED-admission']
        rows = []
        for i, kind in enumerate(kinds):
            rows.extend([(i * 2, 'START', kind), (i * 2 + 1, kind, kind)])
        rows.extend([(20, 'START', 'live'), (25, 'START', 'lost')])
        self.events('A', rows)
        with (self.root / 'lane-queue/events-A.jsonl').open('a') as stream:
            stream.write('{partial\n')
        notes = set()
        with patch.object(review, 'active', side_effect=lambda u: u == 'screen-live.service'):
            holds = []
            spans, lanes = review.queue_events(NOW, notes, holds)
        self.assertEqual(len(spans), 8)
        self.assertEqual(holds, [])
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

    def write_json(self, path, row):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(row))

    def report(self, now, hours=1, device=([], {}, [], [])):
        output = io.StringIO()
        with patch.object(review, 'parse', return_value=([], now)), \
             patch.object(review, 'device_evidence', return_value=device), \
             patch.object(review.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '')), \
             patch.object(review, 'SCRATCH', str(self.root)), \
             patch.object(review, 'REPO', str(self.root)), \
             patch('sys.argv', ['gpu_time_review.py', '--hours', str(hours)]), \
             contextlib.redirect_stdout(output):
            review.main()
        return output.getvalue()

    def test_review29_onecard_chain_and_bracket_card_minutes(self):
        begin = review.timestamp('2026-10-18T17:40:00Z')
        now = review.timestamp('2026-10-18T18:40:00Z')
        # Review 29's two reported ranges. These clock fixtures represent
        # occupancy, not a hardware compute-utilization measurement.
        ranges = [('packet58w-onecard-record', 'card0-58w-a/WS128', '18:12', '18:37'),
                  ('packet58v-async-cache', 'card0-async-a/overlap/WSCREEN', '17:43', '18:04')]
        for packet, output, first, last in ranges:
            self.write_json(review.RESULTS / packet / 'evidence' / output / 'window.json',
                            dict(device_executed=True, card=0,
                                 started_utc_ns=int(review.timestamp(f'2026-10-18T{first}:00Z').timestamp()*1e9),
                                 finished_utc_ns=int(review.timestamp(f'2026-10-18T{last}:00Z').timestamp()*1e9)))
        cards = {}
        spans, lanes, holds = review.chain_windows(begin, now, set(), cards)
        self.assertEqual(len(spans), 2)
        self.assertEqual(set(cards.values()), {(0,)})
        self.assertEqual(review.accounting(holds, begin, now)[0], 46*60)
        busy, available, unknown = review.card_minutes(spans, lanes, cards, begin, now)
        self.assertEqual((busy, available, unknown), (46, 240, 0))
        text = self.report(now)
        self.assertIn('46.0 / 240.0 = 19.2%', text)
        for lane in 'AB':
            self.assertIn(f'Lane {lane} (cards {"0+1" if lane == "A" else "2+3"}) busy/held: 0.77 h = 77%', text)
        self.assertNotIn('17:40-18:40 UTC  60 min', text)

    def test_onecard_queue_and_window_overlap_counts_only_one_card(self):
        output = review.RESULTS / 'packet58x-capacity/evidence/card0-capacity-a/smoke'
        self.write_json(output / 'WSCREEN/window.json', dict(
            device_executed=True, card=0, start_utc=minute(10).isoformat(), end_utc=minute(20).isoformat()))
        self.write_json(self.root / 'lane-queue/done-A.txt', dict(
            job=dict(name='packet58x-smoke-A', lane='A', argv=['runner.py', '--output', str(output)]),
            start_utc=minute(5).isoformat(), end_utc=minute(25).isoformat()))
        text = self.report(NOW)
        self.assertIn('20.0 / 240.0 = 8.3%', text)
        self.assertIn('Lane B (cards 2+3) busy/held: 0.33 h = 33%', text)

    def test_today_saved_chain_clocks_preserve_interwindow_gaps(self):
        # Exact fields from packet58w/evidence/card0-58w-a/*/window.json.
        # The chain spans 18:12–18:37; the 90-second interwindow waits are not
        # fabricated device work. All seven windows must be discovered.
        clocks = {
            'K1a': (1792347131459984298, 1792347141923397448),
            'K1b': (1792347232280628518, 1792347242731081389),
            'KD': (1792347333069857030, 1792347469722552774),
            'W2m': (1792347560062297751, 1792347703116237825),
            'WS': (1792347793497836977, 1792347991951304299),
            'WS128x': (1792348082339605957, 1792348308550206408),
            'WS128': (1792348398922281644, 1792348607398843245),
        }
        root = review.RESULTS / 'packet58w-onecard-record/evidence/card0-58w-a'
        for name, (first, last) in clocks.items():
            self.write_json(root / name / 'window.json', dict(
                device_executed=True, card=0, started_utc_ns=first, finished_utc_ns=last))
        begin = review.timestamp('2026-10-18T18:12:00Z')
        now = review.timestamp('2026-10-18T18:37:00Z')
        cards = {}
        intervals, lanes, holds = review.chain_windows(begin, now, set(), cards)
        self.assertEqual(len(intervals), 7)
        expected_minutes = sum(last-first for first, last in clocks.values()) / 60e9
        busy, available, _ = review.card_minutes(intervals, lanes, cards, begin, now)
        self.assertAlmostEqual(busy, expected_minutes, places=6)
        self.assertEqual(available, 100)
        self.assertEqual(review.accounting(holds, begin, now)[1], [])

    def test_onecard_windows_clip_deduplicate_and_exclude_cpu_refusal(self):
        root = review.RESULTS / 'packet58w-test/evidence/card0-a'
        row = dict(card=0, device_executed=True, start_utc=minute(-5).isoformat(), end_utc=minute(65).isoformat())
        self.write_json(root / 'WS/window.json', row)
        self.write_json(root / 'WS128/window.json', row)
        self.write_json(root / 'CPU/window.json', {**row, 'cpu_rehearsal': True})
        self.write_json(root / 'refusal/window.json', {**row, 'device_executed': False})
        cards = {}
        intervals, lanes, holds = review.chain_windows(BEGIN, NOW, set(), cards)
        self.assertEqual(len(intervals), 2)
        self.assertEqual(review.card_minutes(intervals, lanes, cards, BEGIN, NOW), (60, 240, 0))
        self.assertEqual(review.accounting(holds, BEGIN, NOW)[0], 3600)

    def test_card_minutes_two_lanes_and_unknown_identity(self):
        intervals = [(minute(0), minute(30), 'A', ''),
                     (minute(15), minute(45), 'B', ''),
                     (minute(45), minute(60), 'unknown', '')]
        self.assertEqual(review.card_minutes(intervals, {'A': 'A', 'B': 'B'}, {}, BEGIN, NOW),
                         (120, 240, 15))

    def test_review26_onecard_holds_from_archived_receipts_and_events(self):
        # Actual review-26 UTC ranges. Job scope lives in its saved queue plan,
        # not the events or the archived done record.
        ranges = [('packet58r-v5-A', '15:06:38.281955', '15:20:09.779371'),
                  ('packet58t-resident-A', '15:21:41.185360', '15:35:25.625482')]
        events, receipts = [], []
        for name, first, last in ranges:
            start, end = [f'2026-10-18T{t}Z' for t in (first, last)]
            output = self.root / name
            self.write_json(output / 'queue.json', {'plan': {'scope': 'whole-host'}})
            receipts.append({'job': {'name': name, 'lane': 'A',
                                      'argv': ['runner.py', '--output', str(output)]},
                             'start_utc': start, 'end_utc': end, 'outcome': 'DONE'})
            events.extend([dict(event=kind, lane='A', name=name, utc=stamp)
                           for kind, stamp in [('START', start), ('DONE', end)]])
        queue = self.root / 'lane-queue'
        (queue / 'done-A-reviewed-20261018.txt').write_text(
            ''.join(json.dumps(r) + '\n' for r in receipts))
        (queue / 'events-A.jsonl').write_text(
            ''.join(json.dumps(r) + '\n' for r in events))
        now = review.timestamp('2026-10-18T16:00:00Z')
        holds = []
        spans, lanes = review.queue_events(now, set(), holds)
        expected = sum((review.timestamp(r['end_utc']) - review.timestamp(r['start_utc'])).total_seconds()
                       for r in receipts)
        self.assertAlmostEqual(review.accounting(holds, now-dt.timedelta(hours=1), now)[0], expected)
        self.assertAlmostEqual(review.accounting([(s, e) for s, e, _, _ in spans],
                                                now-dt.timedelta(hours=1), now)[0], expected)
        self.assertEqual(set(lanes.values()), {'A'})
        text = self.report(now)
        for lane in 'AB':
            self.assertIn(f'Lane {lane} (cards {"0+1" if lane == "A" else "2+3"}) busy/held: 0.45 h = 45%', text)
        self.assertNotIn('15:06-15:35 UTC', text)
        # Rotated or lost events must not remove archived evidence.
        (queue / 'events-A.jsonl').write_text('')
        self.assertIn('Lane B (cards 2+3) busy/held: 0.45 h = 45%', self.report(now))

    def test_queue_scope_from_receipt_or_proposal_without_counting_unstarted_jobs(self):
        self.events('A', [(10, 'START', 'planned'), (20, 'REFUSED-new-reason', 'planned')])
        self.write_json(self.root / 'lane-queue/proposed-test.txt',
                        {'name': 'planned', 'scope': 'whole-host'})
        self.write_json(self.root / 'lane-queue/proposed-unused.txt',
                        {'name': 'unused', 'scope': 'whole-host'})
        self.write_json(self.root / 'lane-queue/archived.exit.json',
                        {'job': {'name': 'receipt-only', 'lane': 'B'},
                         'scope': 'whole-host', 'start_utc': minute(30).isoformat(),
                         'end_utc': minute(40).isoformat()})
        holds = []
        spans, lanes = review.queue_events(NOW, set(), holds)
        self.assertEqual(len(spans), 2)
        self.assertEqual(review.accounting(holds, BEGIN, NOW)[0], 20 * 60)
        self.assertNotIn('screen-unused.service', lanes)

    def test_missing_terminal_receipt_does_not_extend_reused_unit(self):
        self.events('A', [(5, 'START', 'reused'), (30, 'START', 'reused')])
        self.write_json(self.root / 'lane-queue/done-A-reviewed.txt',
                        {'job': {'name': 'reused', 'lane': 'A'},
                         'start_utc': minute(5).isoformat(), 'end_utc': minute(10).isoformat()})
        with patch.object(review, 'active', return_value=False):
            spans, _ = review.queue_events(NOW, set())
        self.assertEqual([(s, e) for s, e, _, _ in spans], [(minute(5), minute(10))])

    def test_review26_chain_k_windows_and_whole_host_receipts(self):
        # K receipts have no child/request clocks. Their sibling admission
        # receipts bracket the completed windows, including serial fixture gaps.
        start = review.timestamp('2026-10-18T13:15:00Z')
        now = review.timestamp('2026-10-18T14:00:00Z')
        boot = self.root / 'proc/sys/kernel/random/boot_id'
        boot.parent.mkdir(parents=True)
        boot.write_text('test-boot')
        windows = ('K0', 'K1a', 'K1b', 'K2', 'W0p', 'KD')
        bounds = (0, 1, 4, 7, 12, 15, 22)
        root = review.RESULTS / 'packet124c-record-bundle/build/device-cards01-a'
        for i, name in enumerate(windows):
            self.write_json(root / name / 'window.json',
                            {'device_executed': True, 'lane_admission': {'scope': 'lane-A'}})
            self.write_json(root / f'{name}-lane-admission.json',
                            {'coordination': {'lane': 'A', 'scope': 'lane-A',
                                              'started_monotonic': 900 + bounds[i] * 60},
                             'shared_drain': {'boot_id': 'test-boot',
                                              'started_monotonic': 1000 + bounds[i] * 60,
                                              'completed_monotonic': 1000 + bounds[i+1] * 60}})
        # Wall clocks remain usable across boots; whole-host windows hold B.
        self.write_json(root / 'WSs/window.json',
                        {'start_utc': '2026-10-18T13:40:00Z', 'end_utc': '2026-10-18T13:50:00Z',
                         'boot_id': 'old-boot', 'lane_admission': {'scope': 'whole-host'}})
        class ChainClock(dt.datetime):
            @classmethod
            def now(cls, tz=None):
                return now
        with patch.object(review, 'PROC', self.root / 'proc'), \
             patch.object(review.dt, 'datetime', ChainClock), \
             patch.object(review.time, 'monotonic', return_value=3700):
            spans, lanes, holds = review.chain_windows(start, now, set())
            self.assertEqual(len(spans), 7)
            self.assertEqual(review.accounting([(s, e) for s, e, _, _ in spans], start, now)[0], 32 * 60)
            self.assertEqual(review.accounting(holds, start, now)[0], 10 * 60)
            self.assertEqual(set(lanes.values()), {'A'})
            text = self.report(now)
            self.assertIn('Lane A (cards 0+1) busy/held: 0.53 h = 53%', text)
            self.assertIn('Lane B (cards 2+3) busy/held: 0.17 h = 17%', text)
            self.assertNotIn('13:15-13:37 UTC', text)
            boot.write_text('different-boot')
            spans, _, _ = review.chain_windows(start, now, set())
            self.assertEqual(len(spans), 1)  # only UTC receipt survives reboot

    def test_chain_utc_nanoseconds_and_invalid_or_rehearsal_receipts(self):
        root = review.RESULTS / 'packet2/build/device-cards01-a'
        valid = {'started_utc_ns': int(minute(10).timestamp() * 1e9),
                 'finished_utc_ns': int(minute(20).timestamp() * 1e9),
                 'device_executed': True, 'scope': 'whole-host'}
        self.write_json(root / 'K0/window.json', valid)
        for name, change in [('cpu', {'cpu_rehearsal': True}),
                             ('unlaunched', {'device_executed': False}),
                             ('nan', {'finished_utc_ns': float('nan')}),
                             ('backwards', {'finished_utc_ns': valid['started_utc_ns'] - 1e9}),
                             ('missing', {'finished_utc_ns': None})]:
            self.write_json(root / name / 'window.json', dict(valid, **change))
        with patch.object(review, 'PROC', self.root / 'no-proc'):
            spans, _, holds = review.chain_windows(minute(15), NOW, set())
        self.assertEqual(len(spans), 1)
        self.assertEqual(holds, [(minute(15), minute(20))])


    def test_overlapping_queue_device_and_windows_union_per_lane_and_preserve_wait(self):
        self.events('A', [(10, 'START', 'a'), (30, 'DONE', 'a')])
        self.events('B', [(25, 'START', 'b'), (40, 'DONE', 'b')])
        root = review.RESULTS / 'packet1/build/device-cards01-a'
        self.write_json(root / 'WSs/window.json',
                        {'start_utc': minute(20).isoformat(), 'end_utc': minute(35).isoformat(),
                         'scope': 'whole-host'})
        device = ([(minute(15), minute(25), 'screen-a.service', 'device')], {}, [],
                  [(minute(0), minute(12), 'wait-A', 'A')])
        text = self.report(NOW, device=device)
        self.assertIn('union, excl. pure waiters): 0.50 h = 50%', text)
        self.assertIn('Lane A (cards 0+1) busy/held: 0.42 h = 42%', text)
        self.assertIn('Lane B (cards 2+3) busy/held: 0.33 h = 33%', text)
        self.assertIn('Lane A idle_admission_wait: 10.0 min', text)
        self.assertIn('Lane B whole-host holds included: 15.0 min', text)


    def test_wait_category_subtracts_busy_and_unions_duplicates(self):
        self.assertEqual(review.subtract([(minute(10), minute(40)),
                                          (minute(15), minute(30))],
                                         [(minute(0), minute(20)),
                                          (minute(25), minute(30))]),
                         [(minute(20), minute(25)), (minute(30), minute(40))])


if __name__ == '__main__':
    unittest.main()
