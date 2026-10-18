"""Screen decision only; repeats share one load and cannot qualify a record."""
import math
from decimal import Decimal

def compare(views):
    if [v['label'] for v in views]!=['A0','B0','A1','B1','A2']:
        raise ValueError('complete A/B/A/B/A required')
    rates=[]
    for view in views:
        if not view.get('passed') or len(view['requests'])!=12 or any(
                not r.get('exact_oracle') or r.get('cached_tokens')!=0 for r in view['requests']):
            raise ValueError('complete exact uncached suite required in each view')
        rate=view['class_balanced_tok_s_1_100_intervals_after_ttft']['median']
        if type(rate) not in (float,int) or not math.isfinite(rate) or rate<=0:
            raise ValueError('positive measured class-balanced rate required')
        rates.append(Decimal(str(rate)))
    # Packet58wb amendment: A0 is exact and reported, but only A1/A2
    # participate in the warm steady-state speed and drift comparison.
    controls=rates[2::2];candidates=rates[1::2]
    drift=max(controls)/min(controls)-1
    drift_passed=max(controls)<=min(controls)*Decimal('1.03')
    return dict(rates=list(map(float,rates)),control_drift_fraction=float(drift),control_drift_passed=drift_passed,
        candidate_beats_all_controls=drift_passed and all(c>=a*Decimal('1.005') for c in candidates for a in controls),
        minimum_gain_vs_best_control=float(min(candidates)/max(controls)-1),
        warmup_view=dict(label='A0',rate=float(rates[0]),exact=True,excluded_from_drift_and_comparison=True),
        comparison_controls=['A1','A2'],readiness_policy='packet58xb: packet58wb first-view warm-up amendment',
        required_gain_fraction=.005,maximum_control_drift_fraction=.03,
        fresh_process_repeat=False,submission_eligible=False)
