"""Screen decision only; repeats share one load and cannot qualify a record."""
import math

def compare(views):
    if [v['label'] for v in views]!=['A0','B0','A1']:
        raise ValueError('complete A/B/A required')
    rates=[]
    for view in views:
        if not view.get('passed') or len(view['requests'])!=12 or any(
                not r.get('exact_oracle') or r.get('cached_tokens')!=0 for r in view['requests']):
            raise ValueError('complete exact uncached suite required in each view')
        rate=view['class_balanced_tok_s_1_100_intervals_after_ttft']['median']
        if type(rate) not in (float,int) or not math.isfinite(rate) or rate<=0:
            raise ValueError('positive measured class-balanced rate required')
        rates.append(rate)
    controls=rates[::2];candidates=rates[1::2]
    drift=max(controls)/min(controls)-1
    return dict(rates=rates,control_drift_fraction=drift,control_drift_passed=drift<=.03,
        candidate_beats_all_controls=drift<=.03 and min(candidates)>=max(controls)*1.005,
        minimum_gain_vs_best_control=min(candidates)/max(controls)-1,
        required_gain_fraction=.005,maximum_control_drift_fraction=.03,
        fresh_process_repeat=False,submission_eligible=False)
