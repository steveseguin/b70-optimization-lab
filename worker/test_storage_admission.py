"""CPU-only real Git snapshots with synthetic filesystem capacity/mount metadata."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import types
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('storage_sandbox', Path(__file__).with_name('sandbox.py'))
S = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(S)


class StorageAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.git('init', '-q')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('config', 'user.name', 'Fixture')
        self.files = [(b'empty', 0), ('nested/' + 'é' * 70 + '.txt', 17)]
        self.files[1] = (self.files[1][0].encode(), self.files[1][1])
        for name, size in self.files:
            p = self.repo / os.fsdecode(name)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b'x' * size)
        self.git('add', '--', '.')
        self.git('commit', '-qm', 'fixture')
        self.commit = self.git('rev-parse', 'HEAD').decode().strip()
        self.run = self.root / 'new-parent' / 'run'
        self.mounts = [{'mount_id': 1, 'mount_point': '/', 'filesystem_type': 'synthetic', 'source': 'fixture'}]

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.repo), *args], check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout

    def capacity(self, free, *, readonly=False, block=4096):
        return patch.object(S.os, 'statvfs', return_value=types.SimpleNamespace(
            f_bavail=free, f_frsize=1, f_bsize=block, f_flag=os.ST_RDONLY if readonly else 0))

    def plan(self, floor=0):
        with self.capacity(10**15), patch.object(S._storage, 'read_mounts', return_value=self.mounts):
            return S._snapshot_storage_admission(self.run, self.files, floor, None)

    def snapshot(self, free, **kwargs):
        with self.capacity(free), patch.object(S._storage, 'read_mounts', return_value=self.mounts):
            return S.prepare_snapshot(self.repo, self.commit, self.run, **kwargs)

    def test_default_floor_and_peak_are_refused_before_any_output_or_archive(self):
        budget = self.plan()['planned_write_bytes']
        with patch.object(S.subprocess, 'run', wraps=subprocess.run) as commands:
            with self.assertRaisesRegex(S.SandboxError, 'storage admission refused'):
                self.snapshot(S.DEFAULT_STORAGE_MIN_FREE_BYTES + budget - 1)
        self.assertFalse(self.run.parent.exists())
        self.assertFalse(any('archive' in c.args[0] for c in commands.call_args_list))
        self.assertEqual(self.git('status', '--porcelain'), b'')

    def test_exact_threshold_admits_and_records_actual_destination_and_budget(self):
        floor = 12345
        budget = self.plan(floor)['planned_write_bytes']
        metadata = self.snapshot(floor + budget, storage_min_free_bytes=floor)
        receipt = metadata['storage_admission']
        self.assertEqual(receipt['remaining_after_planned_write_bytes'], floor)
        self.assertEqual(receipt['resolved_destination'], str(self.run))
        self.assertEqual(receipt['checked_existing_path'], str(self.root))
        self.assertEqual(receipt['planned_write_bytes'], budget)
        self.assertFalse(receipt['snapshot_estimate']['reservation'])
        self.assertFalse(receipt['snapshot_estimate']['runtime_write_quota'])
        self.assertEqual(json.loads((self.run / 'snapshot.json').read_text())['storage_admission'], receipt)
        allocated = sum(p.stat().st_blocks * 512 for p in self.run.rglob('*'))
        self.assertGreater(budget, allocated)

    def test_explicit_zero_floor_admits_but_is_never_implicit_for_tmpfs(self):
        self.mounts.append({'mount_id': 2, 'mount_point': str(self.root), 'filesystem_type': 'tmpfs', 'source': 'tmpfs'})
        budget = self.plan()['planned_write_bytes']
        with self.assertRaisesRegex(S.SandboxError, 'storage admission refused'):
            self.snapshot(budget)
        self.assertFalse(self.run.parent.exists())
        metadata = self.snapshot(budget, storage_min_free_bytes=0, storage_require_mount=self.root)
        self.assertEqual(metadata['storage_admission']['min_free_bytes'], 0)
        self.assertEqual(metadata['storage_admission']['filesystem']['filesystem_type'], 'tmpfs')

    def test_invalid_floor_values_are_rejected_without_output(self):
        for bad in [True, False, -1, 1.0, '50GiB', None, [], {}]:
            with self.subTest(value=bad), self.assertRaisesRegex(S.SandboxError, 'nonnegative integer'):
                self.snapshot(10**15, storage_min_free_bytes=bad)
        self.assertFalse(self.run.parent.exists())

    def test_invalid_mount_values_are_rejected_without_output(self):
        for bad in [True, False, 0, '', ' ', [], {}]:
            with self.subTest(value=bad), self.assertRaisesRegex(S.SandboxError, 'nonempty path'):
                self.snapshot(10**15, storage_require_mount=bad)
        self.assertFalse(self.run.parent.exists())

    def test_readonly_destination_is_refused(self):
        with self.capacity(10**15, readonly=True), patch.object(S._storage, 'read_mounts', return_value=self.mounts):
            with self.assertRaisesRegex(S.SandboxError, 'read-only'):
                S.prepare_snapshot(self.repo, self.commit, self.run)
        self.assertFalse(self.run.parent.exists())

    def test_required_unmounted_external_root_is_refused(self):
        with self.assertRaisesRegex(S.SandboxError, 'not mounted'):
            self.snapshot(10**15, storage_require_mount=self.root)
        self.assertFalse(self.run.parent.exists())

    def test_different_nested_mount_is_refused(self):
        self.run.parent.mkdir()
        self.mounts += [
            {'mount_id': 2, 'mount_point': str(self.root), 'filesystem_type': 'synthetic', 'source': 'outer'},
            {'mount_id': 3, 'mount_point': str(self.run.parent), 'filesystem_type': 'synthetic', 'source': 'other'},
        ]
        with self.assertRaisesRegex(S.SandboxError, 'different mount'):
            self.snapshot(10**15, storage_require_mount=self.root)
        self.assertFalse(self.run.exists())

    def test_symlink_destination_refused_before_admission(self):
        alias = self.root / 'alias'; alias.symlink_to(self.root, target_is_directory=True)
        with patch.object(S._storage, 'inspect_destination') as inspect:
            with self.assertRaisesRegex(S.SandboxError, 'symlink ancestors'):
                S.prepare_snapshot(self.repo, self.commit, alias / 'run')
        inspect.assert_not_called()

    def test_actual_existing_destination_ancestor_and_full_budget_use_shared_helper(self):
        with self.capacity(10**15), patch.object(S._storage, 'read_mounts', return_value=self.mounts), \
                patch.object(S._storage, 'inspect_destination', wraps=S._storage.inspect_destination) as inspect:
            plan = S._snapshot_storage_admission(self.run, self.files, 123, None)
        self.assertEqual(inspect.call_count, 2)
        self.assertEqual(inspect.call_args.args[:3], (self.run, 123, plan['planned_write_bytes']))
        self.assertEqual(plan['checked_existing_path'], str(self.root))

    def test_estimate_charges_blocks_paths_directories_and_three_copies(self):
        a = self.plan()['snapshot_estimate']
        with self.capacity(10**15, block=65536), patch.object(S._storage, 'read_mounts', return_value=self.mounts):
            b = S._snapshot_storage_admission(self.run, self.files, 0, None)['snapshot_estimate']
        self.assertEqual(a['source_files'], 2)
        self.assertEqual(a['source_directories'], 1)
        self.assertGreater(a['archive_bytes'], sum(size for name, size in self.files))
        self.assertGreater(a['each_extracted_tree_bytes'], sum(size for name, size in self.files))
        self.assertGreater(b['each_extracted_tree_bytes'], a['each_extracted_tree_bytes'])
        self.assertGreaterEqual(a['receipt_allowance_bytes'], 256 * 1024**2)

    def test_source_cap_is_still_enforced_before_admission(self):
        self.assertEqual(S.MAX_SOURCE_BYTES, 2 * 1024**3)
        with patch.object(S, 'MAX_SOURCE_BYTES', 1), patch.object(S._storage, 'inspect_destination') as inspect:
            with self.assertRaisesRegex(S.SandboxError, 'size or file-count limit'):
                S.prepare_snapshot(self.repo, self.commit, self.run)
        inspect.assert_not_called()
        self.assertFalse(self.run.parent.exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
