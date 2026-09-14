#!/usr/bin/env python3
"""Source/fake-module contracts only; never imports native dependencies."""
import argparse
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
SITE = Path('/home/steve/.venvs/ltx25-baseline/lib/python3.12/site-packages')


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


parent = load('guarded_v2_fake_contracts', 'test_guarded_v2_stdlib.py')
guard = parent.guard
policy = load('cpu_policy_fake_contracts', 'cpu_import_policy_v3.py')
harness = load('guarded_v3_fake_contracts', 'test_block_cpu_guarded_v3.py')


def fixture():
    fake, calls = parent.fake_torch()
    for device in (fake.cuda, fake.xpu):
        def original():
            calls.append('original availability'); raise AssertionError('Do not query hardware')
        device.is_available = original
    report = {'phase': 'stdlib-only'}
    guard.install(fake, report)
    return fake, report, calls


class PolicyContracts(unittest.TestCase):
    def test_both_availability_functions_pure_false(self):
        fake, report, calls = fixture(); intact = policy.install(fake, report, guard)
        for arm in policy.DESCRIPTION['arms']:
            for _ in range(3):
                self.assertIs(fake.cuda.is_available(), False)
                self.assertIs(fake.xpu.is_available(), False)
                intact()
        self.assertEqual(calls, [])
        self.assertEqual(report['accelerator_guard_attempts'], [])
        self.assertEqual(report['cpu_import_policy']['trap_identity_count'], 31)
        self.assertIsNone(report['cpu_import_policy']['cache_metadata_hook'])

    def test_availability_functions_have_only_literal_return(self):
        module = ast.parse((HERE / 'cpu_import_policy_v3.py').read_text())
        for name in ('cpu_cuda_unavailable', 'cpu_xpu_unavailable'):
            function = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == name)
            self.assertEqual(len(function.body), 1)
            self.assertEqual(ast.dump(function.body[0]), ast.dump(ast.Return(value=ast.Constant(value=False))))

    def test_all_31_traps_remain_active(self):
        fake, report, _ = fixture()
        for label in report['accelerator_guard_entries']:
            with self.subTest(entry=label):
                sample, current, calls = fixture(); intact = policy.install(sample, current, guard)
                target = sample
                for part in label.split('.')[1:]: target = getattr(target, part)
                with self.assertRaises(guard.AcceleratorAccessBlocked): target()
                with self.assertRaises(guard.AcceleratorAccessBlocked): intact()
                self.assertEqual(calls, [])

    def test_cannot_install_before_traps(self):
        fake, _, _ = fixture()
        with self.assertRaises(RuntimeError): policy.install(fake, {}, guard)

    def test_cannot_reset_sticky_refusal(self):
        fake, report, _ = fixture(); report['accelerator_guard_tripped'] = True
        with self.assertRaises(guard.AcceleratorAccessBlocked): policy.install(fake, report, guard)

    def test_cannot_reinstall(self):
        fake, report, _ = fixture(); policy.install(fake, report, guard)
        with self.assertRaises(RuntimeError): policy.install(fake, report, guard)

    def test_mutated_availability_or_trap_rejected(self):
        for device, name in (('cuda', 'is_available'), ('xpu', 'is_available'), ('xpu', 'current_stream')):
            fake, report, _ = fixture(); intact = policy.install(fake, report, guard)
            setattr(getattr(fake, device), name, lambda: False)
            with self.assertRaises(RuntimeError): intact()

    def test_actual_kitchen_registration_takes_unavailable_branch(self):
        fake, report, calls = fixture(); intact = policy.install(fake, report, guard)
        source = SITE / 'comfy_kitchen/backends/triton/__init__.py'
        function = next(n for n in ast.parse(source.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == '_register')
        rows = []
        registry = SimpleNamespace(mark_unavailable=lambda *args: rows.append(args),
                                   register=lambda **kwargs: self.fail('Must not register accelerator backend'))
        namespace = {'torch': fake, 'registry': registry, '_TRITON_AVAILABLE': True}
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), namespace)
        namespace['_register'](); intact()
        self.assertEqual(rows, [('triton', 'Neither CUDA nor XPU available on this system')])
        self.assertEqual(calls, [])

    def test_actual_triton_factory_no_active_driver_is_ordinary_error(self):
        source = SITE / 'triton/runtime/driver.py'
        function = next(n for n in ast.parse(source.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == '_create_driver')
        # Annotation stripped; fake driver only, no actual driver import/query.
        function.returns = None
        namespace = {'os': SimpleNamespace(environ={}), 'backends': {'fake': SimpleNamespace(driver=SimpleNamespace(is_active=lambda: False))}}
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), namespace)
        with self.assertRaisesRegex(RuntimeError, '0 active drivers'): namespace['_create_driver']()

    def test_unmodified_cache_metadata_catches_exception_but_not_guard(self):
        source = SITE / 'torch/_inductor/codecache.py'
        nodes = [n for n in ast.walk(ast.parse(source.read_text())) if isinstance(n, ast.Try)
                 and any(isinstance(c, ast.Call) and ast.unparse(c.func) == 'torch.utils._triton.triton_backend' for b in n.body for c in ast.walk(b))]
        node = min(nodes, key=lambda n: n.end_lineno - n.lineno)
        self.assertEqual(ast.unparse(node.handlers[0].type), 'Exception')
        code = compile(ast.Module(body=[node], type_ignores=[]), str(source), 'exec')
        for error in (RuntimeError('no driver'), guard.AcceleratorAccessBlocked('trap')):
            def raise_error(): raise error
            namespace = {'torch': SimpleNamespace(utils=SimpleNamespace(_triton=SimpleNamespace(triton_backend=raise_error)))}
            if isinstance(error, Exception): exec(code, namespace)
            else:
                with self.assertRaises(guard.AcceleratorAccessBlocked): exec(code, namespace)


class SourceContracts(unittest.TestCase):
    def test_frozen_sources(self):
        for name, digest in {'accelerator_guard_v2.py': 'b37549c29f589702e1a9a8279a9ecdc5355fb7b56277f35ff0199a34488908ce',
                             'test_block_cpu_guarded_v2.py': '4e57bf38aacf919870506e765787ec042c6e0a00c0f30deeb0eb180bcaddf002'}.items():
            self.assertEqual(harness.sha(HERE / name), digest)

    def test_policy_precedes_imports_and_shared_arm_loop(self):
        source = (HERE / 'test_block_cpu_guarded_v3.py').read_text()
        self.assertLess(source.index('persist_startup(args.evidence_dir, report)'), source.index('        import torch'))
        self.assertLess(source.index('guard.install(torch, report)'), source.index('policy.install(torch, report, guard)'))
        self.assertLess(source.index('policy.install(torch, report, guard)'), source.index('        import comfy.ops'))
        self.assertEqual(source.count('policy.install(torch, report, guard)'), 1)
        self.assertEqual(source.count('require_cpu_policy()'), 5)
        self.assertIn("'cpu_import_policy_schema': policy.DESCRIPTION['schema']", source)

    def test_startup_records_requested_policy_before_native_import(self):
        report = parent.StartupContracts().report()
        report['cpu_import_policy_requested'] = policy.DESCRIPTION
        with tempfile.TemporaryDirectory() as directory:
            value = harness.persist_startup(Path(directory), report)
        self.assertEqual(value['cpu_import_policy_requested'], policy.DESCRIPTION)
        self.assertFalse(value['torch_imported'])

    def test_nvidia_bypass_is_still_explicit_unresolved_source(self):
        source = SITE / 'triton/backends/nvidia/driver.py'
        function = next(n for n in ast.parse(source.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == '_cuda_driver_is_active')
        text = ast.unparse(function)
        self.assertIn('ctypes.CDLL(candidate)', text)
        self.assertIn('cu_init(0)', text)
        self.assertNotIn('torch.cuda.is_available', text)
        self.assertIn('Pending separate review', policy.DESCRIPTION['native_admission'])

    def test_unchanged_numerical_and_source_gate_functions(self):
        before = ast.parse((HERE / 'test_block_cpu_guarded_v2.py').read_text())
        after = ast.parse((HERE / 'test_block_cpu_guarded_v3.py').read_text())
        for name in ('sha', 'require', 'no_fault', 'source_gate', 'emitted_census'):
            select = lambda tree: next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
            self.assertEqual(ast.dump(select(before)), ast.dump(select(after)))
        # Reverse every intentional textual delta, proving the whole harness otherwise identical.
        original = (HERE / 'test_block_cpu_guarded_v2.py').read_text()
        changed = (HERE / 'test_block_cpu_guarded_v3.py').read_text()
        changed = changed.replace('Inactive guarded diagnostic v3: explicit CPU availability policy, unchanged native gates.', 'Inactive guarded diagnostic v2: durable startup identity and sticky accelerator halt.')
        changed = changed.replace(",\n              'cpu_import_policy_requested': report['cpu_import_policy_requested']", '')
        changed = changed.replace(", HERE / 'cpu_import_policy_v3.py'", '')
        changed = changed.replace("        policy_spec = importlib.util.spec_from_file_location('private_cpu_import_policy_v3', HERE / 'cpu_import_policy_v3.py')\n        policy = importlib.util.module_from_spec(policy_spec); policy_spec.loader.exec_module(policy)\n        report['cpu_import_policy_requested'] = copy.deepcopy(policy.DESCRIPTION)\n", '')
        changed = changed.replace('        require_cpu_policy = policy.install(torch, report, guard)\n', '')
        changed = changed.replace('require_cpu_policy()', 'guard.require_clean(report)')
        changed = changed.replace(", 'cpu_import_policy_schema': policy.DESCRIPTION['schema']", '')
        self.assertEqual(original, changed)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink(): raise FileExistsError(args.output)
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(cls)
                               for cls in (parent.GuardContracts, PolicyContracts, SourceContracts))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    native = [name for name in sys.modules if name.split('.')[0] in ('torch', 'triton', 'comfy_kitchen')]
    receipt = {'passed': result.wasSuccessful() and not native, 'tests': result.testsRun,
               'failures': len(result.failures), 'errors': len(result.errors), 'native_modules': native,
               'scope': 'Stdlib/fake/source checks only. No native qualification; NVIDIA ctypes bypass remains unresolved.',
               'source_sha256s': {p.name: harness.sha(p) for p in (Path(__file__), HERE / 'cpu_import_policy_v3.py', HERE / 'test_block_cpu_guarded_v3.py', HERE / 'accelerator_guard_v2.py')}}
    with args.output.open('x') as output: json.dump(receipt, output, indent=2); output.write('\n')
    raise SystemExit(not receipt['passed'])
