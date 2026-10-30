#!/usr/bin/env python3
"""Stage-overhead analysis (research/tp/stage-overhead-2026-10-30). CPU only, over the phase run directories.

  analyze.py timing RUN [RUN ...]            per-run half times (driver + engine host timings), medians of steps 3..
  analyze.py sites RUN --out FILE.json       OWNRT_TP_EXCHANGE_STATS per-site waits / exchange-kernel time, both cards
  analyze.py probe ONE P0 P1 --out FILE.json one-card site traces: one-card plan vs card 0's / card 1's TP shapes

Clock: the exchange statistics are EU-thread sub-group clock cycles; 2.80 cycles/ns from results/clocktest-c23b.json
(a 200,000-poll spin timed by the host: 53.8-54.2 M cycles in 19.23-19.37 ms).
"""
import argparse, collections, json, re, statistics as st, sys
from pathlib import Path

GHZ = 2.80
# Roles the record's four-card plan splits between the two cards of a stage (state-bundle/build/source-v4/rank.hpp TP
# transform: OWNRT_TP_SPLIT rows, OWNRT_TP_GDN=heads, OWNRT_TP_EXPERTS=compact, OWNRT_TP_QSA_SPLIT (q/k/v rows, prepare,
# pool, attention on 12 heads / 1 KV head), OWNRT_TARGET_HEAD_SPLIT) plus the TP-only route compaction; every other role
# runs whole on both cards. (decode-site-census TP_SPLIT + qsa.prepare/qsa.pool, which the QSA split also halves.)
TP_SPLIT = {'gdn.qkv', 'gdn.z', 'gdn.a', 'gdn.conv', 'gdn.recurrence', 'gdn.gated', 'attention', 'qsa.qgate', 'qsa.k', 'qsa.v',
            'qsa.attention', 'qsa.prepare', 'qsa.pool', 'expsgate', 'expsup', 'expsact', 'expsdown', 'expsdown.check', 'logits',
            'argmax', 'gather.tp_compact'}
LAYER = re.compile(r'^(?:draft\.)?blk\.(\d+)\.(.*)$')


def med(v):
    return round(st.median(v), 4) if v else None


def rank_of(run):
    return 0 if (Path(run) / 'rank0').is_dir() else 1


def timing(run, skip=2):
    run = Path(run); r = rank_of(run); s = json.loads((run / 'summary.json').read_text())
    half = s.get('spec_ms') or s.get('half_ms') or []
    rows = [json.loads(x) for x in open(run / f'rank{r}' / 'timings.jsonl')]
    rows = [x for x in rows if 'fixture' in x and x.get('fixture') == 1]  # decode steps only (prompt rows: fixture 0)
    out = dict(run=run.name, rank=r, tp=s.get('tp'), steps=len(half), half_ms=med(half[skip:]), half_ms_p90=round(sorted(half[skip:])[int(0.9 * len(half[skip:]))], 4) if half[skip:] else None,
               draft_ms=med((s.get('draft_ms') or [])[skip:]))
    for k in ('half_completion_ms', 'enqueue_loop_ms', 'wait_ms', 'card1_thread_start_us', 'p76_retirement_ms', 'prepare_ms', 'launches_issued', 'host_waits'):
        v = [x[k] for x in rows[skip:] if x.get(k) is not None]
        if v:
            out[k] = med(v)
    return out


def kind(label):
    m = LAYER.match(label)
    return m.group(2) if m else label


def sites(run):
    run = Path(run); r = rank_of(run); base = run / f'rank{r}'
    slots = {x['slot']: x for x in json.loads((base / 'tp-exchange-slots.json').read_text())['slots']}
    d = json.loads((base / 'tp-exchange-sites.json').read_text())
    rows = []
    per = [{x['slot']: x for x in card} for card in d['cards']]
    for slot in sorted(slots):
        a, b = per[0].get(slot), per[1].get(slot)
        if not a or not b:
            continue
        f = lambda x, k: x[k] / x['n'] / GHZ / 1000.0  # us per execution
        rows.append(dict(slot=slot, label=slots[slot]['label'], kind=kind(slots[slot]['label']), values=slots[slot]['values'], n=a['n'],
                         wait0_us=round(f(a, 'wait_cycles'), 3), wait1_us=round(f(b, 'wait_cycles'), 3),
                         own0_us=round(f(a, 'own_cycles'), 3), own1_us=round(f(b, 'own_cycles'), 3),
                         max_wait0_us=round(a['max_wait_cycles'] / GHZ / 1000, 2), max_wait1_us=round(b['max_wait_cycles'] / GHZ / 1000, 2),
                         polls0=round(a['polls'] / a['n'], 2), polls1=round(b['polls'] / b['n'], 2), hist0=a['hist'], hist1=b['hist']))
    for x in rows:
        # the card that waits arrived first; the other card's segment since the previous exchange was longer by ~ that wait
        x['late_card'] = 1 if x['wait0_us'] > x['wait1_us'] else 0
        x['imbalance_us'] = round(abs(x['wait0_us'] - x['wait1_us']), 3)
    by = collections.defaultdict(lambda: dict(sites=0, wait0_us=0.0, wait1_us=0.0, own0_us=0.0, own1_us=0.0, imbalance_us=0.0, card1_late=0))
    for x in rows:
        k = by[x['kind']]; k['sites'] += 1
        for f in ('wait0_us', 'wait1_us', 'own0_us', 'own1_us', 'imbalance_us'):
            k[f] = round(k[f] + x[f], 3)
        k['card1_late'] += x['late_card']
    tot = dict(sites=len(rows), wait0_us=round(sum(x['wait0_us'] for x in rows), 2), wait1_us=round(sum(x['wait1_us'] for x in rows), 2),
               own0_us=round(sum(x['own0_us'] for x in rows), 2), own1_us=round(sum(x['own1_us'] for x in rows), 2),
               imbalance_us=round(sum(x['imbalance_us'] for x in rows), 2),
               first_site_wait0_us=rows[0]['wait0_us'] if rows else None, first_site_wait1_us=rows[0]['wait1_us'] if rows else None,
               cycles_per_poll=round(sum(per[c][s]['wait_cycles'] for c in (0, 1) for s in per[c]) / max(1, sum(per[c][s]['polls'] for c in (0, 1) for s in per[c])), 1))
    return dict(run=run.name, rank=r, skip_epochs=d['skip_epochs'], clock_ghz=GHZ, total_per_half=tot, by_kind=dict(by),
                top_imbalance=sorted(rows, key=lambda x: -x['imbalance_us'])[:25], sites=rows)


def trace_roles(run, skip=8):
    """Median over decode halves (phases of kind 'half' with fixture 1) of each role's summed device us; per-label too."""
    run = Path(run); r = rank_of(run)
    phases, events = [], collections.defaultdict(list)
    with open(run / f'rank{r}' / 'site-trace.jsonl') as f:
        for line in f:
            d = json.loads(line)
            if 'phase' in d:
                phases.append(d)
            else:
                events[d['p']].append((d['c'], d['s'], d['e']))
    halves = [p for p in phases if p['kind'] == 'half' and p.get('extra', 0) >= 2]  # extra = fixture*2 + speculative: decode steps
    halves = halves[skip:]
    per_role = collections.defaultdict(list); per_label = collections.defaultdict(list); spans, busy, counts = [], [], collections.defaultdict(list)
    drafts = collections.defaultdict(list)
    for p in halves:
        ev = events.get(p['phase'], [])
        if not ev:
            continue
        acc = collections.defaultdict(float); accl = collections.defaultdict(float); cnt = collections.Counter()
        for c, s, e in ev:
            role = kind(c); acc[role] += (e - s) / 1000.0; accl[c] += (e - s) / 1000.0; cnt[role] += 1
        for k, v in acc.items():
            per_role[k].append(v); counts[k].append(cnt[k])
        for k, v in accl.items():
            per_label[k].append(v)
        spans.append((max(e for _, _, e in ev) - min(s for _, s, _ in ev)) / 1000.0)
        busy.append(sum(e - s for _, s, e in ev) / 1000.0)
    for p in phases:
        if p['kind'].startswith('draft'):
            ev = events.get(p['phase'], [])
            if ev:
                drafts[p['kind']].append((max(e for _, _, e in ev) - min(s for _, s, _ in ev)) / 1000.0)
    return dict(halves=len(spans), span_us=med(spans), busy_us=med(busy),
                roles={k: dict(us=med(v), launches=med(counts[k])) for k, v in per_role.items()},
                labels={k: med(v) for k, v in per_label.items()},
                drafts={k: dict(n=len(v), span_us=med(v[skip:])) for k, v in drafts.items()})


def probe(one, p0, p1):
    A, B0, B1 = trace_roles(one), trace_roles(p0), trace_roles(p1)
    roles = sorted(set(A['roles']) | set(B0['roles']) | set(B1['roles']), key=lambda k: -(A['roles'].get(k, {}).get('us') or 0))
    rows = []
    for k in roles:
        a = (A['roles'].get(k) or {}).get('us') or 0.0
        b0 = (B0['roles'].get(k) or {}).get('us') or 0.0
        b1 = (B1['roles'].get(k) or {}).get('us') or 0.0
        split = k in TP_SPLIT  # split between the two cards by the four-card plan (rank.hpp transform)
        rows.append(dict(role=k, one_us=a, card0_us=b0, card1_us=b1, launches_one=(A['roles'].get(k) or {}).get('launches'),
                         launches_card0=(B0['roles'].get(k) or {}).get('launches'), changed=split,
                         ratio0=round(b0 / a, 3) if a else None, ratio1=round(b1 / a, 3) if a else None,
                         excess_over_half_us=round(max(b0, b1) - a / 2, 1) if split else None,
                         card_gap_us=round(b0 - b1, 1)))
    ch = [x for x in rows if x['changed']]
    # per-layer imbalance of each changed role: card0 - card1 per label
    lab = []
    for l in sorted(set(B0['labels']) & set(B1['labels'])):
        d = B0['labels'][l] - B1['labels'][l]
        if abs(d) >= 0.5:
            lab.append(dict(label=l, card0_us=B0['labels'][l], card1_us=B1['labels'][l], card0_minus_card1_us=round(d, 2)))
    lab.sort(key=lambda x: -abs(x['card0_minus_card1_us']))
    tot = dict(one_busy_us=A['busy_us'], card0_busy_us=B0['busy_us'], card1_busy_us=B1['busy_us'], one_span_us=A['span_us'],
               card0_span_us=B0['span_us'], card1_span_us=B1['span_us'],
               changed_one_us=round(sum(x['one_us'] for x in ch), 1), changed_card0_us=round(sum(x['card0_us'] for x in ch), 1),
               changed_card1_us=round(sum(x['card1_us'] for x in ch), 1),
               changed_excess_over_half_us=round(sum(max(x['card0_us'], x['card1_us']) - x['one_us'] / 2 for x in ch), 1),
               changed_mean_excess_over_half_us=round(sum((x['card0_us'] + x['card1_us']) / 2 - x['one_us'] / 2 for x in ch), 1),
               unchanged_one_us=round(sum(x['one_us'] for x in rows if not x['changed']), 1),
               unchanged_card0_us=round(sum(x['card0_us'] for x in rows if not x['changed']), 1),
               unchanged_card1_us=round(sum(x['card1_us'] for x in rows if not x['changed']), 1))
    return dict(one=one, card0=p0, card1=p1, halves=dict(one=A['halves'], card0=B0['halves'], card1=B1['halves']), totals=tot,
                roles=rows, label_imbalance_top=lab[:40], drafts=dict(one=A['drafts'], card0=B0['drafts'], card1=B1['drafts']))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest='cmd', required=True)
    t = sub.add_parser('timing'); t.add_argument('runs', nargs='+'); t.add_argument('--out')
    s = sub.add_parser('sites'); s.add_argument('run'); s.add_argument('--out')
    p = sub.add_parser('probe'); p.add_argument('one'); p.add_argument('p0'); p.add_argument('p1'); p.add_argument('--out')
    a = ap.parse_args()
    if a.cmd == 'timing':
        res = [timing(x) for x in a.runs]
        for x in res:
            print(json.dumps(x))
    elif a.cmd == 'sites':
        res = sites(a.run); print(json.dumps(res['total_per_half'])); print(json.dumps(res['by_kind']))
    else:
        res = probe(a.one, a.p0, a.p1); print(json.dumps(res['totals']))
    if a.out:
        Path(a.out).write_text(json.dumps(res, indent=1) + '\n')
