#!/usr/bin/env python3
"""Construct the packet123 stream plan (setup + nine qualification graphs per variant). CPU only.

Packet123: the 176 launch variants including145 (132 inherited identities) (the snapshot mode and the decoder-graph pool cap are
server-side launch parameters, not request fields and not in the qualification id), packet-118 names.

`python plan.py` prints the plan identity; `--output PATH` writes it exclusively.
The plan pins every fixed graph by SHA-256 for every launch variant (frames 49/97/121/145,
placement, anchor mixed/latent/frame/guide, LTX_DECODER_GRAPH 0/1, for the frame anchor
LTX_ANCHOR_DECODE full/cone, LTX_BENCODE_OVERLAP 0/1 and LTX_PREP_AHEAD 0/1, LTX_STREAM_TEXT_REUSE 0/1);
streaming graphs are
not enumerable and are instead pinned by stream_contract.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import stream_contract as contract  # noqa: E402

PARENT_MANIFEST_SHA = '897442d035728c35a923840046c51c1bd43cad5097e4807c59e6d786699926a5'
HEADER_BOUND = 65544
GIB, MIB = 2 ** 30, 2 ** 20


def variant_keys():
    return [k + (r,) for k in contract.variant_keys() for r in (0, 1)]


def build_plan():
    setup = []
    for row in contract.setup_graphs():
        setup.append({'name': row['name'], 'kind': row['kind'], 'graph': row['graph'],
                      'graph_sha256': contract.sha256(contract.canonical(row['graph']))})
    keys = variant_keys()
    variants = {k: contract.qualification_params(k[0], k[7], k[1], k[2], k[3], k[4], k[5], k[6]) for k in keys}
    qualification = []
    default = (contract.DEFAULT_FRAMES, contract.DEFAULT_PLACEMENT, contract.DEFAULT_ANCHOR,
               contract.DEFAULT_DECODER_GRAPH) + contract.DEFAULT_LEVERS + (1,)
    for i, p in enumerate(variants[default]):
        qualification.append({
            'name': contract.run_name(p), 'kind': p['kind'], 'scene_id': p['scene_id'],
            'chunk_index': p['chunk_index'], 'seed': p['seed'], 'prompt_sha256': contract.text_sha256(p['prompt']),
            'capture_role': 'full', 'capture_writer': 'decode thread (LTXBaselineCapture.capture)',
            'gate_mode': {'qualify-eager': 'original', 'qualify-graph': 'graph'}.get(
                p['kind'], 'absent (stream graph form; routes persist on the patcher)'),
            'graph_sha256': {contract.variant(*k[:7]) + '/%d' % k[7]: contract.sha256(contract.canonical(
                contract.build_chunk_graph(variants[k][i]))) for k in keys}})
    geometry = {str(f): contract.geometry(f) for f in contract.FRAME_CHOICES}
    combos = contract.variant_keys()
    plan = {
        'schema': 'ltx.stream125.plan.v1', 'status': 'cpu-prepared-not-admitted',
        'qualification_ids': {contract.variant(*k): contract.qualification_id(*k) for k in combos},
        'numerical_contracts': {contract.variant(*k): contract.numerical_contract(*k) for k in combos},
        'launch_parameters': {'LTX_RUN_WRITE_ALLOWANCE_GIB': {'default': '3', 'choices': 'integer GiB 1..64', 'accounting': 'run-owned allocated blocks'}, 'LTX_STREAM_FRAMES': {'default': '49', 'choices': ['49', '97', '121', '145', '169'], 'launch': '145',
                                                    'rule': 'set explicitly'},
                              'LTX_SAMPLER_PLACEMENT': {'default': 'two-way', 'choices': ['two-way', 'two-way20-28'],
                                                        'launch': 'two-way20-28'},
                              'LTX_ANCHOR': {'default': 'frame', 'choices': list(contract.ANCHORS), 'launch': 'frame'},
                              'LTX_DECODER_GRAPH': {'default': '1', 'choices': ['0', '1'], 'launch': '0',
                                                    'rule': 'set explicitly; 1 is refused while the decoder-graph '
                                                            'latch exists in the results root'},
                              'LTX_ANCHOR_DECODE': {'default': 'cone', 'choices': list(contract.ANCHOR_DECODE_CHOICES),
                                                    'launch': 'cone',
                                                    'rule': 'set explicitly; frame anchor only (others: full); cone is '
                                                            'refused while the anchor-decode latch exists'},
                              'LTX_BENCODE_OVERLAP': {'default': '1', 'choices': ['0', '1'], 'launch': '1',
                                                      'rule': 'set explicitly; frame anchor only (others: 0); 1 is '
                                                              'refused while the precompute latch exists'},
                              'LTX_PREP_AHEAD': {'default': '1', 'choices': ['0', '1'], 'launch': '1',
                                                 'rule': 'set explicitly; frame anchor only (others: 0); 1 is refused '
                                                         'while the precompute latch exists'},
                              'LTX_STREAM_TEXT_REUSE': {'default': '1', 'choices': ['0', '1']},
                              'LTX_SNAPSHOT_MODE': {'default': contract.DEFAULT_SNAPSHOT_MODE,
                                                    'choices': list(contract.SNAPSHOT_MODES), 'launch': 'fingerprint',
                                                    'rule': 'set explicitly; server-side only (not a request field, '
                                                            'not in the qualification id; the run name carries '
                                                            '-sm<walk|fp>-); fingerprint is refused while the '
                                                            'snapshot latch exists'},
                              'LTX_DECODER_GRAPH_POOL_CAP_GB': {'default': None,
                                                                'choices': 'unset, or %.2f..%.1f decimal GB'
                                                                           % (contract.POOL_CAP_MIN_GB,
                                                                              contract.POOL_CAP_MAX_GB),
                                                                'launch': 'unset; recommended arms all dg0',
                                                                'rule': 'needs LTX_DECODER_GRAPH=1; server-side only'}},
        'basis': {'supersedes': {'packet': 118, 'manifest_sha256': 'cb68515a1e770697ad0ac2d0c2abd9709780043e9d1579cba81706bb53f482f6', 'status': 'withdrawn-never-launched'},
                  'review': 'notes/2026-10-09-continuation118-review.md',
                  'rebuild': 'notes/2026-10-09-continuation118b-rebuild.md',
                  'parent_packet': '/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-124',
                  'parent_manifest_sha256': PARENT_MANIFEST_SHA,
                  'design': 'notes/2026-10-10-continuation125-stream-design.md',
                  'specification': 'notes/2026-10-09-continuation117-results-97.md and -121.md (the 117 live '
                                   'measurements: submit_to_sampler_start 0.52 s, the 121 dg1 xpu:3 floor refusal) and '
                                   'notes/2026-10-08-continuation117-stream-design.md (open question 2: cheaper but '
                                   'equally strong four-card snapshots)'},
        'reference_hashes': {'path': 'resolution/reference-frame-hashes.json',
                             'variants': ['49/two-way20-28/frame', '97/two-way20-28/frame', '145/two-way20-28/frame'],
                             'rule': 'the eager chain of a frame-anchor launch must equal the reference byte for byte'},
        'setup': setup, 'qualification': qualification,
        'execution_order': [r['name'] for r in setup] + [r['name'] for r in qualification] + ['action:qualify-verdict'],
        'qualification_gate': {
            'levers': 'eager chain: anchor_decode full, native stage-A/B encodes on the prompt thread (the '
                      'reference); graph chain: the launch levers plus their native counterparts on the same inputs '
                      '(cone last frame == full last frame; precomputed stage-A/B conditioning == native '
                      'conditioning, samples and mask byte for byte); repeat chain: the launch levers in the '
                      'stream form; a lever failure latches and writes that lever\'s latch file',
            'decoder_graph': 'LTX_DECODER_GRAPH=1: eager chain = uncached eager decoder; graph chain = uncached '
                             'eager decode AND graph decode of the same latents, byte-identical images; graph '
                             'chain chunk 0 captures the two decoder graphs, nothing later captures; one signature '
                             'per captured method; a failure latches and writes the decoder-graph latch',
            'cross_packet': 'frame anchor: the eager chain equals the packet-113 (49) / packet-114 frame (97) '
                            'reference hashes byte for byte',
            'compare': 'per chunk, byte-identical across the eager chain, the graph chain and the graph repeat: '
                       'the three latents (video, audio, stage A), the anchor file, and the decode thread\'s '
                       'images and waveform; the four captured tensors are re-read from the capture files; '
                       'mixed: the decoded frame each anchored stage B consumed equals its predecessor\'s decode '
                       'record and capture last frame',
            'anchors': 'each chain consumes only its own verified predecessor anchor; chunk 0 is unanchored',
            'prompt_cut': 'chunk 2 of every chain changes the prompt on the same anchor chain',
            'graph': 'eager chain observes zero routes; graph chain chunk 2 and the whole repeat chain '
                     'capture nothing new; uniform <=8 signatures on the prompt thread; frozen afterwards',
            'decode_overlap': 'the decode thread runs in all three chains; gated chunks (eager and graph chains) '
                              'wait for their whole decode and drain it before the next gated request (no overlap, '
                              'the controls); the repeat chain overlaps the next chunk (streaming form)',
            'diagnostic_only': 'slot-0 pin (latent: A and B; mixed: A), guide pin (guide frames before the crop), '
                               'the sharpness profile, mixed frame wait',
            'stream_form': 'the repeat chain uses the streaming graph form (no gate nodes)',
            'snapshots': 'packet123: every qualification receipt lists its four-card snapshots in order, in the launch '
                         'snapshot mode; with fingerprint every one ran the walk beside it and agreed (a disagreement '
                         'latches and writes the snapshot latch)',
            'decoder_pool': 'packet123: with a pool cap the graph chain chunk 0 captures exactly the methods it lists '
                            'as captured; the capped method runs eagerly with the caches (byte-gated as before)',
            'on_failure': 'latch: the server refuses all streaming requests'},
        'stream_contract': {'module': 'stream_contract.py', 'schema': contract.SCHEMA,
                            'ordering': 'one anchor chain; stream_seq n>0 names the anchor of n-1; '
                                        'the prompt may change at any chunk; a chunk flagged reset is '
                                        'unanchored (stream_seq 0 form) and restarts the chain',
                            'anchor_ready': 'mixed/latent/guide: three latents hashed and the latent or guide anchor '
                                            'fsynced, decode queued; frame (116a): the decode thread wrote and '
                                            'fsynced the decoded last frame right after the video decode; audio, '
                                            'hashing, record and preview follow behind the chain',
                            'mixed_wait': 'chunk n+1 stage-B condition node waits (bounded 300 s) for chunk n\'s '
                                          'decode record and frame anchor; its text encode and stage A do not',
                            'decode': 'serial parent worker by default; optional bounded cone/early-audio and display/completion FIFOs; receipts/decode-<run_name>.json',
                            'preview': 'one bounded in-order writer behind the decode thread; '
                                       'receipts/preview-<run_name>.json',
                            'full_captures': 0, 'per_chunk_sanity': ['finite', 'shapes', 'anchor_chain']},
        'naming': {'prefix': contract.RUN_PREFIX + '-', 'fixed_names': contract.fixed_names(),
                   'checked_directories': ['output', 'output/validation', 'requests'],
                   'rule': 'the launcher refuses (also in --check-only) when any fixed name or any entry '
                           'starting with the prefix already exists in a checked directory'},
        'geometry': geometry,
        'capture_contract': {str(f): {'count': 9, 'full_payload_bytes': geometry[str(f)]['full_payload_bytes'],
                                      'full_file_bound_bytes': geometry[str(f)]['full_payload_bytes'] + HEADER_BOUND,
                                      'raw_capture_bound_bytes': 9 * (geometry[str(f)]['full_payload_bytes'] + HEADER_BOUND)}
                             for f in contract.FRAME_CHOICES},
        'admission': {'pre_floor_gib': [8, 8, 2, 9], 'post_floor_gib': 2,
                      'conditioning_stage_floors': 'frame anchor: A and B snapshots; mixed: stage B snapshots only; '
                                                   'latent and guide: no stage snapshots (no encode)',
                      'note': 'Unchanged floors; see packet123 design census;169 is not admitted'},
        'budget': {'reserve_bytes': 50 * GIB, 'run_allowance_bytes': 3 * GIB, 'build_allowance_bytes': 160 * MIB,
                   'retries': 0},
        'out_of_scope': {'stage_overlap_across_sampler_cards': 'not in 118 (two prompts in flight)',
                         'noise_latent_schedule_prep_ahead': 'not moved: they are ComfyUI graph nodes of the '
                                                             'successor request (milliseconds) and moving them would '
                                                             'need cross-request node caching, which the executor '
                                                             'guard refuses',
                         'two_chains': 'no'},
        'guide_signatures': {'per_route_expected': 4, 'ceiling': 8,
                             'note': 'guide replaces the two anchored signatures (stage A %d, stage B %d video tokens '
                                     'at 49 frames; %d / %d at 97) instead of adding to them; the unanchored '
                                     'chunk-0/reset signatures stay'
                                     % (contract.geometry(49)['guided_stage_tokens']['A'],
                                        contract.geometry(49)['guided_stage_tokens']['B'],
                                        contract.geometry(97)['guided_stage_tokens']['A'],
                                        contract.geometry(97)['guided_stage_tokens']['B'])},
        'claims': {'graph_replay_qualified': False, 'seam_quality_accepted': False,
                   'audio_alignment_resolved': False, 'speed_claim': False, 'adopted': False,
                   'text_reuse_default': 1, 'decoder_graph_capture_qualified': False, 'decoder_graph_default': 1,
                   'geometry_97_measured': True, 'geometry_121_measured': True, 'geometry_145_measured': True, 'geometry_169_measured': True,
                   'snapshot_fingerprint_equivalence_on_xpu': False, 'decoder_pool_cap_fits_121_dg1': False,
                   'default_anchor': contract.DEFAULT_ANCHOR, 'default_levers': list(contract.DEFAULT_LEVERS),
                   'cone_exact_on_xpu': False, 'precompute_exact_on_xpu': False,
                   'mixed_seam_accepted': False, 'guide_seam_accepted': False, 'speed_116a_measured': False},
    }
    plan['launch_parameters'].update({
        'LTX_DISPLAY_DEVICE': {'default': 'xpu:3', 'choices': ['xpu:3', 'xpu:2'],
                               'rule': 'xpu:2 requires 121/145-frame/frame/cone/eager-display; full same-latent cross-card gate on all three chains; 2GiB floor'},
        'LTX_DISPLAY_SCHEDULE': {'default': 'sampler-a', 'choices': ['sampler-a', 'sampler-b', 'eager-display'],
                                 'rule': 'frame/cone only for nondefault; unchanged arithmetic, live byte gate'},
        'LTX_ANCHOR_READ_AHEAD': {'default': '0', 'choices': ['0', '1'], 'rule': 'frame only; immutable CPU bytes'},
        'LTX_SNAPSHOT_SCHEDULE': {'default': 'full', 'choices': ['full', 'a-xpu3-sync'],
                                  'rule': 'owner safety decision; fingerprint only; fresh all-card readings retained'}})
    plan['basis']['specification'] = 'notes/2026-10-10-continuation121-results-145.md; matched118b dg0/dg1 and119 receipts'
    plan['qualification_gate']['display_replica'] = 'Optional xpu:2 display is off by default; native xpu:3 uncached eager reference on every chunk of all three qualification chains; per-chunk cone-last-frame equality; fail closed on mismatch or memory refusal.'
    plan['claims']['cross_card_display_exact_on_xpu'] = False
    plan['deferred_geometry'] = {'169': {'admitted': 'conditional on xpu2 auxiliaries/display3 or legacy dg0 replica, and qualification', 'latent_frames': 22, 'tokens': [352, 1408],
        'audio_latent_shape': [1, 8, 176, 16], 'waveform_shape': [1, 2, 336480],
        'reason': 'Move upsampler and audio VAE/vocoder to xpu2; unchanged floors plus0.75GiB screening margin; native memory and byte gates required'}}
    plan['display_transient_allowance'] = {'121': 4 * GIB, '145': 4 * GIB * 19 * 19 // 256, '169': 13 * GIB // 2,
        'definition': '4GiB times squared temporal-latent ratio; planning allowance, observed growth still gated'}
    plan['launch_parameters']['LTX_DISPLAY_REPLICA_TRANSIENT_GIB'] = {
        'default': None, 'unit': 'GiB', 'minimum_by_frames': {'121': 4, '145': 5.640625, '169': 6.5},
        'maximum': 8, 'rule': 'xpu:2 only; integer bytes; may increase the census reserve, never reduce it; all memory and equality gates retained'}
    plan['launch_parameters']['LTX_AUX_RESIDENCY'] = {'default': 'legacy', 'choices': ['legacy', 'xpu2'],
        'rule': 'xpu2 keeps123b scope;169 alternatively admits legacy dg0 display replica;aux+replica refused'}
    plan['qualification_gate']['aux_residency'] = 'Separate residency qualification identity bound to every receipt and verdict;145 must match frozen121 eager outputs;169 three chains and every chunk anchor bytes; floors unchanged.'
    plan['stream_contract']['preview'] = 'Atomic exclusive same-directory temp, fsync, rename publication for MP4 and preview JSON; strict completed-file reads.'
    plan['launch_parameters']['LTX_DISPLAY_WORKER'] = {'default': 'serial', 'choices': ['serial', 'parallel'],
        'rule': 'parallel:145/169 two-way20-28 frame dg0 cone legacy eager-display xpu2; early native audio after B prep; two bounded FIFO stages; parallel repeat-chain proof; byte gates before display completion; no altered snapshots'}
    plan['basis']['design'] = 'notes/2026-10-10-continuation125-stream-design.md'
    plan['admission']['note'] = 'Measured169 phase envelope plus static legacy counterfactual; unchanged floors and0.75GiB screen; qualify145 before169'
    plan['launch_parameters']['LTX_GC_INTERVAL_SECONDS'] = {
        'default': '10', 'choices': ['10', '60'], 'launch': '60',
        'rule': '60:145 frame dg0 cone bo1 pa1 serial display3 sampler-a full snapshots read-ahead0; unchanged gc.collect and soft_empty_cache; automatic GC remains enabled'}
    plan['basis']['specification'] = 'notes/2026-10-10-continuation-2cycle-analysis.md'
    plan['claims']['two_cycle_removed_on_device'] = False
    return {'plan': plan, 'plan_sha256': contract.sha256(contract.canonical(plan))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    value = build_plan()
    if args.output:
        with args.output.open('x') as stream:
            json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
    print(json.dumps({'plan_sha256': value['plan_sha256'], 'qualification_ids': value['plan']['qualification_ids'],
                      'requests': len(value['plan']['execution_order'])}, indent=2))


if __name__ == '__main__':
    main()
