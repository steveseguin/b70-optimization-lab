#!/usr/bin/env python3
"""Miss-stall analysis of the four-card SC117 service (CPU only, retained evidence; 2026-10-29).

Inputs (read-only):
  * the native controller trace of the one request each lab server retains (the 3,490-token prompt, 64 decode tokens):
    <arm>/control/run-*/ranks/native-result.json (rank_trace, guess_rows, timing_rows), and rank 0's p150 host
    segments and per-half rows <arm>/evidence/run-*/req-000040/rank{0,1}/timings.jsonl, in the RAID archives
    target-head-split-suite-20261029 (servers *-r0) and target-head-split-repeat-20261029 (servers *-r1, *-r2);
  * the 12-prompt suite rows of the same servers (repo: target-head-split-2026-10-29/results/.../suite.json).

Outputs analysis.json (every number in ANALYSIS.md comes from it).

Timeline (native_controller.hpp run(); rank 0 runs on the controller thread, rank 1 behind the mailbox):
  E(q)  = rank 1's HALF(q) completion; it publishes token q+1 (the verification of rank 0's guess for q+1).
  Interval(q) = E(q) - E(q-1) carries generated token q+1.
  hit at q  : rank 1 HALF(q) is sent once rank 1 has finished HALF(q-1) AND rank 0's speculative HALF(q) has returned;
              rank 0 then runs DRAFT(q) and the speculative HALF(q+1) while rank 1 runs HALF(q).
  miss at q : after both, rank 0 runs ROLLBACK (op 3), the corrected HALF(q) (redo), ACCEPT; only then rank 1's HALF(q)
              and rank 0's deferred DRAFT(q), then the speculative HALF(q+1).
"""
import glob, json, os, statistics as st, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
ARCH = Path('/mnt/raid-models/ownrt-experiment-archives/2026-10-29')
THS = HERE.parent / 'target-head-split-2026-10-29' / 'results'
SERVERS = {  # name: (archive arm dir, suite.json)
    'tpts-r0': (ARCH / 'target-head-split-suite-20261029/arm-tpts', THS / 'arm-tpts/suite.json'),
    'tpts-r1': (ARCH / 'target-head-split-repeat-20261029/arm-tpts-r1', THS / 'repeat/arm-tpts-r1/suite.json'),
    'tpts-r2': (ARCH / 'target-head-split-repeat-20261029/arm-tpts-r2', THS / 'repeat/arm-tpts-r2/suite.json'),
    'tp-r0': (ARCH / 'target-head-split-suite-20261029/arm-tp', THS / 'arm-tp/suite.json'),
    'tp-r1': (ARCH / 'target-head-split-repeat-20261029/arm-tp-r1', THS / 'repeat/arm-tp-r1/suite.json'),
    'tp-r2': (ARCH / 'target-head-split-repeat-20261029/arm-tp-r2', THS / 'repeat/arm-tp-r2/suite.json'),
    'tpt-r0': (ARCH / 'target-head-split-suite-20261029/arm-tpt', THS / 'arm-tpt/suite.json'),
    'two-r0': (ARCH / 'target-head-split-suite-20261029/arm-two', THS / 'arm-two/suite.json'),
}
HALF, ACCEPT, ROLLBACK, DRAFT = 1, 2, 3, 9
MS = 1000.0


def med(v): return round(st.median(v), 4) if v else None
def mean(v): return round(st.fmean(v), 4) if v else None
def q(v, f): v = sorted(v); return round(v[min(len(v) - 1, int(len(v) * f))], 4) if v else None
def dist(v): return dict(n=len(v), mean=mean(v), median=med(v), p10=q(v, .1), p90=q(v, .9), min=round(min(v), 4) if v else None, max=round(max(v), 4) if v else None)


def one(arm):
    run = sorted(glob.glob(str(arm / 'control/run-*')))[-1]
    d = json.load(open(Path(run) / 'ranks/native-result.json'))
    ev = Path(sorted(glob.glob(str(arm / 'evidence/run-*')))[-1]) / 'req-000040'
    first = d['guess_rows'][0]['position']          # 3490: first position whose token is a guessed one
    tr = d['rank_trace']
    r1 = {t['position']: t for t in tr if t['rank'] == 1 and t['op'] == HALF and t['position'] >= first - 1}
    spec = {t['position']: t for t in tr if t['rank'] == 0 and t['op'] == HALF and t['speculative'] and t['position'] >= first}
    redo = {t['position']: t for t in tr if t['rank'] == 0 and t['op'] == HALF and not t['speculative'] and t['position'] >= first}
    rb = {t['position']: t for t in tr if t['rank'] == 0 and t['op'] == ROLLBACK and t['position'] >= first}
    dr = {t['position']: t for t in tr if t['rank'] == 0 and t['op'] == DRAFT and t['position'] >= first - 1}
    hit = {g['position']: g['hit'] for g in d['guess_rows']}
    # rank 0 p150 host segments (start/end monotonic); spec halves and redo halves share a position: split by time.
    seg = {}
    for line in open(ev / 'rank0/timings.jsonl'):
        r = json.loads(line)
        if 'p150_segment' in r: seg.setdefault(r['p150_segment'], []).append(r)
    def inside(name, t):  # the segment of this name inside rank-0 op t's [sent, completed]
        m = [s for s in seg.get(name, []) if s['start'] >= t['sent'] - 1e-6 and s['end'] <= t['rank_completed'] + 1e-6]
        return m[0]['ms'] if m else 0.0
    r1rows = {r['position']: r for r in map(json.loads, open(ev / 'rank1/timings.jsonl')) if 'fixture' in r}
    r0rows = [r for r in map(json.loads, open(ev / 'rank0/timings.jsonl')) if 'fixture' in r]
    w = lambda t: (t['rank_completed'] - t['sent']) * MS
    E = lambda p: r1[p]['rank_completed']
    rows = []
    for p in range(first, first + len(d['guess_rows'])):
        h = hit[p]; s = spec[p]; prev = E(p - 1)
        late = max(0.0, s['rank_completed'] - prev) * MS          # rank 0's speculative HALF(p) ends after rank 1's HALF(p-1)
        base = max(prev, s['rank_completed'])
        row = dict(position=p, hit=h, interval=(E(p) - prev) * MS, rank0_late=late,
                   rank0_spec_wall=w(s), rank0_spec_busy=s['busy_ms'], snapshot=inside('snapshot', s),
                   layer_body_spec=inside('layer_body', s), token_prep_spec=inside('token_prep', s), export_spec=inside('handoff_export', s),
                   draft_wall=w(dr[p - 1]) if p - 1 in dr else None,
                   rank1_wall=w(r1[p]), rank1_busy=r1[p]['busy_ms'], rank1_device_wait=r1rows[p]['wait_ms'] if p in r1rows else None,
                   rank1_enqueue=r1rows[p]['enqueue_loop_ms'] if p in r1rows else None)
        if h:
            row['ctrl'] = (r1[p]['sent'] - base) * MS                # accepts + handoff + mailbox issue
        else:
            b, x = rb[p], redo[p]
            row.update(gap_to_rollback=(b['sent'] - base) * MS, rollback=w(b), gap_rollback_redo=(x['sent'] - b['rank_completed']) * MS,
                       redo_wall=w(x), redo_busy=x['busy_ms'], redo_layer_body=inside('layer_body', x), redo_token_prep=inside('token_prep', x),
                       redo_export=inside('handoff_export', x), gap_redo_rank1=(r1[p]['sent'] - x['rank_completed']) * MS)
            row['stall'] = (r1[p]['sent'] - base) * MS               # rank 1 idle beyond the hit schedule
        rows.append(row)
    # rank 0's path in each hit cycle: DRAFT(p-1) [sent at rank 1's HALF(p-1) issue] ... speculative HALF(p) returned.
    for row in rows:
        p = row['position']
        if p - 1 in dr:
            row['rank0_path'] = (spec[p]['rank_completed'] - dr[p - 1]['sent']) * MS
            row['rank1_path'] = (E(p - 1) - r1[p - 1]['sent']) * MS
            row['draft_to_spec_gap'] = (spec[p]['sent'] - dr[p - 1]['rank_completed']) * MS
    stamps = [t['completed_monotonic'] for t in d['timing_rows']]
    # rank 0's own per-half rows (decode region): host enqueue time and launch-boundary cancellations
    dec0 = [r for r in r0rows if r['position'] >= first]
    sp0 = [r for r in dec0 if r['speculative']]; co0 = [r for r in dec0 if r['corrected']]
    miss_pos = {p for p, h in hit.items() if not h}
    rank0_rows = dict(speculative_halves=len(sp0), corrected_halves=len(co0),
                      cancelled_speculative_halves=sum(r['cancelled'] for r in sp0),
                      cancelled_launch_counts=sorted(r['launches_issued'] for r in sp0 if r['cancelled']),
                      launches_per_half=sorted(set(r['launches_issued'] for r in sp0 if not r['cancelled'])),
                      speculative_enqueue_loop_ms=dist([r['enqueue_loop_ms'] for r in sp0]),
                      speculative_half_completion_ms=dist([r['half_completion_ms'] for r in sp0]),
                      speculative_at_miss_positions=sum(r['position'] in miss_pos for r in sp0))
    return d, rows, stamps, rank0_rows


def replay(rows, *, rollback=None, snapshot=None, rank1_after_miss=None, cancel_late_on_miss=False, miss_to_hit=None,
           post_miss_draft_free=False, redo_scale=1.0, rank0_delta=0.0, rank1_delta=0.0):
    """Re-time the controller schedule from measured components; with no change it reproduces the measured decode wall.
    The schedule per position p (E = rank-1 completion): start(rank1 HALF(p)) = max(E(p-1), rank0 spec end(p)) + ctrl
    (hit) or + gap + rollback + gap + redo + gap (miss); rank 0's next speculative half ends at
    start(rank1 HALF(p)) + (rank0_path of p+1, measured from DRAFT issue at rank 1's issue)."""
    hits = [r for r in rows if r['hit']]
    ctrl_hit = st.median(r['ctrl'] for r in hits)
    r1_hit = st.median(r['rank1_wall'] for r in hits)
    E = 0.0; c0 = rows[0]['rank0_late']   # first interval: rank 0's spec end relative to E(first-1) as measured
    total = 0.0
    for i, r in enumerate(rows):
        h = r['hit'] or (miss_to_hit is not None and r['position'] in miss_to_hit)
        base = max(E, c0)
        if cancel_late_on_miss and not h: base = E
        if h:
            start1 = base + (r['ctrl'] if r['hit'] else ctrl_hit)
            w1 = (r['rank1_wall'] if r['hit'] else r1_hit) - rank1_delta
        else:
            rbk = r['rollback'] if rollback is None else rollback(r)
            red = r['redo_wall'] * redo_scale - rank0_delta
            start1 = base + r['gap_to_rollback'] + rbk + (r['gap_rollback_redo'] if rollback is None else 0.0) + red + r['gap_redo_rank1']
            w1 = (r['rank1_wall'] if rank1_after_miss is None else rank1_after_miss) - rank1_delta
        newE = start1 + w1
        if i + 1 < len(rows):
            nxt = rows[i + 1]
            path = nxt['rank0_path'] - rank0_delta
            if snapshot is not None: path -= nxt['snapshot'] - snapshot(nxt)
            if post_miss_draft_free and not h: path -= nxt['draft_wall'] + nxt['draft_to_spec_gap']
            c0 = start1 + path
        total += newE - E; E = newE
    return total


def suite_rows(path):
    s = json.load(open(path))
    return [dict(prompt=r['prompt_id'], guesses=r['mtp']['guesses'], hits=r['mtp']['hits'], misses=r['mtp']['misses'],
                 intervals=r['decode_intervals'], wall=r['decode_wall_ms'], tok_s=r['decode_tok_s']) for r in s['rows']], s


def ols(x, y):
    mx, my = st.fmean(x), st.fmean(y)
    sxx = sum((a - mx) ** 2 for a in x); sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    b = sxy / sxx; a = my - b * mx
    ss = sum((b0 - (a + b * a0)) ** 2 for a0, b0 in zip(x, y)); tot = sum((b0 - my) ** 2 for b0 in y)
    return a, b, 1 - ss / tot


def main():
    out = dict(schema='ownrt.research.miss-stall.v1', date='2026-10-29', inputs={}, servers={}, suite={}, candidates={})
    for name, (arm, suite) in SERVERS.items():
        d, rows, stamps, rank0_rows = one(arm)
        out['inputs'][name] = dict(trace=str(sorted(glob.glob(str(arm / 'control/run-*')))[-1]) + '/ranks/native-result.json', suite=str(suite.relative_to(REPO)))
        measured = (stamps[-1] - stamps[0]) * MS
        hits = [r for r in rows if r['hit']]; misses = [r for r in rows if not r['hit']]
        s = dict(decode_wall_ms=round(d['decode_wall_ms'], 3), intervals=len(rows), hits=len(hits), misses=len(misses),
                 interval_hit=dist([r['interval'] for r in hits]), interval_miss=dist([r['interval'] for r in misses]))
        s['miss_penalty_ms'] = round(s['interval_miss']['mean'] - s['interval_hit']['mean'], 4)
        s['miss_share_of_decode'] = round(len(misses) * s['miss_penalty_ms'] / sum(r['interval'] for r in rows), 4)
        s['hit'] = dict(rank1_wall=dist([r['rank1_wall'] for r in hits]), rank1_busy=dist([r['rank1_busy'] for r in hits]),
                        rank0_path=dist([r['rank0_path'] for r in hits if 'rank0_path' in r]),
                        rank1_path=dist([r['rank1_path'] for r in hits if 'rank1_path' in r]),
                        rank0_late=dist([r['rank0_late'] for r in hits]), rank0_later_fraction=round(sum(r['rank0_late'] > 0 for r in hits) / len(hits), 4),
                        ctrl=dist([r['ctrl'] for r in hits]))
        allspec = rows
        s['rank0_speculative_half'] = dict(wall=dist([r['rank0_spec_wall'] for r in allspec]), busy=dist([r['rank0_spec_busy'] for r in allspec]),
                                           snapshot=dist([r['snapshot'] for r in allspec]), token_prep=dist([r['token_prep_spec'] for r in allspec]),
                                           layer_body=dist([r['layer_body_spec'] for r in allspec]), export=dist([r['export_spec'] for r in allspec]),
                                           draft_wall=dist([r['draft_wall'] for r in allspec if r['draft_wall'] is not None]),
                                           draft_to_spec_gap=dist([r['draft_to_spec_gap'] for r in allspec if 'draft_to_spec_gap' in r]))
        if misses:
            s['miss'] = {k: dist([r[k] for r in misses]) for k in ('rank0_late', 'gap_to_rollback', 'rollback', 'gap_rollback_redo', 'redo_wall', 'redo_busy',
                                                                     'redo_layer_body', 'redo_token_prep', 'redo_export', 'gap_redo_rank1', 'stall', 'rank1_wall', 'rank1_busy')}
            s['miss']['rank1_wall_excess_vs_hit_median'] = round(s['miss']['rank1_wall']['median'] - s['hit']['rank1_wall']['median'], 4)
            s['miss']['rank1_device_wait_after_miss'] = med([r['rank1_device_wait'] for r in misses if r['rank1_device_wait'] is not None])
            s['miss']['rank1_device_wait_after_hit'] = med([r['rank1_device_wait'] for r in hits if r['rank1_device_wait'] is not None])
            s['miss']['rank1_enqueue_after_miss'] = med([r['rank1_enqueue'] for r in misses if r['rank1_enqueue'] is not None])
            s['miss']['rank1_enqueue_after_hit'] = med([r['rank1_enqueue'] for r in hits if r['rank1_enqueue'] is not None])
            # Interval of the position after a miss (rank 0 path = deferred draft + spec half against rank 1's slow half)
            after = [r for i, r in enumerate(rows) if i and not rows[i - 1]['hit'] and r['hit']]
            s['post_miss_hit_interval'] = dist([r['interval'] for r in after])
        # Replay: identity, then counterfactuals (ms saved over this request's 63 intervals; per miss / per interval)
        base = replay(rows)
        s['rows'] = rows
        s['rank0_half_rows'] = rank0_rows
        s['replay'] = dict(identity_ms=round(base, 3), measured_e_span_ms=round(sum(r['interval'] for r in rows), 3), stamp_span_ms=round(measured, 3))
        if misses:
            hit_w = st.median(r['rank1_wall'] for r in hits)
            levers = {
                'rollback_free': dict(rollback=lambda r: 0.0),
                'snapshot_free': dict(snapshot=lambda r: 0.0),
                'snapshot_and_rollback_free': dict(rollback=lambda r: 0.0, snapshot=lambda r: 0.0),
                'rank1_post_miss_at_hit_speed': dict(rank1_after_miss=hit_w),
                'cancel_rank0_late_on_miss': dict(cancel_late_on_miss=True),
                'post_miss_draft_free': dict(post_miss_draft_free=True),
                'redo_free_but_rollback_kept': dict(redo_scale=0.0),
                'rank0_half_0p1ms_faster': dict(rank0_delta=0.1),
                'rank1_half_0p1ms_faster': dict(rank1_delta=0.1),
            }
            allhit = {r['position'] for r in misses}
            base_h = replay(rows, miss_to_hit=allhit)
            cf, split = {}, {}
            for k, kw in levers.items():
                v = replay(rows, **kw); cf[k] = v
                vh = replay(rows, miss_to_hit=allhit, **kw)
                per_interval = (base_h - vh) / len(rows)                       # saving of every interval in an all-hit run
                per_miss = ((base - v) - per_interval * len(rows)) / len(misses)  # the rest, per miss
                split[k] = dict(per_interval_ms=round(per_interval, 4), per_miss_ms=round(per_miss, 4))
            cf['all_misses_become_hits'] = base_h
            split['all_misses_become_hits'] = dict(per_interval_ms=0.0, per_miss_ms=round((base - base_h) / len(misses), 4))
            s['all_hit_replay_ms'] = round(base_h, 3)
            s['counterfactual_saving_ms'] = {k: round(base - v, 3) for k, v in cf.items()}
            s['counterfactual_saving_fraction'] = {k: round((base - v) / base, 4) for k, v in cf.items()}
            s['counterfactual_linear'] = split
        out['servers'][name] = s
        # Suite (12 prompts, 512 cap): per-interval time against the miss rate
        sr, sj = suite_rows(suite)
        x = [r['misses'] / r['intervals'] for r in sr]; y = [r['wall'] / r['intervals'] for r in sr]
        a, b, r2 = ols(x, y)
        out['suite'][name] = dict(median_tok_s=round(sj['median_decode_tok_s'], 3), pooled_acceptance=round(sj['pooled_acceptance'], 4),
                                  guesses=sj['guesses'], hits=sj['hits'], misses=sj['guesses'] - sj['hits'],
                                  wall_ms=round(sum(r['wall'] for r in sr), 1), intervals=sum(r['intervals'] for r in sr),
                                  fit_ms_per_interval=dict(hit_interval=round(a, 4), miss_penalty=round(b, 4), r2=round(r2, 4)),
                                  prompts=sr)
    # Pooled over the three tpts servers (the recommended four-card configuration)
    names = ('tpts-r0', 'tpts-r1', 'tpts-r2')
    tp3 = [out['servers'][k] for k in names]; su = [out['suite'][k] for k in names]
    keys = list(tp3[0]['counterfactual_linear'])
    pooled = {
        'miss_penalty_ms_long_prompt': mean([s['miss_penalty_ms'] for s in tp3]),
        'miss_share_long_prompt': mean([s['miss_share_of_decode'] for s in tp3]),
        'counterfactual_linear': {k: dict(per_interval_ms=mean([s['counterfactual_linear'][k]['per_interval_ms'] for s in tp3]),
                                          per_miss_ms=mean([s['counterfactual_linear'][k]['per_miss_ms'] for s in tp3])) for k in keys},
        'counterfactual_saving_fraction_long_prompt': {k: mean([s['counterfactual_saving_fraction'][k] for s in tp3]) for k in keys},
    }
    xs = [r['misses'] / r['intervals'] for s in su for r in s['prompts']]; ys = [r['wall'] / r['intervals'] for s in su for r in s['prompts']]
    a, b, r2 = ols(xs, ys)
    wall = sum(s['wall_ms'] for s in su); mis = sum(s['misses'] for s in su); ints = sum(s['intervals'] for s in su)
    pooled['suite_fit'] = dict(points=len(xs), hit_interval_ms=round(a, 4), miss_penalty_ms=round(b, 4), r2=round(r2, 4),
                               suite_wall_ms=round(wall, 1), suite_intervals=ints, suite_misses=mis,
                               miss_rate=round(mis / ints, 4), mean_interval_ms=round(wall / ints, 4), miss_share=round(mis * b / wall, 4))
    # Suite projection: each server's linear split applied to that server's own 12-prompt suite (interval and miss counts).
    proj = {}
    for k in keys:
        f = []
        for s, u in zip(tp3, su):
            c = s['counterfactual_linear'][k]
            f.append((c['per_interval_ms'] * u['intervals'] + c['per_miss_ms'] * u['misses']) / u['wall_ms'])
        proj[k] = dict(mean=round(st.fmean(f), 4), min=round(min(f), 4), max=round(max(f), 4))
    pooled['suite_projection_fraction'] = proj
    # Pooled component medians (rows of the three servers together)
    R = [r for s in tp3 for r in s['rows']]; H = [r for r in R if r['hit']]; M = [r for r in R if not r['hit']]
    pooled['timeline'] = dict(
        hit=dict(n=len(H), interval=dist([r['interval'] for r in H]), rank1_wall=dist([r['rank1_wall'] for r in H]),
                 rank0_path=dist([r['rank0_path'] for r in H]), rank1_path=dist([r['rank1_path'] for r in H]),
                 rank0_late=dist([r['rank0_late'] for r in H]), rank0_later_fraction=round(sum(r['rank0_late'] > 0 for r in H) / len(H), 4),
                 ctrl=dist([r['ctrl'] for r in H])),
        rank0_spec_half=dict(n=len(R), wall=dist([r['rank0_spec_wall'] for r in R]), busy=dist([r['rank0_spec_busy'] for r in R]),
                             snapshot=dist([r['snapshot'] for r in R]), token_prep=dist([r['token_prep_spec'] for r in R]),
                             layer_body=dist([r['layer_body_spec'] for r in R]), export=dist([r['export_spec'] for r in R]),
                             draft=dist([r['draft_wall'] for r in R]), draft_to_spec_gap=dist([r['draft_to_spec_gap'] for r in R])),
        miss=dict(n=len(M), interval=dist([r['interval'] for r in M]), rank0_late=dist([r['rank0_late'] for r in M]),
                  gap_to_rollback=dist([r['gap_to_rollback'] for r in M]), rollback=dist([r['rollback'] for r in M]),
                  gap_rollback_redo=dist([r['gap_rollback_redo'] for r in M]), redo_wall=dist([r['redo_wall'] for r in M]),
                  redo_busy=dist([r['redo_busy'] for r in M]), redo_token_prep=dist([r['redo_token_prep'] for r in M]),
                  redo_layer_body=dist([r['redo_layer_body'] for r in M]), redo_export=dist([r['redo_export'] for r in M]),
                  gap_redo_rank1=dist([r['gap_redo_rank1'] for r in M]), stall=dist([r['stall'] for r in M]),
                  rank1_wall=dist([r['rank1_wall'] for r in M]), rank1_busy=dist([r['rank1_busy'] for r in M]),
                  rank1_device_wait=dist([r['rank1_device_wait'] for r in M]), rank1_enqueue=dist([r['rank1_enqueue'] for r in M])),
        hit_rank1=dict(rank1_busy=dist([r['rank1_busy'] for r in H]), rank1_device_wait=dist([r['rank1_device_wait'] for r in H]),
                       rank1_enqueue=dist([r['rank1_enqueue'] for r in H])))
    out['pooled_tpts'] = pooled
    for k in out['servers']:
        if not k.startswith('tpts'): out['servers'][k].pop('rows', None)   # per-row data kept for the three tpts servers only
    json.dump(out, open(HERE / 'analysis.json', 'w'), indent=1)
    print(json.dumps(out['pooled_tpts'], indent=1))


if __name__ == '__main__':
    main()
