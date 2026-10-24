#!/usr/bin/env python3
"""Closed current-attribution diagnostic readback; invoke only after root drain authorization.

One stream per payload supplies both range and physical-file hashes. No runtime,
operational adapter, device API, service query or model payload is imported.
"""
from pathlib import Path
import argparse,gzip,hashlib,importlib.util,json,math,os,re,resource,stat,time

D=Path(__file__).resolve().parent;P=D.parents[1];L=P.parents[1];R=L.parents[2]
CONTROL=Path('/home/steve/own-xpu-runtime-results/gsq-current-attribution-a.control')
EVIDENCE=Path('/mnt/usb-models/own-xpu-runtime-results/gsq-current-attribution-a')
PLAN_SHA='1c1512c80116979b4e336e2b708c01b63886d1b4c6579cac1a35fd5ceb51f0a5'
BINARY='5a8c9d3b58606022e21e2f0347360e4dd9cfdf6a869c8daac145e928fe4d4306'
PRIOR=L/'baseline/evidence/independent-a/review.json'
PRIOR_SHA='f662fcecf93c92f90006c09c05d4a4c02e71e84ae9d8c82dbff3fdfc39ebb5bb'
OLD_INDEX=PRIOR.parent/'artifact-index.jsonl.gz'
OLD_INDEX_SHA='e8137dddb0929d5476d27a8a774539a77d595aeb296e9d0ec778ceec066a6982'
REFERENCE=Path('/mnt/usb-models/own-xpu-runtime-results/gsq-baseline-a/resident-suite.json')
BASE=L/'baseline/audit.py';BASE_SHA='43154e5b8101fb879eb08bbbebc29714443dd083cb90df6fbbb7e269d522d0ab'
assert hashlib.sha256(BASE.read_bytes()).hexdigest()==BASE_SHA
s=importlib.util.spec_from_file_location('closed_bundle_baseline_helpers',BASE);B=importlib.util.module_from_spec(s);s.loader.exec_module(B)
sha,read,require=B.sha,B.read,B.require
FILES={'state.bundle','state-index.tsv','state.json','state-seal.txt'}
CAP=256*1024**2;META=1024**2

def stamp(s):return (s.st_dev,s.st_ino,s.st_size,s.st_mode,s.st_nlink,s.st_mtime_ns,s.st_ctime_ns)
def snapshot(s):return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
def unique(items):
 out={}
 for k,v in items:require(k not in out,'duplicate JSON key');out[k]=v
 return out
def digest(b):return hashlib.sha256(b).hexdigest()
def number(s):
 require(re.fullmatch(r'0|[1-9][0-9]{0,9}',s) is not None,'canonical extent');v=int(s);require(v<=CAP,'extent bound');return v

def stream_bundle(path,expected,semantic_oracle=True):
 """Independent range parser with authoritative original per-name byte lengths."""
 require(set(expected) and 'state.json' in expected,'original inventory')
 fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC);opened={};stamps={};physical={}
 try:
  ds=os.fstat(fd);require(set(os.listdir(fd))==FILES,'sealed four-file inventory')
  for name in sorted(FILES):
   f=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=fd);opened[name]=f;st=os.fstat(f)
   require(stat.S_ISREG(st.st_mode) and st.st_nlink==1 and 0<=st.st_size<=(CAP if name=='state.bundle' else META),'bounded regular file');stamps[name]=st
  def small(name):
   chunks=[];left=stamps[name].st_size
   while left:
    b=os.read(opened[name],min(65536,left));require(b,'metadata truncation');chunks.append(b);left-=len(b)
   value=b''.join(chunks);physical[name]=digest(value);return value
  seal=small('state-seal.txt');require(seal.endswith(b'\n'),'seal newline');fields=seal.decode('ascii')[:-1].split('\n')
  require(len(fields)==5 and fields[0]=='GSQ_STATE_SEAL_V1','seal fields');length=number(fields[1])
  require(all(re.fullmatch('[0-9a-f]{64}',h) for h in fields[2:]),'seal digests')
  index=small('state-index.tsv');state=small('state.json')
  require(digest(index)==fields[3] and digest(state)==fields[4],'metadata seal')
  if semantic_oracle:require(len(state)==expected['state.json']['bytes'] and digest(state)==expected['state.json']['sha256'],'byte-exact baseline state.json')
  obj=json.loads(state,object_pairs_hook=unique);require(type(obj.get('buffers')) is dict,'state inventory')
  state_names={}
  for key,h in obj['buffers'].items():
   name=('alternate-'+key.split(':',1)[1] if key.startswith('alternate:') else key)+'.bin'
   require(name not in state_names,'aliased state names');state_names[name]=h
  require(set(state_names)==set(expected)-{'state.json'},'all original buffer names')
  require(index.endswith(b'\n'),'index newline');lines=index.decode('ascii')[:-1].split('\n')
  require(lines[0]=='GSQ_STATE_BUNDLE_V1' and len(lines)==len(expected) and 0<len(state_names)<=4096,'bounded complete index')
  require(length==stamps['state.bundle'].st_size==sum(x['bytes'] for k,x in expected.items() if k!='state.json'),'original total payload extent')
  seen={};offset=0;whole=hashlib.sha256()
  for line in lines[1:]:
   parts=line.split('\t');require(len(parts)==4,'index row fields');name,start,size,h=parts
   require(name in state_names and name not in seen and h==state_names[name],'exact indexed range name/hash')
   if semantic_oracle:require(h==expected[name]['sha256'],'original baseline range hash')
   start=number(start);size=number(size);require(start==offset and size==expected[name]['bytes'] and size<=length-offset,'exact original length/contiguous range')
   part=hashlib.sha256();left=size
   while left:
    data=os.read(opened['state.bundle'],min(left,256*1024));require(data,'payload truncated');whole.update(data);part.update(data);left-=len(data)
   require(part.hexdigest()==h,'actual range bytes differ');seen[name]=h;offset+=size
  require(offset==length and not os.read(opened['state.bundle'],1) and whole.hexdigest()==fields[2],'complete physical payload')
  physical['state.bundle']=whole.hexdigest();seen['state.json']=digest(state)
  for name,f in opened.items():require(stamp(os.fstat(f))==stamp(stamps[name])==stamp(os.stat(name,dir_fd=fd,follow_symlinks=False)),'file changed during streaming')
  now=os.stat(path,follow_symlinks=False);require(stat.S_ISDIR(now.st_mode) and (now.st_dev,now.st_ino)==(ds.st_dev,ds.st_ino) and set(os.listdir(fd))==FILES,'directory changed')
  differences=[n for n,h in seen.items() if h!=expected[n]['sha256']]
  return dict(logical_map=seen,physical_sha256=physical,snapshots={n:snapshot(st) for n,st in stamps.items()},payload_bytes=length,ranges=len(state_names),semantic_baseline_required=semantic_oracle,baseline_hash_differences=differences,state_json_original_length_equal=len(state)==expected['state.json']['bytes'])
 finally:
  for f in opened.values():os.close(f)
  os.close(fd)

def run():
 require(os.getpriority(os.PRIO_PROCESS,0)==19 and os.sched_getaffinity(0)<=set(range(8,16))|set(range(24,32)),'helper placement')
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
 require(not (D/'review.json').exists() and not (D/'artifact-index.jsonl.gz').exists(),'exclusive review')
 start=time.monotonic();receipt=dict(schema='gsq.current-attribution.independent-device.v1',passed=False,no_speed_claim=True,device_executed_by_reviewer=False)
 try:
  require(sha(PRIOR)==PRIOR_SHA and sha(OLD_INDEX)==OLD_INDEX_SHA,'independent original authorities');prior=read(PRIOR)
  require(prior['passed'] and prior['all12_exact'] and prior['index_sha256']==OLD_INDEX_SHA and sha(REFERENCE)==prior['full_result_sha256'],'baseline receipt/result')
  refs={a['name']:a for p in read(REFERENCE)['prompts'] for a in p['arms']}
  plan=read(CONTROL/'plan.json');ad=read(CONTROL/'admission.json');terminal=read(CONTROL/'terminal.json')
  require(sha(CONTROL/'plan.json')==ad['plan_sha256']==terminal['plan_sha256']==PLAN_SHA and ad['plan']==plan,'exact launch plan')
  require(digest(json.dumps(plan,sort_keys=True,separators=(',',':')).encode())==ad['canonical_plan_sha256'],'canonical plan')
  for k,v in plan['unit_properties'].items():require(ad['unit'][k]==v,'safe unit property')
  B.validate_passive(ad['before'],terminal['after'],terminal)
  require(plan['requests']==plan['suite']['requests']==2 and plan['suite']['retained_state_dumps']==3 and plan['suite']['measured_requests']==1 and plan['suite']['timing']=='attribution','fixed two-arm/three-capture scope')
  require(plan['suite']['baseline_review_sha256']==PRIOR_SHA and plan['suite']['baseline_result_sha256']==prior['full_result_sha256'],'baseline admission')
  require(plan['adapter']['storage']['raw_state_bytes']==694327500 and plan['adapter']['storage']['evidence_forecast_bytes']==828545228,'three-capture storage forecast')
  for mapping in (plan['source_sha256'],plan['suite']['source_sha256'],plan['adapter']['source_sha256']):
   for p,h in mapping.items():require(sha(R/p)==h,'source pin '+p)
  native=read(plan['adapter']['build_receipt']);require(native['passed'] and native['mode']=='native' and sha(plan['adapter']['build_receipt'])==plan['adapter']['build_receipt_sha256'],'native receipt')
  require(sha(plan['adapter']['binary'])==native['binary_sha256']==plan['adapter']['binary_sha256']==BINARY,'native binary')
  for mapping in (native['source_sha256'],native['object_sha256']):
   for p,h in mapping.items():require(sha(R/p)==h,'compiled source/object '+p)
  fullpath=Path(terminal['result']['full_result_path']);require(fullpath==EVIDENCE/'profile-result.json' and sha(fullpath)==terminal['result']['full_result_sha256'],'closed result identity');full=read(fullpath)
  require(full['passed'] and full['requests']==2 and len(full['rows'])==len(full['capture_snapshots'])==2 and full['no_speed_claim'],'completed qualification')
  require(full['warmup_RESET_redump_verified'] and full['last_arm_explicit_DUMP_repeat_verified'] and full['normal_FINISH_and_closed_payload_verified'],'successful repeat/closure evidence')
  require(full['rank_pids']==[x[0] for x in terminal['rank_identities']],'same two rank owners')
  roots=[EVIDENCE,EVIDENCE/'warmup-none',EVIDENCE/'prompt-00-none'];expected={}
  for base in roots:
   for rank in (0,1):expected[str((base/f'rank{rank}/state-2147483647').relative_to(EVIDENCE))]={}
  with gzip.open(OLD_INDEX,'rt') as f:
   for line in f:
    x=json.loads(line)
    if x['root']!='evidence':continue
    rel=Path(x['path']);parent=str(rel.parent)
    if parent in expected:
     require(rel.name not in expected[parent],'duplicate original indexed member');expected[parent][rel.name]=x
  rawpaths=[];total=0
  for label,root in [('control',CONTROL),('evidence',EVIDENCE)]:
   for p in sorted(root.rglob('*')):
    st=p.lstat();require(not stat.S_ISLNK(st.st_mode),'artifact symlink')
    if stat.S_ISDIR(st.st_mode):continue
    require(stat.S_ISREG(st.st_mode),'nonregular artifact');total+=st.st_size;rawpaths.append((label,root,p,st))
    require(total<=1024**3 and len(rawpaths)<=2000,'bounded1GiB/2000file readback')
  require({str(p.relative_to(EVIDENCE)) for _,root,p,_ in rawpaths if root==EVIDENCE and p.name=='state.bundle'}=={n+'/state.bundle' for n in expected},'exact six bundles')
  reconstructed={};physical={};captures=[]
  for relative,original in expected.items():
   path=EVIDENCE/relative;got=stream_bundle(path,original,semantic_oracle=relative.startswith('prompt-'));reconstructed[relative]=got
   for name,h in got['physical_sha256'].items():physical[str(path/name)]=h
   captures.append(dict(path=relative,payload_bytes=got['payload_bytes'],ranges=got['ranges'],baseline_semantic_oracle_required=got['semantic_baseline_required'],baseline_hash_differences=got['baseline_hash_differences'],state_json_original_length_equal=got['state_json_original_length_equal'],inventory_and_lengths_exact=True,physical_sha256=got['physical_sha256']))
  with (D/'artifact-index.jsonl.gz').open('xb') as raw,gzip.GzipFile(fileobj=raw,mode='wb',filename='',mtime=0) as z:
   for label,root,p,before in rawpaths:
    h=physical[str(p)] if str(p) in physical else sha(p);require(stamp(p.stat())==stamp(before),'artifact changed since inventory')
    z.write((json.dumps(dict(root=label,path=str(p.relative_to(root)),bytes=before.st_size,sha256=h),separators=(',',':'))+'\n').encode())
  arms=[]
  for i,(row,name,cap) in enumerate(zip(full['rows'],('warmup-none','prompt-00-none'),(8,128))):
   base=EVIDENCE/name;measured=name=='prompt-00-none'
   require(row['name']==name and row['mode']=='none' and row['requested_max_new']==cap and row['excluded']==(not measured),'fixed diagnostic schedule')
   if measured:
    ref=refs[name];require(row['prompt_tokens']==plan['suite']['prompt_tokens']==ref['prompt_tokens'] and row['result']['tokens']==ref['result']['tokens'] and row['state_sha256']==ref['state_sha256'],'measured exact original arm')
   else:require(row['prompt_tokens']==plan['suite']['warmup']['tokens'] and len(row['result']['tokens'])==8,'disjoint excluded warmup')
   require(read(base/'request-result.json')==row,'raw arm/result join')
   for rank in (0,1):
    key=f'{name}/rank{rank}/state-2147483647';got=reconstructed[key]
    require(got['logical_map']==row['state_sha256'][str(rank)] and got['snapshots']==full['capture_snapshots'][i][str(rank)],'closed payload map/stamp unchanged')
    reset=read(base/f'rank{rank}/reset.json');require(reset['passed'] and reset['allocation_ids_preserved'],'positive RESET')
   B.timing(row['result'],cap,eos=measured);consumed=B.confirmed_inputs(row['result'],row['prompt_tokens'])
   require(all(row['result']['stats'][k]==0 for k in ('guesses','hits','misses')),'target-only stats')
   if measured:require(consumed==214 and len(row['prompt_tokens'])==87 and len(row['result']['tokens'])==128,'whole-request214positions')
   arms.append(dict(name=name,excluded=not measured,mode='none',tokens=row['result']['tokens'],stats=row['result']['stats'],consumed_positions=consumed,baseline_tokens_exact=measured,baseline_state_exact=measured))
  source_pins=read(P/'source-pins.json')
  for name,h in source_pins.items():require(sha(R/name)==h,'attribution source authority')
  graph=read(L/'graph/new-plan.json');tensors=read(L/'metadata/new-census.json')['tensors'];sites={}
  for site in graph['launches']:
   require(site['label'] not in sites,'unique graph label');sites[site['label']]=dict(op=site['op'],weights=[dict(name=w,type=tensors[w]['type'],dimensions=tensors[w]['dimensions']) for w in site['weights']])
  reports={};global_sums={};event_total=0
  for rank in (0,1):
   path=EVIDENCE/f'prompt-00-none/rank{rank}/sites.jsonl';require(path.stat().st_size<=32*1024**2,'bounded event stream')
   raw=path.read_bytes();rows=[]
   for line in raw.splitlines():
    require(0<len(line)<=16384,'bounded event row');rows.append(json.loads(line,object_pairs_hook=unique));require(len(rows)<=100000,'bounded event count')
   retained=full['classes'][str(rank)];require(retained['path']==str(path) and retained['sha256']==digest(raw),'raw attribution binding')
   halves={};events=[];ids=set();coverage=set();labels={};formats={}
   for row in rows:
    require(row['schema'] in ('packet65.event.v1','packet65.half.v1'),'known event schema')
    fixture=row['fixture'];position=row['position'];half=row['half']
    require(type(fixture)is int and 9<=fixture<=16 and type(position)is int and position==87+fixture-2,'actual controller sample equation')
    require(type(half)is int and half>0 and row['rank']==rank and row['speculative'] is False,'target rank/half identity')
    if row['schema']=='packet65.half.v1':
     require(half not in halves and row['cancelled'] is False,'unique successful half');halves[half]=(fixture,position)
    else:
     eid=row['event'];require(type(eid)is int and eid>0 and eid not in ids,'unique native event');ids.add(eid)
     require(row['diagnostic'] is True and row['class']=='moe_experts','recorder identity')
     label=row['label'];require(label in sites and label.startswith('blk.'),'exact graph label')
     require(not any(x in label for x in ('shexp','shared','hc.','norm','final.','merge.')) and any(x in label for x in ('gather','moe','exps','expert','router','route','ffn.')),'actual routed predicate')
     layer=int(label.split('.')[1]);require(rank*24<=layer<(rank+1)*24,'owned layer')
     start_ns,end_ns=row['start_ns'],row['end_ns'];require(type(start_ns)is int and type(end_ns)is int and 0<start_ns<=end_ns and end_ns-start_ns<=4000000000,'finite bounded timing')
     events.append(row)
   require(len(halves)==8 and set(halves.values())=={(f,87+f-2) for f in range(9,17)},'eight measured generated halves')
   for row in events:
    require(halves.get(row['half'])==(row['fixture'],row['position']),'exact event/half join')
    label=row['label'];site=sites[label];weights=site['weights'];fmt=weights[0]['type'] if len(weights)==1 else 'none' if not weights else 'mixed';key=(label.split('.',2)[2],fmt);duration=row['end_ns']-row['start_ns'];coverage.add((row['fixture'],label))
    for table,k in ((labels,label),(formats,key),(global_sums,key)):
     item=table.setdefault(k,dict(event_count=0,device_ns=0));item['event_count']+=1;item['device_ns']+=duration
   for fixture in range(9,17):
    for layer in range(rank*24,(rank+1)*24):
     for name in ('expsgate','expsup','expsdown'):require((fixture,f'blk.{layer}.{name}') in coverage,'complete expert projection coverage')
   by_label=[dict(label=k,**v,**sites[k],device_ms=v['device_ns']/1e6) for k,v in sorted(labels.items())]
   by_format=[dict(class_name=k[0],format=k[1],**v,device_ms=v['device_ns']/1e6) for k,v in sorted(formats.items())]
   report=dict(rank=rank,fixtures=list(range(9,17)),absolute_positions=list(range(94,102)),half_count=8,event_count=len(events),device_ns=sum(v['device_ns'] for v in labels.values()),by_label=by_label,by_class_format=by_format)
   require(report['event_count']>0 and report['device_ns']>0,'nonvacuous attribution')
   for key,value in report.items():require(retained['report'][key]==value,'independent attribution aggregate '+key)
   reports[str(rank)]=dict(stream_sha256=digest(raw),**report);event_total+=len(events)
  joined=[dict(class_name=k[0],format=k[1],**v,device_ms=v['device_ns']/1e6) for k,v in sorted(global_sums.items())]
  require(joined==full['sampled_by_class_format'],'independent both-rank class/format sums')
  require(sum(x['device_ns'] for x in joined)==sum(x['device_ns'] for x in reports.values()),'all event durations conserved')
  ledger=read(L/'qkv-q6-p33/engine/operating/candidate-ledger.json')['scenarios']['split24-24_mtp-rank0']['ranks'];owners=[];memory=[]
  for rank in (0,1):
   owner=read(EVIDENCE/f'rank{rank}/receipt.json');require(owner['passed'] and owner['rank']==rank and not owner['error'] and len(owner['teardown'])==1,'clean owner')
   t=owner['teardown'][0];require(t['safe_to_exit'] and t['in_flight']==t['live_bytes']==t['exit_code']==0,'safe owner teardown');owners.append({k:t[k] for k in ('status','safe_to_exit','in_flight','live_bytes','exit_code')})
   census=read(EVIDENCE/f'rank{rank}/census.json');amount=sum(a['bytes'] for a in census['allocations'] if a['live'] and a['memory']=='device');require(amount==census['totals']['device']==ledger[rank]['device_logical_bytes'],'unchanged allocation census');memory.append(amount)
  ownership=read(EVIDENCE/'ownership.json');require(ownership['returncodes']==[0,0] and not ownership['retained_pids'] and ownership['signals_sent']==0 and not ownership['stop_requested'],'clean process closure')
  receipt.update(passed=True,requests=2,measured_requests=1,captures=3,bundles=6,arms=arms,attribution_reports=reports,sampled_by_class_format=joined,event_count=event_total,sampled_fixtures=list(range(9,17)),sampled_positions=list(range(94,102)),attribution_source_sha256=source_pins,consumed_positions=214,bundle_captures=captures,measured_arm_state_json_bytes_exact=True,all_original_buffer_lengths_exact=True,initial_capture_semantic_baseline_required=False,explicit_repeat_and_closed_stamp_verified=True,baseline_review_sha256=PRIOR_SHA,baseline_index_sha256=OLD_INDEX_SHA,plan_sha256=PLAN_SHA,native_binary_sha256=BINARY,full_result_sha256=sha(fullpath),rank_identities=terminal['rank_identities'],owners=owners,ownership=ownership,actual_device_bytes=memory,physical_drain=True,kernel_fault_baseline_unchanged=True,artifact_count=len(rawpaths),indexed_bytes=total,index_sha256=sha(D/'artifact-index.jsonl.gz'),limitations=['Initial and warmup capture hashes are informational versus baseline; sealed bytes, full inventory and original buffer lengths remain verified.','One fixed prompt00 target-only attribution diagnostic, with excluded disjoint warmup; exact prior-baseline state/tokens. Event totals cover only eight early generated positions94..101 and routed labels. No prefill, whole-decode extrapolation, copy-completeness, speed or general-quality claim.','Closure uses retained successful DUMP/RESET/FINISH and owner/drain evidence; a seal alone is insufficient.','No model weights read or GPU/service operations by reviewer; physical host findings use retained monitor evidence.'])
 except BaseException as e:receipt['error']=type(e).__name__+': '+str(e);raise
 finally:
  receipt.update(auditor_sha256=sha(__file__),parent_auditor_sha256=BASE_SHA,derivative_source_sha256="a0d6818704f617ed89d8d4f69bca6e573c321bfa5512893687829ee1ef3b4ef9",elapsed_seconds=time.monotonic()-start)
  with (D/'review.json').open('x') as f:json.dump(receipt,f,indent=2);f.write('\n')
 print(json.dumps(dict(passed=True,review_sha256=sha(D/'review.json'))))

if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',action='store_true',required=True);ap.parse_args();run()
