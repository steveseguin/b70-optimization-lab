"""CPU-only tests for source integrity and safe relocation; no subprocesses."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('build_native', Path(__file__).with_name('build-native.py'))
BUILD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD)


class SourceTests(unittest.TestCase):
    def archive(self, root, entries):
        path = root / 'source.tar.gz'
        with tarfile.open(path, 'w:gz') as tf:
            for name, data, kind in entries:
                item = tarfile.TarInfo(name)
                item.type = kind
                item.size = len(data)
                tf.addfile(item, io.BytesIO(data))
        return path

    def manifest(self, archive, files):
        return {'archive': {'sha256': BUILD.digest(archive.read_bytes())}, 'original_root': '/old/repo',
                'source_files': {name: {'sha256': BUILD.digest(data), 'bytes': len(data)} for name, data in files.items()}}

    def test_relocation_keeps_math_and_binary_constants(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            files = {'a.cpp': b'#include "/old/repo/a.hpp"\nfloat f(float x){return x*x;}\n',
                     'rope.bf16': b'\x00\xff/old/repo'}
            archive = self.archive(root, [(n, b, tarfile.REGTYPE) for n, b in files.items()])
            source = root / 'new'
            result = BUILD.unpack(self.manifest(archive, files), archive, source)
            self.assertEqual((source / 'rope.bf16').read_bytes(), files['rope.bf16'])
            self.assertEqual((source / 'a.cpp').read_bytes().replace(str(source).encode(), b'/old/repo'), files['a.cpp'])
            self.assertEqual(set(result), set(files))

    def test_path_escape_and_links_are_rejected(self):
        for name, kind in [('../escape', tarfile.REGTYPE), ('/absolute', tarfile.REGTYPE), ('link', tarfile.SYMTYPE)]:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                archive = self.archive(root, [(name, b'x', kind)])
                with self.assertRaisesRegex(ValueError, 'unsafe'):
                    BUILD.unpack(self.manifest(archive, {name: b'x'}), archive, root / 'new')

    def test_hash_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = self.archive(root, [('a.cpp', b'bad', tarfile.REGTYPE)])
            with self.assertRaisesRegex(ValueError, 'source hash'):
                BUILD.unpack(self.manifest(archive, {'a.cpp': b'good'}), archive, root / 'new')

    def test_missing_member_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = self.archive(root, [])
            with self.assertRaisesRegex(ValueError, 'every pinned source'):
                BUILD.unpack(self.manifest(archive, {'a.cpp': b'good'}), archive, root / 'new')

    def test_manifest_rebuilds_every_object(self):
        manifest = json.loads(BUILD.MANIFEST.read_text())
        for lane, n in [('one-card', 42), ('two-card', 45)]:
            plan = manifest['plans'][lane]
            self.assertEqual(len(plan['translation_units']), n)
            built = {'@BUILD@/objects/' + row['id'] + '.o' for row in plan['translation_units']}
            linked = {a for a in plan['link_command'] if a.endswith('.o')}
            self.assertEqual(built, linked)
            self.assertTrue(all('-c' in row['command'] for row in plan['translation_units']))
            self.assertNotIn('/home/steve/', '\n'.join(plan['link_command']))


if __name__ == '__main__':
    unittest.main()
