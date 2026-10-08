"""Attempt-3 first-cause preservation, without device imports or allocation."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_overlay_cpu import guard


class FirstCauseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.env = patch.dict(os.environ, {'B70_SCREEN1B': '1', 'B70_SCREEN1B_STATE_DIR': self.tmp.name})
        self.env.start()
        self.addCleanup(self.env.stop)
        for key in ('_cancelled', '_loading'):
            p = patch.object(guard, key, False)
            p.start()
            self.addCleanup(p.stop)

    def test_attempt3_counters_refuse_without_large_allocation(self):
        with patch.object(guard, 'memory', return_value={
                'MemTotal': 124179132416, 'MemAvailable': 44173471744}):
            with self.assertRaisesRegex(guard.LoadCancelled, 'pressure_bytes=80005660672'):
                guard.check_admission(2048)
        rows = [json.loads(x) for x in (self.root/f'loader-{os.getpid()}.jsonl').read_text().splitlines()]
        self.assertEqual(rows[0]['projected_pressure_bytes'], 80005662720)
        self.assertEqual(rows[0]['next_bytes'], 2048)

    def test_sibling_keeps_first_cause_even_after_later_stop(self):
        guard.request_stop('original memory refusal')
        guard.request_stop('later worker failure')
        with self.assertRaisesRegex(guard.LoadCancelled, 'first stop: original memory refusal'):
            guard.check_cancel()
        self.assertEqual((self.root/'STOP').read_text(), 'original memory refusal\n')

    def test_missing_stop_reason_still_cancels(self):
        guard._cancelled = True
        with self.assertRaisesRegex(guard.LoadCancelled, 'first stop reason unavailable'):
            guard.check_cancel()

    def test_empty_stop_during_writer_race_still_cancels(self):
        (self.root/'STOP').touch()
        with self.assertRaisesRegex(guard.LoadCancelled, 'first stop reason not yet written'):
            guard.check_cancel()
