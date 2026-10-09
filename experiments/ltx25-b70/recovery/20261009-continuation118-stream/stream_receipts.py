"""Packet118 receipt, decode-record and preview-record schemas; frame-anchor file I/O. Stdlib only.

Packet118 (schemas ltx.stream118.*), measurement and identity only:
- receipts carry `server_options` {snapshot_mode, decoder_graph_pool_cap_bytes}; more `timing_ns` marks
  (admission_received, precheck_done, queued, executor_entry, request_snapshot_start/done, before_request_done,
  the node starts of stream_text / stream_anchor / stream_condition_a / 377, condition_a_lookup_done /
  condition_a_done, condition_b_lookup_done / condition_b_done); `node_starts_ns` (every executing event of the
  request); `timing_s.submit_split` (SUBMIT_SPLIT: named sub-buckets of submit_to_sampler_start, whose sum plus
  `other` equals it); `snapshots` (each four-card safety snapshot of the request: label, mode, dual walk,
  agreement, duration and its parts); `authority_checks` (healthy() calls and seconds during the request);
  `turnaround` (the predecessor's receipt -> this submit: TURNAROUND_SPLIT, HTTP visibility and poll count);
- decode records carry `decoder.pool` (the decoder-graph pool cap, measured growth, captured and capped methods).

Packet117 (kept): receipts carry `levers` (anchor_decode, bencode_overlap, prep_ahead) and,
for anchored frame chunks, `conditioning_sources` (per stage: native, precomputed or native-inline, the
wait, and in the graph chain the dual-check result); decode records carry `levers`, `anchor_decode` (cone
or full, the cone's last frame and the display decode's, `equal`), `precompute` (the stage-A/B encodes the
decode thread precomputed for the successor, with their xpu:3 snapshots) and `schedule` (the commit and
sampler-A waits), and the timestamps precompute_a_start/done, go, precompute_b_start/done, display_start/done.

Packet116 (116a scheduling): with the frame anchor the decode thread writes the anchor file right
after the VIDEO decode and hands it to the chain (receipt `decode.state` 'video_done',
`timing_ns.video_done` <= `anchor_ready`); the audio decode, hashing, diagnostics and the decode
record follow on the decode thread, so a stream receipt commits before its decode record. Gated
qualification chunks (eager and graph chains) wait for their whole decode in every anchor mode
(`decode.state` 'done'): nothing is decoded, captured or replayed beside them. Decode records
carry the split timestamps `video_done`, `anchor_ready`, `audio_done`, `hashed`, `record_staged`
(`decode_done` = `audio_done`, both decodes finished) and the `decoder` block (eager or graph
decoder, the qualification's dual decode, captures, signatures); preview records add
`record_written` and `preview_written` behind them.

The chunk receipt is committed at "anchor ready". With an off-chain decode (anchor modes
mixed, latent and guide) that is when the three latents are hashed and the latent (40,960
bytes; mixed uses its stage-A slice) or guide (81,920 bytes) anchor file is fsynced; the decode is still queued on the decode thread, which later commits
`receipts/decode-<run_name>.json` (DECODE_SCHEMA: decoded image and waveform hashes,
the border diagnostic of the last frame, the qualification capture), and the preview
writer behind it commits `receipts/preview-<run_name>.json` (PREVIEW_SCHEMA). With the
frame anchor (LTX_ANCHOR=frame) the decode record is committed before the receipt,
because the anchor is the decoded last frame.

Packet116 mixed anchor: the decode thread also writes chunk n's decoded last frame as a
frame-anchor file (decode record `frame_anchor`); chunk n+1's stage-B condition node waits
for that record (receipt `timing_ns.frame_wait_start` / `frame_ready`) and records what it
consumed in `anchor_in.frame`. Decode records carry the sharpness profile.

A frame anchor file is exactly the 786,432 little-endian F32 bytes of images[frames-1]
([1,256,256,3]); the latent anchor format is in latent_anchor.py. Both are written once
(exclusive create, fsync) and re-read by the consumer, which checks the length,
finiteness and the SHA-256 the authority recorded.
"""
import hashlib
import math
import os
from pathlib import Path
import re
import stat
import struct

import stream_contract as contract

SCHEMA = 'ltx.stream118.chunk-receipt.v1'
DECODE_SCHEMA = 'ltx.stream118.decode-record.v1'
PREVIEW_SCHEMA = 'ltx.stream118.preview-record.v1'
DIAGNOSTIC_SCHEMA = 'ltx.stream113.anchor-border-diagnostic.v1'   # unchanged computation, comparable to 113
BORDER_PX = 16
SHA = re.compile(r'[0-9a-f]{64}')
TIMING_KEYS = ('submit', 'execution_start', 'text_start', 'sampler_a_start', 'stage_a_done', 'upsampler_start',
               'condition_b_start', 'concat_b_start', 'sampler_b_start', 'stage_b_done', 'output_start',
               'anchor_ready', 'decode_queued', 'decode_done', 'preview_written', 'receipt_staged',
               # packet116: mixed anchor wait for the predecessor's decoded frame; guide crops
               'frame_wait_start', 'frame_ready', 'crop_a_start', 'crop_b_start',
               # packet116: the frame anchor's video decode finished (the chain waits for this plus the anchor)
               'video_done',
               # packet118 timing split (measurement only; None when the step did not run)
               'admission_received', 'precheck_done', 'queued', 'executor_entry', 'request_snapshot_start',
               'request_snapshot_done', 'before_request_done', 'stream_text_start', 'anchor_start',
               'condition_a_start', 'condition_a_lookup_done', 'condition_a_done', 'concat_a_start',
               'condition_b_lookup_done', 'condition_b_done')
# Packet118: named sub-buckets of submit_to_sampler_start, (label, start mark, end mark). A bucket whose marks are
# missing (a node absent from the graph, an unanchored chunk) is None; `other` is submit_to_sampler_start minus
# the sum of the buckets that exist, so the split always adds up.
SUBMIT_SPLIT = (
    ('precheck', 'submit', 'precheck_done'),                       # storage, observer, graph parse + compare
    ('comfy_validate_queue', 'precheck_done', 'queued'),           # ComfyUI /prompt: validate_prompt, queue put
    ('queue_to_executor', 'queued', 'executor_entry'),             # prompt worker wake-up
    ('authority_begin', 'executor_entry', 'execution_start'),      # classify again, runtime observer, active row
    ('before_request_checks', 'execution_start', 'request_snapshot_start'),   # drain/check, registry, bindings
    ('request_before_snapshot', 'request_snapshot_start', 'request_snapshot_done'),
    ('before_request_tail', 'request_snapshot_done', 'before_request_done'),
    ('executor_to_first_node', 'before_request_done', 'first_node'),          # graph walk, cache, IS_CHANGED
    ('first_node_to_condition_a', 'first_node', 'condition_a_start'),         # text window/reuse, anchor read
    ('condition_a_lookup', 'condition_a_start', 'condition_a_lookup_done'),   # fixed inputs, precompute take
    ('stage_a_before_snapshot', 'A-before:start', 'A-before:end'),
    ('stage_a_consume', 'A-before:end', 'A-after:start'),                     # native node (precomputed encode)
    ('stage_a_after_snapshot', 'A-after:start', 'A-after:end'),
    ('condition_a_tail', 'condition_a_lookup_done', 'condition_a_done'),      # whole guarded stage (contains the 3 above)
    ('dispatch_to_sampler_a', 'condition_a_done', 'sampler_a_start'),         # 377 concat, guiders, noise, executor
)
# The buckets that tile submit -> sampler A without overlap (condition_a_tail contains the three stage-A parts).
SUBMIT_TILES = ('precheck', 'comfy_validate_queue', 'queue_to_executor', 'authority_begin', 'before_request_checks',
                'request_before_snapshot', 'before_request_tail', 'executor_to_first_node',
                'first_node_to_condition_a', 'condition_a_lookup', 'condition_a_tail', 'dispatch_to_sampler_a')
# Packet118: the predecessor's receipt -> this request's submit (reported in THIS receipt's `turnaround`).
TURNAROUND_SPLIT = (
    ('receipt_staged_to_commit', 'receipt_staged', 'commit'),          # after_request tail, executor, finish
    ('commit_write', 'commit', 'commit_written'),                       # exclusive write + fsync of the receipt
    ('commit_to_first_served', 'commit_written', 'first_served'),       # HTTP visibility (client poll period)
    ('served_to_admission', 'first_served', 'admission_received'),      # client: verify, build graph, POST
    ('admission_parse', 'admission_received', 'submit'))                # body read + JSON parse
SNAPSHOT_LABELS = ('request-before', 'A-before', 'A-after', 'B-before', 'B-after', 'request-after')
EVENT_NODES = {'364': 'text_start', '344': 'sampler_a_start', '367': 'stage_a_done', '348': 'upsampler_start',
               'stream_condition_b': 'condition_b_start', '340': 'concat_b_start', '368': 'sampler_b_start',
               '369': 'stage_b_done', 'stream_output': 'output_start',
               'stream_crop_a': 'crop_a_start', 'stream_crop_b': 'crop_b_start',
               # packet118
               'stream_text': 'stream_text_start', 'stream_anchor': 'anchor_start',
               'stream_condition_a': 'condition_a_start', '377': 'concat_a_start'}
DECODE_TIMING_KEYS = ('submit', 'anchor_ready', 'decode_queued', 'decode_start', 'video_done', 'audio_done',
                      'decode_done', 'hashed', 'record_staged',
                      # packet117 (None unless the lever ran)
                      'precompute_a_start', 'precompute_a_done', 'go', 'precompute_b_start', 'precompute_b_done',
                      'display_start', 'display_done')
OPTIONAL_DECODE_TIMING = ('precompute_a_start', 'precompute_a_done', 'go', 'precompute_b_start',
                          'precompute_b_done', 'display_start', 'display_done')
SOURCES = ('native', 'precomputed', 'native-inline')
PRECOMPUTE_STATES = ('done', 'cancelled', 'superseded', 'scheduled', 'running', 'failed')
PREVIEW_TIMING_KEYS = ('submit', 'video_done', 'anchor_ready', 'audio_done', 'decode_done', 'hashed',
                       'record_written', 'preview_queued', 'write_start', 'preview_written')
DECODER_MODES = ('eager', 'graph')
LATENTS = ('video_latent', 'audio_latent', 'stage_a_latent')
DECODED = ('images', 'waveform')
TENSORS = ('images', 'video_latent', 'audio_latent', 'waveform')   # the four captured tensors
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
    return {'kind': 'frame', 'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest(),
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


def delivery(chunk_index, frames, anchored=None, anchor='mixed'):
    """anchored defaults to chunk_index > 0 (packet112); a reset chunk passes anchored=False.
    Packet116: a guide-anchored chunk generates its frame 0 (the guide sits before it), so it
    delivers every frame, like chunk 0."""
    first = not (chunk_index > 0 if anchored is None else anchored)
    g = contract.geometry(frames)
    if not first and anchor == 'guide':
        return {'frames_total': frames, 'fps': contract.FPS, 'new_frames': frames, 'first_new_frame_index': 0,
                'drop_leading_frames': 0, 'overlap': None,
                'continuity': 'guide tokens at pixel frames -16..-1 carry the predecessor\'s last two latent '
                              'groups; frame 0 is new'}
    return {'frames_total': frames, 'fps': contract.FPS,
            'new_frames': g['new_frames_first_chunk'] if first else g['new_frames_continuation'],
            'first_new_frame_index': 0 if first else 1, 'drop_leading_frames': 0 if first else 1,
            'overlap': None if first else
            'frame 0 continues the predecessor\'s last frame (its frame %d); drop it' % g['anchor_frame_index']}


def seconds(timing, start, end):
    a, b = timing.get(start), timing.get(end)
    return None if a is None or b is None else round((b - a) / 1e9, 6)


def submit_split(timing, snapshots=(), node_starts=None):
    """Packet118: the named sub-buckets of submit -> sampler A start (seconds). `snapshots` are this request's
    snapshot records (label, start_ns, end_ns); `node_starts` maps node id -> first executing event (ns)."""
    marks = dict(timing)
    for row in snapshots or ():
        marks[row['label'] + ':start'], marks[row['label'] + ':end'] = row.get('start_ns'), row.get('end_ns')
    starts = [v for v in (node_starts or {}).values() if type(v) is int]
    lower, upper = marks.get('before_request_done'), marks.get('sampler_a_start')
    inside = sorted(v for v in starts if (lower is None or v >= lower) and (upper is None or v <= upper))
    marks['first_node'] = inside[0] if inside else None
    out = {label: seconds(marks, a, b) for label, a, b in SUBMIT_SPLIT}
    total = seconds(marks, 'submit', 'sampler_a_start')
    tiles = [out[k] for k in SUBMIT_TILES if out[k] is not None]
    out['other'] = None if total is None else round(total - sum(tiles), 6)
    out['total'] = total
    return out


def turnaround_split(marks):
    """Packet118: the predecessor's receipt -> this submit, from marks {receipt_staged, commit, commit_written,
    first_served, admission_received, submit} (ns; any may be None)."""
    out = {label: seconds(marks, a, b) for label, a, b in TURNAROUND_SPLIT}
    out['total'] = seconds(marks, 'receipt_staged', 'submit')
    tiles = [v for k, v in out.items() if k != 'total' and v is not None]
    out['other'] = None if out['total'] is None else round(out['total'] - sum(tiles), 6)
    return out


def summarize_bytes(name, raw, frames):
    """Byte-level summary (used by tests and the fake server)."""
    g = contract.geometry(frames)
    shape = {**g['tensor_shapes'], **g['latent_shapes']}[name]
    require(len(raw) == math.prod(shape) * 4, 'Tensor byte count differs: ' + name)
    finite_f32(raw)
    return {'shape': list(shape), 'dtype': 'torch.float32', 'sha256': hashlib.sha256(raw).hexdigest(),
            'finite': True}


def _tensor_row(row, shape, name):
    require(type(row) is dict and row.get('shape') == shape and row.get('dtype') == 'torch.float32' and
            row.get('finite') is True and type(row.get('sha256')) is str and SHA.fullmatch(row['sha256']),
            'Tensor summary differs: ' + name)


def _anchor_out(out, frames, anchor):
    g = contract.geometry(frames)
    require(type(out) is dict and SHA.fullmatch(out.get('sha256', '')) and out.get('kind') == anchor and
            out.get('dtype') == 'F32' and out.get('byte_order') == 'little' and type(out.get('path')) is str,
            'anchor_out differs')
    if anchor in ('latent', 'mixed'):
        require(out.get('bytes') == contract.LATENT_ANCHOR_BYTES and out.get('slot') == g['latent_anchor_slot'] and
                [r.get('part') for r in out.get('layout', [])] == ['A', 'B'] and
                out['path'].endswith('.latent.f32'), 'Latent anchor_out differs')
        if anchor == 'mixed':
            frame = out.get('frame')
            require(type(frame) is dict and frame.get('writer') == 'decode thread' and
                    type(frame.get('record')) is str and type(frame.get('path')) is str and
                    frame['path'].endswith('.f32') and not frame['path'].endswith('.latent.f32'),
                    'Mixed anchor_out must name the decode thread\'s frame anchor')
    elif anchor == 'guide':
        require(out.get('bytes') == contract.GUIDE_ANCHOR_BYTES and out.get('slot') == g['latent_anchor_slot'] and
                out.get('slots') == [g['latent_anchor_slot'] - 1, g['latent_anchor_slot']] and
                out.get('latent_idx') == contract.GUIDE_LATENT_IDX and
                [r.get('part') for r in out.get('layout', [])] == ['A', 'B'] and
                out['path'].endswith('.guide.f32'), 'Guide anchor_out differs')
    else:
        require(out.get('bytes') == contract.ANCHOR_BYTES and out.get('frame_index') == g['anchor_frame_index'] and
                out.get('shape') == contract.ANCHOR_SHAPE and out['path'].endswith('.f32'), 'Frame anchor_out differs')


def decode_state(kind, anchor):
    """Packet116: what the chain waited for before committing the receipt."""
    if kind in contract.GATED_KINDS:
        return 'done'
    return 'video_done' if anchor == 'frame' else 'queued'


def validate_receipt(r):
    """Schema check used by the server before commit and by clients after reading."""
    require(type(r) is dict and r.get('schema') == SCHEMA, 'Receipt schema differs')
    for key in ('run_name', 'prompt_id', 'kind', 'scene_id', 'prompt_sha256', 'plan_sha256',
                'qualification_id', 'runtime_manifest_sha256', 'server_identity_sha256'):
        require(type(r.get(key)) is str and r[key], 'Receipt field missing: ' + key)
    require(type(r.get('chunk_index')) is int and type(r.get('seed')) is int and type(r.get('stream_seq')) is int,
            'Receipt integers missing')
    require(r.get('frames') in contract.FRAME_CHOICES and r.get('reuse_text') in (0, 1) and
            r.get('anchor') in contract.ANCHORS and r.get('placement') in contract.PLACEMENTS and
            r.get('decoder_graph') in contract.DECODER_GRAPH_CHOICES,
            'Receipt frames/anchor/placement/reuse/decoder_graph missing')
    require(r['kind'] in contract.KINDS and r['run_name'] == contract.run_name(r), 'Receipt identity differs')
    levers = r.get('levers')
    require(type(levers) is dict and set(levers) == set(contract.LEVER_FIELDS), 'Receipt levers missing')
    contract.check_levers(r['anchor'], levers['anchor_decode'], levers['bencode_overlap'], levers['prep_ahead'])
    g = contract.geometry(r['frames'])
    tensors = r.get('tensors')
    require(type(tensors) is dict and set(tensors) == set(LATENTS), 'Exactly the three latents required')
    for name in LATENTS:
        _tensor_row(tensors[name], g['latent_shapes'][name], name)
    _anchor_out(r.get('anchor_out'), r['frames'], r['anchor'])
    anchor_in = r.get('anchor_in')
    reset = r.get('reset')
    anchored = r.get('anchored')
    require(reset in (False, True) and anchored is (r['chunk_index'] > 0 and not reset) and
            (not reset or (r['kind'] == 'stream' and r['chunk_index'] > 0)), 'anchored/reset record differs')
    pred = r.get('reset_predecessor_anchor_sha256')
    require(pred is None if not reset else (pred == '' or (type(pred) is str and SHA.fullmatch(pred))),
            'reset_predecessor_anchor_sha256 differs')
    if r['anchor'] != 'guide' or not anchored:
        require(r.get('guide_pin') is None, 'guide_pin belongs to guide-anchored chunks')
    if not anchored:
        require(anchor_in is None and r.get('slot0_pin') is None, 'An unanchored chunk has no anchor_in')
    else:
        previous = dict(r, chunk_index=r['chunk_index'] - 1, stream_seq=r['stream_seq'] - 1
                        if r['kind'] == 'stream' else -1)
        require(type(anchor_in) is dict and SHA.fullmatch(anchor_in.get('sha256', '')) and
                anchor_in.get('kind') == r['anchor'] and
                anchor_in.get('source_run_name') == contract.run_name(previous),
                'anchor_in must name the immediate predecessor')
        if r['anchor'] == 'mixed':
            frame = anchor_in.get('frame')
            require(type(frame) is dict and SHA.fullmatch(frame.get('sha256', '')) and
                    frame.get('source_run_name') == anchor_in['source_run_name'] and
                    SHA.fullmatch(frame.get('decode_record_sha256', '')) and type(frame.get('path')) is str and
                    type(frame.get('waited_s')) in (int, float) and frame['waited_s'] >= 0 and
                    type(frame.get('decode_sequence')) is int, 'Mixed anchor_in must name the decoded frame it used')
        pin = r.get('slot0_pin')
        want = {'latent': {'A', 'B'}, 'mixed': {'A'}}.get(r['anchor'])
        if want is not None:
            require(type(pin) is dict and set(pin) == want and
                    all(type(v) is dict and v.get('diagnostic_only') is True and type(v.get('bytes_equal')) is bool
                        for v in pin.values()), 'slot0_pin diagnostic differs')
        else:
            require(pin is None, 'Frame- and guide-anchored chunks carry no slot0_pin')
        guide_pin = r.get('guide_pin')
        if r['anchor'] == 'guide':
            require(type(guide_pin) is dict and set(guide_pin) == {'A', 'B'} and
                    all(type(v) is dict and v.get('diagnostic_only') is True and type(v.get('bytes_equal')) is bool
                        for v in guide_pin.values()), 'guide_pin diagnostic differs')
    validate_conditioning_sources(r.get('conditioning_sources'), r['kind'], r['anchor'], anchored, levers)
    validate_measurements(r)
    require(r.get('delivery') == delivery(r['chunk_index'], r['frames'], anchored, r['anchor']),
            'Delivery description differs')
    decode = r.get('decode')
    state = decode_state(r['kind'], r['anchor'])
    require(type(decode) is dict and decode.get('state') == state and
            type(decode.get('record')) is str and Path(decode['record']).name == 'decode-%s.json' % r['run_name'] and
            decode.get('device') == 'xpu:3', 'Decode hand-off record differs')
    preview = r.get('preview')
    require(type(preview) is dict and type(preview.get('path')) is str and preview['path'].endswith('.mp4') and
            Path(preview['path']).is_absolute() and preview.get('state') == 'queued' and
            preview.get('includes_overlap_frame') is (anchored and r['anchor'] in contract.SLOT0_ANCHORS) and
            preview.get('bytes') is None and type(preview.get('record')) is str and
            Path(preview['record']).name == 'preview-%s.json' % r['run_name'],
            'Preview MP4 record differs (receipts commit with the preview queued)')
    for key in ('predecessor_preview', 'predecessor_decode'):
        prior = r.get(key)
        require(prior is None or (type(prior) is dict and type(prior.get('run_name')) is str), key + ' differs')
    capture = r.get('capture')
    if r['kind'] in contract.CAPTURE_KINDS:
        require(type(capture) is dict and capture.get('path', '').endswith('tensors.safetensors') and
                capture.get('writer') == 'decode thread', 'Qualification receipts name their full capture')
    else:
        require(capture is None, 'Stream chunks write no full capture')
    timing = r.get('timing_ns')
    require(type(timing) is dict and set(timing) == set(TIMING_KEYS) and
            all(timing[k] is None or type(timing[k]) is int for k in TIMING_KEYS) and
            timing['preview_written'] is None and type(timing['anchor_ready']) is int and
            type(timing['decode_queued']) is int and
            ((r['anchor'] in contract.OFF_CHAIN_DECODE and timing['video_done'] is None and
              timing['anchor_ready'] <= timing['decode_queued']) or
             (r['anchor'] == 'frame' and type(timing['video_done']) is int and
              timing['decode_queued'] <= timing['video_done'] <= timing['anchor_ready'])) and
            ((state == 'done' and type(timing['decode_done']) is int and
              timing['decode_queued'] <= timing['decode_done']) or
             (state != 'done' and timing['decode_done'] is None)),
            'Timing fields differ')
    if r['anchor'] == 'mixed' and anchored:
        require(type(timing['frame_wait_start']) is int and type(timing['frame_ready']) is int and
                timing['frame_wait_start'] <= timing['frame_ready'], 'Mixed frame wait timing differs')
    else:
        require(timing['frame_wait_start'] is None and timing['frame_ready'] is None,
                'frame_wait_* belong to mixed-anchored chunks')
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


def validate_measurements(r):
    """Packet118: server options, the snapshot records, the timing split and the turnaround block."""
    options = r.get('server_options')
    require(type(options) is dict and set(options) == {'snapshot_mode', 'decoder_graph_pool_cap_bytes'} and
            options['snapshot_mode'] in contract.SNAPSHOT_MODES and
            (options['decoder_graph_pool_cap_bytes'] is None or
             (type(options['decoder_graph_pool_cap_bytes']) is int and options['decoder_graph_pool_cap_bytes'] > 0)),
            'Receipt server_options differ')
    snaps = r.get('snapshots')
    require(type(snaps) is list and all(
        type(s) is dict and s.get('label') in SNAPSHOT_LABELS and s.get('mode') in contract.SNAPSHOT_MODES and
        type(s.get('dual')) is bool and s.get('agree') in (True, None) and (s['agree'] is True) is s['dual'] and
        type(s.get('start_ns')) is int and type(s.get('end_ns')) is int and s['start_ns'] <= s['end_ns']
        for s in snaps), 'Receipt snapshot records differ')
    require(all(s['mode'] == options['snapshot_mode'] for s in snaps), 'Snapshot mode differs from the launch')
    labels = [s['label'] for s in snaps]
    require(labels[:1] == ['request-before'] and labels[-1:] == ['request-after'] and
            labels == sorted(labels, key=SNAPSHOT_LABELS.index), 'Snapshot order differs')
    split = (r.get('timing_s') or {}).get('submit_split')
    require(type(split) is dict and set(split) == {k for k, _, _ in SUBMIT_SPLIT} | {'other', 'total'} and
            all(v is None or type(v) in (int, float) for v in split.values()), 'submit_split differs')
    nodes = r.get('node_starts_ns')
    require(type(nodes) is dict and all(type(k) is str and type(v) is int for k, v in nodes.items()),
            'node_starts_ns differs')
    checks = r.get('authority_checks')
    require(type(checks) is dict and type(checks.get('healthy_calls')) is int and checks['healthy_calls'] >= 0 and
            type(checks.get('healthy_s')) in (int, float), 'authority_checks differ')
    turn = r.get('turnaround')
    require(turn is None or (type(turn) is dict and type(turn.get('predecessor_run_name')) is str and
                             type(turn.get('split')) is dict and type(turn.get('marks_ns')) is dict),
            'turnaround differs')
    return r


def validate_conditioning_sources(sources, kind, anchor, anchored, levers):
    """Packet117: where each anchored frame chunk's stage conditioning took its encode from."""
    if anchor != 'frame' or not anchored:
        require(sources is None, 'conditioning_sources belong to anchored frame chunks')
        return sources
    require(type(sources) is dict and set(sources) == {'A', 'B'}, 'conditioning_sources must name stages A and B')
    for stage, lever in (('A', 'prep_ahead'), ('B', 'bencode_overlap')):
        row = sources[stage]
        on = bool(levers[lever]) and kind != 'qualify-eager'
        require(type(row) is dict and row.get('stage') == stage and row.get('lever') == lever and
                row.get('lever_on') is on and row.get('source') in SOURCES and
                (row['source'] == 'native') is (not on), 'conditioning_sources row differs: ' + stage)
        if row['source'] == 'precomputed':
            pre = row.get('precompute')
            require(type(pre) is dict and pre.get('state') == 'done' and pre.get('stage') == stage and
                    type(row.get('waited_s')) in (int, float) and row['waited_s'] >= 0,
                    'Precomputed source record differs: ' + stage)
            if kind == 'qualify-graph':
                require(row.get('dual_equal') is True, 'Graph-chain precomputed conditioning not dual-checked')
            else:
                require(row.get('dual_equal') is None, 'Only the graph chain dual-checks a precomputed stage')
    return sources


def validate_decode_record(d, receipt=None):
    """Schema of receipts/decode-<run_name>.json; with `receipt`, also its binding to the chunk."""
    require(type(d) is dict and d.get('schema') == DECODE_SCHEMA, 'Decode record schema differs')
    for key in ('run_name', 'prompt_id', 'kind', 'anchor', 'last_frame_sha256'):
        require(type(d.get(key)) is str and d[key], 'Decode record field missing: ' + key)
    require(d.get('frames') in contract.FRAME_CHOICES and d['anchor'] in contract.ANCHORS and
            d.get('device') == 'xpu:3' and d.get('order') == 'fifo' and type(d.get('sequence')) is int and
            d.get('sample_rate') == contract.SAMPLE_RATE and SHA.fullmatch(d['last_frame_sha256']),
            'Decode record values differ')
    g = contract.geometry(d['frames'])
    tensors = d.get('tensors')
    require(type(tensors) is dict and set(tensors) == set(DECODED), 'Decode record must hold images and waveform')
    for name in DECODED:
        _tensor_row(tensors[name], g['decoded_shapes'][name], name)
    validate_diagnostic(d.get('anchor_diagnostics'))
    validate_sharpness(d.get('sharpness'), d['frames'])
    capture = d.get('capture')
    require(capture is None if d['kind'] == 'stream' else
            (type(capture) is dict and capture.get('path', '').endswith('tensors.safetensors') and
             type(capture.get('prewrite')) is dict), 'Decode record capture differs')
    frame = d.get('frame_anchor')
    require((frame is None) if d['anchor'] in ('latent', 'guide') else
            (type(frame) is dict and frame.get('sha256') == d['last_frame_sha256'] and
             frame.get('bytes') == contract.ANCHOR_BYTES and
             type(frame.get('path')) is str and frame['path'].endswith('.f32') and
             not frame['path'].endswith('.latent.f32')),   # packet116: the decode thread writes the frame file
            'Decode record frame anchor differs')
    timing = d.get('timing_ns')
    ints = [k for k in DECODE_TIMING_KEYS if k != 'submit' and k not in OPTIONAL_DECODE_TIMING]
    require(type(timing) is dict and set(timing) == set(DECODE_TIMING_KEYS) and
            all(type(timing[k]) is int for k in ints) and
            all(timing[k] is None or type(timing[k]) is int for k in OPTIONAL_DECODE_TIMING) and
            (timing['submit'] is None or type(timing['submit']) is int) and
            timing['decode_queued'] <= timing['decode_start'] <= timing['video_done'] <= timing['audio_done'] ==
            timing['decode_done'] <= timing['hashed'] <= timing['record_staged'] and
            (d['anchor'] != 'frame' or timing['video_done'] <= timing['anchor_ready'] <= timing['audio_done']),
            'Decode record timing differs')
    chain = [timing[k] for k in ('anchor_ready', 'precompute_a_start', 'precompute_a_done', 'go', 'precompute_b_start',
                                 'precompute_b_done', 'display_start', 'display_done', 'audio_done')
             if timing[k] is not None]
    require(chain == sorted(chain), 'Packet117/118 decode-thread order differs (anchor, A, go, B, display, audio)')
    validate_decoder(d.get('decoder'), d['kind'])
    levers = d.get('levers')
    require(type(levers) is dict and set(levers) == set(contract.LEVER_FIELDS), 'Decode record levers missing')
    contract.check_levers(d['anchor'], levers['anchor_decode'], levers['bencode_overlap'], levers['prep_ahead'])
    validate_anchor_decode(d.get('anchor_decode'), d['kind'], d['anchor'], levers, d['last_frame_sha256'], timing)
    pre = d.get('precompute')
    require(pre is None or (type(pre) is dict and set(pre) <= {'A', 'B'} and
                            all(type(v) is dict and v.get('stage') == s and v.get('state') in PRECOMPUTE_STATES
                                for s, v in pre.items())), 'Decode record precompute differs')
    require(type(d.get('schedule')) is dict, 'Decode record schedule missing')
    if receipt is not None:
        require(d['run_name'] == receipt['run_name'] and d['prompt_id'] == receipt['prompt_id'] and
                d['anchor'] == receipt['anchor'] and d['frames'] == receipt['frames'] and
                timing['decode_queued'] == receipt['timing_ns']['decode_queued'],
                'Decode record does not belong to this receipt')
        if receipt['anchor'] == 'mixed':
            require(receipt['anchor_out']['frame']['path'] == frame['path'],
                    'Mixed frame anchor path differs from the receipt')
        if receipt['anchor'] == 'frame':
            require(receipt['anchor_out']['sha256'] == d['last_frame_sha256'] and
                    receipt['anchor_out']['path'] == frame['path'] and
                    receipt['timing_ns']['video_done'] == timing['video_done'] and
                    receipt['timing_ns']['anchor_ready'] == timing['anchor_ready'],
                    'Frame anchor is not the decoded last frame')
        require(d['decoder']['flag'] == receipt['decoder_graph'], 'Decoder flag differs from the receipt')
        if receipt['timing_ns']['decode_done'] is not None:
            require(receipt['timing_ns']['decode_done'] == timing['decode_done'], 'Decode done time differs')
    return d


def validate_anchor_decode(ad, kind, anchor, levers, last_sha, timing):
    """Packet117 decode-record `anchor_decode` block."""
    cone = anchor == 'frame' and kind != 'qualify-eager' and levers['anchor_decode'] == 'cone'
    require(type(ad) is dict and ad.get('mode') == ('cone' if cone else 'full') and
            ad.get('flag') == levers['anchor_decode'] and ad.get('last_frame_sha256') == last_sha and
            type(ad.get('seconds')) in (int, float), 'anchor_decode record differs')
    if cone:
        require(ad.get('equal') is True and ad.get('display_last_frame_sha256') == last_sha and
                type(ad.get('display_seconds')) in (int, float) and type(timing['display_start']) is int and
                type(timing['display_done']) is int, 'Cone anchor decode record differs (or the check failed)')
    else:
        require(ad.get('equal') is None and ad.get('display_last_frame_sha256') == last_sha and
                timing['display_start'] is None, 'Full anchor decode record differs')
    return ad


def validate_decoder(dec, kind):
    """Packet116 decode-record `decoder` block."""
    require(type(dec) is dict and dec.get('flag') in contract.DECODER_GRAPH_CHOICES and
            dec.get('mode') in DECODER_MODES and
            dec['mode'] == ('graph' if dec['flag'] == 1 and kind != 'qualify-eager' else 'eager') and
            type(dec.get('new_captures')) is int and dec['new_captures'] >= 0 and
            type(dec.get('signatures')) is dict and type(dec.get('video_decode_s')) in (int, float),
            'Decoder record differs')
    ref = dec.get('reference')
    if dec['mode'] == 'graph' and kind == 'qualify-graph':
        require(type(ref) is dict and ref.get('mode') == 'eager-uncached' and ref.get('equal') is True and
                type(ref.get('images_sha256')) is str and SHA.fullmatch(ref['images_sha256']),
                'Graph-chain decode records carry their uncached eager reference')
    else:
        require(ref is None, 'Only graph-chain decodes carry a reference decode')
    if dec['mode'] == 'eager':
        require(dec['new_captures'] == 0, 'An eager decode captured a graph')
    pool = dec.get('pool')
    require(pool is None if dec['flag'] == 0 else (
        type(pool) is dict and (pool.get('cap_bytes') is None or type(pool.get('cap_bytes')) is int) and
        type(pool.get('growth_bytes')) is int and type(pool.get('captured')) is list and
        type(pool.get('capped')) is list and not set(pool['captured']) & set(pool['capped']) and
        (pool['cap_bytes'] is not None or not pool['capped'])), 'Decoder pool record differs (packet118)')
    return dec


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
            timing['video_done'] <= timing['audio_done'] == timing['decode_done'] <= timing['hashed'] <=
            timing['record_written'] <= timing['preview_queued'] <= timing['write_start'] <= timing['preview_written'],
            'Preview record timing differs')
    if receipt is not None:
        require(p['run_name'] == receipt['run_name'] and p['prompt_id'] == receipt['prompt_id'] and
                p['path'] == receipt['preview']['path'], 'Preview record does not belong to this receipt')
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


SHARPNESS_SCHEMA = 'ltx.stream116.sharpness-profile.v1'


def sharpness_reference(raw, height=256, width=256):
    """Stdlib reference of one frame's Laplacian variance (the server computes it with torch in float64;
    tests compare the two). raw: little-endian F32 [H, W, 3]."""
    import array
    import sys
    values = array.array('f')
    values.frombytes(raw)
    if sys.byteorder != 'little':
        values.byteswap()
    require(len(values) == height * width * 3, 'Frame size differs')
    y = [0.2126 * float(values[i]) + 0.7152 * float(values[i + 1]) + 0.0722 * float(values[i + 2])
         for i in range(0, len(values), 3)]
    total = squares = 0.0
    n = 0
    for r in range(1, height - 1):
        for c in range(1, width - 1):
            k = r * width + c
            lap = y[k - width] + y[k + width] + y[k - 1] + y[k + 1] - 4.0 * y[k]
            total += lap
            squares += lap * lap
            n += 1
    mean = total / n
    return max(0.0, squares / n - mean * mean)


def sharpness_from_values(values, frames):
    """values: {frame index: Laplacian variance}. The record the decode thread commits."""
    idx = contract.sharpness_frames(frames)
    require(sorted(values) == idx, 'Sharpness frames differ')
    mid = frames // 2
    ref = values[mid]
    rel = {str(i): (None if ref <= 0 else round(values[i] / ref, 6)) for i in idx}
    head = [rel[str(i)] for i in idx if i <= 5 and rel[str(i)] is not None]
    return {'schema': SHARPNESS_SCHEMA, 'diagnostic_only': True,
            'measure': 'variance of the 4-neighbour Laplacian of Rec.709 luma, float64, interior pixels',
            'frames': idx, 'laplacian_variance': {str(i): round(values[i], 9) for i in idx},
            'reference_frame': mid, 'relative_to_reference': rel,
            'first_frames_min_relative': min(head) if head else None,
            'last_frame_relative': rel[str(frames - 1)]}


def validate_sharpness(d, frames):
    idx = contract.sharpness_frames(frames)
    require(type(d) is dict and d.get('schema') == SHARPNESS_SCHEMA and d.get('diagnostic_only') is True and
            d.get('frames') == idx and d.get('reference_frame') == frames // 2 and
            type(d.get('laplacian_variance')) is dict and set(d['laplacian_variance']) == {str(i) for i in idx} and
            all(type(v) in (int, float) and v >= 0 for v in d['laplacian_variance'].values()) and
            type(d.get('relative_to_reference')) is dict and set(d['relative_to_reference']) == {str(i) for i in idx},
            'Sharpness profile differs')
    return d


def validate_diagnostic(d):
    require(type(d) is dict and d.get('schema') == DIAGNOSTIC_SCHEMA and d.get('diagnostic_only') is True and
            d.get('border_px') == BORDER_PX and all(type(d.get(k)) in (int, float) for k in (
                'border_mean_chroma', 'centre_mean_chroma', 'border_mean_luma', 'centre_mean_luma',
                'border_clipped_fraction', 'centre_clipped_fraction')), 'Anchor diagnostic differs')
    return d
