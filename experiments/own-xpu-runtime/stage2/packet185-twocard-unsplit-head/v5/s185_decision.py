"""Packet185 decision (`s185_decision`): the measured attribution packet177(b) asks for, and V3's kill thresholds.

Five fresh-load views on the bundle-8 line, in this order: production (split head, bundle 8 as
recorded) / unsplit (full target head on rank 1, no merge) / production / unsplit / production.
Per view, the vendored packet85 interval model (`interval_model.intervals`, the same accounting
that reproduces the 58.798109 record from its receipts) splits the first 99 intervals of every
prompt into D (rank-1 draft), A (rank-0 speculative half), B (rank-1 half incl. head and merge),
R, C (miss restore/correction), offset and G. Rank-0 host scopes (packet150 `p150_segment`
records) give the suffix-head service on the split views.

V3 GO only if ALL hold (coordinator ruling 2026-10-22):
  u   = mean(unsplit hit-B) - mean(production hit-B)                <= 0.39 ms
        (un-split cost on rank 1; 0.39 ms is where lever-synthesis-20261022's V3 central falls to +2%)
  BA  = mean over the two unsplit views of mean hit (B - A)          >= 0.60 ms   (decoupled B - A)
  every view 13/13 exact, identical draft proposals and per-prompt acceptance across all five views
  control rate drift (max/min - 1 over the three production views)  <= 3 %
Otherwise V3 is CLOSED and packet177's placement row keeps its closure with this attribution appended.

Resolution (reported, not a GO condition): fresh loads drift; `u` is resolved only if
|u - 0.39| exceeds the spread of the three control hit-B means (and the D-corrected u, which
scales the control B by the rank-1 draft's own load-to-load ratio, agrees on the side).
"""
import json, math, statistics as st
from pathlib import Path

U_MAX_MS = 0.39
BA_MIN_MS = 0.60
DRIFT_MAX_PCT = 3.0
ORDER = ('production', 'unsplit', 'production', 'unsplit', 'production')
HEAD_SCOPES = ('head_service_total', 'head_hidden_wait', 'suffix_head', 'head_import', 'head_export')
RULE = ('V3 GO iff un-split cost on rank 1 u <= 0.39 ms AND decoupled B-A on the unsplit views >= 0.60 ms AND every '
        'view 13/13 exact with identical draft proposals AND control drift <= 3%; otherwise V3 closed and packet177(b) '
        'keeps its closure with the measured attribution appended')


class Incomplete(ValueError):
    pass


def demand(ok, reason):
    if not ok:
        raise Incomplete(reason)


def mean(values):
    values = list(values)
    return st.mean(values) if values else None


def head_scopes(request_dir, stamps):
    """Per-cycle rank-0 suffix-service scopes inside the 99-interval window (packet150 clocks)."""
    path = Path(request_dir) / 'rank0/timings.jsonl'
    demand(path.is_file() and path.stat().st_size > 0, 'missing rank0 timing stream: ' + str(path))
    records = [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
    samples = [r for r in records if 'p150_segment' in r and stamps[0] <= r['start'] <= r['end'] <= stamps[-1]]
    demand(samples, 'missing packet150 scopes in the measured window: ' + str(path))
    totals = {name: 0. for name in HEAD_SCOPES}
    counts = {name: 0 for name in HEAD_SCOPES}
    for r in samples:
        if r['p150_segment'] in totals:
            demand(math.isfinite(r['ms']) and r['ms'] >= 0, 'invalid scope clock')
            totals[r['p150_segment']] += r['ms']
            counts[r['p150_segment']] += 1
    return totals, counts


def view_stats(view_dir, prompt_ids, split):
    """Interval and scope statistics of one view directory (12 prompts, first 99 intervals each)."""
    from interval_model import intervals
    view_dir = Path(view_dir)
    rows, cycles, scope_totals, scope_counts = [], 0, {n: 0. for n in HEAD_SCOPES}, {n: 0 for n in HEAD_SCOPES}
    for prompt in prompt_ids:
        receipt = view_dir / prompt / 'receipt.json'
        demand(receipt.is_file(), 'missing request receipt: ' + str(receipt))
        r = json.loads(receipt.read_text())
        demand(r.get('passed') is True and r.get('exact_oracle') is True and r.get('cached_tokens') == 0,
               'request not exact/cold: ' + prompt)
        demand('rank_trace' in r and 'guess_rows' in r and 'generated_token_completion_timestamps' in r,
               'missing native correction stream: ' + prompt)
        part = intervals(r)
        demand(len(part) == 99, 'expected 99 intervals per 128-token prompt: ' + prompt)
        rows += part
        stamps = r['token_timestamps'][:100]
        demand(len(stamps) == 100 and all(b > a for a, b in zip(stamps, stamps[1:])), 'invalid timestamps: ' + prompt)
        totals, counts = head_scopes(view_dir / prompt, stamps)
        cycles += len(stamps) - 1
        for n in HEAD_SCOPES:
            scope_totals[n] += totals[n]
            scope_counts[n] += counts[n]
    hits = [x for x in rows if x['hit']]
    misses = [x for x in rows if not x['hit']]
    demand(len(hits) >= 600 and len(misses) >= 100, 'too few hit/miss intervals for an attribution')
    ba = sorted(x['B'] - x['A'] for x in hits)
    q = st.quantiles(ba, n=10)
    if split:
        demand(all(scope_counts[n] >= cycles * 0.9 for n in HEAD_SCOPES),
               'split view must record the rank-0 suffix service every cycle')
    else:
        demand(all(scope_counts[n] == 0 for n in HEAD_SCOPES),
               'unsplit view must not run a rank-0 suffix service')
    per_cycle = {n: scope_totals[n] / cycles for n in HEAD_SCOPES}
    return dict(
        intervals=len(rows), hits=len(hits), misses=len(misses), cycles=cycles,
        hit=dict(D=mean(x['D'] for x in hits), A=mean(x['A'] for x in hits), B=mean(x['B'] for x in hits),
                 B_minus_A=mean(ba), B_minus_A_p10=q[0], B_minus_A_p50=st.median(ba),
                 rank0_slack=mean(x['rank0_slack_ms'] for x in hits),
                 offset=mean(x['spec_start_offset_ms'] for x in hits),
                 G=mean(x['unresolved_control_gaps_ms'] for x in hits), elapsed=mean(x['elapsed_ms'] for x in hits)),
        miss=dict(D=mean(x['D'] for x in misses), R=mean(x['R'] for x in misses), C=mean(x['C'] for x in misses),
                  A=mean(x['A'] for x in misses), B=mean(x['B'] for x in misses),
                  B_minus_A=mean(x['B'] - x['A'] for x in misses),
                  G=mean(x['unresolved_control_gaps_ms'] for x in misses), elapsed=mean(x['elapsed_ms'] for x in misses)),
        pooled_interval_ms=mean(x['elapsed_ms'] for x in rows),
        head_service_per_cycle_ms=per_cycle,
        sigma_rank0_service_ms=(per_cycle['head_service_total'] - per_cycle['head_hidden_wait']) if split else None,
        split_head=bool(split),
        definition='packet85 intervals (vendored); hit = guess verified at the starting emission; '
                   'B includes rank-1 head and (split) merge wait; rank0_slack = B - A - offset')


def measure(controls, unsplit):
    """Arithmetic of the attribution, for any non-empty control / unsplit view-stat lists."""
    demand(controls and unsplit, 'controls and unsplit views required')
    cB = [v['hit']['B'] for v in controls]
    uB = [v['hit']['B'] for v in unsplit]
    cD = [v['hit']['D'] for v in controls]
    uD = [v['hit']['D'] for v in unsplit]
    u = mean(uB) - mean(cB)
    u_d = mean(uB) - mean(cB) * mean(uD) / mean(cD)
    ba = [v['hit']['B_minus_A'] for v in unsplit]
    sigma = [v['sigma_rank0_service_ms'] for v in controls if v.get('sigma_rank0_service_ms') is not None]
    return dict(
        u_rank1_unsplit_cost_ms=u, u_draft_corrected_ms=u_d,
        control_hit_B_ms=cB, unsplit_hit_B_ms=uB, control_hit_B_range_ms=max(cB) - min(cB),
        control_hit_D_ms=cD, unsplit_hit_D_ms=uD,
        decoupled_B_minus_A_ms=mean(ba), decoupled_B_minus_A_per_view_ms=ba,
        decoupled_B_minus_A_p10_ms=[v['hit']['B_minus_A_p10'] for v in unsplit],
        unsplit_rank0_slack_outside_draft_ms=mean(v['hit']['rank0_slack'] for v in unsplit),
        control_B_minus_A_ms=mean(v['hit']['B_minus_A'] for v in controls),
        sigma_rank0_service_ms=mean(sigma) if sigma else None,
        control_suffix_head_ms=mean(v['head_service_per_cycle_ms']['suffix_head'] for v in controls),
        control_hit_interval_ms=mean(v['hit']['elapsed'] for v in controls),
        unsplit_hit_interval_ms=mean(v['hit']['elapsed'] for v in unsplit),
        control_miss_interval_ms=mean(v['miss']['elapsed'] for v in controls),
        unsplit_miss_interval_ms=mean(v['miss']['elapsed'] for v in unsplit))


def decide(rows):
    """rows: the five view-row records in registered order (index, variant, rate, exactness,
    draft_proposals, acceptance_counts, interval_stats)."""
    demand(len(rows) == 5 and [r['index'] for r in rows] == list(range(5)), 'five view rows 0..4 required')
    demand([r['variant'] for r in rows] == list(ORDER), 'view order must be production/unsplit/production/unsplit/production')
    exact = all(r.get('all_13_exact') is True and r.get('exact_count') == 13 for r in rows)
    proposals = all(r['draft_proposals'] == rows[0]['draft_proposals'] for r in rows)
    acceptance = all(r['acceptance_counts'] == rows[0]['acceptance_counts'] for r in rows)
    controls = [r for r in rows if r['variant'] == 'production']
    unsplit = [r for r in rows if r['variant'] == 'unsplit']
    rates = [r['rate'] for r in controls]
    drift = 100 * (max(rates) / min(rates) - 1)
    m = measure([r['interval_stats'] for r in controls], [r['interval_stats'] for r in unsplit])
    u, ba = m['u_rank1_unsplit_cost_ms'], m['decoupled_B_minus_A_ms']
    go = bool(u <= U_MAX_MS and ba >= BA_MIN_MS and exact and proposals and acceptance and drift <= DRIFT_MAX_PCT)
    resolved_u = abs(u - U_MAX_MS) > m['control_hit_B_range_ms'] and (u <= U_MAX_MS) == (m['u_draft_corrected_ms'] <= U_MAX_MS)
    slack = m['unsplit_rank0_slack_outside_draft_ms']
    attribution = ('packet185 measured (fresh-load C/U/C/U/C, lane B): split-head suffix service on rank 0 sigma = %.3f ms/cycle; '
                   'un-split cost on rank 1 u = %.3f ms (D-corrected %.3f, control B spread %.3f); decoupled B-A = %.3f ms; '
                   'rank-0 slack outside the draft dependency with the full head on rank 1 = %.3f ms/hit (packet177 asks >= 1 ms)'
                   % (m['sigma_rank0_service_ms'] or float('nan'), u, m['u_draft_corrected_ms'], m['control_hit_B_range_ms'], ba, slack))
    return dict(
        schema='packet185.s185-decision.v1', v3_go=go, outcome='V3 GO: build V3 on these measured numbers' if go else
        'V3 CLOSED: packet177(b) keeps its closure; append the measured attribution',
        rule=RULE, thresholds=dict(u_max_ms=U_MAX_MS, decoupled_B_minus_A_min_ms=BA_MIN_MS, drift_max_percent=DRIFT_MAX_PCT),
        every_view_exact=exact, draft_proposals_identical=proposals, acceptance_identical=acceptance,
        control_rates=rates, unsplit_rates=[r['rate'] for r in unsplit], control_drift_percent=drift,
        u_resolved=bool(resolved_u), packet177_slack_condition_met=bool(slack >= 1.0),
        attribution=attribution, **m)


def decide_or_incomplete(rows_or_error):
    try:
        if isinstance(rows_or_error, Exception):
            raise rows_or_error
        return decide(rows_or_error)
    except (Incomplete, KeyError, ValueError, TypeError, OSError) as error:
        return dict(schema='packet185.s185-decision.v1', v3_go=False, outcome='INCOMPLETE: no decision',
                    reason=str(error), rule=RULE)


def row_record(summary):
    """The decision input carried by one view row's bracket-summary.json."""
    view = summary['views'][0]
    return dict(index=summary['view_index'], variant=summary['variant'], rate=view['rate'],
                all_13_exact=view['all_13_exact'], exact_count=view['exact_count'],
                draft_proposals=view['draft_proposals'], acceptance_counts=view['acceptance_counts'],
                interval_stats=summary['interval_stats'])


if __name__ == '__main__':
    import argparse, resource
    resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3))
    ap = argparse.ArgumentParser(description='Recompute s185_decision from the five retained view-row outputs.')
    ap.add_argument('outputs', nargs=5, type=Path)
    ap.add_argument('--write', type=Path)
    a = ap.parse_args()
    from p185_v5_compare import load
    result = decide_or_incomplete([row_record(load(p)) for p in a.outputs])
    print(json.dumps(result, indent=2))
    if a.write:
        a.write.write_text(json.dumps(result, indent=2) + '\n')
