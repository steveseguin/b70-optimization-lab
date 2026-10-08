"""Packet113 per-chunk receipt schema, preview record schema, anchor-file I/O. Stdlib only.

Packet113 commits the chunk receipt at "anchor ready": the anchor file is fsynced
and the four tensors are hashed, but the MP4 preview is still queued on the single
preview-writer thread. The receipt therefore records the preview path it WILL
have (`preview.state: "queued"`, `bytes: null`) and `timing_ns.preview_written:
null`; the writer later commits `receipts/preview-<run_name>.json` (schema
PREVIEW_SCHEMA) with the measured bytes, SHA-256 and preview_written time. The
next chunk's receipt also carries that record's timing (`predecessor_preview`).

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

SCHEMA = 'ltx.stream113.chunk-receipt.v1'
PREVIEW_SCHEMA = 'ltx.stream113.preview-record.v1'
DIAGNOSTIC_SCHEMA = 'ltx.stream113.anchor-border-diagnostic.v1'
BORDER_PX = 16
SHA = re.compile(r'[0-9a-f]{64}')
TIMING_KEYS = ('submit', 'execution_start', 'sampler_a_start', 'sampler_b_start', 'decode_start',
               'decode_done', 'anchor_ready', 'preview_queued', 'preview_written', 'receipt_staged')
PREVIEW_TIMING_KEYS = ('submit', 'anchor_ready', 'preview_queued', 'write_start', 'preview_written')
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


def delivery(chunk_index, frames, anchored=None):
    """anchored defaults to chunk_index > 0 (packet112); a reset chunk passes anchored=False."""
    first = not (chunk_index > 0 if anchored is None else anchored)
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
    reset = r.get('reset')
    anchored = r.get('anchored')
    require(reset in (False, True) and anchored is (r['chunk_index'] > 0 and not reset) and
            (not reset or (r['kind'] == 'stream' and r['chunk_index'] > 0)), 'anchored/reset record differs')
    pred = r.get('reset_predecessor_anchor_sha256')
    require(pred is None if not reset else (pred == '' or (type(pred) is str and SHA.fullmatch(pred))),
            'reset_predecessor_anchor_sha256 differs')
    if not anchored:
        require(anchor_in is None, 'An unanchored chunk has no anchor_in')
    else:
        previous = dict(r, chunk_index=r['chunk_index'] - 1, stream_seq=r['stream_seq'] - 1
                        if r['kind'] == 'stream' else -1)
        require(type(anchor_in) is dict and SHA.fullmatch(anchor_in.get('sha256', '')) and
                anchor_in.get('source_run_name') == contract.run_name(previous),
                'anchor_in must name the immediate predecessor')
    require(r.get('delivery') == delivery(r['chunk_index'], r['frames'], anchored), 'Delivery description differs')
    preview = r.get('preview')
    require(type(preview) is dict and type(preview.get('path')) is str and preview['path'].endswith('.mp4') and
            Path(preview['path']).is_absolute() and preview.get('state') == 'queued' and
            preview.get('bytes') is None and type(preview.get('record')) is str and
            Path(preview['record']).name == 'preview-%s.json' % r['run_name'],
            'Preview MP4 record differs (113 receipts commit with the preview queued)')
    prior = r.get('predecessor_preview')
    require(prior is None or (type(prior) is dict and type(prior.get('run_name')) is str and
                              type(prior.get('preview_written_ns')) is int), 'predecessor_preview differs')
    validate_diagnostic(r.get('anchor_diagnostics'))
    capture = r.get('capture')
    if r['kind'] in contract.CAPTURE_KINDS:
        require(type(capture) is dict and capture.get('path', '').endswith('tensors.safetensors'),
                'Qualification receipts carry their full capture')
    else:
        require(capture is None, 'Stream chunks write no full capture')
    timing = r.get('timing_ns')
    require(type(timing) is dict and set(timing) == set(TIMING_KEYS) and
            all(timing[k] is None or type(timing[k]) is int for k in TIMING_KEYS) and
            timing['preview_written'] is None and type(timing['anchor_ready']) is int and
            type(timing['preview_queued']) is int and timing['anchor_ready'] <= timing['preview_queued'],
            'Timing fields differ')
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


def validate_preview_record(p, receipt=None):
    """Schema of receipts/preview-<run_name>.json; with `receipt`, also its binding to the chunk."""
    require(type(p) is dict and p.get('schema') == PREVIEW_SCHEMA, 'Preview record schema differs')
    for key in ('run_name', 'prompt_id', 'path', 'relative_to_output_directory', 'sha256'):
        require(type(p.get(key)) is str and p[key], 'Preview record field missing: ' + key)
    require(SHA.fullmatch(p['sha256']) and type(p.get('bytes')) is int and p['bytes'] > 0 and
            p['path'].endswith('.mp4') and Path(p['path']).is_absolute() and p.get('container') == 'mp4' and
            p.get('written') is True and p.get('order') in ('fifo',), 'Preview record values differ')
    timing = p.get('timing_ns')
    require(type(timing) is dict and set(timing) == set(PREVIEW_TIMING_KEYS) and
            all(type(timing[k]) is int for k in PREVIEW_TIMING_KEYS if k != 'submit') and
            (timing['submit'] is None or type(timing['submit']) is int) and
            timing['anchor_ready'] <= timing['preview_queued'] <= timing['write_start'] <= timing['preview_written'],
            'Preview record timing differs')
    if receipt is not None:
        require(p['run_name'] == receipt['run_name'] and p['prompt_id'] == receipt['prompt_id'] and
                p['path'] == receipt['preview']['path'] and
                timing['anchor_ready'] == receipt['timing_ns']['anchor_ready'],
                'Preview record does not belong to this receipt')
    return p


def border_diagnostic_reference(raw, height=256, width=256, border=BORDER_PX):
    """Stdlib reference of the anchor border-vs-centre diagnostic (the server computes it with
    torch in float64; tests compare the two). raw: little-endian F32 [1,H,W,3].
    chroma = max(R,G,B) - min(R,G,B); border = outer `border` px ring; centre = middle half square."""
    import array
    values = array.array('f')
    values.frombytes(raw)
    if values.itemsize != 4:
        raise ValueError('float32 array required')
    import sys
    if sys.byteorder != 'little':
        values.byteswap()
    require(len(values) == height * width * 3, 'Anchor size differs')
    acc = {k: [0.0, 0.0, 0, 0] for k in ('border', 'centre')}   # chroma sum, luma sum, clipped, count
    c0, c1 = height // 4, height - height // 4
    for y in range(height):
        for x in range(width):
            if y < border or y >= height - border or x < border or x >= width - border:
                key = 'border'
            elif c0 <= y < c1 and c0 <= x < c1:
                key = 'centre'
            else:
                continue
            i = (y * width + x) * 3
            r, g, b = float(values[i]), float(values[i + 1]), float(values[i + 2])
            row = acc[key]
            row[0] += max(r, g, b) - min(r, g, b)
            row[1] += 0.2126 * r + 0.7152 * g + 0.0722 * b
            row[2] += 1 if (max(r, g, b) >= 0.999 or min(r, g, b) <= 0.001) else 0
            row[3] += 1
    return diagnostic_from_sums({k: tuple(v) for k, v in acc.items()}, border)


def diagnostic_from_sums(sums, border=BORDER_PX):
    out = {'schema': DIAGNOSTIC_SCHEMA, 'border_px': border, 'centre': 'middle half square',
           'chroma': 'max(rgb)-min(rgb)', 'luma': 'Rec.709 weights on the F32 values', 'diagnostic_only': True}
    for key, (chroma, luma, clipped, count) in sums.items():
        out[key + '_pixels'] = int(count)
        out[key + '_mean_chroma'] = round(chroma / count, 6)
        out[key + '_mean_luma'] = round(luma / count, 6)
        out[key + '_clipped_fraction'] = round(clipped / count, 6)
    centre = out['centre_mean_chroma']
    out['border_to_centre_chroma_ratio'] = None if centre <= 0 else round(out['border_mean_chroma'] / centre, 6)
    return out


def validate_diagnostic(d):
    require(type(d) is dict and d.get('schema') == DIAGNOSTIC_SCHEMA and d.get('diagnostic_only') is True and
            d.get('border_px') == BORDER_PX and all(type(d.get(k)) in (int, float) for k in (
                'border_mean_chroma', 'centre_mean_chroma', 'border_mean_luma', 'centre_mean_luma',
                'border_clipped_fraction', 'centre_clipped_fraction')), 'Anchor diagnostic differs')
    return d
