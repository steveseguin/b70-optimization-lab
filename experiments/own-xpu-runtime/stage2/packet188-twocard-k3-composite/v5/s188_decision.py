"""Packet188 decision (`s188_decision`): is k3+trims a screen winner over the V3 record line, and does it clear the chain rule?

Rows (same lane, each depending on the previous): 0 k3+trims smoke (12 x 64 + incident64, exact, first-request data proof),
1 fresh-load V3 control (packet187's record selection, 0-25 storage, 12 x 128 + incident64), 2 one-load bracket
V3/k3+trims/V3/k3+trims/V3 of the k3 storage (rank0_layers 0-26; the V3 views run boundary=rank0 with layer 26 idle on
rank 0). Rates are the class-balanced median of per-prompt 99-interval rates (the record metric).

  screen winner  every view 13/13 exact (smoke 12/12 x 64 + incident) with identical draft proposals and per-prompt
                 acceptance across all six 128-token views, V3-view drift <= 3 % (the fresh V3 load and the three in-load
                 V3 views), AND the slower k3+trims view >= 1.005 x EVERY V3 view;
  chain rule     the same conditions AND the slower k3+trims view >= 1.02 x every V3 view AND >= 1.02 x 60.659520
                 (= 61.873 tok/s, the two-card record bar).
Kill rules (recorded, never a speed claim; they say why to stop investing if the rule fails):
  k3 hit saving   mean hit interval (in-load V3 views) - mean hit interval (k3+trims views) < 0.25 ms;
  draft window    the boundary command exceeds the draft (Bd > D) on > 5 % of k3+trims hits;
  trims           rank 0's speculative half A (in-load V3) - A (k3+trims), mean over hits < 0.105 ms (A carries only the
                  trims: layers 0-23 are identical in both views).
Reported (never a condition): per-variant interval means (packet85 model with the boundary on the ready side), the rank-0
envelope attribution from the existing host scopes (half_total - layer_body = snapshot + token_history + token_prep +
retirement + unattributed; boundary_total - boundary_body = export + rest), and which side binds the emission.
Neither outcome is a record claim: a record needs a fresh-process chain (packet187 harness + this composition, README).
"""
import json, math, statistics as st
from pathlib import Path

RECORD = 60.65951991975228
SCREEN_BAR = 0.005
CHAIN_BAR = 0.02
DRIFT_MAX_PCT = 3.0
ORDER = ('v3k', 'k3trims', 'v3k', 'k3trims', 'v3k')
KILL = dict(k3_hit_saving_ms=0.25, boundary_over_draft_fraction=0.05, trims_A_saving_ms=0.105)
RULE = ('screen winner: min k3+trims >= 1.005 x every V3 view (fresh V3 row + 3 in-load V3 views) with every view exact, '
        'identical proposals/acceptance and V3 drift <= 3%; chain: also min k3+trims >= 1.02 x every V3 view AND >= 1.02 x '
        '60.659520 = 61.873 tok/s; kill rules recorded: k3 hit saving < 0.25 ms, Bd > D on > 5% of k3 hits, trims remove < 0.105 ms of A')
ENVELOPE = ('half_total', 'layer_body', 'snapshot', 'token_history', 'token_prep', 'boundary_total', 'boundary_body', 'handoff_export')


class Incomplete(ValueError):
    pass


def demand(ok, reason):
    if not ok:
        raise Incomplete(reason)


def mean(values):
    values = list(values)
    return st.mean(values) if values else None


def intervals_v3(r, limit=99):
    """Vendored packet85 intervals plus the boundary command (rank 0, op 15) on the ready side."""
    from interval_model import intervals, duration
    rows = intervals(r, limit)
    boundaries = {t['position']: t for t in r['rank_trace'] if t['rank'] == 0 and t['op'] == 15}
    for x in rows:
        b = boundaries.get(x['position'])
        x['Bd'] = duration(b) if b else 0.0
        ready = max(x['D'], x['R'] + x['C'] + x['Bd'])
        race = max(x['B'], x['A'] + x['spec_start_offset_ms'])
        x['ready_v3_ms'] = ready
        x['boundary_over_draft'] = x['Bd'] > x['D']
        x['prediction_without_gaps_ms'] = ready + race
        x['unresolved_control_gaps_ms'] = x['elapsed_ms'] - ready - race
    return rows


def envelope(view_dir, prompt_ids, positions_from=0):
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
        out.update(rank0_half_envelope_ms=env, envelope_parts_ms=parts,
                   envelope_unattributed_ms=env - sum(parts.values()),
                   retirement_note='p76 retirement is host work inside layer_body (enqueue/retire), reported separately')
    bt, bb = per('boundary_total'), per('boundary_body')
    if bt is not None and bb is not None:
        out.update(boundary_envelope_ms=bt - bb, boundary_export_ms=per('handoff_export'))
    return out


def view_stats(view_dir, prompt_ids, variant, require_exact=True):
    """Interval statistics + rank-0 envelope of one view directory (12 prompts, first 99 intervals each).
    require_exact=False only for packet187's chain receipts, whose exactness the tests check against the oracle directly."""
    view_dir = Path(view_dir)
    rows, boundaries = [], 0
    for prompt in prompt_ids:
        receipt = view_dir / prompt / 'receipt.json'
        demand(receipt.is_file(), 'missing request receipt: ' + str(receipt))
        r = json.loads(receipt.read_text())
        demand(r.get('passed') is True and (r.get('exact_oracle') is True or not require_exact) and r.get('cached_tokens') == 0, 'request not exact/cold: ' + prompt)
        demand('rank_trace' in r and 'guess_rows' in r and 'generated_token_completion_timestamps' in r, 'missing native correction stream: ' + prompt)
        part = intervals_v3(r)
        demand(len(part) == 99, 'expected 99 intervals per 128-token prompt: ' + prompt)
        n = sum(1 for t in r['rank_trace'] if t['rank'] == 0 and t['op'] == 15)
        demand(n > 0, 'every packet188 view runs the boundary: ' + prompt)
        boundaries += n
        rows += part
    hits = [x for x in rows if x['hit']]
    misses = [x for x in rows if not x['hit']]
    demand(len(hits) >= 600 and len(misses) >= 100, 'too few hit/miss intervals')
    return dict(
        variant=variant, intervals=len(rows), hits=len(hits), misses=len(misses), boundary_commands=boundaries,
        hit=dict(D=mean(x['D'] for x in hits), A=mean(x['A'] for x in hits), B=mean(x['B'] for x in hits), Bd=mean(x['Bd'] for x in hits),
                 offset=mean(x['spec_start_offset_ms'] for x in hits), ready=mean(x['ready_v3_ms'] for x in hits),
                 boundary_over_draft=mean(float(x['boundary_over_draft']) for x in hits),
                 rank1_binds_emission=mean(float(x['B'] >= x['A'] + x['spec_start_offset_ms']) for x in hits),
                 G=mean(x['unresolved_control_gaps_ms'] for x in hits), elapsed=mean(x['elapsed_ms'] for x in hits)),
        miss=dict(D=mean(x['D'] for x in misses), R=mean(x['R'] for x in misses), C=mean(x['C'] for x in misses), Bd=mean(x['Bd'] for x in misses),
                  A=mean(x['A'] for x in misses), B=mean(x['B'] for x in misses), G=mean(x['unresolved_control_gaps_ms'] for x in misses),
                  elapsed=mean(x['elapsed_ms'] for x in misses)),
        pooled_interval_ms=mean(x['elapsed_ms'] for x in rows), envelope=envelope(view_dir, prompt_ids),
        definition='packet85 intervals (vendored) + boundary on the ready side; hit = guess verified at the starting emission')


def kill_rules(v3_stats, k3_stats):
    """Recorded kill rules from the in-load V3 and k3+trims interval statistics (None when unmeasured)."""
    def m(stats, side, key):
        values = [s[side][key] for s in stats if s and s.get(side) and s[side].get(key) is not None]
        return mean(values) if values else None
    hv, hk = m(v3_stats, 'hit', 'elapsed'), m(k3_stats, 'hit', 'elapsed')
    av, ak = m(v3_stats, 'hit', 'A'), m(k3_stats, 'hit', 'A')
    over = m(k3_stats, 'hit', 'boundary_over_draft')
    out = dict(thresholds=KILL)
    out['k3_hit_saving_ms'] = None if hv is None or hk is None else hv - hk
    out['boundary_over_draft_fraction'] = over
    out['trims_A_saving_ms'] = None if av is None or ak is None else av - ak
    out['fired'] = sorted(k for k, cmp in (('k3_hit_saving_ms', lambda v: v < KILL['k3_hit_saving_ms']),
                                          ('boundary_over_draft_fraction', lambda v: v > KILL['boundary_over_draft_fraction']),
                                          ('trims_A_saving_ms', lambda v: v < KILL['trims_A_saving_ms']))
                          if out[k] is not None and cmp(out[k]))
    for side in ('hit', 'miss'):
        for key in ('D', 'A', 'B', 'Bd', 'elapsed'):
            for name, stats in (('v3', v3_stats), ('k3trims', k3_stats)):
                value = m(stats, side, key)
                if value is not None:
                    out[f'{name}_{side}_{key}_ms'] = value
    env = lambda stats, key: mean(s['envelope'][key] for s in stats if s and s.get('envelope', {}).get(key) is not None)
    for key in ('rank0_half_envelope_ms', 'envelope_unattributed_ms', 'boundary_envelope_ms', 'boundary_export_ms', 'p76_retirement_ms_per_half', 'prepare_ms_per_half'):
        a, b = env(v3_stats, key), env(k3_stats, key)
        if a is not None and b is not None:
            out[f'envelope_{key}'] = dict(v3=a, k3trims=b, removed=a - b)
    return out


def decide(smoke, control, bracket):
    """smoke: dict(kind='smoke', passed, exact); control: fresh V3 view record; bracket: dict(kind='bracket', views=[5 records])."""
    demand(smoke.get('kind') == 'smoke' and smoke.get('passed') is True and smoke.get('exact') is True, 'k3+trims smoke must pass exact first')
    demand(control.get('kind') == 'view' and control.get('variant') == 'v3', 'one fresh-load V3 control view row required')
    demand(bracket.get('kind') == 'bracket' and [v['variant'] for v in bracket['views']] == list(ORDER), 'bracket must be V3/k3+trims/V3/k3+trims/V3')
    views = [control, *bracket['views']]
    for v in views:
        demand(isinstance(v.get('rate'), (int, float)) and math.isfinite(v['rate']) and v['rate'] > 0, 'invalid view rate')
    exact = all(v.get('all_13_exact') is True and v.get('exact_count') == 13 for v in views)
    proposals = all(v['draft_proposals'] == views[0]['draft_proposals'] for v in views)
    acceptance = all(v['acceptance_counts'] == views[0]['acceptance_counts'] for v in views)
    inload = [v['rate'] for v in bracket['views'] if v['variant'] == 'v3k']
    v3 = [control['rate'], *inload]
    k3 = [v['rate'] for v in bracket['views'] if v['variant'] == 'k3trims']
    drift = 100 * (max(v3) / min(v3) - 1)
    fresh_vs_inload = 100 * (control['rate'] / st.median(inload) - 1)
    drift_ok = drift <= DRIFT_MAX_PCT
    gain = min(k3) / max(v3) - 1
    clean = exact and proposals and acceptance and drift_ok
    winner = bool(clean and gain >= SCREEN_BAR)
    chain = bool(clean and gain >= CHAIN_BAR and min(k3) >= (1 + CHAIN_BAR) * RECORD)
    stats = lambda rows: [r.get('interval_stats') for r in rows if isinstance(r.get('interval_stats'), dict) and 'hit' in r.get('interval_stats', {})]
    kills = kill_rules(stats([v for v in bracket['views'] if v['variant'] == 'v3k']), stats([v for v in bracket['views'] if v['variant'] == 'k3trims']))
    fresh = stats([control])
    if chain:
        outcome = 'K3+TRIMS CHAIN RULE MET: derive the record bundle from packet187 (README) and run a fresh chain on cards 0+1'
    elif winner:
        outcome = 'K3+TRIMS SCREEN WINNER below the chain bar: no record chain; record the measured gain and the kill-rule readings'
    else:
        outcome = 'K3+TRIMS NOT A SCREEN WINNER: close at the measured numbers (DO-NOT-REPEAT) with the kill-rule readings'
    return dict(schema='packet188.s188-decision.v1', screen_winner=winner, chain_rule_met=chain, outcome=outcome, rule=RULE,
                thresholds=dict(screen_bar=SCREEN_BAR, chain_bar=CHAIN_BAR, record=RECORD, record_bar=(1 + CHAIN_BAR) * RECORD, drift_max_percent=DRIFT_MAX_PCT),
                every_view_exact=exact, draft_proposals_identical=proposals, acceptance_identical=acceptance,
                v3_rates=v3, fresh_v3_rate=control['rate'], inload_v3_rates=inload, k3trims_rates=k3, v3_drift_percent=drift,
                fresh_vs_inload_v3_percent=fresh_vs_inload, min_gain_vs_every_v3_view_percent=100 * gain,
                slower_k3trims_rate=min(k3), faster_v3_rate=max(v3), kill_rules=kills,
                fresh_v3_interval_stats=fresh[0] if fresh else None)


def decide_or_incomplete(*rows):
    try:
        for row in rows:
            if isinstance(row, Exception):
                raise row
        return decide(*rows)
    except (Incomplete, KeyError, ValueError, TypeError, OSError) as error:
        return dict(schema='packet188.s188-decision.v1', screen_winner=False, chain_rule_met=False, outcome='INCOMPLETE: no decision',
                    reason=str(error), rule=RULE)


def view_record(summary):
    """Decision input of the fresh-load V3 control row (its bracket-summary.json)."""
    view = summary['views'][0]
    return dict(kind='view', index=summary['row_index'], variant=view.get('variant', 'v3'), rate=view['rate'], all_13_exact=view['all_13_exact'],
                exact_count=view['exact_count'], draft_proposals=view['draft_proposals'], acceptance_counts=view['acceptance_counts'],
                interval_stats=view.get('interval_stats') or summary.get('interval_stats'))


def bracket_record(summary):
    """Decision input of the V3/k3+trims bracket row (its bracket-summary.json)."""
    return dict(kind='bracket', views=[dict(variant=v['variant'], rate=v['rate'], all_13_exact=v['all_13_exact'], exact_count=v['exact_count'],
                                            draft_proposals=v['draft_proposals'], acceptance_counts=v['acceptance_counts'],
                                            interval_stats=v.get('interval_stats')) for v in summary['views']])


def smoke_record(summary):
    return dict(kind='smoke', passed=summary.get('passed') is True, exact=summary.get('passed') is True and summary.get('kind') == 'smoke'
                and summary.get('timing_data_proof', {}).get('passed') is True)


if __name__ == '__main__':
    import argparse, resource
    resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3))
    ap = argparse.ArgumentParser(description='Recompute s188_decision from the three retained row outputs (rows 0..2).')
    ap.add_argument('outputs', nargs=3, type=Path)
    ap.add_argument('--write', type=Path)
    a = ap.parse_args()
    from p188_v5_compare import load
    s, c, b = (load(p) for p in a.outputs)
    result = decide_or_incomplete(smoke_record(s), view_record(c), bracket_record(b))
    print(json.dumps(result, indent=2))
    if a.write:
        a.write.write_text(json.dumps(result, indent=2) + '\n')
