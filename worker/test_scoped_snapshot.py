"""Fresh CPU Git fixtures only: explicit source scopes and patch boundaries."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import types
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('scoped_worker_sandbox', Path(__file__).with_name('sandbox.py'))
S = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(S)


class ScopedSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve(); self.repo = self.root / 'repo'; self.repo.mkdir()
        self.git('init', '-q'); self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('config', 'user.name', 'Fixture')
        files = {'AGENTS.md': 'Pinned root instruction.\n', 'pkg/AGENTS.md': 'Pinned package instruction.\n',
                 'pkg/calc.py': 'def calculate(x):\n    return x + 1\n',
                 'check.py': 'from pkg.calc import calculate\nassert calculate(1) == 3\n',
                 'excluded.txt': 'Do not reveal this unrelated content.\n',
                 'other/AGENTS.md': 'Unrelated instructions must not enter a scope.\n',
                 'newtests/AGENTS.md': 'Instructions for a future new test.\n'}
        for name, text in files.items(): self.put(name, text)
        self.commit = self.commit_all('bug fixture')
        self.run = self.root / 'run'
        stats = types.SimpleNamespace(f_bavail=1024**3, f_frsize=4096, f_bsize=4096, f_flag=0)
        self.capacity = patch.object(S.os, 'statvfs', return_value=stats)
        self.capacity.start(); self.addCleanup(self.capacity.stop)

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.repo), *args], check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout

    def put(self, name, text):
        p = self.repo / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(text)

    def commit_all(self, message):
        self.git('add', '--', '.'); self.git('commit', '-qm', message)
        return self.git('rev-parse', 'HEAD').decode().strip()

    def snapshot(self, **kwargs):
        return S.prepare_snapshot(self.repo, self.commit, self.run, **kwargs)

    def test_scoped_baseline_and_fixed_subset_keep_dependency_closure(self):
        self.put('pkg/calc.py', 'def calculate(x):\n    return x + 2\n')
        fixed = self.commit_all('fix fixture')
        meta = self.snapshot(source_paths=['pkg/calc.py', 'check.py'])
        self.assertEqual(meta['source_commit'], self.commit)
        old = subprocess.run([sys.executable, '-B', 'check.py'], cwd=self.run/'workspace', capture_output=True)
        self.assertNotEqual(old.returncode, 0)
        other = self.root / 'fixed'
        S.prepare_snapshot(self.repo, fixed, other, source_paths=['pkg/calc.py', 'check.py'])
        good = subprocess.run([sys.executable, '-B', 'check.py'], cwd=other/'workspace', capture_output=True)
        self.assertEqual(good.returncode, 0, good.stderr)
        self.assertFalse((self.run/'workspace/excluded.txt').exists())
        self.assertFalse((self.run/'workspace/.git').exists())

    def test_exact_archive_membership_and_pinned_blob_hashes(self):
        meta = self.snapshot(source_paths=['pkg/calc.py'])
        expected = {'AGENTS.md', 'pkg/AGENTS.md', 'pkg/calc.py'}
        with tarfile.open(self.run/'source.tar') as archive:
            self.assertEqual(set(archive.getnames()), expected)
            self.assertEqual(len(archive.getmembers()), len(expected))
            self.assertTrue(all(m.isfile() for m in archive.getmembers()))
        self.assertEqual(set(S._regular_tree(self.run/'workspace')), expected)
        scope = meta['source_scope']
        self.assertEqual(scope['mode'], 'explicit-task-scope')
        self.assertEqual(scope['requested_paths'], ['pkg/calc.py'])
        self.assertEqual(scope['auto_included_instruction_paths'], ['AGENTS.md', 'pkg/AGENTS.md'])
        self.assertEqual(scope['full_tree_entry_count'], 7)
        self.assertEqual(scope['excluded_entry_count'], 4)
        full = self.git('ls-tree', '-r', '-l', '-z', self.commit)
        self.assertEqual(scope['full_tree_manifest_sha256'], hashlib.sha256(full).hexdigest())
        for name, identity in scope['selected_files'].items():
            pinned = self.git('show', self.commit + ':' + name)
            self.assertEqual((self.run/'workspace'/name).read_bytes(), pinned)
            self.assertEqual(identity['sha256'], hashlib.sha256(pinned).hexdigest())
            self.assertEqual(identity['git_blob_oid'], self.git('rev-parse', self.commit+':'+name).decode().strip())
        self.assertEqual(scope['excluded_blob_bytes'], scope['full_tree_blob_bytes'] - scope['selected_file_bytes'])

    def test_ancestor_instructions_are_from_selected_commit_not_current_tree(self):
        self.put('AGENTS.md', 'Newer different instruction.\n'); self.commit_all('later instructions')
        self.snapshot(source_paths=['pkg/calc.py'])
        self.assertEqual((self.run/'workspace/AGENTS.md').read_text(), 'Pinned root instruction.\n')
        self.assertFalse((self.run/'workspace/other/AGENTS.md').exists())

    def test_new_path_includes_its_ancestor_instructions_and_exports_exact_addition(self):
        meta = self.snapshot(source_paths=['pkg/calc.py'], allowed_new_paths=['newtests/test_calc.py'])
        self.assertIn('newtests/AGENTS.md', meta['source_scope']['auto_included_instruction_paths'])
        (self.run/'workspace/newtests/test_calc.py').write_text('assert True\n')
        receipt = S.export_patch(self.run)
        self.assertEqual([e['path'] for e in receipt['changed_files']], ['newtests/test_calc.py'])
        self.assertEqual(receipt['source_scope']['allowed_new_paths'], ['newtests/test_calc.py'])

    def test_unexpected_additions_or_recreated_excluded_sources_refuse_export(self):
        self.snapshot(source_paths=['pkg/calc.py'])
        for name in ['excluded.txt', 'unplanned_test.py', 'new_directory/surprise.py']:
            target = self.run/'workspace'/name; target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('new content')
            with self.subTest(name=name), self.assertRaisesRegex(S.SandboxError, 'undeclared new paths'):
                S.export_patch(self.run)
            self.assertFalse((self.run/'changes.patch').exists())
            target.unlink()

    def test_existing_source_modification_exports_only_scoped_patch(self):
        self.snapshot(source_paths=['pkg/calc.py'])
        (self.run/'workspace/pkg/calc.py').write_text('def calculate(x):\n    return x + 2\n')
        receipt = S.export_patch(self.run)
        self.assertEqual([e['path'] for e in receipt['changed_files']], ['pkg/calc.py'])
        replay = self.root/'replay'; shutil.copytree(self.repo, replay)
        subprocess.run(['git','apply','--check',str(self.run/'changes.patch')],cwd=replay,check=True)
        subprocess.run(['git','apply',str(self.run/'changes.patch')],cwd=replay,check=True)
        self.assertEqual((replay/'excluded.txt').read_bytes(),(self.repo/'excluded.txt').read_bytes())

    def test_scope_paths_reject_empty_null_duplicates_traversal_globs_and_magic(self):
        bad = [[], None, 'pkg/calc.py', ['pkg/calc.py','pkg/calc.py'], ['/etc/passwd'],
               ['../excluded.txt'], ['pkg/../excluded.txt'], ['./check.py'], ['pkg//calc.py'],
               ['pkg/'], ['*.py'], ['pkg/[c]alc.py'], [':(top)check.py'], ['-x'], ['.git/config'],
               ['pkg\\calc.py'], ['check.py\n'], [False], ['not-here'], ['pkg']]
        for paths in bad:
            with self.subTest(paths=paths), self.assertRaises(S.SandboxError): self.snapshot(source_paths=paths)
            self.assertFalse(self.run.exists())

    def test_allowed_new_paths_cannot_name_existing_or_invalid_paths(self):
        for value in [None, True, ['excluded.txt'], ['pkg'], ['new.py','new.py'], ['../new.py'], ['*.py']]:
            with self.subTest(value=value), self.assertRaises(S.SandboxError):
                self.snapshot(source_paths=['check.py'], allowed_new_paths=value)
            self.assertFalse(self.run.exists())
        with self.assertRaisesRegex(S.SandboxError, 'requires explicit'):
            self.snapshot(allowed_new_paths=[])

    def test_scoped_selection_rejects_symlinks_and_symlink_instructions(self):
        (self.repo/'link').symlink_to('excluded.txt')
        self.commit = self.commit_all('link')
        with self.assertRaisesRegex(S.SandboxError, 'symlinks or submodules'):
            self.snapshot(source_paths=['link'])
        with self.assertRaisesRegex(S.SandboxError, 'ancestor'):
            self.snapshot(source_paths=['check.py'],allowed_new_paths=['link/new.py'])
        (self.repo/'pkg/AGENTS.md').unlink(); (self.repo/'pkg/AGENTS.md').symlink_to('../excluded.txt')
        self.commit = self.commit_all('instruction link')
        with self.assertRaisesRegex(S.SandboxError, 'symlinks or submodules'):
            self.snapshot(source_paths=['pkg/calc.py'])
        self.assertFalse(self.run.exists())

    def test_scoped_submodule_refused_but_unrelated_one_can_be_excluded(self):
        (self.repo/'sub').mkdir()
        self.git('update-index', '--add', '--cacheinfo', '160000,'+self.commit+',sub')
        self.git('commit','-qm','submodule fixture'); self.commit=self.git('rev-parse','HEAD').decode().strip()
        with self.assertRaisesRegex(S.SandboxError, 'symlinks or submodules'):
            self.snapshot(source_paths=['sub'])
        meta=self.snapshot(source_paths=['check.py'])
        self.assertEqual(meta['source_scope']['excluded_nonregular_entries'],1)

    def test_scoped_cap_applies_to_selected_sources_not_entire_repo(self):
        self.put('large-unrelated.txt','x'*4096); self.commit=self.commit_all('unrelated large file')
        with patch.object(S,'MAX_SOURCE_BYTES',512):
            with self.assertRaisesRegex(S.SandboxError,'size or file-count limit'): self.snapshot()
            self.assertFalse(self.run.exists())
            meta=self.snapshot(source_paths=['pkg/calc.py'])
        self.assertGreater(meta['source_scope']['full_tree_blob_bytes'],512)
        self.assertLess(meta['source_scope']['selected_file_bytes'],512)
        self.assertEqual(S.MAX_SOURCE_BYTES,2*1024**3)

    def test_full_snapshot_default_is_preserved(self):
        meta=self.snapshot()
        self.assertEqual(meta['source_scope']['mode'],'full-repository')
        self.assertTrue((self.run/'workspace/excluded.txt').exists())
        self.assertEqual(meta['source_scope']['excluded_entry_count'],0)

    def test_archive_attributes_cannot_omit_or_substitute_scoped_bytes(self):
        self.put('.gitattributes','pkg/calc.py export-ignore\ncheck.py export-subst\n')
        self.put('check.py','literal = "$Format:%H$"\n'); self.commit=self.commit_all('archive attributes')
        self.snapshot(source_paths=['pkg/calc.py','check.py'])
        self.assertTrue((self.run/'workspace/pkg/calc.py').exists())
        self.assertIn('$Format:%H$',(self.run/'workspace/check.py').read_text())
        self.assertFalse((self.run/'workspace/.gitattributes').exists())

    def test_readonly_planner_has_counts_budget_and_no_output(self):
        plan=S.plan_snapshot(self.repo,self.commit,self.run,source_paths=['pkg/calc.py'])
        self.assertEqual(plan['source_scope']['selected_file_count'],3)
        self.assertTrue(plan['storage_admission']['admitted'])
        self.assertGreater(plan['storage_admission']['planned_write_bytes'],0)
        self.assertFalse(self.run.exists())
        json.dumps(plan)

    def test_model_instance_sees_scope_and_new_file_restrictions_only_when_scoped(self):
        spec=importlib.util.spec_from_file_location('scoped_worker_run',Path(__file__).with_name('run.py'))
        runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
        historical='Issue: {{task}}\n\nAcceptance command: {{acceptance_command}}\nRead relevant project instructions, fix the issue, and add an appropriate regression test.'
        self.assertEqual(runner.instance_prompt({'source_scope':{'mode':'full-repository'}}),(historical,{}))
        plan=S.plan_snapshot(self.repo,self.commit,self.run,source_paths=['pkg/calc.py'],allowed_new_paths=['newtests/test_calc.py'])
        template,variables=runner.instance_prompt(plan)
        self.assertIn('{{source_scope_notice}}',template)
        notice=variables['source_scope_notice']
        for path in ('pkg/calc.py','AGENTS.md','pkg/AGENTS.md','newtests/AGENTS.md','newtests/test_calc.py'):
            self.assertIn(path,notice)
        self.assertIn('undeclared new file causes patch export to fail',notice)
        self.assertNotIn('excluded.txt',notice)
        plan['source_scope']['allowed_new_paths']=[]
        self.assertIn('"allowed_new_paths": []',runner.instance_prompt(plan)[1]['source_scope_notice'])

    def test_corrupt_archive_is_rejected_before_workspace_creation(self):
        original=S._archive_selected_blobs
        def corrupt(repo,entries,path):
            expected=original(repo,entries,path)
            with tarfile.open(path,'a') as archive:
                archive.addfile(tarfile.TarInfo('unexpected.txt'))
            return expected
        with patch.object(S,'_archive_selected_blobs',side_effect=corrupt):
            with self.assertRaisesRegex(S.SandboxError,'membership or pinned blob hashes'):
                self.snapshot(source_paths=['check.py'])
        self.assertFalse((self.run/'workspace').exists())
        self.assertFalse((self.run/'snapshot.json').exists())


if __name__=='__main__':unittest.main(verbosity=2)
