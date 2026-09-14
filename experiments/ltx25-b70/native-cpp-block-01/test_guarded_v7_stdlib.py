#!/usr/bin/env python3
"""V7 registry source/fake checks. Never imports native dependencies."""
import argparse
import ast
from contextlib import contextmanager
import importlib.util
import json
from pathlib import Path
import sys
from types import FunctionType, ModuleType, SimpleNamespace
from typing import Iterable
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


old = load('v6_fake_contracts', HERE / 'test_guarded_v6_stdlib.py')
policy = load('v7_registry_fake_contracts', HERE / 'cpu_device_registry_policy_v7.py')
harness = load('v7_harness_fake_contracts', HERE / 'test_block_cpu_guarded_v7.py')
guard = old.guard


@contextmanager
def fixture():
    with patch.dict(sys.modules):
        sys.modules.pop('torch._dynamo.variables.torch', None)
        # Existing frozen fake guard fixture, no actual Torch imported.
        torch, report, originals = old.old.old.parent.fixture()
        class FakeDevice:
            pass
        torch.device = FakeDevice
        module = ModuleType('torch._dynamo.device_interface')
        module.__file__ = str(policy.SITE / policy.DEVICE_SOURCE)
        module.torch = torch
        module.Iterable = Iterable
        def fake_stream(*args, **kwargs): raise AssertionError('No stream call allowed')
        class Base:
            stream = staticmethod(fake_stream)
            current_stream = staticmethod(fake_stream)
            Event = type('Event', (), {})
        module.DeviceInterface = Base
        for key, name in policy.INTERFACES:
            cls = type(name, (Base,), {'__module__': module.__name__})
            if key in ('cuda', 'xpu'):
                for attr in ('current_device', 'set_device', 'device_count', 'current_stream', 'synchronize', 'get_device_properties'):
                    setattr(cls, attr, staticmethod(getattr(getattr(torch, key), attr)))
                raw = getattr(torch._C, '_' + key + '_getCurrentRawStream')
                setattr(module, 'get_' + key + '_stream', raw)
                cls.get_raw_stream = staticmethod(raw)
            setattr(module, name, cls)
        module.device_interfaces = {}
        module._device_initialized = False
        tree = ast.parse((policy.SITE / policy.DEVICE_SOURCE).read_text())
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in policy.FUNCTIONS]
        code = compile(ast.Module(body=functions, type_ignores=[]), module.__file__, 'exec', dont_inherit=True)
        exec(code, vars(module))
        sys.modules[module.__name__] = module
        yield SimpleNamespace(torch=torch, report=report, originals=originals, module=module, code=code)


class RegistryContracts(unittest.TestCase):
    def test_native_zero_initializer_mapping_and_handler_metadata_match(self):
        with fixture() as f:
            original_registry = f.module.device_interfaces
            controller = policy.CpuDeviceRegistryPolicy(f.module, f.torch, f.report, guard)
            self.assertIs(original_registry, f.module.device_interfaces)
            self.assertTrue(f.module._device_initialized)
            self.assertEqual(f.originals, [])
            zero_calls = []
            def zero(name):
                def count(): zero_calls.append(name); return 0
                return count
            reference = ModuleType('native_zero_loop_reference')
            vars(reference).update(vars(f.module))
            reference.device_interfaces = {}; reference._device_initialized = False
            reference.torch = SimpleNamespace(device=f.torch.device,
                **{name: SimpleNamespace(device_count=zero(name)) for name in ('cuda', 'xpu', 'mtia')})
            exec(f.code, vars(reference))
            reference.init_device_reg()
            self.assertEqual(zero_calls, ['cuda', 'xpu', 'mtia'])
            self.assertEqual(list(reference.device_interfaces.items()), list(f.module.device_interfaces.items()))
            # Same deduplication operation as the native generic stream decorator.
            collect = lambda module, name: list(dict.fromkeys(getattr(cls, name) for _, cls in module.get_registered_device_interfaces()))
            for name in ('stream', 'current_stream', 'Event'):
                self.assertEqual(collect(reference, name), collect(f.module, name))
            controller.require_intact()
            for name, cls in controller.classes.items():
                self.assertIs(f.module.get_interface_for_device(name), cls)
            with self.assertRaises(NotImplementedError): f.module.get_interface_for_device('xpu:0')

    def test_preinitialized_partial_or_replaced_dict_refuses_without_repair(self):
        for kind in ('initialized', 'partial', 'dict_subclass'):
            with fixture() as f:
                if kind == 'initialized': f.module._device_initialized = True
                elif kind == 'partial': f.module.device_interfaces['cuda'] = f.module.CudaInterface
                else: f.module.device_interfaces = type('ForeignDict', (dict,), {})()
                previous = f.module.device_interfaces; entries = list(previous.items())
                with self.assertRaises(guard.AcceleratorAccessBlocked):
                    policy.CpuDeviceRegistryPolicy(f.module, f.torch, f.report, guard)
                self.assertIs(f.module.device_interfaces, previous)
                self.assertEqual(list(previous.items()), entries)
                self.assertEqual(f.originals, [])

    def test_initial_interface_alias_must_capture_existing_trap(self):
        with fixture() as f:
            f.module.XpuInterface.device_count = staticmethod(lambda: 0)
            with self.assertRaises(guard.AcceleratorAccessBlocked): policy.CpuDeviceRegistryPolicy(f.module, f.torch, f.report, guard)
            self.assertEqual(f.module.device_interfaces, {})

    def test_all_captured_query_aliases_still_trap(self):
        for key in ('cuda', 'xpu'):
            for name in ('current_device', 'set_device', 'device_count', 'current_stream', 'synchronize', 'get_device_properties', 'get_raw_stream'):
                with self.subTest(key=key, name=name), fixture() as f:
                    controller = policy.CpuDeviceRegistryPolicy(f.module, f.torch, f.report, guard)
                    with self.assertRaises(guard.AcceleratorAccessBlocked): getattr(controller.classes[key], name)()
                    with self.assertRaises(guard.AcceleratorAccessBlocked): controller.require_intact()
                    self.assertEqual(f.originals, [])

    def test_registry_keys_order_classes_and_dict_identity_are_fixed(self):
        for kind in ('extra', 'ordinal', 'order', 'class', 'dict', 'flag'):
            with fixture() as f:
                controller = policy.CpuDeviceRegistryPolicy(f.module, f.torch, f.report, guard)
                if kind == 'extra': f.module.device_interfaces['other'] = f.module.CpuInterface
                elif kind == 'ordinal': f.module.device_interfaces['xpu:0'] = f.module.XpuInterface
                elif kind == 'order': f.module.device_interfaces['cuda'] = f.module.device_interfaces.pop('cuda')
                elif kind == 'class': f.module.device_interfaces['cpu'] = f.module.XpuInterface
                elif kind == 'dict': f.module.device_interfaces = dict(f.module.device_interfaces)
                else: f.module._device_initialized = False
                with self.assertRaises(guard.AcceleratorAccessBlocked): controller.require_intact()

    def test_native_registration_and_accessor_identities_preserved(self):
        with fixture() as f:
            originals = {name: getattr(f.module, name) for name in policy.FUNCTIONS}
            controller = policy.CpuDeviceRegistryPolicy(f.module, f.torch, f.report, guard)
            for name, value in originals.items(): self.assertIs(getattr(f.module, name), value)
            f.module.get_registered_device_interfaces = lambda: []
            with self.assertRaises(guard.AcceleratorAccessBlocked): controller.require_intact()

    def test_function_code_mutation_refuses(self):
        with fixture() as f:
            controller = policy.CpuDeviceRegistryPolicy(f.module, f.torch, f.report, guard)
            def changed(): return None
            f.module.init_device_reg.__code__ = changed.__code__
            with self.assertRaises(guard.AcceleratorAccessBlocked): controller.require_intact()

    def test_class_or_handler_binding_mutation_refuses(self):
        for kind in ('class', 'handler', 'raw'):
            with fixture() as f:
                controller = policy.CpuDeviceRegistryPolicy(f.module, f.torch, f.report, guard)
                if kind == 'class': f.module.CpuInterface = type('CpuInterface', (), {})
                elif kind == 'handler': f.module.CpuInterface.stream = staticmethod(lambda: None)
                else: f.module.get_xpu_stream = lambda: None
                with self.assertRaises(guard.AcceleratorAccessBlocked): controller.require_intact()

    def test_no_reinstallation(self):
        with fixture() as f:
            policy.CpuDeviceRegistryPolicy(f.module, f.torch, f.report, guard)
            with self.assertRaises(guard.AcceleratorAccessBlocked): policy.CpuDeviceRegistryPolicy(f.module, f.torch, f.report, guard)

    def test_original_handler_code_with_populated_cache_refuses(self):
        for size in (0, 1):
            with fixture() as f:
                module = ModuleType('torch._dynamo.variables.torch')
                original = FunctionType(policy.source_code(policy.HANDLER_SOURCE,
                    'TorchInGraphFunctionVariable._get_handlers'), {})
                wrapper = SimpleNamespace(__wrapped__=original,
                    cache_info=lambda: SimpleNamespace(_asdict=lambda: {'hits': 0, 'misses': size, 'maxsize': None, 'currsize': size}))
                module.TorchInGraphFunctionVariable = SimpleNamespace(_get_handlers=wrapper)
                sys.modules[module.__name__] = module
                if size:
                    with self.assertRaises(guard.AcceleratorAccessBlocked):
                        policy.CpuDeviceRegistryPolicy(f.module, f.torch, f.report, guard)
                    self.assertEqual(f.module.device_interfaces, {})
                else:
                    controller = policy.CpuDeviceRegistryPolicy(f.module, f.torch, f.report, guard)
                    controller.require_intact()
                    self.assertEqual(f.report['cpu_device_registry_policy']['before']['handler_cache']['currsize'], 0)

    def test_handler_cache_admission_rejects_foreign_constructor(self):
        with fixture() as f:
            module = ModuleType('torch._dynamo.variables.torch')
            module.TorchInGraphFunctionVariable = SimpleNamespace(_get_handlers=lambda: {})
            sys.modules[module.__name__] = module
            with self.assertRaises(guard.AcceleratorAccessBlocked): policy.CpuDeviceRegistryPolicy(f.module, f.torch, f.report, guard)
            self.assertEqual(f.module.device_interfaces, {})


class SourceContracts(unittest.TestCase):
    def test_source_pins_and_no_device_query_in_policy_constructor(self):
        policy.source_gate()
        tree = ast.parse((HERE / 'cpu_device_registry_policy_v7.py').read_text())
        calls = [ast.unparse(node.func) for node in ast.walk(tree) if isinstance(node, ast.Call)]
        self.assertFalse(any(name.endswith(('.device_count', '.init_device_reg', '.stream', '.current_stream')) for name in calls))
        self.assertIn("self.functions['register_interface_for_device']", calls)

    def test_frozen_parent_and_numeric_functions_unchanged(self):
        self.assertEqual(harness.sha(HERE / 'test_block_cpu_guarded_v6.py'), '18fc3b783c0b78749b14d0fe5d81f5c54534550385b166b3c4234a17f1255aa6')
        self.assertEqual(harness.sha(HERE / 'cpu_triton_policy_v6.py'), '6feb786c72e07a611abb3c339087b09465074f832ab169d739c20ec883302dfd')
        trees = [ast.parse((HERE / name).read_text()) for name in ('test_block_cpu_guarded_v6.py', 'test_block_cpu_guarded_v7.py')]
        for name in ('sha', 'require', 'no_fault', 'source_gate', 'emitted_census'):
            functions = [next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name) for tree in trees]
            self.assertEqual(ast.dump(functions[0]), ast.dump(functions[1]))

    def test_installed_once_before_kitchen_and_compiler(self):
        source = (HERE / 'test_block_cpu_guarded_v7.py').read_text()
        points = ['guard.install(torch, report)', 'policy.install(torch, report, guard)',
                  'triton_policy_module.CpuTritonPolicy(', 'registry_module.CpuDeviceRegistryPolicy(',
                  '        import comfy.ops', '        compiled =']
        self.assertEqual([source.index(x) for x in points], sorted(source.index(x) for x in points))
        self.assertEqual(source.count('registry_module.CpuDeviceRegistryPolicy('), 1)
        self.assertEqual(source.count('registry_policy.require_intact()'), 4)

    def test_finalizer_cannot_pass_late_registry_mutation(self):
        tree = ast.parse((HERE / 'test_block_cpu_guarded_v7.py').read_text())
        main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
        final = next(n for n in main.body if isinstance(n, ast.Try)).finalbody[0]
        code = compile(ast.Module(body=[final], type_ignores=[]), '<v7-actual-finalizer>', 'exec')
        with fixture() as f:
            controller = policy.CpuDeviceRegistryPolicy(f.module, f.torch, f.report, guard)
            f.report['passed'] = True; f.module.device_interfaces['xpu:0'] = f.module.XpuInterface
            exec(code, {'registry_policy': controller, 'report': f.report})
            self.assertFalse(f.report['passed'])
            self.assertFalse(f.report['cpu_device_registry_finalizer_intact'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink(): raise FileExistsError(args.output)
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(cls)
        for cls in (old.PolicyContracts, old.SourceContracts, RegistryContracts, SourceContracts))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    native = [name for name in sys.modules if name.split('.')[0] in ('torch', 'triton', 'comfy_kitchen')]
    receipt = {'passed': result.wasSuccessful() and not native, 'tests': result.testsRun,
        'failures': len(result.failures), 'errors': len(result.errors), 'native_modules': native,
        'scope': 'Focused v7 registry plus v6 policy stdlib/fake/source tests; no native module/model/device execution',
        'source_sha256s': {str(p): harness.sha(p) for p in (Path(__file__), HERE / 'cpu_device_registry_policy_v7.py', HERE / 'test_block_cpu_guarded_v7.py', HERE / 'test_block_cpu_guarded_v6.py')}}
    with args.output.open('x') as output: json.dump(receipt, output, indent=2); output.write('\n')
    raise SystemExit(not receipt['passed'])
