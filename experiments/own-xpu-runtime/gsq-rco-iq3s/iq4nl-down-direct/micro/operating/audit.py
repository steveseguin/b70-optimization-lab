#!/usr/bin/env python3
"""Explicit closed micro readback; stdlib only, no operational imports."""
import argparse,collections,gzip,hashlib,json,os,resource,stat,statistics,time
from pathlib import Path
R=Path('/home/steve/llm-optimizations');P=R/'experiments/own-xpu-runtime/gsq-rco-iq3s/iq4nl-down-direct/micro';S=Path('/home/steve/own-xpu-runtime-results/gsq-iq4nl-direct-micro-a');D=P/'evidence/device-a'
PLAN_SHA='46b7823b6f3ce76534f3ab5ce6916a68c19a73c509c6d4bc0f5aecb36d728ca7'
BUILD_SHA='d1c5e5d02b674c7b2531559b721e35a7fa1322dcb21970e4b86840f239abb95e'
BINARY_SHA='dcd67040535733a8271191d6fe6feccee4e14eff30f8c13d76e52fd0db9fda5b'
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
 need(len(rows)==28 and len(manifest['schedule'])==28,'all28 pairs');previous=0
 for row,want in zip(rows,manifest['schedule']):
  case=manifest['cases'][want['case']]
  need((row['warmup'],row['cycle'],row['layer'],row['order'],row['label'])==(want['warmup'],want['cycle'],0,''.join(want['order']),'blk.0.expsdown'),'fixed phase/cycle/case/order')
  need(row['exact'] and row['A_sha256']==row['B_sha256']==row['expected_sha256']==case['fixtures']['expected']['sha256'],'exact full output')
  need(row['A_status_sha256']==row['B_status_sha256']==row['expected_status_sha256']==case['fixtures']['status']['sha256'],'exact ten statuses')
  need(case['fixtures']['expected']['bytes']==51200 and case['fixtures']['status']['bytes']==40,'full output/status extent')
  first,second=row['order'];need(previous<row[first+'_start_ns']<row[first+'_end_ns']<row[second+'_start_ns']<row[second+'_end_ns'],'strict native event ordering');previous=row[second+'_end_ns']
 measured=[r for r in rows if not r['warmup']];warm=[r for r in rows if r['warmup']]
 need(len(measured)==24 and len(warm)==4 and collections.Counter(r['order'] for r in measured)=={'AB':12,'BA':12} and collections.Counter(r['order'] for r in warm)=={'AB':2,'BA':2},'balanced preregistered all-sample schedule')
 return measured
def stats(v):return dict(count=len(v),mean=statistics.mean(v),median=statistics.median(v),minimum=min(v),maximum=max(v))
def aggregate(rows):
 a=[r['A_end_ns']-r['A_start_ns'] for r in rows];b=[r['B_end_ns']-r['B_start_ns'] for r in rows]
 return dict(pairs=len(rows),A_ns=stats(a),B_ns=stats(b),B_over_A_paired=stats([y/x for x,y in zip(a,b)]),B_over_A_sum=sum(b)/sum(a))
def run():
 need(os.getpriority(os.PRIO_PROCESS,0)==19 and os.sched_getaffinity(0)<=set(range(8,16))|set(range(24,32)),'helper placement');resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));D.mkdir(parents=True,exist_ok=True);need(not(D/'review.json').exists() and not(D/'artifact-index.jsonl.gz').exists(),'exclusive audit')
 receipt=dict(schema='gsq.iq4nl-direct.closed-review.v1',passed=False,device_executed_by_reviewer=False);start=time.monotonic()
 try:
  ad=read(S/'admission.json');term=read(S/'terminal.json');mon=read(S/'monitor.json');result=read(S/'result/result.json');manifest=read(P/'manifest.json');build=read(P/'evidence/native-build.json')
  planfile=Path(str(S)+'.plan.json');need(digest(planfile)==PLAN_SHA and read(planfile)==ad['plan'],'admitted fixed plan');pins(ad['plan']['source_sha256']);pins(manifest['authority'])
  for key in ('source_sha256','objects_reused','dependencies'):pins(build[key])
  need(digest(build['binary'])==build['binary_sha256']==ad['binary_sha256']==BINARY_SHA,'native binary identity');need(digest(P/'evidence/native-build.json')==ad['proof_sha256']==BUILD_SHA,'native build');need(digest(P/'once.py')==ad['monitor_sha256'],'operating source')
  review=read(P/'evidence/independent-review.json');need(review['passed'] and review['binary_sha256']==BINARY_SHA and review['native_build_sha256']==BUILD_SHA,'final independent prerequisites');pins(review['source_sha256'])
  need(len(manifest['cases'])==1 and (manifest['pairs'],manifest['kernels'],manifest['device_bytes'],manifest['transfer_bytes'],manifest['pinned_bytes'])==(28,56,471974600,474741560,1048576),'fixed schedule/ledger')
  for c in manifest['cases']:
   need(digest(c['sparse_weights']['path'])==c['sparse_weights']['sha256'],'authenticated copied sparse weights')
   for f in c['fixtures'].values():need(digest(f['path'])==f['sha256'] and Path(f['path']).stat().st_size==f['bytes'],'saved complete fixture bytes')
  need(term['passed'] and term['result']==result and term['first_error'] is None and not term['single_term_attempted'] and term['observed_native_target_fd'] and term['backend_acknowledged'] and term['target_descriptors_empty'] and term['qualification_limit'] is None,'complete coordinator qualification')
  need(term['status']['MainPID']=='0' and term['status']['Result']=='success' and term['status']['ExecMainStatus']=='0','unit closed successfully')
  need(result['schema']=='gsq.iq4nl-direct.native-micro.v1' and result['passed'] and result['safe_to_exit'] and result['backend_acknowledged'] and result['card']==0 and result['profiling'] and not result['model_executed'],'native result scope')
  need((result['completed_exact_pairs'],result['attempted_kernel_submissions'],result['device_bytes'],result['transfer_bytes'],result['warmup_cycles'],result['measured_cycles'])==(28,56,471974600,474741560,4,24),'native exact schedule/bytes')
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
  f=S/'result/samples.jsonl';digest(f);rows=[json.loads(line) for line in f.read_text().splitlines()];measured=samples_check(rows,manifest);summary=dict(all=aggregate(measured),by_order={order:aggregate([x for x in measured if x['order']==order]) for order in ('AB','BA')})
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
  receipt.update(passed=True,qualification_complete=True,exact_pairs=28,exact_output_and_status_pairs=28,measured_pairs=24,excluded_warmup_pairs=4,kernel_submissions=56,native_identity=native,observed_target_bdf='0000:23:00.0',backend_ACK=True,contact_record_sha256=digest(S/'result/backend-contact.json'),physical_contact_records_seen=seen,safe_active_property_records=active,physical_drain=True,safe_native_teardown=True,cooperative_signals=0,unchanged_faults_vision_queue=True,statistics=summary,binary_sha256=BINARY_SHA,native_build_sha256=BUILD_SHA,plan_sha256=PLAN_SHA,terminal_duration_seconds=term['duration'],artifact_index_sha256=hashlib.sha256((D/'artifact-index.jsonl.gz').read_bytes()).hexdigest(),indexed_files=len(index),limitations=['One fixed layer0 captured down projection; repeated isolated kernel events, not end-to-end model throughput','All24 measured pairs retained,12 per order;4 warmup pairs excluded by preregistration','Native successful comparisons preserve per-arm hashes/full-byte comparison results; separate successful output blobs were not written','Copied fixtures/sparse slices independently rehashed; no original model/archive reread or wholebank hash','ACK ordering is source-bound plus actual identity/challenge/sample/files; no claim that filesystem timestamps measure GPU execution','No device/service/process/kernel/model operation by auditor'])
 except BaseException as e:receipt['error']=repr(e);raise
 finally:
  receipt.update(auditor_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),elapsed_seconds=time.monotonic()-start)
  with (D/'review.json').open('x') as f:json.dump(receipt,f,indent=2);f.write('\n')
 print(json.dumps(dict(passed=True,review_sha256=hashlib.sha256((D/'review.json').read_bytes()).hexdigest(),B_over_A=summary['all']['B_over_A_sum'])))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--run',action='store_true',required=True);p.parse_args();run()
