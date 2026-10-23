"""Packet194 decision (`s194_decision`): is the exp-diet gate/up kernel a screen winner on the k3x record line, and does it clear
the chain rule? Coordinator ruling (2026-10-23, quoted in the README): "Screen winner at >= +0.5 % over every k3x view; chain
rule at >= +2 % over every k3x view AND >= 63.592 tok/s. Kill rules: any inexact view; proposals or acceptance differ; k3x
drift > 0.5 %; the diet's per-layer gate/up saving (from the p150 scopes ...) < 5 us."

Rows (same lane, each depending on the previous): 0 k3x-diet smoke (12 x 64 + incident64, exact, first-request data proof),
1 one-load bracket k3x / k3x-diet / k3x / k3x-diet / k3x of the k3 storage (20-key selections; the k3x views are the record
line's own engine path: the full-shape gate proves their captures equal the 19-key record selection's). There is no fresh
reference row and none is needed: the control is the record selection itself, in-load. Rates are the class-balanced median
of per-prompt 99-interval rates (the record metric, reproduced on packet190's WS128 chain by the tests).

  screen winner  every view 13/13 exact (smoke 12/12 x 64 + incident) with identical draft proposals and per-prompt
                 acceptance across the five 128-token views, k3x drift <= 0.5 % over the three in-load k3x views, the
                 per-layer gate/up saving >= 5 us on BOTH ranks, AND the slower k3x-diet view >= 1.005 x EVERY k3x view;
  chain rule     the same conditions AND the slower k3x-diet view >= 1.02 x every k3x view AND >= 1.02 x 62.345281904743764
                 (= 63.59218754283864 tok/s, the two-card record bar).
Per-layer gate/up saving (reported in us per layer; host-side scopes and rank traces, never a device kernel clock): rank 0 =
(mean hit A of the k3x views - mean hit A of the diet views) / 24 layers (layers 0-23; also layer_body / 24); rank 1 = (mean
hit B k3x - diet) / 21 layers (QSA 27 + 28-47; B also holds the unchanged 248,320-row head); boundary = (mean boundary_body
k3x - diet) / 3 (GDN 24-26). The kill rule reads min(rank 0, rank 1). Priced (lever synthesis 4): +1.32 % per 0.01 ms per
GDN layer on both ranks; packet193's device micro saved 10.8 (L2-warm) to 15.9 (DRAM-cold) us per layer-equivalent.
D is the draft's observed wall (`draft_rows.draft_wall_ms`), never the op-9 duration (packet189 rule).
"""
import hashlib, json, math, statistics as st
from pathlib import Path

RECORD = 62.345281904743764      # packet190 k3x chain, WS128 class-balanced (LocalMaxxing cmvk51wfn001gng01fpbfy89q)
SCREEN_BAR = 0.005
CHAIN_BAR = 0.02
RECORD_BAR = 1.02 * RECORD       # 63.59218754283864
DRIFT_MAX_PCT = 0.5
SAVING_MIN_US = 5.0
PRICE_PCT_PER_MS_PER_GDN_LAYER = 132.0   # +1.32 % per 0.01 ms per GDN layer (lever synthesis 4)
CONTROL = 'k3x'
CANDIDATE = 'k3x-diet'
ORDER = (CONTROL, CANDIDATE, CONTROL, CANDIDATE, CONTROL)
LAYERS = dict(rank0_half=24, rank1_half=21, boundary=3)
KILL = dict(k3x_drift_percent=DRIFT_MAX_PCT, gateup_saving_us_per_layer=SAVING_MIN_US)
RULE = ('screen winner: min k3x-diet >= 1.005 x every in-load k3x view with every view exact, identical proposals/acceptance, k3x drift '
        '<= 0.5 % and a per-layer gate/up saving >= 5 us on both ranks; chain: also min k3x-diet >= 1.02 x every k3x view AND >= 1.02 x '
        '62.345281904743764 = 63.59218754283864 tok/s; D := draft_rows.draft_wall_ms (never op 9); kill rules: inexact, proposals/acceptance '
        'differ, k3x drift > 0.5 %, gate/up saving < 5 us per layer (min of rank 0 A/24 and rank 1 B/21, hit means, host-side)')
ENVELOPE = ('half_total', 'layer_body', 'snapshot', 'token_history', 'token_prep', 'boundary_total', 'boundary_body', 'handoff_export')
STAGE = Path(__file__).resolve().parents[2]


class Incomplete(ValueError):
    pass


def demand(ok, reason):
    if not ok:
        raise Incomplete(reason)


def mean(values):
    values = list(values)
    return st.mean(values) if values else None


def intervals_v3(r, limit=99):
    """Vendored packet85 intervals plus the boundary command (rank 0, op 15) on the ready side, with the draft's observed wall
    (draft_rows.draft_wall_ms, publication observed) as D. The op-9 command duration is kept as D_op9 (reported only)."""
    from interval_model import intervals, duration
    rows = intervals(r, limit)
    boundaries = {t['position']: t for t in r['rank_trace'] if t['rank'] == 0 and t['op'] == 15}
    walls = {d['position']: d['draft_wall_ms'] for d in r.get('draft_rows', []) if d.get('draft_wall_ms') is not None}
    for x in rows:
        b = boundaries.get(x['position'])
        x['Bd'] = duration(b) if b else 0.0
        demand(x['position'] in walls and math.isfinite(walls[x['position']]) and walls[x['position']] > 0, 'missing draft wall (draft_rows.draft_wall_ms) at position %d' % x['position'])
        x['D_op9'] = x['D']
        x['D'] = walls[x['position']]
        ready = max(x['D'], x['R'] + x['C'] + x['Bd'])
        race = max(x['B'], x['A'] + x['spec_start_offset_ms'])
        x['ready_v3_ms'] = ready
        x['boundary_over_draft'] = x['Bd'] > x['D']
        x['prediction_without_gaps_ms'] = ready + race
        x['unresolved_control_gaps_ms'] = x['elapsed_ms'] - ready - race
    return rows


def envelope(view_dir, prompt_ids):
    """Rank-0 host scopes per decode cycle (p150 records in rank0/timings.jsonl) and p76 retirement per speculative half."""
    view_dir = Path(view_dir)
    sums, counts, retire, prepare, halves = {k: 0.0 for k in ENVELOPE}, {k: 0 for k in ENVELOPE}, 0.0, 0.0, 0
    for prompt in prompt_ids:
        r = json.loads((view_dir / prompt / 'receipt.json').read_text())
        stamps = r['token_timestamps'][:100]
        path = view_dir / prompt / 'rank0/timings.jsonl'
        demand(path.is_file(), 'missing rank0 timing stream: ' + str(path))
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            x = json.loads(line)
            if x.get('p150_segment') in sums and stamps[0] <= x['start'] <= x['end'] <= stamps[-1]:
                sums[x['p150_segment']] += x['ms']; counts[x['p150_segment']] += 1
            elif 'half_completion_ms' in x and x.get('speculative') and x.get('fixture', 0) >= 2:
                retire += x.get('p76_retirement_ms', 0.0); prepare += x.get('prepare_ms', 0.0); halves += 1
    per = lambda k: sums[k] / counts[k] if counts[k] else None
    half, body = per('half_total'), per('layer_body')
    parts = {k: per(k) or 0.0 for k in ('snapshot', 'token_history', 'token_prep')}
    out = dict(scopes_ms={k: per(k) for k in ENVELOPE}, scope_counts=counts,
               p76_retirement_ms_per_half=retire / halves if halves else None, prepare_ms_per_half=prepare / halves if halves else None)
    if half is not None and body is not None:
        env = half - body
        out.update(rank0_half_envelope_ms=env, envelope_parts_ms=parts, envelope_unattributed_ms=env - sum(parts.values()))
    bt, bb = per('boundary_total'), per('boundary_body')
    if bt is not None and bb is not None:
        out.update(boundary_envelope_ms=bt - bb, boundary_export_ms=per('handoff_export'))
    return out


def view_stats(view_dir, prompt_ids, variant, require_exact=True):
    """Interval statistics + rank-0 envelope of one view directory (12 prompts, first 99 intervals each).
    require_exact=False only for chain receipts, whose exactness the tests check against the oracle directly."""
    view_dir = Path(view_dir)
    rows, boundaries = [], 0
    for prompt in prompt_ids:
        receipt = view_dir / prompt / 'receipt.json'
        demand(receipt.is_file(), 'missing request receipt: ' + str(receipt))
        r = json.loads(receipt.read_text())
        demand(r.get('passed') is True and (r.get('exact_oracle') is True or not require_exact) and r.get('cached_tokens') == 0, 'request not exact/cold: ' + prompt)
        demand('rank_trace' in r and 'guess_rows' in r and 'generated_token_completion_timestamps' in r and 'draft_rows' in r, 'missing native correction/draft stream: ' + prompt)
        part = intervals_v3(r)
        demand(len(part) == 99, 'expected 99 intervals per 128-token prompt: ' + prompt)
        n = sum(1 for t in r['rank_trace'] if t['rank'] == 0 and t['op'] == 15)
        demand(n > 0, 'every packet194 view runs the boundary: ' + prompt)
        boundaries += n
        rows += part
    hits = [x for x in rows if x['hit']]
    misses = [x for x in rows if not x['hit']]
    demand(len(hits) >= 600 and len(misses) >= 100, 'too few hit/miss intervals')
    return dict(
        variant=variant, intervals=len(rows), hits=len(hits), misses=len(misses), boundary_commands=boundaries,
        hit=dict(D=mean(x['D'] for x in hits), D_op9=mean(x['D_op9'] for x in hits), A=mean(x['A'] for x in hits), B=mean(x['B'] for x in hits), Bd=mean(x['Bd'] for x in hits),
                 offset=mean(x['spec_start_offset_ms'] for x in hits), ready=mean(x['ready_v3_ms'] for x in hits),
                 boundary_over_draft=mean(float(x['boundary_over_draft']) for x in hits),
                 rank1_binds_emission=mean(float(x['B'] >= x['A'] + x['spec_start_offset_ms']) for x in hits),
                 G=mean(x['unresolved_control_gaps_ms'] for x in hits), elapsed=mean(x['elapsed_ms'] for x in hits)),
        miss=dict(D=mean(x['D'] for x in misses), D_op9=mean(x['D_op9'] for x in misses), R=mean(x['R'] for x in misses), C=mean(x['C'] for x in misses), Bd=mean(x['Bd'] for x in misses),
                  A=mean(x['A'] for x in misses), B=mean(x['B'] for x in misses), G=mean(x['unresolved_control_gaps_ms'] for x in misses),
                  elapsed=mean(x['elapsed_ms'] for x in misses)),
        pooled_interval_ms=mean(x['elapsed_ms'] for x in rows), envelope=envelope(view_dir, prompt_ids),
        definition='packet85 intervals (vendored) + boundary on the ready side; D = draft_rows.draft_wall_ms (publication observed), D_op9 = op-9 command duration (reported only); hit = guess verified at the starting emission')


def gateup_saving(control_stats, diet_stats):
    """Per-layer gate/up saving in us (host-side): hit means of the k3x views minus the diet views, divided by the layers of
    each half; None when a side is unmeasured. The kill rule reads min(rank 0 A/24, rank 1 B/21)."""
    def m(stats, side, key):
        values = [s[side][key] for s in stats if s and s.get(side) and s[side].get(key) is not None]
        return mean(values) if values else None
    scope = lambda stats, key: mean(s['envelope']['scopes_ms'][key] for s in stats if s and s.get('envelope', {}).get('scopes_ms', {}).get(key) is not None)
    def delta_us(a, b, layers):
        return None if a is None or b is None else 1000.0 * (a - b) / layers
    out = dict(layers=LAYERS, clock='host-side rank traces and p150 scopes; never a device kernel clock',
               rank0_A_us_per_layer=delta_us(m(control_stats, 'hit', 'A'), m(diet_stats, 'hit', 'A'), LAYERS['rank0_half']),
               rank0_layer_body_us_per_layer=delta_us(scope(control_stats, 'layer_body'), scope(diet_stats, 'layer_body'), LAYERS['rank0_half']),
               rank1_B_us_per_layer=delta_us(m(control_stats, 'hit', 'B'), m(diet_stats, 'hit', 'B'), LAYERS['rank1_half']),
               boundary_body_us_per_layer=delta_us(scope(control_stats, 'boundary_body'), scope(diet_stats, 'boundary_body'), LAYERS['boundary']),
               miss_C_us_per_layer=delta_us(m(control_stats, 'miss', 'C'), m(diet_stats, 'miss', 'C'), LAYERS['rank0_half']))
    both = [out['rank0_A_us_per_layer'], out['rank1_B_us_per_layer']]
    out['min_both_ranks_us_per_layer'] = None if any(v is None for v in both) else min(both)
    if out['min_both_ranks_us_per_layer'] is not None:
        per_ms = mean(both) / 1000.0
        out['priced_gain_percent_from_saving'] = PRICE_PCT_PER_MS_PER_GDN_LAYER * per_ms
        out['price_rule'] = '+1.32 % per 0.01 ms per GDN layer on both ranks (lever synthesis 4), applied to the mean of the two ranks'
    for side in ('hit', 'miss'):
        for key in ('D', 'A', 'B', 'Bd', 'elapsed') + (('C', 'R') if side == 'miss' else ()):
            for name, stats in ((CONTROL, control_stats), (CANDIDATE, diet_stats)):
                value = m(stats, side, key)
                if value is not None:
                    out[f'{name}_{side}_{key}_ms'] = value
    for key in ('rank1_binds_emission', 'boundary_minus_draft'):
        for name, stats in ((CONTROL, control_stats), (CANDIDATE, diet_stats)):
            value = m(stats, 'hit', key) if key != 'boundary_minus_draft' else None
            if value is not None:
                out[f'{name}_hit_{key}'] = value
    for key in ('layer_body', 'half_total', 'boundary_body', 'boundary_total', 'handoff_export'):
        a, b = scope(control_stats, key), scope(diet_stats, key)
        if a is not None and b is not None:
            out[f'scope_{key}_ms'] = {CONTROL: a, CANDIDATE: b, 'delta': b - a}
    return out


def decide(smoke, bracket):
    """smoke: dict(kind='smoke', passed, exact); bracket: dict(kind='bracket', views=[5 records])."""
    demand(smoke.get('kind') == 'smoke' and smoke.get('passed') is True and smoke.get('exact') is True, 'k3x-diet smoke must pass exact first')
    demand(bracket.get('kind') == 'bracket' and [v['variant'] for v in bracket['views']] == list(ORDER), 'bracket must be k3x/k3x-diet/k3x/k3x-diet/k3x')
    views = list(bracket['views'])
    for v in views:
        demand(isinstance(v.get('rate'), (int, float)) and math.isfinite(v['rate']) and v['rate'] > 0, 'invalid view rate')
    exact = all(v.get('all_13_exact') is True and v.get('exact_count') == 13 for v in views)
    proposals = all(v['draft_proposals'] == views[0]['draft_proposals'] for v in views)
    acceptance = all(v['acceptance_counts'] == views[0]['acceptance_counts'] for v in views)
    control = [v['rate'] for v in views if v['variant'] == CONTROL]
    cand = [v['rate'] for v in views if v['variant'] == CANDIDATE]
    drift = 100 * (max(control) / min(control) - 1)
    drift_ok = drift <= DRIFT_MAX_PCT
    gain = min(cand) / max(control) - 1
    stats = lambda rows: [r.get('interval_stats') for r in rows if isinstance(r.get('interval_stats'), dict) and 'hit' in r.get('interval_stats', {})]
    saving = gateup_saving(stats([v for v in views if v['variant'] == CONTROL]), stats([v for v in views if v['variant'] == CANDIDATE]))
    saving_value = saving.get('min_both_ranks_us_per_layer')
    saving_ok = saving_value is not None and saving_value >= SAVING_MIN_US
    fired = []
    if not exact: fired.append('inexact_view')
    if not proposals: fired.append('draft_proposals_differ')
    if not acceptance: fired.append('acceptance_differs')
    if not drift_ok: fired.append('k3x_drift_percent')
    if not saving_ok: fired.append('gateup_saving_us_per_layer' if saving_value is not None else 'gateup_saving_unmeasured')
    clean = exact and proposals and acceptance and drift_ok and saving_ok
    winner = bool(clean and gain >= SCREEN_BAR)
    chain = bool(clean and gain >= CHAIN_BAR and min(cand) >= RECORD_BAR)
    if chain:
        outcome = 'EXP-DIET CHAIN RULE MET: derive the record bundle from packet190 with the k3x-diet selection and the packet194 engine (README) and run a fresh chain on cards 0+1'
    elif winner:
        outcome = 'EXP-DIET SCREEN WINNER below the chain bar: no record chain; record the measured gain and the per-layer saving'
    else:
        outcome = 'EXP-DIET NOT A SCREEN WINNER: close at the measured numbers (DO-NOT-REPEAT) with the kill-rule readings'
    return dict(schema='packet194.s194-decision.v1', screen_winner=winner, chain_rule_met=chain, outcome=outcome, rule=RULE,
                thresholds=dict(screen_bar=SCREEN_BAR, chain_bar=CHAIN_BAR, record=RECORD, record_bar=RECORD_BAR, drift_max_percent=DRIFT_MAX_PCT, saving_min_us_per_layer=SAVING_MIN_US),
                every_view_exact=exact, draft_proposals_identical=proposals, acceptance_identical=acceptance,
                k3x_rates=control, diet_rates=cand, k3x_drift_percent=drift, min_gain_vs_every_k3x_view_percent=100 * gain,
                slower_diet_rate=min(cand), faster_k3x_rate=max(control), kill_rules=dict(thresholds=KILL, fired=fired), gateup_saving=saving)


def decide_or_incomplete(*rows):
    try:
        for row in rows:
            if isinstance(row, Exception):
                raise row
        return decide(*rows)
    except (Incomplete, KeyError, ValueError, TypeError, OSError) as error:
        return dict(schema='packet194.s194-decision.v1', screen_winner=False, chain_rule_met=False, outcome='INCOMPLETE: no decision',
                    reason=str(error), rule=RULE)


def view_record(summary):
    """Decision input of a single-view row (its bracket-summary.json)."""
    view = summary['views'][0]
    return dict(kind='view', index=summary['row_index'], variant=view.get('variant', CONTROL), rate=view['rate'], all_13_exact=view['all_13_exact'],
                exact_count=view['exact_count'], draft_proposals=view['draft_proposals'], acceptance_counts=view['acceptance_counts'],
                interval_stats=view.get('interval_stats') or summary.get('interval_stats'))


def bracket_record(summary):
    """Decision input of the k3x/k3x-diet bracket row (its bracket-summary.json)."""
    return dict(kind='bracket', views=[dict(variant=v['variant'], rate=v['rate'], all_13_exact=v['all_13_exact'], exact_count=v['exact_count'],
                                            draft_proposals=v['draft_proposals'], acceptance_counts=v['acceptance_counts'],
                                            interval_stats=v.get('interval_stats')) for v in summary['views']])


def smoke_record(summary):
    return dict(kind='smoke', passed=summary.get('passed') is True, exact=summary.get('passed') is True and summary.get('kind') == 'smoke'
                and summary.get('timing_data_proof', {}).get('passed') is True)


if __name__ == '__main__':
    import argparse, resource
    resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3))
    ap = argparse.ArgumentParser(description='Recompute s194_decision from the two retained row outputs (rows 0..1).')
    ap.add_argument('outputs', nargs=2, type=Path)
    ap.add_argument('--write', type=Path)
    a = ap.parse_args()
    from p194_v5_compare import load
    s, b = (load(p) for p in a.outputs)
    result = decide_or_incomplete(smoke_record(s), bracket_record(b))
    print(json.dumps(result, indent=2))
    if a.write:
        a.write.write_text(json.dumps(result, indent=2) + '\n')
