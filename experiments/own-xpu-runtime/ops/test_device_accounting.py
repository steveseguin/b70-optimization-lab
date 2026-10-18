"""Fixture replay of 24b: a 26-minute hold wait is idle, not device time."""
import contextlib
import datetime as dt
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import gpu_time_review as review

FIXTURE = Path(__file__).parent / 'fixtures/admission-wait'
EPOCH = dt.datetime(2026, 10, 18, 13, tzinfo=dt.timezone.utc)
NOW = EPOCH + dt.timedelta(minutes=70)
BEGIN = NOW - dt.timedelta(hours=1)


class Clock(dt.datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW


class DeviceAccountingTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.packet = self.root / 'packet/build/device-a'
        shutil.copytree(FIXTURE, self.packet)
        self.window = self.packet / 'W2m/window.json'
        self.proc = self.root / 'proc'
        boot = self.proc / 'sys/kernel/random/boot_id'
        boot.parent.mkdir(parents=True)
        boot.write_text('fixture-boot')
        self.coord = self.root / 'coordination/chain-lanes-v1'
        self.coord.mkdir(parents=True)
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        for mock in (patch.object(review, 'PROC', self.proc),
                     patch.object(review, 'OPS', self.root / 'ops'),
                     patch.object(review, 'RESULTS', self.root),
                     patch.object(review, 'receipt_paths', return_value=[self.window]),
                     patch.object(review.time, 'monotonic', return_value=4200),
                     patch.object(review.os, 'sysconf', return_value=100),
                     patch.object(review.dt, 'datetime', Clock)):
            stack.enter_context(mock)

    def update(self, path, **changes):
        row = json.loads(path.read_text())
        row.update(changes)
        path.write_text(json.dumps(row))

    def evidence(self):
        return review.device_evidence(BEGIN, NOW, set())

    def test_1337_1403_wait_counts_idle_not_busy_or_held(self):
        intervals, lanes, holds, waits = self.evidence()
        self.assertEqual(review.accounting([(s, e) for s, e, _, _ in intervals], BEGIN, NOW)[0], 120)
        self.assertEqual(review.accounting(holds, BEGIN, NOW)[0], 120)
        self.assertEqual(waits, [(EPOCH + dt.timedelta(minutes=37),
                                 EPOCH + dt.timedelta(minutes=63),
                                 'packet124c-chain.service', 'A')])
        self.assertEqual(lanes['packet124c-chain.service'], 'A')
        # Neither completion at 14:07 nor service exit at 14:09 counts.
        self.assertEqual(max(e for _, e, _, _ in intervals), EPOCH + dt.timedelta(minutes=65))

    def test_cli_fixture_journal_does_not_turn_98_percent_wrapper_into_busy(self):
        def run(cmd, **kwargs):
            if cmd[0] == 'journalctl':
                return subprocess.CompletedProcess(cmd, 0, (FIXTURE / 'journal.log').read_text())
            if cmd[0] == 'systemctl':
                self.fail('durable lane attribution should suffice')
            return subprocess.CompletedProcess(cmd, 0, '')
        output = io.StringIO()
        with patch.object(review.subprocess, 'run', side_effect=run), \
             patch.object(review, 'queue_events', return_value=([], {'screen-lane-b.service': 'B'})), \
             patch.object(review, 'SCRATCH', str(self.root)), \
             patch.object(review, 'REPO', str(self.root)), \
             patch('sys.argv', ['gpu_time_review.py', '--hours', '1']), \
             contextlib.redirect_stdout(output):
            review.main()
        text = output.getvalue()
        self.assertIn('Lane A (cards 0+1) busy/held: 0.03 h = 3%', text)
        self.assertIn('Lane B (cards 2+3) busy/held: 0.03 h = 3%', text)
        self.assertIn('Lane A idle_admission_wait: 26.0 min', text)
        self.assertIn('13:37-14:03 UTC  26 min  [idle_admission_wait]', text)
        self.assertNotIn('98%', text)

    def test_old_boot_cpu_rehearsal_and_no_device_do_not_count(self):
        for change in (dict(boot_id='other-boot'), dict(cpu_rehearsal=True),
                       dict(device_executed=False)):
            with self.subTest(change=change):
                shutil.copyfile(FIXTURE / 'W2m/window.json', self.window)
                self.update(self.window, **change)
                intervals, _, holds, _ = self.evidence()
                self.assertEqual(intervals, [])
                self.assertEqual(holds, [])

    def test_missing_end_and_nan_never_use_drain_or_wrapper_finish(self):
        receipt = self.packet / 'W2m/run/receipt.json'
        for row in ({}, dict(request_start_monotonic=3780),
                    dict(work_start=3780, work_end=float('nan')),
                    dict(work_start=3900, work_end=3800),
                    dict(work_start=3780, work_end=1e300),
                    dict(device_executed=False, work_start=3780, work_end=3900)):
            receipt.write_text(json.dumps(row))
            self.assertEqual(self.evidence()[0], [])

    def test_report_collection_delay_does_not_shift_receipts(self):
        class LaterClock(Clock):
            @classmethod
            def now(cls, tz=None):
                return NOW + dt.timedelta(seconds=5)
        with patch.object(review.dt, 'datetime', LaterClock), \
             patch.object(review.time, 'monotonic', return_value=4205):
            self.test_1337_1403_wait_counts_idle_not_busy_or_held()

    def test_missing_boot_is_disclosed_without_inventing_busy(self):
        (self.proc / 'sys/kernel/random/boot_id').unlink()
        notes = set()
        self.assertEqual(review.device_evidence(BEGIN, NOW, notes), ([], {}, [], []))
        self.assertTrue(any('cannot identify this boot' in note for note in notes))

    def test_screen_rank_identity_and_nested_request_receipts(self):
        (self.packet / 'W2m-lane-admission.json').unlink()
        self.update(self.window, card=2, lane='B', systemd_cgroup='0::/screen-b.service')
        run = self.packet / 'W2m/run'
        (run / 'receipt.json').unlink()
        (run / 'prompt').mkdir()
        (run / 'prompt/receipt.json').write_text(json.dumps(dict(work_start=3800, work_end=3900)))
        (run / 'device-isolation.json').write_text(json.dumps(dict(passed=True, errors=[],
            sampled_monotonic=3850, ranks=[dict(process_start_ticks=378000, fds=[dict(driver='xe')])])))
        spans, lanes, holds, waits = self.evidence()
        self.assertEqual(review.accounting([(s, e) for s, e, _, _ in spans], BEGIN, NOW)[0], 120)
        self.assertEqual(lanes, {'screen-b.service': 'B'})
        self.assertEqual((holds, waits), ([], []))

    def process(self, pid, ppid, comm, ticks, device=False, state='S'):
        root = self.proc / str(pid)
        root.mkdir()
        (root / 'comm').write_text(comm)
        (root / 'stat').write_text(f'{pid} ({comm}) {state} {ppid} ' + '0 ' * 17 + f'{ticks} 0\n')
        (root / 'cgroup').write_text('0::/user.slice/packet124c-chain.service')
        binary = self.root / ('build/device' if device else 'build/gnu-host') / comm
        binary.parent.mkdir(parents=True, exist_ok=True)
        binary.touch()
        (root / 'exe').symlink_to(binary)

    def test_active_chain_is_idle_until_device_child_exists(self):
        self.window.unlink()
        owner = dict(boot_id='fixture-boot', lane='A', scope='whole-host',
                     pid=10, start_ticks=222000, started_monotonic=2220)
        for name, row in (('active-lane-A.json', owner), ('hold-lane-B', owner),
                          ('active-lane-B.json', dict(lane='B'))):
            (self.coord / name).write_text(json.dumps(row))
        self.process(10, 1, 'python3', 222000)
        intervals, _, holds, waits = self.evidence()
        self.assertEqual((intervals, holds), ([], []))
        self.assertEqual((waits[0][1] - waits[0][0]).total_seconds(), 33 * 60)
        self.process(11, 10, 'own-rt-iq3', 378000, device=True)
        intervals, lanes, holds, waits = self.evidence()
        self.assertEqual(review.accounting([(s, e) for s, e, _, _ in intervals], BEGIN, NOW)[0], 7 * 60)
        self.assertEqual(lanes, {'packet124c-chain.service': 'A'})
        self.assertEqual(len(holds), 1)
        self.assertEqual(waits, [])

    def test_cpu_mock_and_zombie_never_count_as_live_device(self):
        self.window.unlink()
        self.process(11, 1, 'own-rt-iq3', 378000)
        self.process(12, 1, 'own-rt-iq3', 378000, device=True, state='Z')
        self.assertEqual(self.evidence()[0], [])

    def test_time_window_clips_proven_child_span(self):
        begin = EPOCH + dt.timedelta(minutes=64, seconds=30)
        spans, _, holds, _ = review.device_evidence(begin, NOW, set())
        self.assertEqual(review.accounting([(s, e) for s, e, _, _ in spans], begin, NOW)[0], 30)
        self.assertEqual(review.accounting(holds, begin, NOW)[0], 30)


if __name__ == '__main__':
    unittest.main()
