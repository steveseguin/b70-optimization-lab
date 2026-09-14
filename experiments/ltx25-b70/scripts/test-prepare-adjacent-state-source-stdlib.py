#!/usr/bin/env python3
"""Source-only tests for packet07 preparation; no packet or native execution."""
import ast
import importlib.util
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
SOURCE = Path(__file__).with_name('prepare-adjacent-state-runtime.py')
spec = importlib.util.spec_from_file_location('adjacent_state_preparer_test', SOURCE)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class SourceContracts(unittest.TestCase):
    def setUp(self):
        self.original = (builder.PARENT / 'source/scripts/ltx_multiblock_compile.py').read_text()
        self.candidate = builder.CANDIDATE.read_text()
        self.checker = (builder.PARENT / 'launch/encoder_runtime_common.py').read_text()

    def test_exact_adapter_delta(self):
        builder.validate_adapter(self.original, self.candidate)
        def definitions(text):
            return {n.name: ast.dump(n, include_attributes=False) for n in ast.parse(text).body
                    if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
        before, after = definitions(self.original), definitions(self.candidate)
        self.assertEqual([name for name in before if before[name] != after[name]], ['CompiledBlockRoute'])

    def test_changed_guard_or_arithmetic_rejected(self):
        for text in (self.candidate.replace('return True', 'return False', 1),
                     self.candidate.replace("args['img'], v_context", "args['img'] * 1.0, v_context", 1)):
            self.assertNotEqual(text, self.candidate)
            with self.assertRaises(RuntimeError): builder.validate_adapter(self.original, text)

    def test_checker_only_verifier_changes(self):
        updated = builder.checker_source(self.checker)
        def definitions(text):
            return {n.name: ast.dump(n, include_attributes=False) for n in ast.parse(text).body
                    if isinstance(n, ast.FunctionDef)}
        before, after = definitions(self.checker), definitions(updated)
        self.assertEqual([name for name in before if before[name] != after[name]], ['verify_packet'])
        for name in ('EXTENSIONS', 'NODES'):
            def assigned(text):
                return ast.dump(next(n for n in ast.parse(text).body if isinstance(n, ast.Assign)
                    and isinstance(n.targets[0], ast.Name) and n.targets[0].id == name), include_attributes=False)
            self.assertEqual(assigned(self.checker), assigned(updated))
        self.assertIn('provenance/adjacent-state-parent/', updated)
        self.assertIn(builder.PARENT_SHA, updated)
        self.assertIn(builder.ORIGINAL_SHA, updated)
        self.assertIn(builder.ADAPTER_SHA, updated)

    def test_missing_checker_anchor_rejected(self):
        changed = self.checker.replace("multi['adapter_sha256']", "multi['unexpected_adapter']", 1)
        with self.assertRaises(RuntimeError): builder.checker_source(changed)

    def test_existing_packet_refused_and_no_native_import(self):
        with self.assertRaises(RuntimeError): builder.validate_inputs(builder.PARENT)
        self.assertNotIn('torch', sys.modules)
        self.assertNotIn('ltx_multiblock_compile', sys.modules)
        self.assertEqual(builder.MODIFIED, ('launch/encoder_runtime_common.py', 'source/scripts/ltx_multiblock_compile.py'))


if __name__ == '__main__':
    unittest.main()
