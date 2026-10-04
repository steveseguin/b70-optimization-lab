#!/usr/bin/env python3
"""Packet 96 campaign summary (summarize-campaign-93.py is left untouched).

    summarize-campaign-96.py --run <server run dir> --out <data dir> --batch B \
        --arm <prefix>:<label> [--arm ...] [--pair <prefixA>:<prefixB> ...]

Per arm, the packet 95 columns: clips verified and exact, interval median and mean
(stalled intervals excluded), encode/sampler/decode job medians, sampler clips in
flight (time-weighted mean and maximum), compute-engine busy seconds per clip per
card. Added: the reference set each arm was checked against, sampler job seconds per
batch job and per clip (job seconds / B), batch jobs in flight, and the decode queue
depth after each decode submit. A sampler receipt's context sentry belongs to the clip
that receipt released (detail.emitted_index), which decode emits later from another
prompt; it is mapped to its fixture through the arm's own fixture order, never through
the emitting prompt's row and never through index mod 10 (review finding 1).

Fails (exit 3) when any requested arm or pair is absent or a required proof receipt
(--require-proof) is missing or did not pass (review findings 2 and 6).

Pairs: the context-hash sentry gate (93b): each fixture must show exactly one
(stage a, stage b) pair of per-clip context hashes, equal between the two arms.
Also folds in the batch reference closeness report and the proof results if present.
Writes <out>/summary.json. Reads files only.
"""
import argparse
import json
import statistics
from pathlib import Path

LANE = Path(__file__).resolve().parents[1]
CARD_ROLE = {'0000:23:00.0': 'xpu:0', '0000:27:00.0': 'xpu:1', '0000:43:00.0': 'xpu:2', '0000:47:00.0': 'xpu:3'}
SKIP_PROMPTS = 6


def median(xs):
    xs = [x for x in xs if isinstance(x, (int, float))]
    return round(statistics.median(xs), 4) if xs else None


def mean(xs):
    xs = [x for x in xs if isinstance(x, (int, float))]
    return round(sum(xs) / len(xs), 4) if xs else None


def load(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return None


def engine_rows(path):
    rows = []
    if path.is_file():
        for line in path.read_text().splitlines():
            try:
                rows.append(json.loads(line))
            except ValueError:
                pass
    return rows


def engine_window(rows, t_dones):
    done = sorted(t_dones)
    if len(done) <= SKIP_PROMPTS:
        return None
    start, end = done[SKIP_PROMPTS - 1], done[-1]
    prompts = sum(1 for t in done if start < t <= end)
    cards = {}
    for r in rows:
        if not (start < r.get('t', 0) <= end):
            continue
        for pdev, c in r.get('cards', {}).items():
            acc = cards.setdefault(pdev, {'ccs_busy_s': 0.0, 'bcs_busy_s': 0.0})
            acc['ccs_busy_s'] += c.get('ccs_busy_s', 0.0)
            acc['bcs_busy_s'] += c.get('bcs_busy_s', 0.0)
    out = {'window_s': round(end - start, 2), 'prompts': prompts, 'cards': {}}
    for pdev, acc in sorted(cards.items()):
        out['cards'][pdev] = {'role': CARD_ROLE.get(pdev),
                              'ccs_s_per_clip': round(acc['ccs_busy_s'] / max(1, prompts), 4),
                              'bcs_s_per_clip': round(acc['bcs_busy_s'] / max(1, prompts), 4),
                              'ccs_util': round(acc['ccs_busy_s'] / max(1e-9, end - start), 4)}
    out['total_ccs_s_per_clip'] = round(sum(c['ccs_s_per_clip'] for c in out['cards'].values()), 4)
    return out


def load_stalls(run):
    stalls = []
    p = Path(run) / 'host-stalls.jsonl'
    if p.is_file():
        for line in p.read_text().splitlines():
            try:
                e = json.loads(line)
                stalls.append((float(e['window_unix'][0]), float(e['window_unix'][1]), e.get('duration_s')))
            except (ValueError, KeyError, TypeError):
                pass
    return stalls


def stall_filtered_intervals(rows, stalls):
    distinct = sorted((r for r in rows if not r.get('fill') and r.get('emitted_index', -1) >= 0 and 't_done' in r),
                      key=lambda r: r['t_done'])
    kept, dropped = [], 0
    for a, b in zip(distinct, distinct[1:]):
        if any(s <= b['t_done'] and e >= a['t_done'] for s, e, _d in stalls):
            dropped += 1
        else:
            kept.append(round(b['t_done'] - a['t_done'], 3))
    return kept, dropped


def in_flight(spans, start_index=5):
    """Time-weighted mean and maximum of overlapping spans, from the sixth span's start."""
    if len(spans) <= start_index + 1:
        return None
    spans = sorted(spans)
    start, end = spans[start_index][0], max(b for _a, b in spans)
    events = sorted([(a, 1) for a, _b in spans] + [(b, -1) for _a, b in spans])
    level, last, area, peak = 0, None, 0.0, 0
    for t, d in events:
        if last is not None and t > start:
            lo = max(last, start)
            if t > lo:
                area += level * (min(t, end) - lo)
        level += d
        peak = max(peak, level)
        last = t
    return {'mean': round(area / max(1e-9, end - start), 3), 'max': peak, 'spans': len(spans)}


def sampler_jobs(run, rows, batch):
    """One entry per sampler job that emitted a clip of this arm: (start, end, seconds)."""
    jobs = {}
    for r in rows:
        smp = load(Path(run) / ('pipeline-sampler-' + r['prompt'] + '.json'))
        det = (smp or {}).get('detail', {})
        e, sec = det.get('emitted_index'), det.get('stage_seconds')
        if not isinstance(e, int) or e < 0 or not isinstance(sec, (int, float)):
            continue
        key = det.get('batch_job', e) if batch > 1 else e
        mk = load(Path(run) / ('pipeline-done-sample-%d.json' % e))
        if mk and isinstance(mk.get('finished_unix'), (int, float)):
            jobs[key] = (mk['finished_unix'] - sec, mk['finished_unix'], sec)
    return jobs


def arm_summary(run, out, prefix, label, batch, engine):
    tp = load(out / (prefix + '-throughput.json'))
    if tp is None:
        return {'label': label, 'present': False}
    rows = tp['rows']
    verified = [r for r in rows if not r.get('fill') and r.get('reference')]
    stalls = load_stalls(run)
    if stalls:
        ivs, stall_excluded = stall_filtered_intervals(rows, stalls)
    else:
        ivs, stall_excluded = tp.get('intervals_between_distinct_clips_s') or [], 0
    steady = ivs[1:] if len(ivs) > 1 else ivs
    encode, decode, decode_pending, sentries = [], [], [], {}
    lean = {'connector_computed': [], 'connector_reused': []}
    order = tp.get('fixture_order') or []
    for r in rows:
        name = r['prompt']
        enc = load(run / ('pipeline-' + name + '.json'))
        if enc and r['index'] >= 2:
            encode.append(enc.get('detail', {}).get('stage_seconds'))
        smp = load(run / ('pipeline-sampler-' + name + '.json'))
        if smp:
            det = smp.get('detail', {})
            if isinstance(det.get('emitted_index'), int) and det['emitted_index'] >= 0:
                sentry = det.get('emitted_context_sentry')
                rel = det['emitted_index'] - tp['index_base']
                fx = order[rel] if 0 <= rel < len(order) else None
                if isinstance(sentry, dict) and fx:
                    sentries.setdefault(fx, set()).add((sentry.get('stage_a_context_sha256'),
                                                        sentry.get('stage_b_context_sha256')))
                    for k in lean:
                        lean[k].append(sentry.get(k))
        dec = load(run / ('pipeline-decode-' + name + '.json'))
        if dec:
            det = dec.get('detail', {})
            if isinstance(det.get('emitted_index'), int) and det['emitted_index'] >= 0:
                decode.append(det.get('stage_seconds'))
        if isinstance(r.get('decode_pending'), int):
            decode_pending.append(r['decode_pending'])
    jobs = sampler_jobs(run, rows, batch)
    job_seconds = [v[2] for v in jobs.values()]
    flight = in_flight([(a, b) for a, b, _s in jobs.values()])
    if flight is not None:
        flight = {'jobs_mean': flight['mean'], 'jobs_max': flight['max'], 'jobs': flight['spans'],
                  'clips_mean': round(flight['mean'] * batch, 3), 'clips_max': flight['max'] * batch}
    t_dones = [r['t_done'] for r in rows if 't_done' in r]
    return {'label': label, 'present': True, 'prompts': len(rows), 'index_base': tp['index_base'],
            'order': tp.get('order'), 'batch': tp.get('batch'),
            'references_checked_against': tp.get('references_from'),
            'clips_emitted': len([r for r in rows if not r.get('fill') and r.get('emitted_index', -1) >= 0]),
            'clips_verified': len(verified), 'exact': sum(1 for r in verified if r['exact']),
            'all_exact': tp.get('all_exact'), 'references': sorted({r['reference'] for r in verified}),
            'interval_median_s': median(ivs), 'interval_mean_s': mean(steady),
            'interval_median_steady_s': median(steady),
            'intervals_excluded_for_host_stall': stall_excluded,
            'host_stall_durations_s_in_run': [d for _s, _e, d in stalls],
            'sampler_in_flight': flight,
            'encode_job_median_s': median(encode),
            'sampler_job_median_s': median(job_seconds),
            'sampler_job_median_per_clip_s': None if median(job_seconds) is None else round(median(job_seconds) / batch, 4),
            'decode_job_median_s': median(decode),
            'decode_queue_depth_median': median(decode_pending),
            'decode_queue_depth_max': max(decode_pending) if decode_pending else None,
            'connector_computed_per_job_median': median(lean['connector_computed']),
            'connector_reused_per_job_median': median(lean['connector_reused']),
            'engine': engine_window(engine, t_dones),
            'context_sentries': {fx: sorted([list(p) for p in v]) for fx, v in sorted(sentries.items())}}


def compare_sentries(a, b, fixtures):
    sa, sb = a.get('context_sentries', {}), b.get('context_sentries', {})
    problems = []
    for fx in fixtures:
        if fx not in sa or fx not in sb:
            problems.append('%s: missing in %s' % (fx, 'both' if fx not in sa and fx not in sb
                                                  else ('first arm' if fx not in sa else 'second arm')))
            continue
        for label, s in (('first', sa[fx]), ('second', sb[fx])):
            if len(s) != 1 or None in s[0]:
                problems.append('%s: %s arm has %d hash pairs or a null hash' % (fx, label, len(s)))
        if sa[fx] != sb[fx]:
            problems.append('%s: context hashes differ between the arms' % fx)
    same = [fx for fx in fixtures if not any(p.startswith(fx + ':') for p in problems)]
    return {'fixtures_expected': len(fixtures), 'identical': len(same), 'passed': not problems, 'problems': problems}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--batch', required=True, type=int)
    ap.add_argument('--arm', action='append', default=[])
    ap.add_argument('--pair', action='append', default=[])
    ap.add_argument('--fixtures', type=Path, default=LANE / 'data/stability-01-prereg.json')
    ap.add_argument('--require-proof', action='append', default=[],
                    help='proof receipt file name in --out that must exist and have passed')
    a = ap.parse_args(argv)
    fixtures = [f['id'] for f in json.loads(a.fixtures.read_text())['fixtures']]
    engine = engine_rows(a.out / 'engine-busy.jsonl')
    arms = {}
    for spec in a.arm:
        prefix, _, label = spec.partition(':')
        arms[prefix] = arm_summary(a.run, a.out, prefix, label or prefix, a.batch, engine)
    pairs = {}
    for spec in a.pair:
        x, _, y = spec.partition(':')
        if arms.get(x, {}).get('present') and arms.get(y, {}).get('present'):
            pairs[spec] = compare_sentries(arms[x], arms[y], fixtures)
    closeness = load(a.out / ('batch%d-reference-vs-w93c.json' % a.batch)) if a.batch > 1 else None
    proofs = {p.name: load(p) for p in sorted(a.out.glob('proof-*.json'))}
    missing = ['arm %s' % k for k, v in arms.items() if not v.get('present')]
    missing += ['pair %s' % spec for spec in a.pair if spec not in pairs]
    for name in a.require_proof:
        rec = proofs.get(name)
        if not isinstance(rec, dict) or rec.get('passed') is not True:
            missing.append('proof %s %s' % (name, 'missing' if rec is None else 'did not pass'))
    gate_ok = bool(pairs) and all(p['passed'] for p in pairs.values()) and not missing
    summary = {'schema': 'ltx.campaign-96-summary.v1', 'run': str(a.run), 'batch': a.batch, 'arms': arms,
               'context_sentry_pairs': pairs, 'context_sentry_gate_passed': gate_ok,
               'missing_or_failed': missing,
               'batch_reference_closeness_vs_w93c': None if closeness is None else {
                   'accepted': closeness.get('accepted'), 'status': closeness.get('status'),
                   'table': closeness.get('table'), 'rows': closeness.get('closeness_vs_w93c')},
               'proofs': proofs,
               'reference_sets': {k: v.get('references_checked_against') for k, v in arms.items() if v.get('present')},
               'label': ('batch 1: the packet 95 path, checked against the w93c references' if a.batch == 1 else
                         'batch %d: changes output at rounding level versus batch 1; checked against the '
                         'stability-01-b%d references (owner decides adoption)' % (a.batch, a.batch)),
               'engine_samples': len(engine)}
    (a.out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    head = ('%-20s %-14s %8s %6s %8s %8s %7s %8s %9s %7s %7s %9s  %s' %
            ('arm', 'references', 'verified', 'exact', 'iv_med', 'iv_mean', 'enc_med', 'smp_job', 'smp/clip',
             'dec_med', 'decQ', 'clips_fl', 'ccs s/clip per card'))
    print(head)
    for prefix, s in arms.items():
        if not s.get('present'):
            print('%-20s (not run)' % prefix)
            continue
        eng = s.get('engine') or {}
        per = ' '.join('%s=%.3f' % (c['role'], c['ccs_s_per_clip']) for c in eng.get('cards', {}).values())
        ref = s.get('references_checked_against') or 'none'
        ref = Path(ref).name.replace('stability-01-', '').replace('-prereg.json', '') if ref != 'none' else ref
        fl = s.get('sampler_in_flight') or {}
        print('%-20s %-14s %8s %6s %8s %8s %7s %8s %9s %7s %7s %9s  %s' % (
            prefix[-20:], ref, s['clips_verified'], s['exact'], s['interval_median_s'], s['interval_mean_s'],
            s['encode_job_median_s'], s['sampler_job_median_s'], s['sampler_job_median_per_clip_s'],
            s['decode_job_median_s'], s['decode_queue_depth_median'],
            '%s/%s' % (fl.get('clips_mean'), fl.get('clips_max')) if fl else '-', per or '-'))
    for prefix, st in arms.items():
        if st.get('present') and st.get('intervals_excluded_for_host_stall'):
            print('%s: %d intervals excluded for known host stalls %s (exactness checked for every clip)'
                  % (prefix, st['intervals_excluded_for_host_stall'], st['host_stall_durations_s_in_run']))
    for spec, c in pairs.items():
        print('context sentry %s: %d/%d fixtures identical %s' % (spec, c['identical'], c['fixtures_expected'],
                                                                 '; '.join(c['problems'][:5])))
    for name, p in proofs.items():
        if isinstance(p, dict):
            print('%s: %s (%s/%s exact)' % (name, 'PASSED' if p.get('passed') else 'FAILED',
                                            p.get('clips_exact'), p.get('clips_checked')))
    if closeness is not None:
        print('batch-%d references vs w93c (a different take, not a gate; %s):' % (a.batch, closeness.get('status')))
        for line in closeness.get('table') or []:
            print('  ' + line)
    if missing:
        print('SUMMARY INCOMPLETE OR A PROOF FAILED: ' + '; '.join(missing))
        return 3
    if not gate_ok:
        print('CONTEXT SENTRY GATE FAILED')
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
