#!/usr/bin/env python3
"""Offline driver/refusal regression checks. Does not import Torch."""
import ast
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

LANE = Path(__file__).resolve().parents[1]
DRIVER = LANE / 'scripts/test-host-embedding-candidate-cpu-v2.py'
spec = importlib.util.spec_from_file_location('host_cpu_guarded_driver', DRIVER)
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)
guard = driver.load('host_cpu_frozen_guard', LANE / 'native-cpp-block-01/accelerator_guard_v2.py')


class Tests(unittest.TestCase):
    def test_actual_source_pins_without_native_import(self):
        self.assertEqual(len(driver.source_gate()), 4)
        self.assertNotIn('torch', sys.modules)

    def test_all_backend_calls_refused_and_sticky(self):
        for target in ('backend', 'compile'):
            calls = []
            original = lambda *args, **kwargs: calls.append('original')
            torch = SimpleNamespace(compile=original)
            utils = SimpleNamespace(triton_backend=original)
            report = {'phase': 'stdlib-fake'}
            intact = driver.install_backend_refusals(torch, utils, report, guard)
            call = utils.triton_backend if target == 'backend' else torch.compile
            with self.assertRaises(guard.AcceleratorAccessBlocked):
                try:
                    call(object(), cpu_only=True)
                except Exception:
                    self.fail('BaseException refusal was swallowed')
            self.assertEqual(calls, [])
            self.assertTrue(report['backend_refusals']['tripped'])
            with self.assertRaises(guard.AcceleratorAccessBlocked):
                intact()
            with self.assertRaises(guard.AcceleratorAccessBlocked):
                driver.install_backend_refusals(torch, utils, report, guard)

    def test_refusal_identity_change_detected(self):
        for target in ('backend', 'compile'):
            torch, utils = SimpleNamespace(compile=lambda: None), SimpleNamespace(triton_backend=lambda: None)
            intact = driver.install_backend_refusals(torch, utils, {}, guard)
            if target == 'backend':
                utils.triton_backend = lambda: None
            else:
                torch.compile = lambda: None
            with self.assertRaises(RuntimeError):
                intact()

    def test_startup_order_and_complete_final_gate(self):
        text = DRIVER.read_text()
        ordering = ["write_exclusive(directory / 'startup-identity.json', startup)",
                    'import torch as imported_torch', 'guard.install(torch, report)',
                    'cpu_intact = policy.install(torch, report, guard)',
                    'backend_intact = install_backend_refusals(torch, triton_utils, report, guard)',
                    "fixture = load('guarded_host_embedding_actual_fixture'"]
        positions = [text.index(value) for value in ordering]
        self.assertEqual(positions, sorted(positions))
        tree = ast.parse(text)
        main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'main')
        final = next(node for node in main.body if isinstance(node, ast.Try)).finalbody
        self.assertIsInstance(final[-1], ast.If)
        self.assertEqual(ast.literal_eval(final[-1].body[0].value), 1)
        self.assertNotIn('torch.compile(', text)

    def test_first_failure_stops_suite(self):
        calls = []
        class Broken(unittest.TestCase):
            def test_a(self):
                calls.append('first')
                raise guard.AcceleratorAccessBlocked('fixture')
            def test_b(self):
                calls.append('forbidden continuation')
        result = unittest.TextTestRunner(stream=io.StringIO(),
            resultclass=driver.StopOnFailureResult).run(unittest.defaultTestLoader.loadTestsFromTestCase(Broken))
        self.assertEqual(result.testsRun, 1)
        self.assertEqual(calls, ['first'])
        self.assertFalse(result.wasSuccessful())


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    print(json.dumps({'status': 'passed' if result.wasSuccessful() else 'failed', 'tests': result.testsRun,
        'driver_sha256': hashlib.sha256(DRIVER.read_bytes()).hexdigest(),
        'test_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'torch_imported': 'torch' in sys.modules, 'native_cpu_tests_executed': False,
        'scope': 'Actual source pins/AST plus stdlib fake refusal behavior only'}, sort_keys=True))
    raise SystemExit(0 if result.wasSuccessful() else 1)
