"""CPU-only acceptance plumbing; no live journal, device, process or container."""
import ast
import os
import datetime as dt
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import time
import unittest
from unittest.mock import patch

import container_command
import first_forward_command
import single_rank_slab_probe as probe
import single_rank_first_forward_probe as forward
import watch_kernel

screen = probe.lane()
ACCEPTANCE = screen.REPO / screen.OWNER_ACCEPTANCE_RELATIVE
HEALTH = screen.REPO / 'experiments/ltx25-b70/data/resume-20261008/postflight-pre118b-20261010T0134Z.json'
BOOT = json.loads(ACCEPTANCE.read_text())['boot_id']
NOW = dt.datetime(2026, 10, 10, 2, tzinfo=dt.timezone.utc)
OLD = ('2026-10-09T02:20:00+00:00 kernel: Fault response\n'
       '2026-10-09T02:27:32+00:00 kernel: CAT error\n')
NEW = '2026-10-10T01:20:00+00:00 kernel: Fault response\n'


class FrozenDatetime(dt.datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW


class OwnerPlumbingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def status(self, sha=screen.OWNER_ACCEPTANCE_SHA256, passed=True):
        audit = screen.admission_audit()
        audit.update(passed=passed, owner_acceptance_sha256=sha,
                     excluded_fault_lines=OLD.splitlines(), counted_fault_lines=[] if passed else NEW.splitlines())
        (self.root / 'watcher.json').write_text(json.dumps(dict(passed=passed, boot_id=BOOT,
            health_sha256='health', updated_unix=NOW.timestamp(), read_started_unix=time.time()+1,
            journal_admission=audit)))

    def test_cpu_runner_rejects_device_open_audit_event(self):
        # Compile only the guard, without invoking the runner or opening a device.
        source = probe.PACKAGE / 'overlay-fix-teardown/run_cpu_tests.py'
        node = next(n for n in ast.parse(source.read_text()).body
                    if isinstance(n, ast.FunctionDef) and n.name == 'forbid_device_open')
        namespace = {'os': os}
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), 'exec'), namespace)
        guard = namespace['forbid_device_open']
        for path in ('/dev/dri/renderD128', b'/dev/dri/renderD128'):
            with self.assertRaisesRegex(RuntimeError, 'CPU suite forbids'):
                guard('open', (path, 'r', 0))
        guard('open', (str(ACCEPTANCE), 'r', 0))

    def test_both_printers_mount_and_forward_acceptance_readonly(self):
        realpath = container_command.os.path.realpath
        def resolve(path, *args, **kwargs):
            if str(path).startswith('/dev/dri/by-path/'):
                return '/dev/dri/renderD128'
            return realpath(path, *args, **kwargs)
        with patch.object(container_command.os.path, 'realpath', side_effect=resolve):
            for command in (container_command.command('/dev/dri/by-path/pci-0000:23:00.0-render', HEALTH, self.root,
                                                      owner_acceptance=ACCEPTANCE),
                            first_forward_command.command('/dev/dri/by-path/pci-0000:23:00.0-render', HEALTH,
                                                          self.root, 'a'*64, owner_acceptance=ACCEPTANCE)):
                target = '/repo/' + str(screen.OWNER_ACCEPTANCE_RELATIVE)
                self.assertIn(f'type=bind,src={ACCEPTANCE},dst={target},readonly', command)
                self.assertEqual(command[command.index('--owner-acceptance')+1], target)

    def test_watcher_acceptance_must_match_in_both_directions(self):
        with patch.object(dt, 'datetime', FrozenDatetime):
            for watcher_sha, expected in ((None, screen.OWNER_ACCEPTANCE_SHA256),
                                          (screen.OWNER_ACCEPTANCE_SHA256, None), ('tampered', screen.OWNER_ACCEPTANCE_SHA256)):
                self.status(watcher_sha)
                with self.assertRaisesRegex(RuntimeError, 'different owner acceptance'):
                    probe.check_watcher(self.root, BOOT, 'health', expected)

    def test_matching_watcher_copies_audit_to_probe_receipt(self):
        self.status()
        receipt = dict(boot_id=BOOT, health_sha256='health', owner_acceptance_sha256=screen.OWNER_ACCEPTANCE_SHA256)
        with patch.object(dt, 'datetime', FrozenDatetime):
            probe.check_receipt_watcher(self.root, receipt)
        self.assertEqual(receipt['journal_admission']['excluded_fault_lines'], OLD.splitlines())

    def test_final_postflight_refusal_retains_counted_lines(self):
        self.status(passed=False)
        (self.root / 'STOP').write_text('new fault')
        receipt = dict(boot_id=BOOT, health_sha256='health', owner_acceptance_sha256=screen.OWNER_ACCEPTANCE_SHA256)
        with self.assertRaisesRegex(RuntimeError, 'STOP'):
            probe.wait_postflight(self.root, receipt, 0)
        self.assertEqual(receipt['journal_admission']['counted_fault_lines'], NEW.splitlines())

    def watcher(self, text, health=HEALTH):
        argv = ['watch_kernel.py', '--health-receipt', str(health), '--receipt-dir', str(self.root),
                '--owner-acceptance', str(ACCEPTANCE)]
        (self.root / 'receipt.json').write_text(json.dumps(dict(worker_wait_status=0, postflight_requested_unix=0)))
        read_text = Path.read_text
        def read(path, *a, **kw):
            return BOOT if str(path) == '/proc/sys/kernel/random/boot_id' else read_text(path, *a, **kw)
        with patch.object(watch_kernel.argparse._sys, 'argv', argv), patch.object(Path, 'read_text', read), \
             patch.object(dt, 'datetime', FrozenDatetime), patch.object(watch_kernel.subprocess, 'run',
                 return_value=SimpleNamespace(stdout=text, stderr='')):
            watch_kernel.main()

    def test_watcher_success_records_excluded_lines_and_sha(self):
        self.watcher(OLD)
        audit = json.loads((self.root / 'watcher.json').read_text())['journal_admission']
        self.assertTrue(audit['passed'])
        self.assertEqual(audit['excluded_fault_lines'], OLD.splitlines())
        self.assertEqual(audit['owner_acceptance_sha256'], screen.OWNER_ACCEPTANCE_SHA256)

    def test_watcher_refusal_records_new_fault_and_sha(self):
        with self.assertRaisesRegex(RuntimeError, 'at/after owner acceptance'):
            self.watcher(OLD + NEW)
        audit = json.loads((self.root / 'watcher.json').read_text())['journal_admission']
        self.assertFalse(audit['passed'])
        self.assertEqual(audit['counted_fault_lines'], NEW.splitlines())
        self.assertEqual(audit['excluded_fault_lines'], OLD.splitlines())
        self.assertEqual(audit['owner_acceptance_sha256'], screen.OWNER_ACCEPTANCE_SHA256)

    def test_missing_health_watcher_still_records_acceptance(self):
        with self.assertRaises(FileNotFoundError):
            self.watcher(OLD, self.root / 'missing')
        audit = json.loads((self.root / 'watcher.json').read_text())['journal_admission']
        self.assertEqual(audit['owner_acceptance_sha256'], screen.OWNER_ACCEPTANCE_SHA256)
        self.assertFalse(audit['journal_evidence_available'])

    def test_slab_refusal_retains_acceptance_before_environment_gate(self):
        read_text = Path.read_text
        def read(path, *a, **kw):
            return BOOT if str(path) == '/proc/sys/kernel/random/boot_id' else read_text(path, *a, **kw)
        with patch.object(Path, 'read_text', read), patch.object(dt, 'datetime', FrozenDatetime), \
             patch.dict(probe.os.environ, {'FLASHNEXT_PROBE_ADMIT': '0'}), patch.object(probe.os, 'fork') as fork:
            code = probe.main(['--health-receipt', str(HEALTH), '--owner-acceptance', str(ACCEPTANCE),
                               '--receipt-dir', str(self.root), '--clean-exit'])
        self.assertEqual(code, 2)
        fork.assert_not_called()
        audit = json.loads((self.root / 'receipt.json').read_text())['journal_admission']
        self.assertEqual(audit['owner_acceptance_sha256'], screen.OWNER_ACCEPTANCE_SHA256)

    def test_direct_first_forward_worker_cannot_reuse_acceptance_implicitly(self):
        receipt = dict(boot_id=BOOT, health_sha256='health', owner_acceptance_sha256=screen.OWNER_ACCEPTANCE_SHA256)
        (self.root / 'receipt.json').write_text(json.dumps(receipt))
        args = SimpleNamespace(receipt_dir=self.root, health_receipt=HEALTH, owner_acceptance=None, overlay_sha256='a'*64)
        with patch.object(probe, 'admission', return_value=dict(boot_id=BOOT, health_sha256='health',
                                                              owner_acceptance_sha256=None)), \
             patch.object(forward, 'device_work') as device:
            self.assertEqual(forward.worker(args), 2)
        device.assert_not_called()
        result = json.loads((self.root / 'receipt.json').read_text())
        self.assertIn('worker admission differs: owner_acceptance_sha256', result['exception']['message'])


if __name__ == '__main__':
    unittest.main()
