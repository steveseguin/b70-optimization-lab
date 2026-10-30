#!/usr/bin/env python3
"""Per-stage TP overhead breakdown (research/tp/stage-overhead-2026-10-30). CPU only, over results/*.json written by
analyze.py and hitcycle.py. Writes results/breakdown.json; every number in RESULT.md comes from it or from the inputs.

Per rank (ms per decode half, rank-harness medians of steps 3..64, positions 128-191, fixture inputs):
  overhead = TP half - (one-card half - S/2), S = one-card device time of the roles the four-card plan splits (probe trace)
  (c) split shapes   = probe: card's device busy for its TP plan without exchanges - (one-card busy - S/2)   [measured, 1 card]
  (a) exchange       = OWNRT_TP_EXCHANGE_STATS: own (entry -> start of wait) summed over sites, mean of cards   [measured, TP]
      + flag latency = sum over sites of min(wait0, wait1): the wait a card sees even when both arrive together    [measured, TP]
  (b) imbalance      = sum over sites of |wait0 - wait1| / 2 (the cost of the later card on the critical path)  [measured, TP]
  (d) two-card host  = engine host timings, TP minus one card: input preparation + the tail after the enqueue loop  [measured]
                       and device wait (card-1 thread join, second drain, card-1 error readback); cross-check: rep - one
  residual           = overhead - (a + b + c + d): exchange-kernel launch/teardown not seen by the in-kernel clock,
                       and anything else                                                                           [derived]
Cross-check: xonly - rep = in-engine cost of the row-split sites' exchanges with nothing split (direct-replicated).
"""
import json, statistics as st
from pathlib import Path
HERE = Path(__file__).resolve().parent
R = HERE / 'results'


def load(n):
    return json.loads((R / n).read_text())


def runs(timing, prefix):
    return [x for x in timing if x['run'].startswith(prefix)]


def mean(v):
    return round(st.fmean(v), 4)


def rank(r, timing, sites, probe, one_prefix, xonly_exchanges):
    one = mean([x['half_ms'] for x in timing if x['run'] in one_prefix])
    full = mean([x['half_ms'] for x in timing if x['run'].endswith(('-full', '-full2'))])
    full_xs = [x['half_ms'] for x in timing if x['run'].endswith('-full-xs')][0]
    rep = [x['half_ms'] for x in timing if x['run'].endswith('-rep')][0]
    xonly = [x['half_ms'] for x in timing if x['run'].endswith('-xonly')][0]
    t = probe['totals']
    S = t['changed_one_us'] / 1000.0
    ideal = one - S / 2
    overhead = full - ideal
    split_c = [(t[f'card{c}_busy_us'] - (t['one_busy_us'] - t['changed_one_us'] / 2)) / 1000.0 for c in (0, 1)]
    c = max(split_c)
    rows = sites['sites']
    own = st.fmean([sum(x['own0_us'] for x in rows), sum(x['own1_us'] for x in rows)]) / 1000.0
    floor = sum(min(x['wait0_us'], x['wait1_us']) for x in rows) / 1000.0
    imb = sum(abs(x['wait0_us'] - x['wait1_us']) / 2 for x in rows) / 1000.0
    first = rows[0]
    # (d) host-side two-card cost, from the engine's own per-half host timings (timings.jsonl): input preparation plus the
    # tail after the enqueue loop and the device wait (card-1 thread join, second card's drain, card-1 error readback),
    # TP minus one card. The replicated A/B (rep - one) is kept as a cross-check: on rank 0 it also carries the
    # replicated layout's own extra work (full-size card-1 state and snapshot), so it overstates the TP cost there.
    host = lambda xs: (st.fmean([x['prepare_ms'] for x in xs]), st.fmean([x['half_completion_ms'] - x['prepare_ms'] - x['enqueue_loop_ms'] - x['wait_ms'] for x in xs]))
    one_rows = [x for x in timing if x['run'] in one_prefix]; full_rows = [x for x in timing if x['run'].endswith(('-full', '-full2'))]
    (p1, t1), (pf, tf) = host(one_rows), host(full_rows)
    d = (pf - p1) + (tf - t1)
    a = own + floor
    residual = overhead - (a + imb + c + d)
    # split excess per role (max of the two cards minus half the one-card time), largest first
    roles = sorted([dict(role=x['role'], one_us=round(x['one_us'], 1), card0_us=round(x['card0_us'], 1), card1_us=round(x['card1_us'], 1),
                         launches=x['launches_one'] or x['launches_card0'], ratio=x['ratio0'],
                         excess_us=round(max(x['card0_us'], x['card1_us']) - x['one_us'] / 2, 1),
                         card0_minus_card1_us=x['card_gap_us'])
                    for x in probe['roles'] if x['changed']], key=lambda y: -y['excess_us'])
    repl = [x for x in probe['roles'] if not x['changed']]
    return dict(
        rank=r,
        halves=dict(one_card=one, tp_full=full, tp_full_with_stats=full_xs, tp_replicated_no_exchange=rep, tp_exchange_only=xonly,
                    stats_perturbation_ms=round(full_xs - full, 4)),
        split_roles_one_card_ms=round(S, 4), ideal_tp_half_ms=round(ideal, 4), overhead_ms=round(overhead, 4),
        components_ms=dict(
            c_split_shapes=dict(ms=round(c, 4), per_card=[round(x, 4) for x in split_c], source='one-card probe trace (OWNRT_TP_SHAPE_PROBE + OWNRT_SITE_TRACE)', kind='measured'),
            a_exchange_kernels=dict(ms=round(a, 4), own=round(own, 4), flag_latency=round(floor, 4), sites=len(rows),
                                    per_site_us=round(a * 1000 / len(rows), 2), source='OWNRT_TP_EXCHANGE_STATS (sub-group clock, 2.80 GHz)', kind='measured'),
            b_imbalance=dict(ms=round(imb, 4), first_site_card1_start_lag_us=round(abs(first['wait0_us'] - first['wait1_us']) / 2, 2),
                             waits_card0=sites['total_per_half']['wait0_us'] / 1000, waits_card1=sites['total_per_half']['wait1_us'] / 1000,
                             source='OWNRT_TP_EXCHANGE_STATS', kind='measured'),
            d_two_card_host=dict(ms=round(d, 4), prepare_delta=round(pf - p1, 4), tail_delta=round(tf - t1, 4), tail_one_card=round(t1, 4), tail_tp=round(tf, 4),
                                 replicated_ab_ms=round(rep - one, 4), source='engine host timings (timings.jsonl), TP minus one card; cross-check A/B --tp-replicate nothing split', kind='measured'),
            residual=dict(ms=round(residual, 4), kind='derived (overhead minus a+b+c+d): exchange-kernel launch/teardown and the rest')),
        cross_check=dict(exchange_only_minus_replicated_ms=round(xonly - rep, 4), exchanges=xonly_exchanges,
                         per_exchange_us=round((xonly - rep) * 1000 / xonly_exchanges, 2)),
        split_role_excess=roles,
        replicated_roles_one_vs_card=dict(one_us=round(sum(x['one_us'] for x in repl), 1), card0_us=round(sum(x['card0_us'] for x in repl), 1),
                                          card1_us=round(sum(x['card1_us'] for x in repl), 1)),
        probe_card_busy_us=dict(card0=t['card0_busy_us'], card1=t['card1_busy_us'], one=t['one_busy_us']))


def main():
    out = dict(schema='ownrt.research.tp-stage-overhead.v1', date='2026-10-30', clock_ghz=2.80)
    t1 = load('a1-rank1-timing.json'); t0 = load('b1-rank0-timing.json') + load('c2-rank0-timing.json')
    out['rank1'] = rank(1, t1, load('a1-rank1-sites.json'), load('c1-rank1-probe.json'), ('a1-r1-one', 'a1-r1-one2'), 33)
    # rank 0: the one-card baseline with the same snapshot/rollback nowait flags as the four-card arms (c2-r0-one-nw*);
    # the flagless one-card arms (b1-r0-one*) are kept for reference
    out['rank0'] = rank(0, t0, load('b1-rank0-sites.json'), load('c2-rank0-probe.json'), ('c2-r0-one-nw', 'c2-r0-one-nw2'), 37)
    out['rank0']['one_card_without_nowait_ms'] = mean([x['half_ms'] for x in t0 if x['run'] in ('b1-r0-one', 'b1-r0-one2')])
    out['rank0']['draft_ms'] = dict(one_card=mean([x['draft_ms'] for x in t0 if x['run'].startswith('c2-r0-one-nw')]),
                                    tp=mean([x['draft_ms'] for x in t0 if x['run'].endswith(('-full', '-full2'))]))
    out['hitcycle_service'] = {k: {kk: v[kk] for kk in ('hit_interval', 'rank1_wall', 'rank0_spec_wall', 'draft_wall', 'snapshot', 'token_prep', 'layer_body',
                                                       'export', 'ctrl', 'rank0_path', 'rank1_path', 'rank0_later_fraction')}
                               for k, v in load('hitcycle-tptsxqc.json').items()}
    (R / 'breakdown.json').write_text(json.dumps(out, indent=1) + '\n')
    for r in ('rank1', 'rank0'):
        x = out[r]
        print(r, json.dumps(x['halves']), 'S', x['split_roles_one_card_ms'], 'ideal', x['ideal_tp_half_ms'], 'overhead', x['overhead_ms'])
        print('  ', json.dumps({k: v['ms'] for k, v in x['components_ms'].items()}), 'xcheck', x['cross_check'])
        print('   top excess', [(y['role'], y['excess_us']) for y in x['split_role_excess'][:12]])


if __name__ == '__main__':
    main()
