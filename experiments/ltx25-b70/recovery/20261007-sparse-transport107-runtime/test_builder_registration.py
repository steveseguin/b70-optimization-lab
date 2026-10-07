"""CPU source regression for107's wrapper/helper mix-up; no node imports/builds."""
import ast
import importlib.util
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
AUTHOR = Path(__file__).resolve().parent.parent / '20261007-resolution-runtime'
SPEC = importlib.util.spec_from_file_location('registration107_builder', AUTHOR / 'runtime_packet.py')
B = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(B)
GRAPH_NODE = 'source/custom_nodes/ltx_graph_capture_lab/__init__.py'
GRAPH_HELPER = 'source/scripts/ltx_graph_capture.py'
GRAPH_WRAPPER = 'source/scripts/graph_capture_node.py'
MIRRORS = {
    'pipeline_node.py': 'ltx_pipeline_lab',
    'pipeline_sampler_node.py': 'ltx_pipeline_sampler_lab',
    'pipeline_decode_node.py': 'ltx_pipeline_decode_lab',
    'na_axis_decode_node.py': 'ltx_na_axis_decode_lab',
}


def registration(raw):
    """Read static exports, requiring every exported class to exist locally."""
    tree = ast.parse(raw)
    values = [n.value for n in tree.body if isinstance(n, ast.Assign)
              and any(isinstance(t, ast.Name) and t.id == 'NODE_CLASS_MAPPINGS'
                      for t in n.targets)]
    if len(values) != 1 or not isinstance(values[0], ast.Dict):
        raise ValueError('Missing unique static node registration')
    classes = {n.name for n in tree.body if isinstance(n, ast.ClassDef)}
    result = {}
    for key, value in zip(values[0].keys, values[0].values):
        if not (isinstance(key, ast.Constant) and isinstance(key.value, str)
                and isinstance(value, ast.Name) and value.id in classes
                and key.value not in result):
            raise ValueError('Invalid or missing registered node class')
        result[key.value] = value.id
    return result


class BuilderRegistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # source_delta only returns bytes; never materialize or execute nodes.
        cls.delta = B.source_delta(AUTHOR)

    def effective(self, path):
        return self.delta[path] if path in self.delta else B.regular(B.PARENT / path)

    def test_graph_gate_wrapper_and_export_preserved(self):
        before = B.regular(B.PARENT / GRAPH_NODE)
        after = self.effective(GRAPH_NODE)
        self.assertEqual(before, B.regular(B.PARENT / GRAPH_WRAPPER))
        self.assertEqual(after, before)
        self.assertEqual(self.effective(GRAPH_WRAPPER), before)
        self.assertEqual(registration(after), registration(before))
        self.assertEqual(registration(after), {'LTXGraphCaptureGate': 'LTXGraphCaptureGate'})

    def test_preserved_wrapper_imports_instrumented_canonical_adapter(self):
        imports = [(alias.name, alias.asname)
                   for n in ast.parse(self.effective(GRAPH_NODE)).body
                   if isinstance(n, ast.Import) for alias in n.names]
        self.assertIn(('ltx_graph_capture', 'adapter'), imports)
        helper = self.effective(GRAPH_HELPER)
        self.assertNotEqual(helper, B.regular(B.PARENT / GRAPH_HELPER))
        helper_imports = [(alias.name, alias.asname)
                          for n in ast.parse(helper).body if isinstance(n, ast.Import)
                          for alias in n.names]
        self.assertIn(('ltx_sparse_transport107', '_transport107'), helper_imports)
        self.assertEqual(B.RUNTIME_MODULES['sparse_transport.py'], 'ltx_sparse_transport107.py')

    def test_old_helper_as_wrapper_error_is_rejected(self):
        # This is the precise failed107 substitution, not an invented mutation.
        with self.assertRaisesRegex(ValueError, 'node registration'):
            registration(self.effective(GRAPH_HELPER))

    def test_export_without_class_definition_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'registered node class'):
            registration(b"NODE_CLASS_MAPPINGS = {'LTXGraphCaptureGate': LTXGraphCaptureGate}\n")

    def test_other_mirrors_are_actual_nodes_and_preserve_exports(self):
        for script, package in MIRRORS.items():
            with self.subTest(script=script):
                canonical = 'source/scripts/' + script
                node = 'source/custom_nodes/' + package + '/__init__.py'
                before = B.regular(B.PARENT / canonical)
                self.assertEqual(before, B.regular(B.PARENT / node))
                self.assertEqual(self.effective(canonical), self.effective(node))
                self.assertEqual(registration(before), registration(self.effective(node)))


if __name__ == '__main__':
    unittest.main()
