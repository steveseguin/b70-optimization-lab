#!/usr/bin/env python3
"""Read-only closed profiling audit. Does not import a runtime transport."""
import gzip,hashlib,importlib.util,json,math,os,resource,time
from pathlib import Path
P=Path(__file__).resolve().parent;L=P.parent;R=P.parents[3]
s=importlib.util.spec_from_file_location('closed_baseline_audit',L/'baseline/audit.py');B=importlib.util.module_from_spec(s);s.loader.exec_module(B)
read,sha,require=B.read,B.sha,B.require
C=Path('/home/steve/own-xpu-runtime-results/gsq-profile-a.control');E=Path('/mnt/usb-models/own-xpu-runtime-results/gsq-profile-a')
def run():
 require(os.getpriority(os.PRIO_PROCESS,0)==19,'nice19');require(os.sched_getaffinity(0)<=set(range(8,16))|set(range(24,32)),'helper affinity');resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
 out=P/'evidence/independent-a';out.mkdir(exist_ok=False);started=time.monotonic();review=dict(passed=False,device_executed_by_reviewer=False,schema='ownrt.gsq.profile-independent.v1')
 try:
  p=read(C/'plan.json');a=read(C/'admission.json');t=read(C/'terminal.json');q=p['suite'];adapter=p['adapter']
  require(t['plan_sha256']==a['plan_sha256']==sha(C/'plan.json') and a['plan']==p,'admission identity')
  require(a['canonical_plan_sha256']==hashlib.sha256(json.dumps(p,sort_keys=True,separators=(',',':')).encode()).hexdigest(),'canonical identity')
  for k,v in p['unit_properties'].items():require(a['unit'][k]==v,'safe unit '+k)
  B.validate_passive(a['before'],t['after'],t)
  require(t['result']['full_result_path']==str(E/'profile-result.json') and t['result']['full_result_sha256']==sha(E/'profile-result.json'),'result binding')
  f=read(E/'profile-result.json');require(f['passed'] and f['requests']==2 and f['measured_requests']==1 and f['exact_baseline_tokens'] and f['exact_baseline_target_state'],'complete profile')
  for mapping in (p['source_sha256'],q['source_sha256'],adapter['source_sha256']):
   for name,h in mapping.items():require(sha(R/name)==h,'source '+name)
  nr=read(adapter['build_receipt']);require(nr['passed'] and sha(adapter['build_receipt'])==adapter['build_receipt_sha256'] and sha(adapter['binary'])==nr['binary_sha256']==adapter['binary_sha256'],'native identity')
  for mapping in (nr['source_sha256'],nr['object_sha256']):
   for name,h in mapping.items():require(sha(R/name)==h,'native source/object '+name)
  br=L/'baseline/evidence/independent-a/review.json';bj=read(br);require(bj['passed'] and bj['all12_exact'] and bj['source_and_binary_pins_verified'] and bj['native_binary_sha256']==adapter['binary_sha256'],'independent baseline')
  require(q['baseline_evidence_sha256']==f['baseline_evidence_sha256'],'baseline bindings')
  for name,h in q['baseline_evidence_sha256'].items():require(sha(name)==h,'baseline artifact '+name)
  base=read(B.EVIDENCE/'resident-suite.json');bp=read(B.CONTROL/'plan.json');arm=next(x for x in base['prompts'][0]['arms'] if x['mode']=='none')
  require(q['prompt_id']==f['prompt_id']==base['prompts'][0]['prompt_id'] and q['prompt_tokens']==arm['prompt_tokens'],'fixed prompt00')
  require(f['result']['tokens']==arm['result']['tokens'] and f['state_sha256']==arm['state_sha256'],'baseline token/state maps')
  auditarm=next(x for x in bj['prompts'][0]['arms'] if x['mode']=='none');require(auditarm['tokens']==f['result']['tokens'],'audited baseline tokens')
  argv_deltas=[]
  for rank in (0,1):
   old=bp['adapter']['rank_argv'][rank];new=adapter['rank_argv'][rank];require(len(old)==len(new),'argv size');differences=[]
   for i,(x,y) in enumerate(zip(old,new)):
    if x!=y:
     key=old[i-1];require(key in ('--shared','--output','--seconds','--timing'),'unexpected argv delta')
     if key=='--seconds':require((x,y)==('7200','3600'),'watchdog delta')
     if key=='--timing':require((x,y)==('token','class'),'timing delta')
     if key in ('--shared','--output'):require(x.replace('gsq-baseline-a','gsq-profile-a')==y,'output identity')
     differences.append(dict(option=key,baseline=x,profile=y))
   require(len(differences)==4,'exact argv delta set');argv_deltas.append(differences)
   for k,v in bp['adapter']['environment'][rank].items():require(v.replace('gsq-baseline-a','gsq-profile-a')==adapter['environment'][rank][k],'environment '+k)
   require(set(bp['adapter']['environment'][rank])==set(adapter['environment'][rank]),'env keys')
  digests={};sizes={};count=total=0
  with (out/'artifact-index.jsonl.gz').open('xb') as raw,gzip.GzipFile(fileobj=raw,mode='wb',filename='',mtime=0) as z:
   for label,root in [('control',C),('evidence',E)]:
    for path in sorted(root.rglob('*')):
     require(not path.is_symlink(),'retained symlink')
     if not path.is_file():continue
     h=sha(path);n=path.stat().st_size;digests[str(path)]=h;sizes[str(path)]=n;count+=1;total+=n;require(count<20000 and total<1024**3,'readback bound')
     z.write((json.dumps(dict(root=label,path=str(path.relative_to(root)),bytes=n,sha256=h),separators=(',',':'))+'\n').encode())
  state_manifests=state_bytes=0
  for state in E.rglob('state.json'):
   parent=state.parent
   if not parent.name.startswith('state-'):continue
   sj=read(state);state_manifests+=1
   for name,h in sj['buffers'].items():
    fname=('alternate-'+name.split(':',1)[1] if name.startswith('alternate:') else name)+'.bin';path=parent/fname
    require(digests[str(path)]==h,'state manifest '+str(path));state_bytes+=sizes[str(path)]
  require(state_manifests==6,'three dumps both ranks')
  raw_target_bytes=0
  for rank in (0,1):
   directory=E/f'profile-none/rank{rank}/state-2147483647';actual={str(path.relative_to(directory)):digests[str(path)] for path in directory.rglob('*') if path.is_file()}
   require(actual==f['state_sha256'][str(rank)]==arm['state_sha256'][str(rank)],'full measured state readback');raw_target_bytes+=sum(sizes[str(x)] for x in directory.glob('*.bin'))
   for request in ('warmup-none','profile-none'):
    reset=read(E/request/f'rank{rank}/reset.json');require(reset['passed'] and reset['allocation_ids_preserved'],'full RESET')
  require(raw_target_bytes==221743168,'state extent')
  B.timing(f['result'],128);consumed=B.confirmed_inputs(f['result'],q['prompt_tokens']);require(all(f['result']['stats'][k]==0 for k in ('guesses','hits','misses')),'target only')
  warm=read(E/'warmup-none/warmup.json');require(warm['excluded'],'warmup excluded');B.timing(warm['result'],8,False);B.confirmed_inputs(warm['result'],q['warmup']['tokens'])
  classes={}
  for rank in (0,1):
   retained=f['classes'][str(rank)];path=E/f'profile-none/rank{rank}/class-times.json';r=read(path)
   require(str(path)==retained['path'] and r==retained['report'] and digests[str(path)]==retained['sha256'],'class identity');require(r['profiling'] and r['tokens']==128 and r['classes'],'class scope')
   names=[]
   for x in r['classes']:
    names.append(x['class']);require(type(x['device_ms']) in (int,float) and math.isfinite(x['device_ms']) and x['device_ms']>=0,'finite class time')
    for key in ('launches','groups'):require(type(x[key]) is int and x[key]>=0,'class count')
   require(len(names)==len(set(names)) and any(x['device_ms']>0 and x['launches']>0 for x in r['classes']),'nonvacuous classes')
   classes[str(rank)]=dict(classes=len(names),launches=sum(x['launches'] for x in r['classes']),groups=sum(x['groups'] for x in r['classes']),device_ms_sum=sum(x['device_ms'] for x in r['classes']),top_classes=sorted(r['classes'],key=lambda x:x['device_ms'],reverse=True)[:10])
  owners=[]
  for rank in (0,1):
   owner=read(E/f'rank{rank}/receipt.json');require(owner['passed'] and owner['error']=='' and owner['rank']==rank and len(owner['teardown'])==1,'owner receipt');o=owner['teardown'][0];require(o['safe_to_exit'] and o['exit_code']==o['in_flight']==o['live_bytes']==0,'owner clean');owners.append(o)
  ownership=read(E/'ownership.json');require(ownership['returncodes']==[0,0] and not ownership['retained_pids'] and ownership['signals_sent']==0 and not ownership['stop_requested'] and not ownership['diagnostic_errors'],'process close')
  require(total<=q['storage']['evidence_forecast_bytes']+q['storage']['root_cache_forecast_bytes'],'actual combined bytes within combined forecast')
  review.update(passed=True,artifact_count=count,indexed_bytes=total,index_sha256=sha(out/'artifact-index.jsonl.gz'),baseline_audit_sha256=sha(br),full_result_sha256=sha(E/'profile-result.json'),plan_sha256=sha(C/'plan.json'),source_pins_verified=True,native_binary_sha256=adapter['binary_sha256'],requests=2,warmup_excluded=True,measured_tokens=len(f['result']['tokens']),consumed_positions=consumed,exact_baseline_tokens=True,exact_baseline_target_state=True,state_manifests=state_manifests,state_manifest_buffer_bytes=state_bytes,argv_deltas=argv_deltas,classes=classes,owners=owners,ownership=ownership,retained_passive_fault_and_drain_verified=True,roots=dict(control=str(C),evidence=str(E)),limitations=['Whole-request diagnostic class event sums include prefill, not decode-only attribution or end-to-end latency','Profiling changes queue properties and adds overhead; no speed claim','Per-run paths and watchdog7200-to3600 differ from baseline; only compute configuration delta is token-to-class timing','Native class labels are inherited; not all copy work is classified','State exactness is same-engine baseline, not external engine semantic quality','Physical drain/fault evidence is retained coordinator evidence; reviewer performed no device/service/kernel queries'])
 except BaseException as error:
  review['error']=type(error).__name__+': '+str(error);raise
 finally:
  review.update(auditor_sha256=sha(__file__),baseline_auditor_sha256=sha(L/'baseline/audit.py'),elapsed_seconds=time.monotonic()-started)
  (out/'review.json').write_text(json.dumps(review,indent=2)+'\n')
 print(json.dumps(dict(passed=True,review=str(out/'review.json'),sha256=sha(out/'review.json'))))
if __name__=='__main__':run()
