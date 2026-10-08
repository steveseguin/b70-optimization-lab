"""Packet112 exact-replay qualification decision. Stdlib only; no tensors are converted.

Inputs are the nine committed receipts (eager chain, graph chain, graph repeat)
and an independent re-read of each full capture file. The verdict passes only if,
for every chunk, all four complete tensors are byte-identical across the three
chains (compared by SHA-256 of the complete little-endian F32 payload, computed
twice: by the output node and from the capture file), the anchors chain exactly,
and the graph routes behaved as replay (no capture after the graph chain's first
conditioned chunk, uniform signatures, at most eight per route).
"""
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import struct

import stream_contract as contract

SCHEMA = 'ltx.stream112.qualification-verdict.v1'
MAX_HEADER = 65536
CHAINS = ('qualify-eager', 'qualify-graph', 'qualify-repeat')


def require(ok, why):
    if not ok:
        raise ValueError(why)


def capture_tensor_hashes(path, frames):
    """Single pass over one safetensors capture: per-tensor and frame-24 hashes."""
    path = Path(path)
    require(path.is_absolute() and not any(p.is_symlink() for p in (path, *path.parents)), 'Unsafe capture path')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb', buffering=0) as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, 'Capture is not a single-link file')
        prefix = stream.read(8)
        count = struct.unpack('<Q', prefix)[0]
        require(2 <= count <= MAX_HEADER and count + 8 <= info.st_size, 'Invalid capture header length')
        header = json.loads(stream.read(count))
        g = contract.geometry(frames)
        require(set(header) == set(g['tensor_shapes']), 'Capture must hold exactly the four tensors')
        payload = stream.read()
        require(len(payload) == info.st_size - 8 - count, 'Capture truncated during read')
    whole = hashlib.sha256(prefix + json.dumps(header).encode()).hexdigest()  # informational only
    result = {'path': str(path), 'bytes': info.st_size, 'tensors': {}}
    for name, shape in g['tensor_shapes'].items():
        row = header[name]
        require(row.get('dtype') == 'F32' and row.get('shape') == shape, 'Capture tensor differs: ' + name)
        start, end = row['data_offsets']
        require(end - start == math.prod(shape) * 4 and 0 <= start <= end <= len(payload), 'Capture range differs')
        result['tensors'][name] = hashlib.sha256(payload[start:end]).hexdigest()
    frame = math.prod(g['tensor_shapes']['images'][1:]) * 4
    start = header['images']['data_offsets'][0] + g['anchor_frame_index'] * frame
    result['last_frame_sha256'] = hashlib.sha256(payload[start:start + frame]).hexdigest()
    result['header_digest'] = whole
    return result


def decide(receipts, captures, plan_sha256, frames, text_reuse_mode, placement='two-way', max_signatures=8):
    """receipts: nine committed receipt dicts in execution order.
    captures: {run_name: capture_tensor_hashes(...)}. Returns a verdict dict."""
    failures = []

    def check(ok, why):
        if not ok:
            failures.append(why)
        return ok

    expected = contract.qualification_params(frames, text_reuse_mode, placement)
    if not check(type(receipts) is list and len(receipts) == 9, 'Exactly nine qualification receipts required'):
        return {'schema': SCHEMA, 'passed': False, 'failures': failures, 'plan_sha256': plan_sha256}
    for r, params in zip(receipts, expected):
        name = contract.run_name(params)
        check(r.get('run_name') == name and r.get('kind') == params['kind'] and r.get('frames') == frames and
              r.get('reuse_text') == params['reuse_text'] and
              r.get('chunk_index') == params['chunk_index'] and r.get('seed') == params['seed'] and
              r.get('committed') is True and r.get('plan_sha256') == plan_sha256,
              'Receipt order/identity/commit differs at ' + name)
        check(r.get('sanity') == {'finite': True, 'shapes': True, 'anchor_chain': True}, 'Sanity failed: ' + name)
        cap = captures.get(name)
        if check(type(cap) is dict, 'Capture re-read missing: ' + name):
            for tensor in ('images', 'video_latent', 'audio_latent', 'waveform'):
                check(cap['tensors'].get(tensor) == r['tensors'][tensor]['sha256'],
                      'Capture file and output node disagree: %s/%s' % (name, tensor))
            check(cap['last_frame_sha256'] == r['anchor_out']['sha256'],
                  'Anchor file is not the last frame of the capture: ' + name)
    by_chain = {kind: receipts[i * 3:(i + 1) * 3] for i, kind in enumerate(CHAINS)}
    for kind, chain in by_chain.items():
        for k, r in enumerate(chain):
            if k == 0:
                check(r.get('anchor_in') is None, 'Chunk 0 consumed an anchor: ' + kind)
            else:
                check(type(r.get('anchor_in')) is dict and
                      r['anchor_in'].get('sha256') == chain[k - 1]['anchor_out']['sha256'] and
                      r['anchor_in'].get('source_run_name') == chain[k - 1]['run_name'],
                      'Anchor chain broken at %s chunk %d' % (kind, k))
    pairs = []
    for k in range(3):
        rows = [by_chain[kind][k] for kind in CHAINS]
        same = {t: len({row['tensors'][t]['sha256'] for row in rows}) == 1
                for t in ('images', 'video_latent', 'audio_latent', 'waveform')}
        pairs.append({'chunk': k, 'all_four_identical': all(same.values()), 'per_tensor': same,
                      'anchor_identical': len({row['anchor_out']['sha256'] for row in rows}) == 1})
        check(all(same.values()), 'Eager/graph/repeat tensors differ at chunk %d: %s'
              % (k, sorted(t for t, ok in same.items() if not ok)))
    eager, graph, repeat = (by_chain[kind] for kind in CHAINS)
    for r in eager:
        check(r['graph']['gate_mode'] == 'original' and r['graph']['routes'] == 0 and r['graph']['new_captures'] == 0,
              'Eager chunk observed graph routes: ' + r['run_name'])
    check(graph[0]['graph']['new_captures'] > 0, 'Graph chain chunk 0 captured nothing')
    for r in [graph[2]] + repeat:
        check(r['graph']['new_captures'] == 0, 'Replay-only request captured a new graph: ' + r['run_name'])
    sigs = {r['graph']['signatures_per_route'] for r in graph + repeat}
    final = repeat[-1]['graph']['signatures_per_route']
    check(type(final) is int and 0 < final <= max_signatures and sigs <= set(range(1, max_signatures + 1)),
          'Signature count outside 1..%d' % max_signatures)
    check(all(r['graph']['routes'] == 48 for r in graph + repeat), 'Graph chain did not run 48 routes')
    reuse = bool(text_reuse_mode)
    check([r['text']['reused'] for r in receipts] == [bool(p['reuse_text']) for p in expected],
          'Text reuse pattern differs')
    text_shas = [tuple(t['sha256'] for t in r['text']['tensors']) for r in receipts]
    for k in range(3):
        check(len({text_shas[i * 3 + k] for i in range(3)}) == 1,
              'Text conditioning differs across chains at chunk %d' % k)
    return {'schema': SCHEMA, 'passed': not failures, 'failures': failures, 'plan_sha256': plan_sha256,
            'exact_replay': pairs, 'signatures_per_route': final,
            'masked_chunk_new_captures': graph[1]['graph']['new_captures'],
            'text_reuse': reuse,
            'prompt_cut_at_chunk': 2,
            'text_conditioning_hashes_by_chunk': [list(text_shas[k]) for k in range(3)],
            'text_reuse_bit_identity_evidence': (reuse and not failures),
            'unique_video_frames_per_chain': frames + 2 * (frames - 1),
            'claims': {'seam_quality_accepted': False, 'audio_alignment_resolved': False,
                       'speed_claim': False, 'adopted': False}}
