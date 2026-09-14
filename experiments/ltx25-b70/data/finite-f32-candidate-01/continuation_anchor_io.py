"""Read an exact float anchor from a capture; standard library, no tensor runtime.

Only the safetensors header and images frame 24 are read. This is deliberately
not a general tensor loader or an attestation of the other captured samples.
"""
import hashlib
import json
import math
import os
import re
import stat
import struct

IMAGE_SHAPE = [25, 256, 256, 3]
ANCHOR_SHAPE = [1, 256, 256, 3]
FRAME_INDEX = 24
FRAME_BYTES = 786432
MAX_HEADER_BYTES = 1024 * 1024
DTYPE_BYTES = {'BOOL': 1, 'U8': 1, 'I8': 1, 'I16': 2, 'U16': 2,
               'I32': 4, 'U32': 4, 'I64': 8, 'U64': 8,
               'F16': 2, 'BF16': 2, 'F32': 4, 'F64': 8}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _anchor_metadata(payload):
    _require(type(payload) is bytes, 'anchor payload must be immutable bytes')
    _require(len(payload) == FRAME_BYTES, 'anchor must contain exactly 786432 bytes')
    # IEEE754 exponent all ones means infinity or NaN, regardless of sign or
    # mantissa. No float conversions: preserve zeros, subnormals and every bit.
    for index, (word,) in enumerate(struct.iter_unpack('<I', payload)):
        if word & 0x7f800000 == 0x7f800000:
            raise ValueError(f'nonfinite anchor sample at scalar index {index}')
    return {'sha256': hashlib.sha256(payload).hexdigest(), 'dtype': 'float32',
            'storage_dtype': 'F32', 'byte_order': 'little',
            'shape': list(ANCHOR_SHAPE), 'byte_length': FRAME_BYTES,
            'finite': True, 'transformation': 'none'}


def validate_anchor_bytes(payload, expected_sha256):
    """Validate immutable little-endian F32 RGB bytes against a caller's hash."""
    _require(isinstance(expected_sha256, str) and
             re.fullmatch(r'[0-9a-f]{64}', expected_sha256),
             'expected SHA256 must be 64 lowercase hexadecimal characters')
    metadata = _anchor_metadata(payload)
    _require(metadata['sha256'] == expected_sha256, 'anchor SHA256 mismatch')
    return metadata


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, f'duplicate JSON key: {key}')
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError(f'nonstandard JSON constant: {value}')


def _read_exact(stream, length):
    data = stream.read(length)
    _require(len(data) == length, 'truncated capture')
    return data


def _file_identity(info):
    return {'device': info.st_dev, 'inode': info.st_ino, 'size': info.st_size,
            'mtime_ns': info.st_mtime_ns, 'ctime_ns': info.st_ctime_ns}


def _validate_header(raw, data_size):
    _require(raw.startswith(b'{'), 'safetensors header must start with an object')
    try:
        header = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_object,
                            parse_constant=_reject_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise ValueError('invalid safetensors JSON header') from error
    _require(isinstance(header, dict), 'header must be an object')
    ranges = []
    for name, desc in header.items():
        _require(isinstance(name, str) and name, 'invalid tensor name')
        if name == '__metadata__':
            _require(isinstance(desc, dict) and all(isinstance(v, str) for v in desc.values()),
                     'metadata must map strings to strings')
            continue
        _require(isinstance(desc, dict) and set(desc) == {'dtype', 'shape', 'data_offsets'},
                 f'{name}: invalid tensor descriptor')
        dtype, shape, offsets = desc['dtype'], desc['shape'], desc['data_offsets']
        _require(isinstance(dtype, str) and dtype in DTYPE_BYTES, f'{name}: unsupported dtype')
        _require(isinstance(shape, list) and len(shape) <= 16 and
                 all(type(dim) is int and 0 <= dim <= 2**63 - 1 for dim in shape),
                 f'{name}: invalid tensor shape')
        _require(isinstance(offsets, list) and len(offsets) == 2 and
                 all(type(offset) is int for offset in offsets), f'{name}: invalid offsets')
        start, end = offsets
        _require(0 <= start <= end <= data_size, f'{name}: offsets outside data buffer')
        _require(end - start == math.prod(shape) * DTYPE_BYTES[dtype],
                 f'{name}: shape/dtype byte count disagrees with offsets')
        ranges.append((start, end))
    position = 0
    for start, end in sorted(ranges):
        _require(start == position, 'tensor ranges overlap or leave a gap')
        position = end
    _require(position == data_size, 'unindexed trailing bytes in capture')
    _require('images' in header and isinstance(header['images'], dict), 'images tensor missing')
    image = header['images']
    _require(image['dtype'] == 'F32', 'images must be F32')
    _require(image['shape'] == IMAGE_SHAPE, 'images must have shape [25,256,256,3]')
    return image


def extract_anchor(capture_path):
    """Return (frame24 bytes, metadata); validate header and bounded file ranges.

    No output files are written. SHA256 covers this anchor, not the whole capture.
    The caller must separately bind the original capture and predecessor identity.
    """
    # NONBLOCK permits rejecting a FIFO without hanging before the regular-file
    # check. The descriptor remains the same across validation and frame reading.
    fd = os.open(capture_path, os.O_RDONLY | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        _require(stat.S_ISREG(before.st_mode), 'capture must be a regular file')
        stream = os.fdopen(fd, 'rb', buffering=0)
    except BaseException:
        os.close(fd)
        raise
    with stream:
        _require(before.st_size >= 10, 'capture is too short for its header')
        header_size = struct.unpack('<Q', _read_exact(stream, 8))[0]
        _require(2 <= header_size <= MAX_HEADER_BYTES, 'header length outside bounded capture limit')
        data_start = 8 + header_size
        _require(data_start <= before.st_size, 'header exceeds file bounds')
        raw_header = _read_exact(stream, header_size)
        image = _validate_header(raw_header, before.st_size - data_start)
        offset = data_start + image['data_offsets'][0] + FRAME_INDEX * FRAME_BYTES
        stream.seek(offset)
        payload = _read_exact(stream, FRAME_BYTES)
        after = os.fstat(stream.fileno())
        _require(_file_identity(before) == _file_identity(after), 'capture changed during extraction')
    metadata = _anchor_metadata(payload)
    metadata.update({'frame_index': FRAME_INDEX, 'source_tensor': 'images',
                     'source_shape': list(IMAGE_SHAPE), 'source_byte_offset': offset,
                     'source_capture_path': os.fsdecode(capture_path),
                     'source_file_identity': _file_identity(before),
                     'source_header_sha256': hashlib.sha256(raw_header).hexdigest(),
                     'source_header_bytes': header_size,
                     'bytes_read': 8 + header_size + FRAME_BYTES,
                     'whole_capture_hash_verified': False,
                     'other_frames_finite_verified': False})
    return payload, metadata
