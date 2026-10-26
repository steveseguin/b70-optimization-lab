#!/usr/bin/env python3
"""Collect the QSA attention study's run evidence into results.json."""
import json, statistics
from pathlib import Path

LAB = Path('/dev/shm/ownrt-lab-attn')
OUT = Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/qsa-attention/results.json')
builds = {}
for tag, d in [('ref', 'engine-build-lab-attn-ref'), ('c1', 'engine-build-lab-attn-c1'), ('c2', 'engine-build-lab-attn-c2'),
               ('ref2', 'engine-build-lab-attn-ref2'), ('c4', 'engine-build-lab-attn-c4')]:
    r = json.loads((Path('/dev/shm') / d / 'build-receipt.json').read_text())
    builds[tag] = dict(binary=r['binary'], binary_sha256=r['binary_sha256'],
                       p49_qsa_kernel_hpp=r['sources'].get('stage2/packet194-expert-diet-engine/p49_qsa_kernel.hpp'),
                       p49_qsa_submit_cpp=r['sources'].get('stage2/packet194-expert-diet-engine/p49_qsa_submit.cpp'),
                       rank_hpp=r['sources'].get('gsq-rco-iq3s/state-bundle/build/source-v4/rank.hpp'))
notes = {
    'ref': 'unmodified lab copy of canonical engine/src taken 05:12 (session_checkpoint.hpp as of 03:33)',
    'c1': 'lab copy + attention v1 (tiles_heads 384-lane + L1 prefetch, combine_blocked, guard) + LAB-ONLY rank.hpp profile-export deferral (inert without OWNRT_DECODE_PROFILE>=2)',
    'c2': 'lab copy + final attention kernels (tiles_heads v3) + LAB-ONLY rank.hpp deferral',
    'ref2': 'fresh copy of canonical engine/src at 06:0x (includes the 05:35 session_checkpoint.hpp update), unmodified',
    'c4': 'ref2 sources + attention.patch only (the deliverable)',
}
for k, v in notes.items():
    builds[k]['note'] = notes[k]

def run(tag):
    d = LAB / tag
    r = json.loads((d / 'lab-result.json').read_text())
    s = json.loads((d / 'summary.json').read_text())
    t = s['half_ms']
    return dict(tag=tag, binary=r['binary'], env=r['env'], prompt=s['prompt'], steps=s['steps'], rc=r['rc'],
                dri=r['dri'], kernel_fault_lines=len(r['faults']), median_half_ms=round(statistics.median(t), 4),
                mean_half_ms=round(statistics.mean(t), 4), min_half_ms=round(min(t), 4), prompt_ms=round(s['prompt_ms'], 1),
                tokens=s['tokens'])

tags = sorted(p.name for p in LAB.iterdir() if p.is_dir() and (p / 'lab-result.json').exists() and (p / 'summary.json').exists())
runs = {t: run(t) for t in tags}
for t, r in runs.items():
    ref = 'fin-ref2-p300' if t.startswith('fin-') and r['prompt'] == 300 else 'fin-ref2-p4096-a' if t.startswith('fin-') else \
          'ref-p300' if r['prompt'] == 300 else 'ref-p4096'
    if ref in runs and r['steps'] == runs[ref]['steps']:
        r['tokens_equal_ref'] = r['tokens'] == runs[ref]['tokens']
        r['tokens_ref'] = ref
for r in runs.values():
    r.pop('tokens')
compares = {}
for p in sorted(LAB.glob('cmp-*.json')):
    try:
        compares[p.stem[4:]] = json.loads(p.read_text())
    except Exception as e:
        compares[p.stem[4:]] = dict(error=str(e))

def profile(tag):
    rows = [json.loads(l) for l in (LAB / tag / 'rank1' / 'decode-device-profile.jsonl').open()]
    rows = [r for r in rows if not r['speculative']]
    out = {}
    for k in rows[0]['sites']:
        if 'qsa_attention' in k or k == 'qsa_select':
            v = [r['sites'][k]['busy_us'] for r in rows if k in r['sites']]
            cnt = rows[0]['sites'][k]['count']
            out[k] = dict(count_per_token=cnt, median_busy_us_per_token=round(statistics.median(v), 2),
                          per_layer_us=round(statistics.median(v) / cnt, 2))
    out['span_us_median'] = round(statistics.median([r['span_us'] for r in rows]), 1)
    out['tokens_profiled'] = len(rows)
    return out

profiles = {t: profile(t) for t in ('c2-prof-off-p4096', 'c2-prof-on-p4096') if (LAB / t).exists()}
final = {}
for kind, pat in (('ref2', 'fin-ref2-p4096-'), ('c4_on', 'fin-c4on-p4096-')):
    xs = [runs[t]['median_half_ms'] for t in runs if t.startswith(pat)]
    if xs:
        final[kind] = dict(per_run_median_half_ms=xs, mean_of_medians=round(statistics.mean(xs), 4))
if 'ref2' in final and 'c4_on' in final:
    a, b = final['ref2']['mean_of_medians'], final['c4_on']['mean_of_medians']
    final['delta_ms'] = round(b - a, 4)
    final['delta_pct'] = round(100 * (b - a) / a, 2)
result = dict(
    schema='ownrt.lab.qsa-attention.v1', date='2026-10-26', card='0000:27:00.0 (renderD131)',
    launch_template='research/context-64k/rank1-card27-s24-ctx65536-launch.json (binary replaced; FilterBdfPath=0000:27:00.0, OWNRT_SELECT_TOPK=1, OWNRT_RESET_DEVICE_ZERO=1)',
    driver='engine/tools/tp_rank1_driver.py run --steps 48 --prompt N --batched --rows 32 (cache /dev/shm/ownrt-lab-attn/cache)',
    switches=dict(OWNRT_ATTN_HEADS='1: tiles_heads (512-lane work-group per row, KV head, tile)', OWNRT_ATTN_COMBINE2='1: combine_blocked',
                  OWNRT_ATTN_GUARD='1: incumbent tiles/combine with the guard read once per work-group'),
    best=dict(env={'OWNRT_ATTN_HEADS': '1', 'OWNRT_ATTN_COMBINE2': '1'}, binary_sha256=builds['c4']['binary_sha256']),
    builds=builds, final_series=final, runs=runs, compares=compares, rank1_device_profiles=profiles,
    bench=json.loads((LAB / 'work' / 'bench_results.json').read_text()))
OUT.write_text(json.dumps(result, indent=1) + '\n')
print(json.dumps(final, indent=1))
