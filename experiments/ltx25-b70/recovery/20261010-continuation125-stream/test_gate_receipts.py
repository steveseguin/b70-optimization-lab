"""CPU tests (packet117): qualification gate (with the decoder-graph, cross-packet reference and lever checks),
capture re-read, receipt / decode-record / preview-record schemas (116a timestamps, the 117 lever blocks), and
frame-anchor files."""
import copy
import hashlib
import json
import math
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import qualification_gate as gate  # noqa: E402
import stream_contract as c  # noqa: E402
import stream_receipts as rec  # noqa: E402

PLAN = 'p' * 64
LATENTS = ('video_latent', 'audio_latent', 'stage_a_latent')
DECODED = ('images', 'waveform')
DIAG = rec.border_diagnostic_reference(struct.pack('<f', 0.5) * (c.ANCHOR_BYTES // 4))


def h(*parts):
    return hashlib.sha256(repr(parts).encode()).hexdigest()


def sharpness(frames):
    return rec.sharpness_from_values({i: 1.0 + i / 100 for i in c.sharpness_frames(frames)}, frames)


def anchor_out(name, sha, frames, anchor):
    g = c.geometry(frames)
    if anchor in ('latent', 'mixed'):
        out = {'kind': anchor, 'path': '/run/anchors/' + name + '.latent.f32', 'sha256': sha,
               'bytes': c.LATENT_ANCHOR_BYTES, 'slot': g['latent_anchor_slot'], 'dtype': 'F32', 'byte_order': 'little',
               'layout': [{'part': 'A'}, {'part': 'B'}]}
        if anchor == 'mixed':
            out['frame'] = {'writer': 'decode thread', 'path': '/run/anchors/' + name + '.f32',
                            'record': '/run/receipts/decode-' + name + '.json'}
        return out
    if anchor == 'guide':
        s = g['latent_anchor_slot']
        return {'kind': 'guide', 'path': '/run/anchors/' + name + '.guide.f32', 'sha256': sha,
                'bytes': c.GUIDE_ANCHOR_BYTES, 'slot': s, 'slots': [s - 1, s], 'latent_idx': -2, 'dtype': 'F32',
                'byte_order': 'little', 'layout': [{'part': 'A'}, {'part': 'B'}]}
    return {'kind': 'frame', 'path': '/run/anchors/' + name + '.f32', 'sha256': sha, 'bytes': c.ANCHOR_BYTES,
            'frame_index': g['anchor_frame_index'], 'shape': c.ANCHOR_SHAPE, 'dtype': 'F32', 'byte_order': 'little'}


def pin(stages=('A', 'B')):
    row = {'bytes_equal': True, 'elements': 2048, 'differing_elements': 0, 'differing_all_signed_zero': True,
           'anchor_negative_zeros': 0, 'output_negative_zeros': 0, 'output_finite': True, 'diagnostic_only': True}
    return {s: dict(row) for s in stages}


def lever_tuple(params):
    return tuple(params[k] for k in c.LEVER_FIELDS)


def sources(params, anchor):
    """Packet117 conditioning_sources as the runtime records them for a passing chunk."""
    if anchor != 'frame' or not c.anchored(params):
        return None
    out = {}
    for stage, lever in (('A', 'prep_ahead'), ('B', 'bencode_overlap')):
        live = bool(params[lever]) and params['kind'] != 'qualify-eager'
        out[stage] = {'stage': stage, 'lever': lever, 'lever_on': live,
                      'source': 'precomputed' if live else 'native', 'reason': None,
                      'waited_s': 0.01 if live else None,
                      'dual_equal': True if live and params['kind'] == 'qualify-graph' else None,
                      'precompute': {'stage': stage, 'state': 'done', 'anchor_sha256': 'a' * 64} if live else None}
    return out


def snapshot_labels(params, anchor):
    """Packet123: the four-card snapshots the runtime takes for one request, in order."""
    middle = {'frame': ['A-before', 'A-after', 'B-before', 'B-after'],
              'mixed': ['B-before', 'B-after']}.get(anchor, []) if c.anchored(params) else []
    return ['request-before'] + middle + ['request-after']


def snapshots(params, anchor, mode='walk', dual=None):
    dual = (mode == 'fingerprint') if dual is None else dual
    return [{'synchronized': ['xpu:0', 'xpu:1', 'xpu:2', 'xpu:3'],
             'memory_cards': ['xpu:0', 'xpu:1', 'xpu:2', 'xpu:3'], 'label': label, 'mode': mode, 'dual': dual, 'agree': True if dual else None, 'start_ns': 100 + i,
             'end_ns': 101 + i, 'seconds': 1e-9, 'parts_s': {}, 'min_margin_bytes': 2 ** 31}
            for i, label in enumerate(snapshot_labels(params, anchor))]


def receipt(params, frames, anchor, latents, anchor_sha, anchor_in=None, new_captures=0, routes=48, sigs=4,
            reused=False, text='t', drained=None, snapshot_mode='walk', pool_cap=None):
    g = c.geometry(frames)
    name = c.run_name(params)
    k = params['chunk_index']
    anchored = c.anchored(params)
    timing = {key: None for key in rec.TIMING_KEYS}
    state = rec.decode_state(params['kind'], anchor)
    if anchor in c.OFF_CHAIN_DECODE:
        timing.update(anchor_ready=10, decode_queued=11)
    else:
        timing.update(decode_queued=10, video_done=20, anchor_ready=21)
    if state == 'done':
        timing.update(decode_done=30)
    if anchor == 'mixed' and anchored:
        timing.update(frame_wait_start=5, frame_ready=6)
    return {
        'schema': rec.SCHEMA, 'run_name': name, 'prompt_id': 'pid-' + name, 'kind': params['kind'],
        'scene_id': params['scene_id'], 'chunk_index': k, 'seed': params['seed'], 'stream_seq': params['stream_seq'],
        'prompt_sha256': c.text_sha256(params['prompt']), 'frames': frames, 'placement': params['placement'],
        'anchor': anchor, 'decoder_graph': params['decoder_graph'], 'reuse_text': params['reuse_text'],
        'levers': {k: params[k] for k in c.LEVER_FIELDS}, 'conditioning_sources': sources(params, anchor),
        'plan_sha256': PLAN, 'qualification_id': c.qualification_id(frames, params['placement'], anchor,
                                                                    params['decoder_graph'], *lever_tuple(params)),
        'runtime_manifest_sha256': 'r' * 64, 'server_identity_sha256': 's' * 64, 'committed': True,
        'tensors': {t: {'shape': g['latent_shapes'][t], 'dtype': 'torch.float32', 'finite': True,
                        'sha256': latents[t]} for t in LATENTS},
        'anchor_in': anchor_in, 'anchor_out': anchor_out(name, anchor_sha, frames, anchor),
        'slot0_pin': (pin() if anchor == 'latent' else pin(('A',)) if anchor == 'mixed' else None) if anchored else None,
        'guide_pin': pin() if (anchored and anchor == 'guide') else None,
        'anchored': anchored, 'reset': bool(params['reset']),
        'reset_predecessor_anchor_sha256': params['predecessor_anchor_sha256'] if params['reset'] else None,
        'delivery': rec.delivery(k, frames, anchored, anchor),
        'decode': {'state': state, 'device': 'xpu:3',
                   'record': '/run/receipts/decode-' + name + '.json'},
        'preview': {'path': '/out/' + name + '/preview_00001_.mp4', 'bytes': None, 'state': 'queued',
                    'includes_overlap_frame': anchored and anchor in c.SLOT0_ANCHORS,
                    'record': '/run/receipts/preview-' + name + '.json'},
        'predecessor_preview': None, 'predecessor_decode': None,
        'decode_at_start': {'drained': params['kind'] in c.GATED_KINDS if drained is None else drained,
                            'pending': 0, 'current': None},
        'capture': ({'path': '/out/validation/' + name + '/tensors.safetensors', 'writer': 'decode thread'}
                    if params['kind'] in c.CAPTURE_KINDS else None),
        'timing_ns': timing,
        'sanity': {'finite': True, 'shapes': True, 'anchor_chain': True},
        'text': {'reused': reused, 'tensors': [{'sha256': h('text', text)}]},
        'graph': {'gate_mode': 'original' if params['kind'] == 'qualify-eager' else 'graph',
                  'routes': routes, 'new_captures': new_captures, 'signatures_per_route': sigs},
        'memory': {}, 'storage': {'allowance_bytes': 3 * 2**30, 'accounting': 'run-owned-st_blocks-v1'},
        # packet123
        'server_options': {'run_write_allowance_bytes': 3 * 2**30, 'display_schedule': 'sampler-a', 'anchor_read_ahead': 0, 'snapshot_schedule': 'full', 'display_device': 'xpu:3', 'snapshot_mode': snapshot_mode, 'decoder_graph_pool_cap_bytes': pool_cap},
        'snapshots': snapshots(params, anchor, snapshot_mode), 'node_starts_ns': {},
        'timing_s': {'submit_split': rec.submit_split(timing)}, 'turnaround': None,
        'authority_checks': {'healthy_calls': 12, 'healthy_s': 0.05, 'plan_digest_s': 0.04, 'window': 'x'}}


def decoder_block(r, images_sha):
    flag = r['decoder_graph']
    graph = flag == 1 and r['kind'] != 'qualify-eager'
    first = graph and r['kind'] == 'qualify-graph' and r['chunk_index'] == 0
    cap = (r.get('server_options') or {}).get('decoder_graph_pool_cap_bytes')
    pool = None if not flag else {'cap_bytes': cap, 'growth_bytes': 3 * 10 ** 9,
                                  'captured': ['forward_diff_step', 'forward_pre_diffusion'] if cap is None else
                                  ['forward_pre_diffusion'],
                                  'capped': [] if cap is None else ['forward_diff_step'], 'capped_calls': {}}
    return {'pool': pool, 'flag': flag, 'mode': 'graph' if graph else 'eager',
            'reference': ({'mode': 'eager-uncached', 'equal': True, 'images_sha256': images_sha, 'seconds': 0.9}
                          if graph and r['kind'] == 'qualify-graph' else None),
            'video_decode_s': 0.5, 'new_captures': ((2 if cap is None else 1) if first else 0),
            'captured_graphs_total': (2 if cap is None else 1) if graph else 0,
            'signatures': ({'forward_pre_diffusion': 1, 'forward_diff_step': 1} if graph else
                           ({'forward_pre_diffusion': 0, 'forward_diff_step': 0} if flag else {})),
            'replays': {}, 'frozen': False if flag else None}


def decode_record(r, decoded, last_sha, sequence):
    g = c.geometry(r['frames'])
    levers = r['levers']
    cone = r['anchor'] == 'frame' and r['kind'] != 'qualify-eager' and levers['anchor_decode'] == 'cone'
    timing = {k: None for k in rec.DECODE_TIMING_KEYS}
    timing.update({'submit': None, 'anchor_ready': r['timing_ns']['anchor_ready'],
                   'decode_queued': r['timing_ns']['decode_queued'], 'decode_start': 15,
                   'video_done': 20, 'audio_done': 30, 'decode_done': 30, 'hashed': 31, 'record_staged': 32})
    if cone:
        timing.update(go=23, display_start=25, display_done=28)
    frame_mode = r['anchor'] == 'frame'
    frame_anchor = None
    if frame_mode:
        frame_anchor = {'sha256': last_sha, 'bytes': c.ANCHOR_BYTES, 'path': r['anchor_out']['path']}
    elif r['anchor'] == 'mixed':
        frame_anchor = {'sha256': last_sha, 'bytes': c.ANCHOR_BYTES, 'path': r['anchor_out']['frame']['path']}
    return {'schema': rec.DECODE_SCHEMA, 'run_name': r['run_name'], 'prompt_id': r['prompt_id'], 'kind': r['kind'],
            'stream_seq': r['stream_seq'], 'chunk_index': r['chunk_index'], 'frames': r['frames'],
            'anchor': r['anchor'], 'device': 'xpu:3', 'order': 'fifo', 'sequence': sequence, 'thread': 'ltx120-decode',
            'sample_rate': 48000,
            'tensors': {t: {'shape': g['decoded_shapes'][t], 'dtype': 'torch.float32', 'finite': True,
                            'sha256': decoded[t]} for t in DECODED},
            'last_frame_sha256': last_sha, 'anchor_diagnostics': copy.deepcopy(DIAG),
            'sharpness': sharpness(r['frames']),
            'capture': ({'path': '/out/validation/%s/tensors.safetensors' % r['run_name'], 'prewrite': {}}
                        if r['kind'] != 'stream' else None),
            'frame_anchor': frame_anchor, 'decoder': decoder_block(r, decoded['images']),
            'levers': dict(levers),
            'anchor_decode': {'mode': 'cone' if cone else 'full', 'flag': levers['anchor_decode'],
                              'last_frame_sha256': last_sha, 'seconds': 0.3,
                              'display_seconds': 0.5 if cone else None, 'display_last_frame_sha256': last_sha,
                              'equal': True if cone else None},
            'precompute': None, 'schedule': {'gated': r['kind'] in c.GATED_KINDS},
            'timing_ns': timing, 'timing_s': {}}


def passing(frames=49, reuse=1, anchor=c.DEFAULT_ANCHOR, decoder_graph=c.DEFAULT_DECODER_GRAPH, levers=None,
            snapshot_mode='walk', pool_cap=None):
    rows = c.qualification_params(frames, reuse, 'two-way20-28', anchor, decoder_graph, *(levers or (None,) * 3))
    receipts, decodes, captures = [], {}, {}
    for i, params in enumerate(rows):
        chain, k = divmod(i, 3)
        latents = {t: h(t, k) for t in LATENTS}
        decoded = {t: h(t, k) for t in DECODED}
        last = h('last', k)
        anchor_sha = last if anchor == 'frame' else h('latent-anchor', k)
        anchor_in = None if k == 0 else {'kind': anchor, 'sha256': (h('last', k - 1) if anchor == 'frame' else
                                                                    h('latent-anchor', k - 1)),
                                         'source_run_name': c.run_name(rows[i - 1]), 'path': '/x'}
        if anchor == 'mixed' and k:
            anchor_in['frame'] = {'sha256': h('last', k - 1), 'source_run_name': c.run_name(rows[i - 1]),
                                  'decode_record_sha256': h('record', i - 1), 'path': '/x.f32', 'waited_s': 0.25,
                                  'decode_sequence': i}
        eager = chain == 0
        r = receipt(params, frames, anchor, latents, anchor_sha, anchor_in,
                    new_captures=(0 if eager else (96 if (chain, k) in ((1, 0), (1, 1)) else 0)),
                    routes=0 if eager else 48, sigs=0 if eager else 4,
                    reused=bool(params['reuse_text']), text=params['prompt'], snapshot_mode=snapshot_mode,
                    pool_cap=pool_cap if decoder_graph else None)
        receipts.append(r)
        decodes[r['run_name']] = decode_record(r, decoded, last, i + 1)
        captures[r['run_name']] = {'tensors': {'images': decoded['images'], 'waveform': decoded['waveform'],
                                               'video_latent': latents['video_latent'],
                                               'audio_latent': latents['audio_latent']},
                                   'last_frame_sha256': last}
    return receipts, decodes, captures


def decide(receipts, decodes, captures, frames=49, reuse=1, anchor=c.DEFAULT_ANCHOR,
           decoder_graph=c.DEFAULT_DECODER_GRAPH, references=None, levers=None, server_options=None):
    options = server_options or receipts[0].get('server_options')
    return gate.decide(receipts, decodes, captures, PLAN, frames, reuse, 'two-way20-28', anchor,
                       decoder_graph=decoder_graph, references=references, levers=levers, server_options=options)


def reference_doc(receipts, decodes, frames=49, anchor='frame', placement='two-way20-28', packet=113):
    """A reference document built from the eager chain of `receipts` (the shape of the sealed file)."""
    rows = []
    for r in receipts[:3]:
        d = decodes[r['run_name']]
        rows.append({'source_run_name': 'old-' + r['run_name'], 'video_latent': r['tensors']['video_latent']['sha256'],
                     'audio_latent': r['tensors']['audio_latent']['sha256'],
                     'images': d['tensors']['images']['sha256'], 'waveform': d['tensors']['waveform']['sha256'],
                     'last_frame': d['last_frame_sha256'], 'anchor_file': r['anchor_out']['sha256']})
    return {'schema': 'ltx.stream116.reference-frame-hashes.v1',
            'variants': {'%d/%s/%s' % (frames, placement, anchor): {'source_packet': packet, 'chunks': rows,
                                                                     'source_verdict': '/v', 'verdict_passed': True,
                                                                     'source_verdict_sha256': 'v' * 64}}}


class Gate(unittest.TestCase):
    def test_passes_when_all_identical(self):
        for frames in (49, 97, 121, 145):  #169 auxiliary scope is covered by test_aux_runtime123
            for anchor in c.ANCHORS:
                for reuse in (0, 1):
                    for dg in c.DECODER_GRAPH_CHOICES:
                        receipts, decodes, captures = passing(frames, reuse, anchor, dg)
                        for r in receipts:
                            rec.validate_receipt(r)
                            rec.validate_decode_record(decodes[r['run_name']], r)
                        verdict = decide(receipts, decodes, captures, frames, reuse, anchor, dg)
                        self.assertTrue(verdict['passed'], verdict['failures'])
                        self.assertEqual(verdict['decoder_graph_failures'], [])
                        self.assertIsNone(verdict['reference_check'])     # no reference passed
                    self.assertTrue(all(p['all_identical'] for p in verdict['exact_replay']))
                    self.assertEqual(verdict['unique_video_frames_per_chain'], frames + 2 * (frames - 1))
                    self.assertEqual(verdict['schema'], 'ltx.stream118.qualification-verdict.v1')

    def test_any_latent_or_anchor_byte_difference_fails(self):
        for t in LATENTS:
            receipts, decodes, captures = passing()
            receipts[7]['tensors'][t]['sha256'] = h('different')
            if t != 'stage_a_latent':
                captures[receipts[7]['run_name']]['tensors'][t] = h('different')
            verdict = decide(receipts, decodes, captures)
            self.assertFalse(verdict['passed'])
            self.assertTrue(any('differ at chunk 1' in f and t in f for f in verdict['failures']), verdict['failures'])
        receipts, decodes, captures = passing()
        receipts[8]['anchor_out']['sha256'] = h('other anchor')
        verdict = decide(receipts, decodes, captures)
        self.assertTrue(any('anchor_file' in f for f in verdict['failures']))

    def test_any_decode_thread_difference_fails(self):
        for t in DECODED:
            receipts, decodes, captures = passing()
            decodes[receipts[5]['run_name']]['tensors'][t]['sha256'] = h('different')
            captures[receipts[5]['run_name']]['tensors'][t] = h('different')
            verdict = decide(receipts, decodes, captures)
            self.assertFalse(verdict['passed'])
            self.assertTrue(any('differ at chunk 2' in f for f in verdict['failures']))

    def test_capture_must_agree_with_output_node_and_decode_thread(self):
        for key in ('video_latent', 'images', 'waveform'):
            receipts, decodes, captures = passing()
            captures[receipts[2]['run_name']]['tensors'][key] = h('other')
            self.assertFalse(decide(receipts, decodes, captures)['passed'])
        receipts, decodes, captures = passing()
        captures[receipts[2]['run_name']]['last_frame_sha256'] = h('other')
        self.assertFalse(decide(receipts, decodes, captures)['passed'])
        receipts, decodes, captures = passing(anchor='frame')
        receipts[1]['anchor_out']['sha256'] = h('not the frame')
        self.assertFalse(decide(receipts, decodes, captures, anchor='frame')['passed'])

    def test_decode_records_present_bound_and_in_order(self):
        receipts, decodes, captures = passing()
        decodes.pop(receipts[4]['run_name'])
        self.assertFalse(decide(receipts, decodes, captures)['passed'])
        receipts, decodes, captures = passing()
        decodes[receipts[4]['run_name']]['prompt_id'] = 'someone else'
        self.assertFalse(decide(receipts, decodes, captures)['passed'])
        receipts, decodes, captures = passing()
        a, b = receipts[3]['run_name'], receipts[4]['run_name']
        decodes[a]['sequence'], decodes[b]['sequence'] = decodes[b]['sequence'], decodes[a]['sequence']
        verdict = decide(receipts, decodes, captures)
        self.assertTrue(any('submission order' in f for f in verdict['failures']))

    def test_gated_requests_require_a_drained_decode_thread(self):
        receipts, decodes, captures = passing()
        receipts[3]['decode_at_start'] = {'drained': False, 'pending': 1, 'current': receipts[2]['run_name']}
        verdict = decide(receipts, decodes, captures)
        self.assertTrue(any('not drained' in f for f in verdict['failures']))
        receipts, decodes, captures = passing()
        receipts[7]['decode_at_start'] = {'drained': False, 'pending': 1, 'current': receipts[6]['run_name']}
        verdict = decide(receipts, decodes, captures)          # the repeat chain overlaps: allowed, recorded
        self.assertTrue(verdict['passed'], verdict['failures'])
        self.assertEqual(verdict['decode_overlap'][7]['pending'], 1)

    def test_anchor_chain_must_use_own_predecessor(self):
        receipts, decodes, captures = passing()
        receipts[4]['anchor_in']['source_run_name'] = receipts[0]['run_name']
        self.assertFalse(decide(receipts, decodes, captures)['passed'])
        receipts, decodes, captures = passing()
        receipts[3]['anchor_in'] = {'sha256': h('x'), 'source_run_name': 'y'}
        self.assertFalse(decide(receipts, decodes, captures)['passed'])

    def test_replay_only_requests_must_not_capture(self):
        for index in (5, 6, 7, 8):
            receipts, decodes, captures = passing()
            receipts[index]['graph']['new_captures'] = 1
            self.assertFalse(decide(receipts, decodes, captures)['passed'])

    def test_eager_chain_must_not_see_routes_and_signature_ceiling(self):
        receipts, decodes, captures = passing()
        receipts[1]['graph']['routes'] = 48
        self.assertFalse(decide(receipts, decodes, captures)['passed'])
        receipts, decodes, captures = passing()
        for r in receipts[3:]:
            r['graph']['signatures_per_route'] = 9
        self.assertFalse(decide(receipts, decodes, captures)['passed'])

    def test_text_pattern_and_conditioning_identity(self):
        receipts, decodes, captures = passing(reuse=1)
        receipts[4]['text']['reused'] = False
        self.assertFalse(decide(receipts, decodes, captures)['passed'])
        receipts, decodes, captures = passing(reuse=1)
        receipts[7]['text']['tensors'] = [{'sha256': h('drift')}]
        verdict = decide(receipts, decodes, captures)
        self.assertFalse(verdict['passed'])
        self.assertFalse(verdict['text_reuse_bit_identity_evidence'])

    def test_identity_count_and_order(self):
        receipts, decodes, captures = passing()
        self.assertFalse(decide(receipts[:8], decodes, captures)['passed'])
        receipts, decodes, captures = passing()
        receipts[3], receipts[6] = receipts[6], receipts[3]
        self.assertFalse(decide(receipts, decodes, captures)['passed'])
        receipts, decodes, captures = passing()
        self.assertFalse(decide(receipts, decodes, captures, anchor='latent')['passed'])   # wrong anchor variant
        self.assertFalse(decide(receipts, decodes, captures, decoder_graph=0)['passed'])   # wrong decoder variant
        self.assertFalse(gate.decide(receipts, decodes, captures, PLAN, 49, 1, 'two-way', 'latent')['passed'])


class DecoderGraphGate(unittest.TestCase):
    """Packet116: the decoder-graph rows of the verdict."""
    def failures(self, mutate, dg=1, anchor='frame'):
        receipts, decodes, captures = passing(anchor=anchor, decoder_graph=dg)
        mutate(receipts, decodes)
        verdict = decide(receipts, decodes, captures, anchor=anchor, decoder_graph=dg)
        self.assertFalse(verdict['passed'])
        self.assertTrue(verdict['decoder_graph_failures'], verdict['failures'])
        return verdict['decoder_graph_failures']

    def test_rows_and_modes(self):
        receipts, decodes, captures = passing()
        verdict = decide(receipts, decodes, captures)
        self.assertEqual([r['mode'] for r in verdict['decoder_graph_rows']], ['eager'] * 3 + ['graph'] * 6)
        self.assertEqual([r['new_captures'] for r in verdict['decoder_graph_rows']], [0, 0, 0, 2, 0, 0, 0, 0, 0])
        self.assertEqual([r['reference_equal'] for r in verdict['decoder_graph_rows']],
                         [None] * 3 + [True] * 3 + [None] * 3)
        off = decide(*passing(decoder_graph=0), decoder_graph=0)
        self.assertTrue(off['passed'], off['failures'])
        self.assertEqual([r['mode'] for r in off['decoder_graph_rows']], ['eager'] * 9)

    def name(self, receipts, i):
        return receipts[i]['run_name']

    def test_mismatch_and_missing_reference_fail(self):
        def unequal(receipts, decodes):
            decodes[self.name(receipts, 4)]['decoder']['reference']['equal'] = False
        self.assertIn('not byte-identical', self.failures(unequal)[0])

        def other_sha(receipts, decodes):
            decodes[self.name(receipts, 5)]['decoder']['reference']['images_sha256'] = h('x')
        self.assertIn('not byte-identical', self.failures(other_sha)[0])

        def dropped(receipts, decodes):
            decodes[self.name(receipts, 3)]['decoder']['reference'] = None
        self.failures(dropped)

        def extra(receipts, decodes):
            decodes[self.name(receipts, 7)]['decoder']['reference'] = {'mode': 'eager-uncached', 'equal': True}
        self.assertIn('Unexpected dual decode', self.failures(extra)[0])

    def test_modes_captures_and_signatures(self):
        def eager_graph(receipts, decodes):
            decodes[self.name(receipts, 1)]['decoder']['mode'] = 'graph'
        self.assertIn('Decoder mode differs', self.failures(eager_graph)[0])

        def repeat_eager(receipts, decodes):
            decodes[self.name(receipts, 8)]['decoder']['mode'] = 'eager'
        self.failures(repeat_eager)

        def late_capture(receipts, decodes):
            decodes[self.name(receipts, 6)]['decoder']['new_captures'] = 2
        self.assertIn('captured after', self.failures(late_capture)[0])

        def no_capture(receipts, decodes):
            decodes[self.name(receipts, 3)]['decoder']['new_captures'] = 0
        self.assertIn('did not capture', self.failures(no_capture)[0])

        def two_sigs(receipts, decodes):
            decodes[self.name(receipts, 8)]['decoder']['signatures'] = {'forward_pre_diffusion': 2,
                                                                       'forward_diff_step': 1}
        self.assertIn('signatures differ', self.failures(two_sigs)[0])

        def flag(receipts, decodes):
            decodes[self.name(receipts, 0)]['decoder']['flag'] = 0
        self.failures(flag)

        def off_capture(receipts, decodes):
            decodes[self.name(receipts, 3)]['decoder']['new_captures'] = 2
        self.failures(off_capture, dg=0)

    def test_every_anchor_mode_carries_the_decoder_gate(self):
        for anchor in c.ANCHORS:
            def unequal(receipts, decodes):
                decodes[receipts[3]['run_name']]['decoder']['reference']['equal'] = False
            self.failures(unequal, anchor=anchor)


class CrossPacketReference(unittest.TestCase):
    """Packet116: the eager chain of a frame-anchor launch equals the recorded 113/114 frame qualification."""
    def test_equal_reference_passes_and_any_difference_fails(self):
        receipts, decodes, captures = passing(anchor='frame')
        doc = reference_doc(receipts, decodes)
        verdict = decide(receipts, decodes, captures, references=doc)
        self.assertTrue(verdict['passed'], verdict['failures'])
        self.assertEqual(len(verdict['reference_check']), 3)
        self.assertEqual(verdict['reference_source']['packet'], 113)
        for k in range(3):
            for t in ('video_latent', 'audio_latent', 'images', 'waveform', 'last_frame', 'anchor_file'):
                bad = copy.deepcopy(doc)
                bad['variants']['49/two-way20-28/frame']['chunks'][k][t] = h('old')
                verdict = decide(receipts, decodes, captures, references=bad)
                self.assertFalse(verdict['passed'])
                self.assertTrue(any('packet-113 reference at chunk %d' % k in f and t in f
                                    for f in verdict['failures']), verdict['failures'])
        with_stage_a = copy.deepcopy(doc)
        with_stage_a['variants']['49/two-way20-28/frame']['chunks'][0]['stage_a_latent'] = h('x')
        self.assertFalse(decide(receipts, decodes, captures, references=with_stage_a)['passed'])

    def test_reference_applies_only_to_its_variant(self):
        receipts, decodes, captures = passing(anchor='latent')
        doc = reference_doc(*passing(anchor='frame')[:2])
        for t in doc['variants']['49/two-way20-28/frame']['chunks']:
            t['images'] = h('other')
        verdict = decide(receipts, decodes, captures, anchor='latent', references=doc)
        self.assertTrue(verdict['passed'], verdict['failures'])
        self.assertIsNone(verdict['reference_check'])

    def test_sealed_reference_document(self):
        doc = json.loads((Path(__file__).resolve().parent / 'reference-frame-qualification-hashes.json').read_text())
        self.assertEqual(doc['schema'], 'ltx.stream116.reference-frame-hashes.v1')
        self.assertEqual(sorted(doc['variants']), ['145/two-way20-28/frame', '49/two-way20-28/frame', '97/two-way20-28/frame'])
        self.assertEqual(doc['variants']['49/two-way20-28/frame']['source_packet'], 113)
        self.assertEqual(doc['variants']['97/two-way20-28/frame']['source_packet'], 114)
        for v in doc['variants'].values():
            self.assertEqual(len(v['chunks']), 3)
            for row in v['chunks']:
                self.assertEqual(row['last_frame'], row['anchor_file'])      # frame anchor = decoded last frame
                for key, value in row.items():
                    if key != 'source_run_name':
                        self.assertRegex(value, '^[0-9a-f]{64}$')
        # chunk 0 is unanchored: identical in the 113 frame and 114 latent qualifications (49 frames)
        self.assertEqual(doc['variants']['49/two-way20-28/frame']['chunks'][0]['last_frame'],
                         'c7c773b2c92549f7143085a9fff999f879de5d8bba2884965f713fb332b4fc28')


class CaptureReread(unittest.TestCase):
    def test_reads_safetensors_layout(self):
        for frames in (49, 97, 121, 145):  #169 auxiliary scope is covered by test_aux_runtime123
            g = c.geometry(frames)
            header, offset, blobs = {}, 0, {}
            for i, name in enumerate(sorted(g['tensor_shapes'])):
                shape = g['tensor_shapes'][name]
                size = math.prod(shape) * 4
                blobs[name] = (bytes([i + 1]) * size)
                header[name] = {'dtype': 'F32', 'shape': shape, 'data_offsets': [offset, offset + size]}
                offset += size
            raw = json.dumps(header).encode()
            raw += b' ' * (-len(raw) % 8)
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'tensors.safetensors'
                path.write_bytes(struct.pack('<Q', len(raw)) + raw + b''.join(blobs[n] for n in sorted(blobs)))
                result = gate.capture_tensor_hashes(path, frames)
            for name in g['tensor_shapes']:
                self.assertEqual(result['tensors'][name], hashlib.sha256(blobs[name]).hexdigest())
            frame = c.ANCHOR_BYTES
            last = g['anchor_frame_index']
            self.assertEqual(result['last_frame_sha256'],
                             hashlib.sha256(blobs['images'][last * frame:(last + 1) * frame]).hexdigest())


class Receipts(unittest.TestCase):
    def sample(self, kind='stream', k=3, reset=0, anchor='latent', frames=49):
        if kind == 'stream':
            params = c.stream_params(frames, k, 'boat', 1, 'a' * 64 if k else '', 's', reset=reset, anchor=anchor)
            prev = dict(params, stream_seq=k - 1, chunk_index=k - 1)
        else:
            params = c.qualification_params(frames, 0, anchor=anchor)[k]
            prev = dict(params, chunk_index=k - 1)
        latents = {t: h(t) for t in LATENTS}
        anchor_in = ({'kind': anchor, 'sha256': 'a' * 64, 'source_run_name': c.run_name(prev), 'path': '/a'}
                     if k and not reset else None)
        if anchor_in is not None and anchor == 'mixed':
            anchor_in['frame'] = {'sha256': 'f' * 64, 'source_run_name': c.run_name(prev), 'path': '/a.f32',
                                  'decode_record_sha256': 'e' * 64, 'waited_s': 0.0, 'decode_sequence': 3}
        return receipt(params, frames, anchor, latents, h('a'), anchor_in)

    def test_valid_stream_and_qualification(self):
        for anchor in c.ANCHORS:
            for frames in (49, 97, 121, 145):  #169 auxiliary scope is covered by test_aux_runtime123
                rec.validate_receipt(self.sample(anchor=anchor, frames=frames))
                rec.validate_receipt(self.sample(k=0, anchor=anchor, frames=frames))
                rec.validate_receipt(self.sample('qualify', 1, anchor=anchor, frames=frames))

    def test_schema_violations(self):
        bad = [
            lambda r: r['tensors'].pop('stage_a_latent'),
            lambda r: r['tensors'].__setitem__('images', r['tensors']['video_latent']),
            lambda r: r['tensors']['video_latent'].__setitem__('finite', False),
            lambda r: r['tensors']['video_latent'].__setitem__('shape', [1, 128, 13, 8, 8]),
            lambda r: r.__setitem__('anchor_in', None),
            lambda r: r['anchor_in'].__setitem__('source_run_name', 'stream112-s00000002'),
            lambda r: r['anchor_in'].__setitem__('kind', 'frame'),
            lambda r: r['anchor_out'].__setitem__('bytes', c.ANCHOR_BYTES),
            lambda r: r['anchor_out'].__setitem__('kind', 'frame'),
            lambda r: r.__setitem__('slot0_pin', None),
            lambda r: r.__setitem__('capture', {'path': '/x/tensors.safetensors', 'writer': 'decode thread'}),
            lambda r: r['delivery'].__setitem__('new_frames', 49),
            lambda r: r['timing_ns'].pop('preview_written'),
            lambda r: r['timing_ns'].__setitem__('preview_written', 5),
            lambda r: r['timing_ns'].__setitem__('decode_done', 50),           # latent: done later, in the record
            lambda r: r['timing_ns'].__setitem__('anchor_ready', None),
            lambda r: r['timing_ns'].__setitem__('decode_queued', 1),          # latent: anchor before the hand-off
            lambda r: r['decode'].__setitem__('state', 'done'),
            lambda r: r['decode'].__setitem__('record', '/run/receipts/decode-other.json'),
            lambda r: r['preview'].__setitem__('bytes', 1000),
            lambda r: r['preview'].__setitem__('state', 'written'),
            lambda r: r.__setitem__('anchored', False),
            lambda r: r.__setitem__('reset', True),
            lambda r: r.__setitem__('anchor', 'pixel'),
            lambda r: r['sanity'].__setitem__('anchor_chain', False),
            lambda r: r['preview'].__setitem__('path', 'relative.mp4'),
            lambda r: r['text'].__setitem__('reused', True),
            lambda r: r['graph'].__setitem__('gate_mode', 'original'),
        ]
        for mutate in bad:
            r = copy.deepcopy(self.sample())
            mutate(r)
            with self.assertRaises((ValueError, KeyError, TypeError)):
                rec.validate_receipt(r)

    def test_frame_mode_timing_and_decode_state(self):
        r = self.sample(anchor='frame')
        rec.validate_receipt(r)
        self.assertEqual((r['decode']['state'], r['timing_ns']['decode_done']), ('video_done', None))
        q = self.sample('qualify', 1, anchor='frame')
        rec.validate_receipt(q)
        self.assertEqual(q['decode']['state'], 'done')                # gated chunks wait for the whole decode
        for mutate in (lambda r: r['timing_ns'].__setitem__('video_done', None),
                       lambda r: r['timing_ns'].__setitem__('video_done', 22),     # after anchor_ready
                       lambda r: r['timing_ns'].__setitem__('decode_done', 30),    # the record is not committed yet
                       lambda r: r['decode'].__setitem__('state', 'queued'),
                       lambda r: r['decode'].__setitem__('state', 'done'),
                       lambda r: r.__setitem__('decoder_graph', None),
                       lambda r: r.__setitem__('slot0_pin', pin())):
            x = copy.deepcopy(r)
            mutate(x)
            with self.assertRaises((ValueError, KeyError, TypeError)):
                rec.validate_receipt(x)

    def test_reset_receipts(self):
        r = self.sample(reset=1)
        rec.validate_receipt(r)
        self.assertEqual((r['anchored'], r['reset'], r['anchor_in'], r['delivery']['drop_leading_frames']),
                         (False, True, None, 0))
        bad = [lambda r: r.__setitem__('anchor_in', {'kind': 'latent', 'sha256': 'a' * 64,
                                                     'source_run_name': 'stream125-s00000002'}),
               lambda r: r.__setitem__('anchored', True),
               lambda r: r['delivery'].__setitem__('drop_leading_frames', 1),
               lambda r: r.__setitem__('slot0_pin', pin()),
               lambda r: r.__setitem__('reset_predecessor_anchor_sha256', 'zz')]
        for mutate in bad:
            x = copy.deepcopy(r)
            mutate(x)
            with self.assertRaises((ValueError, KeyError, TypeError)):
                rec.validate_receipt(x)

    def test_delivery(self):
        self.assertEqual(rec.delivery(0, 49)['new_frames'], 49)
        d = rec.delivery(5, 97)
        self.assertEqual((d['new_frames'], d['first_new_frame_index'], d['drop_leading_frames']), (96, 1, 1))
        self.assertEqual(rec.delivery(1, 49)['new_frames'], 48)
        self.assertEqual(rec.delivery(7, 97, anchored=False)['new_frames'], 97)


class DecodeAndPreviewRecords(unittest.TestCase):
    def test_decode_record_and_binding(self):
        receipts, decodes, _ = passing(97, 1, 'latent')
        r, d = receipts[1], decodes[receipts[1]['run_name']]
        rec.validate_decode_record(d, r)
        bad = [lambda d: d['tensors'].pop('waveform'),
               lambda d: d['tensors']['images'].__setitem__('shape', [49, 256, 256, 3]),
               lambda d: d.__setitem__('device', 'xpu:2'),
               lambda d: d.__setitem__('capture', None),
               lambda d: d.__setitem__('frame_anchor', {'sha256': d['last_frame_sha256'], 'bytes': c.ANCHOR_BYTES}),
               lambda d: d['timing_ns'].__setitem__('decode_start', 1),
               lambda d: d.pop('anchor_diagnostics'),
               lambda d: d.__setitem__('schema', 'ltx.stream113.preview-record.v1')]
        for mutate in bad:
            x = copy.deepcopy(d)
            mutate(x)
            with self.assertRaises((ValueError, KeyError, TypeError)):
                rec.validate_decode_record(x, r)
        other = copy.deepcopy(d)
        other['prompt_id'] = 'other'
        with self.assertRaises(ValueError):
            rec.validate_decode_record(other, r)
        receipts, decodes, _ = passing(49, 1, 'frame')
        r, d = receipts[2], decodes[receipts[2]['run_name']]
        rec.validate_decode_record(d, r)
        x = copy.deepcopy(r)
        x['timing_ns']['decode_done'] = 19
        with self.assertRaises(ValueError):
            rec.validate_decode_record(d, x)
        for mutate in (lambda r: r['timing_ns'].__setitem__('anchor_ready', 22),
                       lambda r: r['timing_ns'].__setitem__('video_done', 19),
                       lambda r: r['anchor_out'].__setitem__('path', '/run/anchors/other.f32'),
                       lambda r: r.__setitem__('decoder_graph', 0)):
            x = copy.deepcopy(r)
            mutate(x)
            with self.assertRaises(ValueError):
                rec.validate_decode_record(d, x)

    def test_decode_record_116a_timestamps_and_decoder_block(self):
        receipts, decodes, _ = passing(49, 1, 'frame')
        for i, r in enumerate(receipts):
            d = decodes[r['run_name']]
            rec.validate_decode_record(d, r)
            self.assertEqual(d['decoder']['mode'], 'eager' if i < 3 else 'graph')
        d = decodes[receipts[4]['run_name']]
        bad = [lambda d: d['timing_ns'].pop('audio_done'),
               lambda d: d['timing_ns'].__setitem__('audio_done', 29),               # decode_done = audio_done
               lambda d: d['timing_ns'].__setitem__('hashed', 29),
               lambda d: d['timing_ns'].__setitem__('record_staged', 30),
               lambda d: d['timing_ns'].__setitem__('anchor_ready', 31),             # frame: before the audio
               lambda d: d['timing_ns'].__setitem__('video_done', 14),
               lambda d: d.pop('decoder'),
               lambda d: d['decoder'].__setitem__('mode', 'eager'),
               lambda d: d['decoder'].__setitem__('reference', None),
               lambda d: d['decoder']['reference'].__setitem__('equal', False),
               lambda d: d['decoder'].__setitem__('new_captures', -1),
               lambda d: d['decoder'].__setitem__('flag', 2)]
        for mutate in bad:
            x = copy.deepcopy(d)
            mutate(x)
            with self.assertRaises((ValueError, KeyError, TypeError)):
                rec.validate_decode_record(x, receipts[4])
        eager = copy.deepcopy(decodes[receipts[1]['run_name']])
        eager['decoder']['new_captures'] = 1
        with self.assertRaises(ValueError):
            rec.validate_decode_record(eager, receipts[1])
        repeat = copy.deepcopy(decodes[receipts[7]['run_name']])
        repeat['decoder']['reference'] = {'mode': 'eager-uncached', 'equal': True, 'images_sha256': 'a' * 64}
        with self.assertRaises(ValueError):
            rec.validate_decode_record(repeat, receipts[7])

    def test_preview_record(self):
        r = Receipts().sample()
        p = {'schema': rec.PREVIEW_SCHEMA, 'run_name': r['run_name'], 'prompt_id': r['prompt_id'],
             'path': r['preview']['path'], 'relative_to_output_directory': 'x/preview_00001_.mp4', 'bytes': 10,
             'sha256': 'b' * 64, 'container': 'mp4', 'written': True, 'order': 'fifo',
             'timing_ns': {'submit': None, 'video_done': 20, 'anchor_ready': 21, 'audio_done': 30,
                           'decode_done': 30, 'hashed': 31, 'record_written': 33, 'preview_queued': 34,
                           'write_start': 35, 'preview_written': 40}}
        rec.validate_preview_record(p, r)
        for mutate in (lambda p: p['timing_ns'].__setitem__('decode_done', 35),
                       lambda p: p['timing_ns'].pop('decode_done'),
                       lambda p: p['timing_ns'].pop('record_written'),
                       lambda p: p['timing_ns'].__setitem__('record_written', 36),    # the record precedes the MP4
                       lambda p: p['timing_ns'].__setitem__('hashed', 29),
                       lambda p: p.__setitem__('bytes', 0),
                       lambda p: p.__setitem__('path', '/elsewhere.mp4')):
            x = copy.deepcopy(p)
            mutate(x)
            with self.assertRaises((ValueError, KeyError, TypeError)):
                rec.validate_preview_record(x, r)


class AnchorFiles(unittest.TestCase):
    def test_frame_anchor_roundtrip_and_refusals(self):
        raw = struct.pack('<f', 0.5) * (c.ANCHOR_BYTES // 4)
        with tempfile.TemporaryDirectory() as tmp:
            meta = rec.write_anchor(Path(tmp), 'stream125-s00000000', raw, 97)
            self.assertEqual((meta['kind'], meta['frame_index']), ('frame', 96))
            self.assertEqual(rec.read_anchor(meta['path'], meta['sha256']), raw)
            with self.assertRaises(ValueError):
                rec.read_anchor(meta['path'], 'b' * 64)
            with self.assertRaises(FileExistsError):
                rec.write_anchor(Path(tmp), 'stream125-s00000000', raw, 49)
            with self.assertRaises(ValueError):
                rec.write_anchor(Path(tmp), 'short', raw[:-4], 49)
            nan = struct.pack('<I', 0x7fc00000) + raw[4:]
            with self.assertRaises(ValueError):
                rec.write_anchor(Path(tmp), 'nan', nan, 49)
            link = Path(tmp) / 'link.f32'
            os.symlink(meta['path'], link)
            with self.assertRaises((ValueError, OSError)):
                rec.read_anchor(str(link), meta['sha256'])


class MixedAndGuide(unittest.TestCase):
    """Packet116: what the gate and the schemas require of the mixed and guide anchors."""
    def test_mixed_stage_b_must_use_the_predecessors_decoded_frame(self):
        receipts, decodes, captures = passing(anchor='mixed')
        self.assertTrue(decide(receipts, decodes, captures, anchor='mixed')['passed'])
        receipts[4]['anchor_in']['frame']['sha256'] = h('another frame')
        verdict = decide(receipts, decodes, captures, anchor='mixed')
        self.assertTrue(any('decoded last frame' in f for f in verdict['failures']), verdict['failures'])
        receipts, decodes, captures = passing(anchor='mixed')
        decodes[receipts[3]['run_name']]['frame_anchor']['sha256'] = h('not the capture frame')
        verdict = decide(receipts, decodes, captures, anchor='mixed')
        self.assertTrue(any('Mixed frame anchor is not the last frame' in f for f in verdict['failures']))
        verdict = decide(*passing(anchor='mixed'), anchor='mixed')
        self.assertEqual(verdict['mixed_frame_wait_s'], [[None, 0.25, 0.25]] * 3)
        self.assertEqual(len(verdict['sharpness_relative_by_chunk']), 3)
        self.assertIn('frame_anchor_in', verdict['exact_replay'][1]['per_tensor'])

    def test_mixed_receipt_schema(self):
        r = Receipts().sample(anchor='mixed')
        rec.validate_receipt(r)
        self.assertEqual((r['delivery']['drop_leading_frames'], set(r['slot0_pin'])), (1, {'A'}))
        bad = [lambda r: r['anchor_in'].pop('frame'),
               lambda r: r['anchor_in']['frame'].__setitem__('source_run_name', 'stream125-s00000001'),
               lambda r: r['anchor_in']['frame'].__setitem__('waited_s', -1),
               lambda r: r['anchor_out'].pop('frame'),
               lambda r: r['anchor_out']['frame'].__setitem__('writer', 'output node'),
               lambda r: r.__setitem__('slot0_pin', pin()),
               lambda r: r['timing_ns'].__setitem__('frame_ready', None),
               lambda r: r['timing_ns'].__setitem__('frame_ready', 4),
               lambda r: r['timing_ns'].__setitem__('decode_done', 30),
               lambda r: r['preview'].__setitem__('includes_overlap_frame', False),
               lambda r: r.__setitem__('guide_pin', pin())]
        for mutate in bad:
            x = copy.deepcopy(r)
            mutate(x)
            with self.assertRaises((ValueError, KeyError, TypeError)):
                rec.validate_receipt(x)
        first = Receipts().sample(k=0, anchor='mixed')
        rec.validate_receipt(first)
        x = copy.deepcopy(first)
        x['timing_ns'].update(frame_wait_start=1, frame_ready=2)       # an unanchored chunk never waits
        with self.assertRaises(ValueError):
            rec.validate_receipt(x)

    def test_guide_receipt_schema_and_delivery(self):
        r = Receipts().sample(anchor='guide', frames=97)
        rec.validate_receipt(r)
        self.assertEqual((r['delivery']['new_frames'], r['delivery']['drop_leading_frames'],
                          r['preview']['includes_overlap_frame'], r['slot0_pin']), (97, 0, False, None))
        self.assertEqual(r['anchor_out']['bytes'], 81920)
        bad = [lambda r: r.__setitem__('guide_pin', None),
               lambda r: r.__setitem__('slot0_pin', pin()),
               lambda r: r['delivery'].__setitem__('drop_leading_frames', 1),
               lambda r: r.__setitem__('delivery', rec.delivery(3, 97, True, 'latent')),
               lambda r: r['anchor_out'].__setitem__('bytes', c.LATENT_ANCHOR_BYTES),
               lambda r: r['anchor_out'].__setitem__('latent_idx', 0),
               lambda r: r['anchor_out'].__setitem__('path', '/run/anchors/x.latent.f32'),
               lambda r: r['preview'].__setitem__('includes_overlap_frame', True)]
        for mutate in bad:
            x = copy.deepcopy(r)
            mutate(x)
            with self.assertRaises((ValueError, KeyError, TypeError)):
                rec.validate_receipt(x)
        self.assertEqual(rec.delivery(3, 49, True, 'guide')['new_frames'], 49)
        self.assertEqual(rec.delivery(3, 49, True, 'mixed')['new_frames'], 48)
        self.assertEqual(rec.delivery(0, 49, False, 'guide')['new_frames'], 49)

    def test_guide_gate_compares_the_guide_file(self):
        receipts, decodes, captures = passing(97, 1, 'guide')
        self.assertTrue(decide(receipts, decodes, captures, 97, 1, 'guide')['passed'])
        receipts[8]['anchor_out']['sha256'] = h('other guide')
        verdict = decide(receipts, decodes, captures, 97, 1, 'guide')
        self.assertTrue(any('anchor_file' in f for f in verdict['failures']))

    def test_decode_record_sharpness_and_mixed_frame(self):
        receipts, decodes, _ = passing(49, 1, 'mixed')
        r, d = receipts[4], decodes[receipts[4]['run_name']]
        rec.validate_decode_record(d, r)
        for mutate in (lambda d: d.pop('sharpness'),
                       lambda d: d['sharpness'].__setitem__('frames', [0, 1]),
                       lambda d: d['frame_anchor'].pop('path'),
                       lambda d: d.__setitem__('frame_anchor', None),
                       lambda d: d['frame_anchor'].__setitem__('path', '/elsewhere.f32')):
            x = copy.deepcopy(d)
            mutate(x)
            with self.assertRaises((ValueError, KeyError, TypeError)):
                rec.validate_decode_record(x, r)
        receipts, decodes, _ = passing(49, 1, 'guide')
        rec.validate_decode_record(decodes[receipts[1]['run_name']], receipts[1])
        x = copy.deepcopy(decodes[receipts[1]['run_name']])
        x['frame_anchor'] = {'sha256': x['last_frame_sha256'], 'bytes': c.ANCHOR_BYTES, 'path': '/a.f32'}
        with self.assertRaises(ValueError):
            rec.validate_decode_record(x, receipts[1])


class LeverGate(unittest.TestCase):
    """Packet117: the lever rows of the verdict and the lever blocks of receipts and decode records."""
    def failures(self, mutate, levers=None, key='precompute_failures'):
        receipts, decodes, captures = passing(levers=levers)
        mutate(receipts, decodes, captures)
        verdict = decide(receipts, decodes, captures, levers=levers)
        self.assertFalse(verdict['passed'])
        self.assertTrue(verdict[key], verdict['failures'])
        return verdict[key]

    def test_every_lever_combination_passes(self):
        for frames in (49, 97, 121, 145):  #169 auxiliary scope is covered by test_aux_runtime123
            for levers in [(ad, bo, pa) for ad in c.ANCHOR_DECODE_CHOICES for bo in (0, 1) for pa in (0, 1)]:
                receipts, decodes, captures = passing(frames, levers=levers)
                for r in receipts:
                    rec.validate_receipt(r)
                    rec.validate_decode_record(decodes[r['run_name']], r)
                verdict = decide(receipts, decodes, captures, frames, levers=levers)
                self.assertTrue(verdict['passed'], (levers, verdict['failures']))
                self.assertEqual(verdict['levers'], dict(zip(c.LEVER_FIELDS, levers)))
                self.assertEqual((verdict['anchor_decode_failures'], verdict['precompute_failures']), ([], []))
                rows = verdict['lever_rows']
                self.assertEqual([r['anchor_decode'] for r in rows], ['full'] * 3 + [levers[0]] * 6)
                for i, row in enumerate(rows):
                    if i % 3 == 0:
                        self.assertIsNone(row['sources'])
                        continue
                    eager = i < 3
                    self.assertEqual(row['sources'], {'A': 'precomputed' if levers[2] and not eager else 'native',
                                                      'B': 'precomputed' if levers[1] and not eager else 'native'})

    def test_levers_must_match_the_launch(self):
        receipts, decodes, captures = passing()
        verdict = decide(receipts, decodes, captures, levers=('full', 1, 1))
        self.assertFalse(verdict['passed'])
        self.assertTrue(any('identity' in f for f in verdict['failures']), verdict['failures'])
        with self.assertRaises(ValueError):
            decide(*passing(anchor='latent'), anchor='latent', levers=('cone', 0, 0))

    def test_cone_failures(self):
        def mode(receipts, decodes, captures):
            decodes[receipts[4]['run_name']]['anchor_decode']['mode'] = 'full'
        self.assertIn('Anchor decode mode differs', self.failures(mode, key='anchor_decode_failures')[0])

        def unequal(receipts, decodes, captures):
            decodes[receipts[7]['run_name']]['anchor_decode']['equal'] = False
        self.assertIn('Cone anchor frame', self.failures(unequal, key='anchor_decode_failures')[0])

        def display(receipts, decodes, captures):
            decodes[receipts[8]['run_name']]['anchor_decode']['display_last_frame_sha256'] = h('other')
        self.failures(display, key='anchor_decode_failures')

        def capture(receipts, decodes, captures):
            captures[receipts[5]['run_name']]['last_frame_sha256'] = h('other')
        self.failures(capture, key='anchor_decode_failures')

        def eager_cone(receipts, decodes, captures):
            decodes[receipts[1]['run_name']]['anchor_decode']['mode'] = 'cone'
        self.failures(eager_cone, key='anchor_decode_failures')

        def full_under_cone(receipts, decodes, captures):
            decodes[receipts[3]['run_name']]['anchor_decode']['mode'] = 'cone'
        self.failures(full_under_cone, levers=('full', 0, 0), key='anchor_decode_failures')

    def test_precompute_failures(self):
        def inline(receipts, decodes, captures):
            receipts[7]['conditioning_sources']['A'].update(source='native-inline', reason='cancelled')
        self.assertIn('did not use the precomputed encode', self.failures(inline)[0])

        def no_dual(receipts, decodes, captures):
            receipts[4]['conditioning_sources']['B']['dual_equal'] = False
        self.assertIn('differs from the native one', self.failures(no_dual)[0])

        def eager_precomputed(receipts, decodes, captures):
            receipts[1]['conditioning_sources']['A']['source'] = 'precomputed'
        self.assertIn('should use the native encode', self.failures(eager_precomputed)[0])

        def off_precomputed(receipts, decodes, captures):
            receipts[7]['conditioning_sources']['B']['source'] = 'precomputed'
        self.failures(off_precomputed, levers=('cone', 0, 1))

        def missing(receipts, decodes, captures):
            receipts[8]['conditioning_sources'] = None
        self.failures(missing)

    def test_receipt_lever_blocks(self):
        receipts, decodes, _ = passing()
        r = receipts[4]                                     # graph chain chunk 1: precomputed, dual-checked
        rec.validate_receipt(r)
        bad = [lambda r: r.pop('levers'),
               lambda r: r['levers'].__setitem__('anchor_decode', 'tail'),
               lambda r: r['levers'].__setitem__('prep_ahead', True),
               lambda r: r.__setitem__('conditioning_sources', None),
               lambda r: r['conditioning_sources'].pop('B'),
               lambda r: r['conditioning_sources']['A'].__setitem__('source', 'native'),
               lambda r: r['conditioning_sources']['A'].__setitem__('source', 'guessed'),
               lambda r: r['conditioning_sources']['A'].__setitem__('lever_on', False),
               lambda r: r['conditioning_sources']['A'].__setitem__('stage', 'B'),
               lambda r: r['conditioning_sources']['A'].__setitem__('lever', 'bencode_overlap'),
               lambda r: r['conditioning_sources']['A'].__setitem__('dual_equal', None),
               lambda r: r['conditioning_sources']['B'].__setitem__('waited_s', -1),
               lambda r: r['conditioning_sources']['B'].__setitem__('precompute', None),
               lambda r: r['conditioning_sources']['B']['precompute'].__setitem__('state', 'cancelled')]
        for mutate in bad:
            x = copy.deepcopy(r)
            mutate(x)
            with self.assertRaises((ValueError, KeyError, TypeError, AttributeError)):
                rec.validate_receipt(x)
        repeat = copy.deepcopy(receipts[7])
        rec.validate_receipt(repeat)
        repeat['conditioning_sources']['A']['dual_equal'] = True       # only the graph chain dual-checks
        with self.assertRaises(ValueError):
            rec.validate_receipt(repeat)
        inline = copy.deepcopy(receipts[7])
        inline['conditioning_sources']['B'].update(source='native-inline', reason='cancelled', precompute=None)
        rec.validate_receipt(inline)                                   # exact; the gate (not the schema) refuses it
        first = copy.deepcopy(receipts[6])
        first['conditioning_sources'] = sources(dict(c.qualification_params(49, 1, 'two-way20-28')[7]), 'frame')
        with self.assertRaises(ValueError):
            rec.validate_receipt(first)                                # unanchored chunks carry none
        latent = Receipts().sample(anchor='latent')
        self.assertIsNone(latent['conditioning_sources'])
        x = copy.deepcopy(latent)
        x['levers']['anchor_decode'] = 'cone'
        with self.assertRaises(ValueError):
            rec.validate_receipt(x)

    def test_decode_record_lever_blocks(self):
        receipts, decodes, _ = passing(121)
        r = receipts[7]
        d = decodes[r['run_name']]
        rec.validate_decode_record(d, r)
        self.assertEqual(d['anchor_decode']['mode'], 'cone')
        bad = [lambda d: d.pop('levers'),
               lambda d: d['levers'].__setitem__('bencode_overlap', 2),
               lambda d: d.pop('anchor_decode'),
               lambda d: d['anchor_decode'].__setitem__('mode', 'full'),
               lambda d: d['anchor_decode'].__setitem__('equal', False),
               lambda d: d['anchor_decode'].__setitem__('equal', None),
               lambda d: d['anchor_decode'].__setitem__('flag', 'full'),
               lambda d: d['anchor_decode'].__setitem__('last_frame_sha256', 'b' * 64),
               lambda d: d['anchor_decode'].__setitem__('display_last_frame_sha256', 'b' * 64),
               lambda d: d['anchor_decode'].__setitem__('seconds', None),
               lambda d: d['timing_ns'].__setitem__('display_start', None),
               lambda d: d['timing_ns'].__setitem__('display_done', 31),        # after the audio decode
               lambda d: d['timing_ns'].__setitem__('go', 26),                  # after the display started
               lambda d: d['timing_ns'].__setitem__('go', 'soon'),
               lambda d: d['timing_ns'].pop('precompute_b_start'),
               lambda d: d.__setitem__('precompute', {'C': {'stage': 'C', 'state': 'done'}}),
               lambda d: d.__setitem__('precompute', {'A': {'stage': 'A', 'state': 'guessed'}}),
               lambda d: d.__setitem__('precompute', {'A': {'stage': 'B', 'state': 'done'}}),
               lambda d: d.pop('schedule')]
        for mutate in bad:
            x = copy.deepcopy(d)
            mutate(x)
            with self.assertRaises((ValueError, KeyError, TypeError)):
                rec.validate_decode_record(x, r)
        ok = copy.deepcopy(d)
        ok['precompute'] = {'A': {'stage': 'A', 'state': 'done'}, 'B': {'stage': 'B', 'state': 'cancelled'}}
        ok['timing_ns'].update(precompute_a_start=21, precompute_a_done=22)
        rec.validate_decode_record(ok, r)
        eager = copy.deepcopy(decodes[receipts[1]['run_name']])
        self.assertEqual(eager['anchor_decode']['mode'], 'full')
        eager['anchor_decode'].update(mode='cone', equal=True, display_seconds=0.5)
        with self.assertRaises(ValueError):
            rec.validate_decode_record(eager, receipts[1])             # the eager chain never runs the cone
        full = passing(levers=('full', 1, 1))
        d = full[1][full[0][7]['run_name']]
        rec.validate_decode_record(d, full[0][7])
        x = copy.deepcopy(d)
        x['timing_ns'].update(display_start=25, display_done=28)
        with self.assertRaises(ValueError):
            rec.validate_decode_record(x, full[0][7])                  # a full decode has no display decode


if __name__ == '__main__':
    unittest.main()
