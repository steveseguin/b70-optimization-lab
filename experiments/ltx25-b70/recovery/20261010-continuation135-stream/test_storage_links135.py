"""Real CPU filesystem links and deterministic unlink/publication race coverage."""
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import run_storage as s


class Links135(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='ltx135-links-')
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.run = self.root / 'run'
        self.run.mkdir()
        self.a = self.run / 'a'
        self.a.write_bytes(b'x' * 8192)
        self.counter = s.OwnWrites(self.root, self.run, 'stream135')

    def expected(self, directories=()):
        return sum(p.stat().st_blocks * 512 for p in (self.run, self.a, *directories))

    def test_internal_link_counted_once(self):
        os.link(self.a, self.run / 'b')
        with patch.object(s.time, 'sleep') as sleep:
            self.assertEqual(self.counter.allocated_bytes(), self.expected())
        sleep.assert_called_once_with(s.LINK_RECHECK_SECONDS)

    def test_nested_internal_link_counted_once(self):
        sub = self.run / 'nested'; sub.mkdir()
        os.link(self.a, sub / 'b')
        self.assertEqual(self.counter.allocated_bytes(), self.expected((sub,)))

    def test_transient_external_link_disappears_on_only_retry(self):
        outside = self.root / 'outside'; os.link(self.a, outside)
        with patch.object(s.time, 'sleep', side_effect=lambda _: outside.unlink()) as sleep:
            self.assertEqual(self.counter.allocated_bytes(), self.expected())
        sleep.assert_called_once_with(s.LINK_RECHECK_SECONDS)

    def test_transient_internal_alias_disappears(self):
        alias = self.run / 'b'; os.link(self.a, alias)
        with patch.object(s.time, 'sleep', side_effect=lambda _: alias.unlink()) as sleep:
            self.assertEqual(self.counter.allocated_bytes(), self.expected())
        sleep.assert_called_once()

    def test_external_link_refusal_has_path_nlink_inode_and_scope(self):
        os.link(self.a, self.root / 'outside')
        with patch.object(s.time, 'sleep') as sleep, self.assertRaises(RuntimeError) as caught:
            self.counter.allocated_bytes()
        sleep.assert_called_once_with(0.01)
        for text in (str(self.a), 'nlink=[2]', 'owned_links=1', 'inode=', 'outside owned run tree'):
            self.assertIn(text, str(caught.exception))
        self.assertEqual(self.counter.scans, 0)

    def test_internal_and_external_link_still_refuses(self):
        os.link(self.a, self.run / 'b'); os.link(self.a, self.root / 'outside')
        with self.assertRaisesRegex(RuntimeError, 'nlink=\[3\].*owned_links=2'):
            self.counter.allocated_bytes()

    def test_selected_output_and_request_entries_are_owned(self):
        out = self.root / 'output'; out.mkdir()
        req = self.root / 'requests'; req.mkdir()
        os.link(self.a, out / 'stream135-preview')
        os.link(self.a, req / 'stream135-request')
        self.assertEqual(self.counter.allocated_bytes(), self.expected())

    def test_other_prefix_is_external_even_in_shared_parent(self):
        out = self.root / 'output'; out.mkdir()
        os.link(self.a, out / 'stream133b-preview')
        with self.assertRaisesRegex(RuntimeError, 'outside owned run tree'):
            self.counter.allocated_bytes()

    def test_unlink_between_lookup_and_stat_is_not_multiply_linked(self):
        real = s.os.stat
        raced = False
        def lookup(path, *args, **kwargs):
            nonlocal raced
            st = real(path, *args, **kwargs)
            if path == 'a' and not raced:
                raced = True
                self.a.unlink()
                return SimpleNamespace(st_mode=st.st_mode, st_dev=st.st_dev, st_ino=st.st_ino,
                                       st_nlink=0, st_blocks=st.st_blocks)
            return st
        with patch.object(s.os, 'stat', side_effect=lookup), patch.object(s.time, 'sleep') as sleep:
            self.assertEqual(self.counter.allocated_bytes(), self.run.stat().st_blocks * 512)
        sleep.assert_called_once()

    def test_deleted_alias_does_not_double_count_on_next_scan(self):
        b = self.run / 'b'; os.link(self.a, b)
        self.counter.allocated_bytes()
        b.unlink()
        self.assertEqual(self.counter.allocated_bytes(), self.expected())

    def test_single_link_rename_during_walk_retries_before_counting(self):
        # Rename a -> b after stat(a), with both names in the saved listing.
        b = self.run / 'b'; b.write_bytes(b'old')
        real = s.os.stat
        raced = False
        def lookup(path, *args, **kwargs):
            nonlocal raced
            st = real(path, *args, **kwargs)
            if path == 'a' and not raced:
                raced = True
                os.replace(self.a, b)
            return st
        # Force deterministic listing order using the walk's membership cache.
        st = self.run.stat()
        self.counter._dirs['run'] = ((st.st_dev, st.st_ino, st.st_mtime_ns, st.st_ctime_ns), ['a', 'b'])
        with patch.object(s.os, 'stat', side_effect=lookup), patch.object(s.time, 'sleep') as sleep:
            got = self.counter.allocated_bytes()
        sleep.assert_called_once()
        self.assertEqual(got, sum(p.stat().st_blocks * 512 for p in (self.run, b)))

    def test_background_failure_keeps_diagnostic(self):
        os.link(self.a, self.root / 'outside')
        bg = s.BackgroundOwnWrites(self.counter)
        bg.refresh()
        self.assertIn(str(self.a), bg.failed)
        self.assertIn('nlink=[2]', bg.failed)

    def test_directories_with_multiple_links_are_not_regular_files(self):
        sub = self.run / 'sub'; sub.mkdir()
        self.assertGreater(self.run.stat().st_nlink, 1)
        with patch.object(s.time, 'sleep') as sleep:
            self.assertEqual(self.counter.allocated_bytes(), self.expected((sub,)))
        sleep.assert_not_called()

    def test_same_content_distinct_inodes_both_count(self):
        b = self.run / 'b'; b.write_bytes(self.a.read_bytes())
        self.assertEqual(self.counter.allocated_bytes(), self.expected() + b.stat().st_blocks * 512)

    def test_rejected_scan_does_not_corrupt_previous_total(self):
        before = self.counter.allocated_bytes()
        outside = self.root / 'outside'; os.link(self.a, outside)
        with self.assertRaises(RuntimeError): self.counter.allocated_bytes()
        self.assertEqual(self.counter._total, before)
        outside.unlink()
        self.assertEqual(self.counter.allocated_bytes(), self.expected())
