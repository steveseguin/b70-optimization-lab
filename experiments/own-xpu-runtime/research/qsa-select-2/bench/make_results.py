#!/usr/bin/env python3
"""Collect the QSA select study's run evidence into research/qsa-select-2/results.json."""
import json, statistics
from pathlib import Path

LAB = Path('/dev/shm/ownrt-lab-sel')
OUT = Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/qsa-select-2/results.json')
builds = {}
notes = {
    'ref2': 'fresh copy of canonical engine/src (includes the attention patch and the prefill agent changes as of ~07:00), unmodified',
    'fin': 'ref2 sources + select.patch only (the deliverable)',
    'c2P': 'lab copy of canonical at 06:23 + select.patch + LAB-ONLY rank.hpp profile-export deferral (inert without OWNRT_DECODE_PROFILE>=2); used only for per-kernel device profiles',
}
for tag in notes:
    r = json.loads((Path('/dev/shm') / f'engine-build-lab-sel-{tag}' / 'build-receipt.json').read_text())
    builds[tag] = dict(binary=r['binary'], binary_sha256=r['binary_sha256'], note=notes[tag],
                       specialised_submit_cpp=r['sources'].get('stage2/packet194-expert-diet-engine/specialised_submit.cpp'),
                       select_fast_hpp=r['sources'].get('stage2/packet194-expert-diet-engine/select_fast.hpp'))
builds['refP'] = dict(binary_sha256='b2f0001f272525c56f4bd97bf0711e0d3b1ff2b8c8d73df2af550e5b48b02ea8',
                      note='lab copy of canonical at 06:23 (unmodified select) + LAB-ONLY rank.hpp deferral; 30K reference profile; build deleted after use')
builds['c1'] = dict(binary_sha256='7056564661923e81c7e900a7e5839c65192fb0c4a19b7685f4e020221595c655',
                    note='lab copy + select v1 (stage 0 BPS 8, stage 1 with float-compare rank split); build deleted after use')
builds['c1P'] = dict(binary_sha256='d28fc49aa97461e98b9ea7172d13fc083696170981951d44bcf99397dbaae571',
                     note='c1 + LAB-ONLY rank.hpp deferral; build deleted after use')
builds['ref'] = dict(binary_sha256='1827ef6d481af15d8419ec3206ecf805ab7cd7a4c8682280c539fbdddf396ff2',
                     note='lab copy of canonical at 06:23, unmodified; build deleted after use')

def engine_timing(d):
    f = d / 'rank1' / 'timings.jsonl'
    if not f.exists():
        return {}
    rows = [json.loads(l) for l in f.open()][1:]
    if not rows:
        return {}
    m = lambda k: round(statistics.median([r[k] for r in rows]), 4)
    return dict(engine_half_completion_ms=m('half_completion_ms'), engine_enqueue_loop_ms=m('enqueue_loop_ms'),
                engine_wait_ms=m('wait_ms'), host_load_1m=round(statistics.mean([r['load_average_1m'] for r in rows]), 2))

def run(tag):
    d = LAB / tag
    r = json.loads((d / 'lab-result.json').read_text())
    s = json.loads((d / 'summary.json').read_text())
    t = s['half_ms']
    return dict(tag=tag, binary=r['binary'], env=r['env'], prompt=s['prompt'], steps=s['steps'], rc=r['rc'], dri=r['dri'],
                kernel_fault_lines=len(r['faults']), median_half_ms=round(statistics.median(t), 4),
                mean_half_ms=round(statistics.mean(t), 4), min_half_ms=round(min(t), 4), prompt_ms=round(s['prompt_ms'], 1),
                tokens=s['tokens'], **engine_timing(d))

tags = sorted(p.name for p in LAB.iterdir() if p.is_dir() and (p / 'lab-result.json').exists() and (p / 'summary.json').exists())
runs = {t: run(t) for t in tags}
refmap = {('fin', 4096): 'fin-ref2-p4096-a', ('fin', 300): 'fin-ref2-p300', ('fin', 30000): 'fin-ref2-p30000', ('c1', 4096): 'ref-p4096'}
for t, r in runs.items():
    ref = refmap.get(('fin' if t.startswith('fin') else 'c1', r['prompt']))
    if ref and ref in runs and ref != t and r['steps'] == runs[ref]['steps']:
        r['tokens_equal_ref'] = r['tokens'] == runs[ref]['tokens']
        r['tokens_ref'] = ref
for r in runs.values():
    r.pop('tokens')
compares = {p.stem[4:]: json.loads(p.read_text()) for p in sorted(LAB.glob('cmp-*.json'))}

def profile(tag):
    rows = [json.loads(l) for l in (LAB / tag / 'rank1' / 'decode-device-profile.jsonl').open()]
    rows = [r for r in rows if not r['speculative']]
    out = {}
    for k in rows[0]['sites']:
        if k.startswith('qsa_select') or k in ('qsa_prepare', 'qsa_append_pool', 'qsa_attention'):
            v = [r['sites'][k]['busy_us'] for r in rows if k in r['sites']]
            cnt = rows[0]['sites'][k]['count']
            out[k] = dict(count_per_token=cnt, median_busy_us_per_token=round(statistics.median(v), 2),
                          per_layer_us=round(statistics.median(v) / cnt, 2))
    out['span_us_median'] = round(statistics.median([r['span_us'] for r in rows]), 1)
    out['tokens_profiled'] = len(rows)
    return out

profiles = {t: profile(t) for t in runs if 'prof' in t and (LAB / t / 'rank1' / 'decode-device-profile.jsonl').exists()}
final = {}
xs = {k: [runs[t]['median_half_ms'] for t in runs if t.startswith(p)] for k, p in (('ref2', 'fin-ref2-p4096-'), ('fin_on', 'fin-on-p4096-'))}
if xs['ref2'] and xs['fin_on']:
    a, b = statistics.mean(xs['ref2']), statistics.mean(xs['fin_on'])
    final['p4096'] = dict(ref2_medians=xs['ref2'], fin_on_medians=xs['fin_on'], ref2_mean=round(a, 4), fin_on_mean=round(b, 4),
                          delta_ms=round(b - a, 4), delta_pct=round(100 * (b - a) / a, 2))
a, b = runs.get('fin-ref2-p300'), runs.get('fin-on-p300')
if a and b:
    final['p300'] = dict(ref2=a['median_half_ms'], fin_on=b['median_half_ms'], delta_ms=round(b['median_half_ms'] - a['median_half_ms'], 4))
pr = [t for t in ('fin-ref2-p30000', 'fin-ref2-p30000-b') if t in runs]
pc = [t for t in ('fin-on-p30000', 'fin-on-p30000-b') if t in runs]
if pr and pc:
    g = lambda ts, k: [runs[t][k] for t in ts]
    final['p30000'] = dict(order='ref2-a, on-a, (on-b, ref2-b)', ref2_medians=g(pr, 'median_half_ms'), fin_on_medians=g(pc, 'median_half_ms'),
                           delta_ms=round(statistics.mean(g(pc, 'median_half_ms')) - statistics.mean(g(pr, 'median_half_ms')), 4),
                           ref2_engine_wait_ms=g(pr, 'engine_wait_ms'), fin_on_engine_wait_ms=g(pc, 'engine_wait_ms'),
                           ref2_engine_enqueue_ms=g(pr, 'engine_enqueue_loop_ms'), fin_on_engine_enqueue_ms=g(pc, 'engine_enqueue_loop_ms'),
                           ref2_host_load_1m=g(pr, 'host_load_1m'), fin_on_host_load_1m=g(pc, 'host_load_1m'))
result = dict(
    schema='ownrt.lab.qsa-select.v1', date='2026-10-26', card='0000:27:00.0 (renderD131)',
    launch_template='research/context-64k/rank1-card27-s24-ctx65536-launch.json (binary replaced; + OWNRT_ATTN_HEADS=1 OWNRT_ATTN_COMBINE2=1 in every run, as the service)',
    driver='engine/tools/tp_rank1_driver.py run --steps 48 --prompt N --batched --rows 32',
    switch=dict(OWNRT_SELECT_FAST='1 (with OWNRT_SELECT_TOPK=1): select_scores_sg (stage 0) + select_topk_row2 (stage 1), select_fast.hpp'),
    best=dict(env={'OWNRT_SELECT_TOPK': '1', 'OWNRT_SELECT_FAST': '1'}, binary_sha256=builds['fin']['binary_sha256']),
    builds=builds, final_series=final, runs=runs, compares=compares, rank1_device_profiles=profiles,
    bench=json.loads((LAB / 'work' / 'bench_results.json').read_text()))
OUT.write_text(json.dumps(result, indent=1) + '\n')
print(json.dumps(final, indent=1))
