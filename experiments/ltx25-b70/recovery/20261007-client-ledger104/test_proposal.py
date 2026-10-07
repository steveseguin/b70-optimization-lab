#!/usr/bin/env python3
"""CPU-only controls with fake storage and durability; no real client constructed."""
import ast
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

import proposal as P


def require(ok, why):
    if not ok:
        raise ValueError(why)


def function(raw, name):
    tree = ast.parse(raw)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Client')
    method = next(n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)
    if name != 'checkpoint':
        return method
    scope = {'G': SimpleNamespace(require=require), 'WRITE_ALLOWANCE': 1000, 'MIN_FREE': 1000}
    exec(compile(ast.Module(body=[method], type_ignores=[]), '<isolated-checkpoint>', 'exec'), scope)
    return scope[name]


class Fake:
    def __init__(self, readings, check_error=None, save_error=None):
        self.root = 'synthetic-no-filesystem'
        self.state = {'charged_write_bytes': 0, 'last_available_bytes': 3000,
                      'attempts': [], 'prompt_ids': [], 'completed': [], 'halted': None}
        self.durable = copy.deepcopy(self.state)
        self.readings = iter(readings)
        self.events = []
        self.save_error = save_error
        self.check_error = check_error
        self.saved = []

    def check_fixed(self):
        self.events.append('check_fixed')
        if self.check_error:
            raise self.check_error

    def free_probe(self, root):
        assert root == self.root
        self.events.append('free_probe')
        value = next(self.readings)
        if isinstance(value, BaseException):
            raise value
        return value

    def save_state(self):
        self.events.append('save_state')
        if self.save_error:
            raise self.save_error
        self.durable = copy.deepcopy(self.state)
        self.saved.append(copy.deepcopy(self.state))


class ProposalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = P.SOURCE.read_bytes()
        cls.changed = P.transform(cls.original)
        cls.old = staticmethod(function(cls.original, 'checkpoint'))
        cls.new = staticmethod(function(cls.changed, 'checkpoint'))

    def test_source_pin_and_exclusive_function_change(self):
        with self.assertRaisesRegex(ValueError, 'exact sealed103'):
            P.transform(self.original + b'\n')
        for name in ('check_fixed', 'execute', 'save_state', 'acquire', 'release', 'phase_observation'):
            self.assertEqual(ast.dump(function(self.original, name)), ast.dump(function(self.changed, name)))

    def test_unchanged_fields_keep_all_checks_but_no_write(self):
        f = Fake([3000]*3)
        for _ in range(3): self.new(f)
        self.assertEqual(f.events, ['check_fixed', 'free_probe']*3)
        self.assertEqual(f.state, f.durable)
        self.assertEqual(f.saved, [])

    def test_decrease_charges_and_persists_increase_persists_without_refund(self):
        f = Fake([2900, 3100, 3100, 3050])
        for _ in range(4): self.new(f)
        self.assertEqual(len(f.saved), 3)
        self.assertEqual([s['charged_write_bytes'] for s in f.saved], [100,100,150])
        self.assertEqual(f.state, f.durable)
        self.assertEqual(f.state['last_available_bytes'], 3050)

    def test_zero_free_invalid_bool_and_float_still_refused(self):
        for value in (-1, True, 3000., None, 0):
            f = Fake([value])
            with self.assertRaises(ValueError): self.new(f)
            self.assertEqual(f.saved, [])
            self.assertEqual(f.events[:2], ['check_fixed', 'free_probe'])

    def test_source_fault_or_pid_failure_precedes_free_probe_even_when_unchanged(self):
        for reason in ('source changed', 'fault latched', 'PID reused'):
            f = Fake([3000], check_error=ValueError(reason))
            with self.assertRaisesRegex(ValueError, reason): self.new(f)
            self.assertEqual(f.events, ['check_fixed'])

    def test_free_probe_and_persistence_errors_propagate(self):
        f = Fake([OSError('free probe failed')])
        with self.assertRaisesRegex(OSError, 'free probe failed'): self.new(f)
        self.assertEqual(f.saved, [])
        f = Fake([2999], save_error=OSError('fsync failed'))
        with self.assertRaisesRegex(OSError, 'fsync failed'): self.new(f)
        self.assertEqual(f.state['charged_write_bytes'], 1)

    def test_unchanged_budget_violation_cannot_skip_limit_check(self):
        f = Fake([3000]); f.state['charged_write_bytes'] = 1001
        with self.assertRaisesRegex(ValueError, 'allowance exhausted'): self.new(f)
        self.assertEqual(f.saved, [])

    def test_storage_traces_match_old_state_at_every_success(self):
        traces = [[3000]*100, list(range(3000,2900,-1)),
                  [3000-(i//8)*4 for i in range(100)], [3000,3010,3000,3010]*20]
        for trace in traces:
            a, b = Fake(trace), Fake(trace)
            for _ in trace:
                self.old(a); self.new(b)
                self.assertEqual(a.state, b.state)
                self.assertEqual(b.state, b.durable)
            self.assertEqual(a.events.count('check_fixed'), b.events.count('check_fixed'))
            self.assertEqual(a.events.count('free_probe'), b.events.count('free_probe'))

    def test_all_nonstorage_state_mutations_remain_explicitly_saved(self):
        method = function(self.changed, 'execute')
        found = []
        def contains_mutation(node):
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                call = node.value
                if isinstance(call.func, ast.Attribute) and call.func.attr == 'append':
                    target = call.func.value
                    if isinstance(target, ast.Subscript) and ast.unparse(target.value) == 'self.state':
                        return target.slice.value
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Subscript) and ast.unparse(target.value) == 'self.state':
                        return target.slice.value
            return None
        for parent in ast.walk(method):
            for _, value in ast.iter_fields(parent):
                if isinstance(value, list):
                    for i, node in enumerate(value):
                        if not isinstance(node, ast.AST): continue
                        key = contains_mutation(node)
                        if key:
                            self.assertEqual(ast.unparse(value[i+1]), 'self.save_state()')
                            found.append(key)
        self.assertEqual(sorted(found), ['attempts','completed','halted','prompt_ids'])
        # Event durability remains literal file flush plus real fsync; unchanged AST above
        # also covers all submission/terminal failure handling around this code.
        text = ast.unparse(method)
        self.assertIn('log.flush()', text)
        self.assertIn('os.fsync(log.fileno())', text)


if __name__ == '__main__': unittest.main(verbosity=2)
