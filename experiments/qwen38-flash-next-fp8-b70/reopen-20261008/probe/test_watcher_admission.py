"""CPU-only watcher exits using fake journal, boot and clocks; no processes."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import watch_kernel as watcher


class WatcherAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.health = self.root / 'health.json'
        self.health.write_text('{"passed": true}\n')
        self.serial = 0

    def refusal(self, **changes):
        result = dict(schema='neural.download.flashnext-first-forward.v1',
                      passed=False, stage='admission_refused', worker_started=False,
                      admission_refused_unix=100.0,
                      exception={'type': 'ValueError', 'message': 'support path'})
        result.update(changes)
        return result

    def prepare(self, outcome):
        self.serial += 1
        self.directory = self.root / str(self.serial)
        self.directory.mkdir()
        if outcome is not None:
            (self.directory / 'receipt.json').write_text(json.dumps(outcome))
        self.elapsed = 0.0
        self.wall = 100.0
        self.reads = []

    def run_watcher(self, *, sleep_step=.5, fault=False):
        read_text = Path.read_text

        def read(path, *args, **kwargs):
            if str(path) == '/proc/sys/kernel/random/boot_id':
                return 'test-boot'
            return read_text(path, *args, **kwargs)

        def sleep(_seconds):
            self.elapsed += sleep_step
            self.wall += sleep_step

        def journal(*args, **kwargs):
            self.reads.append(self.wall)
            return SimpleNamespace(stdout='kernel: Fault response\n' if fault
                                   else 'kernel: clean test journal\n', stderr='')

        def admit(text, health, **kwargs):
            audit = kwargs['audit']
            audit.update(journal_evidence_available=True, passed=not fault,
                         counted_fault_lines=text.splitlines() if fault else [])
            if fault:
                raise RuntimeError('new kernel fault')

        screen = SimpleNamespace(admission_audit=lambda: dict(passed=False),
                                 admit_journal=admit)
        with patch.object(Path, 'read_text', read), \
             patch.object(watcher, 'lane', return_value=screen), \
             patch.object(watcher.subprocess, 'run', side_effect=journal), \
             patch.object(watcher.time, 'monotonic', side_effect=lambda: self.elapsed), \
             patch.object(watcher.time, 'time', side_effect=lambda: self.wall), \
             patch.object(watcher.time, 'sleep', side_effect=sleep):
            return watcher.main(['--health-receipt', str(self.health),
                                 '--receipt-dir', str(self.directory)])

    def status(self):
        return json.loads((self.directory / 'watcher.json').read_text())

    def assert_times_out(self, outcome):
        self.prepare(outcome)
        with self.assertRaisesRegex(RuntimeError, '150-second watcher bound exceeded'):
            self.run_watcher(sleep_step=151)
        self.assertEqual(len(self.reads), 1)
        self.assertFalse(self.status()['passed'])
        self.assertNotIn('status', self.status())
        self.assertIn('150-second', (self.directory / 'STOP').read_text())

    def test_terminal_refusal_finishes_promptly_with_failure_and_reason(self):
        self.prepare(self.refusal())
        self.assertEqual(self.run_watcher(), 2)
        self.assertEqual(self.elapsed, 0)
        self.assertEqual(self.reads, [100.0])
        status = self.status()
        self.assertFalse(status['passed'])
        self.assertEqual(status['status'], 'harness refused before device work')
        self.assertEqual(status['probe_exception']['message'], 'support path')
        self.assertEqual(status['new_fault_lines'], [])
        self.assertTrue(status['journal_admission']['passed'])
        self.assertEqual((self.directory / 'STOP').read_text(),
                         'harness refused before device work\n')
        self.assertFalse((self.directory / 'FAULT.json').exists())

    def test_refusal_requires_journal_read_started_after_refusal(self):
        self.prepare(self.refusal(admission_refused_unix=100.25))
        self.assertEqual(self.run_watcher(), 2)
        self.assertEqual(self.reads, [100.0, 100.5])
        self.assertGreaterEqual(self.status()['read_started_unix'], 100.25)

    def test_new_fault_takes_precedence_over_terminal_refusal(self):
        self.prepare(self.refusal())
        with self.assertRaisesRegex(RuntimeError, 'new kernel fault'):
            self.run_watcher(fault=True)
        status = self.status()
        self.assertNotIn('status', status)
        self.assertFalse(status['passed'])
        self.assertEqual(status['journal_admission']['counted_fault_lines'],
                         ['kernel: Fault response'])
        self.assertIn('new kernel fault', (self.directory / 'STOP').read_text())

    def test_missing_receipt_retains_timeout(self):
        self.assert_times_out(None)

    def test_old_skeletal_admission_receipt_does_not_end_monitoring(self):
        self.assert_times_out(dict(stage='admission', passed=False))

    def test_incomplete_refusal_markers_do_not_end_monitoring(self):
        for missing in ('schema', 'stage', 'passed', 'worker_started',
                        'admission_refused_unix'):
            with self.subTest(missing=missing):
                outcome = self.refusal()
                del outcome[missing]
                self.assert_times_out(outcome)

    def test_started_worker_cannot_be_classified_as_admission_refusal(self):
        self.assert_times_out(self.refusal(worker_started=True))

    def test_worker_identifiers_prevent_admission_shortcut(self):
        for key in ('worker_pid', 'worker_wait_status', 'worker_returncode'):
            with self.subTest(key=key):
                outcome = self.refusal(**{key: 42})
                if key == 'worker_wait_status':
                    # An unfinished independent post-worker handshake also cannot pass.
                    outcome['postflight_requested_unix'] = 200.0
                self.assert_times_out(outcome)

    def test_wrong_schema_and_unconfirmed_failure_do_not_end_monitoring(self):
        for change in (dict(schema='other'), dict(passed=True), dict(passed=None),
                       dict(admission_refused_unix='100')):
            with self.subTest(change=change):
                self.assert_times_out(self.refusal(**change))

    def test_original_post_worker_handshake_requires_fresh_read(self):
        self.prepare(dict(worker_wait_status=0, postflight_requested_unix=100.25))
        self.assertIsNone(self.run_watcher())
        self.assertEqual(self.reads, [100.0, 100.5])
        self.assertTrue(self.status()['passed'])
        self.assertFalse((self.directory / 'STOP').exists())

    def test_existing_stop_and_fault_survive_admission_refusal(self):
        self.prepare(self.refusal())
        stop = 'original STOP evidence\n'
        fault = '{"original": "fault evidence"}\n'
        (self.directory / 'STOP').write_text(stop)
        (self.directory / 'FAULT.json').write_text(fault)
        self.assertEqual(self.run_watcher(), 2)
        self.assertEqual((self.directory / 'STOP').read_text(), stop)
        self.assertEqual((self.directory / 'FAULT.json').read_text(), fault)

    def test_existing_stop_and_fault_survive_timeout(self):
        self.prepare(None)
        (self.directory / 'STOP').write_text('keep STOP\n')
        (self.directory / 'FAULT.json').write_text('keep FAULT\n')
        with self.assertRaisesRegex(RuntimeError, '150-second'):
            self.run_watcher(sleep_step=151)
        self.assertEqual((self.directory / 'STOP').read_text(), 'keep STOP\n')
        self.assertEqual((self.directory / 'FAULT.json').read_text(), 'keep FAULT\n')


if __name__ == '__main__':
    unittest.main()
