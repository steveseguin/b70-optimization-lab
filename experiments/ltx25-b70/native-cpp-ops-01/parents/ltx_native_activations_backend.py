"""Inactive block-local native RMS/sigmoid/tanh-GELU compiler hypothesis.

The pinned RMS implementation is reused unchanged. Graph structures are copied;
original graph nodes, parameters, module forwards and global decompositions are
not modified. Native XPU block parity and speed remain unqualified.
"""
import hashlib
import importlib.util
import json
from pathlib import Path

RMS_BACKEND_SHA256 = '09defae7340dc3d7f33e16ab80c76f22b6a2ae733617704f2e7b69086108d9fb'
_RMS_PATH = Path(__file__).resolve().with_name('ltx_native_rms_backend.py')
_SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
_rms_spec = importlib.util.find_spec('ltx_native_rms_backend')
if (_rms_spec is None or _rms_spec.origin is None
        or Path(_rms_spec.origin).resolve() != _RMS_PATH
        or hashlib.sha256(_RMS_PATH.read_bytes()).hexdigest() != RMS_BACKEND_SHA256):
    raise RuntimeError('Pinned native RMS dependency changed or resolves elsewhere')

import ltx_native_rms_backend as rms
import torch
import torch.nn.functional as F

_ORIGINAL_SIGMOID = torch.sigmoid
_ORIGINAL_GELU = F.gelu


def _layout(input):
    if (input.dtype not in (torch.bfloat16, torch.float32) or not input.is_contiguous()
            or any(type(size) is not int or size < 0 for size in input.shape)):
        raise RuntimeError('Native activations require static contiguous BF16/F32 input')


def _check_result(input, result):
    strides, stride = [], 1
    for size in reversed(input.shape):
        strides.insert(0, stride)
        stride *= max(size, 1)
    if (result.shape != input.shape or result.dtype != input.dtype or result.device != input.device
            or result.stride() != tuple(strides)):
        raise RuntimeError('Native activation result violates the reviewed fake layout')
    return result


@torch.library.custom_op('ltx_exact_activations::sigmoid', mutates_args=())
def native_sigmoid(input: torch.Tensor) -> torch.Tensor:
    _layout(input)
    return _check_result(input, _ORIGINAL_SIGMOID(input))


@native_sigmoid.register_fake
def _fake_native_sigmoid(input):
    _layout(input)
    return torch.empty(input.shape, dtype=input.dtype, device=input.device)


@torch.library.custom_op('ltx_exact_activations::gelu', mutates_args=())
def native_gelu(input: torch.Tensor, approximate: str) -> torch.Tensor:
    _layout(input)
    if approximate != 'tanh':
        raise RuntimeError('Only explicit tanh GELU is supported')
    return _check_result(input, _ORIGINAL_GELU(input, approximate=approximate))


@native_gelu.register_fake
def _fake_native_gelu(input, approximate):
    _layout(input)
    if approximate != 'tanh':
        raise RuntimeError('Only explicit tanh GELU is supported')
    return torch.empty(input.shape, dtype=input.dtype, device=input.device)


def _activation_arguments(node, kind):
    # These match the captured torch.sigmoid and keyword-only tanh GELU calls.
    allowed = {'input'} if kind == 'sigmoid' else {'input', 'approximate'}
    if len(node.args) > 1 or set(node.kwargs) - allowed:
        raise RuntimeError('Unknown native activation signature: ' + kind)
    values = {'input': node.args[0]} if node.args else {}
    if set(values) & set(node.kwargs):
        raise RuntimeError('Duplicate native activation argument: ' + kind)
    values.update(node.kwargs)
    if not isinstance(values.get('input'), torch.fx.Node):
        raise RuntimeError('Native activation input must be a graph value')
    if kind == 'gelu' and values.get('approximate') != 'tanh':
        raise RuntimeError('Only explicit tanh GELU is supported')
    return values['input']


def _counts(expected):
    result = {'sigmoid': 6, 'gelu': 2} if expected is None else dict(expected)
    if (set(result) != {'sigmoid', 'gelu'}
            or any(type(value) is not int or value < 0 for value in result.values())
            or not sum(result.values())):
        raise RuntimeError('Explicit nonnegative sigmoid/GELU counts are required')
    return result


def rewrite_activations(gm, *, expected_activation_counts=None):
    """Copy a graph (normally RMS-rewritten) without copying registered weights."""
    expected = _counts(expected_activation_counts)
    graph, environment, census = torch.fx.Graph(), {}, []
    targets = {torch.sigmoid: 'sigmoid', F.gelu: 'gelu', torch._C._nn.gelu: 'gelu'}
    for old in gm.graph.nodes:
        new = graph.node_copy(old, lambda node: environment[node])
        new.meta = dict(old.meta)
        environment[old] = new
        if old.op == 'call_function' and old.target in targets:
            kind = targets[old.target]
            input = _activation_arguments(new, kind)
            metadata = rms._metadata(input)
            if metadata is not None:
                example = input.meta.get('example_value')
                _layout(example)
            census.append({'node': old.name, 'kind': kind, 'original_target': str(old.target),
                           'input': metadata, **({'approximate': 'tanh'} if kind == 'gelu' else {})})
            new.target = (torch.ops.ltx_exact_activations.sigmoid.default if kind == 'sigmoid'
                          else torch.ops.ltx_exact_activations.gelu.default)
            new.args = (input,) if kind == 'sigmoid' else (input, 'tanh')
            new.kwargs = {}
        elif old.op in ('call_function', 'call_method') and any(
                token in str(old.target).lower() for token in ('sigmoid', 'gelu')):
            raise RuntimeError('Unrecognized or already rewritten activation target: ' + str(old.target))
    observed = {kind: sum(row['kind'] == kind for row in census) for kind in expected}
    if observed != expected:
        raise RuntimeError(f'Unexpected activation replacement counts: {observed} expected {expected}')
    result = torch.fx.GraphModule(gm, graph)
    result.graph.lint()
    result.recompile()
    return result, census


def _source_identity():
    if (Path(rms.__file__).resolve() != _RMS_PATH
            or hashlib.sha256(_RMS_PATH.read_bytes()).hexdigest() != RMS_BACKEND_SHA256
            or hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != _SOURCE_SHA256):
        raise RuntimeError('Native activation backend/dependency source changed after import')


def make_backend(options, directory, *, expected_count=15, expected_activation_counts=None):
    """Bind original Inductor options and explicit expected graph replacement counts."""
    _source_identity()
    if type(expected_count) is not int or expected_count <= 0:
        raise RuntimeError('Explicit positive RMS replacement count required')
    expected_activations = _counts(expected_activation_counts)
    options = dict(options)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    count = 0

    def backend(gm, example_inputs, **kwargs):
        nonlocal count
        count += 1
        report = {'schema': 'ltx25.native-activations-fx-rewrite.v1', 'status': 'started',
                  'graph': count, 'torch': str(torch.__version__), 'options': dict(options),
                  'source_sha256': _SOURCE_SHA256, 'dependency_sha256': RMS_BACKEND_SHA256,
                  'expected_count': expected_count, 'expected_activation_counts': dict(expected_activations)}
        try:
            _source_identity()
            if kwargs:
                raise RuntimeError('Backend options must be explicitly bound at construction')
            if torch.is_grad_enabled():
                raise RuntimeError('Native activation backend is inference only')
            with (directory / f'graph-{count:03d}-before.py').open('x') as stream:
                stream.write(gm.code)
            rms_graph, rms_census = rms.rewrite_rms(gm, expected_count=expected_count)
            report['replacements'] = rms_census
            rewritten, activation_census = rewrite_activations(
                rms_graph, expected_activation_counts=expected_activations)
            report['activation_replacements'] = activation_census
            with (directory / f'graph-{count:03d}-after.py').open('x') as stream:
                stream.write(rewritten.code)
            result = torch._inductor.compile(rewritten, example_inputs, options=dict(options))
            report['status'] = 'compiled-native-activations-boundary'
            return result
        except BaseException as error:
            report.update(status='failed', error=repr(error))
            raise
        finally:
            with (directory / f'graph-{count:03d}.json').open('x') as stream:
                json.dump(report, stream, indent=2)
                stream.write('\n')

    return backend
