"""Inactive block-local FX rewrite keeping native RMS opaque to Inductor.

No global decomposition edits, module monkey-patches, or parameter copies.
Only static contiguous inference inputs are supported by this first candidate.
"""
import hashlib
import json
from pathlib import Path
from typing import Optional

import torch
import torch.nn.functional as F

_ORIGINAL_RMS = F.rms_norm


def _layout(input, normalized_shape, weight):
    if not input.is_contiguous():
        raise RuntimeError('Native RMS candidate requires contiguous input')
    if (not normalized_shape or any(type(n) is not int or n <= 0 for n in normalized_shape)
            or tuple(input.shape[-len(normalized_shape):]) != tuple(normalized_shape)):
        raise RuntimeError('Native RMS candidate requires a static matching normalization shape')
    if weight is not None and (not weight.is_contiguous() or tuple(weight.shape) != tuple(normalized_shape)
                               or weight.dtype != input.dtype or weight.device != input.device):
        raise RuntimeError('Native RMS candidate requires matching contiguous weight')


@torch.library.custom_op('ltx_exact_rms::native', mutates_args=())
def native_rms(input: torch.Tensor, normalized_shape: list[int],
               weight: Optional[torch.Tensor], eps: Optional[float]) -> torch.Tensor:
    _layout(input, normalized_shape, weight)
    result = _ORIGINAL_RMS(input, normalized_shape, weight, eps)
    if not result.is_contiguous() or result.shape != input.shape or result.dtype != input.dtype:
        raise RuntimeError('Native RMS result violates the reviewed fake layout')
    return result


@native_rms.register_fake
def _fake_native_rms(input, normalized_shape, weight, eps):
    _layout(input, normalized_shape, weight)
    return torch.empty_like(input, memory_format=torch.contiguous_format)


def _metadata(node):
    value = node.meta.get('example_value') if isinstance(node, torch.fx.Node) else node
    if not isinstance(value, torch.Tensor):
        return None
    return {'shape': list(value.shape), 'stride': list(value.stride()), 'dtype': str(value.dtype),
            'device': str(value.device), 'contiguous': value.is_contiguous()}


def _arguments(node):
    names = ('input', 'normalized_shape', 'weight', 'eps')
    if len(node.args) > 4 or set(node.kwargs) - set(names):
        raise RuntimeError('Unknown RMS signature')
    values = dict(zip(names, node.args))
    if set(values) & set(node.kwargs):
        raise RuntimeError('Duplicate RMS argument')
    values.update(node.kwargs)
    if not {'input', 'normalized_shape'} <= set(values):
        raise RuntimeError('Missing RMS input/shape')
    values.setdefault('weight', None)
    values.setdefault('eps', None)
    x, shape, weight, eps = (values[name] for name in names)
    if not isinstance(x, torch.fx.Node) or (weight is not None and not isinstance(weight, torch.fx.Node)):
        raise RuntimeError('RMS input/weight must be graph values')
    if (not isinstance(shape, (tuple, list)) or not shape
            or any(type(n) is not int or n <= 0 for n in shape)):
        raise RuntimeError('Only explicit static RMS shapes are supported')
    if eps is not None and (type(eps) not in (int, float) or eps < 0):
        raise RuntimeError('Unknown RMS epsilon')
    return x, list(shape), weight, eps


def rewrite_rms(gm, *, expected_count=None):
    """Copy the FX graph structure, retaining original attributes/parameters."""
    graph, environment, census = torch.fx.Graph(), {}, []
    targets = {torch.rms_norm, F.rms_norm}
    for old in gm.graph.nodes:
        new = graph.node_copy(old, lambda n: environment[n])
        new.meta = dict(old.meta)
        environment[old] = new
        if old.op == 'call_function' and old.target in targets:
            x, shape, weight, eps = _arguments(new)
            imeta, wmeta = _metadata(x), _metadata(weight)
            if imeta is not None and not imeta['contiguous']:
                raise RuntimeError('Observed noncontiguous RMS input; review before broadening')
            if wmeta is not None and not wmeta['contiguous']:
                raise RuntimeError('Observed noncontiguous RMS weight; review before broadening')
            census.append({'node': old.name, 'original_target': str(old.target),
                           'normalized_shape': shape, 'eps': eps, 'weighted': weight is not None,
                           'input': imeta, 'weight': wmeta})
            new.target = torch.ops.ltx_exact_rms.native.default
            new.args = (x, shape, weight, eps)
            new.kwargs = {}
        elif old.op in ('call_function', 'call_method') and 'rms_norm' in str(old.target):
            raise RuntimeError('Unrecognized or already decomposed RMS target: ' + str(old.target))
    if not census or (expected_count is not None and len(census) != expected_count):
        raise RuntimeError(f'Unexpected RMS replacement count: {len(census)} expected {expected_count}')
    result = torch.fx.GraphModule(gm, graph)
    result.graph.lint()
    result.recompile()
    return result, census


def make_backend(options, directory, *, expected_count=None):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    count = 0

    def backend(gm, example_inputs, **kwargs):
        nonlocal count
        if kwargs:
            raise RuntimeError('Backend options must be explicitly bound at construction')
        if torch.is_grad_enabled():
            raise RuntimeError('Native RMS backend is inference only')
        count += 1
        report = {'schema': 'ltx25.native-rms-fx-rewrite.v1', 'status': 'started', 'graph': count,
                  'torch': str(torch.__version__), 'options': dict(options),
                  'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
        try:
            rewritten, census = rewrite_rms(gm, expected_count=expected_count)
            report['replacements'] = census
            (directory / f'graph-{count:03d}-before.py').write_text(gm.code)
            (directory / f'graph-{count:03d}-after.py').write_text(rewritten.code)
            result = torch._inductor.compile(rewritten, example_inputs, options=dict(options))
            report['status'] = 'compiled-native-rms-boundary'
            return result
        except BaseException as error:
            report.update(status='failed', error=repr(error))
            raise
        finally:
            with (directory / f'graph-{count:03d}.json').open('x') as stream:
                json.dump(report, stream, indent=2)
                stream.write('\n')

    return backend
