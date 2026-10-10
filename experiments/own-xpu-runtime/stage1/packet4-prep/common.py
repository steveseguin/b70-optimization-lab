"""Packet 4 portable raw tensors and independent reference dispatch. CPU only."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys

import torch

HERE = Path(__file__).resolve().parent
LANE = HERE.parents[1]
DTYPES = {'F16': torch.float16, 'BF16': torch.bfloat16, 'F32': torch.float32,
          'F8_E4M3': torch.float8_e4m3fn, 'I32': torch.int32, 'I64': torch.int64}
NAMES = {v: k for k, v in DTYPES.items()}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def json_bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def token_hash(ids):
    return digest(json.dumps(ids, separators=(',', ':')).encode())


def contained(root, relative):
    p = Path(relative)
    if p.is_absolute() or '..' in p.parts:
        raise ValueError('unsafe relative artifact path')
    result = (root / p).resolve()
    if not result.is_relative_to(root.resolve()):
        raise ValueError('artifact escapes fixture directory')
    return result


def load_ref(model):
    paths = {'27b': LANE / 'stage1/packet1b/reference/math.py',
             'flash-next': LANE / 'stage2/packet1b/reference.py'}
    name = '_packet4_reference_' + model.replace('-', '_')
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, paths[model])
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


# Explicit allowlist: fixture JSON cannot execute arbitrary Python.
FUNCTIONS = {
    '27b': ('fp8_dequant', 'rmsnorm', 'residual_add', 'silu', 'conv_step',
            'gdn_recurrence', 'gdn', 'rope', 'attention_output_gate', 'attention',
            'ffn', 'decoder_layer', 'target_head', 'stable_argmax', 'mtp_forward'),
    'flash-next': ('norm', 'silu', 'conv', 'recurrence', 'gdn', 'rope', 'compress',
                   'select', 'qsa', 'route', 'ffn', 'moe', 'hc_mix', 'hc_combine',
                   'ple_ids', 'ple_lookup', 'layer', 'mtp'),
}


def evaluate(model, function, args, kwargs):
    r = load_ref(model)
    if function == 'linear':
        return r.Linear(args[1], args[2] if len(args) == 3 else None)(args[0])
    if function not in FUNCTIONS[model]:
        raise NotImplementedError('no CPU reference: ' + function)
    return getattr(r, function)(*args, **kwargs)


def decode_tree(tree, tensors, model):
    """Reconstitute a bounded, declarative reference call (no pickle/eval).

    linear/bank/rows/call let the existing full FFN, attention, HC, PLE, layer
    and MTP references run unchanged, including their callable dependencies.
    Native layout adaptation belongs in the reviewed binding, never here.
    """
    if isinstance(tree, list):
        return [decode_tree(x, tensors, model) for x in tree]
    if not isinstance(tree, dict):
        return tree
    if '$tensor' in tree:
        return tensors[tree['$tensor']]
    if '$dtype' in tree:
        return DTYPES[tree['$dtype']]
    if '$tuple' in tree:
        return tuple(decode_tree(x, tensors, model) for x in tree['$tuple'])
    if '$linear' in tree:
        v = decode_tree(tree['$linear'], tensors, model)
        return load_ref(model).Linear(**v)
    if '$bank' in tree:
        v = decode_tree(tree['$bank'], tensors, model)
        return lambda expert: v[str(expert)]  # Missing experts fail closed.
    if '$rows' in tree:
        v = decode_tree(tree['$rows'], tensors, model)
        return lambda part, row: v[f'{part}:{row}']
    if '$call' in tree:
        v = tree['$call']
        args = decode_tree(v.get('args', []), tensors, model)
        kwargs = decode_tree(v.get('kwargs', {}), tensors, model)
        return lambda x: evaluate(model, v['function'], [x, *args], kwargs)
    return {k: decode_tree(v, tensors, model) for k, v in tree.items()}


def flatten(value, prefix='result'):
    if isinstance(value, torch.Tensor):
        return {prefix: value}
    if isinstance(value, (list, tuple)):
        result = {}
        for i, item in enumerate(value):
            result.update(flatten(item, f'{prefix}.{i}'))
        return result
    if isinstance(value, dict):
        result = {}
        for k, item in value.items():
            result.update(flatten(item, f'{prefix}.{k}'))
        return result
    if value is None:
        return {}
    # Integer state such as PLE token history must also be compared.
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return {prefix: torch.tensor([value], dtype=torch.int64 if isinstance(value, int) else torch.float32)}
    raise ValueError('unsupported result leaf: ' + type(value).__name__)


def load_tensor(root, desc, max_bytes):
    dtype = DTYPES[desc['dtype']]
    shape = desc['shape']
    size = torch.empty((), dtype=dtype).element_size()
    expected = math.prod(shape) * size
    if expected != desc['nbytes'] or expected > max_bytes:
        raise ValueError('tensor size/cap mismatch')
    # The writer stores logical contiguous values, independent of source stride.
    stride = []
    n = 1
    for dim in reversed(shape):
        stride.insert(0, n)
        n *= max(1, dim)
    if desc['strides_elements'] != stride or desc['storage_offset_bytes'] != 0:
        raise ValueError('noncanonical stored tensor layout')
    path = contained(root, desc['artifact']['path'])
    if path.stat().st_size != expected or file_hash(path) != desc['artifact']['sha256']:
        raise ValueError('tensor artifact hash/length mismatch')
    if expected == 0:
        return torch.empty(shape, dtype=dtype)
    # mmap; raw bytes cannot execute code and are verified before interpretation.
    return torch.from_file(str(path), shared=False, size=math.prod(shape), dtype=dtype).reshape(shape)
