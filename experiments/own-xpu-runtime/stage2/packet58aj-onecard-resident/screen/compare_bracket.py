"""Warm neutrality is sufficient: this experiment targets fresh-load stability."""
from decimal import Decimal
import math
METRIC='class_balanced_tok_s_1_100_intervals_after_ttft'
def compare(views):
    if [v['label'] for v in views]!=['A0','B0','A1','B1','A2']:
        raise ValueError('complete A/B/A/B/A required')
    rates=[];signatures=[]
    for i,v in enumerate(views):
        if v.get('view')!=('resident' if i%2 else 'mapped'):
            raise ValueError('lookup view order differs')
        rows=v['requests']
        if not v.get('passed') or len(rows)!=12 or len({r['prompt_id'] for r in rows})!=12 or any(
            r.get('passed') is not True or r.get('exact_oracle') is not True or r.get('cached_tokens')!=0 or len(r['tokens'])!=128 for r in rows):
            raise ValueError('complete exact 128-token uncached suite required')
        signatures.append([(r['prompt_id'],r['prompt_token_sha256'],r['tokens']) for r in rows])
        rate=v[METRIC]['median']
        if type(rate) not in (int,float) or not math.isfinite(rate) or rate<=0:raise ValueError('invalid rate')
        rates.append(Decimal(str(rate)))
    if any(s!=signatures[0] for s in signatures):raise ValueError('prompt/token identity differs')
    controls=rates[2::2];candidates=rates[1::2]
    drift=max(controls)/min(controls)-1
    neutral=all(a*Decimal('.995')<=c<=a*Decimal('1.005') for a in controls for c in candidates)
    return dict(passed=True,rates=list(map(float,rates)),control_drift_fraction=float(drift),control_drift_passed=drift<=Decimal('.03'),
        resident_within_half_percent=neutral,candidate_beats_all_controls=neutral and drift<=Decimal('.03'),
        minimum_gain_vs_best_control=float(min(candidates)/max(controls)-1),maximum_gain_vs_slowest_control=float(max(candidates)/min(controls)-1),
        warmup_view=dict(label='A0',rate=float(rates[0]),exact=True,excluded_from_drift_and_comparison=True),
        comparison_controls=['A1','A2'],readiness_policy='packet58aj: exact resident copies within +/-0.5% of both warm mapped controls',
        required_gain_fraction=-.005,maximum_gain_fraction=.005,maximum_control_drift_fraction=.03,
        fresh_process_repeat=False,submission_eligible=False)
