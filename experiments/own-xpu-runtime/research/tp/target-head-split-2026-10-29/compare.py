#!/usr/bin/env python3
"""Compare the service-ready suite arms (two-card control vs four-card TP, both at context 65536 with 256-row batched
prompt reading) with each other and with the B19 receipt at 65536; include the long-prompt TTFT probe and the startup
prefill gates. Writes results/summary.json. Usage: compare.py [ARM ...] (default two tp)
Copy for research/tp/draft-split-2026-10-29: arms two tp tps; adds the paired per-prompt ratios of tps against tp and
two, and the long-prompt output equality across all arms.
research/tp/target-head-split-2026-10-29: paired ratios for every split arm present (tps, tpt, tpts)."""
import json, statistics, sys
from pathlib import Path
D = Path(__file__).resolve().parent
B19 = Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/service-speed/d-mtp-fp8/suite/f32-suite-51f32b2655cc-ctx65536-split23.json')
arms = [a for a in (sys.argv[1:] or ['two', 'tp']) if (D / f'results/arm-{a}/suite.json').exists()]
ref = json.loads(B19.read_text())
data = {a: json.loads((D / f'results/arm-{a}/suite.json').read_text()) for a in arms}
order = [r['prompt_id'] for r in ref['rows']]
def by(s): return {r['prompt_id']: r for r in s['rows']}
R = by(ref)
out = dict(b19=dict(path=str(B19), median_decode_tok_s=ref['median_decode_tok_s'], pooled_acceptance=ref['pooled_acceptance'],
                    median_prompt_wall_ms=statistics.median(R[p]['prompt_wall_ms'] for p in order)), arms={}, prompts=[])
for a, s in data.items():
    rows = by(s)
    assert [r['prompt_id'] for r in s['rows']] == order, a
    rates = [rows[p]['decode_tok_s'] for p in order]; ttft = [rows[p]['prompt_wall_ms'] for p in order]
    arm = dict(label=s['label'], median_decode_tok_s=s['median_decode_tok_s'], recomputed_median=statistics.median(rates),
               mean_decode_tok_s=statistics.mean(rates), min=min(rates), max=max(rates),
               pooled_acceptance=s['pooled_acceptance'], guesses=s['guesses'], hits=s['hits'],
               median_prompt_wall_ms=statistics.median(ttft), mean_prompt_wall_ms=statistics.mean(ttft),
               median_wall_s=statistics.median(rows[p]['wall_s'] for p in order),
               cached_tokens_all_zero=all(rows[p]['cached_tokens'] == 0 for p in order),
               output_tokens=sum(rows[p]['output_tokens'] for p in order),
               ids_equal_b19=all(rows[p]['output_token_ids'] == R[p]['output_token_ids'] for p in order),
               sha_equal_b19=all(rows[p]['output_sha256'] == R[p]['output_sha256'] for p in order),
               mtp_equal_b19=all(rows[p]['mtp'] == R[p]['mtp'] for p in order))
    t = D / f'results/arm-{a}/ttft-long.json'
    if t.exists():
        tt = json.loads(t.read_text()); arm['ttft_long'] = {k: v for k, v in tt.items() if k != 'output_token_ids'}
    g = D / f'results/arm-{a}/prefill-gate.json'
    if g.exists():
        gg = json.loads(g.read_text()); arm['prefill_gate'] = dict(passed=gg['passed'], rows=gg['rows'], cases=len(gg['cases']),
            cases_passed=sum(c['passed'] for c in gg['cases']), binary=gg['binary_sha256'][:12],
            batched_vs_token_prompt_ms=[(c['case'], c.get('prompt_wall_ms')) for c in gg['cases'] if 'prompt_wall_ms' in c])
    out['arms'][a] = arm
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
if 'two' in data and 'tp' in data:
    out['speedup_tp_vs_two'] = out['arms']['tp']['median_decode_tok_s'] / out['arms']['two']['median_decode_tok_s']
    rb, ra = by(data['two']), by(data['tp'])
    out['per_prompt_ratio_tp_vs_two'] = {p: round(ra[p]['decode_tok_s'] / rb[p]['decode_tok_s'], 4) for p in order}
    out['median_ttft_ratio_tp_vs_two'] = out['arms']['tp']['median_prompt_wall_ms'] / out['arms']['two']['median_prompt_wall_ms']
    lt, lw = out['arms']['tp'].get('ttft_long'), out['arms']['two'].get('ttft_long')
    if lt and lw:
        out['ttft_long_ratio_tp_vs_two'] = lt['prompt_wall_ms'] / lw['prompt_wall_ms']
        out['ttft_long_outputs_equal'] = json.loads((D / 'results/arm-tp/ttft-long.json').read_text())['output_token_ids'] == json.loads((D / 'results/arm-two/ttft-long.json').read_text())['output_token_ids']
for X in [x for x in ('tps', 'tpt', 'tpts') if x in data]:
    rs = by(data[X])
    for base in ('tp', 'two') + (('tpt',) if X == 'tpts' else ()):
        if base in data:
            rb = by(data[base]); ratios = [rs[p]['decode_tok_s'] / rb[p]['decode_tok_s'] for p in order]
            out[f'speedup_{X}_vs_{base}'] = out['arms'][X]['median_decode_tok_s'] / out['arms'][base]['median_decode_tok_s']
            out[f'per_prompt_ratio_{X}_vs_{base}'] = {p: round(r, 4) for p, r in zip(order, ratios)}
            out[f'per_prompt_ratio_{X}_vs_{base}_median'] = statistics.median(ratios)
            out[f'per_prompt_ratio_{X}_vs_{base}_range'] = [min(ratios), max(ratios)]
            lt, lb = out['arms'][X].get('ttft_long'), out['arms'][base].get('ttft_long')
            if lt and lb: out[f'ttft_long_ratio_{X}_vs_{base}'] = lt['prompt_wall_ms'] / lb['prompt_wall_ms']
    long_ids = [json.loads((D / f'results/arm-{a}/ttft-long.json').read_text())['output_token_ids'] for a in data if (D / f'results/arm-{a}/ttft-long.json').exists()]
    out['ttft_long_outputs_equal_all_arms'] = bool(long_ids) and all(x == long_ids[0] for x in long_ids)
(D / 'results').mkdir(exist_ok=True)
(D / 'results/summary.json').write_text(json.dumps(out, indent=1) + '\n')
print(json.dumps({k: v for k, v in out.items() if k != 'prompts'}, indent=1))
