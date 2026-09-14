#!/usr/bin/env python3
"""V6 CPU diagnostic config contracts; stdlib/fakes/source only."""
import argparse
import ast
import builtins
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


old = load('v5_fake_contracts', HERE / 'test_guarded_v5_stdlib.py')
policy = load('v6_fake_policy', HERE / 'cpu_triton_policy_v6.py')
harness = load('v6_fake_harness', HERE / 'test_block_cpu_guarded_v6.py')
guard = old.guard
FAKE_SOURCE = '''import functools
@functools.cache
def has_triton():
    calls.append('native has_triton')
    return result
'''


@contextmanager
def fixture(result=False):
    with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ):
        root = Path(directory); path = root / 'torch/utils/_triton.py'
        path.parent.mkdir(parents=True); path.write_text(FAKE_SOURCE)
        config_path = root / 'torch/_inductor/config.py'; config_path.parent.mkdir(parents=True); config_path.write_text('# fake\n')
        pins = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in (path, config_path)}
        with patch.object(policy, 'SITE', root), patch.object(policy, 'PINS', pins):
            torch, report, _ = old.old.parent.fixture()
            policy.prepare_environment(report)
            calls = []; namespace = {'calls': calls, 'result': result, '__file__': str(path)}
            exec(compile(FAKE_SOURCE, str(path), 'exec', dont_inherit=True), namespace)
            utils = SimpleNamespace(**namespace)
            config = SimpleNamespace(__file__=str(config_path), triton_disable_device_detection=True)
            yield SimpleNamespace(report=report, utils=utils, config=config, calls=calls)


class PolicyContracts(unittest.TestCase):
    def test_native_function_and_environment_observed_without_replacement(self):
        with fixture() as f:
            original = f.utils.has_triton
            control = policy.CpuTritonPolicy(f.utils, f.config, f.report, guard)
            self.assertIs(f.utils.has_triton, original)
            self.assertEqual(f.calls, ['native has_triton'])
            control.require_intact()
            self.assertEqual(f.report['cpu_triton_policy']['native_has_triton'], False)
            self.assertTrue(f.report['cpu_triton_policy']['total_compiler_config_changed'])
            self.assertFalse(f.report['cpu_triton_policy']['numeric_OPTIONS_changed'])
            self.assertEqual(f.report['accelerator_guard_attempts'], [])

    def test_previous_environment_preserved_in_receipt(self):
        with patch.dict(os.environ, {policy.ENV_KEY: '0'}), fixture() as f:
            self.assertEqual(f.report['cpu_triton_environment']['previous'], '0')
            self.assertEqual(os.environ[policy.ENV_KEY], '1')
            self.assertFalse(f.report['cpu_triton_environment']['torch_imported'])

    def test_environment_must_precede_torch_import(self):
        with patch.dict(sys.modules, {'torch': SimpleNamespace()}):
            with self.assertRaises(RuntimeError): policy.prepare_environment({})

    def test_cannot_prepare_twice(self):
        with fixture() as f:
            with self.assertRaises(RuntimeError): policy.prepare_environment(f.report)

    def test_wrong_native_config_refuses_before_detection_call(self):
        with fixture() as f:
            f.config.triton_disable_device_detection = False
            with self.assertRaises(guard.AcceleratorAccessBlocked): policy.CpuTritonPolicy(f.utils, f.config, f.report, guard)
            self.assertEqual(f.calls, [])

    def test_native_result_must_be_exact_false(self):
        for result in (True, 0, None):
            with fixture(result) as f:
                with self.assertRaises(guard.AcceleratorAccessBlocked): policy.CpuTritonPolicy(f.utils, f.config, f.report, guard)
                self.assertTrue(f.report['accelerator_guard_tripped'])

    def test_late_environment_config_or_callable_change_refuses(self):
        for kind in ('environment', 'config', 'callable'):
            with fixture() as f:
                control = policy.CpuTritonPolicy(f.utils, f.config, f.report, guard)
                if kind == 'environment': os.environ[policy.ENV_KEY] = '0'
                elif kind == 'config': f.config.triton_disable_device_detection = False
                else: f.utils.has_triton = lambda: False
                with self.assertRaises(guard.AcceleratorAccessBlocked): control.require_intact()

    def test_actual_native_config_expression(self):
        tree = ast.parse((policy.SITE / 'torch/_inductor/config.py').read_text())
        assignment = next(n for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'triton_disable_device_detection' for t in n.targets))
        for value, expected in (('1', True), ('0', False), ('true', False)):
            namespace = {'os': SimpleNamespace(environ={policy.ENV_KEY: value})}
            exec(compile(ast.Module(body=[assignment], type_ignores=[]), '<native-config-expression>', 'exec'), namespace)
            self.assertIs(namespace['triton_disable_device_detection'], expected)

    def test_actual_has_triton_early_false_without_registry_import(self):
        source = policy.SITE / 'torch/utils/_triton.py'
        function = next(n for n in ast.parse(source.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == 'has_triton')
        function.decorator_list = []
        imports = []
        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            imports.append(name)
            if name != 'torch._inductor.config': raise AssertionError('No device/registry import allowed: ' + name)
            return SimpleNamespace(triton_disable_device_detection=True)
        namespace = {'has_triton_package': lambda: True, '__builtins__': {**vars(builtins), '__import__': fake_import}}
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), namespace)
        self.assertIs(namespace['has_triton'](), False)
        self.assertEqual(imports, ['torch._inductor.config'])


class SourceContracts(unittest.TestCase):
    def test_installed_source_pins(self):
        policy.source_gate()

    def test_environment_before_startup_torch_and_check_only_is_read_only(self):
        text = (HERE / 'test_block_cpu_guarded_v6.py').read_text()
        points = ['        if args.check_only:', 'triton_policy_module.prepare_environment(report)',
                  'persist_startup(args.evidence_dir, report)', '        import torch']
        self.assertEqual([text.index(x) for x in points], sorted(text.index(x) for x in points))
        self.assertIn("'TRITON_CACHE_DIR', triton_policy_module.ENV_KEY", text)
        self.assertEqual(text.count('triton_policy_module.CpuTritonPolicy('), 1)

    def test_frozen_v5_and_numeric_functions(self):
        self.assertEqual(harness.sha(HERE / 'test_block_cpu_guarded_v5.py'), 'f73a16e11f0674fdaac23366a68fa6bc6ceef3c2b249557fe5159a7610b405da')
        trees = [ast.parse((HERE / name).read_text()) for name in ('test_block_cpu_guarded_v5.py', 'test_block_cpu_guarded_v6.py')]
        for name in ('sha', 'require', 'no_fault', 'source_gate', 'emitted_census'):
            functions = [next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name) for tree in trees]
            self.assertEqual(ast.dump(functions[0]), ast.dump(functions[1]))

    def test_finalizer_rejects_swallowed_setting_change(self):
        tree = ast.parse((HERE / 'test_block_cpu_guarded_v6.py').read_text())
        main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
        final = next(n for n in main.body if isinstance(n, ast.Try)).finalbody[0]
        code = compile(ast.Module(body=[final], type_ignores=[]), '<v6-actual-finalizer>', 'exec')
        with fixture() as f:
            control = policy.CpuTritonPolicy(f.utils, f.config, f.report, guard)
            f.report['passed'] = True; f.config.triton_disable_device_detection = False
            exec(code, {'triton_policy': control, 'report': f.report})
            self.assertFalse(f.report['passed'])
            self.assertFalse(f.report['cpu_triton_finalizer_intact'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink(): raise FileExistsError(args.output)
    classes = (old.old.parent.parent.GuardContracts, old.old.parent.PolicyContracts, old.old.MetadataContracts,
               old.old.SourceContracts, old.ImportContracts, old.SourceContracts, PolicyContracts, SourceContracts)
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(cls) for cls in classes)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    native = [name for name in sys.modules if name.split('.')[0] in ('torch', 'triton', 'comfy_kitchen')]
    receipt = {'passed': result.wasSuccessful() and not native, 'tests': result.testsRun,
        'failures': len(result.failures), 'errors': len(result.errors), 'native_modules': native,
        'scope': 'Stdlib/fake/source checks only; no native imports or model/device execution',
        'source_sha256s': {str(p): harness.sha(p) for p in (Path(__file__), HERE / 'cpu_triton_policy_v6.py', HERE / 'test_block_cpu_guarded_v6.py', HERE / 'test_block_cpu_guarded_v5.py')}}
    with args.output.open('x') as output: json.dump(receipt, output, indent=2); output.write('\n')
    raise SystemExit(not receipt['passed'])
