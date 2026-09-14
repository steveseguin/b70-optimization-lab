#!/usr/bin/env python3
"""Stdlib naming and exact-source gates; never import or run the campaign client."""
import argparse
import ast
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import unittest

SCRIPTS = Path(__file__).resolve().parent
ORIGINAL_SHA = '51376640d128bfeac5bb6e76e40ce2d7bdb44a610e9e649f9aef9a0dcfc069e6'
OLD = ast.parse((SCRIPTS / 'run-compiler-screen.py').read_text())
NEW = ast.parse((SCRIPTS / 'run-compiler-screen-v2.py').read_text())
old_functions = {node.name: node for node in OLD.body if isinstance(node, ast.FunctionDef)}
new_functions = {node.name: node for node in NEW.body if isinstance(node, ast.FunctionDef)}
functions = {name: copy.deepcopy(new_functions[name]) for name in ('campaign_name', 'schedule', 'parse_args')}
namespace = {'argparse': argparse, 'Path': Path, 're': re, '__doc__': __doc__}
exec(compile(ast.Module(body=list(functions.values()), type_ignores=[]), '<naming-only AST>', 'exec'), namespace)
CLI = ['--campaign', 'compiler-screen-02',
       '--packet', '/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-compiler-03',
       '--manifest-sha256', '9ecd5f9863289e00a934c1f4f400582092f37d0ee92035512fc095773ad02980',
       '--server-run', '/mnt/fast-ai/bench-results/ltx25-baseline-20260913/encoder-server-compiler-03']


class OldNames(ast.NodeTransformer):
    def visit_Name(self, node):
        if node.id == 'campaign':
            node.id = 'CAMPAIGN'
        return node

    def visit_Call(self, node):
        self.generic_visit(node)
        if isinstance(node.func, ast.Name) and node.func.id == 'schedule':
            node.args = []
        return node


class NamingTests(unittest.TestCase):
    def test_frozen_source_and_helper_pins(self):
        hashes = {'run-compiler-screen.py': ORIGINAL_SHA,
                  'run-encoder-screen.py': '4ec94d7e69c3d93b2caa740209f6a84ff35d56bdbbb8bf55f4b9782bacde10b0',
                  'compare-clip.py': '80ee7a45468f95c6c0b8df9ecceea338af9fdf4d2537ba5966603b4f5b03fe0e',
                  'profile-clip.py': 'ad0141ff493c8c4cc5993ff4f8c2aceea76c2e99359477c7cef2d24628eb1980',
                  'run-stability.py': '7769cf87ed005be6e13dc6acced399f1541f68bc988953e7a409ba7fb80937b2'}
        for name, expected in hashes.items():
            with self.subTest(name=name):
                self.assertEqual(hashlib.sha256((SCRIPTS / name).read_bytes()).hexdigest(), expected)

    def test_all_required_arguments_and_no_default_campaign(self):
        for index in range(0, len(CLI), 2):
            with self.subTest(missing=CLI[index]), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    namespace['parse_args'](CLI[:index] + CLI[index + 2:])
                self.assertEqual(error.exception.code, 2)

    def test_safe_campaign_names(self):
        for name in ('', '../old', '/old', 'a/b', 'Upper', '-leading', 'trail\n', 'x' * 65):
            with self.subTest(name=name), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    namespace['parse_args'](['--campaign', name] + CLI[2:])
                with self.assertRaises(argparse.ArgumentTypeError):
                    namespace['schedule'](name)

    def test_fresh_names_preserve_nine_request_schedule(self):
        args = namespace['parse_args'](CLI)
        self.assertEqual(args.campaign, 'compiler-screen-02')
        rows = namespace['schedule'](args.campaign)
        old_ns = {'CAMPAIGN': 'compiler-screen-01'}
        exec(compile(ast.Module(body=[copy.deepcopy(old_functions['schedule'])], type_ignores=[]),
                     '<old schedule AST>', 'exec'), old_ns)
        expected = old_ns['schedule']()
        self.assertEqual(len(rows), 9)
        self.assertEqual(len({row['run'] for row in rows}), 9)
        for current, prior in zip(rows, expected):
            self.assertEqual(current['run'], prior['run'].replace('compiler-screen-01-', 'compiler-screen-02-', 1))
            self.assertEqual({k: v for k, v in current.items() if k != 'run'},
                             {k: v for k, v in prior.items() if k != 'run'})

    def test_all_non_naming_ast_is_unchanged(self):
        # Reverse only the declared naming/CLI transformations. Every remaining
        # statement, including quality, identity, retention and failure gates,
        # must then equal the frozen client AST exactly.
        old = copy.deepcopy(OLD)
        new = copy.deepcopy(NEW)
        old.body = [node for node in old.body if not (isinstance(node, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == 'CAMPAIGN' for t in node.targets))]
        new.body = [node for node in new.body if not (
                    isinstance(node, ast.Import) and [item.name for item in node.names] == ['re'])
                    and not (isinstance(node, ast.FunctionDef) and node.name in ('campaign_name', 'parse_args'))]
        for node in new.body:
            if not isinstance(node, ast.FunctionDef):
                continue
            if node.name == 'schedule':
                node.args.args = []
                node.body = node.body[1:]
            if node.name == 'run_campaign':
                node.body = node.body[1:]
            if node.name == 'main':
                node.body = copy.deepcopy(old_functions['main'].body[:5]) + node.body[1:]
            if node.name in ('schedule', 'run_campaign'):
                OldNames().visit(node)
        self.assertEqual(ast.dump(new), ast.dump(old))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    log = io.StringIO()
    result = unittest.TextTestRunner(stream=log, verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(NamingTests))
    names = ('run-compiler-screen.py', 'run-compiler-screen-v2.py', 'test-compiler-screen-v2.py',
             'run-encoder-screen.py', 'compare-clip.py', 'profile-clip.py', 'run-stability.py')
    parsed = vars(namespace['parse_args'](CLI))
    receipt = {'schema': 'ltx25.compiler-client-naming-cpu.v1',
               'status': 'passed' if result.wasSuccessful() else 'failed',
               'tests_run': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
               'source_sha256': {name: hashlib.sha256((SCRIPTS / name).read_bytes()).hexdigest() for name in names},
               'parsed_cli': {key: str(value) if isinstance(value, Path) else value for key, value in parsed.items()},
               'schedule': namespace['schedule'](parsed['campaign']), 'transcript': log.getvalue(),
               'client_imported_or_executed': False, 'torch_imported': 'torch' in sys.modules,
               'native_or_gpu_execution': False, 'runtime_qualification': False, 'python': sys.version}
    with args.output.open('x') as stream:
        json.dump(receipt, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write('\n')
    print(log.getvalue(), end='')
    print(json.dumps({'status': receipt['status'], 'parsed_cli': receipt['parsed_cli']}))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
