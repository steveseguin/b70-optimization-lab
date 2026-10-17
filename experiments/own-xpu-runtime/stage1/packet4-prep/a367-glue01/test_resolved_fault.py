"""CPU-only synthetic admission and journal mutations; no health execution."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import resolved_fault as r

class Resolution(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.spec = r.w.read(r.RESOLUTION)
        self.boot = self.spec['boot_id']
        self.log = (r.w.REPO / self.spec['kernel_window_path']).read_text()
        self.health = r.w.read(r.w.REPO / self.spec['probe_receipt_path'])
        self.kernel = self.root / 'kernel.log'; self.kernel.write_text(self.log)
        self.probe = self.root / 'probe.json'; r.w.write(self.probe, self.health)
        self.spec.update(kernel_window_path=str(self.kernel), kernel_window_sha256=r.w.sha(self.kernel),
                         probe_receipt_path=str(self.probe), probe_receipt_sha256=r.w.sha(self.probe))
        self.resolution = self.root / 'resolution.json'
        r.w.write(self.resolution, self.spec)
        self.patcher = patch.object(r, 'RESOLUTION', self.resolution)
        self.patcher.start(); self.addCleanup(self.patcher.stop)

    def admit(self, log=None, health=None, spec=None, boot=None):
        return r.validate_resolution({'resolved_fault': self.spec if spec is None else spec},
                    self.health if health is None else health, boot or self.boot, self.log if log is None else log)

    def test_exact_set_accepted(self):
        self.assertEqual(self.admit(), self.spec)

    def test_order_is_not_membership(self):
        self.admit('\n'.join(reversed(r.w.fault_lines(self.log))))

    def test_third_line_refused(self):
        with self.assertRaisesRegex(ValueError, 'exact resolved set'):
            self.admit(self.log + '\n2026-10-16T21:12:00-04:00 kernel: xe Engine reset: new')

    def test_duplicate_third_line_refused(self):
        with self.assertRaises(ValueError):
            self.admit(self.log + '\n' + self.spec['fault_lines'][0]['text'])

    def test_altered_line_refused(self):
        with self.assertRaises(ValueError):
            self.admit(self.log.replace('logical_mask: 0x1', 'logical_mask: 0x2'))

    def test_missing_line_refused(self):
        with self.assertRaises(ValueError):
            self.admit(self.spec['fault_lines'][0]['text'])

    def test_missing_probe_refused(self):
        self.probe.unlink()
        with self.assertRaisesRegex(ValueError, 'probe missing'):
            self.admit()

    def test_probe_hash_tampering_refused(self):
        self.probe.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'probe hash'):
            self.admit()

    def test_fault_after_probe_refused_even_with_consistent_hashes(self):
        self.log = self.log.replace('21:09:16-04:00', '21:10:16-04:00')
        self.kernel.write_text(self.log)
        lines = r.w.fault_lines(self.log)
        self.spec['fault_lines'] = [{'text': line, 'sha256': hashlib.sha256(line.encode()).hexdigest()} for line in lines]
        self.spec['fault_lines_sha256'] = r.line_sha(lines)
        self.spec['kernel_window_sha256'] = r.w.sha(self.kernel)
        r.w.write(self.resolution, self.spec)
        with self.assertRaisesRegex(ValueError, 'precede probe'):
            self.admit()

    def test_during_probe_fault_refused(self):
        health = copy.deepcopy(self.health); health['journal_fault_lines_during_probe'] = ['fault']
        with self.assertRaises(ValueError):
            self.admit(health=health)

    def test_failed_resolving_probe_refused(self):
        health = copy.deepcopy(self.health); health['cards'][2]['pass'] = False
        r.w.write(self.probe, health)
        self.spec['probe_receipt_sha256'] = r.w.sha(self.probe)
        r.w.write(self.resolution, self.spec)
        with self.assertRaisesRegex(ValueError, 'rank coverage'):
            self.admit()

    def test_additional_resolution_refused(self):
        spec = copy.deepcopy(self.spec); spec['extra_resolution'] = self.spec
        with self.assertRaisesRegex(ValueError, 'single resolution'):
            self.admit(spec=spec)

    def test_wrong_boot_refused(self):
        with self.assertRaisesRegex(ValueError, 'wrong boot'):
            self.admit(boot='other')

    def test_launch_count_must_be_two(self):
        for count in (0, 1, 3, None):
            with self.subTest(count=count), self.assertRaises(ValueError):
                self.admit(health=dict(self.health, fault_lines_earlier_this_boot=count))

    def test_clean_boot_without_resolution(self):
        self.assertIsNone(r.validate_resolution({}, {'fault_lines_earlier_this_boot': 0}, 'new', 'kernel clean'))

    def test_nonzero_without_resolution_refused(self):
        with self.assertRaises(ValueError):
            r.validate_resolution({}, self.health, self.boot, self.log)

    def test_watcher_excludes_only_exact_set_and_latches_new_line(self):
        watch = r.ResolvedWatch(self.root, self.log, self.boot, {'resolved_fault': self.spec}, self.health)
        original = Path.read_text
        def read(path, *a, **kw):
            return self.boot if str(path) == '/proc/sys/kernel/random/boot_id' else original(path, *a, **kw)
        with patch.object(Path, 'read_text', read), patch.object(r, 'journal', return_value=self.log), patch.object(r.w, 'FAULT_ROOTS', ()):
            watch.poll()
            with patch.object(r, 'journal', return_value=self.log + '\n' + self.spec['fault_lines'][0]['text']):
                with self.assertRaisesRegex(ValueError, 'new kernel fault'):
                    watch.poll()
        self.assertEqual(len(r.w.read(self.root / 'FAULT.json')['lines']), 1)

    def test_watcher_rejects_lost_history(self):
        watch = r.ResolvedWatch(self.root, self.log, self.boot, {'resolved_fault': self.spec}, self.health)
        with patch.object(Path, 'read_text', return_value=self.boot), patch.object(r, 'journal', return_value='clean'), self.assertRaisesRegex(ValueError, 'history'):
            watch.poll()

if __name__ == '__main__':
    unittest.main()
