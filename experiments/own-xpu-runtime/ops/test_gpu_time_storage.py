"""CPU-only disk review tests; no plans, devices or services."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import gpu_time_review as review


class DiskReviewTests(unittest.TestCase):
    def test_largest_pending_excludes_inflight_and_uses_shared_default(self):
        with tempfile.TemporaryDirectory() as temp:
            ops = Path(temp)
            directory = ops / 'lane-queue'
            directory.mkdir()
            rows = [dict(name='live', argv=['/usr/bin/true'], planned_write_bytes=10_000_000_000),
                    dict(name='bracket', argv=['/usr/bin/true', '--kind', 'bracket'])]
            (directory / 'queue-A.txt').write_text(''.join(json.dumps(row) + '\n' for row in rows))
            (directory / 'inflight-A.json').write_text(json.dumps({'job': rows[0]}))
            (directory / 'queue-B.txt').write_text(json.dumps(dict(name='small', planned_write_bytes=123)) + '\n')
            with patch.object(review, 'OPS', ops), \
                 patch.object(review.shutil, 'disk_usage', return_value=SimpleNamespace(free=30_000_000_000)), \
                 patch.object(review.subprocess, 'run', side_effect=AssertionError('no commands')):
                line = review.disk_line(set())
            self.assertIn('root free now 30000000000 bytes', line)
            self.assertIn('5500000000 bytes', line)
            self.assertIn('lane A, bracket', line)
            self.assertIn('default', line)

    def test_bad_reservation_is_reported_unknown(self):
        with tempfile.TemporaryDirectory() as temp:
            ops = Path(temp)
            directory = ops / 'lane-queue'
            directory.mkdir()
            (directory / 'queue-B.txt').write_text('{"name":"bad","planned_write_bytes":-1}\n')
            with patch.object(review, 'OPS', ops):
                line = review.disk_line(set())
            self.assertIn('none known', line)
            self.assertIn('1 queued reservation(s) unreadable', line)
