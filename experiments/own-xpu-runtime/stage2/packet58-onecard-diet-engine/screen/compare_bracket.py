"""Warm neutrality is sufficient: this experiment targets fresh-load stability."""
from decimal import Decimal
import math
METRIC='class_balanced_tok_s_1_100_intervals_after_ttft'
CONTROL_VIEW='max23'          # the record line (packet58-onecard-cache23-chain): cache_cap max23, production gate/up kernel
CANDIDATE_VIEW='max23+diet'   # the same load with expert_gateup=diet (p58ag_diet::GateUp)
def compare(views):
    if [v['label'] for v in views]!=['A0','B0','A1','B1','A2']:
        raise ValueError('complete A/B/A/B/A required')
    rates=[];signatures=[]
    for i,v in enumerate(views):
        if v.get('view')!=(CANDIDATE_VIEW if i%2 else CONTROL_VIEW):
            raise ValueError('gate-up view order differs')
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
        diet_beats_each_warm_control=neutral,candidate_beats_all_controls=neutral and drift<=Decimal('.03'),
        minimum_gain_vs_best_control=float(min(candidates)/max(controls)-1),maximum_gain_vs_slowest_control=float(max(candidates)/min(controls)-1),
        warmup_view=dict(label='A0',rate=float(rates[0]),exact=True,excluded_from_drift_and_comparison=True),
        comparison_controls=['A1','A2'],readiness_policy='packet58-onecard-diet-engine: both diet views >=+0.5% over every warm max23 (record line) control, drift <=3%, 60/60 exact; chain rule >=+2% over every control view and >=37.335',
        required_gain_fraction=.005,maximum_control_drift_fraction=.03,
        fresh_process_repeat=False,submission_eligible=False)


# packet58-onecard-diet-engine decision (coordinator ruling, quoted in README). Kept on every outcome.
RECORD_TOK_S = 36.602512          # packet58-onecard-cache23-chain WS128, LocalMaxxing cmvkcqznb002lng01fsrhjn7t
CHAIN_BAR_TOK_S = 37.33456224     # exactly 1.02 x 36.602512 (the ruling quotes it rounded, 37.335)
WARM_FLOOR_TOK_S = 36.0           # below this the host is disturbed (A arm = the 36.60 record line)
SAVING_FLOOR_US_PER_LAYER = 5.0   # gate/up saving from the host scopes: per-token layer-body delta / 48 serial layers
LAYERS = 48

def s58de_decision(comparison, readout):
    """screen winner iff both diet views >= 1.005 x every warm max23 control (A1, A2), 60/60 exact (compare() raised
    otherwise), drift <= 3 %; chain rule iff also >= 1.02 x EVERY control view (A0 included) and >= 37.33456224 tok/s.
    Kill rules: any inexact view (compare() refuses); DRM > 30.5 GB is the native/supervisor guard (the window refuses
    before this runs); control drift > 3 % or a warm control < 36.0 tok/s -> host disturbed, report, no automatic
    rerun; gate/up saving < 5 us per layer from the host scopes (mean decode-token layer body of the warm controls
    minus the diet views, / 48); fills/token or fill MB/token differing between the two arms (the diet moves no
    bytes: identical routes give identical fills; a difference means the views were not the same computation)."""
    rates = [Decimal(str(r)) for r in comparison['rates']]
    controls, diets = rates[0::2], rates[1::2]
    warm = rates[2::2]
    drift = Decimal(str(comparison['control_drift_fraction']))
    kills = []
    if drift > Decimal('.03'):
        kills.append('control drift > 3 %: host disturbed; report, no automatic rerun')
    if any(a < Decimal(str(WARM_FLOOR_TOK_S)) for a in warm):
        kills.append(f'warm max23 control below {WARM_FLOOR_TOK_S} tok/s: host disturbed; report, no automatic rerun')
    per_view = {}
    views = (readout or {}).get('views') or {}
    for label, v in views.items():
        per_view[label] = dict(fills_per_token=v.get('fills_per_token'), fill_mb_per_token=v.get('fill_mb_per_token'),
                               layer_body_ms=v.get('layer_body_ms'), wait_ms=v.get('wait_ms'), wall_ms=v.get('wall_ms'),
                               miss_read_regression=v.get('miss_read_regression'))
    # fills: equal across arms (the diet moves no bytes)
    fills_equal = None
    a_views = [views[l] for l in ('A1', 'A2') if l in views]
    b_views = [views[l] for l in ('B0', 'B1') if l in views]
    if a_views and b_views and all(v.get('fills_per_token') is not None and v.get('fill_mb_per_token') is not None for v in a_views + b_views):
        fills = {round(v['fills_per_token'], 3) for v in a_views + b_views}
        mbs = {round(v['fill_mb_per_token'], 3) for v in a_views + b_views}
        fills_equal = len(fills) == 1 and len(mbs) == 1
        if not fills_equal:
            kills.append('fills/token or fill MB/token differ between the production and diet views: the diet moved bytes; not the same computation; report')
    else:
        kills.append('fills/token unavailable for both arms: readout failed; report')
    # gate/up saving from the host scopes
    saving = None
    if a_views and b_views and all(v.get('layer_body_ms') is not None for v in a_views + b_views):
        ctrl = sum(Decimal(str(v['layer_body_ms'])) for v in a_views) / len(a_views)
        cand = sum(Decimal(str(v['layer_body_ms'])) for v in b_views) / len(b_views)
        saving = float((ctrl - cand) * 1000 / LAYERS)
        if saving < SAVING_FLOOR_US_PER_LAYER:
            kills.append(f'gate/up saving {saving:.2f} us per layer < {SAVING_FLOOR_US_PER_LAYER} us (host scopes: layer-body delta / 48); report')
    else:
        kills.append('layer-body host scope unavailable for both arms: readout failed; report')
    screen_winner = bool(comparison['candidate_beats_all_controls']) and not kills
    chain = screen_winner and all(b >= a * Decimal('1.02') for a in controls for b in diets) and all(b >= Decimal(str(CHAIN_BAR_TOK_S)) for b in diets)
    return dict(schema='packet58dietengine.decision.v1', screen_winner=screen_winner, chain_rule=chain,
                kill_rules_fired=kills, record_tok_s=RECORD_TOK_S, chain_bar_tok_s=CHAIN_BAR_TOK_S, warm_floor_tok_s=WARM_FLOOR_TOK_S,
                saving_floor_us_per_layer=SAVING_FLOOR_US_PER_LAYER, control_views=list(map(float, controls)), diet_views=list(map(float, diets)),
                minimum_gain_vs_every_control_view=float(min(diets) / max(controls) - 1), fills_equal_across_arms=fills_equal,
                gateup_saving_us_per_layer=saving, saving_definition='(mean warm-control layer_body_ms - mean diet layer_body_ms) x 1000 / 48; '
                'layer_body_ms = wall_ms - transfer_wall_ms - prepare_ms of decode tokens (generated_index >= 2): the compute window between the head load and the tail check',
                per_view=per_view,
                drm_guard='native after-load + supervisor refuse DRM total-vram0 > 30,500,000,000 B before any view (unchanged, never lowered)',
                rule='screen winner iff both diet views >= 1.005 x every warm max23 control, 60/60 exact, drift <= 3 %, no kill; chain iff also >= 1.02 x every control view and >= 37.33456224; '
                     'kills: inexact view, DRM > 30.5 GB, drift > 3 %, warm control < 36.0, saving < 5 us/layer, fills differ; no automatic rerun on any kill')
