"""Packet186 decision (`s186_decision`): is V3 a screen winner, and does it clear the chain rule?

Rows (same lane, each depending on the previous): 0 V3 smoke (12 x 64, exact), 1 fresh-load bundle-8
control (split head), 2 one-load bracket U/V3/U/V3/U of the V3 dual layout, 3 fresh-load bundle-8 control.
Rates are the class-balanced median of per-prompt 99-interval rates (packet185/packet136 metric).

  screen winner  every view 13/13 exact (smoke 12/12 x 64 + incident) with identical draft proposals and
                 per-prompt acceptance across all seven 128-token views, split-control drift <= 3 % and U drift
                 <= 3 %, AND the slower V3 view >= 1.005 x every control view (both split-head controls and
                 all three in-load U views);
  chain rule     the same exactness/drift conditions AND the slower V3 view >= 1.02 x the faster split-head
                 control AND >= 1.02 x 58.798109 (= 59.974 tok/s, the two-card record bar).
Neither is ever a record claim: a record needs a fresh-process chain (bundle 8 + V3, see README).

Reported (never a condition): per-variant interval means (packet85 model; V3 rows add the boundary command
to the ready side: ready = max(D, R + C + boundary)), the measured rank-1 saving per moved layer
s1 = (B_u - B_v3)/2, the rank-0 boundary cost, and which side binds the emission.
"""
import json, math, statistics as st
from pathlib import Path

RECORD = 58.798108759182306
SCREEN_BAR = 0.005
CHAIN_BAR = 0.02
DRIFT_MAX_PCT = 3.0
ORDER = ('u', 'v3', 'u', 'v3', 'u')
HEAD_SCOPES = ('head_service_total', 'head_hidden_wait', 'suffix_head', 'head_import', 'head_export')
RULE = ('screen winner: min V3 >= 1.005 x every control view (2 split-head + 3 U) with every view exact, identical '
        'proposals/acceptance and drift <= 3% (split controls and U views); chain: also min V3 >= 1.02 x max split control '
        'AND >= 1.02 x 58.798109 = 59.974 tok/s')


class Incomplete(ValueError):
    pass


def demand(ok, reason):
    if not ok:
        raise Incomplete(reason)


def mean(values):
    values = list(values)
    return st.mean(values) if values else None


def intervals_v3(r, limit=99):
    """Vendored packet85 intervals plus the V3 boundary command (rank 0, op 15) on the ready side."""
    from interval_model import intervals, duration
    rows = intervals(r, limit)
    boundaries = {t['position']: t for t in r['rank_trace'] if t['rank'] == 0 and t['op'] == 15}
    for x in rows:
        b = boundaries.get(x['position'])
        x['Bd'] = duration(b) if b else 0.0
        ready = max(x['D'], x['R'] + x['C'] + x['Bd'])
        race = max(x['B'], x['A'] + x['spec_start_offset_ms'])
        x['ready_v3_ms'] = ready
        x['boundary_binds_ready'] = x['R'] + x['C'] + x['Bd'] > x['D']
        x['prediction_without_gaps_ms'] = ready + race
        x['unresolved_control_gaps_ms'] = x['elapsed_ms'] - ready - race
    return rows


def view_stats(view_dir, prompt_ids, variant):
    """Interval statistics of one view directory (12 prompts, first 99 intervals each)."""
    view_dir = Path(view_dir)
    rows, cycles, head_counts = [], 0, {n: 0 for n in HEAD_SCOPES}
    boundaries = 0
    for prompt in prompt_ids:
        receipt = view_dir / prompt / 'receipt.json'
        demand(receipt.is_file(), 'missing request receipt: ' + str(receipt))
        r = json.loads(receipt.read_text())
        demand(r.get('passed') is True and r.get('exact_oracle') is True and r.get('cached_tokens') == 0, 'request not exact/cold: ' + prompt)
        demand('rank_trace' in r and 'guess_rows' in r and 'generated_token_completion_timestamps' in r, 'missing native correction stream: ' + prompt)
        part = intervals_v3(r)
        demand(len(part) == 99, 'expected 99 intervals per 128-token prompt: ' + prompt)
        n = sum(1 for t in r['rank_trace'] if t['rank'] == 0 and t['op'] == 15)
        demand((n > 0) == (variant == 'v3'), 'boundary commands present iff the view is V3: ' + prompt)
        boundaries += n
        rows += part
        stamps = r['token_timestamps'][:100]
        cycles += len(stamps) - 1
        path = view_dir / prompt / 'rank0/timings.jsonl'
        demand(path.is_file(), 'missing rank0 timing stream: ' + str(path))
        for line in path.read_text().splitlines():
            x = json.loads(line) if line.strip() else {}
            if x.get('p150_segment') in head_counts and stamps[0] <= x['start'] <= x['end'] <= stamps[-1]:
                head_counts[x['p150_segment']] += 1
    if variant == 'production':
        demand(all(head_counts[n] >= cycles * 0.9 for n in HEAD_SCOPES), 'split-head view must record the rank-0 suffix service every cycle')
    else:
        demand(all(head_counts[n] == 0 for n in HEAD_SCOPES), 'un-split view must not run a rank-0 suffix service')
    hits = [x for x in rows if x['hit']]
    misses = [x for x in rows if not x['hit']]
    demand(len(hits) >= 600 and len(misses) >= 100, 'too few hit/miss intervals')
    return dict(
        variant=variant, intervals=len(rows), hits=len(hits), misses=len(misses), cycles=cycles, boundary_commands=boundaries,
        hit=dict(D=mean(x['D'] for x in hits), A=mean(x['A'] for x in hits), B=mean(x['B'] for x in hits), Bd=mean(x['Bd'] for x in hits),
                 ready=mean(x['ready_v3_ms'] for x in hits), boundary_binds_ready=mean(float(x['boundary_binds_ready']) for x in hits),
                 rank1_binds_emission=mean(float(x['B'] >= x['A'] + x['spec_start_offset_ms']) for x in hits),
                 G=mean(x['unresolved_control_gaps_ms'] for x in hits), elapsed=mean(x['elapsed_ms'] for x in hits)),
        miss=dict(D=mean(x['D'] for x in misses), R=mean(x['R'] for x in misses), C=mean(x['C'] for x in misses), Bd=mean(x['Bd'] for x in misses),
                  A=mean(x['A'] for x in misses), B=mean(x['B'] for x in misses), G=mean(x['unresolved_control_gaps_ms'] for x in misses),
                  elapsed=mean(x['elapsed_ms'] for x in misses)),
        pooled_interval_ms=mean(x['elapsed_ms'] for x in rows),
        definition='packet85 intervals (vendored) + V3 boundary on the ready side; hit = guess verified at the starting emission')


def measured(split_stats, u_stats, v3_stats):
    """Reported arithmetic (never a decision condition); any input may be missing."""
    def m(stats, side, key):
        values = [s[side][key] for s in stats if s and s[side].get(key) is not None]
        return mean(values) if values else None
    out = {}
    bu, bv = m(u_stats, 'hit', 'B'), m(v3_stats, 'hit', 'B')
    if bu is not None and bv is not None:
        out['s1_rank1_saving_per_moved_layer_ms'] = (bu - bv) / 2
    bd = m(v3_stats, 'hit', 'Bd')
    if bd is not None:
        out['boundary_command_ms'] = bd
    for name, stats in (('split', split_stats), ('u', u_stats), ('v3', v3_stats)):
        for side in ('hit', 'miss'):
            for key in ('D', 'A', 'B', 'Bd', 'elapsed'):
                value = m(stats, side, key)
                if value is not None:
                    out[f'{name}_{side}_{key}_ms'] = value
    rb = m(v3_stats, 'hit', 'rank1_binds_emission')
    if rb is not None:
        out['v3_hits_where_rank1_binds_fraction'] = rb
    return out


def decide(smoke, control0, bracket, control1):
    """smoke/control rows: dict(kind, rate?, all_13_exact, exact_count, draft_proposals?, acceptance_counts?, interval_stats?);
    bracket: dict(kind='bracket', views=[five view records with variant u/v3/u/v3/u])."""
    demand(smoke.get('kind') == 'smoke' and smoke.get('passed') is True and smoke.get('exact') is True, 'V3 smoke must pass exact first')
    demand(control0.get('kind') == 'view' and control1.get('kind') == 'view', 'two fresh-load control view rows required')
    demand(bracket.get('kind') == 'bracket' and [v['variant'] for v in bracket['views']] == list(ORDER), 'bracket must be U/V3/U/V3/U')
    views = [control0, *bracket['views'], control1]
    for v in views:
        demand(isinstance(v.get('rate'), (int, float)) and math.isfinite(v['rate']) and v['rate'] > 0, 'invalid view rate')
    exact = all(v.get('all_13_exact') is True and v.get('exact_count') == 13 for v in views)
    proposals = all(v['draft_proposals'] == views[0]['draft_proposals'] for v in views)
    acceptance = all(v['acceptance_counts'] == views[0]['acceptance_counts'] for v in views)
    split = [control0['rate'], control1['rate']]
    u = [v['rate'] for v in bracket['views'] if v['variant'] == 'u']
    v3 = [v['rate'] for v in bracket['views'] if v['variant'] == 'v3']
    split_drift = 100 * (max(split) / min(split) - 1)
    u_drift = 100 * (max(u) / min(u) - 1)
    drift_ok = split_drift <= DRIFT_MAX_PCT and u_drift <= DRIFT_MAX_PCT
    controls = split + u
    gain_all = min(v3) / max(controls) - 1
    gain_split = min(v3) / max(split) - 1
    gain_u = min(v3) / max(u) - 1
    clean = exact and proposals and acceptance and drift_ok
    winner = bool(clean and gain_all >= SCREEN_BAR)
    chain = bool(clean and gain_split >= CHAIN_BAR and min(v3) >= (1 + CHAIN_BAR) * RECORD)
    stats = lambda rows: [r.get('interval_stats') for r in rows if isinstance(r.get('interval_stats'), dict) and 'hit' in r.get('interval_stats', {})]
    report = measured(stats([control0, control1]), stats([v for v in bracket['views'] if v['variant'] == 'u']),
                      stats([v for v in bracket['views'] if v['variant'] == 'v3']))
    if chain:
        outcome = 'V3 CHAIN RULE MET: prepare the record bundle (bundle 8 + V3 + static snapshot), fresh chain on cards 0+1'
    elif winner:
        outcome = 'V3 SCREEN WINNER below the chain bar: no record chain; record the measured gain'
    else:
        outcome = 'V3 NOT A SCREEN WINNER: close V3 at the measured numbers (DO-NOT-REPEAT)'
    return dict(schema='packet186.s186-decision.v1', screen_winner=winner, chain_rule_met=chain, outcome=outcome, rule=RULE,
                thresholds=dict(screen_bar=SCREEN_BAR, chain_bar=CHAIN_BAR, record=RECORD, record_bar=(1 + CHAIN_BAR) * RECORD, drift_max_percent=DRIFT_MAX_PCT),
                every_view_exact=exact, draft_proposals_identical=proposals, acceptance_identical=acceptance,
                split_control_rates=split, u_rates=u, v3_rates=v3, split_drift_percent=split_drift, u_drift_percent=u_drift,
                min_gain_vs_every_control_percent=100 * gain_all, min_gain_vs_split_controls_percent=100 * gain_split,
                min_gain_vs_u_percent=100 * gain_u, slower_v3_rate=min(v3), faster_split_control_rate=max(split), measured=report)


def decide_or_incomplete(*rows):
    try:
        for row in rows:
            if isinstance(row, Exception):
                raise row
        return decide(*rows)
    except (Incomplete, KeyError, ValueError, TypeError, OSError) as error:
        return dict(schema='packet186.s186-decision.v1', screen_winner=False, chain_rule_met=False, outcome='INCOMPLETE: no decision',
                    reason=str(error), rule=RULE)


def view_record(summary):
    """Decision input of a fresh-load control view row (its bracket-summary.json)."""
    view = summary['views'][0]
    return dict(kind='view', index=summary['row_index'], variant='production', rate=view['rate'], all_13_exact=view['all_13_exact'],
                exact_count=view['exact_count'], draft_proposals=view['draft_proposals'], acceptance_counts=view['acceptance_counts'],
                interval_stats=summary.get('interval_stats'))


def bracket_record(summary):
    """Decision input of the U/V3 bracket row (its bracket-summary.json)."""
    return dict(kind='bracket', views=[dict(variant=v['variant'], rate=v['rate'], all_13_exact=v['all_13_exact'], exact_count=v['exact_count'],
                                            draft_proposals=v['draft_proposals'], acceptance_counts=v['acceptance_counts'],
                                            interval_stats=v.get('interval_stats')) for v in summary['views']])


def smoke_record(summary):
    return dict(kind='smoke', passed=summary.get('passed') is True, exact=summary.get('passed') is True and summary.get('kind') == 'smoke'
                and summary.get('timing_data_proof', {}).get('passed') is True)


if __name__ == '__main__':
    import argparse, resource
    resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3))
    ap = argparse.ArgumentParser(description='Recompute s186_decision from the four retained row outputs (rows 0..3).')
    ap.add_argument('outputs', nargs=4, type=Path)
    ap.add_argument('--write', type=Path)
    a = ap.parse_args()
    from p186_v5_compare import load
    s, c0, b, c1 = (load(p) for p in a.outputs)
    result = decide_or_incomplete(smoke_record(s), view_record(c0), bracket_record(b), view_record(c1))
    print(json.dumps(result, indent=2))
    if a.write:
        a.write.write_text(json.dumps(result, indent=2) + '\n')
