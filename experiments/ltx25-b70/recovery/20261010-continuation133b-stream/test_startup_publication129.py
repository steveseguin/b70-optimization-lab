"""Extract only transformed write_json; never import or run a launcher."""
import ast
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest import mock

import evidence129
import evidence_publication

PARENT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-128')


class StartupPublication129(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ltx129-startup-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.original = (PARENT / 'launch/serve-encoder.py').read_bytes()
        tree = ast.parse(evidence129.transform_launcher(self.original))
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                        and node.name == 'write_json')
        self.load = mock.Mock(return_value={'publish_bytes': evidence_publication.publish_bytes})
        namespace = dict(runpy=types.SimpleNamespace(run_path=self.load), Path=Path,
                         __file__=str(self.root / 'launch/serve-encoder.py'), json=json)
        exec(compile(ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])),
                     '<write-json129-only>', 'exec'), namespace)
        self.write_json = namespace['write_json']

    def test_startup_identity_preserves_exact_bytes(self):
        path = self.root / 'server-identity.json'
        value = {'pid': 123, 'nested': {'text': 'é', 'passed': True}}
        self.write_json(path, value)
        self.assertEqual(path.read_bytes(), (json.dumps(value, indent=2) + '\n').encode())
        self.load.assert_called_once_with(str(self.root / 'source/scripts/evidence_publication.py'))
        self.assertFalse(evidence_publication.temporary_name(path).exists())

    def test_startup_identity_duplicate_preserves_previous(self):
        path = self.root / 'server-identity.json'
        self.write_json(path, {'pid': 123})
        old = path.read_bytes()
        with self.assertRaises(FileExistsError):
            self.write_json(path, {'pid': 456})
        self.assertEqual(path.read_bytes(), old)

    def test_unknown_startup_writer_is_refused(self):
        with self.assertRaisesRegex(RuntimeError, 'parent differs'):
            evidence129.transform_launcher(self.original.replace(b"with path.open('x') as handle:", b'with bad_writer as handle:'))


if __name__ == '__main__':
    unittest.main()
