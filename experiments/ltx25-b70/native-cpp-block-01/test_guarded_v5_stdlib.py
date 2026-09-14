#!/usr/bin/env python3
"""Source/fake tests for one Comfy CPU import refusal; no native imports."""
import argparse
import ast
from contextlib import contextmanager
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
HELPER = HERE.parent / 'scripts/cpu_comfy_import_policy_v1.py'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


old = load('v4_fake_contracts', HERE / 'test_guarded_v4_stdlib.py')
policy = load('comfy_import_fake_contracts', HELPER)
harness = load('v5_harness_fake_contracts', HERE / 'test_block_cpu_guarded_v5.py')
guard = old.guard
SOURCE = '''try:
    _ = torch.xpu.device_count()
    xpu_available = torch.xpu.is_available()
except:
    xpu_available = False
'''


@contextmanager
def fixture(cpu=True, phase=policy.EXPECTED_PHASE):
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / 'model_management.py'; source.write_text(SOURCE)
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        with patch.object(policy, 'MODEL_SHA256', digest), patch.dict(sys.modules):
            sys.modules.pop(policy.MODULE_NAME, None)
            torch, report, originals = old.parent.fixture()
            report['phase'] = phase
            control = policy.ComfyImportPolicy(torch, report, guard, model_management_source=source)
            intact = old.parent.policy.install(torch, report, guard)
            module = ModuleType(policy.MODULE_NAME)
            module.__dict__.update(__file__=str(source), torch=torch, args=SimpleNamespace(cpu=cpu))
            sys.modules[policy.MODULE_NAME] = module
            yield SimpleNamespace(source=source, module=module, torch=torch, report=report,
                originals=originals, control=control, intact=intact,
                execute=lambda: exec(compile(SOURCE, str(source), 'exec', dont_inherit=True), module.__dict__))


class ImportContracts(unittest.TestCase):
    def test_exact_import_ordinary_refusal_and_completion(self):
        with fixture() as f:
            f.execute()
            f.control.finish_import(f.module)
            f.control.require_intact(require_complete=True); f.intact()
            self.assertEqual(len(f.report['cpu_comfy_import_omissions']), 1)
            self.assertEqual(f.report['accelerator_guard_attempts'], [])
            self.assertFalse(f.module.xpu_available)
            self.assertEqual(f.originals, [])
            self.assertIs(f.torch.xpu.is_available(), False)

    def test_second_same_import_refuses_even_before_completion(self):
        with fixture() as f:
            f.execute(); f.execute()  # Comfy bare except swallows BaseException.
            self.assertTrue(f.report['accelerator_guard_tripped'])
            with self.assertRaises(guard.AcceleratorAccessBlocked): f.control.finish_import(f.module)
            self.assertEqual(len(f.report['cpu_comfy_import_omissions']), 1)

    def test_post_import_call_delegates_frozen_trap(self):
        with fixture() as f:
            f.execute(); f.control.finish_import(f.module)
            with self.assertRaises(guard.AcceleratorAccessBlocked): f.torch.xpu.device_count()
            self.assertEqual(f.report['accelerator_guard_attempts'][0]['entry'], 'torch.xpu.device_count')
            self.assertEqual(f.originals, [])

    def test_wrong_phase_or_not_exact_cpu_true_is_sticky(self):
        for cpu, phase in ((False, policy.EXPECTED_PHASE), (1, policy.EXPECTED_PHASE), (True, 'python-compile')):
            with self.subTest(cpu=cpu, phase=phase), fixture(cpu, phase) as f:
                f.execute()
                self.assertTrue(f.report['accelerator_guard_tripped'])
                self.assertEqual(f.report['cpu_comfy_import_omissions'], [])
                with self.assertRaises(guard.AcceleratorAccessBlocked): f.control.require_intact()

    def test_foreign_code_or_globals_cannot_omit(self):
        for kind in ('code', 'globals'):
            with fixture() as f:
                if kind == 'code':
                    exec(compile(SOURCE + '\nforeign = True\n', str(f.source), 'exec', dont_inherit=True), f.module.__dict__)
                else:
                    exec(compile(SOURCE, str(f.source), 'exec', dont_inherit=True), dict(f.module.__dict__))
                self.assertTrue(f.report['accelerator_guard_tripped'])
                self.assertEqual(f.report['cpu_comfy_import_omissions'], [])

    def test_foreign_arguments_still_delegate_original_trap(self):
        with fixture() as f:
            with self.assertRaises(guard.AcceleratorAccessBlocked): f.torch.xpu.device_count(7, unexpected=True)
            event = f.report['accelerator_guard_attempts'][0]
            self.assertEqual(event['argument_types'], ['int'])
            self.assertEqual(event['keyword_names'], ['unexpected'])

    def test_missing_completion_cannot_pass(self):
        with fixture() as f:
            with self.assertRaises(guard.AcceleratorAccessBlocked): f.control.require_intact(require_complete=True)

    def test_wrong_completion_module_refuses(self):
        with fixture() as f:
            f.execute()
            with self.assertRaises(guard.AcceleratorAccessBlocked): f.control.finish_import(ModuleType('foreign'))

    def test_duplicate_completion_refuses(self):
        with fixture() as f:
            f.execute(); f.control.finish_import(f.module)
            with self.assertRaises(guard.AcceleratorAccessBlocked): f.control.finish_import(f.module)

    def test_late_module_or_hook_identity_change_refuses(self):
        for kind in ('module', 'hook'):
            with fixture() as f:
                f.execute(); f.control.finish_import(f.module)
                if kind == 'module': sys.modules[policy.MODULE_NAME] = ModuleType(policy.MODULE_NAME)
                else: f.torch.xpu.device_count = lambda: 0
                with self.assertRaises(guard.AcceleratorAccessBlocked): f.control.require_intact(require_complete=True)

    def test_source_pin_drift_refuses(self):
        with fixture() as f:
            f.source.write_text('changed')
            with self.assertRaises(RuntimeError): policy.source_gate(f.source)

    def test_non_cpu_result_false_is_required(self):
        with fixture() as f:
            f.execute(); f.module.xpu_available = True
            with self.assertRaises(guard.AcceleratorAccessBlocked): f.control.finish_import(f.module)


class SourceContracts(unittest.TestCase):
    def test_actual_comfy_source_pin_and_import_call(self):
        source = harness.SOURCE / 'comfy/model_management.py'
        self.assertEqual(policy.source_gate(source), source)
        tree = ast.parse(source.read_text())
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and ast.unparse(n.func) == 'torch.xpu.device_count']
        self.assertTrue(any(n.lineno == 127 for n in calls))

    def test_guard_helper_availability_import_order(self):
        text = (HERE / 'test_block_cpu_guarded_v5.py').read_text()
        ordered = ['guard.install(torch, report)', 'comfy_import_module.ComfyImportPolicy(torch, report, guard,',
                   'policy.install(torch, report, guard)', 'metadata_module.MetadataPolicy(triton_utils, report, guard)',
                   '        import comfy.ops', 'comfy_import_policy.finish_import(comfy.model_management)']
        self.assertEqual([text.index(part) for part in ordered], sorted(text.index(part) for part in ordered))
        self.assertEqual(text.count('comfy_import_module.ComfyImportPolicy('), 1)
        self.assertGreaterEqual(text.count('comfy_import_policy.require_intact(require_complete=True)'), 4)

    def test_finalizer_cannot_pass_without_unique_omission(self):
        tree = ast.parse((HERE / 'test_block_cpu_guarded_v5.py').read_text())
        main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
        final = next(n for n in main.body if isinstance(n, ast.Try)).finalbody[0]
        code = compile(ast.Module(body=[final], type_ignores=[]), '<v5-actual-finalizer>', 'exec')
        with fixture() as f:
            f.report['passed'] = True
            exec(code, {'comfy_import_policy': f.control, 'report': f.report})
            self.assertFalse(f.report['passed'])
            self.assertFalse(f.report['cpu_comfy_import_finalizer_intact'])
            self.assertTrue(f.report['accelerator_guard_tripped'])

    def test_frozen_v4_sources_unchanged(self):
        for name, digest in {'test_block_cpu_guarded_v4.py': '35924bf2f856afa57cb6f29c004b0dac56cf9d50764de8a6309dd432043a2a00',
                             'cpu_metadata_policy_v4.py': '4fffdedf7d109cc14456aef37031e7471138a9c19c840596efb1e3197e972a80'}.items():
            self.assertEqual(harness.sha(HERE / name), digest)

    def test_numerical_and_source_functions_unchanged(self):
        trees = [ast.parse((HERE / name).read_text()) for name in ('test_block_cpu_guarded_v4.py', 'test_block_cpu_guarded_v5.py')]
        for name in ('sha', 'require', 'no_fault', 'source_gate', 'emitted_census'):
            functions = [next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name) for tree in trees]
            self.assertEqual(ast.dump(functions[0]), ast.dump(functions[1]))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink(): raise FileExistsError(args.output)
    classes = (old.parent.parent.GuardContracts, old.parent.PolicyContracts, old.MetadataContracts,
               old.SourceContracts, ImportContracts, SourceContracts)
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(cls) for cls in classes)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    native = [name for name in sys.modules if name.split('.')[0] in ('torch', 'triton', 'comfy_kitchen')]
    receipt = {'passed': result.wasSuccessful() and not native, 'tests': result.testsRun,
        'failures': len(result.failures), 'errors': len(result.errors), 'native_modules': native,
        'scope': 'Stdlib/fake/source checks only; no native imports or model/device execution',
        'source_sha256s': {str(p): harness.sha(p) for p in (Path(__file__), HELPER, HERE / 'test_block_cpu_guarded_v5.py', HERE / 'test_block_cpu_guarded_v4.py')}}
    with args.output.open('x') as output: json.dump(receipt, output, indent=2); output.write('\n')
    raise SystemExit(not receipt['passed'])
