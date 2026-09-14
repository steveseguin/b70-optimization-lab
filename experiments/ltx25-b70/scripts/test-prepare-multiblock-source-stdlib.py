#!/usr/bin/env python3
"""In-memory checker/graph construction only; never call prepare or create a packet."""
import ast
import copy
import importlib.util
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
SOURCE = Path(__file__).with_name('prepare-multiblock-runtime.py')
spec = importlib.util.spec_from_file_location('multiblock_preparer_source_test', SOURCE)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class SourceConstruction(unittest.TestCase):
    def setUp(self):
        self.parent = (builder.PARENT / 'launch/encoder_runtime_common.py').read_text()
        self.control = {'388': {'inputs': {'model': ['420', 0], 'other': 12}},
                        '391': {'inputs': {'model': ['420', 0]}},
                        '75': {'class_type': 'untouched'}}

    def test_checker_construction_preserves_other_functions(self):
        text = builder.checker_source(self.parent)
        def functions(text):
            return {n.name: ast.dump(n, include_attributes=False) for n in ast.parse(text).body
                    if isinstance(n, ast.FunctionDef)}
        old, new = functions(self.parent), functions(text)
        self.assertEqual(old.keys(), new.keys())
        self.assertEqual([n for n in old if old[n] != new[n]], ['verify_packet'])
        self.assertIn("manifest['native_rms_parent_manifest_sha256']", text)
        self.assertIn(builder.PARENT_SHA, text)
        self.assertIn(builder.ADAPTER_SHA, text)
        self.assertIn(builder.NODE_SHA, text)

    def test_extension_and_plugin_additions_only(self):
        def literals(text):
            return {n.targets[0].id: ast.literal_eval(n.value) for n in ast.parse(text).body
                    if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
                    and n.targets[0].id in ('EXTENSIONS', 'NODES')}
        old = literals(self.parent); new = literals(builder.checker_source(self.parent))
        self.assertEqual(new['EXTENSIONS'], old['EXTENSIONS'] + (builder.ADAPTER, builder.NODE))
        self.assertEqual(new['NODES'], {**old['NODES'], 'ltx_multiblock_compile_lab': builder.NODE})

    def test_ambiguous_or_missing_edit_anchor_rejected(self):
        anchor = "'ltx_block_compile_lab': 'block_compile_node.py'}"
        for text in (self.parent.replace(anchor, "'unexpected': 'block_compile_node.py'}"),
                     self.parent + '\n# ' + anchor):
            with self.assertRaises(RuntimeError): builder.checker_source(text)

    def test_nine_graph_choices_roundtrip_to_control(self):
        original = copy.deepcopy(self.control)
        seen = []
        for selection in builder.SELECTIONS:
            for mode in builder.MODES:
                graph = builder.graph_source(self.control, selection, mode)
                node = graph.pop('422')
                self.assertEqual(node['class_type'], 'LTXCompileBlocksGate')
                self.assertEqual(node['inputs']['selection'], selection)
                self.assertEqual(node['inputs']['mode'], mode)
                for name in ('388', '391'):
                    self.assertEqual(graph[name]['inputs']['model'], ['422', 0])
                    graph[name]['inputs']['model'] = ['420', 0]
                self.assertEqual(graph, original)
                seen.append((selection, mode))
        self.assertEqual(len(set(seen)), 9)
        self.assertEqual(self.control, original)

    def test_invalid_graph_choice_or_collision_rejected(self):
        with self.assertRaises(RuntimeError): builder.graph_source(self.control, 'other', 'compiled')
        with self.assertRaises(RuntimeError): builder.graph_source(self.control, 'all48', 'eager')
        with self.assertRaises(RuntimeError): builder.graph_source({**self.control, '422': {}}, 'all48', 'original')

    def test_changed_control_edge_rejected(self):
        self.control['388']['inputs']['model'] = ['bad', 0]
        with self.assertRaises(RuntimeError): builder.graph_source(self.control, 'single24', 'compiled')

    def test_no_native_import(self):
        self.assertNotIn('torch', sys.modules)
        self.assertNotIn('ltx_multiblock_compile', sys.modules)
        self.assertNotIn('multiblock_compile_node', sys.modules)


if __name__ == '__main__':
    unittest.main()
