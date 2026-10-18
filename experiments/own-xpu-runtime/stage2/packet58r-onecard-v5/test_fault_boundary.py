"""CPU-only regression for the 2026-10-18 pre-device journal refusal."""
import gzip
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import fault_review as F
import queue_runner as Q


class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.newest = 1792306806230449  # Exact newest timestamp in the refused review.
        self.boot = '2cba7160-054a-4ffe-b4c4-e252eb956f5f'
        self.rows = [dict(_BOOT_ID=self.boot.replace('-', ''),
                          __REALTIME_TIMESTAMP=str(stamp), MESSAGE=message)
                     for stamp, message in ((self.newest-10_000_000, 'Fault response'),
                                            (self.newest-9_000_000, 'Engine reset'),
                                            (self.newest, 'benign newest kernel line'))]
        self.text = '\n'.join(json.dumps(row) for row in self.rows)+'\n'
        self.review = F.inspect(self.text, self.boot, 'captured-cursor')

    def journal(self, since):
        def runner(argv, **kwargs):
            # Real supervisor constructs the inclusive --since = RT + 1 us.
            epoch = argv[argv.index('--since')+1][1:]
            seconds, micros = epoch.split('.')
            start = int(seconds)*1_000_000 + int(micros)
            selected = [r for r in self.rows if int(r['__REALTIME_TIMESTAMP']) >= start]
            text = '\n'.join(json.dumps(r) for r in selected)
            if selected:
                text += '\n-- cursor: captured-cursor\n'
            return SimpleNamespace(returncode=0, stderr='', stdout=text)
        return F.S.journal(runner=runner, since_us=since)

    def test_exact_boundary_refuses_old_argument_and_accepts_overlap(self):
        with self.assertRaisesRegex(ValueError, 'kernel journal boundary missing'):
            self.journal(self.newest)
        boundary = F.window_boundary(self.review)
        self.assertEqual(boundary, '2026-10-18T07:00:04.230449Z')
        _, rt = F.S.fault_review(boundary, self.newest)
        self.assertEqual(self.newest-rt, 2_000_000)
        text, cursor = self.journal(rt)
        self.assertEqual(cursor, 'captured-cursor')
        self.assertIn('benign newest kernel line', text)
        self.assertFalse(F.fault_lines(text))

    def test_no_gap_and_faults_at_every_boundary_still_seen(self):
        _, rt = F.S.fault_review(F.window_boundary(self.review), self.newest)
        for stamp in (rt, rt+1, self.newest, self.newest+1):
            with self.subTest(stamp=stamp):
                fault = dict(self.rows[-1], __REALTIME_TIMESTAMP=str(stamp), MESSAGE='Fault response')
                # Every timestamp is reviewed, scanned by the window, or both.
                self.assertTrue(stamp <= self.newest or stamp > rt)
                self.rows.append(fault)
                try:
                    text, _ = self.journal(rt)
                    self.assertEqual(bool(F.fault_lines(text)), stamp > rt)
                finally:
                    self.rows.pop()

    def test_saved_capture_validated_and_not_later_live_or_wall_time(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            capture = root/'kernel.gz'
            capture.write_bytes(gzip.compress(self.text.encode(), mtime=0))
            recorded = dict(self.review, kernel_capture=str(capture))
            receipt = root/'review.json'
            receipt.write_text(json.dumps(recorded))
            later = dict(self.review, through_us=self.newest+60_000_000)
            with (patch.object(F, 'capture', return_value=(later, 'later live capture')),
                  patch.object(F.S, 'journal', return_value=('', 'fresh-cursor'))):
                validated, _, _, _ = F.validate(receipt)
                self.assertEqual(F.window_boundary(validated), '2026-10-18T07:00:04.230449Z')
                recorded['through_us'] += 1
                receipt.write_text(json.dumps(recorded))
                with self.assertRaisesRegex(ValueError, 'differs from captured'):
                    F.validate(receipt)

    def test_changed_or_missing_timestamp_refuses(self):
        for value in (True, -1, 1_999_999, self.newest+1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                F.window_boundary(dict(self.review, through_us=value))

    def test_each_arm_passes_derived_boundary_to_all_windows(self):
        class CommandsCaptured(Exception):
            pass
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)/'card0-loo-a'
            for arm, view in Q.STAGES:
                with (patch.object(Q, 'ROOT', root), patch.object(Q, 'plan', return_value={}),
                      patch.object(Q.W, 'user_unit_gate'), patch.object(Q.W, 'closed_environment'),
                      patch.object(Q.os, 'getpriority', return_value=0),
                      patch.object(Q.os, 'sched_getaffinity', return_value={0,1,2,3,16,17,18,19}),
                      patch.object(F, 'validate', return_value=(self.review, '', '', 'cursor')),
                      patch.object(Q, 'commands', side_effect=CommandsCaptured) as commands,
                      self.assertRaises(CommandsCaptured)):
                    Q.main(['--arm', arm, '--output', str(root/arm), '--fault-review', '/unused',
                            '--authorized-device-window'])
                args = commands.call_args.args
                self.assertEqual(args[2], '2026-10-18T07:00:04.230449Z')
                for cmd in Q.commands(*args).values():
                    self.assertEqual(cmd[cmd.index('--faults-reviewed-through')+1], args[2])
                self.assertFalse(root.exists())


if __name__ == '__main__':
    unittest.main()
