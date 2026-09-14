#!/usr/bin/env python3
"""Stdlib regression checks for the guarded CLIP integration test preparation."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

LANE = Path(__file__).resolve().parents[1]
DRIVER = LANE / 'scripts/test-host-embedding-integration-cpu.py'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


driver = load('host_integration_guarded_driver', DRIVER)
previous = load('host_integration_previous_stdlib', LANE / 'scripts/test-host-embedding-cpu-v3-stdlib.py')
previous.driver = driver
previous.DRIVER = DRIVER
previous.previous.driver = driver
previous.previous.DRIVER = DRIVER


class Tests(previous.Tests):
    def test_actual_source_pins_without_native_import(self):
        self.assertEqual(len(driver.source_gate()), 6)
        self.assertNotIn('torch', sys.modules)

    def test_metadata_hook_is_observational_and_bounded(self):
        tree = ast.parse((LANE / 'scripts/host_embedding_clip_v2.py').read_text())
        group = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'ClipOwnership')
        method = next(node for node in group.body if isinstance(node, ast.FunctionDef) and node.name == 'observe_embedding')
        self.assertFalse(any(isinstance(node, ast.Return) for node in ast.walk(method)))
        calls = [ast.unparse(node.func) for node in ast.walk(method) if isinstance(node, ast.Call)]
        self.assertFalse(any(value.endswith(('.to', '.cpu', '.clone', '.item', '.numpy')) for value in calls))
        self.assertIn('self.embedding_observations.append', calls)
        text = (LANE / 'scripts/host_embedding_clip_v2.py').read_text()
        self.assertIn('self.observation_limit = 4', text)
        self.assertIn('self.embedding_observations.clear()', text)
        node = (LANE / 'scripts/host_embedding_placement_node_v2.py').read_text()
        self.assertIn('group.consume_observations()', node)
        self.assertIn('return (conditioning,)', node)

    def test_actual_fixture_and_native_result_contract(self):
        text = (LANE / 'scripts/test-host-embedding-integration-cpu-fixture.py').read_text()
        tree = ast.parse(text)
        tests = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'Tests')
        names = [node.name for node in tests.body if isinstance(node, ast.FunctionDef) and node.name.startswith('test_')]
        self.assertEqual(len(names), 6)
        self.assertIn('return original_load(models, **kwargs)', text)
        self.assertIn('comfy.sd.CLIP(target=', text)
        self.assertIn('base.raw(actual)', text)
        driver_text = DRIVER.read_text()
        self.assertIn("report['test_names'] = list(fixture.TEST_NAMES)", driver_text)
        self.assertIn('and not result.skipped', driver_text)


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    print(json.dumps({'status': 'passed' if result.wasSuccessful() else 'failed', 'tests': result.testsRun,
        'driver_sha256': hashlib.sha256(DRIVER.read_bytes()).hexdigest(),
        'test_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'torch_imported': 'torch' in sys.modules, 'native_cpu_tests_executed': False,
        'scope': 'Guard/refusal regression plus integration metadata/result source contracts only'}, sort_keys=True))
    raise SystemExit(0 if result.wasSuccessful() else 1)
