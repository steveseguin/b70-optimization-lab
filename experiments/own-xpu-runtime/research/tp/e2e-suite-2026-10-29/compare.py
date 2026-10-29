#!/usr/bin/env python3
"""Compare the arms' suite JSONs with each other and with the B19 receipt; write results/summary.json.
Usage: compare.py [ARM ...]  (default A B C, missing arms skipped)"""
import json, statistics, sys
from pathlib import Path
D = Path(__file__).resolve().parent
B19 = Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/service-speed/d-mtp-fp8/suite/f32-suite-51f32b2655cc-ctx65536-split23.json')
arms = [a for a in (sys.argv[1:] or ['A', 'B', 'C']) if (D / f'results/arm-{a}/suite.json').exists()]
ref = json.loads(B19.read_text())
data = {a: json.loads((D / f'results/arm-{a}/suite.json').read_text()) for a in arms}
order = [r['prompt_id'] for r in ref['rows']]
def by(s): return {r['prompt_id']: r for r in s['rows']}
R = by(ref)
out = dict(b19=dict(path=str(B19), median_decode_tok_s=ref['median_decode_tok_s'], pooled_acceptance=ref['pooled_acceptance']), arms={}, prompts=[])
for a, s in data.items():
    rows = by(s)
    assert [r['prompt_id'] for r in s['rows']] == order, a
    rates = [rows[p]['decode_tok_s'] for p in order]
    ttft = [rows[p]['prompt_wall_ms'] for p in order]
    out['arms'][a] = dict(label=s['label'], median_decode_tok_s=s['median_decode_tok_s'], recomputed_median=statistics.median(rates),
                          mean_decode_tok_s=statistics.mean(rates), min=min(rates), max=max(rates),
                          pooled_acceptance=s['pooled_acceptance'], guesses=s['guesses'], hits=s['hits'],
                          median_prompt_wall_ms=statistics.median(ttft), median_wall_s=statistics.median(rows[p]['wall_s'] for p in order),
                          cached_tokens_all_zero=all(rows[p]['cached_tokens'] == 0 for p in order),
                          output_tokens=sum(rows[p]['output_tokens'] for p in order),
                          ids_equal_b19=all(rows[p]['output_token_ids'] == R[p]['output_token_ids'] for p in order),
                          sha_equal_b19=all(rows[p]['output_sha256'] == R[p]['output_sha256'] for p in order),
                          mtp_equal_b19=all(rows[p]['mtp'] == R[p]['mtp'] for p in order))
for p in order:
    row = dict(prompt_id=p, prompt_tokens=R[p]['prompt_tokens'], output_tokens=R[p]['output_tokens'], b19_tok_s=round(R[p]['decode_tok_s'], 3))
    for a, s in data.items():
        r = by(s)[p]
        row[a] = dict(tok_s=round(r['decode_tok_s'], 3), acceptance=round(r['acceptance'], 4), prompt_wall_ms=round(r['prompt_wall_ms'], 1),
                      ids_equal_b19=r['output_token_ids'] == R[p]['output_token_ids'])
    ids = [by(s)[p]['output_token_ids'] for s in data.values()]
    row['all_arms_ids_equal'] = all(x == ids[0] for x in ids)
    out['prompts'].append(row)
out['all_arms_identical'] = all(r['all_arms_ids_equal'] for r in out['prompts'])
m = {a: out['arms'][a]['median_decode_tok_s'] for a in arms}
if 'A' in m and 'B' in m: out['speedup_B_vs_A'] = m['B'] / m['A']
if 'B' in m and 'C' in m: out['speedup_C_vs_B'] = m['C'] / m['B']
if 'A' in m and 'C' in m: out['speedup_C_vs_A'] = m['C'] / m['A']
for a in arms:
    if 'B' in data and a != 'B':
        rb, ra = by(data['B']), by(data[a])
        out['arms'][a]['per_prompt_ratio_vs_B'] = {p: round(ra[p]['decode_tok_s'] / rb[p]['decode_tok_s'], 4) for p in order}
(D / 'results/summary.json').write_text(json.dumps(out, indent=1) + '\n')
print(json.dumps({k: v for k, v in out.items() if k != 'prompts'}, indent=1))
