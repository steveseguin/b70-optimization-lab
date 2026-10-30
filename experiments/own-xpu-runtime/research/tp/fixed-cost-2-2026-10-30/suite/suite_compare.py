#!/usr/bin/env python3
"""Lab-service results of research/tp/fixed-cost-2-2026-10-30/suite (results/suite/arm-<name>-c<ctx>): per server the 12-prompt
suite median/mean decode tok/s and equality of every output (ids, sha256, MTP guesses/hits) with B19
(f32-suite-51f32b2655cc-ctx65536-split23.json), the 3,490-token TTFT probe, and at 131072 the 121,854/512 long request
(TTFT = service prompt_wall_ms, decode = (512-1)/first-to-last token, output ids against both long512 references).
Configurations: the mean of their server medians; per pair (each B server against each A server of the same context)
the per-prompt ratios. Writes results/suite/summary.json."""
import json, statistics as st
from pathlib import Path
D = Path(__file__).resolve().parent
B19 = Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/service-speed/d-mtp-fp8/suite/f32-suite-51f32b2655cc-ctx65536-split23.json')
ref = json.loads(B19.read_text()); order = [r['prompt_id'] for r in ref['rows']]; R = {r['prompt_id']: r for r in ref['rows']}
S = D / 'results/suite'
out = dict(b19=str(B19), servers={}, configurations={}, pairs={})
data = {}
for d in sorted(S.glob('arm-*')):
    if not (d / 'suite.json').exists():
        continue
    n = d.name[4:]
    rows = {r['prompt_id']: r for r in json.loads((d / 'suite.json').read_text())['rows']}
    data[n] = rows
    rates = [rows[p]['decode_tok_s'] for p in order]
    row = dict(median=st.median(rates), mean=st.mean(rates), min=min(rates), max=max(rates),
               ids_equal_b19=all(rows[p]['output_token_ids'] == R[p]['output_token_ids'] for p in order),
               sha_equal_b19=all(rows[p]['output_sha256'] == R[p]['output_sha256'] for p in order),
               mtp_equal_b19=all(rows[p]['mtp'] == R[p]['mtp'] for p in order),
               cached_tokens_all_zero=all(rows[p]['cached_tokens'] == 0 for p in order),
               output_tokens=sum(rows[p]['output_tokens'] for p in order), request_wall_s_sum=sum(rows[p]['wall_s'] for p in order),
               per_prompt={p: rows[p]['decode_tok_s'] for p in order})
    t = d / 'ttft-long.json'
    if t.exists():
        tt = json.loads(t.read_text()); row['ttft_3490'] = dict(prompt_wall_ms=tt['prompt_wall_ms'], decode_tok_s=tt.get('decode_tok_s'),
                                                                output_sha256=tt['output_sha256'], prompt_tokens=tt['prompt_tokens'])
    l = d / 'long512.json'
    if l.exists():
        ll = json.loads(l.read_text())
        row['long512'] = dict(prompt_tokens=ll['prompt_tokens'], prompt_equals_long512_prompt_i32=ll['prompt_equals_long512_prompt_i32'],
                              ttft_s=ll['prompt_wall_ms'] / 1000, decode_tok_s_all511=ll['decode_tok_s'], request_wall_s=ll['wall_s'],
                              output_tokens=ll['output_tokens'], mtp=ll.get('mtp'), output_ids_sha256=ll['output_ids_sha256'], compare=ll['compare'])
    out['servers'][n] = row
cfgs = {}
for n in data:
    arm, rest = n.rsplit('-r', 1); rep, ctx = rest.split('-c')
    cfgs.setdefault(f'{arm}-c{ctx}', []).append(n)
for c, s in sorted(cfgs.items()):
    out['configurations'][c] = dict(servers=s, mean_of_medians=st.mean(out['servers'][n]['median'] for n in s),
                                    mean_request_wall_s_sum=st.mean(out['servers'][n]['request_wall_s_sum'] for n in s))
for b, a in (('tptsxqcp-c65536', 'tptsxqc-c65536'),):
    if b in cfgs and a in cfgs:
        out['configurations'][f'{b} / {a}'] = out['configurations'][b]['mean_of_medians'] / out['configurations'][a]['mean_of_medians']
        for nb in cfgs[b]:
            for na in cfgs[a]:
                r = [data[nb][p]['decode_tok_s'] / data[na][p]['decode_tok_s'] for p in order]
                out['pairs'][f'{nb} / {na}'] = dict(medians=out['servers'][nb]['median'] / out['servers'][na]['median'],
                    per_prompt_median=st.median(r), per_prompt_min=min(r), per_prompt_max=max(r), faster_on=sum(x > 1 for x in r))
(S / 'summary.json').write_text(json.dumps(out, indent=1) + '\n')
for n, r in out['servers'].items():
    print(n, round(r['median'], 2), round(r['mean'], 2), f"{r['min']:.2f}-{r['max']:.2f}", 'B19', r['ids_equal_b19'], r['sha_equal_b19'], r['mtp_equal_b19'],
          'ttft3490', r.get('ttft_3490', {}).get('prompt_wall_ms'), 'long512', {k: v for k, v in r.get('long512', {}).items() if k in ('ttft_s', 'decode_tok_s_all511', 'compare')})
for c, v in out['configurations'].items():
    print(c, v if not isinstance(v, dict) else round(v['mean_of_medians'], 3))
for p, v in out['pairs'].items():
    print(p, {k: round(x, 4) if isinstance(x, float) else x for k, x in v.items()})
