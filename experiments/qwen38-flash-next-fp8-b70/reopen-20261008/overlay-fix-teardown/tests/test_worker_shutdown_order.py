"""Execute copied worker shutdown methods with entirely fake runtime globals.

AST extraction retains the actual method bodies and class-bound super(); no
vLLM, Torch, GPU module, Docker process, or allocator is imported or created.
"""
import ast
import copy
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

WORKERS = (Path(__file__).resolve().parents[1] / 'copies' / 'overlay' / 'vllm'
           / 'v1' / 'worker')


def shutdown_class(filename, name, base):
    source = ast.parse((WORKERS / filename).read_text())
    source_name = 'Worker' if name == 'GPUWorker' else name
    original = next(n for n in source.body if isinstance(n, ast.ClassDef) and n.name == source_name)
    method = copy.deepcopy(next(n for n in original.body
                                if isinstance(n, ast.FunctionDef) and n.name == 'shutdown'))
    return ast.ClassDef(name=name, bases=[ast.Name(id=base, ctx=ast.Load())],
                        keywords=[], body=[method], decorator_list=[])


def fake_module(name, **fields):
    module = ModuleType(name)
    vars(module).update(fields)
    return module


class WorkerShutdownOrderTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.failure = None
        self.guard_enabled = True

        def record(name):
            self.events.append(name)
            if self.failure == name:
                raise RuntimeError('fake failure: ' + name)

        self.record = record
        self.guard = SimpleNamespace(enabled=lambda: self.guard_enabled)
        self.config = object()
        self.pool_allocator = SimpleNamespace(instance=SimpleNamespace(
            release_pools=lambda: record('xpu_pools')))

        def release_runner(runner, guard, torch, free_before_shutdown):
            self.assertIs(guard, self.guard)
            record('fallback_release_start')
            free_before_shutdown()
            record('fallback_release_done')

        def free_before_shutdown(config):
            self.assertIs(config, self.config)
            record('free_before_shutdown')

        modules = {
            'vllm': fake_module('vllm', screen1b_guard=self.guard),
            'vllm.screen1b_teardown': fake_module('vllm.screen1b_teardown', release_runner=release_runner),
            'vllm.v1.worker.gpu.shutdown': fake_module('vllm.v1.worker.gpu.shutdown',
                                                     free_before_shutdown=free_before_shutdown),
            'vllm.device_allocator.xpumem': fake_module('vllm.device_allocator.xpumem',
                                                        XpuMemAllocator=self.pool_allocator),
        }
        patcher = patch.dict(sys.modules, modules)
        patcher.start()
        self.addCleanup(patcher.stop)
        namespace = {
            'gc': SimpleNamespace(unfreeze=lambda: record('gc_unfreeze')),
            'ensure_kv_transfer_shutdown': lambda: record('kv_service'),
            'ensure_ec_transfer_shutdown': lambda: record('ec_service'),
            'torch': SimpleNamespace(xpu=SimpleNamespace(synchronize=lambda: record('xpu_sync'))),
            'current_platform': SimpleNamespace(is_cuda_alike=lambda: False),
            'logger': SimpleNamespace(info=lambda *args, **kwargs: None),
        }
        module_ast = ast.Module(body=[shutdown_class('gpu_worker.py', 'GPUWorker', 'object'),
                                     shutdown_class('xpu_worker.py', 'XPUWorker', 'GPUWorker')],
                                type_ignores=[])
        exec(compile(ast.fix_missing_locations(module_ast), '<copied-worker-shutdowns>', 'exec'), namespace)
        self.worker = namespace['XPUWorker']()
        self.worker.rank = 0
        self.worker.local_rank = 0
        self.worker.vllm_config = self.config
        self.namespace = namespace

    def full_worker(self):
        for attr, event in [('profiler', 'profiler'), ('weight_transfer_engine', 'weight_service'),
                            ('elastic_ep_executor', 'elastic_service'), ('model_runner', 'runner_release')]:
            setattr(self.worker, attr, SimpleNamespace(shutdown=lambda event=event: self.record(event)))

    def test_services_runner_then_sync_and_xpu_pools(self):
        self.full_worker()
        self.worker.shutdown()
        self.assertEqual(self.events, ['gc_unfreeze', 'kv_service', 'ec_service', 'profiler',
                                       'weight_service', 'elastic_service', 'runner_release',
                                       'xpu_sync', 'xpu_pools'])
        self.assertIsNone(self.worker.model_runner)

    def test_no_runner_fallback_releases_globals_before_xpu_pools(self):
        self.worker.model_runner = None
        self.worker.shutdown()
        self.assertEqual(self.events, ['gc_unfreeze', 'kv_service', 'ec_service',
                                       'fallback_release_start', 'free_before_shutdown',
                                       'fallback_release_done', 'xpu_sync', 'xpu_pools'])

    def test_missing_optional_partial_initialization_attributes_are_safe(self):
        self.assertFalse(hasattr(self.worker, 'model_runner'))
        self.namespace['ensure_kv_transfer_shutdown'] = None
        self.namespace['ensure_ec_transfer_shutdown'] = None
        self.worker.shutdown()
        self.assertEqual(self.events, ['gc_unfreeze', 'fallback_release_start',
                                       'free_before_shutdown', 'fallback_release_done',
                                       'xpu_sync', 'xpu_pools'])

    def test_service_failure_preserves_runner_and_pools(self):
        self.full_worker()
        self.failure = 'weight_service'
        with self.assertRaisesRegex(RuntimeError, 'weight_service'):
            self.worker.shutdown()
            self.record('complete')
        self.assertIsNotNone(self.worker.model_runner)
        self.assertNotIn('runner_release', self.events)
        self.assertNotIn('xpu_pools', self.events)
        self.assertNotIn('complete', self.events)

    def test_runner_failure_preserves_pools_and_cannot_complete(self):
        self.full_worker()
        self.failure = 'runner_release'
        with self.assertRaisesRegex(RuntimeError, 'runner_release'):
            self.worker.shutdown()
            self.record('complete')
        self.assertIsNotNone(self.worker.model_runner)
        self.assertNotIn('xpu_sync', self.events)
        self.assertNotIn('xpu_pools', self.events)
        self.assertNotIn('complete', self.events)

    def test_partial_global_release_failure_preserves_pools(self):
        self.failure = 'free_before_shutdown'
        with self.assertRaisesRegex(RuntimeError, 'free_before_shutdown'):
            self.worker.shutdown()
            self.record('complete')
        self.assertNotIn('fallback_release_done', self.events)
        self.assertNotIn('xpu_pools', self.events)
        self.assertNotIn('complete', self.events)

    def test_post_runner_sync_failure_preserves_pools(self):
        self.full_worker()
        self.failure = 'xpu_sync'
        with self.assertRaisesRegex(RuntimeError, 'xpu_sync'):
            self.worker.shutdown()
            self.record('complete')
        self.assertIn('runner_release', self.events)
        self.assertNotIn('xpu_pools', self.events)
        self.assertNotIn('complete', self.events)

    def test_absent_xpu_allocator_instance_is_safe(self):
        self.full_worker()
        self.pool_allocator.instance = None
        self.worker.shutdown()
        self.assertEqual(self.events[-2:], ['runner_release', 'xpu_sync'])
        self.assertNotIn('xpu_pools', self.events)


if __name__ == '__main__':
    unittest.main()
