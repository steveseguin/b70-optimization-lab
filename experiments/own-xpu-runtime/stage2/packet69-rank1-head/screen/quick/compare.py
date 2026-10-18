#!/usr/bin/env python3
"""CPU-only diagnostic comparison, same-lane controls; never a promotion gate."""
import argparse
import math
from pathlib import Path
import statistics
from types import SimpleNamespace
from jobs import jobs, QUICK
from common import D, HERE, METRICS, read, require, sealed, sha
from conditions import cpu_gate, LANES
from quick_seal import verify


def checked_rate(summary, oracle):
    rows = summary['requests']
    require([r['prompt_id'] for r in rows] == list(D.CHECK.PROMPT_IDS), 'incomplete/reordered suite')
    require(summary.get('cached_tokens') == 0 and summary.get('requested_max_new') == 128
            and summary.get('request_count') == 12, 'not the twelve cold 128-token requests')
    grouped = {}
    exact = summary.get('passed') is True
    for row in rows:
        prompt = row['prompt_id']
        require(row['prompt_class'] == METRICS.PROMPT_CLASSES[prompt], 'prompt class changed')
        require(row.get('cached_tokens') == 0 and row.get('repeat', 1) == 1, 'non-cold/repeated request')
        exact &= (row.get('exact_oracle') is True and row.get('passed') is True
                  and len(row['tokens']) == 128 and row['tokens'] == oracle(prompt)[:128])
        stamps = row['token_timestamps']
        require(len(stamps) == len(row['tokens']) == 128, 'timestamp/token count changed')
        require(all(math.isfinite(t) for t in stamps) and all(b > a for a,b in zip(stamps,stamps[1:])),
                'invalid token timestamps')
        rate = 99 / (stamps[99] - stamps[0])
        require(math.isclose(rate, row['tok_s_1_100_intervals_after_ttft'], rel_tol=1e-10), 'stored rate differs')
        grouped.setdefault(row['prompt_class'], []).append(rate)
    return statistics.median(statistics.median(v) for v in grouped.values()), bool(exact)


def load(row, lane):
    root = HERE / 'evidence' / row['out']
    window, identity = read(root / 'window.json'), read(root / 'identity.json')
    summary = read(root / 'run/summary.json')
    require(window.get('wrapper_seal_sha256') == sha(QUICK / 'wrapper-seal.json'), 'quick wrapper seal differs')
    require(window.get('passed') is True and window.get('device_executed') is True
            and not window.get('child_still_running') and not window.get('child_retained')
            and not window.get('stop_reasons'), 'unfinished/failed screen')
    require(window['identity'] == identity and window['model_lifetimes'] == 1
            and window['lane'] == lane and window['conditions'] == LANES[lane], 'screen identity differs')
    expected = sealed(SimpleNamespace(lineage=Path(row['lineage']), seal=Path(row['seal']),
                      binary=Path(row['binary']), dispatch=Path(row['dispatch']),
                      profile='tp2', timing='token', placement='1'))
    require(all(identity.get(k) == v for k,v in expected.items()), 'job/selection seal differs')
    require(read(root / 'suite-manifest.snapshot.json') == D.oracle_inputs(), 'oracle input manifest differs')
    require(window['oracle_completion_sha256'] == sha(D.ORACLE / 'results/completion.json'), 'oracle binding differs')
    require(summary.get('device_isolation', {}).get('passed') is True, 'device isolation failed')
    coordination = read(root / 'lane-coordination.json')
    require(coordination.get('passed') is True and coordination['reservation']['scope'] == 'lane-' + lane
            and coordination.get('released_before_report') is True and window.get('lease_released') is True, 'lane lease/drain proof differs')
    for name in ('identity.json','run/summary.json','suite-manifest.snapshot.json','run/incident64/receipt.json'):
        require(window['files'].get(name) == sha(root / name), 'finished artifact changed: ' + name)
    oracle = lambda prompt: D.CHECK.token_record(D.ORACLE / 'results' / prompt)
    rate, exact = checked_rate(summary, oracle)
    incident = read(root / 'run/incident64/receipt.json')
    exact &= (summary['incident64'].get('passed') is True and summary['incident64'].get('tokens_compared') == 64
              and incident.get('passed') is True and incident.get('exact_oracle') is True
              and len(incident['tokens']) == 64 and incident['tokens'] == oracle(D.CHECK.PROMPT_IDS[0])[:64])
    return dict(choice=row['choice'], rate=rate, exact=exact, acceptance=statistics.mean(r['acceptance'] for r in summary['requests']), draft_wall_ms=statistics.mean(r['draft_wall_ms'] for r in summary['requests']) if all('draft_wall_ms' in r for r in summary['requests']) else None)


def baseline(rows):
    controls = [r for r in rows if r['choice'] == 'production']
    require(len(controls) == 2 and all(r['exact'] for r in controls), 'both production screens must be exact')
    return statistics.mean(r['rate'] for r in controls)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--jobs-A', type=Path, default=QUICK / 'jobs-A-r3.txt')
    ap.add_argument('--jobs-B', type=Path, default=QUICK / 'jobs-B-r3.txt')
    args = ap.parse_args()
    cpu_gate()
    verify()
    valid = True
    for lane in ('A', 'B'):
        try:
            rows = [load(row, lane) for row in jobs(getattr(args, 'jobs_' + lane), lane)]
            control = baseline(rows)
            print(f'Lane {lane}: production mean {control:.6f} tok/s')
            print('selection          class-balanced tok/s    vs production    all-13-exact    acceptance')
            for row in rows:
                delta = 100 * (row['rate']/control - 1)
                print(f"{row['choice']:18} {row['rate']:>20.6f} {delta:>+15.2f}%    {'PASS' if row['exact'] else 'FAIL'}    {row['acceptance']:.4f}")
                valid &= row['exact']
        except (OSError, ValueError, KeyError, TypeError) as error:
            print(f'Lane {lane}: INCOMPLETE/REFUSED: {error}')
            valid = False
    print('Diagnostic 128-token screen only; 99/(t100-t1), median within class then across classes.')
    return 0 if valid else 1


if __name__ == '__main__':
    raise SystemExit(main())
