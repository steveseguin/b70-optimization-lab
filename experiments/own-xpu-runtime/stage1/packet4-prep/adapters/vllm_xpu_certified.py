"""Source-bound, eager-only comparator observations, never an inference runtime.

The historical filename is NOT certification of the reopen image. See names.json.
Install before model construction so CustomOp cannot cache unobserved methods.
No vLLM import occurs here; the admitted worker passes already resolved owners.
"""
from __future__ import annotations

import ast
from contextlib import contextmanager, ExitStack
from contextvars import ContextVar
from functools import wraps
import inspect
import json
from pathlib import Path

from common import file_hash
from extract_fixtures import refuse_capture, forbid_graph_entrypoints

MANIFEST = Path(__file__).with_name('names.json')
_GUARDED = ContextVar('packet4_eager_guard', default=False)


@contextmanager
def eager_guard(config, torch_module, graph_wrapper_class):
    """Enter before model construction; stay active through cooperative teardown.

    The caller resolves the hash-verified vLLM CUDAGraphWrapper. Torch module
    attributes are inspected only: no availability checks or device queries.
    Patching capture_begin on the class also blocks previously bound contexts.
    Worker must reject pre-existing captured graphs and cached callable aliases.
    """
    refuse_capture(config)
    targets = [(graph_wrapper_class, '__call__')]
    for backend, graph_class in (('xpu', 'XPUGraph'), ('cuda', 'CUDAGraph')):
        api = getattr(torch_module, backend, None)
        if api is None:
            continue
        for name in ('graph',):
            if hasattr(api, name):
                targets.append((api, name))
        cls = getattr(api, graph_class, None)
        if cls is not None:
            targets.append((cls, 'capture_begin'))
    if len(targets) == 1:
        raise ValueError('no torch capture entry points bound')
    with forbid_graph_entrypoints(targets):
        token = _GUARDED.set(True)
        try:
            yield
        finally:
            _GUARDED.reset(token)



def load_manifest(path=MANIFEST):
    value = json.loads(Path(path).read_text())
    if value['schema'] != 'own-xpu-runtime.packet4.names.v1':
        raise ValueError('unknown names manifest')
    ids = [row['id'] for row in value['symbols']]
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate symbol identity')
    return value


def source_symbol(row, roots):
    """Hash/AST validation only; never imports or evaluates comparator source."""
    root = Path(roots[row['source_id']]).resolve()
    relative = Path(row['file'])
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('unsafe source path')
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or file_hash(path) != row['sha256']:
        raise ValueError('source hash mismatch: ' + row['id'])
    tree = ast.parse(path.read_text())
    scope = tree
    if row['class']:
        scope = next((n for n in tree.body if isinstance(n, ast.ClassDef)
                      and n.name == row['class']), None)
    if scope is None:
        raise ValueError('class missing: ' + row['id'])
    candidates = [n for n in ast.walk(scope) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                  and n.name == row['method'] and n.lineno == row['line']]
    if len(candidates) != 1:
        raise ValueError('method/line missing: ' + row['id'])
    fn = candidates[0]
    args = {n.arg for n in fn.args.posonlyargs + fn.args.args + fn.args.kwonlyargs}
    for selector in row['inputs'] + row['outputs'] + row.get('state', []):
        if selector == 'result' or selector.startswith('result.'):
            continue
        pieces = selector.split('.')
        if pieces[0] != 'arg' or len(pieces) < 2 or pieces[1] not in args:
            raise ValueError('selector is not a boundary argument: ' + selector)
        # self/layer attributes must actually occur in this source file. Do not
        # pretend a local intermediate is an argument or a reachable attribute.
        if len(pieces) > 2 and not pieces[2].isdigit():
            attributes = {ast.unparse(n) for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
            if '.'.join(pieces[1:3]) not in attributes:
                raise ValueError('attribute missing in source: ' + selector)
    return fn


def verify_sources(manifest, roots):
    counts = {f'U{i}': 0 for i in range(1, 8)}
    for row in manifest['symbols']:
        source_symbol(row, roots)
        for u in row['u_rows']:
            counts[u] += 1
    return counts


def select(selector, bound, result=None):
    parts = selector.split('.')
    if parts[0] == 'result':
        value, parts = result, parts[1:]
    elif parts[0] == 'arg':
        value, parts = bound[parts[1]], parts[2:]
    else:
        raise ValueError('unknown tensor selector')
    for part in parts:
        if part.isdigit():
            value = value[int(part)]
        elif isinstance(value, dict):
            value = value[part]
        else:
            value = getattr(value, part)
    return value


def tensors(row, key, bound, result=None):
    return {name: select(name, bound, result) for name in row.get(key, [])}


def check_dtypes(values, expectations):
    """Metadata only. Never cast comparator values to make a check pass."""
    from common import NAMES
    import torch
    def leaves(value):
        if isinstance(value, torch.Tensor):
            yield value
        elif isinstance(value, (tuple, list)):
            for v in value:
                yield from leaves(v)
        elif isinstance(value, dict):
            for v in value.values():
                yield from leaves(v)
    for selector, allowed in expectations.items():
        if selector in values:
            for tensor in leaves(values[selector]):
                if NAMES.get(tensor.dtype) not in allowed:
                    raise ValueError('dtype mismatch: ' + selector)


def make_spec(row, metadata):
    """Scheduling metadata must come from the worker's CPU request metadata.

    Returning None admits no fixture for that call. No inferred/fabricated row
    count, positions, rank, padding mask, layer, or projection dimensions.
    """
    if metadata is None:
        return None
    required = ('M', 'N', 'K', 'layer', 'rank', 'positions', 'valid_rows')
    if any(k not in metadata for k in required):
        raise ValueError('incomplete CPU dispatch metadata')
    if type(metadata['M']) is not int or metadata['M'] not in (1, 2, 6):
        raise ValueError('unadmitted actual M')
    for key in ('positions', 'valid_rows'):
        if type(metadata[key]) is not list or len(metadata[key]) != metadata['M']:
            raise ValueError('CPU row metadata required')
    if any(type(x) is not int for x in metadata['positions']):
        raise ValueError('positions must already be CPU integers')
    if any(type(x) is not bool for x in metadata['valid_rows']):
        raise ValueError('valid_rows must already be CPU booleans')
    return dict(metadata, rows=list(range(metadata['M'])), name=row['operator'],
                location=row['id'], census_items=row['u_rows'],
                arithmetic_order='unchanged original ' + row['module'] + '.' + row['method'],
                rounding_points=[row['rounding']], reference=None, expected={})


@contextmanager
def bind(recorder, row, owner, metadata, state_views, *, verified_path):
    """Observe a concrete class method/module function exactly once.

    metadata(row,bound) supplies CPU scheduling data. state_views(row,bound)
    MUST return bounded views of touched state, selected from CPU scheduler
    indices, never device .item()/tolist() or a whole cache pool. A stateful
    symbol refuses if this contract is absent. The window driver owns it.
    """
    refuse_capture(recorder.config)
    if not _GUARDED.get():
        raise ValueError('eager_guard must surround hook lifetime')
    name = row.get('runtime_attribute', row['method'])
    original = getattr(owner, name)
    original_descriptor = inspect.getattr_static(owner, name)
    if not row.get('runtime_owner'):
        source_path = inspect.getsourcefile(original)
        if source_path is None or Path(source_path).resolve() != Path(verified_path).resolve():
            raise ValueError('loaded callable differs from validated source')
        if file_hash(source_path) != row['sha256']:
            raise ValueError('loaded source bytes changed')
        function = inspect.unwrap(original)
        expected = (row['class'] + '.' if row['class'] else '') + row['method']
        if function.__qualname__ != expected or function.__module__ != row['module']:
            raise ValueError('loaded callable symbol mismatch')
        tree = ast.parse(Path(source_path).read_text())
        fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                  and n.lineno == row['line'] and n.name == row['method'])
        first = min([fn.lineno] + [d.lineno for d in fn.decorator_list])
        if function.__code__.co_firstlineno != first:
            raise ValueError('loaded callable code location mismatch')
    else:
        if row['runtime_owner'] != 'torch.ops.vllm':
            raise ValueError('unsupported registered operator alias')
        schema = original.default._schema
        if schema.name != 'vllm::' + name or [a.name for a in schema.arguments] != row['arguments']:
            raise ValueError('registered operator schema mismatch')
    if isinstance(original_descriptor, classmethod):
        raise ValueError('classmethod observation not supported')
    # torch operator schemas and decorated methods can lose Python signatures.
    signature = inspect.signature(original) if not row.get('runtime_owner') else None
    if row.get('requires_state_views') and state_views is None:
        raise ValueError('bounded touched-state binding missing: ' + row['id'])

    @wraps(original)
    def observed(*args, **kwargs):
        refuse_capture(recorder.config)  # BEFORE metadata, selectors or host I/O
        if not _GUARDED.get():
            raise ValueError('hook invoked outside guarded eager lifetime')
        if signature is not None:
            bound = signature.bind(*args, **kwargs)
            bound.apply_defaults()
            values = bound.arguments
        else:
            names = row['arguments']
            if len(args) > len(names) or any(k not in names for k in kwargs):
                raise ValueError('registered operator argument mismatch')
            values = dict(zip(names, args))
            if values.keys() & kwargs.keys():
                raise ValueError('duplicate operator arguments')
            values.update(kwargs)
            if set(values) != set(names):
                raise ValueError('incomplete registered operator arguments')
        spec = make_spec(row, metadata(row, values))
        if spec is None:
            return original(*args, **kwargs)
        ins = tensors(row, 'inputs', values)
        check_dtypes(ins, row.get('dtypes', {}))
        def states():
            result = tensors(row, 'state', values)
            if row.get('requires_state_views'):
                extra = state_views(row, values)
                if not isinstance(extra, dict) or not extra:
                    raise ValueError('missing touched state views')
                result.update(extra)
            return result
        def outputs(result):
            out = tensors(row, 'outputs', values, result)
            check_dtypes(out, row.get('dtypes', {}))
            return out
        return recorder.observe(original, args, kwargs, spec,
                                lambda: ((), ins), outputs, states)
    replacement = staticmethod(observed) if isinstance(original_descriptor, staticmethod) else observed
    setattr(owner, name, replacement)
    try:
        yield
    finally:
        setattr(owner, name, original_descriptor)


@contextmanager
def install(recorder, *, source_id, roots, owners, metadata, state_views=None,
            symbol_ids=None, manifest=None):
    """Install an explicitly selected, source-verified census before construction.

    owners maps exact manifest module/class keys to already resolved objects.
    No fallback name guessing or vLLM imports. Selected symbol misses refuse.
    An explicit subset is diagnostic; it never becomes a complete census.
    """
    manifest = manifest or load_manifest()
    refuse_capture(recorder.config)
    rows = [r for r in manifest['symbols'] if r['source_id'] == source_id]
    if symbol_ids is not None:
        requested = set(symbol_ids)
        rows = [r for r in rows if r['id'] in requested]
        if {r['id'] for r in rows} != requested:
            raise ValueError('unknown symbol selection')
    if not rows:
        raise ValueError('empty hook selection')
    # Validate everything before installing even the first hook.
    for row in rows:
        source_symbol(row, roots)
        owner_key = row.get('runtime_owner') or row['module'] + ('.' + row['class'] if row['class'] else '')
        if owner_key not in owners:
            raise ValueError('unresolved source-bound owner: ' + owner_key)
    with ExitStack() as stack:
        for row in rows:
            key = row.get('runtime_owner') or row['module'] + ('.' + row['class'] if row['class'] else '')
            stack.enter_context(bind(recorder, row, owners[key], metadata, state_views,
                                     verified_path=Path(roots[source_id]) / row['file']))
        yield


def run(args, Recorder):
    """extract_fixtures --driver protocol; refuse an unbound native window.

    The CPU source adapter deliberately cannot construct a model or launch a
    server. A reviewed in-process worker driver calls install() with its actual
    scheduler/state bindings. Do not replace this refusal with synthetic data.
    """
    raise RuntimeError('native session driver missing: bind actual CPU scheduler positions, '
                       'touched cache/state views, graph-entry guards before construction, '
                       'per-rank recorders, token collection and cooperative teardown; '
                       'see WINDOW-RUNBOOK.md. No model was constructed.')
