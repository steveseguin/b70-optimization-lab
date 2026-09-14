#!/usr/bin/env python3
"""Exercise the exact identity loop as a plugin __init__.py without native imports."""
import ast
import hashlib
from pathlib import Path
import tempfile
import types
import unittest

SOURCE = Path(__file__).with_name('multiblock_compile_node.py')
TREE = ast.parse(SOURCE.read_text())
REQUIRE = next(n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name == 'require')
CLASS = next(n for n in TREE.body if isinstance(n, ast.ClassDef) and n.name == 'LTXCompileBlocksGate')
APPLY = next(n for n in CLASS.body if isinstance(n, ast.FunctionDef) and n.name == '_apply')
LOOP = next(n for n in ast.walk(APPLY) if isinstance(n, ast.For) and
            isinstance(n.target, ast.Tuple) and [x.id for x in n.target.elts] == ['path', 'name'])


class PluginIdentity(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ltx-plugin-identity-')
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        plugin = root / 'custom_nodes/ltx_multiblock_compile_lab/__init__.py'
        adapter = root / 'scripts/ltx_multiblock_compile.py'
        activation = root / 'dependencies/ltx_native_activations_backend.py'
        rms = root / 'dependencies/ltx_native_rms_backend.py'
        self.paths = {'multiblock_compile_node.py': plugin, 'ltx_multiblock_compile.py': adapter,
                      'ltx_native_activations_backend.py': activation, 'ltx_native_rms_backend.py': rms}
        for name, path in self.paths.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('# fixture ' + name + '\n')
        self.digests = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in self.paths.items()}
        self.env = {'Path': Path, 'hashlib': hashlib, '__file__': str(plugin), 'hashes': {},
                    'server': {'extension_sha256s': dict(self.digests)},
                    'adapter': types.SimpleNamespace(__file__=str(adapter), activation_backend=
                        types.SimpleNamespace(__file__=str(activation), rms=types.SimpleNamespace(__file__=str(rms))))}

    def execute(self):
        exec(compile(ast.Module(body=[REQUIRE, LOOP], type_ignores=[]), str(SOURCE), 'exec'), self.env)

    def test_plugin_explicit_names_and_actual_dependency_paths(self):
        self.execute()
        self.assertEqual(self.env['hashes'], self.digests)
        self.assertNotIn('__init__.py', self.env['hashes'])
        self.assertFalse(self.paths['multiblock_compile_node.py'].with_name('ltx_native_activations_backend.py').exists())

    def test_plugin_bytes_must_match_sealed_extension(self):
        self.paths['multiblock_compile_node.py'].write_text('# changed plugin\n')
        with self.assertRaises(RuntimeError): self.execute()

    def test_actual_loaded_dependency_bytes_must_match(self):
        self.paths['ltx_native_activations_backend.py'].write_text('# changed actual dependency\n')
        with self.assertRaises(RuntimeError): self.execute()


if __name__ == '__main__':
    unittest.main()
