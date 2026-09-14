#!/usr/bin/env python3
"""CPU-only tests for campaign retention's destructive boundary."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('stability', Path(__file__).with_name('run-stability.py'))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class RetentionSafety(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.campaign = 'stability-01'
        self.run = 'stability-01-r01-boat'
        self.runs = {self.run}
        self.relative = Path('output/validation') / self.run / 'tensors.safetensors'
        self.path = self.root / self.relative
        self.path.parent.mkdir(parents=True)
        self.path.write_bytes(b'exact test tensor archive')
        self.receipts = self.root / 'receipts.jsonl'
        self.record = mod.inventory(self.root, self.campaign, self.runs, self.run, self.relative)

    def tearDown(self):
        self.temp.cleanup()

    def delete(self, passed):
        mod.delete_owned(self.root, self.campaign, self.runs, self.record,
                         parity_passed=passed, receipts=self.receipts)

    def test_failed_parity_preserves_archive(self):
        with self.assertRaises(RuntimeError):
            self.delete(False)
        self.assertTrue(self.path.exists())
        self.assertFalse(self.receipts.exists())

    def test_passed_parity_records_hash_and_deletes_only_one_file(self):
        sibling = self.path.with_name('summary.json')
        sibling.write_text('{}')
        self.delete(True)
        self.assertFalse(self.path.exists())
        self.assertTrue(sibling.exists())
        self.assertIn(self.record['sha256'], self.receipts.read_text())
        self.assertIn('completed', self.receipts.read_text())

    def test_traversal_and_absolute_paths_refused(self):
        for relative in ['../outside', '/etc/passwd', 'output/../outside']:
            with self.subTest(relative=relative), self.assertRaises(RuntimeError):
                mod.safe_path(self.root, relative)

    def test_symlink_file_refused(self):
        outside = self.root / 'protected'
        outside.write_bytes(b'protected')
        self.path.unlink()
        self.path.symlink_to(outside)
        with self.assertRaises(RuntimeError):
            self.delete(True)
        self.assertEqual(outside.read_bytes(), b'protected')

    def test_symlink_parent_refused(self):
        self.path.unlink()
        self.path.parent.rmdir()
        outside = self.root / 'protected-dir'
        outside.mkdir()
        (outside / self.path.name).write_bytes(b'protected')
        self.path.parent.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(RuntimeError):
            self.delete(True)
        self.assertEqual((outside / self.path.name).read_bytes(), b'protected')

    def test_original_and_unregistered_runs_refused(self):
        for run in ['baseline-01', 'resident-split-03', 'stability-01-r02-unknown']:
            with self.subTest(run=run), self.assertRaises(RuntimeError):
                mod.owned_file(self.root, self.campaign, self.runs, run,
                               Path('output/validation') / run / 'tensors.safetensors')

    def test_metadata_and_unknown_file_names_refused(self):
        for filename in ['summary.json', 'secret.mp4', 'float-lossless.mkv']:
            with self.subTest(filename=filename), self.assertRaises(RuntimeError):
                mod.owned_file(self.root, self.campaign, self.runs, self.run,
                               Path('output/validation') / self.run / filename)

    def test_mutation_after_inventory_preserves_file(self):
        self.path.write_bytes(b'changed file contents')
        with self.assertRaises(RuntimeError):
            self.delete(True)
        self.assertTrue(self.path.exists())
        self.assertFalse(self.receipts.exists())


if __name__ == '__main__':
    unittest.main()
