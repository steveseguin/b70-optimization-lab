"""Fail closed on the preregistered 0.6 recurrence-time ratio in BOTH owners."""
import json, statistics
from pathlib import Path
from build_engine import P, ROOT, sha, save

def require(ok, why):
    if not ok: raise ValueError(why)

def analyze(rows, receipt, cases):
    require(receipt.get('passed') is True and receipt.get('safe_to_exit') is True
            and receipt.get('device_executed') is True and receipt.get('cpu_mock') is False
            and receipt.get('recurrence_checks') == 768 and receipt.get('checks', 0) > 400
            and receipt.get('timing_pair_checks') == 100, 'complete exact native receipt')
    expected = [f'm{m}-s{s}-a{a}-p{p}-t{t}' for m in (1,2,4) for s in range(16)
                for a in range(2) for p in range(2) for t in range(4)]
    require([c['case'] for c in cases] == expected and all(c['equal'] is True for c in cases), 'complete exceptional/state cases')
    for c in cases:
        m=int(c['case'][1]);require(c['tokens']==m and c['bytes']==1572864+m*12288+12, 'state coverage')
        require(len(c['sha256'])==64 and all(x in '0123456789abcdef' for x in c['sha256']), 'state digest')
    require(len(rows)==200, 'both contexts, 50 complete alternating pairs each')
    strata={}
    for context in (128,4096):
        selected=[r for r in rows if r['occupied_context']==context]
        require(len(selected)==100, 'context coverage')
        for i in range(50):
            pair=selected[i*2:i*2+2]
            require([r['iteration'] for r in pair]==[i,i] and [r['mode'] for r in pair]==
                    (['current','specialized'] if i%2==0 else ['specialized','current']), 'alternating order')
            for r in pair:
                require(r['layer']==4 and r['position']==context-1 and r['warmup']==(i<10), 'workload identity')
                events=r['events'];require(len(events)==r['submissions'] and events, 'event count')
                measured={}
                for e in events:
                    require(type(e['start_ns']) is int and type(e['end_ns']) is int and 0<e['start_ns']<e['end_ns']
                            and e['end_ns']-e['start_ns']<4_000_000_000, 'event endpoints')
                    measured[e['class']]=measured.get(e['class'],0)+e['end_ns']-e['start_ns']
                require(measured==r['classes_ns'] and sum(measured.values())==r['gpu_ns'], 'class accounting')
                require(sum(e['class']=='gdn.recurrence' for e in events)==1, 'one full recurrence event')
                dt=measured['gdn.recurrence']
                if i>=10:
                    for order in ('all',str(i%2)):
                        strata.setdefault((context,order),{}).setdefault(r['mode'],[]).append(dt)
    result=[]
    for (context,order),times in strata.items():
        control=statistics.median(times['current']);candidate=statistics.median(times['specialized'])
        result.append(dict(context=context,order=order,pairs=len(times['current']),production_us=control/1000,
                           candidate_us=candidate/1000,ratio=candidate/control,saved_us=(control-candidate)/1000,
                           qualified=candidate<=0.6*control))
    return dict(qualified=all(r['qualified'] for r in result),strata=result)

def evaluate(p=P):
    p=Path(p);result=dict(schema='ownrt.packet113.micro-gate.v1',qualified=False,integration_allowed=False,
        device_speed_measured=False,threshold_ratio=0.6,model_speed_claim=False,processes=[])
    dirs=[p/'evidence'/f'micro-B-{i}' for i in (1,2)]
    if not all((d/'window.json').exists() for d in dirs):
        result['status']='pending two fresh device processes';save(p/'evidence/qualification.json',result);return result
    bindings={};identities=[];owners=[];digests=[]
    from run_micro import build_gate
    identity=build_gate()
    for d in dirs:
        paths=[d/'window.json',d/'native/receipt.json',d/'native/iterations.jsonl',d/'native/recurrence-cases.jsonl',d/'native/comparisons.jsonl']
        w=json.loads(paths[0].read_text());receipt=json.loads(paths[1].read_text())
        require(all(w.get(k) is True for k in ('passed','device_executed','drained','lease_released'))
                and w.get('child_still_running') is False and not w['stop_reasons'], 'clean completed process')
        require(w['identity']==identity and w['samples_sha256']==sha(d/'samples.jsonl'), 'immutable window identity')
        require(w['physical_cards']==[2] and w['device_isolation']['passed'] is True
                and w['device_isolation']['observed_pci']==['0000:43:00.0'], 'lane-B isolation')
        require(w['native_files']=={str(x.relative_to(d)):sha(x) for x in paths[1:]}, 'hash-bound native evidence')
        rows=[json.loads(x) for x in paths[2].read_text().splitlines()]
        cases=[json.loads(x) for x in paths[3].read_text().splitlines()]
        check=analyze(rows,receipt,cases)
        require(receipt['exact_output_identity']==sha(paths[4]), 'complete-layer comparison digest')
        result['processes'].append(dict(owner=d.name,pid=w['pid'],start_ticks=w['process_start_ticks'],**check))
        owners.append((w['pid'],w['process_start_ticks']));digests.append((sha(paths[3]),sha(paths[4])))
        bindings.update({str(x.relative_to(ROOT)):sha(x) for x in paths})
    require(owners[0]!=owners[1], 'two fresh processes')
    require(digests[0]==digests[1], 'fresh-process exact state and layer identity')
    qualified=all(r['qualified'] for r in result['processes'])
    result.update(qualified=qualified,integration_allowed=qualified,device_speed_measured=True,bindings=bindings,
        status='micro-qualified; runtime byte/oracle/startup gates still required' if qualified else 'closed: recurrence kill gate failed; no integration')
    save(p/'evidence/qualification.json',result);return result
if __name__=='__main__': print(json.dumps(evaluate(),indent=2))
