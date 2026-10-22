"""Packet189 decision (`s189_decision`): is k3x a screen winner over the V3 record line, and does it clear the chain rule?

Rows (same lane, each depending on the previous): 0 k3x smoke (12 x 64 + incident64, exact, first-request data proof),
1 one-load bracket V3/k3x/V3/k3x/V3 of the k3 storage (rank0_layers 0-26; the V3 views run boundary=rank0 with layer 26
idle on rank 0). There is no fresh V3 row: packet188 row 1 (the packet187 record selection loaded fresh on this lane,
60.50488520482965 tok/s, 2026-10-22) is the fresh reference, read where packet188 retained it and pinned by sha256
(FRESH_V3). Rates are the class-balanced median of per-prompt 99-interval rates (the record metric).

  screen winner  every view 13/13 exact (smoke 12/12 x 64 + incident) with identical draft proposals and per-prompt
                 acceptance across the five 128-token views, V3-view drift <= 3 % over the three in-load V3 views PLUS
                 packet188's fresh V3 row, AND the slower k3x view >= 1.005 x EVERY V3 view (the three in-load views and
                 the fresh 60.50488520482965);
  chain rule     the same conditions AND the slower k3x view >= 1.02 x every V3 view AND >= 1.02 x 60.659520
                 (= 61.87271031814733 tok/s, the two-card record bar).
D is the draft's observed wall time (`draft_rows.draft_wall_ms`, publication observed), never the op-9 command
duration: under rank0_prepare=async the rank-1 controller stamps op 9 complete after its nonblocking host issue
(0.43 ms in packet188) while the draft really completes 1.5 ms later (lever synthesis 3, section 1.2).
Kill rules (recorded, never a speed claim; they say why to stop investing if the rule fails):
  export          mean `handoff_export` scope on the k3x views > 0.10 ms (the export is not on the copy path; priced 0.053);
  boundary        mean `boundary_total` scope on the k3x views > 1.60 ms (layer 26 costs more than 0.57 ms; priced 1.466);
  k3 hit saving   mean hit interval (in-load V3 views) - mean hit interval (k3x views) < 0.35 ms (priced 0.51-0.54);
  draft window    the boundary exceeds the observed draft wall (Bd > draft_wall) on > 10 % of k3x hits (priced 0 %);
  trims           rank 0's speculative half A (in-load V3) - A (k3x), mean over hits < 0.105 ms (A carries only the
                  trims: layers 0-23 are identical in both views; packet188 measured 0.142).
Reported (never a condition): per-variant interval means (packet85 model with the boundary on the ready side and D from
the draft wall), the rank-0 envelope attribution from the existing host scopes (half_total - layer_body = snapshot +
token_history + token_prep + retirement + unattributed; boundary_total - boundary_body = export + rest), which side binds
the emission, and the miss interval. Neither outcome is a record claim: a record needs a fresh-process chain (packet187
harness + the k3x selection, README).
"""
import hashlib, json, math, statistics as st
from pathlib import Path

RECORD = 60.65951991975228
SCREEN_BAR = 0.005
CHAIN_BAR = 0.02
RECORD_BAR = 61.87271031814733
DRIFT_MAX_PCT = 3.0
CANDIDATE = 'k3x'
ORDER = ('v3k', CANDIDATE, 'v3k', CANDIDATE, 'v3k')
KILL = dict(handoff_export_ms=0.10, boundary_total_ms=1.60, k3_hit_saving_ms=0.35, boundary_over_draft_wall_fraction=0.10, trims_A_saving_ms=0.105)
RULE = ('screen winner: min k3x >= 1.005 x every V3 view (3 in-load V3 views + packet188 fresh V3 row 1 = 60.50488520482965, hash-pinned) with '
        'every view exact, identical proposals/acceptance and V3 drift <= 3%; chain: also min k3x >= 1.02 x every V3 view AND >= 1.02 x '
        '60.659520 = 61.87271031814733 tok/s; D := draft_rows.draft_wall_ms (publication observed), never op 9; kill rules recorded: '
        'handoff_export > 0.10 ms, boundary_total > 1.60 ms, k3 hit saving < 0.35 ms, Bd > draft wall on > 10% of k3x hits, trims remove < 0.105 ms of A')
ENVELOPE = ('half_total', 'layer_body', 'snapshot', 'token_history', 'token_prep', 'boundary_total', 'boundary_body', 'handoff_export')
STAGE = Path(__file__).resolve().parents[2]
# packet188 row 1: the packet187 record selection (0-25 storage) loaded fresh on lane B (lanequeue-B35, 2026-10-22), 13/13 exact.
FRESH_V3 = dict(packet='packet188-twocard-k3-composite', row='device-row1-control-v3-B-p188',
                summary='experiments/own-xpu-runtime/stage2/packet188-twocard-k3-composite/v5/evidence/device-row1-control-v3-B-p188/bracket-summary.json',
                sha256='4ff1ec14a842c5ec652c9cdc0527658929a84edd2baaefecb9de753f12db0aae', rate=60.50488520482965)


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
        demand('rank_trace' in r and 'guess_rows' in r and 'generated_token_completion_timestamps' in r and 'draft_rows' in r, 'missing native correction/draft stream: ' + prompt)
        part = intervals_v3(r)
        demand(len(part) == 99, 'expected 99 intervals per 128-token prompt: ' + prompt)
        n = sum(1 for t in r['rank_trace'] if t['rank'] == 0 and t['op'] == 15)
        demand(n > 0, 'every packet189 view runs the boundary: ' + prompt)
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
                 boundary_minus_draft=mean(x['Bd'] - x['D'] for x in hits),
                 rank1_binds_emission=mean(float(x['B'] >= x['A'] + x['spec_start_offset_ms']) for x in hits),
                 G=mean(x['unresolved_control_gaps_ms'] for x in hits), elapsed=mean(x['elapsed_ms'] for x in hits)),
        miss=dict(D=mean(x['D'] for x in misses), D_op9=mean(x['D_op9'] for x in misses), R=mean(x['R'] for x in misses), C=mean(x['C'] for x in misses), Bd=mean(x['Bd'] for x in misses),
                  A=mean(x['A'] for x in misses), B=mean(x['B'] for x in misses), G=mean(x['unresolved_control_gaps_ms'] for x in misses),
                  elapsed=mean(x['elapsed_ms'] for x in misses)),
        pooled_interval_ms=mean(x['elapsed_ms'] for x in rows), envelope=envelope(view_dir, prompt_ids),
        definition='packet85 intervals (vendored) + boundary on the ready side; D = draft_rows.draft_wall_ms (publication observed), D_op9 = op-9 command duration (reported only); hit = guess verified at the starting emission')


def kill_rules(v3_stats, k3_stats):
    """Recorded kill rules from the in-load V3 and k3x interval statistics (None when unmeasured)."""
    def m(stats, side, key):
        values = [s[side][key] for s in stats if s and s.get(side) and s[side].get(key) is not None]
        return mean(values) if values else None
    env = lambda stats, key: mean(s['envelope'][key] for s in stats if s and s.get('envelope', {}).get(key) is not None)
    scope = lambda stats, key: mean(s['envelope']['scopes_ms'][key] for s in stats if s and s.get('envelope', {}).get('scopes_ms', {}).get(key) is not None)
    hv, hk = m(v3_stats, 'hit', 'elapsed'), m(k3_stats, 'hit', 'elapsed')
    av, ak = m(v3_stats, 'hit', 'A'), m(k3_stats, 'hit', 'A')
    out = dict(thresholds=KILL, draft_definition='D = draft_rows.draft_wall_ms (publication observed), never the op-9 command duration')
    out['handoff_export_ms'] = scope(k3_stats, 'handoff_export')
    out['boundary_total_ms'] = scope(k3_stats, 'boundary_total')
    out['k3_hit_saving_ms'] = None if hv is None or hk is None else hv - hk
    out['boundary_over_draft_wall_fraction'] = m(k3_stats, 'hit', 'boundary_over_draft')
    out['trims_A_saving_ms'] = None if av is None or ak is None else av - ak
    out['fired'] = sorted(k for k, cmp in (('handoff_export_ms', lambda v: v > KILL['handoff_export_ms']),
                                          ('boundary_total_ms', lambda v: v > KILL['boundary_total_ms']),
                                          ('k3_hit_saving_ms', lambda v: v < KILL['k3_hit_saving_ms']),
                                          ('boundary_over_draft_wall_fraction', lambda v: v > KILL['boundary_over_draft_wall_fraction']),
                                          ('trims_A_saving_ms', lambda v: v < KILL['trims_A_saving_ms']))
                          if out[k] is not None and cmp(out[k]))
    for side in ('hit', 'miss'):
        for key in ('D', 'D_op9', 'A', 'B', 'Bd', 'elapsed'):
            for name, stats in (('v3', v3_stats), (CANDIDATE, k3_stats)):
                value = m(stats, side, key)
                if value is not None:
                    out[f'{name}_{side}_{key}_ms'] = value
    for key in ('rank1_binds_emission', 'boundary_minus_draft'):
        for name, stats in (('v3', v3_stats), (CANDIDATE, k3_stats)):
            value = m(stats, 'hit', key)
            if value is not None:
                out[f'{name}_hit_{key}'] = value
    for key in ('rank0_half_envelope_ms', 'envelope_unattributed_ms', 'boundary_envelope_ms', 'boundary_export_ms', 'p76_retirement_ms_per_half', 'prepare_ms_per_half'):
        a, b = env(v3_stats, key), env(k3_stats, key)
        if a is not None and b is not None:
            out[f'envelope_{key}'] = dict(v3=a, **{CANDIDATE: b}, removed=a - b)
    for key in ('boundary_body', 'boundary_total', 'handoff_export'):
        a, b = scope(v3_stats, key), scope(k3_stats, key)
        if a is not None and b is not None:
            out[f'scope_{key}_ms'] = dict(v3=a, **{CANDIDATE: b}, delta=b - a)
    return out


def fresh_v3_record(summary_path=None, pin=FRESH_V3):
    """Decision input of the fresh V3 reference (packet188 row 1), read in place and verified against its sha256 pin."""
    path = Path(summary_path) if summary_path else STAGE.parents[2] / pin['summary']
    demand(path.is_file(), 'fresh V3 reference summary missing: ' + str(path))
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    demand(digest == pin['sha256'], 'fresh V3 reference changed where packet188 retained it: ' + digest)
    summary = json.loads(data)
    demand(summary.get('kind') == 'view' and summary.get('passed') is True and summary.get('row_index') == 1, 'fresh V3 reference is not packet188 row 1')
    record = view_record(summary)
    demand(record['variant'] == 'v3' and record['rate'] == pin['rate'], 'fresh V3 reference rate differs from its pin')
    record.update(source=str(path.relative_to(STAGE.parents[2])), sha256=digest, read_in_place=True)
    return record


def decide(smoke, bracket, fresh=None):
    """smoke: dict(kind='smoke', passed, exact); bracket: dict(kind='bracket', views=[5 records]); fresh: the packet188 row-1 record
    (default: read in place and pin-checked)."""
    demand(smoke.get('kind') == 'smoke' and smoke.get('passed') is True and smoke.get('exact') is True, 'k3x smoke must pass exact first')
    demand(bracket.get('kind') == 'bracket' and [v['variant'] for v in bracket['views']] == list(ORDER), 'bracket must be V3/k3x/V3/k3x/V3')
    fresh = fresh if fresh is not None else fresh_v3_record()
    demand(fresh.get('kind') == 'view' and fresh.get('variant') == 'v3' and fresh.get('all_13_exact') is True and fresh.get('exact_count') == 13, 'fresh V3 reference must be an exact packet187-selection view')
    views = list(bracket['views'])
    for v in views + [fresh]:
        demand(isinstance(v.get('rate'), (int, float)) and math.isfinite(v['rate']) and v['rate'] > 0, 'invalid view rate')
    exact = all(v.get('all_13_exact') is True and v.get('exact_count') == 13 for v in views)
    proposals = all(v['draft_proposals'] == views[0]['draft_proposals'] for v in views)
    acceptance = all(v['acceptance_counts'] == views[0]['acceptance_counts'] for v in views)
    fresh_proposals = fresh['draft_proposals'] == views[0]['draft_proposals'] and fresh['acceptance_counts'] == views[0]['acceptance_counts']
    inload = [v['rate'] for v in views if v['variant'] == 'v3k']
    v3 = [fresh['rate'], *inload]
    k3 = [v['rate'] for v in views if v['variant'] == CANDIDATE]
    drift = 100 * (max(v3) / min(v3) - 1)
    fresh_vs_inload = 100 * (fresh['rate'] / st.median(inload) - 1)
    drift_ok = drift <= DRIFT_MAX_PCT
    gain = min(k3) / max(v3) - 1
    clean = exact and proposals and acceptance and drift_ok
    winner = bool(clean and gain >= SCREEN_BAR)
    chain = bool(clean and gain >= CHAIN_BAR and min(k3) >= RECORD_BAR)
    stats = lambda rows: [r.get('interval_stats') for r in rows if isinstance(r.get('interval_stats'), dict) and 'hit' in r.get('interval_stats', {})]
    kills = kill_rules(stats([v for v in views if v['variant'] == 'v3k']), stats([v for v in views if v['variant'] == CANDIDATE]))
    if chain:
        outcome = 'K3X CHAIN RULE MET: derive the record bundle from packet187 with the k3x selection (README) and run a fresh chain on cards 0+1'
    elif winner:
        outcome = 'K3X SCREEN WINNER below the chain bar: no record chain; record the measured gain and the kill-rule readings'
    else:
        outcome = 'K3X NOT A SCREEN WINNER: close at the measured numbers (DO-NOT-REPEAT) with the kill-rule readings'
    return dict(schema='packet189.s189-decision.v1', screen_winner=winner, chain_rule_met=chain, outcome=outcome, rule=RULE,
                thresholds=dict(screen_bar=SCREEN_BAR, chain_bar=CHAIN_BAR, record=RECORD, record_bar=RECORD_BAR, drift_max_percent=DRIFT_MAX_PCT),
                every_view_exact=exact, draft_proposals_identical=proposals, acceptance_identical=acceptance,
                fresh_reference_proposals_and_acceptance_identical=fresh_proposals,
                v3_rates=v3, fresh_v3_rate=fresh['rate'], fresh_v3_source=dict(source=fresh.get('source'), sha256=fresh.get('sha256'), read_in_place=fresh.get('read_in_place')),
                inload_v3_rates=inload, k3x_rates=k3, v3_drift_percent=drift,
                fresh_vs_inload_v3_percent=fresh_vs_inload, min_gain_vs_every_v3_view_percent=100 * gain,
                slower_k3x_rate=min(k3), faster_v3_rate=max(v3), kill_rules=kills,
                fresh_v3_interval_stats=fresh.get('interval_stats'))


def decide_or_incomplete(*rows, fresh=None):
    try:
        for row in rows:
            if isinstance(row, Exception):
                raise row
        return decide(*rows, fresh=fresh)
    except (Incomplete, KeyError, ValueError, TypeError, OSError) as error:
        return dict(schema='packet189.s189-decision.v1', screen_winner=False, chain_rule_met=False, outcome='INCOMPLETE: no decision',
                    reason=str(error), rule=RULE)


def view_record(summary):
    """Decision input of a fresh single-view row (its bracket-summary.json)."""
    view = summary['views'][0]
    return dict(kind='view', index=summary['row_index'], variant=view.get('variant', 'v3'), rate=view['rate'], all_13_exact=view['all_13_exact'],
                exact_count=view['exact_count'], draft_proposals=view['draft_proposals'], acceptance_counts=view['acceptance_counts'],
                interval_stats=view.get('interval_stats') or summary.get('interval_stats'))


def bracket_record(summary):
    """Decision input of the V3/k3x bracket row (its bracket-summary.json)."""
    return dict(kind='bracket', views=[dict(variant=v['variant'], rate=v['rate'], all_13_exact=v['all_13_exact'], exact_count=v['exact_count'],
                                            draft_proposals=v['draft_proposals'], acceptance_counts=v['acceptance_counts'],
                                            interval_stats=v.get('interval_stats')) for v in summary['views']])


def smoke_record(summary):
    return dict(kind='smoke', passed=summary.get('passed') is True, exact=summary.get('passed') is True and summary.get('kind') == 'smoke'
                and summary.get('timing_data_proof', {}).get('passed') is True)


if __name__ == '__main__':
    import argparse, resource
    resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3))
    ap = argparse.ArgumentParser(description='Recompute s189_decision from the two retained row outputs (rows 0..1) and the pinned packet188 fresh V3 row.')
    ap.add_argument('outputs', nargs=2, type=Path)
    ap.add_argument('--write', type=Path)
    a = ap.parse_args()
    from p189_v5_compare import load
    s, b = (load(p) for p in a.outputs)
    result = decide_or_incomplete(smoke_record(s), bracket_record(b))
    print(json.dumps(result, indent=2))
    if a.write:
        a.write.write_text(json.dumps(result, indent=2) + '\n')
