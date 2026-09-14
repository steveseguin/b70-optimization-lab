#!/usr/bin/env python3
"""Stdlib-only successor import-order and frozen fixture regression checks."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

LANE = Path(__file__).resolve().parents[1]
DRIVER = LANE / 'scripts/test-host-embedding-candidate-cpu-v3.py'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


driver = load('host_cpu_guarded_driver_v3', DRIVER)
previous = load('host_cpu_guarded_stdlib_v2', LANE / 'scripts/test-host-embedding-cpu-v2-stdlib.py')
# Run the same five guard behavior/source checks against the successor driver.
previous.driver = driver
previous.DRIVER = DRIVER


class Tests(previous.Tests):
    def test_comfy_import_policy_order_and_completion(self):
        text = DRIVER.read_text()
        ordered = ['guard.install(torch, report)',
                   'import_controller = comfy_import_policy.ComfyImportPolicy',
                   'cpu_intact = policy.install(torch, report, guard)',
                   "report['phase'] = comfy_import_policy.EXPECTED_PHASE",
                   "fixture = load('guarded_host_embedding_actual_fixture'",
                   "import_controller.finish_import(sys.modules['comfy.model_management'])",
                   'imports_complete = True']
        positions = [text.index(value) for value in ordered]
        self.assertEqual(positions, sorted(positions))
        self.assertIn('import_controller.require_intact(require_complete=imports_complete)', text)
        self.assertIn("model_management_source=SOURCE / 'comfy/model_management.py'", text)

    def test_previous_refusals_and_fixture_unchanged(self):
        def functions(path):
            return {node.name: ast.dump(node) for node in ast.parse(path.read_text()).body
                    if isinstance(node, ast.FunctionDef)}
        old = functions(LANE / 'scripts/test-host-embedding-candidate-cpu-v2.py')
        new = functions(DRIVER)
        self.assertEqual(old['install_backend_refusals'], new['install_backend_refusals'])
        self.assertEqual(driver.HELPERS['scripts/ltx_host_embedding_candidate.py'],
                         'b58bf0bbfc084ea89f2673f3c10d9520b5f6ac1993517c79e346ea2c573ca7e9')
        self.assertEqual(driver.HELPERS['scripts/test-host-embedding-candidate-cpu-fixture-v2.py'],
                         'b1295210e04c20069bded9972bdbb29ee65589410c57dc81a410956ae7e63a32')
        self.assertNotIn('torch', sys.modules)


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    print(json.dumps({'status': 'passed' if result.wasSuccessful() else 'failed', 'tests': result.testsRun,
        'driver_sha256': hashlib.sha256(DRIVER.read_bytes()).hexdigest(),
        'test_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'torch_imported': 'torch' in sys.modules, 'native_cpu_tests_executed': False,
        'scope': 'Frozen refusal tests plus successor import-order/fixture source checks; stdlib only'}, sort_keys=True))
    raise SystemExit(0 if result.wasSuccessful() else 1)
