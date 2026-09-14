"""Bounded stdlib capture verification and exact F32 frame delivery; no writes.

Integrity against a capture's own summary is not original-reference parity or
runtime attestation. The caller owns immutable captures and receipt provenance.
"""
from contextlib import contextmanager
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import struct

import continuation_anchor_io as anchor_io

READ_BYTES = 65536
MAX_SUMMARY_BYTES = 262144
SHAPES = {'images': [25, 256, 256, 3], 'video_latent': [1, 128, 4, 8, 8],
          'audio_latent': [1, 8, 26, 16], 'waveform': [1, 2, 48480]}
BYTE_LENGTHS = {'images': 19660800, 'video_latent': 131072,
                'audio_latent': 13312, 'waveform': 387840}
SCHEMA = 'ltx25.continuation-capture-verification.v1'


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _valid_hash(value):
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value) is not None


@contextmanager
def _open_regular(path):
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        _require(stat.S_ISREG(info.st_mode), 'capture/summary must be a regular file')
        stream = os.fdopen(fd, 'rb', buffering=0)
    except BaseException:
        os.close(fd)
        raise
    with stream:
        yield stream, anchor_io._file_identity(info)


def _unchanged(stream, identity):
    _require(anchor_io._file_identity(os.fstat(stream.fileno())) == identity,
             'source file changed during reading')


def _read_exact(stream, length):
    chunks = []
    while length:
        chunk = stream.read(min(length, READ_BYTES))
        _require(chunk, 'truncated source file')
        chunks.append(chunk)
        length -= len(chunk)
    return b''.join(chunks)


def _json(raw):
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=anchor_io._unique_object,
                          parse_constant=anchor_io._reject_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise ValueError('invalid JSON') from error


def _header(stream, identity):
    _require(identity['size'] >= 10, 'capture too short')
    size = struct.unpack('<Q', _read_exact(stream, 8))[0]
    _require(2 <= size <= anchor_io.MAX_HEADER_BYTES and 8 + size <= identity['size'],
             'capture header exceeds bounded file limits')
    raw = _read_exact(stream, size)
    anchor_io._validate_header(raw, identity['size'] - 8 - size)
    header = _json(raw)
    _require(set(header) - {'__metadata__'} == set(SHAPES), 'capture must have exactly four expected tensors')
    for name, shape in SHAPES.items():
        _require(header[name]['dtype'] == 'F32', f'{name}: expected F32')
        _require(header[name]['shape'] == shape, f'{name}: unexpected shape')
    return header, 8 + size, hashlib.sha256(raw).hexdigest()


def _summary(summary_path, run_name):
    with _open_regular(summary_path) as (stream, identity):
        _require(0 < identity['size'] <= MAX_SUMMARY_BYTES, 'summary exceeds bounded size')
        raw = _read_exact(stream, identity['size'])
        _unchanged(stream, identity)
    report = _json(raw)
    _require(isinstance(report, dict), 'summary must be an object')
    _require(report.get('run_name') == run_name, 'summary run_name must equal capture parent directory name')
    _require(report.get('deterministic_enabled') is True and report.get('deterministic_warn_only') is False,
             'summary must report strict deterministic settings')
    _require(type(report.get('sample_rate')) is int and report['sample_rate'] == 48000,
             'summary sample_rate must be 48000')
    tensors = report.get('tensors')
    _require(isinstance(tensors, dict) and set(tensors) == set(SHAPES), 'summary requires exactly four tensors')
    for name, shape in SHAPES.items():
        desc = tensors[name]
        _require(isinstance(desc, dict), f'{name}: invalid summary descriptor')
        _require(desc.get('dtype') == 'torch.float32' and desc.get('shape') == shape,
                 f'{name}: summary dtype/shape mismatch')
        _require(all(type(dim) is int for dim in desc['shape']), f'{name}: noninteger summary shape')
        _require(desc.get('finite') is True and _valid_hash(desc.get('sha256')),
                 f'{name}: expected finite flag and SHA256')
    return report, hashlib.sha256(raw).hexdigest()


def _finite(data, name):
    for (word,) in struct.iter_unpack('<I', data):
        if word & 0x7f800000 == 0x7f800000:
            raise ValueError(f'{name}: nonfinite captured sample')


def verify_capture(capture_path, summary_path):
    """Fully verify four tensors in <=64KiB reads, returning a compact receipt.

    Nothing is returned on partial verification or failure. Summary deterministic
    flags are reported settings only; GPU/runtime identity needs an external bind.
    """
    capture_path = Path(capture_path)
    run_name = capture_path.parent.name
    summary, summary_sha = _summary(summary_path, run_name)
    verified = {}
    frame_hashes = []
    with _open_regular(capture_path) as (stream, identity):
        header, data_start, header_sha = _header(stream, identity)
        for name in sorted(SHAPES, key=lambda key: header[key]['data_offsets'][0]):
            start, end = header[name]['data_offsets']
            stream.seek(data_start + start)
            remaining = end - start
            digest = hashlib.sha256()
            frame_digest = hashlib.sha256()
            frame_remaining = anchor_io.FRAME_BYTES
            while remaining:
                data = _read_exact(stream, min(remaining, READ_BYTES))
                _finite(data, name)
                digest.update(data)
                if name == 'images':
                    cursor = 0
                    while cursor < len(data):
                        count = min(frame_remaining, len(data) - cursor)
                        frame_digest.update(data[cursor:cursor + count])
                        frame_remaining -= count
                        cursor += count
                        if frame_remaining == 0:
                            frame_hashes.append(frame_digest.hexdigest())
                            frame_digest = hashlib.sha256()
                            frame_remaining = anchor_io.FRAME_BYTES
                remaining -= len(data)
            _require(digest.hexdigest() == summary['tensors'][name]['sha256'], f'{name}: summary SHA256 mismatch')
            verified[name] = {'dtype': 'float32', 'storage_dtype': 'F32', 'shape': list(SHAPES[name]),
                              'sha256': digest.hexdigest(), 'byte_offset': data_start + start,
                              'byte_length': end - start, 'finite': True}
            _unchanged(stream, identity)
        _require(len(frame_hashes) == 25, 'wrong number of verified video frames')
        _unchanged(stream, identity)
    return {'schema': SCHEMA, 'complete': True, 'run_name': run_name,
            'source_capture_path': str(capture_path), 'source_file_identity': identity,
            'source_header_sha256': header_sha, 'source_header_bytes': data_start - 8,
            'summary_file_sha256': summary_sha, 'tensors': verified,
            'frame_sha256': frame_hashes, 'anchor_sha256': frame_hashes[24],
            'strict_determinism_reported': True, 'sample_rate': 48000,
            'byte_order': 'little', 'integrity_scope': 'four raw tensors against their own capture summary',
            'runtime_identity_verified': False, 'original_reference_parity_verified': False,
            'deterministic_replay_verified': False, 'delivery_complete': False}


def _validate_receipt(receipt):
    _require(isinstance(receipt, dict) and receipt.get('schema') == SCHEMA and receipt.get('complete') is True,
             'full capture verification receipt required')
    _require(receipt.get('strict_determinism_reported') is True and receipt.get('byte_order') == 'little',
             'receipt settings/type contract mismatch')
    _require(receipt.get('sample_rate') == 48000 and type(receipt.get('sample_rate')) is int,
             'receipt sample rate mismatch')
    for name in ('summary_file_sha256', 'source_header_sha256', 'anchor_sha256'):
        _require(_valid_hash(receipt.get(name)), f'invalid receipt {name}')
    identity = receipt.get('source_file_identity')
    _require(isinstance(identity, dict) and set(identity) == {'device', 'inode', 'size', 'mtime_ns', 'ctime_ns'}
             and all(type(value) is int for value in identity.values()), 'invalid source file identity')
    _require(type(receipt.get('source_header_bytes')) is int and
             2 <= receipt['source_header_bytes'] <= anchor_io.MAX_HEADER_BYTES, 'invalid receipt header length')
    tensors = receipt.get('tensors')
    _require(isinstance(tensors, dict) and set(tensors) == set(SHAPES), 'receipt requires all four tensors')
    for name, shape in SHAPES.items():
        item = tensors[name]
        _require(isinstance(item, dict) and item.get('dtype') == 'float32' and item.get('storage_dtype') == 'F32'
                 and item.get('shape') == shape and all(type(dim) is int for dim in item['shape']),
                 f'{name}: receipt dtype/shape mismatch')
        _require(item.get('finite') is True and _valid_hash(item.get('sha256')),
                 f'{name}: invalid verified hash/finite flag')
        _require(type(item.get('byte_offset')) is int and type(item.get('byte_length')) is int
                 and item['byte_length'] == BYTE_LENGTHS[name], f'{name}: invalid byte range')
    hashes = receipt.get('frame_sha256')
    _require(isinstance(hashes, list) and len(hashes) == 25 and all(_valid_hash(value) for value in hashes),
             'all 25 verified frame hashes required')
    _require(receipt['anchor_sha256'] == hashes[24], 'anchor/frame24 hash mismatch')


def iter_delivery_frames(capture_path, verification, chunk_index):
    """Yield exact raw frames0..24 or1..24, holding only one frame at a time.

    Early close releases the file without declaring delivery complete. Exhaustion
    is the completion signal; consumers must not equate the last yield with it.
    Caller must retain an immutable capture and a trusted full-verification receipt.
    """
    _validate_receipt(verification)
    verification = copy.deepcopy(verification)
    _require(type(chunk_index) is int and chunk_index >= 0, 'chunk index must be nonnegative integer')
    capture_path = Path(capture_path)
    _require(capture_path.parent.name == verification.get('run_name'), 'delivery run_name mismatch')
    with _open_regular(capture_path) as (stream, identity):
        _require(identity == verification['source_file_identity'], 'source differs from verified file identity')
        header, data_start, header_sha = _header(stream, identity)
        _require(header_sha == verification['source_header_sha256'] and
                 data_start == 8 + verification['source_header_bytes'], 'verified header changed')
        for name in SHAPES:
            item = verification['tensors'][name]
            start, end = header[name]['data_offsets']
            _require(item['byte_offset'] == data_start + start and item['byte_length'] == end - start,
                     f'{name}: verified range differs from header')
        first = 0 if chunk_index == 0 else 1
        stream.seek(verification['tensors']['images']['byte_offset'] + first * anchor_io.FRAME_BYTES)
        for frame_index in range(first, 25):
            _unchanged(stream, identity)
            payload = _read_exact(stream, anchor_io.FRAME_BYTES)
            _unchanged(stream, identity)
            _require(hashlib.sha256(payload).hexdigest() == verification['frame_sha256'][frame_index],
                     f'frame{frame_index}: differs from verified bytes')
            yield payload
        _unchanged(stream, identity)
