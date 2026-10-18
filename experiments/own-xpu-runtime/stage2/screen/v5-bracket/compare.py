"""V4 request-schema adapter; bracket views share one explicitly labeled lifetime."""
import json, math, statistics
from pathlib import Path
from common import D, METRICS, read, require, sha, save, summary, label

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

def finish_bracket(output, window, identity, coordination):
    proof = read(output / 'run/bracket-inputs.json')
    views = proof['views']
    require(proof.get('passed') is True and len(views) == len(identity['bracket']['views']), 'incomplete bracket')
    oracle = lambda prompt: D.CHECK.token_record(D.ORACLE / 'results' / prompt)
    isolation = read(output / 'run/device-isolation.json')
    require(isolation.get('passed') is True, 'bracket isolation failed')
    rows, descriptors = [], None
    for index, view in enumerate(views):
        selection = identity['bracket']['views'][index]
        require(view['index'] == index and view['choice'] == selection['choice'] and
                view['selection_sha256'] == selection['selection_sha256'], 'view order/identity differs')
        dest = output / 'run/views' / f'{index:02d}-{view["choice"]}'
        require(view['output'] == str(dest), 'view output escape')
        require(view['passed'] is True and view['started_utc_ns'] < view['finished_utc_ns'], 'failed view')
        if index: require(views[index-1]['finished_utc_ns'] < view['started_utc_ns'], 'overlapping views')
        boundary = []
        for rank in (0, 1):
            r = read(dest / 'boundary' / f'boundary-rank{rank}.json')
            require(r == view['boundary'][rank] and r['passed'] is True and r['total_reset'] is True and
                    r['cached_tokens'] == 0 and r['weight_uploads_after_load'] == 0 and
                    r['selection_sha256'] == selection['selection_sha256'], 'boundary not proven')
            boundary.append((r['arena_descriptors_sha256'], r['weight_descriptors_sha256']))
        if descriptors is None: descriptors = boundary
        require(boundary == descriptors, 'view loaded arena differs')
        incident = read(dest / 'incident64/receipt.json')
        require(view['incident64']['receipt_sha256'] == sha(dest / 'incident64/receipt.json') and
                incident['tokens'] == oracle(D.CHECK.PROMPT_IDS[0])[:64] and incident['cached_tokens'] == 0 and
                incident['passed'] is True and incident['exact_oracle'] is True, 'incident64 differs')
        result = summary(view['requests'], view['incident64'], 'tp2')
        result.update(placement=identity['placement'], lane=identity['lane'], conditions=identity['conditions'],
                      timing='token', device_isolation=isolation, bracket_view=index, shared_model_lifetime=True)
        metrics = checked_requests(result, oracle)
        save(dest / 'summary.json', result)
        save(dest / 'identity.json', dict(identity, view=selection, bracket_view=index))
        rows.append(dict(index=index, choice=view['choice'], all_13_exact=True, exact_count=13,
                         lane=identity['lane'], boot_id=window['boot_id'], output=str(dest),
                         started_utc_ns=view['started_utc_ns'], finished_utc_ns=view['finished_utc_ns'], **metrics))
    controls = [r['rate'] for r in rows if r['choice'] == 'control']
    drift = 100 * (max(controls) / min(controls) - 1)
    result = label(dict(schema='own-runtime.bracket.summary.v1', passed=True, kind=proof['kind'],
                        model_lifetimes=1, target_loads=1, draft_loads=1, teardown_count=1,
                        views=rows, all_13_exact=True, control_drift_percent=drift,
                        control_drift_limit_percent=3.0,
                        measured_wall_seconds=(__import__('time').time_ns()-window['started_utc_ns'])/1e9,
                        device_wall_savings_seconds=None,
                        savings_status='matched v4 wall reference required; no inferred measured saving'))
    if proof['kind'] == 'smoke':
        result['timing_equal_within_control_drift'] = drift <= 3.0
        result['passed'] = drift <= 3.0
    else:
        result['candidates'] = [dict(index=r['index'], rate=r['rate'],
             faster_than_all_controls=r['rate'] > max(controls),
             gain_percent=100*(r['rate']/statistics.mean(controls)-1)) for r in rows if r['choice']=='candidate']
    save(output / 'bracket-summary.json', result)
    require(result['passed'], 'A/A timing drift exceeds preregistered 3% control bound')
    return result

def load(output):
    """Read shared-lifetime views without impersonating fresh v4 server windows."""
    output=Path(output)
    window=read(output/'window.json')
    require(window.get('passed') is True and window.get('device_executed') is True and window.get('device_complete') is True and
            window.get('lease_released') is True and not window.get('child_still_running') and
            not window.get('stop_reasons'), 'bracket device phase incomplete')
    require(read(output/'run/teardown.json').get('drained') is True, 'teardown unproven')
    for leaf,digest in window['files'].items():
        path=(output/leaf).resolve()
        require(path.is_relative_to(output.resolve()) and sha(path)==digest, 'changed bracket artifact: '+leaf)
    result=read(output/'bracket-summary.json')
    require(result['passed'] is True and result['model_lifetimes']==1, 'bracket result failed')
    identity=read(output/'identity.json')
    require(window['identity']==identity, 'bracket window identity differs')
    from common import HERE
    require(window['wrapper_seal_sha256']==sha(HERE/'placement-validation/wrapper-seal.json'), 'wrapper seal changed')
    require(window['oracle_completion_sha256']==sha(D.ORACLE/'results/completion.json'), 'oracle changed')
    require(read(output/'suite-manifest.snapshot.json')==D.oracle_inputs(), 'oracle prompt suite changed')
    oracle=lambda prompt:D.CHECK.token_record(D.ORACLE/'results'/prompt)
    require(len(result['views'])==len(identity['bracket']['views']), 'missing bracket views')
    for index,row in enumerate(result['views']):
        dest=output/'run/views'/f'{index:02d}-{row["choice"]}'
        checked=checked_requests(read(dest/'summary.json'),oracle)
        require(checked['rate']==row['rate'] and checked['acceptance_counts']==row['acceptance_counts'], 'changed view metrics')
        incident=read(dest/'incident64/receipt.json')
        require(incident['tokens']==oracle(D.CHECK.PROMPT_IDS[0])[:64] and incident['cached_tokens']==0, 'changed incident')
    return result

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('output',type=Path);args=parser.parse_args()
    print(json.dumps(load(args.output),indent=2))
