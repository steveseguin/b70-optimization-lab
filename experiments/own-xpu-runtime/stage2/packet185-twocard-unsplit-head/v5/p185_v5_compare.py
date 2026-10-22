"""V4 request-schema adapter; packet185: one fresh load and one view per queue row."""
import hashlib, json, math, statistics
from pathlib import Path
from common import D, METRICS, read, require, sha, save, summary, label

def proposal_identity(destination):
    """Compare actual proposals, not only aggregate acceptance or target tokens."""
    traces=list(Path(destination).glob('rank1/draft-rows.jsonl'))
    require(len(traces)==1,'rank1 draft proposal trace missing')
    rows=[json.loads(line) for line in traces[0].read_text().splitlines() if line.strip()]
    keys=('draft_position','confirmed_token','guess','head')
    values=[[r[k] for k in keys] for r in rows]
    require(values and any(r[3] for r in values),'draft proposal sequence empty')
    return dict(rows=len(values),sha256=hashlib.sha256(json.dumps(values,separators=(',',':')).encode()).hexdigest())

def class_copies(output,identity):
    # Packet149 has no copied class bank. Scratch is not model state.
    return []

def checked_requests(summary, oracle, cap=64):
    require(cap in (64,128), 'unsupported diagnostic cap')
    rows = summary['requests']
    require([r['prompt_id'] for r in rows] == list(D.CHECK.PROMPT_IDS), 'complete ordered suite required')
    require(summary.get('cached_tokens') == 0 and summary.get('requested_max_new') == cap
            and summary.get('request_count') == 12, 'twelve cold 64-token diagnostic requests required')
    require(summary.get('passed') is True and summary.get('kv_dtype') == 'BF16', 'summary/precision failed')
    grouped, acceptance, counts = {}, [], []
    for r in rows:
        prompt = r['prompt_id']
        require(r['prompt_class'] == METRICS.PROMPT_CLASSES[prompt], 'prompt class changed')
        require(r.get('cached_tokens') == 0 and r.get('repeat', 1) == 1, 'cached/repeated request')
        require(r.get('passed') is True and r.get('exact_oracle') is True and
                len(r['tokens']) == cap and r['tokens'] == oracle(prompt)[:cap], 'target output mismatch')
        ts = r['token_timestamps']
        require(len(ts) == cap and all(math.isfinite(t) for t in ts)
                and all(b > a for a, b in zip(ts, ts[1:])), 'invalid timestamps')
        rate = (min(cap,100)-1) / (ts[min(cap,100)-1] - ts[0])
        require(rate>0, 'invalid diagnostic rate')
        grouped.setdefault(r['prompt_class'], []).append(rate)
        hits, guesses = r['hits'], r['guesses']
        require(type(hits) is int and type(guesses) is int and 0 <= hits <= guesses and guesses > 0,
                'invalid acceptance counts')
        require(math.isclose(r['acceptance'], hits / guesses, rel_tol=1e-10), 'acceptance differs from counts')
        acceptance.append(hits / guesses)
        counts.append(dict(prompt_id=prompt, hits=hits, guesses=guesses))
    return dict(rate=statistics.median(statistics.median(v) for v in grouped.values()),
                acceptance=statistics.mean(acceptance), acceptance_counts=counts)

def row_output(index, lane):
    """Registered output of packet185 fresh-load view row `index` on `lane`."""
    from common import HERE
    from bracket_config import VIEWS
    return HERE / 'evidence' / f'device-view{index}-{VIEWS[index]}-{lane}-p185'

def finish_bracket(output, window, identity, coordination):
    """Packet185 row report: one fresh load, one view; the fifth row also decides (s185_decision)."""
    proof = read(output / 'run/bracket-inputs.json')
    views = proof['views']
    config = identity['bracket']
    require(proof.get('passed') is True and proof['kind'] == 'view' == config['kind'] and len(views) == 1 == len(config['views']),
            'incomplete fresh-load view row')
    oracle = lambda prompt: D.CHECK.token_record(D.ORACLE / 'results' / prompt)
    isolation = read(output / 'run/device-isolation.json')
    require(isolation.get('passed') is True, 'view isolation failed')
    view, selection, index = views[0], config['views'][0], config['view_index']
    require(view['index'] == 0 and view['choice'] == selection['choice'] and
            view['selection_sha256'] == selection['selection_sha256'], 'view identity differs')
    dest = output / 'run/views' / f'00-{view["choice"]}'
    require(view['output'] == str(dest) and view['passed'] is True and view['started_utc_ns'] < view['finished_utc_ns'], 'failed view')
    for rank in (0, 1):
        r = read(dest / 'boundary' / f'boundary-rank{rank}.json')
        require(r == view['boundary'][rank] and r['passed'] is True and r['total_reset'] is True and
                r['cached_tokens'] == 0 and r['weight_uploads_after_load'] == 0 and
                r['selection_sha256'] == selection['selection_sha256'], 'boundary not proven')
    incident = read(dest / 'incident64/receipt.json')
    require(view['incident64']['receipt_sha256'] == sha(dest / 'incident64/receipt.json') and
            incident['tokens'] == oracle(D.CHECK.PROMPT_IDS[0])[:64] and incident['cached_tokens'] == 0 and
            incident['passed'] is True and incident['exact_oracle'] is True, 'incident64 differs')
    result = summary(view['requests'], view['incident64'], 'tp2')
    result.update(placement=identity['placement'], lane=identity['lane'], conditions=identity['conditions'],
                  timing='token', device_isolation=isolation, bracket_view=index, shared_model_lifetime=False)
    metrics = checked_requests(result, oracle, 128)
    save(dest / 'summary.json', result)
    save(dest / 'identity.json', dict(identity, view=selection, bracket_view=index))
    proposals = {name: proposal_identity(dest / name) for name in ['incident64', *D.CHECK.PROMPT_IDS]}
    variant = 'production' if view['choice'] == 'control' else 'unsplit'
    row = dict(index=index, choice=view['choice'], variant=variant, all_13_exact=True, exact_count=13, draft_proposals=proposals,
               lane=identity['lane'], boot_id=window['boot_id'], output=str(dest),
               started_utc_ns=view['started_utc_ns'], finished_utc_ns=view['finished_utc_ns'], **metrics)
    from s185_decision import view_stats, decide_or_incomplete, row_record
    if isolation.get('synthetic_cpu_fixture'):
        stats = dict(status='synthetic report wiring only; no interval statistics', device_evidence=False)
    else:
        stats = view_stats(dest, list(D.CHECK.PROMPT_IDS), view['choice'] == 'control')
    result = label(dict(schema='packet185.view-row.v1', passed=True, kind='view', view_index=index, variant=variant,
                        model_lifetimes=1, target_loads=1, draft_loads=1, teardown_count=1, fresh_load_view=True,
                        views=[row], all_13_exact=True, interval_stats=stats, class_copies=class_copies(output, identity),
                        measured_wall_seconds=(__import__('time').time_ns() - window['started_utc_ns']) / 1e9))
    from timing_report import summarize
    result['scheduling_costs'] = summarize(output, views)
    if not isolation.get('synthetic_cpu_fixture'):
        require(all(v['status'] == 'measured' for v in result['scheduling_costs']['views']), 'missing real correction trace')
    from analyze import analyze
    result['rank0_split'] = analyze(views, synthetic=isolation.get('synthetic_cpu_fixture', False))
    result['candidate_qualified'] = False
    result['purpose'] = 'packet185 fresh-load attribution of the split-head coupling (V3 kill thresholds); never a record or speed claim'
    if index == 4:
        rows = []
        try:
            for previous in range(4):
                rows.append(row_record(load(row_output(previous, identity['lane']))))
            rows.append(row_record(dict(result, views=[row])))
            result['s185_decision'] = decide_or_incomplete(rows)
        except (ValueError, KeyError, OSError) as error:
            result['s185_decision'] = decide_or_incomplete(error)
    else:
        result['s185_decision'] = dict(schema='packet185.s185-decision.v1', v3_go=False,
                                       outcome='PENDING: decided by view row 4 (or s185_decision.py over all five rows)')
    save(output / 'bracket-summary.json', result)
    return result

def load(output):
    """Read one retained fresh-load view row, verifying every retained file digest."""
    output=Path(output)
    window=read(output/'window.json')
    require(window.get('passed') is True and window.get('device_executed') is True and window.get('device_complete') is True and
            window.get('lease_released') is True and not window.get('child_still_running') and
            not window.get('stop_reasons'), 'view row device phase incomplete')
    require(read(output/'run/teardown.json').get('drained') is True, 'teardown unproven')
    for leaf,digest in window['files'].items():
        path=(output/leaf).resolve()
        require(path.is_relative_to(output.resolve()) and sha(path)==digest, 'changed view-row artifact: '+leaf)
    result=read(output/'bracket-summary.json')
    require(result['passed'] is True and result['kind']=='view' and result['model_lifetimes']==1, 'view row result failed')
    identity=read(output/'identity.json')
    require(window['identity']==identity and identity['bracket']['view_index']==result['view_index'], 'view row identity differs')
    from common import HERE
    require(window['wrapper_seal_sha256']==sha(HERE/'placement-validation/wrapper-seal.json'), 'wrapper seal changed')
    require(window['oracle_completion_sha256']==sha(D.ORACLE/'results/completion.json'), 'oracle changed')
    require(read(output/'suite-manifest.snapshot.json')==D.oracle_inputs(), 'oracle prompt suite changed')
    oracle=lambda prompt:D.CHECK.token_record(D.ORACLE/'results'/prompt)
    row=result['views'][0]
    dest=output/'run/views'/f'00-{row["choice"]}'
    checked=checked_requests(read(dest/'summary.json'),oracle,128)
    require(checked['rate']==row['rate'] and checked['acceptance_counts']==row['acceptance_counts'], 'changed view metrics')
    proposals={name:proposal_identity(dest/name) for name in ['incident64',*D.CHECK.PROMPT_IDS]}
    require(proposals==row['draft_proposals'],'draft proposal record changed')
    incident=read(dest/'incident64/receipt.json')
    require(incident['tokens']==oracle(D.CHECK.PROMPT_IDS[0])[:64] and incident['cached_tokens']==0, 'changed incident')
    return result

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('output',type=Path);args=parser.parse_args()
    print(json.dumps(load(args.output),indent=2))
