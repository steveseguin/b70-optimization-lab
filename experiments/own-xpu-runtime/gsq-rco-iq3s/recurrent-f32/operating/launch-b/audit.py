#!/usr/bin/env python3
"""Root-only closed F32 pair readback. No model payload/runtime/device operations."""
from pathlib import Path
import argparse,gzip,hashlib,importlib.util,json,os,resource,stat,time
HERE=Path(__file__).resolve().parent;P=HERE.parent;L=P.parents[1];R=L.parents[2];D=HERE/'evidence/device-b'
CONTROL=Path('/home/steve/own-xpu-runtime-results/gsq-recurrent-f32-b.control')
EVIDENCE=Path('/mnt/usb-models/own-xpu-runtime-results/gsq-recurrent-f32-b')
PLAN_SHA='67add3de84d91bf85d09e3d98d73ac1d5dc46306b24056682ad8b249b576e1ee' # separately admitted B; failed A remains unqualified
BINARY='5926a24746c62c6b0ecdc5c3e4895f310145e0f9d74a90a5d657035b9a8151f4'
INDEX=L/'baseline/evidence/independent-a/artifact-index.jsonl.gz'
INDEX_SHA='e8137dddb0929d5476d27a8a774539a77d595aeb296e9d0ec778ceec066a6982'
def load(p,n):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
S=load(P/'bundle_scan.py','f32_closed_bundle_scan');B=S.OLD.B
sha,read,require=B.sha,B.read,B.require

def corrected_extent(name,old):
 if name.endswith('.gdn.state.bin'):require(old==1572864,'old matrix geometry');return 3145728
 if name.endswith('.gdn.history.bin'):require(old==61440,'old GDN history geometry');return 122880
 if name.endswith('ple.history.bin'):require(old==184320,'old PLE history geometry');return 368640
 return old

def budget_ok(v):
 require(v['stage']==5 and v['acknowledged']==['initial_reset','target_dump','second_reset','mtp_dump','finish'] and v['remaining_payload_bytes']==0,'closed capture ACK chain')
 require(v['metadata_reserve_bytes']==128<<20 and v['external_floor_bytes']==2<<30,'unchanged reserves')
def raw_join(saved,row):
 expected=dict(row);expected.pop('reference_comparison');require(saved==expected,'raw arm versus enriched result')
def run():
 require(os.getpriority(os.PRIO_PROCESS,0)==19 and os.sched_getaffinity(0)<=set(range(8,16))|set(range(24,32)),'placement');resource.setrlimit(resource.RLIMIT_AS,(4<<30,4<<30))
 D.mkdir(parents=True,exist_ok=True);require(not (D/'review.json').exists() and not (D/'artifact-index.jsonl.gz').exists(),'fresh audit');start=time.monotonic();receipt={'passed':False,'scope':'Corrected F32 native pair readback; no speed or broad quality claim','historical_bf16_state_oracle_used':False}
 try:
  plan=read(CONTROL/'plan.json');ad=read(CONTROL/'admission.json');term=read(CONTROL/'terminal.json')
  require(sha(CONTROL/'plan.json')==ad['plan_sha256']==term['plan_sha256']==PLAN_SHA and ad['plan']==plan,'exact admitted plan');require(S.digest(json.dumps(plan,sort_keys=True,separators=(',',':')).encode())==ad['canonical_plan_sha256'],'canonical plan')
  for k,v in plan['unit_properties'].items():require(ad['unit'][k]==v,'safe unit property')
  B.validate_passive(ad['before'],term['after'],term)
  require(plan['initial_cache_growth_margin_bytes']==128<<20 and plan['initial_root_free_required_bytes']==27000000000+(256<<20),'initial-only B cache admission')
  require(plan['requests']==plan['suite']['requests']==2 and plan['suite']['max_new']==32 and plan['suite']['modes']==['none','mtp'] and not plan['suite']['historical_bf16_state_oracle'],'fixed new-baseline scope')
  for mapping in (plan['source_sha256'],plan['suite']['source_sha256'],plan['adapter']['source_sha256']):
   for f,h in mapping.items():require(sha(R/f)==h,'source '+f)
  native=read(plan['adapter']['build_receipt']);require(sha(plan['adapter']['build_receipt'])==plan['adapter']['build_receipt_sha256'] and native['passed'] and native['objects_rebuilt']==21 and native['objects_reused']==19,'corrected native build')
  require(sha(plan['adapter']['binary'])==native['binary_sha256']==plan['adapter']['binary_sha256']==BINARY,'binary')
  for mapping in (native['source_sha256'],native['objects']):
   for f,h in mapping.items():require(sha(R/f)==h,'compiled source/object')
  require(plan['adapter']['storage']['raw_state_bytes']==960190668 and plan['adapter']['storage']['evidence_forecast_bytes']==960190668+(128<<20),'three capture forecast')
  for rank in (0,1):
   launch=read(CONTROL/f'ranks/rank{rank}-launch.json');require(launch['argv'].count('--recurrent-f32')==1,'actual precision flag')
  fp=Path(term['result']['full_result_path']);require(fp==EVIDENCE/'f32-correctness.json' and sha(fp)==term['result']['full_result_sha256'],'full result identity');full=read(fp)
  require(full['passed'] and full['requests']==2 and len(full['rows'])==len(full['capture_snapshots'])==2 and full['normal_FINISH_and_closed_payload_verified'],'closed two-arm result');require(full['rank_pids']==[x[0] for x in term['rank_identities']],'same owners');budget_ok(full['capture_budget'])
  expected={f'{prefix}rank{rank}/state-2147483647':{} for prefix in ('','prompt-00-none/','prompt-00-mtp/') for rank in (0,1)}
  require(sha(INDEX)==INDEX_SHA,'original inventory geometry authority')
  with gzip.open(INDEX,'rt') as f:
   for line in f:
    x=json.loads(line);rel=Path(x['path']);parent=str(rel.parent)
    if x['root']=='evidence' and parent in expected:
     require(rel.name not in expected[parent],'duplicate inventory');row=dict(x);row['bytes']=corrected_extent(rel.name,row['bytes']);expected[parent][rel.name]=row
  # Historical hashes are deliberately not an oracle; only fixed names and corrected lengths are used.
  paths=[];total=0
  for label,root in [('control',CONTROL),('evidence',EVIDENCE)]:
   for f in sorted(root.rglob('*')):
    st=f.lstat();require(not stat.S_ISLNK(st.st_mode),'artifact symlink')
    if stat.S_ISDIR(st.st_mode):continue
    require(stat.S_ISREG(st.st_mode),'regular artifact');paths.append((label,root,f,st));total+=st.st_size;require(total<=2<<30 and len(paths)<=3000,'readback2GiB/3000 bounds')
  require({str(f.relative_to(EVIDENCE)) for _,root,f,_ in paths if root==EVIDENCE and f.name=='state.bundle'}=={k+'/state.bundle' for k in expected},'exact six bundles')
  got={};physical={};captures=[];lowbits=0;recurrent_count=0
  for rel,exp in expected.items():
   d=EVIDENCE/rel;x=S.stream_bundle(d,exp,semantic_oracle=False);got[rel]=x;rank=int(rel.split('rank')[-1].split('/')[0]);require(x['payload_bytes']==(184765556,125598668)[rank],'new typed target extent')
   recurrent_count+=len(x['recurrent_precision']);lowbits+=sum(z['non_bf16_words'] for z in x['recurrent_precision'].values()) if rel.startswith('prompt-') else 0
   for name,h in x['physical_sha256'].items():physical[str(d/name)]=h
   captures.append({'path':rel,'payload_bytes':x['payload_bytes'],'ranges':x['ranges'],'f32_ranges':x['recurrent_precision'],'physical_sha256':x['physical_sha256']})
  require(recurrent_count==330 and lowbits>0,'actual full F32 recurrent inventory/non-BF16 storage')
  refpath=L/'reference-cpu/runtime-b/evidence/closed-readback-review.json';ref=read(refpath);require(ref['evidence_review_passed'] and ref['output_tokens']==plan['suite']['reference_tokens'],'independent reference binding')
  arms=[]
  for i,(row,mode) in enumerate(zip(full['rows'],('none','mtp'))):
   name='prompt-00-'+mode;require(row['name']==name and row['mode']==mode and row['requested_max_new']==32 and row['prompt_tokens']==plan['suite']['prompt_tokens'] and len(row['prompt_tokens'])==87,'request identity')
   tokens=row['result']['tokens'];require(0<len(tokens)<=32,'natural EOS/cap bounds');raw_join(read(EVIDENCE/name/'request-result.json'),row)
   for rank in (0,1):
    x=got[f'{name}/rank{rank}/state-2147483647'];require(x['logical_map']==row['state_sha256'][str(rank)] and x['snapshots']==full['capture_snapshots'][i][str(rank)],'closed state/stamp')
    reset=read(EVIDENCE/name/f'rank{rank}/reset.json');require(reset['passed'] and reset['allocation_ids_preserved'],'RESET acknowledgement')
   B.timing(row['result'],len(tokens));B.confirmed_inputs(row['result'],row['prompt_tokens'])
   if mode=='mtp':B.guess_outcomes(row['result'],row['prompt_tokens'],len(tokens))
   else:require(all(row['result']['stats'][k]==0 for k in ('guesses','hits','misses')),'target-only stats')
   reference_equal=tokens==ref['output_tokens'];first=next((j for j,(x,y) in enumerate(zip(tokens,ref['output_tokens'])) if x!=y),None)
   if first is None and len(tokens)!=len(ref['output_tokens']):first=min(len(tokens),len(ref['output_tokens']))
   require(row['reference_comparison']['equal']==reference_equal and row['reference_comparison']['reference_tokens']==ref['output_tokens'] and row['reference_comparison']['first_difference']==first,'reference comparison truth')
   arms.append({'name':name,'mode':mode,'tokens':tokens,'stats':row['result']['stats'],'reference_equal':reference_equal,'reference_first_difference':first,'scope':'Only this87-token input/32 cap; no general quality or bitwise-logit claim'})
  require(arms[0]['tokens']==arms[1]['tokens'] and full['rows'][0]['state_sha256']==full['rows'][1]['state_sha256'] and full['corrected_target_mtp_exact'],'new target/MTP exact')
  require(full['reference_equal']==arms[0]['reference_equal'],'full reference flag')
  owners=[];memory=[]
  for rank in (0,1):
   r=read(EVIDENCE/f'rank{rank}/receipt.json');require(r['passed'] and r['rank']==rank and r['device_executed'] and not r['error'] and len(r['teardown'])==1,'native owner');t=r['teardown'][0];require(t['safe_to_exit'] and t['in_flight']==t['live_bytes']==t['exit_code']==0,'safe teardown');owners.append({k:t[k] for k in ('status','safe_to_exit','in_flight','live_bytes','exit_code')})
   c=read(EVIDENCE/f'rank{rank}/census.json');n=sum(a['bytes'] for a in c['allocations'] if a['live'] and a['memory']=='device');require(n==c['totals']['device']==(31083481994,29995470740)[rank],'new actual allocation census');memory.append(n)
  owner=read(EVIDENCE/'ownership.json');require(owner['returncodes']==[0,0] and not owner['retained_pids'] and owner['signals_sent']==0 and not owner['stop_requested'] and not owner['diagnostic_errors'],'clean process closure')
  with (D/'artifact-index.jsonl.gz').open('xb') as raw,gzip.GzipFile(fileobj=raw,mode='wb',filename='',mtime=0) as z:
   for label,root,f,st in paths:
    h=physical[str(f)] if str(f) in physical else sha(f);require(S.stamp(f.stat())==S.stamp(st),'artifact changed');z.write((json.dumps({'root':label,'path':str(f.relative_to(root)),'bytes':st.st_size,'sha256':h},separators=(',',':'))+'\n').encode())
  receipt.update(passed=True,plan_sha256=PLAN_SHA,native_binary_sha256=BINARY,full_result_sha256=sha(fp),arms=arms,corrected_target_mtp_exact=True,reference32_equal=arms[0]['reference_equal'],reference_review_sha256=sha(refpath),captures=captures,target_bundles=6,f32_ranges=recurrent_count,non_bf16_f32_words=lowbits,actual_device_bytes=memory,owners=owners,ownership=owner,rank_identities=term['rank_identities'],physical_drain=True,kernel_fault_baseline_unchanged=True,artifact_count=len(paths),indexed_bytes=total,index_sha256=sha(D/'artifact-index.jsonl.gz'),capture_budget=full['capture_budget'],quality_qualified=False)
 except BaseException as e:receipt['error']=repr(e);raise
 finally:
  receipt.update(auditor_sha256=sha(__file__),bundle_scan_sha256=sha(P/'bundle_scan.py'),elapsed_seconds=time.monotonic()-start)
  with (D/'review.json').open('x') as f:json.dump(receipt,f,indent=2);f.write('\n')
 print(json.dumps({'passed':True,'review_sha256':sha(D/'review.json')}))
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--run',action='store_true',required=True);ap.parse_args();run()
