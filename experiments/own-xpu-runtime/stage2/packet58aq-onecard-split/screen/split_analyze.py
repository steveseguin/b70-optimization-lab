"""Publication interventions and host-call envelopes; never a speed claim."""
import json, math, statistics
from pathlib import Path
LABELS=('A0','U0','S0','D0','W0','A1')
ARMS=('control','no-upload','no-scatter','drain-only','wait-split','control')
THRESHOLD=.67

def finite(x):
    if type(x) not in (int,float) or not math.isfinite(x) or x<0:raise ValueError('invalid nonnegative timing')
    return x

def check(row, arm):
    p=row['publication_split']
    if p['arm']!=arm or p['diagnostic_only'] is not True:raise ValueError('split identity')
    for key in ('construction_ms','submit_ms','drain_ms','repair_ms','retire_host_ms'):finite(p[key])
    if type(p['calls']) is not int or p['calls']<0:raise ValueError('publication count')
    for w in p['waits']:
        if w['scope'] not in ('normal','probe','repair') or not w['kind'] or not w['phase']:raise ValueError('wait identity')
        if not all(type(w[k]) is int for k in ('begin_ns','call_ns','end_ns')) or not 0<w['begin_ns']<=w['call_ns']<=w['end_ns']:raise ValueError('wait clock order')
    if arm=='wait-split' and not p['waits']:raise ValueError('missing per-operation waits')
    return p

def read_rows(path):
    rows=[json.loads(x) for x in path.read_text().splitlines()]
    if not rows:raise ValueError('missing native token stream')
    for r in rows:
        for k in ('wall_ms','wait_ms','prepare_ms','enqueue_loop_ms'):finite(r[k])
    return rows

def component(row):
    p=row['publication_split'];waits=[w for w in p['waits'] if w['scope']=='normal']
    wait_call=sum((w['end_ns']-w['call_ns'])/1e6 for w in waits)
    wrapper=sum((w['call_ns']-w['begin_ns'])/1e6 for w in waits)
    prep_wait=sum((w['end_ns']-w['begin_ns'])/1e6 for w in waits if w['phase']=='resident-lookup-prepare')
    return dict(publication_calls=p['calls'],construction_ms=p['construction_ms'],submission_ms=p['submit_ms'],drain_ms=p['drain_ms'],
        publication_ms=p['construction_ms']+p['submit_ms']+p['drain_ms'],repair_ms=p['repair_ms'],
        wait_call_envelope_ms=wait_call,wait_wrapper_host_ms=wrapper,retire_host_ms=p['retire_host_ms'],
        lookup_host_upper_ms=max(0,row['prepare_ms']-prep_wait),enqueue_host_ms=row['enqueue_loop_ms'],wall_ms=row['wall_ms'])

def analyze(out,manifest,views):
    if [v['label'] for v in views]!=list(LABELS):raise ValueError('complete six-arm screen required')
    report={};raw={};hashes={};operation_requests={}
    import hashlib
    for label,arm in zip(LABELS,ARMS):
        requests={};prefill=[]
        for entry in manifest['prompts']:
            f=out/'run'/label/entry['prompt_id']/'timings.jsonl';rows=read_rows(f)
            hashes[str(f.relative_to(out))]=hashlib.sha256(f.read_bytes()).hexdigest()
            result=json.loads((f.parent/'result.json').read_text())
            if len(rows)!=len(result['tokens']) or [r['generated_index'] for r in rows]!=list(range(1,len(rows)+1)) or [r['token_id'] for r in rows]!=result['tokens']:
                raise ValueError('timing stream does not cover exact output')
            for row in rows:check(row,arm)
            if arm=='wait-split':
                groups={}
                for row in rows:
                    for w in row['publication_split']['waits']:
                        key=w['scope']+'/'+w['phase']+'/'+w['kind']
                        value=groups.setdefault(key,dict(blocking_call_ms=0.,wrapper_host_ms=0.,calls=0))
                        value['blocking_call_ms']+=(w['end_ns']-w['call_ns'])/1e6/len(rows)
                        value['wrapper_host_ms']+=(w['call_ns']-w['begin_ns'])/1e6/len(rows)
                        value['calls']+=1/len(rows)
                operation_requests[entry['prompt_id']]=groups
            # Keep all generated rows, including slow first generated token. No point selection.
            vals=[component(r) for r in rows]
            requests[entry['prompt_id']]={k:statistics.mean(x[k] for x in vals) for k in vals[0]}
            pre=out/'run'/label/entry['prompt_id']/'prefill-timings.jsonl'
            pr=read_rows(pre)
            if len(pr)!=entry['prompt_tokens']-1 or any(r['generated_index']!=0 for r in pr):
                raise ValueError('incomplete prefill stream')
            for row in pr:check(row,arm)
            prefill.extend(pr)
        raw[label]=requests
        report[label]={k:statistics.median(r[k] for r in requests.values()) for k in next(iter(requests.values()))}
        report[label].update(requests=requests,generated_rows=sum(len(read_rows(out/'run'/label/e['prompt_id']/'timings.jsonl')) for e in manifest['prompts']),prefill_rows=len(prefill),arm=arm,prefill_ms_per_token=({k:statistics.mean(component(r)[k] for r in prefill) for k in component(prefill[0])} if prefill else None))
    operation_keys=set().union(*(r.keys() for r in operation_requests.values()))
    operations={k:{field:statistics.median(r.get(k,{}).get(field,0.) for r in operation_requests.values()) for field in ('blocking_call_ms','wrapper_host_ms','calls')} for k in sorted(operation_keys)}
    report['W0']['wait_by_scope_phase_operation_ms_per_token']=operations
    # Paired request differences against BOTH bracketing controls, no fitted/interpolated control.
    pairs={}
    for component_name,label,base in [('upload_including_submission','U0',None),('scatter_including_submission','S0',None),('device_publication_and_drain','D0',None),('construction','D0','construction_ms')]:
        comparisons=[]
        for control in ('A0','A1'):
            vals=[]
            for prompt in raw[control]:
                c=raw[control][prompt];a=raw[label][prompt]
                vals.append(c[base] if base else c['publication_ms']-a['publication_ms'])
            comparisons.append(statistics.median(vals))
        matched=all(raw[c][prompt]['publication_calls']==raw[label][prompt]['publication_calls'] for c in ('A0','A1') for prompt in raw[c])
        pairs[component_name]=dict(ms_per_token_by_control=comparisons,conservative_ms_per_token=min(comparisons),publication_cadence_matched=matched)
    drift={k:report['A1'][k]-report['A0'][k] for k in ('publication_ms','construction_ms','drain_ms','wall_ms')}
    eligible={k:v for k,v in pairs.items() if v['publication_cadence_matched'] and v['conservative_ms_per_token']>=THRESHOLD+abs(drift['publication_ms'])}
    host={k:report['W0'][k] for k in ('wait_wrapper_host_ms','retire_host_ms','lookup_host_upper_ms','enqueue_host_ms') if report['W0'][k]>=THRESHOLD}
    host.update({k+':wrapper_host_ms':v['wrapper_host_ms'] for k,v in operations.items() if k.startswith('normal/') and v['wrapper_host_ms']>=THRESHOLD})
    # lookup_host_upper includes driver work and is explicitly an upper bound, not proven removable.
    decision='build-brief' if eligible else 'name-host-work' if host else 'close' if all(v['publication_cadence_matched'] for v in pairs.values()) else 'inconclusive-cadence'
    return dict(candidate_beats_all_controls=False,diagnostic_only=True,submission_eligible=False,
        decision=decision,threshold_ms_per_token=THRESHOLD,segments=report,paired_differences=pairs,
        qualifying_publication_segments=eligible,host_work_components=host,control_drift_ms_per_token=drift,
        timing_stream_sha256=hashes,aggregation='per-request mean milliseconds per generated token, median across all twelve requests; both controls kept',
        limitation='Skip probes are repaired before model readers. Differences are causal boundary diagnostics, not end-to-end speedups. Device wait includes 1ms polling and scheduler latency; it is not kernel time. Components overlap: never sum host, publication and wait envelopes.')

def publish(out,result):
    """Write the requested actionable decision after complete device evidence."""
    if result['decision']=='build-brief':
        (out/'BUILD-BRIEF.md').write_text('# Exact publication change to build\n\n'+
            'Qualifying components: '+', '.join(result['qualifying_publication_segments'])+'.\n'+
            'For construction/upload/scatter: build only changed final pointer/generation entries and preserve exact full-table fallback. For device_publication_and_drain: investigate retaining dependency ordering and staging lifetime through subsequent same-queue work instead of a blocking poll at publication; never remove a reader fence or reuse staging early. Preserve revocation and fill completion. Measure replacement overhead; retain BF16 KV and resident lookups. Require byte parity, iq3-p49-split32-v1 oracle and two fresh-process repeats before any speed claim.\n')
    elif result['decision']=='name-host-work':
        (out/'HOST-WORK.md').write_text('# Host work to investigate\n\n'+json.dumps(result['host_work_components'],indent=2)+'\nThese measured host scopes are not proof that all their work is removable.\n')
    elif result['decision']=='close':
        (out/'DO-NOT-REPEAT.md').write_text('| Date / arm | Outcome | Revisit |\n| --- | --- | --- |\n| packet58aq device split | No publication component clears 0.67 ms/token plus observed boundary drift; no named host scope clears 0.67 ms/token. See summary.json. | New matched causal evidence, not CPU-only estimates. |\n')

    if result['decision']=='inconclusive-cadence':
        (out/'CADENCE.md').write_text('Publication counts differ between arms. Keep the measured scopes, but do not call the difference a removable cost or close this lever. A matched boundary-call experiment is required.\n')
