"""Packet112 per-chunk receipt schema and anchor-file I/O. Stdlib only.

An anchor file is exactly the 786,432 little-endian F32 bytes of the last frame
(images[frames-1], [1,256,256,3]) of a completed chunk, written once (exclusive
create, fsync).
The provider re-reads it for every consumer and checks length, finiteness and
the SHA-256 recorded by the authority; no cached tensor substitutes for it.
"""
import hashlib
import math
import os
from pathlib import Path
import re
import stat
import struct

import stream_contract as contract

SCHEMA = 'ltx.stream112.chunk-receipt.v1'
SHA = re.compile(r'[0-9a-f]{64}')
TIMING_KEYS = ('submit', 'execution_start', 'sampler_a_start', 'sampler_b_start', 'decode_start',
               'decode_done', 'preview_written', 'receipt_staged')
TENSORS = ('images', 'video_latent', 'audio_latent', 'waveform')


def require(ok, why):
    if not ok:
        raise ValueError(why)


def finite_f32(raw):
    require(type(raw) is bytes and len(raw) % 4 == 0, 'F32 bytes required')
    require(all(word & 0x7f800000 != 0x7f800000 for (word,) in struct.iter_unpack('<I', raw)),
            'Nonfinite F32 value')


def _safe(path):
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts and
            not any(p.is_symlink() for p in (path, *path.parents)), 'Unsafe anchor path')
    return path


def anchor_path(anchor_dir, run_name):
    return _safe(anchor_dir) / (run_name + '.f32')


def write_anchor(anchor_dir, run_name, raw, frames):
    require(type(raw) is bytes and len(raw) == contract.ANCHOR_BYTES, 'Anchor must be 786,432 bytes')
    finite_f32(raw)
    path = anchor_path(anchor_dir, run_name)
    with path.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return {'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest(),
            'bytes': len(raw), 'frame_index': contract.geometry(frames)['anchor_frame_index'],
            'shape': list(contract.ANCHOR_SHAPE), 'dtype': 'F32', 'byte_order': 'little'}


def read_anchor(path, expected_sha256):
    require(type(expected_sha256) is str and SHA.fullmatch(expected_sha256), 'Expected anchor SHA required')
    path = _safe(path)
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
                before.st_size == contract.ANCHOR_BYTES, 'Anchor file is not a single-link 786,432-byte file')
        raw = stream.read(contract.ANCHOR_BYTES + 1)
        key = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink)
        require(len(raw) == contract.ANCHOR_BYTES and key(before) == key(os.fstat(stream.fileno())) ==
                key(path.lstat()), 'Anchor changed during read')
    require(hashlib.sha256(raw).hexdigest() == expected_sha256, 'Anchor bytes differ from the recorded hash')
    finite_f32(raw)
    return raw


def delivery(chunk_index, frames):
    first = chunk_index == 0
    g = contract.geometry(frames)
    return {'frames_total': frames, 'fps': contract.FPS,
            'new_frames': g['new_frames_first_chunk'] if first else g['new_frames_continuation'],
            'first_new_frame_index': 0 if first else 1, 'drop_leading_frames': 0 if first else 1,
            'overlap': None if first else
            'frame 0 re-renders the predecessor anchor (its frame %d); drop it' % g['anchor_frame_index']}


def seconds(timing, start, end):
    a, b = timing.get(start), timing.get(end)
    return None if a is None or b is None else round((b - a) / 1e9, 6)


def validate_receipt(r):
    """Schema check used by the server before commit and by clients after reading."""
    require(type(r) is dict and r.get('schema') == SCHEMA, 'Receipt schema differs')
    for key in ('run_name', 'prompt_id', 'kind', 'scene_id', 'prompt_sha256', 'plan_sha256',
                'qualification_id', 'runtime_manifest_sha256', 'server_identity_sha256'):
        require(type(r.get(key)) is str and r[key], 'Receipt field missing: ' + key)
    require(type(r.get('chunk_index')) is int and type(r.get('seed')) is int and type(r.get('stream_seq')) is int,
            'Receipt integers missing')
    require(r.get('frames') in contract.FRAME_CHOICES and r.get('reuse_text') in (0, 1), 'Receipt frames/reuse missing')
    require(r['kind'] in contract.KINDS and r['run_name'] == contract.run_name(r), 'Receipt identity differs')
    g = contract.geometry(r['frames'])
    tensors = r.get('tensors')
    require(type(tensors) is dict and set(tensors) == set(TENSORS), 'Exactly four tensors required')
    for name, row in tensors.items():
        require(type(row) is dict and row.get('shape') == g['tensor_shapes'][name] and
                row.get('dtype') == 'torch.float32' and row.get('finite') is True and
                type(row.get('sha256')) is str and SHA.fullmatch(row['sha256']),
                'Tensor summary differs: ' + name)
    out = r.get('anchor_out')
    require(type(out) is dict and SHA.fullmatch(out.get('sha256', '')) and out.get('bytes') == contract.ANCHOR_BYTES
            and out.get('frame_index') == g['anchor_frame_index'], 'anchor_out differs')
    anchor_in = r.get('anchor_in')
    if r['chunk_index'] == 0:
        require(anchor_in is None, 'Chunk 0 has no anchor_in')
    else:
        previous = dict(r, chunk_index=r['chunk_index'] - 1, stream_seq=r['stream_seq'] - 1
                        if r['kind'] == 'stream' else -1)
        require(type(anchor_in) is dict and SHA.fullmatch(anchor_in.get('sha256', '')) and
                anchor_in.get('source_run_name') == contract.run_name(previous),
                'anchor_in must name the immediate predecessor')
    require(r.get('delivery') == delivery(r['chunk_index'], r['frames']), 'Delivery description differs')
    preview = r.get('preview')
    require(type(preview) is dict and type(preview.get('path')) is str and preview['path'].endswith('.mp4') and
            Path(preview['path']).is_absolute() and type(preview.get('bytes')) is int and preview['bytes'] > 0,
            'Preview MP4 record differs')
    capture = r.get('capture')
    if r['kind'] in contract.CAPTURE_KINDS:
        require(type(capture) is dict and capture.get('path', '').endswith('tensors.safetensors'),
                'Qualification receipts carry their full capture')
    else:
        require(capture is None, 'Stream chunks write no full capture')
    timing = r.get('timing_ns')
    require(type(timing) is dict and set(timing) == set(TIMING_KEYS) and
            all(timing[k] is None or type(timing[k]) is int for k in TIMING_KEYS), 'Timing fields differ')
    sanity = r.get('sanity')
    require(sanity == {'finite': True, 'shapes': True, 'anchor_chain': True}, 'Sanity checks did not pass')
    text = r.get('text')
    require(type(text) is dict and text.get('reused') is bool(r['reuse_text']) and type(text.get('tensors')) is list and
            text['tensors'] and all(SHA.fullmatch(t.get('sha256', '')) for t in text['tensors']),
            'Text conditioning record differs')
    graph = r.get('graph')
    require(type(graph) is dict and graph.get('gate_mode') in ('original', 'graph') and
            type(graph.get('new_captures')) is int and graph['new_captures'] >= 0 and
            graph.get('routes') in (0, 48) and type(graph.get('signatures_per_route')) is int and
            (graph['gate_mode'] == 'graph') == (r['kind'] != 'qualify-eager'), 'Graph record differs')
    for key in ('memory', 'storage'):
        require(type(r.get(key)) is dict, 'Receipt field missing: ' + key)
    return r


def summarize_bytes(name, raw, frames):
    """Byte-level summary (used by tests)."""
    shape = contract.geometry(frames)['tensor_shapes'][name]
    require(len(raw) == math.prod(shape) * 4, 'Tensor byte count differs: ' + name)
    finite_f32(raw)
    return {'shape': list(shape), 'dtype': 'torch.float32', 'sha256': hashlib.sha256(raw).hexdigest(),
            'finite': True}
