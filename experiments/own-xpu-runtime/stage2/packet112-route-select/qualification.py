"""Require both clean fresh processes and <=0.5 production device time."""
import json, math, statistics
from build_engine import P, ROOT, sha, save
def require(ok,why):
    if not ok:raise ValueError(why)
def analyze(rows):
    require(rows and rows[0]['kind']=='process' and rows[-1]['kind']=='summary','complete native transcript')
    summary=rows[-1];require(summary['passed'] is True and summary['drained'] is True and summary['cases']==2048 and summary['nonfinite_cases']==512,'native summary')
    checks=[r for r in rows if r['kind']=='correctness']
    require([r['case'] for r in checks]==list(range(2048)) and all(r['exact'] is True for r in checks),'complete ordered byte gate')
    require(sum(r['nonfinite'] for r in checks)==512,'nonfinite coverage')
    samples=[r for r in rows if r['kind']=='sample'];require(len(samples)==16*64*2,'all measured pairs')
    seen={};times={}
    for r in samples:
        row,rep,pos=r['row'],r['repeat'],r['position'];view=r['view']
        require(type(row) is int and 0<=row<16 and type(rep) is int and 0<=rep<64 and pos in (0,1),'sample bounds')
        require(view==('p112' if pos^(rep%2) else 'production'),'alternating AB/BA')
        key=(row,rep,view);require(key not in seen,'duplicate sample');seen[key]=r
        dt=r['end_ns']-r['start_ns'];require(r['start_ns']>0 and dt==r['event_ns'] and 0<dt<1_000_000_000 and math.isfinite(r['wall_ns']) and r['wall_ns']>0,'event endpoints')
        for scope in ('all',f'order-{rep%2}',f'layer-{4 if row<8 else 3}'):
            times.setdefault(scope,{}).setdefault(view,[]).append(dt)
    result={}
    for scope,views in times.items():
        production=statistics.median(views['production']);candidate=statistics.median(views['p112'])
        result[scope]=dict(production_ns=production,p112_ns=candidate,ratio=candidate/production,saved_ns=production-candidate,qualified=candidate<=production*0.5)
    return dict(qualified=all(r['qualified'] for r in result.values()),times=result,pid=rows[0]['pid'],input_sha256=rows[0]['input_sha256'],output_sha256=summary['output_sha256'])
def evaluate():
    dirs=[P/'evidence'/f'micro-B-{i}' for i in (1,2)]
    if not all((d/'window.json').exists() for d in dirs):
        result=dict(qualified=False,status='pending two fresh device processes');save(P/'evidence/qualification.json',result);return result
    results=[];bindings={}
    build=P/'evidence/build-device.json';br=json.loads(build.read_text())
    for n,h in br['sources'].items():require(sha(ROOT/n)==h,'changed build source '+n)
    for n,h in br['artifacts'].items():require(sha(P/n)==h,'changed binary')
    seal=P/'seal.json';sr=json.loads(seal.read_text())
    for n,h in sr['sources'].items():require(sha(ROOT/n)==h,'changed sealed source '+n)
    for n,h in sr['files'].items():require(sha(P/n)==h,'changed sealed file '+n)
    for d in dirs:
        window=d/'window.json';samples=d/'samples.jsonl';w=json.loads(window.read_text())
        require(all(w.get(k) is True for k in ('passed','device_executed','drained','lease_released')) and w.get('child_still_running') is False and not w['stop_reasons'],'unclean device process')
        require(w['device_isolation']['passed'] and w['physical_cards']==[2],'isolation')
        require(w['binary_sha256']==sha(P/'build/micro-device') and w['build_receipt_sha256']==sha(build) and w['samples_sha256']==sha(samples) and w['identity']['packet_seal_sha256']==sha(seal),'window identity')
        rows=[json.loads(s) for s in samples.read_text().splitlines()];r=analyze(rows)
        require(r['pid']==w['pid'] and r['input_sha256']==sha(P/'evidence/capture/harness-logits.bin'),'native identity')
        results.append(r)
        for path in (window,samples):bindings[str(path.relative_to(ROOT))]=sha(path)
    require(results[0]['pid']!=results[1]['pid'],'fresh processes required')
    require(results[0]['output_sha256']==results[1]['output_sha256'],'fresh-process output identity')
    for path in (build,seal,P/'qualification.py'):bindings[str(path.relative_to(ROOT))]=sha(path)
    qualified=all(r['qualified'] for r in results)
    result=dict(qualified=qualified,status='micro-qualified; model gates pending' if qualified else 'closed: micro kill gate failed',processes=results,bindings=bindings,model_speed_claim=False)
    save(P/'evidence/qualification.json',result);return result
if __name__=='__main__':print(json.dumps(evaluate(),indent=2))
