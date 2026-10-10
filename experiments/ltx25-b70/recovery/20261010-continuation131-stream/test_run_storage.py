"""CPU-only incident regressions and ownership/allowance gates."""
import ast
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import run_storage as s
import integration
import stream_contract
import test_gate_receipts as fixtures
import stream_receipts


def require(ok, why):
    if not ok:
        raise RuntimeError(why)


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ltx124-storage-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.run = self.root / 'run'
        self.run.mkdir()
        for name in ('output/validation', 'requests'):
            (self.root / name).mkdir(parents=True)
        self.counter = s.OwnWrites(self.root, self.run, 'stream131')
        self.free = 100 * s.GIB
        self.mock = patch.object(s.shutil, 'disk_usage', side_effect=lambda _: SimpleNamespace(free=self.free))
        self.mock.start()
        self.addCleanup(self.mock.stop)

    def write(self, path, size=8192):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b'x' * size)
        return target

    def check(self):
        return self.counter.check(3 * s.GIB, require)

    def test_other_writer_growth_does_not_refuse(self):
        before = self.check()['consumed_bytes']
        self.write('unrelated-build/log', 100000)
        self.write('output/stream123-s00000000/preview.mp4')
        self.write('requests/stream121-other.json')
        self.free -= 4 * s.GIB
        self.assertEqual(self.check()['consumed_bytes'], before)

    def test_own_growth_refuses_even_when_other_writer_frees_space(self):
        own = self.write('run/log')
        self.check()
        real_stat = s.os.stat
        def large(path, *args, **kwargs):
            st = real_stat(path, *args, **kwargs)
            if path == 'log':
                return SimpleNamespace(st_mode=st.st_mode, st_dev=st.st_dev, st_nlink=1,
                                       st_blocks=(3 * s.GIB + 512) // 512)
            return st
        self.free += 4 * s.GIB
        with patch.object(s.os, 'stat', side_effect=large):
            with self.assertRaisesRegex(RuntimeError, 'storage allowance exhausted'):
                self.check()

    def test_global_reserve_unchanged(self):
        self.free = 50 * s.GIB
        self.check()
        self.free -= 1
        with self.assertRaisesRegex(RuntimeError, '50 GiB reserve'):
            self.check()

    def test_owned_scopes_include_validation_requests_and_hidden_temps(self):
        files = [self.write(p) for p in ('run/receipts/r.json', 'output/stream131-s00000000/.preview.tmp',
                 'output/validation/stream131-qeager-c0/tensors.safetensors', 'requests/stream131-s00000000.json')]
        expected = sum(p.stat().st_blocks * 512 for p in files)
        expected += sum(p.stat().st_blocks * 512 for p in (self.run, self.run/'receipts',
            self.root/'output/stream131-s00000000', self.root/'output/validation/stream131-qeager-c0'))
        self.assertEqual(self.check()['consumed_bytes'], expected)

    def test_in_place_growth_updates_cached_membership(self):
        p = self.write('run/log')
        first = self.check()['consumed_bytes']
        old_dirs = dict(self.counter._dirs)
        with p.open('ab') as out:
            out.write(b'x' * 32768)
        self.assertEqual(self.check()['consumed_bytes'] - first, 32768)
        self.assertEqual(old_dirs, self.counter._dirs)

    def test_deletion_decrements_cache_without_negative_delta(self):
        p = self.write('output/stream131-s00000000/preview.mp4')
        blocks = p.stat().st_blocks * 512
        first = self.check()['consumed_bytes']
        p.unlink()
        self.assertEqual(first - self.check()['consumed_bytes'], blocks)
        self.assertGreaterEqual(self.check()['consumed_bytes'], 0)

    def test_sparse_files_count_allocated_blocks(self):
        p = self.run/'sparse'
        with p.open('wb') as out:
            out.truncate(4 * s.GIB)
        self.assertLess(self.check()['consumed_bytes'], s.GIB)

    def test_symlink_refused_without_following(self):
        (self.run/'link').symlink_to('/dev/dri')
        with self.assertRaisesRegex(RuntimeError, 'symlink'):
            self.check()

    def test_shared_parent_symlink_refused(self):
        (self.root/'requests').rmdir()
        (self.root/'requests').symlink_to('/dev/dri')
        with self.assertRaises(OSError):
            self.check()

    def test_hardlink_refused(self):
        p = self.write('run/a')
        os.link(p, self.run/'b')
        with self.assertRaisesRegex(RuntimeError, 'multiply linked'):
            self.check()

    def test_depth_bound(self):
        self.write('run/a/b/c/log')
        self.counter.max_depth = 1
        with self.assertRaisesRegex(RuntimeError, 'depth bound'):
            self.check()

    def test_entry_bound_includes_other_names(self):
        for i in range(10):
            self.write('requests/other-%d' % i)
        self.counter.max_entries = 4
        with self.assertRaisesRegex(RuntimeError, 'entry bound'):
            self.check()

    def test_runtime_calls_own_account_and_preserves_refusal(self):
        ctx = SimpleNamespace(storage_account=self.counter, run_write_allowance=3*s.GIB,
                              session=SimpleNamespace(require=require))
        self.assertEqual(integration.Runtime.storage_check(ctx)['accounting'], s.ACCOUNTING)
        with patch.dict(os.environ, LTX_RUN_WRITE_ALLOWANCE_GIB='64'):
            self.assertEqual(integration.Runtime.storage_check(ctx)['allowance_bytes'], 3*s.GIB)
        self.free = 49*s.GIB
        with self.assertRaisesRegex(RuntimeError, 'storage allowance exhausted'):
            integration.Runtime.storage_check(ctx, mutate=False)

    def test_unchanged_scan_reuses_directory_listings(self):
        self.write('run/a/log')
        expected = self.check()
        with patch.object(s.os, 'scandir', side_effect=AssertionError('uncached listing')):
            self.assertEqual(self.check(), expected)


class OptionTests(unittest.TestCase):
    def test_default(self):
        self.assertEqual(s.launch_allowance_bytes({}), 3*s.GIB)

    def test_all_valid_integers(self):
        for value in range(1,65):
            self.assertEqual(s.launch_allowance_bytes({'LTX_RUN_WRITE_ALLOWANCE_GIB': str(value)}), value*s.GIB)

    def test_invalid_options(self):
        for value in ('', '0', '65', '-1', '3.0', ' 3', '3 ', '+3', '03', '1e1', 'NaN', True, 3, None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                s.parse_allowance_gib(value)

    def test_receipt_binds_selected_allowance(self):
        rows, _, _ = fixtures.passing()
        r = rows[0]
        stream_receipts.validate_receipt(r)
        r['server_options']['run_write_allowance_bytes'] = 8*s.GIB
        r['storage']['allowance_bytes'] = 8*s.GIB
        stream_receipts.validate_receipt(r)
        r['storage']['allowance_bytes'] = 3*s.GIB
        with self.assertRaisesRegex(ValueError, 'storage allowance'):
            stream_receipts.validate_receipt(r)

    def test_receipt_missing_option_refuses(self):
        rows, _, _ = fixtures.passing()
        del rows[0]['server_options']['run_write_allowance_bytes']
        with self.assertRaises(ValueError):
            stream_receipts.validate_receipt(rows[0])

    def test_qualification_option_drift_refuses(self):
        rows, decodes, captures = fixtures.passing()
        rows[4]['server_options']['run_write_allowance_bytes'] = 4*s.GIB
        rows[4]['storage']['allowance_bytes'] = 4*s.GIB
        self.assertFalse(fixtures.decide(rows, decodes, captures)['passed'])

    def test_option_bound_to_three_receipt_writers(self):
        source = Path(integration.__file__).read_text()
        self.assertIn('record = dict(record, server_options=dict(self.server_options)', source)
        self.assertIn("record = {'server_options': dict(self.server_options)", source)
        self.assertIn("'storage': self.storage_check()", source)
        self.assertNotIn('free_at_install', source)

    def test_launch_grammar_and_preflight_budget(self):
        source = Path(__file__).with_name('launch-131.sh').read_text()
        self.assertIn('REC=${13:?health receipt}; MODE=${14:-launch}', source)
        self.assertIn('--planned-write-bytes "${WA}GiB"', source)
        self.assertIn('LTX_RUN_WRITE_ALLOWANCE_GIB=$WA', source)
        self.assertLess(source.index('WA=${LTX_RUN_WRITE_ALLOWANCE_GIB-3}'), source.index('ss -ltn'))
