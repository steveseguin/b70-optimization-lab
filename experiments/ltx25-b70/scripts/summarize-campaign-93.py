#!/usr/bin/env python3
"""Packet 93 campaign summary: per arm exactness, interval, job medians, engine busy per clip,
and the context-hash sentry comparison between arms.

    summarize-campaign-93.py --run <server run dir> --out <data dir> \
        --arm <prefix>:<label> [--arm ...] [--pair <prefixA>:<prefixB> ...]

Reads <out>/<prefix>-throughput.json (run-throughput-fixtures.py), the server's
pipeline receipts, and <out>/engine-busy.jsonl (sample-gpu-engine-busy.py).
Engine window per arm: from the sixth completed prompt's execution_success to
the last (as data/decode-91c/engine-busy-summary.json); busy seconds summed over
samples whose end falls inside it, divided by the prompts completed inside it.
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


def arm_summary(run, out, prefix, label, fixtures, engine):
    tp = load(out / (prefix + '-throughput.json'))
    if tp is None:
        return {'label': label, 'present': False}
    rows = tp['rows']
    verified = [r for r in rows if not r.get('fill') and r.get('reference')]
    ivs = tp.get('intervals_between_distinct_clips_s') or []
    steady = ivs[1:] if len(ivs) > 1 else ivs
    encode, sampler, decode, sentries = [], [], [], {}
    lean = {'connector_computed': [], 'connector_reused': []}
    for r in rows:
        name = r['prompt']
        enc = load(run / ('pipeline-' + name + '.json'))
        if enc and r['index'] >= 2:
            encode.append(enc.get('detail', {}).get('stage_seconds'))
        smp = load(run / ('pipeline-sampler-' + name + '.json'))
        if smp:
            det = smp.get('detail', {})
            if isinstance(det.get('emitted_index'), int) and det['emitted_index'] >= 0:
                sampler.append(det.get('stage_seconds'))
                sentry = det.get('emitted_context_sentry')
                if isinstance(sentry, dict):
                    fx = fixtures[(det['emitted_index'] - tp['index_base']) % len(fixtures)]
                    sentries.setdefault(fx, set()).add((sentry.get('stage_a_context_sha256'),
                                                        sentry.get('stage_b_context_sha256')))
                    for k in lean:
                        lean[k].append(sentry.get(k))
        dec = load(run / ('pipeline-decode-' + name + '.json'))
        if dec:
            det = dec.get('detail', {})
            if isinstance(det.get('emitted_index'), int) and det['emitted_index'] >= 0:
                decode.append(det.get('stage_seconds'))
    t_dones = [r['t_done'] for r in rows if 't_done' in r]
    return {'label': label, 'present': True, 'prompts': len(rows), 'index_base': tp['index_base'],
            'clips_verified': len(verified), 'exact': sum(1 for r in verified if r['exact']),
            'all_exact': tp.get('all_exact'), 'references': sorted({r['reference'] for r in verified}),
            # As the lane's notes report them: median over all intervals between distinct
            # emitted clips, mean over the client's steady intervals (the first excluded).
            'interval_median_s': median(ivs), 'interval_mean_s': mean(steady),
            'interval_median_steady_s': median(steady),
            'encode_job_median_s': median(encode), 'sampler_job_median_s': median(sampler),
            'decode_job_median_s': median(decode),
            'connector_computed_per_clip_median': median(lean['connector_computed']),
            'connector_reused_per_clip_median': median(lean['connector_reused']),
            'engine': engine_window(engine, t_dones),
            'context_sentries': {fx: sorted([list(p) for p in v]) for fx, v in sorted(sentries.items())}}


def compare_sentries(a, b):
    """Per fixture: the (stage a, stage b) context hashes seen in both arms must be one equal pair."""
    sa, sb = a.get('context_sentries', {}), b.get('context_sentries', {})
    common = sorted(set(sa) & set(sb))
    same = [fx for fx in common if len(sa[fx]) == 1 and sa[fx] == sb[fx] and None not in sa[fx][0]]
    return {'fixtures_compared': len(common), 'identical': len(same),
            'differing': [fx for fx in common if fx not in same]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--arm', action='append', default=[])
    ap.add_argument('--pair', action='append', default=[])
    ap.add_argument('--fixtures', type=Path, default=LANE / 'data/stability-01-prereg.json')
    a = ap.parse_args()
    fixtures = [f['id'] for f in json.loads(a.fixtures.read_text())['fixtures']]
    engine = engine_rows(a.out / 'engine-busy.jsonl')
    arms = {}
    for spec in a.arm:
        prefix, _, label = spec.partition(':')
        arms[prefix] = arm_summary(a.run, a.out, prefix, label or prefix, fixtures, engine)
    pairs = {}
    for spec in a.pair:
        x, _, y = spec.partition(':')
        if arms.get(x, {}).get('present') and arms.get(y, {}).get('present'):
            pairs[spec] = compare_sentries(arms[x], arms[y])
    summary = {'schema': 'ltx.campaign-93-summary.v1', 'run': str(a.run), 'arms': arms,
               'context_sentry_pairs': pairs,
               'window_label': 'changes output at rounding level; owner decision pending',
               'engine_samples': len(engine)}
    (a.out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print('%-22s %8s %7s %9s %9s %8s %8s %8s  %s' % ('arm', 'verified', 'exact', 'iv_med', 'iv_mean',
                                                    'enc_med', 'smp_med', 'dec_med', 'ccs s/clip per card'))
    for prefix, s in arms.items():
        if not s.get('present'):
            print('%-22s (not run)' % prefix)
            continue
        eng = s.get('engine') or {}
        per = ' '.join('%s=%.3f' % (c['role'], c['ccs_s_per_clip']) for c in eng.get('cards', {}).values())
        print('%-22s %8s %7s %9s %9s %8s %8s %8s  %s' % (prefix, s['clips_verified'], s['exact'],
              s['interval_median_s'], s['interval_mean_s'], s['encode_job_median_s'],
              s['sampler_job_median_s'], s['decode_job_median_s'], per or '-'))
    for spec, c in pairs.items():
        print('context sentry %s: %d/%d fixtures identical %s' % (spec, c['identical'], c['fixtures_compared'],
                                                                 c['differing'] or ''))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
