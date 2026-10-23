"""Warm neutrality is sufficient: this experiment targets fresh-load stability."""
from decimal import Decimal
import math
METRIC='class_balanced_tok_s_1_100_intervals_after_ttft'
def compare(views):
    if [v['label'] for v in views]!=['A0','B0','A1','B1','A2']:
        raise ValueError('complete A/B/A/B/A required')
    rates=[];signatures=[]
    for i,v in enumerate(views):
        if v.get('view')!=('max23' if i%2 else 'max'):
            raise ValueError('capacity view order differs')
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
    neutral=all(c>=a*Decimal('1.005') for a in controls for c in candidates)
    return dict(passed=True,rates=list(map(float,rates)),control_drift_fraction=float(drift),control_drift_passed=drift<=Decimal('.03'),
        max23_beats_each_warm_control=neutral,candidate_beats_all_controls=neutral and drift<=Decimal('.03'),
        minimum_gain_vs_best_control=float(min(candidates)/max(controls)-1),maximum_gain_vs_slowest_control=float(max(candidates)/min(controls)-1),
        warmup_view=dict(label='A0',rate=float(rates[0]),exact=True,excluded_from_drift_and_comparison=True),
        comparison_controls=['A1','A2'],readiness_policy='packet58-cache23: both max23 views >=+0.5% over every warm max (packet182c record line) control, drift <=3%, 60/60 exact; chain rule >=+2% over every max view and >=36.645',
        required_gain_fraction=.005,maximum_control_drift_fraction=.03,
        fresh_process_repeat=False,submission_eligible=False)


# packet58-cache23 decision (coordinator ruling, one-card synthesis 1). Kept on every outcome.
RECORD_TOK_S = 35.926720          # packet182c chain WS128, LocalMaxxing cmvjejvoi03qcrf0138emu5a6
CHAIN_BAR_TOK_S = 36.6452544      # exactly +2 % over the record (the ruling quotes it rounded, 36.645)
WARM_FLOOR_TOK_S = 35.2           # below this the host is disturbed (A arm = the 35.93 record line)
FILL_REDUCTION_REQUIRED = 0.08    # max23 fills/token must be >= 8 % below max

def s58c23_decision(comparison, readout):
    """screen winner iff both max23 >= 1.005 x every warm max, 60/60 exact (compare() raised otherwise),
    drift <= 3 %; chain rule iff also >= 1.02 x EVERY max view (A0 included) and >= 36.645 tok/s.
    Kill rules: DRM > 30.5 GB is the native/supervisor guard (the window refuses before this runs);
    max23 fills/token not >= 8 % below max -> capacity closed at 23 GB; warm max < 35.2 or drift > 3 %
    -> host disturbed, no automatic rerun. Fills/token, MB/token and the miss-read regression are
    reported for both views from the mechanism readout."""
    rates = [Decimal(str(r)) for r in comparison['rates']]
    maxes, max23s = rates[0::2], rates[1::2]
    warm = rates[2::2]
    drift = Decimal(str(comparison['control_drift_fraction']))
    kills = []
    if drift > Decimal('.03'):
        kills.append('control drift > 3 %: host disturbed; report, no automatic rerun')
    if any(a < Decimal(str(WARM_FLOOR_TOK_S)) for a in warm):
        kills.append(f'warm max view below {WARM_FLOOR_TOK_S} tok/s: host disturbed; report, no automatic rerun')
    per_view = {}
    views = (readout or {}).get('views') or {}
    for label, v in views.items():
        per_view[label] = dict(fills_per_token=v.get('fills_per_token'), fill_mb_per_token=v.get('fill_mb_per_token'),
                               miss_read_regression=v.get('miss_read_regression'))
    fills_ok = None
    a_fills = [views[l]['fills_per_token'] for l in ('A1', 'A2') if l in views and views[l].get('fills_per_token') is not None]
    b_fills = [views[l]['fills_per_token'] for l in ('B0', 'B1') if l in views and views[l].get('fills_per_token') is not None]
    if a_fills and b_fills:
        fills_ok = all(b <= (1 - FILL_REDUCTION_REQUIRED) * a for b in b_fills for a in a_fills)
        if not fills_ok:
            kills.append('max23 fills/token not >= 8 % below max: capacity closed at 23 GB regardless of speed')
    else:
        kills.append('fills/token unavailable for both arms: readout failed; report')
    screen_winner = bool(comparison['candidate_beats_all_controls']) and not kills
    chain = screen_winner and all(b >= a * Decimal('1.02') for a in maxes for b in max23s) and all(b >= Decimal(str(CHAIN_BAR_TOK_S)) for b in max23s)
    return dict(schema='packet58cache23.decision.v1', screen_winner=screen_winner, chain_rule=chain, capacity_closed_at_23gb=fills_ok is False,
                kill_rules_fired=kills, record_tok_s=RECORD_TOK_S, chain_bar_tok_s=CHAIN_BAR_TOK_S, warm_floor_tok_s=WARM_FLOOR_TOK_S,
                fill_reduction_required=FILL_REDUCTION_REQUIRED, max_views=list(map(float, maxes)), max23_views=list(map(float, max23s)),
                minimum_gain_vs_every_max_view=float(min(max23s) / max(maxes) - 1), fills_reduced_8pct=fills_ok, per_view=per_view,
                drm_guard='native after-load + supervisor refuse DRM total-vram0 > 30,500,000,000 B before any view (unchanged, never lowered)',
                rule='screen winner iff both max23 >= 1.005 x every warm max, 60/60 exact, drift <= 3 %; chain iff also >= 1.02 x every max view and >= 36.645; '
                     'no automatic rerun on any kill')
