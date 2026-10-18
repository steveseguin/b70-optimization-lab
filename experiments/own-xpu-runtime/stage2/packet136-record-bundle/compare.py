"""Same-lane composition screen, never a record or promotion attestation."""
import json
import math
import statistics
from types import SimpleNamespace
from screen_jobs import P as HERE, ORDER, output, view, verify, sha, jobs
from bootstrap import install, WRAPPER
install()
from common import D, METRICS, read, require, sealed
from conditions import LANES

def checked_requests(summary, oracle):
    rows = summary['requests']
    require([r['prompt_id'] for r in rows] == list(D.CHECK.PROMPT_IDS), 'complete ordered suite required')
    require(summary.get('cached_tokens') == 0 and summary.get('requested_max_new') == 128
            and summary.get('request_count') == 12, 'twelve cold 128-token requests required')
    require(summary.get('passed') is True and summary.get('kv_dtype') == 'BF16', 'summary/precision failed')
    grouped, acceptance, counts = {}, [], []
    for r in rows:
        prompt = r['prompt_id']
        require(r['prompt_class'] == METRICS.PROMPT_CLASSES[prompt], 'prompt class changed')
        require(r.get('cached_tokens') == 0 and r.get('repeat', 1) == 1, 'cached/repeated request')
        require(r.get('passed') is True and r.get('exact_oracle') is True and
                len(r['tokens']) == 128 and r['tokens'] == oracle(prompt)[:128], 'target output mismatch')
        ts = r['token_timestamps']
        require(len(ts) == 128 and all(math.isfinite(t) for t in ts)
                and all(b > a for a, b in zip(ts, ts[1:])), 'invalid timestamps')
        rate = 99 / (ts[99] - ts[0])
        require(math.isclose(rate, r['tok_s_1_100_intervals_after_ttft'], rel_tol=1e-10), 'stored rate differs')
        grouped.setdefault(r['prompt_class'], []).append(rate)
        hits, guesses = r['hits'], r['guesses']
        require(type(hits) is int and type(guesses) is int and 0 <= hits <= guesses and guesses > 0,
                'invalid acceptance counts')
        require(math.isclose(r['acceptance'], hits / guesses, rel_tol=1e-10), 'acceptance differs from counts')
        acceptance.append(hits / guesses)
        counts.append(dict(prompt_id=prompt, hits=hits, guesses=guesses))
    return dict(rate=statistics.median(statistics.median(v) for v in grouped.values()),
                acceptance=statistics.mean(acceptance), acceptance_counts=counts)

def load(job):
    lane=job['lane'];index=job['index']
    root=output(job) if job['mode']=='grid' else WRAPPER/'evidence'/f'p103-{lane}-confirm-{index}'
    lineage=view(job['choice'])
    window, identity = read(root / 'window.json'), read(root / 'identity.json')
    require(window.get('passed') is True and window.get('device_executed') is True
            and not window.get('child_still_running') and not window.get('child_retained')
            and not window.get('stop_reasons'), 'unfinished/failed screen')
    require(window['identity'] == identity and window['model_lifetimes'] == 1
            and window['lane'] == identity['lane'] == lane
            and window['conditions'] == identity['conditions'] == LANES[lane], 'same lane identity required')
    require(window['wrapper_seal_sha256'] == sha(WRAPPER / 'placement-validation/wrapper-seal.json'), 'wrapper differs')
    expected = sealed(SimpleNamespace(lineage=lineage, seal=lineage / 'screen-seal.json',
                      binary=None, dispatch=None, profile='tp2', timing='token', placement='1'))
    require(all(identity.get(k) == v for k, v in expected.items()), 'composition identity differs')
    require(read(root / 'suite-manifest.snapshot.json') == D.oracle_inputs(), 'oracle manifest differs')
    require(window['oracle_completion_sha256'] == sha(D.ORACLE / 'results/completion.json'), 'oracle binding differs')
    for leaf in ('identity.json', 'run/summary.json', 'suite-manifest.snapshot.json', 'run/incident64/receipt.json'):
        require(window['files'].get(leaf) == sha(root / leaf), 'finished artifact changed: ' + leaf)
    coordination = read(root / 'lane-coordination.json')
    require(coordination.get('passed') is True and coordination['reservation']['scope'] == 'lane-'+lane
            and coordination.get('released_before_report') is True and window.get('lease_released') is True,
            'lease/drain proof required')
    summary = read(root / 'run/summary.json')
    require(summary.get('device_isolation', {}).get('passed') is True, 'device isolation failed')
    oracle = lambda prompt: D.CHECK.token_record(D.ORACLE / 'results' / prompt)
    result = checked_requests(summary, oracle)
    incident = read(root / 'run/incident64/receipt.json')
    require(summary['incident64'].get('passed') is True and summary['incident64'].get('tokens_compared') == 64
            and summary['incident64']['receipt_sha256'] == sha(root / 'run/incident64/receipt.json')
            and incident.get('passed') is True and incident.get('exact_oracle') is True
            and len(incident['tokens']) == 64 and incident['tokens'] == oracle(D.CHECK.PROMPT_IDS[0])[:64],
            'incident64 exactness failed')
    return dict(index=index, choice=job['choice'], exact=True, exact_count=13, lane=lane, all_13_exact=True, output=str(root),
                boot_id=window['boot_id'], started_utc_ns=window['started_utc_ns'], finished_utc_ns=window['finished_utc_ns'],
                window_sha256=sha(root / 'window.json'), **result)

def compare(rows, order=ORDER):
    require([r['choice'] for r in rows] == list(order), 'complete ordered matched screen required')
    require(all(r['all_13_exact'] for r in rows), 'all thirteen checks must pass in every screen')
    require(len({r['boot_id'] for r in rows}) == 1 and len({r['lane'] for r in rows}) == 1, 'matched screens require the same boot')
    require(all(r['started_utc_ns'] < r['finished_utc_ns'] for r in rows)
            and all(a['finished_utc_ns'] < b['started_utc_ns'] for a, b in zip(rows, rows[1:])),
            'screens must run in control/A/B/control order without overlap')
    require(all(r['exact'] and r['exact_count']==13 for r in rows), '13/13 exact required')
    require(rows[0]['acceptance_counts']==rows[-1]['acceptance_counts'], 'control acceptance changed')
    # Prefix proposals differ; target tokens remain exact. Candidate determinism is gated by the record chain.
    control_rate = statistics.mean(r['rate'] for r in (rows[0], rows[-1]))
    control_acceptance = statistics.mean(r['acceptance'] for r in (rows[0], rows[-1]))
    require(control_rate > 0 and all(math.isfinite(r['rate']) and r['rate'] > 0 for r in rows), 'invalid rates')
    return dict(lane=rows[0]['lane'], diagnostic=True, submission_eligible=False, all_13_exact=True,
                metric='median of prompt-class medians; 99 intervals between token events 1 and 100',
                control_mean_tok_s=control_rate, control_mean_acceptance=control_acceptance,
                control_drift_percent=100 * (rows[-1]['rate'] / rows[0]['rate'] - 1),
                screens=rows, candidates=[dict(choice=r['choice'], tok_s=r['rate'],
                    gain_percent=100 * (r['rate'] / control_rate - 1),
                    faster_than_control_mean=r['rate'] > control_rate,
                    faster_than_both_controls=r['rate'] > max(rows[0]['rate'], rows[-1]['rate']),
                    acceptance=r['acceptance'], acceptance_delta_percentage_points=100 * (r['acceptance'] - control_acceptance))
                    for r in rows[1:-1]])

if __name__ == '__main__':
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('--lane',choices=('A','B'),required=True);a=ap.parse_args();verify()
    print(json.dumps(compare([load(j) for j in jobs(a.lane)]),indent=2))
