"""Packet112 F32 anchor extraction from qualification captures (last frame, 256x256).

No cached anchor can replace the predecessor: every load checks its entire file
hash, exact four-tensor header, frame48 and stable file identity. Runtime authority
and predecessor retention are the future coordinator's responsibility.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import struct
import sys

import stream_contract as _contract
_GEOMETRY = _contract.geometry(_contract.launch_frames())
SHAPES = _GEOMETRY['tensor_shapes']
ANCHOR_SHAPE = list(_contract.ANCHOR_SHAPE)
FRAME_INDEX = _GEOMETRY['anchor_frame_index']
FRAME_BYTES = _contract.ANCHOR_BYTES
MAX_HEADER = 65536
MAX_FILE = _GEOMETRY['full_payload_bytes'] + MAX_HEADER + 8
BLOCK = 1024 * 1024
CONTEXT_KEYS = {'runtime_manifest_sha256', 'model_verification_sha256', 'plan_sha256',
                'prompt_sha256', 'pass_index', 'chunk_index', 'seed', 'graph_sha256', 'capture_name'}


def require(ok, why):
    if not ok:
        raise ValueError(why)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def digest(value):
    require(isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value), 'Invalid SHA256')
    return value


def strict_json(raw):
    def pairs(items):
        out = {}
        for k, v in items:
            require(k not in out, 'Duplicate JSON key')
            out[k] = v
        return out
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: require(False, 'Nonfinite JSON'))


def safe_path(path):
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts and
            not any(p.is_symlink() for p in (path, *path.parents)), 'Unsafe predecessor path')
    return path


def identity(s):
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink)


def finite_bytes(raw):
    require(type(raw) is bytes and len(raw) % 4 == 0, 'Immutable complete F32 bytes required')
    # Inspect exponent bits without conversion, clamping or loss of signed zero.
    require(all(word & 0x7f800000 != 0x7f800000 for (word,) in struct.iter_unpack('<I', raw)),
            'Nonfinite anchor')


def _header(raw, data_size, shapes):
    require(raw.startswith(b'{'), 'Header must start with object')
    values = strict_json(raw)
    require(type(values) is dict and set(values) == set(shapes), 'Exactly four capture tensors required')
    ranges = []
    for key, shape in shapes.items():
        row = values[key]
        require(type(row) is dict and set(row) == {'dtype', 'shape', 'data_offsets'}, 'Tensor descriptor differs')
        require(row['dtype'] == 'F32' and type(row['shape']) is list and
                all(type(n) is int for n in row['shape']) and row['shape'] == shape,
                'Capture shape/dtype differs: ' + key)
        offsets = row['data_offsets']
        require(type(offsets) is list and len(offsets) == 2 and all(type(n) is int for n in offsets),
                'Invalid tensor offsets')
        start, end = offsets
        require(0 <= start <= end <= data_size and end-start == math.prod(shape)*4, 'Tensor range differs')
        ranges.append((start, end))
    cursor = 0
    for start, end in sorted(ranges):
        require(start == cursor, 'Tensor gaps/overlap')
        cursor = end
    require(cursor == data_size, 'Unindexed capture bytes')
    return values


def _extract(path, expected_capture_sha256, shapes, frame_index):
    """Private parameterized parser seam permits tiny CPU structural fixtures."""
    digest(expected_capture_sha256)
    path = safe_path(path)
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
                10 <= before.st_size <= MAX_FILE, 'Nonregular/linked/oversized predecessor')
        stream = os.fdopen(fd, 'rb', buffering=0)
    except BaseException:
        os.close(fd)
        raise
    with stream:
        prefix = stream.read(8)
        require(len(prefix) == 8, 'Truncated header prefix')
        count = struct.unpack('<Q', prefix)[0]
        require(2 <= count <= MAX_HEADER and count % 8 == 0 and count+8 <= before.st_size,
                'Invalid bounded header length')
        raw_header = stream.read(count)
        require(len(raw_header) == count, 'Truncated header')
        tensors = _header(raw_header, before.st_size-8-count, shapes)
        image = tensors['images']
        require(0 <= frame_index < shapes['images'][0], 'Invalid frame index')
        frame_bytes = math.prod(shapes['images'][1:])*4
        anchor_start = 8+count+image['data_offsets'][0]+frame_index*frame_bytes
        anchor_end = anchor_start+frame_bytes
        whole = hashlib.sha256(prefix+raw_header)
        anchor = bytearray()
        position = 8+count
        while position < before.st_size:
            block = stream.read(min(BLOCK, before.st_size-position))
            require(block, 'Truncated capture payload')
            whole.update(block)
            lo, hi = max(position, anchor_start), min(position+len(block), anchor_end)
            if lo < hi:
                anchor.extend(block[lo-position:hi-position])
            position += len(block)
        require(not stream.read(1), 'Capture grew during read')
        require(identity(before) == identity(os.fstat(fd)) == identity(path.lstat()),
                'Predecessor changed during extraction')
        require(not path.is_symlink(), 'Predecessor replaced by symlink')
        require(whole.hexdigest() == expected_capture_sha256, 'Whole predecessor SHA256 mismatch')
    payload = bytes(anchor)
    require(len(payload) == frame_bytes, 'Truncated anchor')
    finite_bytes(payload)
    return payload, {'capture_path': str(path), 'capture_sha256': expected_capture_sha256,
        'anchor_sha256': sha(payload), 'frame_index': frame_index,
        'shape': [1, *shapes['images'][1:]], 'dtype': 'F32', 'byte_order': 'little',
        'byte_length': len(payload), 'source_file_identity': list(identity(before)),
        'header_sha256': sha(raw_header), 'whole_capture_hash_verified': True,
        'anchor_finite_verified': True, 'other_tensor_finiteness_verified': False,
        'transformation': 'none'}


def extract_anchor(path, expected_capture_sha256):
    return _extract(path, expected_capture_sha256, SHAPES, FRAME_INDEX)


def validate_context(context):
    require(type(context) is dict and set(context) == CONTEXT_KEYS, 'Predecessor context differs')
    for key in CONTEXT_KEYS:
        if key.endswith('_sha256'):
            digest(context[key])
    require(type(context['pass_index']) is int and context['pass_index'] in (0, 1) and
            type(context['chunk_index']) is int and context['chunk_index'] in (0, 1),
            'Only pass0/1 predecessor chunks0/1 supported')
    require(type(context['seed']) is int and 0 <= context['seed'] < 2**64, 'Seed must be uint64')
    require(context['capture_name'] == 'continuation111-pass%d-chunk%d' %
            (context['pass_index'], context['chunk_index']), 'Capture name/order differs')


def bind_predecessor(path, expected_capture_sha256, context):
    """Create metadata only; caller must obtain expected identities from authority."""
    validate_context(context)
    path = safe_path(path)
    require(path.name == 'tensors.safetensors' and path.parent.name == context['capture_name'],
            'Predecessor capture path/name mismatch')
    payload, metadata = extract_anchor(path, expected_capture_sha256)
    return {'schema': 'ltx.continuation111.anchor.v1', 'context': dict(context), **metadata}


def validate_binding(binding, expected_context):
    validate_context(expected_context)
    require(type(binding) is dict and binding.get('schema') == 'ltx.continuation111.anchor.v1' and
            binding.get('context') == expected_context, 'Anchor context/lineage mismatch')
    require(binding.get('shape') == ANCHOR_SHAPE and binding.get('frame_index') == FRAME_INDEX and
            binding.get('dtype') == 'F32' and binding.get('byte_order') == 'little' and
            binding.get('byte_length') == FRAME_BYTES and binding.get('transformation') == 'none' and
            binding.get('whole_capture_hash_verified') is True and binding.get('anchor_finite_verified') is True,
            'Anchor shape/format/verification differs')
    digest(binding.get('capture_sha256')); digest(binding.get('anchor_sha256'))
    path = safe_path(binding['capture_path'])
    require(path.name == 'tensors.safetensors' and path.parent.name == expected_context['capture_name'],
            'Predecessor capture path/name mismatch')


def load_bytes(binding, expected_context):
    """Re-read predecessor every time; no cached payload, fallback or artifact write."""
    validate_binding(binding, expected_context)
    payload, actual = extract_anchor(binding['capture_path'], binding['capture_sha256'])
    for key, value in actual.items():
        require(binding.get(key) == value, 'Predecessor binding changed: ' + key)
    return payload


def load_image(binding, expected_context, torch_module):
    """Explicit future provider seam; no imports, devices, registration or conversion."""
    require(sys.byteorder == 'little', 'Little-endian CPU required')
    payload = load_bytes(binding, expected_context)
    # Clone owns storage independent of both file lifetime and temporary buffer.
    image = torch_module.frombuffer(bytearray(payload), dtype=torch_module.float32)
    return image.reshape(*ANCHOR_SHAPE).clone()
