#!/usr/bin/env python3
"""Construct the packet115 stream plan (setup + nine qualification graphs per variant). CPU only.

`python plan.py` prints the plan identity; `--output PATH` writes it exclusively.
The plan pins every fixed graph by SHA-256 for every launch variant (frames 49/97,
placement, anchor latent/frame, LTX_STREAM_TEXT_REUSE 0/1); streaming graphs are
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

PARENT_MANIFEST_SHA = '3e8b7abeb21fff903869907fd67c41128dd6179fa17fa441abdd5544468c97f3'
HEADER_BOUND = 65544
GIB, MIB = 2 ** 30, 2 ** 20


def variant_keys():
    return [(f, p, a, r) for f in contract.FRAME_CHOICES for p in contract.PLACEMENTS
            for a in contract.ANCHORS for r in (0, 1)]


def build_plan():
    setup = []
    for row in contract.setup_graphs():
        setup.append({'name': row['name'], 'kind': row['kind'], 'graph': row['graph'],
                      'graph_sha256': contract.sha256(contract.canonical(row['graph']))})
    keys = variant_keys()
    variants = {k: contract.qualification_params(k[0], k[3], k[1], k[2]) for k in keys}
    qualification = []
    for i, p in enumerate(variants[(contract.DEFAULT_FRAMES, contract.DEFAULT_PLACEMENT, contract.DEFAULT_ANCHOR, 1)]):
        qualification.append({
            'name': contract.run_name(p), 'kind': p['kind'], 'scene_id': p['scene_id'],
            'chunk_index': p['chunk_index'], 'seed': p['seed'], 'prompt_sha256': contract.text_sha256(p['prompt']),
            'capture_role': 'full', 'capture_writer': 'decode thread (LTXBaselineCapture.capture)',
            'gate_mode': {'qualify-eager': 'original', 'qualify-graph': 'graph'}.get(
                p['kind'], 'absent (stream graph form; routes persist on the patcher)'),
            'graph_sha256': {'%d/%s/%s/%d' % k: contract.sha256(contract.canonical(
                contract.build_chunk_graph(variants[k][i]))) for k in keys}})
    geometry = {str(f): contract.geometry(f) for f in contract.FRAME_CHOICES}
    combos = [(f, p, a) for f in contract.FRAME_CHOICES for p in contract.PLACEMENTS for a in contract.ANCHORS]
    plan = {
        'schema': 'ltx.stream115.plan.v1', 'status': 'cpu-prepared-not-admitted',
        'qualification_ids': {contract.variant(*k): contract.qualification_id(*k) for k in combos},
        'numerical_contracts': {contract.variant(*k): contract.numerical_contract(*k) for k in combos},
        'launch_parameters': {'LTX_STREAM_FRAMES': {'default': '49', 'choices': ['49', '97'], 'launch': '49'},
                              'LTX_SAMPLER_PLACEMENT': {'default': 'two-way', 'choices': ['two-way', 'two-way20-28'],
                                                        'launch': 'two-way20-28'},
                              'LTX_ANCHOR': {'default': 'mixed', 'choices': list(contract.ANCHORS), 'launch': 'mixed'},
                              'LTX_STREAM_TEXT_REUSE': {'default': '1', 'choices': ['0', '1']}},
        'basis': {'parent_packet': '/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-114',
                  'parent_manifest_sha256': PARENT_MANIFEST_SHA,
                  'design': 'notes/2026-10-08-continuation115-stream-design.md',
                  'specification': 'notes/2026-10-08-continuation-latent-anchor-design.md (variant L2 = guide) and '
                                   'the packet-114 live sharpness result (first six frames at 0.60-0.83 of mid-chunk)'},
        'setup': setup, 'qualification': qualification,
        'execution_order': [r['name'] for r in setup] + [r['name'] for r in qualification] + ['action:qualify-verdict'],
        'qualification_gate': {
            'compare': 'per chunk, byte-identical across the eager chain, the graph chain and the graph repeat: '
                       'the three latents (video, audio, stage A), the anchor file, and the decode thread\'s '
                       'images and waveform; the four captured tensors are re-read from the capture files; '
                       'mixed: the decoded frame each anchored stage B consumed equals its predecessor\'s decode '
                       'record and capture last frame',
            'anchors': 'each chain consumes only its own verified predecessor anchor; chunk 0 is unanchored',
            'prompt_cut': 'chunk 2 of every chain changes the prompt on the same anchor chain',
            'graph': 'eager chain observes zero routes; graph chain chunk 2 and the whole repeat chain '
                     'capture nothing new; uniform <=8 signatures on the prompt thread; frozen afterwards',
            'decode_overlap': 'the decode thread runs in all three chains; it is drained before every gated '
                              'request (eager and graph chains: no overlap, the controls) and overlaps the next '
                              'chunk in the repeat chain (streaming form)',
            'diagnostic_only': 'slot-0 pin (latent: A and B; mixed: A), guide pin (guide frames before the crop), '
                               'the sharpness profile, mixed frame wait',
            'stream_form': 'the repeat chain uses the streaming graph form (no gate nodes)',
            'on_failure': 'latch: the server refuses all streaming requests'},
        'stream_contract': {'module': 'stream_contract.py', 'schema': contract.SCHEMA,
                            'ordering': 'one anchor chain; stream_seq n>0 names the anchor of n-1; '
                                        'the prompt may change at any chunk; a chunk flagged reset is '
                                        'unanchored (stream_seq 0 form) and restarts the chain',
                            'anchor_ready': 'mixed/latent/guide: three latents hashed and the latent or guide anchor '
                                            'fsynced, decode queued; frame: after the decode thread returned the '
                                            'last frame',
                            'mixed_wait': 'chunk n+1 stage-B condition node waits (bounded 300 s) for chunk n\'s '
                                          'decode record and frame anchor; its text encode and stage A do not',
                            'decode': 'one ordered decode thread on xpu:3; receipts/decode-<run_name>.json',
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
                      'note': 'Unchanged floors; see LAUNCH.md for the per-card memory estimate at 97 frames'},
        'budget': {'reserve_bytes': 50 * GIB, 'run_allowance_bytes': 3 * GIB, 'build_allowance_bytes': 160 * MIB,
                   'retries': 0},
        'out_of_scope': {'stage_overlap_across_sampler_cards': 'not in 115 (two prompts in flight; see design note)',
                         'encode_ahead': 'not in 115 (contract change)', 'decoder_capture': 'not planned',
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
                   'text_reuse_default': 1, 'decoder_graph_capture': False,
                   'geometry_97_measured': False, 'default_anchor': contract.DEFAULT_ANCHOR,
                   'mixed_seam_accepted': False, 'guide_seam_accepted': False},
    }
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
