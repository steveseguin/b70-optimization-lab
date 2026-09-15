"""Inactive startup-only Kitchen eager routing for invocation-local axis masks.

Import is stdlib-only. install() is explicit and must precede serving. No custom
op registration, backend override, installed-file edit, or cross-call mask cache.
"""
import ast
from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import importlib
import math
from pathlib import Path
import re
import threading

ORIGINAL_SHA = '4f1d82fe02af995d395969667f6cfd8d10635c3144eec8ca78fe37c103803995'
CANDIDATE_SHA = 'd2907c1ee764fbb344db08851e19a67f0fd2144256d5451f0d15a9382dc08b6a'
FUNCTIONS = ('_window_bounds', '_pick_tiles', '_group_mask', 'na3d')


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _candidate(path, torch):
    require(digest(path) == CANDIDATE_SHA, 'Axis candidate source changed')
    tree = ast.parse(Path(path).read_text())
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in FUNCTIONS]
    require(len(functions) == 4 and {n.name for n in functions} == set(FUNCTIONS) and
            all(not n.decorator_list for n in functions), 'Unexpected extracted functions')
    constants = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name in ('NA_SCORE_BUDGET', 'NA_KV_STACK_BUDGET'):
                constants[name] = eval(compile(ast.Expression(node.value), '<pinned-budget>', 'eval'),
                                       {'__builtins__': {}})
    require(constants == {'NA_SCORE_BUDGET': 2**25, 'NA_KV_STACK_BUDGET': 2**28}, 'NA budgets changed')
    namespace = {'torch': torch, 'functional': torch.nn.functional, 'math': math, **constants}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(path), 'exec'), namespace)
    return namespace['na3d']


class AxisRouter:
    def __init__(self, eager, source, registry, candidate):
        require(registry._backends.get('eager') is eager and eager.na3d is source.na3d,
                'Eager module/callable owner differs or router already installed')
        self.eager, self.source, self.registry = eager, source, registry
        self.original, self.candidate = source.na3d, candidate
        self._expected_candidate = candidate
        self._mode = ContextVar('ltx_na_axis_route_' + str(id(self)), default=None)
        self._baseline = self._registry_state()
        self.wrapper = self._dispatch
        # The sole routing mutation; never repeat this assignment per request.
        eager.na3d = self.wrapper

    def _registry_state(self):
        registry = self.registry
        return {'modules': {k: id(v) for k, v in registry._backends.items()},
                'priority': tuple(registry._priority), 'disabled': frozenset(registry._disabled),
                'unavailable': dict(registry._unavailable),
                'capabilities': {k: frozenset(v) for k, v in registry._capabilities.items()},
                'constraints': {k: (id(v), repr(v)) for k, v in registry._constraints.items()},
                'other_eager_operations': {name: id(getattr(self.eager, name))
                    for name in registry._capabilities.get('eager', ()) if name != 'na3d'}}

    def validate(self):
        require(self.registry._backends.get('eager') is self.eager and self.eager.na3d is self.wrapper and
                self.source.na3d is self.original and self.candidate is self._expected_candidate,
                'NA router ownership changed')
        require(self._registry_state() == self._baseline, 'Kitchen registry/other operations changed')

    def _dispatch(self, q, k, v, kernel_size, is_causal=None, scale=None):
        current = self._mode.get()
        if current is None:
            return self.original(q, k, v, kernel_size, is_causal, scale)
        require(current['thread_id'] == threading.get_ident(), 'Decode scope crossed worker threads')
        require(len(current['calls']) < 256, 'Decode exceeded bounded NA receipt count')
        row = {'index': len(current['calls']), 'mode': current['mode'], 'status': 'started',
               'inputs': [{'shape': list(x.shape), 'dtype': str(x.dtype), 'device': str(x.device)} for x in (q, k, v)],
               'kernel_size': list(kernel_size), 'is_causal': None if is_causal is None else list(is_causal),
               'scale': scale}
        current['calls'].append(row)
        function = self.candidate if current['mode'] == 'axis-cache' else self.original
        out = function(q, k, v, kernel_size, is_causal, scale)
        row.update(status='completed', output={'shape': list(out.shape), 'dtype': str(out.dtype), 'device': str(out.device)})
        return out

    @contextmanager
    def scope(self, mode, run_name, *, expected_calls=None):
        require(mode in ('original', 'axis-cache'), 'Unknown NA route mode')
        require(isinstance(run_name, str) and re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,127}', run_name),
                'Unsafe NA receipt run name')
        require(expected_calls is None or type(expected_calls) is int and 1 <= expected_calls <= 256,
                'Invalid expected NA call count')
        self.validate()
        receipt = {'schema': 'ltx.na-axis-route.v1', 'status': 'running', 'mode': mode, 'run_name': run_name,
                   'thread_id': threading.get_ident(), 'original_sha256': ORIGINAL_SHA,
                   'candidate_sha256': CANDIDATE_SHA, 'calls': []}
        token = self._mode.set(receipt)
        try:
            yield receipt
            self.validate()
            require(receipt['calls'] and all(row['status'] == 'completed' for row in receipt['calls']),
                    'No complete eager NA coverage; candidate selection is unqualified')
            require(expected_calls is None or len(receipt['calls']) == expected_calls,
                    'Unexpected eager NA call count')
            receipt['status'] = 'passed-route-coverage'
        except BaseException as error:
            receipt.update(status='failed', error=repr(error))
            raise
        finally:
            self._mode.reset(token)
            receipt['scope_reset'] = True


def install(candidate_path):
    """Install once in this process; caller owns startup identity and lifetime."""
    import torch
    eager = importlib.import_module('comfy_kitchen.backends.eager')
    source = importlib.import_module('comfy_kitchen.backends.eager.na')
    registry = importlib.import_module('comfy_kitchen.registry').registry
    require(digest(source.__file__) == ORIGINAL_SHA, 'Installed eager NA source changed')
    candidate = _candidate(candidate_path, torch)
    return AxisRouter(eager, source, registry, candidate)
