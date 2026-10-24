#!/usr/bin/env python3
"""Explicit closed micro readback; stdlib only, no operational imports."""
import argparse,collections,gzip,hashlib,json,os,resource,stat,statistics,time
from pathlib import Path
R=Path('/home/steve/llm-optimizations');P=R/'experiments/own-xpu-runtime/gsq-rco-iq3s/dense-packed-block/micro';O=P/'operating';S=Path('/home/steve/own-xpu-runtime-results/gsq-dense-packed-block-micro-a');D=O/'evidence/device-a'
PLAN_SHA=None
BUILD_SHA=None
BINARY_SHA=None
PARENT=Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/hc-bf16-one-sg/micro/operating/evidence/device-a/audit.py');PARENT_SHA='01c8b44723ab8e45efdde748d113fc4ffb6a292428a8cd338c9b2fa8d213b694'
index={}
def need(v,m):
 if not v:raise ValueError(m)
def stamp(s):return(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
def digest(path):
 p=Path(path);p=p if p.is_absolute() else R/p;fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
 with os.fdopen(fd,'rb') as f:
  before=os.fstat(f.fileno());need(stat.S_ISREG(before.st_mode),'regular artifact');h=hashlib.sha256()
  while b:=f.read(1024*1024):h.update(b)
  need(stamp(before)==stamp(os.fstat(f.fileno()))==stamp(p.stat(follow_symlinks=False)),'artifact changed')
 index[str(p)]=dict(path=str(p),bytes=before.st_size,sha256=h.hexdigest());return h.hexdigest()
def read(p):
 h=digest(p);raw=Path(p).read_bytes();need(hashlib.sha256(raw).hexdigest()==h,'metadata reread changed');return json.loads(raw)
def pins(m):
 for p,h in m.items():need(digest(p)==h,'source/artifact pin '+p)
def ack_join(ready,ack,contact,native):
 need(ready==ack and 0<len(ready)<=256,'ACK exact challenge bytes');fields=ready.decode('ascii').split()
 need(len(fields)==4 and fields[0]=='GSQ_NATIVE_BACKEND_READY_V1' and ready==(' '.join(fields)+'\n').encode(),'canonical backend readiness')
 need((int(fields[1]),int(fields[2]))==tuple(native) and len(fields[3])==32 and all(x in '0123456789abcdef' for x in fields[3]),'ACK native identity/nonce')
 need(contact['native_identity']==native and contact['ready_sha256']==hashlib.sha256(ready).hexdigest(),'durable accepted-contact challenge')
 h=contact['native_holders'];snap=contact['snapshot'];need(h,'positive native descriptors')
 for row in h:
  need((row['pid'],snap['holders'][str(row['pid'])]['start_ticks'])==tuple(native),'physical PID/startticks')
  need(row in snap['inventory']['holders'] and snap['drm'][row['node']]['bdf']=='0000:23:00.0','actual target descriptor in accepted sample')
 return True
def samples_check(rows,manifest):
 expected=[dict(warmup=warm,cycle=cycle,case=((cycle//2)+j)%3,order=['B','A'] if cycle%2 else ['A','B']) for warm,n in ((True,4),(False,24)) for cycle in range(n) for j in range(3)]
 need(len(rows)==84 and manifest['schedule']==expected,'all84 preregistered pairs')
 need([(c['label'],c['type_id'],c['rows'],c['columns']) for c in manifest['cases']]==[('blk.0.gdn.z',12,6144,2560),('blk.1.gdn.qkv',13,10240,2560),('blk.2.gdn.z',23,6144,2560)],'fixed three format/shape cases')
 previous=0
 for row,want in zip(rows,expected):
  case=manifest['cases'][want['case']]
  need((row['warmup'],row['cycle'],row['layer'],row['order'],row['label'])==(want['warmup'],want['cycle'],want['case'],''.join(want['order']),case['label']),'fixed phase/cycle/case/order')
  need(row['exact'] and row['A_sha256']==row['B_sha256']==row['expected_sha256']==case['fixtures']['expected']['sha256'],'exact full output')
  need(case['fixtures']['expected']['bytes']==case['rows']*2 and case['fixtures']['input']['bytes']==5120,'full dense output/input extent')
  first,second=row['order'];need(previous<row[first+'_start_ns']<row[first+'_end_ns']<row[second+'_start_ns']<row[second+'_end_ns'],'strict native event ordering');previous=row[second+'_end_ns']
 measured=[r for r in rows if not r['warmup']];warm=[r for r in rows if r['warmup']]
 for case in manifest['cases']:
  m=[r for r in measured if r['label']==case['label']];w=[r for r in warm if r['label']==case['label']]
  need(len(m)==24 and len(w)==4 and collections.Counter(r['order'] for r in m)=={'AB':12,'BA':12} and collections.Counter(r['order'] for r in w)=={'AB':2,'BA':2},'each case balanced all-sample schedule')
 return measured
def stats(v):return dict(count=len(v),mean=statistics.mean(v),median=statistics.median(v),minimum=min(v),maximum=max(v))
def aggregate(rows):
 a=[r['A_end_ns']-r['A_start_ns'] for r in rows];b=[r['B_end_ns']-r['B_start_ns'] for r in rows]
 return dict(pairs=len(rows),A_ns=stats(a),B_ns=stats(b),B_over_A_paired=stats([y/x for x,y in zip(a,b)]),B_over_A_sum=sum(b)/sum(a))
def per_case(rows):
 return {label:dict(all=aggregate([r for r in rows if r['label']==label]),by_order={order:aggregate([r for r in rows if r['label']==label and r['order']==order]) for order in ('AB','BA')}) for label in ('blk.0.gdn.z','blk.1.gdn.qkv','blk.2.gdn.z')}
def run():
 need(os.getpriority(os.PRIO_PROCESS,0)==19 and os.sched_getaffinity(0)<=set(range(8,16))|set(range(24,32)),'helper placement');resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));D.mkdir(parents=True,exist_ok=True);need(not(D/'review.json').exists() and not(D/'artifact-index.jsonl.gz').exists(),'exclusive audit')
 need(all(isinstance(h,str) and len(h)==64 and all(c in '0123456789abcdef' for c in h) for h in (PLAN_SHA,BUILD_SHA,BINARY_SHA)),'root actual plan/build/binary binding pending');need(digest(PARENT)==PARENT_SHA,'qualified parent auditor source')
 receipt=dict(schema='gsq.dense-packed-block.closed-review.v1',passed=False,device_executed_by_reviewer=False);start=time.monotonic()
 try:
  ad=read(S/'admission.json');term=read(S/'terminal.json');mon=read(S/'monitor.json');result=read(S/'result/result.json');manifest=read(O/'manifest.json');build=read(P/'evidence/native-build.json')
  planfile=S/'plan.json';need(digest(planfile)==PLAN_SHA and read(planfile)==ad['plan'],'admitted fixed plan');pins(ad['plan']['source_sha256']);pins(manifest['authority'])
  for key in ('source_sha256','objects_reused','dependencies'):pins(build[key])
  need(digest(build['binary'])==build['binary_sha256']==ad['binary_sha256']==BINARY_SHA,'native binary identity');need(digest(P/'evidence/native-build.json')==ad['proof_sha256']==BUILD_SHA,'native build');need(digest(O/'once.py')==ad['monitor_sha256'],'operating source')
  review=read(O/'evidence/independent-review.json');need(review['passed'] and review['binary_sha256']==BINARY_SHA and review['native_build_sha256']==BUILD_SHA,'final independent prerequisites');pins(review['source_sha256'])
  need(len(manifest['cases'])==3 and (manifest['pairs'],manifest['kernels'],manifest['device_bytes'],manifest['transfer_bytes'],manifest['pinned_bytes'])==(84,168,35331072,37764096,1048576),'fixed schedule/ledger')
  for c in manifest['cases']:
   need(digest(c['packed_weights']['path'])==c['packed_weights']['sha256'],'authenticated copied complete tensor')
   for f in c['fixtures'].values():need(digest(f['path'])==f['sha256'] and Path(f['path']).stat().st_size==f['bytes'],'saved complete fixture bytes')
  need(term['passed'] and term['result']==result and term['first_error'] is None and not term['single_term_attempted'] and term['observed_native_target_fd'] and term['backend_acknowledged'] and term['target_descriptors_empty'] and term['qualification_limit'] is None,'complete coordinator qualification')
  need(term['status']['MainPID']=='0' and term['status']['Result']=='success' and term['status']['ExecMainStatus']=='0','unit closed successfully')
  need(result['schema']=='gsq.dense-packed-block.native-micro.v1' and result['passed'] and result['safe_to_exit'] and result['backend_acknowledged'] and result['card']==0 and result['profiling'] and not result['model_executed'],'native result scope')
  need((result['completed_exact_pairs'],result['attempted_kernel_submissions'],result['device_bytes'],result['transfer_bytes'],result['warmup_cycles'],result['measured_cycles'])==(84,168,35331072,37764096,4,24),'native exact schedule/bytes')
  need(not result['error'] and not result['cleanup_error'],'no native errors');t=result['teardown'];need(t['safe_to_exit'] and t['exit_code']==0 and t['idle_marker_complete'] and t['in_flight']==t['live_bytes']==0 and not t['error'],'positive native teardown')
  native=term['native_identity'];contact=read(S/'result/backend-contact.json');ready_path=S/'result/backend-ready.txt';ack_path=S/'result/backend-ack.txt';ready_hash=digest(ready_path);ack_hash=digest(ack_path);ready=ready_path.read_bytes();ack=ack_path.read_bytes();need(hashlib.sha256(ready).hexdigest()==ready_hash and hashlib.sha256(ack).hexdigest()==ack_hash,'challenge reread stable');ack_join(ready,ack,contact,native)
  need(not(S/'result/backend-ready.partial').exists() and not(S/'result/backend-ack.partial').exists(),'no partial handshake files');need(ready_path.stat().st_mtime_ns<=(S/'result/backend-contact.json').stat().st_mtime_ns<=ack_path.stat().st_mtime_ns,'ready/contact/ACK write order')
  before=ad['before'];allowed={(h['pid'],before['holders'][str(h['pid'])]['start_ticks'],h['node']) for h in before['inventory']['holders']};seen=0;active=0
  snapshots=[(before,None)]+[(x['snapshot'],x['state']) for x in mon['samples']]+[(contact['snapshot'],contact['unit_state']),(term['after'],None)]
  for snap,state in snapshots:
   need(snap['known_fault_baseline_matches'] and snap['kernel']['faults']==before['kernel']['faults'] and snap['boot']==before['boot'],'unchanged boot/fault baseline')
   need(snap['units']==before['units'] and snap['queue']==before['queue'] and not snap['identity_races'],'unchanged apps/queue/exact PID sampling')
   need(snap['root_free_bytes']>=27000000000 and snap['memory']['MemAvailable']>=8*1024**3,'continuous resource floors');inv=snap['inventory'];need(not inv['errors'] and inv['metadata_only'] and inv['device_opens']==0,'complete passive inventory')
   for h in inv['holders']:
    who=(h['pid'],snap['holders'][str(h['pid'])]['start_ticks']);bdf=snap['drm'][h['node']]['bdf'];need(bdf!='0000:47:00.0','other target stays empty')
    if who==tuple(native):need(bdf=='0000:23:00.0','actual native target only');seen+=1
    else:need((*who,h['node']) in allowed,'only admitted vision holders')
   if state and state['ActiveState'] in ('active','activating','deactivating'):
    active+=1
    for k,v in ad['plan']['safe_properties'].items():need(state[k]==v,'safe active unit properties')
  need(seen>0 and active>0 and all(x['observation_complete'] and x['first_error'] is None for x in mon['samples']),'positive contact/complete samples');need(mon['first_error'] is None and not mon['single_term_attempted'],'monitor no incident')
  need(not any(term['after']['drm'][h['node']]['bdf']=='0000:23:00.0' for h in term['after']['inventory']['holders']),'physical target drained')
  f=S/'result/samples.jsonl';digest(f);rows=[json.loads(line) for line in f.read_text().splitlines()];measured=samples_check(rows,manifest);summary=per_case(measured)
  raw=[];size=0
  for f in sorted(S.rglob('*')):
   st=f.lstat();need(not stat.S_ISLNK(st.st_mode),'no artifact symlinks')
   if stat.S_ISDIR(st.st_mode):continue
   need(stat.S_ISREG(st.st_mode),'regular raw artifacts');raw.append(f);size+=st.st_size;need(len(raw)<=2000 and size<=128*1024**2,'bounded closed raw audit')
  for f in raw:digest(f)
  for name in ('admission.json','terminal.json','monitor.json','result/result.json','result/samples.jsonl','result/backend-ready.txt','result/backend-ack.txt','result/backend-contact.json'):
   with (D/('raw-'+name.replace('/','-'))).open('xb') as f:f.write((S/name).read_bytes())
  with (D/'artifact-index.jsonl.gz').open('xb') as f,gzip.GzipFile(fileobj=f,mode='wb',mtime=0,filename='') as z:
   for item in sorted(index.values(),key=lambda x:x['path']):z.write((json.dumps(item,sort_keys=True)+'\n').encode())
  receipt.update(passed=True,qualification_complete=True,exact_pairs=84,exact_output_pairs=84,measured_pairs=72,excluded_warmup_pairs=12,kernel_submissions=168,native_identity=native,observed_target_bdf='0000:23:00.0',backend_ACK=True,contact_record_sha256=digest(S/'result/backend-contact.json'),physical_contact_records_seen=seen,safe_active_property_records=active,physical_drain=True,safe_native_teardown=True,cooperative_signals=0,unchanged_faults_vision_queue=True,statistics=summary,binary_sha256=BINARY_SHA,native_build_sha256=BUILD_SHA,plan_sha256=PLAN_SHA,terminal_duration_seconds=term['duration'],artifact_index_sha256=hashlib.sha256((D/'artifact-index.jsonl.gz').read_bytes()).hexdigest(),indexed_files=len(index),limitations=['Three fixed dense Q4_K/Q5_K/IQ4_XS shapes; isolated kernel events reported per case, not aggregate or end-to-end model speed','Each case retains all24 measured pairs,12 per order;4 warmup pairs per case excluded by preregistration','Native successful comparisons preserve per-arm hashes/full-byte comparison results; separate successful output blobs were not written','Copied complete three tensors and fixtures independently rehashed; no original model/bundle reread','ACK ordering is source-bound plus actual identity/challenge/sample/files; no claim that filesystem timestamps measure GPU execution','No device/service/process/kernel/model operation by auditor'])
 except BaseException as e:receipt['error']=repr(e);raise
 finally:
  receipt.update(auditor_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),parent_auditor_sha256=PARENT_SHA,elapsed_seconds=time.monotonic()-start)
  with (D/'review.json').open('x') as f:json.dump(receipt,f,indent=2);f.write('\n')
 print(json.dumps(dict(passed=True,review_sha256=hashlib.sha256((D/'review.json').read_bytes()).hexdigest(),per_case_B_over_A={k:v['all']['B_over_A_sum'] for k,v in summary.items()})))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--run',action='store_true',required=True);p.parse_args();run()
