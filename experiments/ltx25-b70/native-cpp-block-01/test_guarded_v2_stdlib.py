#!/usr/bin/env python3
"""Fake-module and source-only contracts; no Torch/Kitchen/Inductor imports."""
import argparse
import ast
import copy
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
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


guard = load('tested_accelerator_guard_v2', HERE / 'accelerator_guard_v2.py')
harness = load('tested_cpu_guarded_harness_v2', HERE / 'test_block_cpu_guarded_v2.py')


def fake_torch():
    calls = []
    def original(*args, **kwargs):
        calls.append((args, kwargs))
        return 'ORIGINAL MUST NOT RUN'
    names = ('init', '_lazy_init', 'device_count', 'get_device_properties', 'get_device_capability',
             'get_device_name', 'current_device', 'current_stream', 'set_device', 'synchronize')
    native = ('_cuda_init', '_cuda_getDeviceCount', '_cuda_getDevice', '_cuda_setDevice',
              '_cuda_getCurrentRawStream', '_xpu_init', '_xpu_getDeviceCount', '_xpu_getDevice',
              '_xpu_getDeviceProperties', '_xpu_setDevice', '_xpu_getCurrentRawStream')
    device = lambda: SimpleNamespace(is_initialized=lambda: False, **{name: original for name in names})
    return SimpleNamespace(cuda=device(), xpu=device(), _C=SimpleNamespace(**{name: original for name in native})), calls


class GuardContracts(unittest.TestCase):
    def test_all_installed_entries_block_originals(self):
        sample, _ = fake_torch(); report = {}; guard.install(sample, report)
        self.assertEqual(len(report['accelerator_guard_entries']), 31)
        for label in report['accelerator_guard_entries']:
            with self.subTest(label=label):
                fake, calls = fake_torch(); current = {'phase': 'synthetic-admission'}; guard.install(fake, current)
                target = fake
                for name in label.split('.')[1:]:
                    target = getattr(target, name)
                with self.assertRaises(guard.AcceleratorAccessBlocked):
                    target(7, device='xpu:3')
                self.assertEqual(calls, [])
                self.assertTrue(current['accelerator_guard_tripped'])
                event = current['accelerator_guard_attempts'][0]
                self.assertEqual(event['entry'], label)
                self.assertEqual(event['pid'], os.getpid())
                self.assertEqual(event['phase'], 'synthetic-admission')
                self.assertEqual(event['argument_types'], ['int'])
                self.assertEqual(event['keyword_names'], ['device'])
                self.assertTrue(event['stack'])
                self.assertLessEqual(len(event['stack']), 40)

    def test_exception_not_swallowed_by_ordinary_exception_handler(self):
        fake, calls = fake_torch(); report = {}; guard.install(fake, report)
        with self.assertRaises(guard.AcceleratorAccessBlocked):
            try:
                fake.xpu._lazy_init()
            except Exception:
                self.fail('Guard must bypass ordinary cache exception handling')
        self.assertEqual(calls, [])

    def test_swallowed_baseexception_still_sticky(self):
        fake, _ = fake_torch(); report = {}; guard.install(fake, report)
        try:
            fake.xpu.current_stream()
        except BaseException:
            pass
        with self.assertRaises(guard.AcceleratorAccessBlocked):
            guard.require_clean(report)
        report['accelerator_guard_attempts'].clear()
        with self.assertRaises(guard.AcceleratorAccessBlocked):
            guard.require_clean(report)

    def test_attempt_list_alone_also_halts(self):
        with self.assertRaises(guard.AcceleratorAccessBlocked):
            guard.require_clean({'accelerator_guard_attempts': [{'entry': 'synthetic'}]})

    def test_clean_report_and_install_allowed(self):
        guard.require_clean({})
        fake, calls = fake_torch(); report = {}; guard.install(fake, report); guard.require_clean(report)
        self.assertEqual(calls, [])
        self.assertFalse(fake.xpu.is_initialized())

    def test_install_cannot_reset_sticky_failure(self):
        fake, _ = fake_torch()
        with self.assertRaises(guard.AcceleratorAccessBlocked):
            guard.install(fake, {'accelerator_guard_tripped': True})

    def test_already_initialized_is_rejected(self):
        for device in ('cuda', 'xpu'):
            with self.subTest(device=device):
                fake, calls = fake_torch(); getattr(fake, device).is_initialized = lambda: True
                with self.assertRaises(guard.AcceleratorAccessBlocked):
                    guard.install(fake, {})
                self.assertEqual(calls, [])


class StartupContracts(unittest.TestCase):
    def report(self):
        return {'command': ['test', '--synthetic'], 'helper_sha256s': {'test.py': 'a' * 64},
                'source_pins': {'model.py': 'b' * 64}, 'fixture_parent_sha256': 'c' * 64,
                'operator_qualification_sha256': 'd' * 64, 'options': {'compile_threads': 1},
                'compiler_environment': {'MAX_JOBS': '1'}}

    def test_exclusive_startup_pid_identity_and_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory); report = self.report()
            with patch.object(harness.os, 'fsync', wraps=os.fsync) as sync:
                saved = harness.persist_startup(path, report)
                self.assertEqual(sync.call_count, 1)
            actual = json.loads((path / 'startup-identity.json').read_text())
            self.assertEqual(saved, actual)
            self.assertEqual(actual['pid'], os.getpid())
            self.assertEqual(actual['ppid'], os.getppid())
            self.assertFalse(actual['torch_imported'])
            self.assertEqual(actual['helper_sha256s'], report['helper_sha256s'])
            self.assertEqual(actual['source_pins'], report['source_pins'])
            self.assertEqual(report['startup_receipt']['sha256'], harness.sha(path / 'startup-identity.json'))
            with self.assertRaises(FileExistsError):
                harness.persist_startup(path, self.report())
            self.assertEqual(saved, json.loads((path / 'startup-identity.json').read_text()))

    def test_startup_refuses_after_torch_import(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(sys.modules, {'torch': SimpleNamespace()}):
            with self.assertRaises(RuntimeError):
                harness.persist_startup(Path(directory), self.report())
            self.assertFalse((Path(directory) / 'startup-identity.json').exists())

    def test_startup_cannot_follow_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); target = root / 'target'; target.write_text('untouched')
            (root / 'startup-identity.json').symlink_to(target)
            with self.assertRaises(FileExistsError):
                harness.persist_startup(root, self.report())
            self.assertEqual(target.read_text(), 'untouched')


class SourceContracts(unittest.TestCase):
    def test_prior_sources_still_frozen(self):
        pins = {'accelerator_guard.py': '5f6a1a05ef98955bf4f4934a818626b3d7671d8aec4de48f7207dc9812656ad6',
                'test_block_cpu_guarded.py': '83e03c31578b333f581babd22ca67da95637851f4bafe86997ae983e34ad6da1'}
        for name, digest in pins.items():
            self.assertEqual(harness.sha(HERE / name), digest)

    def test_startup_precedes_torch_and_guard_precedes_kitchen(self):
        source = (HERE / 'test_block_cpu_guarded_v2.py').read_text()
        self.assertLess(source.index('persist_startup(args.evidence_dir, report)'), source.index('        import torch'))
        self.assertLess(source.index('        guard.install(torch, report)'), source.index('        import comfy.ops'))
        self.assertLess(source.index('        guard.install(torch, report)'), source.index('        from torch._dynamo.utils import counters'))

    def test_whole_harness_ast_reverses_only_intended_changes(self):
        before = ast.parse((HERE / 'test_block_cpu_guarded.py').read_text())
        after = ast.parse((HERE / 'test_block_cpu_guarded_v2.py').read_text())
        class Undo(ast.NodeTransformer):
            def visit_ImportFrom(self, node):
                return None if node.module == 'datetime' else node
            def visit_FunctionDef(self, node):
                return None if node.name == 'persist_startup' else self.generic_visit(node)
            def visit_Expr(self, node):
                value = node.value
                if isinstance(value, ast.Call) and ast.unparse(value.func) in ('persist_startup', 'guard.require_clean'):
                    return None
                return self.generic_visit(node)
            def visit_If(self, node):
                if ast.unparse(node.test) == "report.get('accelerator_guard_tripped') or report.get('accelerator_guard_attempts')":
                    return None
                return self.generic_visit(node)
            def visit_Constant(self, node):
                changes = {'Inactive guarded diagnostic v2: durable startup identity and sticky accelerator halt.':
                           'Inactive guarded diagnostic successor: stop at any accelerator entry before initialization.',
                           'accelerator_guard_v2.py': 'accelerator_guard.py',
                           'private_cpu_accelerator_guard_v2': 'private_cpu_accelerator_guard'}
                if isinstance(node.value, str) and node.value in changes:
                    node.value = changes[node.value]
                return node
        self.assertEqual(ast.dump(before), ast.dump(Undo().visit(after)))

    def test_finalizer_cannot_keep_a_pass_after_trap(self):
        module = ast.parse((HERE / 'test_block_cpu_guarded_v2.py').read_text())
        main = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
        final = next(n for n in main.body if isinstance(n, ast.Try)).finalbody[0]
        code = compile(ast.Module(body=[final], type_ignores=[]), '<actual-finalizer-check>', 'exec')
        for report in ({'passed': True, 'accelerator_guard_tripped': True},
                       {'passed': True, 'accelerator_guard_attempts': [{'entry': 'fake'}]}):
            exec(code, {'report': report})
            self.assertFalse(report['passed'])
            self.assertIn('halted', report['error'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        raise FileExistsError(args.output)
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(cls)
                               for cls in (GuardContracts, StartupContracts, SourceContracts))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    native_modules = [name for name in sys.modules if name == 'torch' or name.startswith(('torch.', 'comfy_kitchen'))]
    receipt = {'passed': result.wasSuccessful() and not native_modules, 'tests': result.testsRun,
               'failures': len(result.failures), 'errors': len(result.errors), 'native_modules': native_modules,
               'scope': 'Stdlib fake modules, AST reversibility, and temporary startup-file contracts only; no native imports/execution',
               'source_sha256s': {p.name: harness.sha(p) for p in (Path(__file__), HERE / 'accelerator_guard_v2.py', HERE / 'test_block_cpu_guarded_v2.py')}}
    with args.output.open('x') as out:
        json.dump(receipt, out, indent=2); out.write('\n')
    raise SystemExit(not receipt['passed'])
