"""Owner-decision admission regressions; fixture journals only, no operations."""
import contextlib
import copy
import datetime as dt
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import screen


NOW = dt.datetime(2026, 10, 11, 1, tzinfo=dt.timezone.utc)
BOOT = '4aafe57b-a54f-4bfd-b4ed-9f1cbb8830c7'
ACCEPTANCE = screen.REPO / screen.OWNER_ACCEPTANCE_RELATIVE
HEALTH = screen.REPO / 'experiments/ltx25-b70/data/resume-20261008/postflight-pre118b-20261010T0134Z.json'
ACCEPTED = dt.datetime(2026, 10, 11, 0, 36, 14, tzinfo=dt.timezone.utc)


def line(timestamp, message='xe Fault response'):
    return f'{timestamp}+00:00 synthetic kernel: {message}\n'


OLD = (line('2026-10-08T21:11:00') + line('2026-10-08T21:11:02', 'CAT error') +
       line('2026-10-09T02:27:30') + line('2026-10-09T02:27:32', 'device coredump created'))


class OwnerAcceptanceTests(unittest.TestCase):
    def setUp(self):
        # Synthetic health timing; the historical receipt on disk stays untouched.
        self.health = dict(json.loads(HEALTH.read_bytes()),
                           start_utc='2026-10-11 00:40:00 UTC',
                           end_utc='2026-10-11 00:40:05 UTC')
        self.audit = screen.admission_audit()

    def admit(self, journal=OLD, **kwargs):
        arguments = dict(receipt=self.health, boot_id=BOOT, now=NOW,
                         owner_acceptance=ACCEPTANCE, audit=self.audit)
        arguments.update(kwargs)
        return screen.admit_journal(journal, **arguments)

    @contextlib.contextmanager
    def fixture(self, changes=None, *, missing=False, tamper=False):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / screen.OWNER_ACCEPTANCE_RELATIVE
            document = json.loads(ACCEPTANCE.read_bytes())
            for key, value in (changes or {}).items():
                if value is None:
                    document.pop(key, None)
                else:
                    document[key] = value
            raw = json.dumps(document).encode()
            if not missing:
                path.parent.mkdir(parents=True)
                path.write_bytes(raw + (b' ' if tamper else b''))
            with patch.object(screen, 'REPO', root), patch.object(
                    screen, 'OWNER_ACCEPTANCE_SHA256', hashlib.sha256(raw).hexdigest()):
                yield path

    def test_committed_acceptance_excludes_two_old_incidents(self):
        lines, cutoff = self.admit()
        self.assertEqual(lines, OLD.splitlines())
        self.assertEqual(cutoff, ACCEPTED.timestamp())
        self.assertEqual(self.audit['owner_acceptance_sha256'], screen.OWNER_ACCEPTANCE_SHA256)
        self.assertTrue(self.audit['owner_acceptance_verified'])
        self.assertTrue(self.audit['passed'])
        self.assertEqual(self.audit['counted_gpu_incidents'], 0)
        self.assertEqual(self.audit['counted_fault_lines'], [])
        self.assertEqual(self.audit['excluded_fault_lines'], OLD.splitlines())

    def test_no_option_keeps_two_incident_refusal(self):
        with self.assertRaisesRegex(RuntimeError, '2 GPU fault incidents.*owner must decide'):
            self.admit(owner_acceptance=None)
        self.assertIsNone(self.audit['owner_acceptance_sha256'])
        self.assertEqual(self.audit['counted_gpu_incidents'], 2)
        self.assertEqual(self.audit['counted_fault_lines'], OLD.splitlines())
        self.assertEqual(self.audit['excluded_fault_lines'], [])

    def test_no_option_clean_boot_still_needs_no_receipt(self):
        self.assertEqual(self.admit('', receipt=None, owner_acceptance=None), ([], NOW.timestamp()))

    def test_wrong_boot_refused(self):
        with self.assertRaisesRegex(RuntimeError, 'another boot'):
            self.admit(boot_id='wrong-boot')
        self.assertFalse(self.audit['owner_acceptance_verified'])
        self.assertEqual(self.audit['owner_acceptance_sha256'], screen.OWNER_ACCEPTANCE_SHA256)

    def test_missing_committed_file_refused(self):
        with self.fixture(missing=True) as path, self.assertRaisesRegex(RuntimeError, 'Cannot read owner acceptance'):
            self.admit(owner_acceptance=path)

    def test_tampered_committed_file_refused(self):
        with self.fixture(tamper=True) as path, self.assertRaisesRegex(RuntimeError, 'SHA256 mismatch'):
            self.admit(owner_acceptance=path)
        self.assertIsNotNone(self.audit['owner_acceptance_sha256'])
        self.assertFalse(self.audit['owner_acceptance_verified'])

    def test_identical_receipt_at_wrong_path_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'lookalike.json'
            path.write_bytes(ACCEPTANCE.read_bytes())
            with self.assertRaisesRegex(RuntimeError, 'must be the committed receipt'):
                self.admit(owner_acceptance=path)

    def test_missing_or_empty_decision_refused(self):
        for value in (None, '', '   ', 1):
            with self.subTest(value=value), self.fixture({'decision': value}) as path:
                with self.assertRaisesRegex(RuntimeError, 'decision text'):
                    self.admit(owner_acceptance=path)

    def test_missing_or_invalid_time_refused(self):
        for value in (None, '', '2026-10-11', 1):
            with self.subTest(value=value), self.fixture({'time_utc': value}) as path:
                with self.assertRaisesRegex(RuntimeError, 'readable UTC time'):
                    self.admit(owner_acceptance=path)

    def test_wrong_receipt_schema_refused(self):
        with self.fixture({'schema': 'wrong'}) as path, self.assertRaisesRegex(RuntimeError, 'schema invalid'):
            self.admit(owner_acceptance=path)

    def test_future_acceptance_refused(self):
        with self.assertRaisesRegex(RuntimeError, 'acceptance time is in the future'):
            self.admit(now=ACCEPTED-dt.timedelta(seconds=1))

    def test_acceptance_still_requires_health(self):
        with self.assertRaisesRegex(RuntimeError, 'still requires --health-receipt'):
            self.admit(receipt=None)

    def test_stale_health_refused(self):
        with self.assertRaisesRegex(RuntimeError, '6 hours'):
            self.admit(now=screen.parse_utc(self.health['end_utc'])+dt.timedelta(hours=6))

    def test_health_before_acceptance_refused(self):
        health = dict(self.health, start_utc='2026-10-11 00:36:13 UTC')
        with self.assertRaisesRegex(RuntimeError, 'start at/after owner acceptance'):
            self.admit(receipt=health)

    def test_new_fault_before_passing_health_still_refused(self):
        later = line('2026-10-11T00:38:00')
        with self.assertRaisesRegex(RuntimeError, 'fault at/after owner acceptance'):
            self.admit(OLD+later)
        self.assertFalse(self.audit['passed'])
        self.assertEqual(self.audit['counted_fault_lines'], later.splitlines())
        self.assertEqual(self.audit['excluded_fault_lines'], OLD.splitlines())
        self.assertEqual(self.audit['counted_gpu_incidents'], 1)
        self.assertEqual(self.audit['owner_acceptance_sha256'], screen.OWNER_ACCEPTANCE_SHA256)
        self.assertIn('exception', self.audit)

    def test_fault_at_acceptance_boundary_refused(self):
        with self.assertRaisesRegex(RuntimeError, 'fault at/after owner acceptance'):
            self.admit(OLD+line('2026-10-11T00:36:14'))

    def test_new_unexplained_host_fault_refused(self):
        with self.assertRaisesRegex(RuntimeError, 'fault at/after owner acceptance'):
            self.admit(OLD+line('2026-10-11T00:38:00', 'BUG: soft lockup - CPU#21 stuck for 22s!'))

    def test_untimestamped_fault_refused(self):
        with self.assertRaisesRegex(RuntimeError, 'Cannot timestamp fault'):
            self.admit(OLD+'xe Fault response\n')

    def test_all_health_card_evidence_still_required(self):
        health = copy.deepcopy(self.health)
        health['cards'][2]['copy_roundtrip_exact'] = False
        with self.assertRaisesRegex(RuntimeError, 'card 2 evidence'):
            self.admit(receipt=health)

    def test_screen_cli_passes_explicit_acceptance_to_worker(self):
        with tempfile.TemporaryDirectory() as temp:
            argv = ['screen.py', 'run', '--mode', 'calibrate-load', '--run-dir', str(Path(temp)/'fresh'),
                    '--health-receipt', str(HEALTH), '--owner-acceptance', str(ACCEPTANCE), '--execute']
            with patch.object(screen.sys, 'argv', argv), patch.object(screen, 'preflight'), \
                 patch.object(screen, 'overlay_check'), patch.object(screen, 'call') as call, \
                 contextlib.redirect_stdout(io.StringIO()):
                screen.main()
            command = call.call_args.args[0]
            self.assertEqual(command[command.index('--owner-acceptance')+1], str(ACCEPTANCE.resolve()))


if __name__ == '__main__':
    unittest.main()
