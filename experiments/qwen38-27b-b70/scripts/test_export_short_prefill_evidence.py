import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
spec = importlib.util.spec_from_file_location('exporter', Path(__file__).with_name('export-short-prefill-evidence.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class ExportTests(unittest.TestCase):
    def test_archive_deterministic_and_byte_exact(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / 'raw'
            root.mkdir()
            (root / 'receipt.json').write_bytes(b'{"raw": "bytes"}\n')
            a = m.archive(root, [root / 'receipt.json'], base / 'a.tar.gz')
            b = m.archive(root, [root / 'receipt.json'], base / 'b.tar.gz')
            self.assertEqual(a['sha256'], b['sha256'])
            with tarfile.open(base / 'a.tar.gz') as tar:
                self.assertEqual(tar.extractfile('receipt.json').read(), (root / 'receipt.json').read_bytes())
                self.assertEqual(tar.getmember('receipt.json').mtime, 0)

    def test_cache_and_unknown_subdirs_excluded(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            profile = root / '4b'
            for tree in ('cache', 'baseline', 'unrelated'):
                (profile / tree).mkdir(parents=True)
                (profile / tree / 'test.json').write_text('{}')
            (profile / 'DONE').write_text('done')
            self.assertEqual([p.relative_to(root).as_posix() for p in m.select(root, '4b')], ['4b/DONE', '4b/baseline/test.json'])

    def test_symlink_binary_credentials_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            good = root / 'good.txt'
            good.write_text('safe')
            link = root / 'link.txt'
            link.symlink_to(good)
            with self.assertRaises(ValueError): m.safe_file(link, root)
            for payload in (b'abc\x00def', b'-----BEGIN PRIVATE KEY-----', b'ghp_' + b'A' * 40):
                good.write_bytes(payload)
                with self.assertRaises(ValueError): m.safe_file(good, root)

    def test_cache_in_selected_tree_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / '4b/baseline/cache').mkdir(parents=True)
            with self.assertRaises(ValueError): m.select(root, '4b')

if __name__ == '__main__': unittest.main()
