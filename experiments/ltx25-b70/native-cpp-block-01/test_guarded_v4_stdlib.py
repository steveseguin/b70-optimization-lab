#!/usr/bin/env python3
"""Inactive v4 source/fake contracts. No Torch/Inductor/Kitchen/Triton imports."""
import argparse
import ast
from contextlib import contextmanager
import functools
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


parent = load('v3_fake_contracts', 'test_guarded_v3_stdlib.py')
metadata = load('v4_metadata_contracts', 'cpu_metadata_policy_v4.py')
harness = load('v4_harness_contracts', 'test_block_cpu_guarded_v4.py')
guard = parent.guard

TRITON_SOURCE = '''import functools
@functools.cache
def triton_backend():
    raise AssertionError("Original backend must never run")
'''
ORDERED_SOURCE = '''class OrderedSet:
    __slots__ = ("_dict",)
    def __init__(self, iterable=None):
        self._dict = dict.fromkeys(iterable, None) if iterable is not None else {}
'''
CACHE_SOURCE = '''class FxGraphCache:
    @staticmethod
    def _save_graph(compiled_graph):
        try:
            backend = utils.triton_backend()
            compiled_graph.extern_libs_key = backend
        except Exception:
            pass
        compiled_graph.saved = True
'''


@contextmanager
def installed(bind=True):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        contents = {'torch/utils/_triton.py': TRITON_SOURCE,
                    'torch/utils/_ordered_set.py': ORDERED_SOURCE,
                    'torch/_inductor/codecache.py': CACHE_SOURCE,
                    'torch/_inductor/output_code.py': '# fake metadata source\n'}
        pins = {}
        for name, text in contents.items():
            path = root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text)
            pins[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        with patch.object(metadata, 'SITE', root), patch.object(metadata, 'PINS', pins):
            fake, report, originals = parent.fixture()
            intact = parent.policy.install(fake, report, guard)
            triton_ns = {'__file__': str(root / 'torch/utils/_triton.py')}
            exec(compile(TRITON_SOURCE, triton_ns['__file__'], 'exec', dont_inherit=True), triton_ns)
            utils = SimpleNamespace(**triton_ns)
            ordered_ns = {}
            exec(compile(ORDERED_SOURCE, str(root / 'torch/utils/_ordered_set.py'), 'exec', dont_inherit=True), ordered_ns)
            cache_ns = {'utils': utils, 'OrderedSet': ordered_ns['OrderedSet']}
            exec(compile(CACHE_SOURCE, str(root / 'torch/_inductor/codecache.py'), 'exec', dont_inherit=True), cache_ns)
            cache = cache_ns['FxGraphCache']
            control = metadata.MetadataPolicy(utils, report, guard)
            if bind: control.bind(cache)
            yield SimpleNamespace(root=root, torch=fake, report=report, originals=originals,
                utils=utils, cache=cache, control=control, intact=intact)


class MetadataContracts(unittest.TestCase):
    def test_exact_cpu_save_continues_without_backend(self):
        with installed() as f:
            graph = SimpleNamespace(device_types=f.control.ordered_set(['cpu']), extern_libs_key=None)
            f.cache._save_graph(graph)
            self.assertTrue(graph.saved); self.assertIsNone(graph.extern_libs_key)
            self.assertEqual(f.originals, [])
            self.assertEqual(f.report['accelerator_guard_attempts'], [])
            self.assertEqual(len(f.report['cpu_metadata_omissions']), 1)
            row = f.report['cpu_metadata_omissions'][0]
            self.assertEqual(row['device_types'], ['cpu']); self.assertEqual(row['ordinal'], 1)
            f.intact(); f.control.require_intact()

    def test_only_exact_ordered_layout_accepted(self):
        with installed() as f:
            graph = SimpleNamespace(device_types=f.control.ordered_set(['cpu']), extern_libs_key=None)
            f.cache._save_graph(graph)
            self.assertTrue(graph.saved)
        for cls in (set, frozenset, list, tuple):
            with installed() as f:
                with self.assertRaises(guard.AcceleratorAccessBlocked):
                    f.cache._save_graph(SimpleNamespace(device_types=cls(['cpu']), extern_libs_key=None))

    def test_foreign_iterable_never_iterated(self):
        class Foreign:
            def __iter__(self):
                raise AssertionError('Foreign iterator must never run')
        with installed() as f:
            with self.assertRaises(guard.AcceleratorAccessBlocked):
                f.cache._save_graph(SimpleNamespace(device_types=Foreign(), extern_libs_key=None))

    def test_non_string_metadata_refuses(self):
        with installed() as f:
            with self.assertRaises(guard.AcceleratorAccessBlocked):
                f.cache._save_graph(SimpleNamespace(device_types=f.control.ordered_set([None]), extern_libs_key=None))

    def test_unbound_query_sticky_refuses(self):
        with installed(False) as f:
            with self.assertRaises(guard.AcceleratorAccessBlocked): f.utils.triton_backend()
            with self.assertRaises(guard.AcceleratorAccessBlocked): f.control.bind(f.cache)
            self.assertTrue(f.report['accelerator_guard_tripped'])

    def test_foreign_direct_caller_refuses_even_cpu_graph(self):
        with installed() as f:
            compiled_graph = SimpleNamespace(device_types=f.control.ordered_set(['cpu']), extern_libs_key=None)
            with self.assertRaises(guard.AcceleratorAccessBlocked): f.utils.triton_backend()
            self.assertEqual(f.report['cpu_metadata_omissions'], [])

    def test_foreign_caller_arguments_refuse(self):
        with installed() as f:
            with self.assertRaises(guard.AcceleratorAccessBlocked): f.utils.triton_backend('cpu')
            self.assertIn('arguments', f.report['accelerator_guard_attempts'][0]['reason'])

    def test_non_cpu_or_missing_metadata_refuses(self):
        for fields in ({'device_types': {'xpu'}, 'extern_libs_key': None},
                       {'device_types': {'cpu', 'cuda'}, 'extern_libs_key': None},
                       {'device_types': set(), 'extern_libs_key': None},
                       {'device_types': None, 'extern_libs_key': None},
                       {'device_types': {'cpu'}},
                       {'device_types': {'cpu'}, 'extern_libs_key': 'old'}):
            with self.subTest(fields=fields), installed() as f:
                fields = dict(fields)
                if type(fields.get('device_types')) is set:
                    fields['device_types'] = f.control.ordered_set(fields['device_types'])
                graph = SimpleNamespace(**fields)
                with self.assertRaises(guard.AcceleratorAccessBlocked): f.cache._save_graph(graph)
                self.assertFalse(hasattr(graph, 'saved'))
                self.assertEqual(f.report['cpu_metadata_omissions'], [])

    def test_four_allowed_fifth_refuses(self):
        with installed() as f:
            for _ in range(4): f.cache._save_graph(SimpleNamespace(device_types=f.control.ordered_set(['cpu']), extern_libs_key=None))
            with self.assertRaises(guard.AcceleratorAccessBlocked):
                f.cache._save_graph(SimpleNamespace(device_types=f.control.ordered_set(['cpu']), extern_libs_key=None))
            self.assertEqual(len(f.report['cpu_metadata_omissions']), 4)

    def test_binding_replacement_refuses(self):
        with installed() as f:
            with self.assertRaises(guard.AcceleratorAccessBlocked): f.control.bind(f.cache)

    def test_modified_cache_function_rejected(self):
        with installed(False) as f:
            f.cache._save_graph = staticmethod(lambda compiled_graph: None)
            with self.assertRaises(guard.AcceleratorAccessBlocked): f.control.bind(f.cache)

    def test_cache_identity_late_mutation_refuses(self):
        with installed() as f:
            f.cache._save_graph = staticmethod(lambda compiled_graph: None)
            with self.assertRaises(guard.AcceleratorAccessBlocked): f.control.require_intact()

    def test_hook_identity_late_mutation_refuses(self):
        with installed() as f:
            f.utils.triton_backend = lambda: None
            with self.assertRaises(guard.AcceleratorAccessBlocked): f.control.require_intact()

    def test_equal_code_different_globals_rejected(self):
        with installed(False) as f:
            import types
            original = f.cache._save_graph
            f.cache._save_graph = staticmethod(types.FunctionType(original.__code__, {}, original.__name__))
            with self.assertRaises(guard.AcceleratorAccessBlocked): f.control.bind(f.cache)

    def test_source_drift_rejected_before_hook_install(self):
        with installed(False) as f:
            (f.root / 'torch/_inductor/output_code.py').write_text('changed')
            with self.assertRaises(RuntimeError): metadata.source_gate()

    def test_traps_retained_for_both_arms(self):
        for device, name in (('xpu', 'device_count'), ('cuda', 'current_stream')):
            with installed() as f:
                f.intact()
                self.assertIs(f.torch.cuda.is_available(), False)
                self.assertIs(f.torch.xpu.is_available(), False)
                with self.assertRaises(guard.AcceleratorAccessBlocked): getattr(getattr(f.torch, device), name)()
                with self.assertRaises(guard.AcceleratorAccessBlocked): f.control.require_intact()


class SourceContracts(unittest.TestCase):
    def test_installed_source_pins_and_code_extraction_only(self):
        metadata.source_gate()
        code = metadata.source_code('torch/_inductor/codecache.py', 'FxGraphCache._save_graph')
        self.assertEqual(code.co_qualname, 'FxGraphCache._save_graph')
        self.assertEqual(code.co_firstlineno, 2276)

    def test_v3_sources_unchanged(self):
        for name, expected in {'test_block_cpu_guarded_v3.py': 'd42c828d577dc7ecc7217224804480f4eb92cee1316356d87daae50202e2d9c2',
                               'cpu_import_policy_v3.py': '03fdcf06f6de141ef7197b2b8e5a813a0929bd2bc958825c7d68f4e353843c0a'}.items():
            self.assertEqual(harness.sha(HERE / name), expected)

    def test_hook_precedes_imports_and_binding_precedes_compile(self):
        text = (HERE / 'test_block_cpu_guarded_v4.py').read_text()
        self.assertLess(text.index('metadata_module.MetadataPolicy(triton_utils, report, guard)'), text.index('        import comfy.ops'))
        self.assertLess(text.index('metadata_policy.bind(FxGraphCache)'), text.index('        compiled ='))
        self.assertLess(text.index('persist_startup(args.evidence_dir, report)'), text.index('        import torch'))
        self.assertEqual(text.count('metadata_module.MetadataPolicy(triton_utils, report, guard)'), 1)
        self.assertIn("require(metadata_delta == expected_new_graphs", text)
        self.assertIn("require(len(report['cpu_metadata_omissions']) == 4", text)

    def test_startup_records_both_policies(self):
        report = parent.parent.StartupContracts().report()
        report['cpu_import_policy_requested'] = parent.policy.DESCRIPTION
        report['cpu_metadata_policy_requested'] = metadata.DESCRIPTION
        with tempfile.TemporaryDirectory() as directory:
            receipt = harness.persist_startup(Path(directory), report)
        self.assertEqual(receipt['cpu_metadata_policy_requested'], metadata.DESCRIPTION)
        self.assertFalse(receipt['torch_imported'])

    def test_finalizer_swallowed_tampering_cannot_pass(self):
        tree = ast.parse((HERE / 'test_block_cpu_guarded_v4.py').read_text())
        main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
        final = next(n for n in main.body if isinstance(n, ast.Try)).finalbody[0]
        code = compile(ast.Module(body=[final], type_ignores=[]), '<actual-v4-finalizer>', 'exec')
        with installed() as f:
            f.report['passed'] = True
            f.utils.triton_backend = lambda: None
            namespace = {'metadata_policy': f.control, 'require_cpu_policy': f.intact, 'report': f.report}
            exec(code, namespace)
            self.assertFalse(f.report['passed'])
            self.assertFalse(f.report['cpu_metadata_finalizer_intact'])
            self.assertTrue(f.report['accelerator_guard_tripped'])

    def test_numerical_functions_and_source_gate_unchanged(self):
        before = ast.parse((HERE / 'test_block_cpu_guarded_v3.py').read_text())
        after = ast.parse((HERE / 'test_block_cpu_guarded_v4.py').read_text())
        for name in ('sha', 'require', 'no_fault', 'source_gate', 'emitted_census'):
            select = lambda tree: next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
            self.assertEqual(ast.dump(select(before)), ast.dump(select(after)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink(): raise FileExistsError(args.output)
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(cls)
        for cls in (parent.parent.GuardContracts, parent.PolicyContracts, MetadataContracts, SourceContracts))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    native = [name for name in sys.modules if name.split('.')[0] in ('torch', 'triton', 'comfy_kitchen')]
    receipt = {'passed': result.wasSuccessful() and not native, 'tests': result.testsRun,
        'failures': len(result.failures), 'errors': len(result.errors), 'native_modules': native,
        'scope': 'Stdlib/source/fake contracts only; no CPU native block qualification or device execution',
        'source_sha256s': {p.name: harness.sha(p) for p in (Path(__file__), HERE / 'cpu_metadata_policy_v4.py', HERE / 'test_block_cpu_guarded_v4.py', HERE / 'cpu_import_policy_v3.py', HERE / 'accelerator_guard_v2.py')}}
    with args.output.open('x') as output: json.dump(receipt, output, indent=2); output.write('\n')
    raise SystemExit(not receipt['passed'])
