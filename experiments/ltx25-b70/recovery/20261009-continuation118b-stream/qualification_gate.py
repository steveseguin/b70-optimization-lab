"""Packet118b exact-replay qualification decision. Stdlib only; no tensors are converted.

Packet118b adds two gates. (1) Snapshot rows: every qualification receipt lists its four-card snapshots in the
expected order (request before, stage A before/after and stage B before/after where the anchor mode conditions
through the guard, request after), all in the launch's snapshot mode; with LTX_SNAPSHOT_MODE=fingerprint every one
of them ran the walk beside the fingerprint (dual) and agreed (a disagreement latches before any receipt is
written, so `agree: true` is required). Failures are also listed under `snapshot_failures` (the runtime then writes
the snapshot latch). (2) Decoder pool: with LTX_DECODER_GRAPH_POOL_CAP_GB the graph chain's chunk 0 captured the
methods its decode record lists as captured (1 or 2) and nothing else; captured and capped methods are disjoint
and together are the two decoder methods; without a cap both are captured (packet 117).

Packet117 adds the lever gates (frame anchor): the eager chain runs every lever off (full anchor decode,
native stage-A/B encodes on the prompt thread); with LTX_ANCHOR_DECODE=cone every graph- and repeat-chain
chunk's anchor came from the cone decode and equals its full display decode's last frame (decode record
`anchor_decode.equal`, and independently the capture file's last frame); with LTX_PREP_AHEAD=1 /
LTX_BENCODE_OVERLAP=1 every anchored graph- and repeat-chain chunk conditioned stage A / stage B from the
encode the decode thread precomputed, and in the graph chain that conditioning equals the native one on the
same inputs byte for byte (`dual_equal`). These failures are also listed under `anchor_decode_failures` and
`precompute_failures` (the runtime then writes that lever's latch). Together with the unchanged
eager/graph/repeat byte identity of every tensor this proves the levers change no output.

Inputs are the nine committed receipts (eager chain, graph chain, graph repeat), the
nine decode records the decode thread committed, and an independent re-read of each
full capture file (which the decode thread wrote). The verdict passes only if, for
every chunk, every tensor is byte-identical across the three chains: the three latents
(video, audio and the stage-A latent, hashed by the output node), the anchor file the
chunk wrote, and the decoded images and waveform (hashed by the decode thread); the
capture files agree with both; the anchors chain exactly; and the graph routes behaved
as replay (no capture after the graph chain's first conditioned chunk, uniform
signatures, at most eight per route). The slot-0 pin is reported, never gated.

Packet116 adds two gates. (1) Decoder graph (LTX_DECODER_GRAPH=1): every eager-chain chunk was
decoded by the uncached eager decoder; every graph-chain chunk was decoded twice on the same latents
(uncached eager first, then graph replay) with byte-identical images; every graph- and repeat-chain
chunk used the graph decoder; the graph chain's chunk 0 captured the decoder graphs, nothing after it
captured anything, and each captured method holds exactly one signature. With LTX_DECODER_GRAPH=0
every decode is the uncached eager decode and nothing is captured. These failures are also listed
under `decoder_graph_failures` (the runtime then writes the decoder-graph latch). (2) Cross-packet
reference: for a variant with a recorded reference (frame anchor, 49 frames: packet 113; 97 frames:
packet 114's frame launch) every eager-chain tensor, last frame and anchor file must equal the
reference byte for byte, so the 116a scheduling and the decoder caches provably change no output.

Packet115: with the mixed anchor every anchored chunk must have conditioned stage B on its
predecessor's decoded last frame exactly (anchor_in.frame.sha256 equals the predecessor's
decode-record last frame and its capture's last frame), and the decode thread's frame anchor
equals its capture's last frame. With the guide anchor the anchor file is the 81,920-byte
guide file; it is compared like the latent file. The sharpness profiles are reported, never
gated (they are functions of the gated images).
"""
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import struct

import stream_contract as contract

SCHEMA = 'ltx.stream118.qualification-verdict.v1'
MAX_HEADER = 65536
CHAINS = ('qualify-eager', 'qualify-graph', 'qualify-repeat')
RECEIPT_TENSORS = ('video_latent', 'audio_latent', 'stage_a_latent')
DECODE_TENSORS = ('images', 'waveform')


def require(ok, why):
    if not ok:
        raise ValueError(why)


def capture_tensor_hashes(path, frames):
    """Single pass over one safetensors capture: per-tensor and last-frame hashes."""
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


def decide(receipts, decodes, captures, plan_sha256, frames, text_reuse_mode, placement='two-way',
           anchor=contract.DEFAULT_ANCHOR, max_signatures=8, decoder_graph=contract.DEFAULT_DECODER_GRAPH,
           references=None, levers=None, server_options=None):
    """receipts: nine committed receipt dicts in execution order; decodes: {run_name: decode record};
    captures: {run_name: capture_tensor_hashes(...)}; references: the packet's reference-frame-hashes
    document (or None). Returns a verdict dict."""
    failures = []
    decoder_failures = []
    cone_failures = []
    precompute_failures = []
    snapshot_failures = []
    options = dict(server_options or {'snapshot_mode': 'walk', 'decoder_graph_pool_cap_bytes': None})
    levers = contract._levers(anchor, *(levers if levers is not None else (None, None, None)))
    anchor_decode, bencode_overlap, prep_ahead = levers

    def check(ok, why):
        if not ok:
            failures.append(why)
        return ok

    def check_decoder(ok, why):
        if not ok:
            decoder_failures.append(why)
        return check(ok, why)

    def check_cone(ok, why):
        if not ok:
            cone_failures.append(why)
        return check(ok, why)

    def check_precompute(ok, why):
        if not ok:
            precompute_failures.append(why)
        return check(ok, why)

    def check_snapshot(ok, why):
        if not ok:
            snapshot_failures.append(why)
        return check(ok, why)

    expected = contract.qualification_params(frames, text_reuse_mode, placement, anchor, decoder_graph, *levers)
    if not check(type(receipts) is list and len(receipts) == 9, 'Exactly nine qualification receipts required'):
        return {'schema': SCHEMA, 'passed': False, 'failures': failures, 'plan_sha256': plan_sha256}
    decodes = decodes if type(decodes) is dict else {}
    sequences = []
    for r, params in zip(receipts, expected):
        name = contract.run_name(params)
        check(r.get('run_name') == name and r.get('kind') == params['kind'] and r.get('frames') == frames and
              r.get('anchor') == anchor and r.get('placement') == placement and
              r.get('decoder_graph') == decoder_graph and
              r.get('levers') == dict(zip(contract.LEVER_FIELDS, levers)) and
              r.get('reuse_text') == params['reuse_text'] and
              r.get('chunk_index') == params['chunk_index'] and r.get('seed') == params['seed'] and
              r.get('committed') is True and r.get('plan_sha256') == plan_sha256,
              'Receipt order/identity/commit differs at ' + name)
        check(r.get('sanity') == {'finite': True, 'shapes': True, 'anchor_chain': True}, 'Sanity failed: ' + name)
        d = decodes.get(name)
        if check(type(d) is dict and d.get('run_name') == name and d.get('prompt_id') == r.get('prompt_id'),
                 'Decode record missing or unbound: ' + name):
            sequences.append(d.get('sequence'))
        cap = captures.get(name)
        if check(type(cap) is dict, 'Capture re-read missing: ' + name) and type(d) is dict:
            for tensor in ('video_latent', 'audio_latent'):
                check(cap['tensors'].get(tensor) == r['tensors'][tensor]['sha256'],
                      'Capture file and output node disagree: %s/%s' % (name, tensor))
            for tensor in DECODE_TENSORS:
                check(cap['tensors'].get(tensor) == d['tensors'][tensor]['sha256'],
                      'Capture file and decode thread disagree: %s/%s' % (name, tensor))
            check(cap['last_frame_sha256'] == d.get('last_frame_sha256'),
                  'Decode record last frame is not the capture\'s: ' + name)
            if anchor == 'frame':
                check(cap['last_frame_sha256'] == r['anchor_out']['sha256'],
                      'Frame anchor is not the last frame of the capture: ' + name)
            if anchor == 'mixed':
                check((d.get('frame_anchor') or {}).get('sha256') == cap['last_frame_sha256'],
                      'Mixed frame anchor is not the last frame of the capture: ' + name)
    check(sequences == sorted(sequences) and len(set(sequences)) == len(sequences),
          'Decode records are not in submission order')
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
                if anchor == 'mixed':
                    pred = chain[k - 1]['run_name']
                    frame = (r.get('anchor_in') or {}).get('frame') or {}
                    check(frame.get('sha256') is not None and
                          frame.get('sha256') == (decodes.get(pred) or {}).get('last_frame_sha256') and
                          frame.get('sha256') == (captures.get(pred) or {}).get('last_frame_sha256'),
                          'Mixed stage B did not use its predecessor\'s decoded last frame at %s chunk %d' % (kind, k))
    pairs = []
    for k in range(3):
        rows = [by_chain[kind][k] for kind in CHAINS]
        recs = [decodes.get(row['run_name']) or {} for row in rows]
        same = {t: len({row['tensors'][t]['sha256'] for row in rows}) == 1 for t in RECEIPT_TENSORS}
        same.update({t: len({(rec.get('tensors') or {}).get(t, {}).get('sha256') for rec in recs}) == 1 and
                     all(rec.get('tensors') for rec in recs) for t in DECODE_TENSORS})
        same['anchor_file'] = len({row['anchor_out']['sha256'] for row in rows}) == 1
        if anchor == 'mixed' and k > 0:
            same['frame_anchor_in'] = len({((row.get('anchor_in') or {}).get('frame') or {}).get('sha256')
                                          for row in rows}) == 1
        pairs.append({'chunk': k, 'all_identical': all(same.values()), 'per_tensor': same,
                      'slot0_pin': [row.get('slot0_pin') for row in rows]})
        check(all(same.values()), 'Eager/graph/repeat tensors differ at chunk %d: %s'
              % (k, sorted(t for t, ok in same.items() if not ok)))
        if decoder_graph and all(same[t] for t in RECEIPT_TENSORS) and not all(same[t] for t in DECODE_TENSORS):
            # Identical latents, different decoded tensors: the decoder is the only difference.
            decoder_failures.append('Decoded tensors differ across chains on identical latents at chunk %d '
                                    '(decoder graph)' % k)
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
    # -- packet116: the decoder graph -------------------------------------------------------------
    graph_rows = []
    for kind in CHAINS:
        for k, r in enumerate(by_chain[kind]):
            d = (decodes.get(r['run_name']) or {}).get('decoder') or {}
            want_mode = 'graph' if decoder_graph and kind != 'qualify-eager' else 'eager'
            ref = d.get('reference')
            row = {'run_name': r['run_name'], 'mode': d.get('mode'), 'new_captures': d.get('new_captures'),
                   'reference_equal': None if ref is None else ref.get('equal'), 'signatures': d.get('signatures')}
            graph_rows.append(row)
            check_decoder(d.get('flag') == decoder_graph and d.get('mode') == want_mode,
                          'Decoder mode differs at %s (flag %r mode %r, expected %s)'
                          % (r['run_name'], d.get('flag'), d.get('mode'), want_mode))
            if decoder_graph and kind == 'qualify-graph':
                check_decoder(type(ref) is dict and ref.get('mode') == 'eager-uncached' and ref.get('equal') is True and
                              ref.get('images_sha256') == ((decodes.get(r['run_name']) or {}).get('tensors') or {})
                              .get('images', {}).get('sha256'),
                              'Graph decode is not byte-identical to the uncached eager decode of the same latents: '
                              + r['run_name'])
            else:
                check_decoder(ref is None, 'Unexpected dual decode at ' + r['run_name'])
            first_capture = bool(decoder_graph) and kind == 'qualify-graph' and k == 0
            pool = d.get('pool') or {}
            row['pool'] = {key: pool.get(key) for key in ('cap_bytes', 'growth_bytes', 'captured', 'capped')} \
                if pool else None
            if first_capture:
                cap = options.get('decoder_graph_pool_cap_bytes')
                captured, capped = list(pool.get('captured') or []), list(pool.get('capped') or [])
                want = 2 if cap is None else len(captured)
                check_decoder(pool.get('cap_bytes') == cap and sorted(captured + capped) ==
                              ['forward_diff_step', 'forward_pre_diffusion'] and 1 <= want <= 2 and
                              (cap is not None or not capped),
                              'Decoder pool record differs at the graph chain chunk 0: %r' % (row['pool'],))
                check_decoder(type(d.get('new_captures')) is int and d['new_captures'] == want,
                              'Graph chain chunk 0 did not capture the %d decoder graph(s) it lists: %r'
                              % (want, d.get('new_captures')))
            else:
                check_decoder(d.get('new_captures') == 0, 'Decoder graph captured after the graph chain\'s chunk 0: '
                              + r['run_name'])
            if want_mode == 'graph':
                check_decoder(d.get('signatures') == {'forward_pre_diffusion': 1, 'forward_diff_step': 1},
                              'Decoder graph signatures differ at %s: %r' % (r['run_name'], d.get('signatures')))
    # -- packet117: the levers ----------------------------------------------------------------------
    lever_rows = []
    for kind in CHAINS:
        for k, r in enumerate(by_chain[kind]):
            d = decodes.get(r['run_name']) or {}
            ad = d.get('anchor_decode') or {}
            live = anchor == 'frame' and kind != 'qualify-eager'
            want_cone = live and anchor_decode == 'cone'
            sources = r.get('conditioning_sources') or {}
            row = {'run_name': r['run_name'], 'anchor_decode': ad.get('mode'), 'cone_equal': ad.get('equal'),
                   'sources': {s: (sources.get(s) or {}).get('source') for s in ('A', 'B')} if sources else None,
                   'dual_equal': {s: (sources.get(s) or {}).get('dual_equal') for s in ('A', 'B')} if sources else None,
                   'precompute_waited_s': {s: (sources.get(s) or {}).get('waited_s') for s in ('A', 'B')}
                   if sources else None}
            lever_rows.append(row)
            check_cone(ad.get('mode') == ('cone' if want_cone else 'full'),
                       'Anchor decode mode differs at %s (%r)' % (r['run_name'], ad.get('mode')))
            if want_cone:
                check_cone(ad.get('equal') is True and ad.get('last_frame_sha256') == r['anchor_out']['sha256'] ==
                           ad.get('display_last_frame_sha256') ==
                           (captures.get(r['run_name']) or {}).get('last_frame_sha256'),
                           'Cone anchor frame is not the full decode\'s last frame at ' + r['run_name'])
            if anchor != 'frame' or k == 0:
                continue
            for stage, on in (('A', prep_ahead), ('B', bencode_overlap)):
                src = sources.get(stage) or {}
                if not live or not on:
                    check_precompute(src.get('source') == 'native',
                                     'Stage %s of %s should use the native encode' % (stage, r['run_name']))
                    continue
                check_precompute(src.get('source') == 'precomputed',
                                 'Stage %s of %s did not use the precomputed encode (%r: %r)'
                                 % (stage, r['run_name'], src.get('source'), src.get('reason')))
                if kind == 'qualify-graph':
                    check_precompute(src.get('dual_equal') is True,
                                     'Precomputed stage-%s conditioning differs from the native one at %s'
                                     % (stage, r['run_name']))
    # -- packet118b: the four-card snapshot rows ------------------------------------------------------
    snapshot_rows = []
    mode = options.get('snapshot_mode')
    for kind in CHAINS:
        for k, r in enumerate(by_chain[kind]):
            snaps = r.get('snapshots') or []
            labels = [s.get('label') for s in snaps]
            anchored = k > 0
            middle = {'frame': ['A-before', 'A-after', 'B-before', 'B-after'],
                      'mixed': ['B-before', 'B-after']}.get(anchor, []) if anchored else []
            want = ['request-before'] + middle + ['request-after']
            snapshot_rows.append({'run_name': r['run_name'], 'labels': labels,
                                  'modes': sorted({s.get('mode') for s in snaps}),
                                  'dual': [s.get('dual') for s in snaps], 'agree': [s.get('agree') for s in snaps],
                                  'seconds': [s.get('seconds') for s in snaps]})
            check_snapshot(labels == want, 'Snapshot sequence differs at %s: %r (expected %r)'
                           % (r['run_name'], labels, want))
            check_snapshot(all(s.get('mode') == mode for s in snaps), 'Snapshot mode differs at ' + r['run_name'])
            if mode == 'fingerprint':
                check_snapshot(all(s.get('dual') is True and s.get('agree') is True for s in snaps),
                               'A qualification snapshot did not run (or agree with) the walk at ' + r['run_name'])
            else:
                check_snapshot(all(s.get('dual') is False for s in snaps),
                               'Walk-mode snapshots ran a fingerprint at ' + r['run_name'])
    # -- packet116: cross-packet reference (frame anchor) -------------------------------------------
    reference_rows = None
    ref_variant = '%d/%s/%s' % (frames, placement, anchor)
    table = ((references or {}).get('variants') or {}).get(ref_variant)
    if table is not None:
        reference_rows = []
        for k, r in enumerate(eager):
            want = table['chunks'][k]
            d = decodes.get(r['run_name']) or {}
            have = {'video_latent': r['tensors']['video_latent']['sha256'],
                    'audio_latent': r['tensors']['audio_latent']['sha256'],
                    'stage_a_latent': r['tensors']['stage_a_latent']['sha256'],
                    'images': ((d.get('tensors') or {}).get('images') or {}).get('sha256'),
                    'waveform': ((d.get('tensors') or {}).get('waveform') or {}).get('sha256'),
                    'last_frame': d.get('last_frame_sha256'), 'anchor_file': r['anchor_out']['sha256']}
            same = {t: have[t] == want[t] for t in want if t != 'source_run_name'}
            reference_rows.append({'chunk': k, 'reference_run_name': want.get('source_run_name'), 'per_tensor': same})
            check(all(same.values()), 'Eager chain differs from the packet-%s reference at chunk %d: %s'
                  % (table.get('source_packet'), k, sorted(t for t, ok in same.items() if not ok)))
    overlap = [dict(r.get('decode_at_start') or {}, run_name=r['run_name']) for r in receipts]
    for r, row in zip(receipts, overlap):
        if r['kind'] in contract.GATED_KINDS:
            check(row.get('drained') is True and row.get('pending') == 0,
                  'Decode thread was not drained before a gated request: ' + r['run_name'])
    return {'schema': SCHEMA, 'passed': not failures, 'failures': failures, 'plan_sha256': plan_sha256,
            'frames': frames, 'placement': placement, 'anchor': anchor, 'decoder_graph': decoder_graph,
            'decoder_graph_rows': graph_rows, 'decoder_graph_failures': decoder_failures,
            'levers': dict(zip(contract.LEVER_FIELDS, levers)), 'lever_rows': lever_rows,
            'anchor_decode_failures': cone_failures, 'precompute_failures': precompute_failures,
            'server_options': options, 'snapshot_rows': snapshot_rows, 'snapshot_failures': snapshot_failures,
            'reference_variant': ref_variant, 'reference_check': reference_rows,
            'reference_source': None if table is None else {'packet': table.get('source_packet'),
                                                            'verdict': table.get('source_verdict'),
                                                            'verdict_sha256': table.get('source_verdict_sha256')},
            'exact_replay': pairs, 'signatures_per_route': final,
            'masked_chunk_new_captures': graph[1]['graph']['new_captures'],
            'text_reuse': reuse,
            'prompt_cut_at_chunk': 2,
            'text_conditioning_hashes_by_chunk': [list(text_shas[k]) for k in range(3)],
            'text_reuse_bit_identity_evidence': (reuse and not failures),
            'decode_overlap': overlap,
            'mixed_frame_wait_s': ([[((r.get('anchor_in') or {}).get('frame') or {}).get('waited_s')
                                     for r in by_chain[kind]] for kind in CHAINS] if anchor == 'mixed' else None),
            'sharpness_relative_by_chunk': [[((decodes.get(r['run_name']) or {}).get('sharpness') or {})
                                             .get('relative_to_reference') for r in by_chain[kind]]
                                            for kind in CHAINS],
            'unique_video_frames_per_chain': frames + 2 * (frames - 1),
            'claims': {'seam_quality_accepted': False, 'audio_alignment_resolved': False,
                       'speed_claim': False, 'adopted': False}}
