#!/usr/bin/env python3
"""Suite of research/tp/fault-ladder-2026-10-29 (copy of persistent-thread-2026-10-29/suite_compare.py; adds full request wall
times): four fresh lab servers in the order tptsxq-r1, tptsxqc-r1, tptsxq-r2, tptsxqc-r2
(results/suite/arm-*), one binary, context 65536. Per server: median and mean decode tok/s and equality of every output
(ids, sha256, MTP guesses/hits) with B19; per configuration: the mean of its two server medians (pair means); per pair
(each tptsxqc server against each tptsxq server): the per-prompt ratios. Writes results/suite/summary.json."""
import json, statistics as st
from pathlib import Path
D = Path(__file__).resolve().parent
B19 = Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/service-speed/d-mtp-fp8/suite/f32-suite-51f32b2655cc-ctx65536-split23.json')
ref = json.loads(B19.read_text()); order = [r['prompt_id'] for r in ref['rows']]; R = {r['prompt_id']: r for r in ref['rows']}
names = ('tptsxq-r1', 'tptsxqc-r1', 'tptsxq-r2', 'tptsxqc-r2')
data = {n: {r['prompt_id']: r for r in json.loads((D / f'results/suite/arm-{n}/suite.json').read_text())['rows']}
        for n in names if (D / f'results/suite/arm-{n}/suite.json').exists()}
out = dict(b19=str(B19), order=list(names), servers={}, configurations={}, pairs={})
for n, rows in data.items():
    rates = [rows[p]['decode_tok_s'] for p in order]
    out['servers'][n] = dict(median=st.median(rates), mean=st.mean(rates), min=min(rates), max=max(rates),
        ids_equal_b19=all(rows[p]['output_token_ids'] == R[p]['output_token_ids'] for p in order),
        sha_equal_b19=all(rows[p]['output_sha256'] == R[p]['output_sha256'] for p in order),
        mtp_equal_b19=all(rows[p]['mtp'] == R[p]['mtp'] for p in order),
        cached_tokens_all_zero=all(rows[p]['cached_tokens'] == 0 for p in order),
        output_tokens=sum(rows[p]['output_tokens'] for p in order), request_wall_s_sum=sum(rows[p]['wall_s'] for p in order),
        request_wall_s_max=max(rows[p]['wall_s'] for p in order), per_prompt_wall_s={p: round(rows[p]['wall_s'], 4) for p in order},
        per_prompt={p: rows[p]['decode_tok_s'] for p in order})
for cfg in ('tptsxq', 'tptsxqc'):
    s = [n for n in (f'{cfg}-r1', f'{cfg}-r2') if n in data]
    out['configurations'][cfg] = dict(servers=s, pair_mean_of_medians=st.mean(out['servers'][n]['median'] for n in s) if s else None,
        pair_mean_request_wall_s_sum=st.mean(out['servers'][n]['request_wall_s_sum'] for n in s) if s else None)
c = out['configurations']
if c['tptsxq']['pair_mean_of_medians'] and c['tptsxqc']['pair_mean_of_medians']:
    out['pair_mean_ratio_tptsxqc_vs_tptsxq'] = c['tptsxqc']['pair_mean_of_medians'] / c['tptsxq']['pair_mean_of_medians']
    out['request_wall_ratio_tptsxqc_vs_tptsxq'] = c['tptsxqc']['pair_mean_request_wall_s_sum'] / c['tptsxq']['pair_mean_request_wall_s_sum']
for a, b in (('tptsxqc-r1', 'tptsxq-r1'), ('tptsxqc-r2', 'tptsxq-r2'), ('tptsxqc-r1', 'tptsxq-r2'), ('tptsxqc-r2', 'tptsxq-r1')):
    if a in data and b in data:
        r = [data[a][p]['decode_tok_s'] / data[b][p]['decode_tok_s'] for p in order]
        out['pairs'][f'{a}/{b}'] = dict(median_ratio=out['servers'][a]['median'] / out['servers'][b]['median'], per_prompt_median=st.median(r),
            per_prompt_range=[min(r), max(r)], prompts_faster=sum(x > 1 for x in r), per_prompt={p: round(x, 4) for p, x in zip(order, r)})
        w = [data[a][p]['wall_s'] / data[b][p]['wall_s'] for p in order]
        out['pairs'][f'{a}/{b}'].update(request_wall_ratio_median=st.median(w), request_wall_ratio_range=[min(w), max(w)],
            prompts_shorter=sum(x < 1 for x in w), per_prompt_wall_ratio={p: round(x, 4) for p, x in zip(order, w)})
out['all_servers_outputs_equal_b19'] = all(v['ids_equal_b19'] and v['sha_equal_b19'] and v['mtp_equal_b19'] for v in out['servers'].values())
(D / 'results/suite').mkdir(parents=True, exist_ok=True)
(D / 'results/suite/summary.json').write_text(json.dumps(out, indent=1) + '\n')
print(json.dumps({k: v for k, v in out.items() if k not in ('pairs', 'servers')}, indent=1))
for n, v in out['servers'].items(): print(n, {k: vv for k, vv in v.items() if not k.startswith('per_prompt')})
for k, v in out['pairs'].items(): print(k, {kk: vv for kk, vv in v.items() if not kk.startswith('per_prompt')})
