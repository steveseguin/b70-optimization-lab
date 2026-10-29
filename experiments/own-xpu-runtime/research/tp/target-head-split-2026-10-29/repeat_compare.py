#!/usr/bin/env python3
"""Fresh-server repeat of research/tp/target-head-split-2026-10-29: TP against TP with both head splits, four servers in
the order tp-r1, tpts-r1, tp-r2, tpts-r2 (results/repeat/arm-*), plus the first suite's tp and tpts servers
(results/arm-tp, results/arm-tpts) as a third server of each configuration. Per server: median and mean tok/s and
output equality with B19; per configuration: the mean of the server medians; per adjacent pair: the per-prompt ratios;
between servers of one configuration: the drift. Writes results/repeat/summary.json."""
import json, statistics as st
from pathlib import Path
D = Path(__file__).resolve().parent
B19 = Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/service-speed/d-mtp-fp8/suite/f32-suite-51f32b2655cc-ctx65536-split23.json')
ref = json.loads(B19.read_text()); order = [r['prompt_id'] for r in ref['rows']]; R = {r['prompt_id']: r for r in ref['rows']}
servers = {n: D / f'results/repeat/arm-{n}/suite.json' for n in ('tp-r1', 'tpts-r1', 'tp-r2', 'tpts-r2')}
servers.update({'tp-r0': D / 'results/arm-tp/suite.json', 'tpts-r0': D / 'results/arm-tpts/suite.json'})
data = {n: {r['prompt_id']: r for r in json.loads(p.read_text())['rows']} for n, p in servers.items() if p.exists()}
out = dict(b19=str(B19), servers={}, configurations={}, pairs={}, drift={})
for n, rows in data.items():
    rates = [rows[p]['decode_tok_s'] for p in order]
    out['servers'][n] = dict(median=st.median(rates), mean=st.mean(rates), min=min(rates), max=max(rates),
        ids_equal_b19=all(rows[p]['output_token_ids'] == R[p]['output_token_ids'] for p in order),
        sha_equal_b19=all(rows[p]['output_sha256'] == R[p]['output_sha256'] for p in order),
        mtp_equal_b19=all(rows[p]['mtp'] == R[p]['mtp'] for p in order),
        cached_tokens_all_zero=all(rows[p]['cached_tokens'] == 0 for p in order),
        output_tokens=sum(rows[p]['output_tokens'] for p in order))
def ratios(a, b): return [data[a][p]['decode_tok_s'] / data[b][p]['decode_tok_s'] for p in order]
for cfg in ('tp', 'tpts'):
    rep = [n for n in (f'{cfg}-r1', f'{cfg}-r2') if n in data]; allv = [n for n in (f'{cfg}-r0', f'{cfg}-r1', f'{cfg}-r2') if n in data]
    out['configurations'][cfg] = dict(repeat_servers=rep, mean_of_repeat_medians=st.mean(out['servers'][n]['median'] for n in rep) if rep else None,
        all_servers=allv, mean_of_all_medians=st.mean(out['servers'][n]['median'] for n in allv) if allv else None)
    for a, b in ((f'{cfg}-r2', f'{cfg}-r1'), (f'{cfg}-r1', f'{cfg}-r0'), (f'{cfg}-r2', f'{cfg}-r0')):
        if a in data and b in data:
            r = ratios(a, b); out['drift'][f'{a}/{b}'] = dict(median_ratio=out['servers'][a]['median'] / out['servers'][b]['median'],
                per_prompt_median=st.median(r), per_prompt_range=[min(r), max(r)])
for a, b in (('tpts-r1', 'tp-r1'), ('tpts-r2', 'tp-r2'), ('tpts-r1', 'tp-r2'), ('tpts-r0', 'tp-r0')):
    if a in data and b in data:
        r = ratios(a, b); out['pairs'][f'{a}/{b}'] = dict(median_ratio=out['servers'][a]['median'] / out['servers'][b]['median'],
            per_prompt_median=st.median(r), per_prompt_range=[min(r), max(r)], prompts_faster=sum(x > 1 for x in r),
            per_prompt={p: round(x, 4) for p, x in zip(order, r)})
c = out['configurations']
if c['tp']['mean_of_repeat_medians'] and c['tpts']['mean_of_repeat_medians']:
    out['repeat_mean_ratio_tpts_vs_tp'] = c['tpts']['mean_of_repeat_medians'] / c['tp']['mean_of_repeat_medians']
ids = [data[n][p]['output_token_ids'] for n in data for p in order]
out['all_servers_identical'] = all(all(data[n][p]['output_token_ids'] == R[p]['output_token_ids'] for p in order) for n in data)
(D / 'results/repeat').mkdir(parents=True, exist_ok=True)
(D / 'results/repeat/summary.json').write_text(json.dumps(out, indent=1) + '\n')
print(json.dumps({k: v for k, v in out.items() if k != 'pairs'}, indent=1))
for k, v in out['pairs'].items(): print(k, {kk: vv for kk, vv in v.items() if kk != 'per_prompt'})
