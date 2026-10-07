#!/usr/bin/env python3
"""CPU identity/mutation controls, with no prepared model/runtime source tree."""
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('source99_checker', HERE / 'check-upstream-source-99.py')
C = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(C)
PSPEC = importlib.util.spec_from_file_location('source99_builder', HERE / 'prepare-upstream-99.py')
P = importlib.util.module_from_spec(PSPEC); PSPEC.loader.exec_module(P)


class PlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = json.loads(subprocess.check_output(['python3', '-B', str(HERE / 'prepare-upstream-99.py'), '--plan'], timeout=60))

    def test_actual_plan_checked_independently(self):
        tree, _ = C.validate_plan(self.plan)
        self.assertEqual(len(tree), 1270)
        self.assertEqual(self.plan['counts']['historical_files_accounted'], 1501)

    def test_wrong_commit_status_and_control_refused(self):
        for key, value in [('new_commit', C.OLD), ('status', 'READY'), ('qualification', True),
                           ('unchanged_control', {'sampler_split': '20/28', 'batch': 1, 'references': 'w93c'})]:
            with self.subTest(key=key):
                changed = copy.deepcopy(self.plan); changed[key] = value
                with self.assertRaises(ValueError): C.validate_plan(changed)

    def test_coherent_native_hash_relabel_refused(self):
        changed = copy.deepcopy(self.plan)
        changed['source_files']['comfy/sd.py']['sha256'] = '1' * 64
        with self.assertRaisesRegex(ValueError, 'Reviewed native overlay'): C.validate_plan(changed)

    def test_dropped_historical_dependency_refused(self):
        changed = copy.deepcopy(self.plan)
        del changed['historical_file_disposition']['launch/serve-encoder.py']
        with self.assertRaisesRegex(ValueError, 'Historical closure'): C.validate_plan(changed)

    def test_forged_patch_provenance_refused(self):
        changed = copy.deepcopy(self.plan); changed['overlay_patches']['comfy/sd.py'] += '# fake\n'
        with self.assertRaisesRegex(ValueError, 'patch provenance'): C.validate_plan(changed)


class SourceMutationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ltx99-source-check-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'source'; self.root.mkdir()
        raw = b'# exact\r\nvalue = "\xc3\xa9"\r\n'
        p = self.root / 'example.py'; p.write_bytes(raw); p.chmod(0o644)
        self.rows = {'example.py': {'basis': 'new-upstream', 'bytes': len(raw), 'sha256': C.sha(raw),
                                   'blob': C.blob(raw), 'mode': '100644', 'upstream_sha256': C.sha(raw)}}

    def test_exact_bytes_and_git_identity(self):
        self.assertEqual(C.check_source_files(self.root, self.rows), {})

    def test_extra_missing_and_modified_refused(self):
        empty = self.root / 'empty-extra'; empty.mkdir()
        with self.assertRaisesRegex(ValueError, 'inventory'): C.check_source_files(self.root, self.rows)
        empty.rmdir()
        extra = self.root / 'unexpected'; extra.write_text('extra')
        with self.assertRaisesRegex(ValueError, 'inventory'): C.check_source_files(self.root, self.rows)
        extra.unlink()
        p = self.root / 'example.py'; original = p.read_bytes(); p.write_bytes(original.replace(b'value', b'other'))
        with self.assertRaisesRegex(ValueError, 'bytes'): C.check_source_files(self.root, self.rows)
        p.unlink()
        with self.assertRaisesRegex(ValueError, 'inventory'): C.check_source_files(self.root, self.rows)

    def test_coherent_sha_tamper_still_checks_git_blob(self):
        raw = b'changed = True\n'; (self.root / 'example.py').write_bytes(raw)
        self.rows['example.py'].update(bytes=len(raw), sha256=C.sha(raw))
        with self.assertRaisesRegex(ValueError, 'Git blob'): C.check_source_files(self.root, self.rows)

    def test_fifo_refused_without_reading(self):
        p = self.root / 'example.py'; p.unlink(); os.mkfifo(p)
        with self.assertRaisesRegex(ValueError, 'Nonregular'): C.check_source_files(self.root, self.rows)

    def test_file_and_directory_symlinks_refused(self):
        p = self.root / 'example.py'; p.unlink(); p.symlink_to('/definitely-not-read')
        with self.assertRaisesRegex(ValueError, 'symlink'): C.check_source_files(self.root, self.rows)
        p.unlink(); p.write_bytes(b'x'); link = self.root / 'directory'; link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlink'): C.check_source_files(self.root, self.rows)

    def test_wrong_mode_and_traversal_refused(self):
        (self.root / 'example.py').chmod(0o600)
        with self.assertRaisesRegex(ValueError, 'mode'): C.check_source_files(self.root, self.rows)
        for name in ('../escape.py', '/absolute.py', './example.py', 'dir//file'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                C.check_source_files(self.root, {name: self.rows['example.py']})

    def test_duplicate_json_refused(self):
        with self.assertRaisesRegex(ValueError, 'Duplicate'): C.load_json(b'{"status":"READY","status":"UNSEALED"}')

    def test_archive_exact_missing_substitution_and_extra_refused(self):
        row = self.rows['example.py']; raw = (self.root / 'example.py').read_bytes()
        archive = Path(self.temp.name) / 'source.tar'
        def write(items):
            with tarfile.open(archive, 'w') as tar:
                for name, data in items:
                    member = tarfile.TarInfo(name); member.size = len(data); tar.addfile(member, io.BytesIO(data))
        write([('example.py', raw)])
        C.check_archive(archive, {'example.py': row}, self.rows)
        for items in ([], [('example.py', raw.replace(b'exact', b'other'))],
                      [('example.py', raw), ('extra.py', b'x')], [('example.py', raw), ('example.py', raw)]):
            write(items)
            with self.assertRaises(ValueError): C.check_archive(archive, {'example.py': row}, self.rows)

    def test_archive_wrong_exec_and_special_modes_refused(self):
        row = self.rows['example.py']; raw = (self.root / 'example.py').read_bytes()
        archive = Path(self.temp.name) / 'mode.tar'
        for expected, wrong in [('100644', 0o755), ('100755', 0o644), ('100644', 0o4644)]:
            selected = {**row, 'mode': expected}
            member = tarfile.TarInfo('example.py'); member.mode = wrong; member.size = len(raw)
            with tarfile.open(archive, 'w') as tar: tar.addfile(member, io.BytesIO(raw))
            with self.subTest(expected=expected, wrong=wrong):
                with self.assertRaisesRegex(ValueError, 'mode'): C.check_archive(archive, {'example.py': selected}, self.rows)
                with self.assertRaisesRegex(ValueError, 'mode'): P.verify_archive_member(member, raw, selected)


class GitReplacementTests(unittest.TestCase):
    def test_real_replacement_refs_cannot_change_objects_or_archive(self):
        with tempfile.TemporaryDirectory(prefix='ltx99-replace-fixture-') as directory:
            root = Path(directory); repo = root / 'repo'; repo.mkdir()
            def git(*args, data=None):
                return subprocess.check_output(['git', '-C', str(repo), *args], input=data, stderr=subprocess.PIPE)
            git('init', '-q', '--initial-branch=main')
            git('config', 'user.email', 'fixture@example.invalid'); git('config', 'user.name', 'Fixture')
            git('config', 'tar.umask', '0000')  # Builder must override ambient archive permissions.
            original, replacement = b'original\n', b'replaced\n'
            normal = repo / 'normal.py'; normal.write_bytes(original)
            executable = repo / 'run.py'; executable.write_bytes(original); executable.chmod(0o755)
            git('add', 'normal.py', 'run.py'); git('commit', '-qm', 'original fixture')
            commit = git('rev-parse', 'HEAD').decode().strip()
            oid = git('rev-parse', commit + ':normal.py').decode().strip()
            other = git('hash-object', '-w', '--stdin', data=replacement).decode().strip()
            git('replace', oid, other)
            self.assertEqual(git('cat-file', 'blob', oid), replacement)
            self.assertEqual(P.git(repo, 'cat-file', 'blob', oid), original)
            self.assertEqual(C.git(repo, 'cat-file', 'blob', oid), original)
            replacement_tree = git('mktree', data=('100644 blob ' + other + '\talternate.py\n').encode()).decode().strip()
            replacement_commit = git('commit-tree', replacement_tree, data=b'replacement commit\n').decode().strip()
            git('replace', commit, replacement_commit)
            self.assertEqual(git('ls-tree', '--name-only', commit).decode().strip(), 'alternate.py')
            rows = P.tree(repo, commit)
            self.assertEqual(set(C.git_tree(repo, commit)), {'normal.py', 'run.py'})
            self.assertEqual(dict(P.blobs(repo, rows)), {'normal.py': original, 'run.py': original})
            archive = root / 'fixture.tar'
            with archive.open('wb') as stream: P.write_archive(repo, commit, stream)
            with tarfile.open(archive) as tar:
                for item in tar:
                    raw = tar.extractfile(item).read()
                    self.assertEqual(raw, original)
                    self.assertEqual(item.mode, 0o755 if item.name == 'run.py' else 0o644)
                    P.verify_archive_member(item, raw, rows[item.name])


if __name__ == '__main__':
    unittest.main(verbosity=2)
