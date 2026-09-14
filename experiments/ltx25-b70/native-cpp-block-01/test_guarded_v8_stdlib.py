#!/usr/bin/env python3
"""V8 CPU cache-system source/fake tests; no native imports."""
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


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


v3 = load('v3_fake_contracts_for_v8', HERE / 'test_guarded_v3_stdlib.py')
v7 = load('v7_fake_contracts_for_v8', HERE / 'test_guarded_v7_stdlib.py')
policy = load('v8_fake_policy', HERE / 'cpu_cache_system_policy_v8.py')
harness = load('v8_fake_harness', HERE / 'test_block_cpu_guarded_v8.py')
guard = v3.guard
SOURCE = '''import functools
class CacheBase:
    @staticmethod
    @functools.cache
    def get_system():
        try:
            torch.cuda.current_device()
            raise AssertionError("Hardware query must not return")
        except (AssertionError, RuntimeError):
            return dict(fallback)
class FxGraphHashDetails:
    def __init__(self, gm, example_inputs):
        self.system_info = CacheBase.get_system()
'''


class Tensor:
    def __init__(self, device='cpu'):
        self.device = SimpleNamespace(type=device)
        self.dtype = 'torch.bfloat16'; self.shape = (1, 2)
    def stride(self): return (2, 1)


class Parameter(Tensor):
    pass


class FakeTensor(Tensor):
    pass


class GraphModule:
    def __init__(self, parameters=(), buffers=()):
        self.parameters, self.buffers = parameters, buffers
    def named_parameters(self): return iter(self.parameters)
    def named_buffers(self): return iter(self.buffers)


@contextmanager
def fixture(bind=True):
    with tempfile.TemporaryDirectory() as directory, patch.dict(sys.modules):
        root = Path(directory); path = root / policy.CODECACHE
        path.parent.mkdir(parents=True); path.write_text(SOURCE)
        with patch.object(policy, 'SITE', root), patch.object(policy, 'PINS', {policy.CODECACHE: hashlib.sha256(path.read_bytes()).hexdigest()}):
            torch, report, originals = v3.fixture()
            torch.Tensor = Tensor; torch.nn = SimpleNamespace(Parameter=Parameter); torch.fx = SimpleNamespace(GraphModule=GraphModule)
            report['phase'] = 'python-compile-and-execute'
            control = policy.CpuCacheSystemPolicy(torch, report, guard)
            # Ensure unchanged v3 identity policy captures the new wrapper.
            intact = v3.policy.install(torch, report, guard)
            module = ModuleType('torch._inductor.codecache'); module.__file__ = str(path)
            vars(module).update(torch=torch, FakeTensor=FakeTensor, fallback=policy.EXPECTED_FALLBACK)
            exec(compile(SOURCE, str(path), 'exec', dont_inherit=True), vars(module))
            sys.modules[module.__name__] = module
            if bind: control.bind(module.CacheBase, module.FxGraphHashDetails)
            yield SimpleNamespace(torch=torch, report=report, originals=originals, control=control,
                module=module, intact=intact, graph=GraphModule(), inputs=[Tensor()])


class CacheSystemContracts(unittest.TestCase):
    def test_exact_cpu_frames_native_fallback_cached_once_both_arms(self):
        with fixture() as f:
            f.control.verify_cache()
            first = f.module.FxGraphHashDetails(f.graph, f.inputs)
            self.assertEqual(first.system_info, policy.EXPECTED_FALLBACK)
            f.control.verify_cache(require_ready=True); f.intact()
            f.report['phase'] = 'cpp-compile-and-execute'
            second = f.module.FxGraphHashDetails(f.graph, [FakeTensor(), 1, None, False])
            self.assertIs(first.system_info, second.system_info)
            f.control.verify_cache(require_ready=True)
            info = f.module.CacheBase.get_system.cache_info()
            self.assertEqual((info.misses, info.currsize), (1, 1))
            self.assertEqual(len(f.report['cpu_cache_system_omissions']), 1)
            self.assertEqual(f.report['accelerator_guard_attempts'], [])
            self.assertEqual(f.originals, [])

    def test_parameter_and_buffer_metadata_cpu(self):
        with fixture() as f:
            graph = GraphModule(parameters=[('weight', Parameter())], buffers=[('buffer', Tensor())])
            f.module.FxGraphHashDetails(graph, [FakeTensor()])
            self.assertEqual([x['kind'] for x in f.report['cpu_cache_system_omissions'][0]['graph_state']], ['parameter', 'buffer'])

    def test_unbound_foreign_query_delegates_original_trap(self):
        with fixture(False) as f:
            with self.assertRaises(guard.AcceleratorAccessBlocked): f.torch.cuda.current_device()
            self.assertEqual(f.report['accelerator_guard_attempts'][0]['entry'], 'torch.cuda.current_device')
            self.assertEqual(f.originals, [])

    def test_missing_outer_frame_refuses_even_native_system_caller(self):
        with fixture() as f:
            with self.assertRaises(guard.AcceleratorAccessBlocked): f.module.CacheBase.get_system()
            self.assertEqual(f.report['cpu_cache_system_omissions'], [])

    def test_wrong_phase_refuses(self):
        with fixture() as f:
            f.report['phase'] = 'eager'
            with self.assertRaises(guard.AcceleratorAccessBlocked): f.module.FxGraphHashDetails(f.graph, f.inputs)

    def test_gpu_input_parameter_or_buffer_refuses(self):
        for kind in ('input', 'parameter', 'buffer'):
            with fixture() as f:
                graph = GraphModule(parameters=[('weight', Parameter('xpu'))] if kind == 'parameter' else (),
                    buffers=[('buffer', Tensor('cuda'))] if kind == 'buffer' else ())
                inputs = [Tensor('cuda')] if kind == 'input' else [Tensor()]
                with self.assertRaises(guard.AcceleratorAccessBlocked): f.module.FxGraphHashDetails(graph, inputs)
                self.assertEqual(f.report['cpu_cache_system_omissions'], [])

    def test_empty_opaque_nested_or_unknown_tensor_inputs_refuse(self):
        class UnknownTensor(Tensor): pass
        for inputs in ([], [1, None], [[Tensor()]], [object()], [UnknownTensor()]):
            with fixture() as f:
                with self.assertRaises(guard.AcceleratorAccessBlocked): f.module.FxGraphHashDetails(f.graph, inputs)

    def test_cache_must_be_pristine_at_binding(self):
        with fixture(False) as f:
            # Populate only the fake cache with an ordinary refusal; no hardware.
            current = f.torch.cuda.current_device
            def ordinary(): raise RuntimeError('fake unavailable')
            f.torch.cuda.current_device = ordinary
            f.module.CacheBase.get_system()
            f.torch.cuda.current_device = current
            with self.assertRaises(guard.AcceleratorAccessBlocked): f.control.bind(f.module.CacheBase, f.module.FxGraphHashDetails)

    def test_cache_clear_is_not_repaired_or_retried(self):
        with fixture() as f:
            f.module.FxGraphHashDetails(f.graph, f.inputs)
            f.module.CacheBase.get_system.cache_clear()  # Fake-only negative mutation.
            with self.assertRaises(guard.AcceleratorAccessBlocked): f.control.verify_cache(require_ready=True)
            self.assertEqual(len(f.report['cpu_cache_system_omissions']), 1)

    def test_cached_fallback_mutation_refuses(self):
        with fixture() as f:
            value = f.module.FxGraphHashDetails(f.graph, f.inputs).system_info
            value['hash'] = 'changed'
            with self.assertRaises(guard.AcceleratorAccessBlocked): f.control.verify_cache(require_ready=True)

    def test_late_hook_class_function_or_code_mutation_refuses(self):
        for kind in ('hook', 'class', 'cached', 'code'):
            with fixture() as f:
                if kind == 'hook': f.torch.cuda.current_device = lambda: 0
                elif kind == 'class': f.module.CacheBase = type('Other', (), {})
                elif kind == 'cached': f.module.CacheBase.get_system = staticmethod(lambda: {})
                else:
                    def different(): return None
                    f.control.native.__code__ = different.__code__
                with self.assertRaises(guard.AcceleratorAccessBlocked): f.control.require_intact()

    def test_other_query_arguments_preserved_in_sticky_trap(self):
        with fixture() as f:
            with self.assertRaises(guard.AcceleratorAccessBlocked): f.torch.cuda.current_device(1, synthetic=True)
            event = f.report['accelerator_guard_attempts'][0]
            self.assertEqual(event['argument_types'], ['int']); self.assertEqual(event['keyword_names'], ['synthetic'])


class SourceContracts(unittest.TestCase):
    def test_actual_source_pins_exception_path_and_empty_hash(self):
        policy.source_gate()
        tree = ast.parse((policy.SITE / policy.CODECACHE).read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'CacheBase')
        function = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'get_system')
        handler = next(n for n in ast.walk(function) if isinstance(n, ast.ExceptHandler))
        self.assertEqual(ast.unparse(handler.type), '(AssertionError, RuntimeError)')
        self.assertEqual(ast.unparse(handler.body[0]), "return {'hash': SYSTEM_CACHE_KEY_STRATEGY.key_from_json({})}")
        self.assertEqual(policy.EXPECTED_FALLBACK, {'hash': hashlib.sha256(b'{}').hexdigest()})

    def test_install_before_captured_aliases_bind_before_compile(self):
        source = (HERE / 'test_block_cpu_guarded_v8.py').read_text()
        order = ['guard.install(torch, report)', 'cache_system_module.CpuCacheSystemPolicy(',
                 'policy.install(torch, report, guard)', 'registry_module.CpuDeviceRegistryPolicy(',
                 'cache_system_policy.bind(CacheBase, FxGraphHashDetails)', '        compiled =']
        self.assertEqual([source.index(x) for x in order], sorted(source.index(x) for x in order))
        self.assertEqual(source.count('cache_system_module.CpuCacheSystemPolicy('), 1)
        self.assertIn("require(system_delta == int(arm == 'python' and tokens == 64 and seed == 17)", source)
        self.assertIn("require(len(report['cpu_metadata_omissions']) == 4", source)

    def test_frozen_parent_and_numerical_functions_unchanged(self):
        self.assertEqual(harness.sha(HERE / 'test_block_cpu_guarded_v7.py'), 'ac75b4bffe6449a939fed91ae07b494aec867a858e0615a87e64566549c57da2')
        self.assertEqual(harness.sha(HERE / 'cpu_device_registry_policy_v7.py'), 'f6fe6e2723f9fb71cfe8bc627f7f2df0531d4720ea0ca8b96a854c61b71490a1')
        trees = [ast.parse((HERE / name).read_text()) for name in ('test_block_cpu_guarded_v7.py', 'test_block_cpu_guarded_v8.py')]
        for name in ('sha', 'require', 'no_fault', 'source_gate', 'emitted_census'):
            functions = [next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name) for tree in trees]
            self.assertEqual(ast.dump(functions[0]), ast.dump(functions[1]))

    def test_finalizer_cannot_pass_missing_fallback(self):
        tree = ast.parse((HERE / 'test_block_cpu_guarded_v8.py').read_text())
        main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
        final = next(n for n in main.body if isinstance(n, ast.Try)).finalbody[0]
        code = compile(ast.Module(body=[final], type_ignores=[]), '<v8-actual-finalizer>', 'exec')
        with fixture() as f:
            f.report['passed'] = True
            exec(code, {'cache_system_policy': f.control, 'report': f.report})
            self.assertFalse(f.report['passed']); self.assertFalse(f.report['cpu_cache_system_finalizer_intact'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink(): raise FileExistsError(args.output)
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(cls)
        for cls in (v7.RegistryContracts, v7.SourceContracts, CacheSystemContracts, SourceContracts))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    native = [name for name in sys.modules if name.split('.')[0] in ('torch', 'triton', 'comfy_kitchen')]
    receipt = {'passed': result.wasSuccessful() and not native, 'tests': result.testsRun,
        'failures': len(result.failures), 'errors': len(result.errors), 'native_modules': native,
        'scope': 'Focused v8 cache-system and v7 registry stdlib/fake/source tests; no native modules/model/device execution',
        'source_sha256s': {str(p): harness.sha(p) for p in (Path(__file__), HERE / 'cpu_cache_system_policy_v8.py', HERE / 'test_block_cpu_guarded_v8.py', HERE / 'test_block_cpu_guarded_v7.py')}}
    with args.output.open('x') as output: json.dump(receipt, output, indent=2); output.write('\n')
    raise SystemExit(not receipt['passed'])
