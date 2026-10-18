"""V4 request-schema adapter; bracket views share one explicitly labeled lifetime."""
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
    expected=read(Path(identity['lineage'])/'selection.json')['choices']['class_layout_bank']
    rows=[]
    for rank in (0,1):
        path=output/'run/ranks'/('rank'+str(rank))/'class-layout.json'
        row=read(path)
        require(row['class_layout_bank']==expected and 0<row['bytes']<=600*1024**2 and row['budget']==600*1024**2 and row['weights'],'class copy allocation receipt missing')
        rows.append(dict(rank=rank,sha256=sha(path),**row))
    return rows

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
    if proof['kind']=='smoke':return finish_smoke(output,window,identity,proof,isolation,oracle)
    samples=class_copies(output,identity)
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
        proposals={name:proposal_identity(dest/name) for name in ['incident64',*D.CHECK.PROMPT_IDS]}
        rows.append(dict(index=index, choice=view['choice'], all_13_exact=True, exact_count=13, draft_proposals=proposals,
                         lane=identity['lane'], boot_id=window['boot_id'], output=str(dest),
                         started_utc_ns=view['started_utc_ns'], finished_utc_ns=view['finished_utc_ns'], **metrics))
    controls = [r['rate'] for r in rows if r['choice'] == 'control']
    require(all(r['acceptance_counts']==rows[0]['acceptance_counts'] for r in rows), 'per-prompt acceptance changed across views')
    require(all(r['draft_proposals']==rows[0]['draft_proposals'] for r in rows),'per-prompt draft proposals changed across views')
    drift = 100 * (max(controls) / min(controls) - 1)
    result = label(dict(schema='own-runtime.bracket.summary.v1', passed=True, kind=proof['kind'],
                        model_lifetimes=1, target_loads=1, draft_loads=1, teardown_count=1,
                        views=rows, all_13_exact=True, draft_proposals_identical=True, class_copies=samples, control_drift_percent=drift,
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
             gain_percent=100*(r['rate']/max(controls)-1),
             diagnostic_gain_over_control_mean_percent=100*(r['rate']/statistics.mean(controls)-1))
             for r in rows if r['choice']=='candidate']
        candidate_rates=[r['rate'] for r in rows if r['choice']=='candidate']
        require(len(candidate_rates)==2, 'both candidate repeats required')
        result['strict_candidate_control_ratio']=min(candidate_rates)/max(controls)
        result['strict_gain_percent']=100*(result['strict_candidate_control_ratio']-1)
        result['both_candidates_faster_than_all_controls']=min(candidate_rates)>max(controls)
        result['candidate_qualified']=drift<=3.0 and result['strict_candidate_control_ratio']>=1.005
        result['required_gain_percent']=0.5
    from timing_report import summarize
    result['scheduling_costs']=summarize(output,views)
    save(output / 'bracket-summary.json', result)
    require(result['passed'], 'A/A timing drift exceeds preregistered 3% control bound')
    return result

def smoke_checked(output,identity,proof,oracle):
    require(proof['kind']=='smoke' and proof['passed'] is True and len(proof['views'])==1,'incomplete smoke')
    view=proof['views'][0];selection=identity['bracket']['views'][0]
    require(view['index']==0 and view['choice']=='candidate' and view['selection_sha256']==selection['selection_sha256'],'smoke view identity')
    dest=output/'run/views/00-candidate'
    require(view['output']==str(dest),'smoke output escape')
    require([r['prompt_id'] for r in view['requests']]==list(D.CHECK.PROMPT_IDS),'complete smoke suite required')
    for row in view['requests']:
        require(row['passed'] is True and row['exact_oracle'] is True and row['cached_tokens']==0 and row['tokens']==oracle(row['prompt_id'])[:64] and len(row['tokens'])==64,'smoke target differs')
    incident=read(dest/'incident64/receipt.json')
    require(view['incident64']['receipt_sha256']==sha(dest/'incident64/receipt.json') and incident['tokens']==oracle(D.CHECK.PROMPT_IDS[0])[:64] and incident['passed'] is True,'smoke incident differs')
    for rank in (0,1):
        r=read(dest/'boundary'/f'boundary-rank{rank}.json')
        require(r==view['boundary'][rank] and r['passed'] is True and r['total_reset'] is True and r['cached_tokens']==0 and r['weight_uploads_after_load']==0 and r['selection_sha256']==selection['selection_sha256'],'smoke boundary differs')
    return dict(selection_sha256=selection['selection_sha256'],prompts=[dict(prompt_id=r['prompt_id'],tokens=r['tokens']) for r in view['requests']])

def finish_smoke(output,window,identity,proof,isolation,oracle):
    checked=smoke_checked(output,identity,proof,oracle)
    dest=output/'run/views/00-candidate'
    proposals={name:proposal_identity(dest/name) for name in ['incident64',*D.CHECK.PROMPT_IDS]}
    result=label(dict(passed=True,kind='smoke',model_lifetimes=1,request_count=12,max_new=64,views=proof['views'],smoke_identity=checked,class_copies=class_copies(output,identity),draft_proposals=proposals,timing_status='smoke only; no speed verdict; device proposal parity checked by bracket'))
    save(output/'bracket-summary.json',result);return result

def load(output):
    """Read shared-lifetime views without impersonating fresh v4 server windows."""
    output=Path(output)
    window=read(output/'window.json')
    recovered=(output/'report-regeneration.json').exists()
    if recovered:
        from report_recovery import recovered_window
        window=recovered_window(output,window)
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
    require(class_copies(output,identity)==result['class_copies'],'class copy receipt changed')
    require(window['identity']==identity, 'bracket window identity differs')
    from common import HERE
    if not recovered:require(window['wrapper_seal_sha256']==sha(HERE/'placement-validation/wrapper-seal.json'), 'wrapper seal changed')
    require(window['oracle_completion_sha256']==sha(D.ORACLE/'results/completion.json'), 'oracle changed')
    require(read(output/'suite-manifest.snapshot.json')==D.oracle_inputs(), 'oracle prompt suite changed')
    oracle=lambda prompt:D.CHECK.token_record(D.ORACLE/'results'/prompt)
    require(len(result['views'])==len(identity['bracket']['views']), 'missing bracket views')
    if result['kind']=='smoke':
        proof=read(output/'run/bracket-inputs.json')
        checked=smoke_checked(output,identity,proof,oracle)
        require(checked==result['smoke_identity'],'smoke identity changed')
        dest=output/'run/views/00-candidate'
        require({name:proposal_identity(dest/name) for name in ['incident64',*D.CHECK.PROMPT_IDS]}==result['draft_proposals'],'smoke draft proposals changed')
        return result
    for index,row in enumerate(result['views']):
        dest=output/'run/views'/f'{index:02d}-{row["choice"]}'
        checked=checked_requests(read(dest/'summary.json'),oracle)
        require(checked['rate']==row['rate'] and checked['acceptance_counts']==row['acceptance_counts'], 'changed view metrics')
        proposals={name:proposal_identity(dest/name) for name in ['incident64',*D.CHECK.PROMPT_IDS]}
        require(proposals==row['draft_proposals']==result['views'][0]['draft_proposals'],'draft proposal parity changed')
        incident=read(dest/'incident64/receipt.json')
        require(incident['tokens']==oracle(D.CHECK.PROMPT_IDS[0])[:64] and incident['cached_tokens']==0, 'changed incident')
    return result

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('output',type=Path);args=parser.parse_args()
    print(json.dumps(load(args.output),indent=2))
