#!/usr/bin/env python3
"""Extract pure receipt guards with AST; never import Torch or the runtime node."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import types
import unittest

SOURCE = Path(__file__).with_name('multiblock_compile_node.py')
TREE = ast.parse(SOURCE.read_text())
OPTIONS = {'compile_threads': 1, 'emulate_precision_casts': True,
           'eager_numerics.division_rounding': True, 'triton.cudagraphs': False,
           'max_autotune': False, 'max_autotune_gemm': False}
ENV = {'Path': Path, 'json': json, 'hashlib': hashlib,
       'adapter': types.SimpleNamespace(OPTIONS=OPTIONS)}
selected = []
for node in TREE.body:
    if isinstance(node, ast.FunctionDef) and node.name in ('require', 'graph_receipts'):
        selected.append(node)
    if isinstance(node, ast.Assign) and any(isinstance(n, ast.Name) and
            n.id in ('ACTIVATIONS_SHA256', 'RMS_SHA256', 'SELECTIONS') for n in node.targets):
        selected.append(node)
exec(compile(ast.Module(body=selected, type_ignores=[]), str(SOURCE), 'exec'), ENV)


def row(number, device):
    rms = []
    for i in range(15):
        width = 4096 if i < 12 else 2048
        metadata = {'shape': [1, 64, width], 'contiguous': True,
                    'dtype': 'torch.bfloat16', 'device': device}
        rms.append({'node': f'rms{i}', 'normalized_shape': [width], 'input': metadata,
                    'weighted': i < 12, 'eps': 1e-5 if i < 12 else 1e-6,
                    'weight': {**metadata, 'shape': [width]} if i < 12 else None})
    v = 64 if number == 1 else 256
    activations = []
    for kind, shapes in [('sigmoid', [[1, v, 32]] * 3 + [[1, 26, 32]] * 3),
                         ('gelu', [[1, v, 16384], [1, 26, 8192]])]:
        for shape in shapes:
            activations.append({'node': f'act{len(activations)}', 'kind': kind,
                'input': {'shape': shape, 'stride': [shape[1] * shape[2], shape[2], 1],
                          'contiguous': True, 'dtype': 'torch.bfloat16', 'device': device},
                **({'approximate': 'tanh'} if kind == 'gelu' else {})})
    return {'schema': 'ltx25.native-activations-fx-rewrite.v1',
            'status': 'compiled-native-activations-boundary', 'graph': number,
            'source_sha256': ENV['ACTIVATIONS_SHA256'], 'dependency_sha256': ENV['RMS_SHA256'],
            'options': dict(OPTIONS), 'expected_count': 15,
            'expected_activation_counts': {'sigmoid': 6, 'gelu': 2},
            'replacements': rms, 'activation_replacements': activations}


class Contracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ltx-multiblock-contract-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for number in (1, 2):
            self.write(number, row(number, 'xpu:0'))
            for phase in ('before', 'after'):
                (self.root / f'graph-{number:03d}-{phase}.py').write_text('# fixture\n')

    def write(self, number, value):
        (self.root / f'graph-{number:03d}.json').write_text(json.dumps(value))

    def check(self, count=2, device='xpu:0'):
        return ENV['graph_receipts'](self.root, count, device)

    def reject(self, value, number=1):
        self.write(number, value)
        with self.assertRaises((RuntimeError, TypeError, KeyError, ValueError)):
            self.check()

    def test_both_route_devices(self):
        self.assertEqual(len(self.check()), 2)
        for n in (1, 2):
            self.write(n, row(n, 'xpu:1'))
        self.assertEqual(len(self.check(device='xpu:1')), 2)

    def test_first_stage_only(self):
        (self.root / 'graph-002.json').unlink()
        self.assertEqual(len(self.check(count=1)), 1)
        with self.assertRaises(RuntimeError): self.check(count=2)

    def test_missing_extra_or_failed_graph(self):
        self.write(3, row(3, 'xpu:0'))
        with self.assertRaises(RuntimeError): self.check()
        (self.root / 'graph-003.json').unlink()
        changed = row(1, 'xpu:0'); changed['status'] = 'failed'; self.reject(changed)

    def test_pins_options_and_count(self):
        for key, value in [('source_sha256', 'bad'), ('dependency_sha256', 'bad'),
                           ('options', {}), ('expected_count', 14),
                           ('expected_activation_counts', {'sigmoid': 6, 'gelu': 1})]:
            changed = row(1, 'xpu:0'); changed[key] = value; self.reject(changed)

    def test_graph_identity(self):
        for key, value in [('graph', True), ('graph', 2), ('schema', 'wrong'), ('error', 'bad')]:
            changed = row(1, 'xpu:0'); changed[key] = value; self.reject(changed)

    def test_rms_identity_weight_and_device(self):
        for key, value in [('weighted', False), ('eps', 1e-6), ('weight', None)]:
            changed = row(1, 'xpu:0'); changed['replacements'][0][key] = value; self.reject(changed)
        changed = row(1, 'xpu:0'); changed['replacements'][0]['input']['device'] = 'xpu:1'; self.reject(changed)
        changed = row(1, 'xpu:0'); changed['replacements'][-1] = copy.deepcopy(changed['replacements'][0]); self.reject(changed)

    def test_activation_shape_precision_layout(self):
        for key, value in [('shape', [1, 256, 32]), ('dtype', 'torch.float16'),
                           ('device', 'xpu:1'), ('stride', [1, 1, 1]), ('contiguous', False)]:
            changed = row(1, 'xpu:0'); changed['activation_replacements'][0]['input'][key] = value; self.reject(changed)

    def test_second_stage_shape(self):
        changed = row(1, 'xpu:0'); changed['graph'] = 2; self.reject(changed, number=2)

    def test_approximation_and_duplicates(self):
        changed = row(1, 'xpu:0'); changed['activation_replacements'][-1]['approximate'] = 'none'; self.reject(changed)
        changed = row(1, 'xpu:0'); changed['activation_replacements'][0]['approximate'] = 'tanh'; self.reject(changed)
        changed = row(1, 'xpu:0'); changed['activation_replacements'][-1] = copy.deepcopy(changed['activation_replacements'][0]); self.reject(changed)

    def test_sources_and_receipt_symlinks(self):
        p = self.root / 'graph-001-before.py'; p.unlink()
        with self.assertRaises(RuntimeError): self.check()
        p.write_text('# fixture\n')
        receipt = self.root / 'graph-001.json'; saved = self.root / 'saved.json'; receipt.rename(saved); receipt.symlink_to(saved)
        with self.assertRaises(RuntimeError): self.check()

    def test_fixed_bounded_selections(self):
        self.assertEqual(ENV['SELECTIONS'], {'single24': (24,), 'boundary4': (0, 20, 21, 47),
                                            'all48': tuple(range(48))})

    def test_original_parity_helpers_preserved(self):
        old = ast.parse(SOURCE.with_name('block_compile_node.py').read_text())
        names = {'independent_streams', 'ComparisonError', 'require_exact', 'exact_pair'}
        def extract(tree):
            return {n.name: ast.dump(n, include_attributes=False) for n in tree.body
                    if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names}
        self.assertEqual(extract(old), extract(TREE))


if __name__ == '__main__':
    unittest.main()
