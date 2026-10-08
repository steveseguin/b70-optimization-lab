#!/usr/bin/env python3
"""Construct the packet113 stream plan (setup + nine qualification graphs, unchanged from 112). CPU only.

`python plan.py` prints the plan identity; `--output PATH` writes it exclusively.
The plan pins every fixed graph by SHA-256 for both LTX_STREAM_TEXT_REUSE values;
streaming graphs are not enumerable and are instead pinned by stream_contract.
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

PARENT_MANIFEST_SHA = 'e49f669d580a55d7f2a99ddfc5c2c5fc4a22dd7168987eb471704e2be6352b91'
HEADER_BOUND = 65544
GIB, MIB = 2 ** 30, 2 ** 20


def build_plan():
    setup = []
    for row in contract.setup_graphs():
        setup.append({'name': row['name'], 'kind': row['kind'], 'graph': row['graph'],
                      'graph_sha256': contract.sha256(contract.canonical(row['graph']))})
    keys = [(f, p, r) for f in contract.FRAME_CHOICES for p in contract.PLACEMENTS for r in (0, 1)]
    variants = {k: contract.qualification_params(k[0], k[2], k[1]) for k in keys}
    qualification = []
    for i, p in enumerate(variants[(contract.DEFAULT_FRAMES, contract.DEFAULT_PLACEMENT, 0)]):
        qualification.append({
            'name': contract.run_name(p), 'kind': p['kind'], 'scene_id': p['scene_id'],
            'chunk_index': p['chunk_index'], 'seed': p['seed'], 'prompt_sha256': contract.text_sha256(p['prompt']),
            'capture_role': 'full', 'gate_mode': {'qualify-eager': 'original', 'qualify-graph': 'graph'}.get(
                p['kind'], 'absent (stream graph form; routes persist on the patcher)'),
            'graph_sha256': {'%d/%s/%d' % k: contract.sha256(contract.canonical(
                contract.build_chunk_graph(variants[k][i]))) for k in keys}})
    geometry = {str(f): contract.geometry(f) for f in contract.FRAME_CHOICES}
    plan = {
        'schema': 'ltx.stream113.plan.v1', 'status': 'cpu-prepared-not-admitted',
        'qualification_ids': {'%d/%s' % (f, p): contract.qualification_id(f, p)
                              for f in contract.FRAME_CHOICES for p in contract.PLACEMENTS},
        'numerical_contracts': {'%d/%s' % (f, p): contract.numerical_contract(f, p)
                                for f in contract.FRAME_CHOICES for p in contract.PLACEMENTS},
        'launch_parameters': {'LTX_STREAM_FRAMES': {'default': '49', 'choices': ['49', '25']},
                              'LTX_SAMPLER_PLACEMENT': {'default': 'two-way', 'choices': ['two-way', 'two-way20-28']},
                              'LTX_STREAM_TEXT_REUSE': {'default': '0', 'choices': ['0', '1']}},
        'basis': {'parent_packet': '/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-112',
                  'parent_manifest_sha256': PARENT_MANIFEST_SHA,
                  'qualification_graphs': 'byte-identical to packet112 (same graph_sha256 pins)',
                  'design': 'notes/2026-10-08-continuation113-stream-design.md'},
        'setup': setup, 'qualification': qualification,
        'execution_order': [r['name'] for r in setup] + [r['name'] for r in qualification] + ['action:qualify-verdict'],
        'qualification_gate': {
            'compare': 'all four complete tensors (SHA-256 of full F32 payload) of each chunk equal across '
                       'eager chain, graph chain and graph repeat; capture files re-read and must agree',
            'anchors': 'each chain consumes only its own verified predecessor anchor (the last frame)',
            'prompt_cut': 'chunk 2 of every chain changes the prompt on the same anchor chain',
            'graph': 'eager chain observes zero routes; graph chain chunk 2 and the whole repeat chain '
                     'capture nothing new; uniform <=8 signatures on the prompt thread; frozen afterwards',
            'stream_form': 'the repeat chain uses the streaming graph form (no gate nodes)',
            'on_failure': 'latch: the server refuses all streaming requests'},
        'stream_contract': {'module': 'stream_contract.py', 'schema': contract.SCHEMA,
                            'ordering': 'one anchor chain; stream_seq n>0 names the anchor of n-1; '
                                        'the prompt may change at any chunk; a chunk flagged reset is '
                                        'unanchored (stream_seq 0 form) and restarts the chain',
                            'preview': 'committed at anchor ready; the MP4 is written afterwards by one '
                                       'bounded in-order writer thread and recorded in '
                                       'receipts/preview-<run_name>.json',
                            'full_captures': 0, 'per_chunk_sanity': ['finite', 'shapes', 'anchor_chain']},
        'geometry': geometry,
        'capture_contract': {str(f): {'count': 9, 'full_payload_bytes': geometry[str(f)]['full_payload_bytes'],
                                      'full_file_bound_bytes': geometry[str(f)]['full_payload_bytes'] + HEADER_BOUND,
                                      'raw_capture_bound_bytes': 9 * (geometry[str(f)]['full_payload_bytes'] + HEADER_BOUND)}
                             for f in contract.FRAME_CHOICES},
        'admission': {'pre_floor_gib': [8, 8, 2, 9], 'post_floor_gib': 2, 'conditioning_stage_floors': 'same',
                      'note': 'Unchanged from the after-111 preregistration; see LAUNCH.md for the xpu:0 margin risk'},
        'budget': {'reserve_bytes': 50 * GIB, 'run_allowance_bytes': 3 * GIB, 'build_allowance_bytes': 160 * MIB,
                   'retries': 0},
        'claims': {'graph_replay_qualified': False, 'seam_quality_accepted': False,
                   'audio_alignment_resolved': False, 'speed_claim': False, 'adopted': False,
                   'text_reuse_default': 0, 'decoder_graph_capture': False},
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
