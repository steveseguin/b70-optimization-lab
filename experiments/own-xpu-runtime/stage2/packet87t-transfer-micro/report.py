"""Receipt-bound transport summary and unchanged packet87 equation evaluation."""
import ast
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import statistics

def require(ok, message):
    if not ok: raise ValueError(message)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def stats(values):
    v=sorted(values);require(len(v)>=200,'at least 200 samples required')
    return dict(n=len(v),median=statistics.median(v),p90=v[math.ceil(.9*len(v))-1],mean=statistics.mean(v))
def summarize(rows):
    require(len(rows)==1801 and rows[-1].get('kind')=='summary','complete 1800-sample receipt required')
    require(rows[-1].get('passed') is True and rows[-1].get('drained') is True,'native success and drain required')
    groups={}
    for r in rows[:-1]:
        require(r.get('kind')=='sample' and r.get('bytes_exact') is True,'sample/byte proof missing')
        case=r['case'];concurrent=r['concurrent'];require(type(concurrent) is bool,'mode must be boolean')
        expected={'hidden':5120,'best8':8,'best16':16,'pipeline20480':20480,'mailbox20480':20480}
        require(case in expected and r['bytes']==expected[case],'wrong transfer size')
        require([r['source_card'],r['destination_card']]==([3,2] if case=='hidden' else [2,3]),'wrong card direction')
        require(type(r['rep']) is int and 0<=r['rep']<200,'wrong repetition')
        for name in ('total_us','export_us','import_us','host_boundary_us'):
            require(math.isfinite(r[name]) and r[name]>=0,'invalid latency')
        require(r['start_s']<=r['export_done_s']<=r['usable_s'],'unordered completion timestamps')
        require(abs(r['total_us']-(r['usable_s']-r['start_s'])*1e6)<1e-6,'total endpoint mismatch')
        require(abs(r['total_us']-r['export_us']-r['import_us'])<1e-6,'leg sum mismatch')
        groups.setdefault((case,concurrent),[]).append(r)
    expected={(c,b) for c in ('hidden','best8','best16','pipeline20480') for b in (False,True)}|{('mailbox20480',False)}
    require(set(groups)==expected,'missing/extra cases')
    result={}
    for (case,busy),group in groups.items():
        require(len(group)==200 and {r['rep'] for r in group}==set(range(200)),'duplicate/missing repetition')
        result[case+('/compute' if busy else '/idle')]={field:stats([r[field] for r in group]) for field in ('total_us','export_us','import_us','host_boundary_us')}
    return result

def equations(packet):
    old=packet.parent/'packet87-slack-model';d=load(old/'DECISION.json')
    # Extract, do not rewrite, the six nested pure functions. No frozen main or
    # output writer is invoked. This executes packet87 model.py's actual code.
    tree=ast.parse((old/'model.py').read_text());main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
    names={'costs','target_race','draft_time','paths','evaluate','optimum'}
    nodes=[n for n in main.body if isinstance(n,ast.FunctionDef) and n.name in names]
    require(len(nodes)==6,'packet87 equation interface changed')
    spec=importlib.util.spec_from_file_location('packet85_model',packet.parent/'packet85-critical-path/model.py')
    p85=importlib.util.module_from_spec(spec);spec.loader.exec_module(p85)
    head=d['measured_head_ms']
    ns=dict(p85=p85,c=d['baseline']['components_ms'],probability=d['baseline']['acceptance'],
            observed=d['baseline']['measured_tok_s'],baseline_rate=d['baseline']['modeled_tok_s'],
            known=d['handoff_accounting']['new_host_boundary_proxy_ms'],head=head['target'],prefix=head['draft_prefix'],target_argmax=head['target_argmax'],draft_argmax=head['draft_argmax'])
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(old/'model.py'),'exec'),ns)
    return ns,d

def predict(packet,summary):
    ns,old=equations(packet)
    # Check the imported functions against the published optimistic optima first.
    for option in ('target','draft'):
        expected=old['options'][option]['known_boundary_only_optimum']
        require(ns['optimum'](option)==expected,'packet87 reproduction failed')
    # Transport timing already includes mailbox/host slab work: replace E/I/V,
    # never add the old publication proxy on top of its measured replacement.
    # The final CPU merge/collection still retains its old small proxy.
    collect=old['handoff_accounting']['measured_host_boundaries_ms']['emission_after_race_ms']['mean']
    ns['known']={k:0.0 for k in ns['known']}
    scenarios={}
    for mode in ('idle','compute'):
        for quantile in ('median','p90'):
            h=summary['hidden/'+mode];v=summary['best16/'+mode]
            legs=(h['export_us'][quantile]/1000,h['import_us'][quantile]/1000,v['total_us'][quantile]/1000+collect)
            rows={o:ns['optimum'](o,legs) for o in ('target','draft')}
            for row in rows.values():
                row['measured_E_I_V_ms']=row.pop('unmeasured_extra_ms_export_import_return')
                row['design_threshold_passed']=row['rank0_rows']>0 and row['gain_percent_vs_measured_control']>=.5
            scenarios[mode+'/'+quantile]=rows
    # Busy-case queue wait is deliberately charged in full: conservative screen.
    # It cannot be reported as a model speed measurement.
    return dict(scenarios=scenarios,decision_basis='compute/median',
        options={o:dict(predicted_gain_percent=scenarios['compute/median'][o]['gain_percent_vs_measured_control'],
                       design_threshold_passed=scenarios['compute/median'][o]['design_threshold_passed']) for o in ('target','draft')},
        calibration_packet85_mean_us=old['handoff_accounting']['measured_host_boundaries_ms']['handoff_ready_to_rank1_ms']['mean']*1000,
        assumptions=['Packet87 head row scaling and acceptance unchanged.',
                     'E/I/V include measured ordered host completion and staging; old publication proxies replaced.',
                     '16-byte return includes H2D to rank1, conservative relative to packet87 CPU-merge-only design.',
                     'Final CPU collection/merge retains packet87 proxy; no target logit arithmetic is benchmarked.',
                     'Same in-order queues serialize own-card compute and copy. Busy median includes outstanding compute wait; no hidden overlap credit.',
                     'p90 of component costs is a sensitivity scenario, not p90 of model throughput.'])

def evaluate(packet):
    packet=Path(packet);out=packet/'evidence/micro-B';window=load(out/'window.json');build=load(packet/'evidence/microbench-build.json')
    require(window.get('passed') is True and window.get('drained') is True and window.get('device_executed') is True,'passed device receipt required')
    require(window.get('lane')=='B' and window.get('physical_cards')==[2,3],'wrong lane')
    require(window.get('samples_sha256')==sha(out/'samples.jsonl'),'sample receipt mismatch')
    require(window.get('binary_sha256')==sha(packet/'build/microbench')==build['artifacts']['build/microbench'],'binary identity mismatch')
    require(window.get('device_isolation',{}).get('passed') is True,'device isolation missing')
    rows=[json.loads(l) for l in (out/'samples.jsonl').read_text().splitlines() if l.strip()]
    summary=summarize(rows);prediction=predict(packet,summary)
    result=dict(schema='packet87t.measured-transfer-model.v1',device_executed=True,diagnostic=True,model_speed_measured=False,
                summary_us=summary,prediction=prediction,sources={str(p):sha(p) for p in [out/'window.json',out/'samples.jsonl',packet/'report.py',packet.parent/'packet87-slack-model/model.py',packet.parent/'packet87-slack-model/DECISION.json']})
    (packet/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n')
    lines=['# Packet87t decision','', 'Measured transfer microbenchmark; gains below are predictions, not model speeds.','']
    for option,row in prediction['options'].items():
        verdict='eligible for a seal-ready implementation design' if row['design_threshold_passed'] else 'closed: below the +0.5% design threshold'
        lines.append(f"- {option}: {row['predicted_gain_percent']:+.4f}%; {verdict}.")
    lines+=['','Exact model inputs and all idle/compute median/p90 sensitivities: [RESULT.json](RESULT.json).',
            'Any eligible design still requires row arithmetic, tie/finite checks, memory admission and fresh-process output gates.']
    (packet/'DECISION.md').write_text('\n'.join(lines)+'\n')
    closed=[o for o,r in prediction['options'].items() if not r['design_threshold_passed']]
    if closed:(packet/'DO-NOT-REPEAT.md').write_text('# Packet87t closed arms\n\n'+''.join(f'- {o}: measured-cost prediction below +0.5%. Revisit only with a changed measured transport/queue mechanism; do not rerun this unchanged split.\n' for o in closed))
    return result

if __name__=='__main__':evaluate(Path(__file__).resolve().parent)
