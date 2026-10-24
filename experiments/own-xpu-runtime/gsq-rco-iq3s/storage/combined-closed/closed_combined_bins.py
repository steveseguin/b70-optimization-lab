#!/usr/bin/env python3
"""Fixed closed combined-run bins; explicit phases, no retries or discovery."""
from pathlib import Path
import argparse,gzip,hashlib,importlib.util,json,os,resource,stat
P=Path(__file__).resolve().parent;L=P.parent.parent
HELPER=P.parent/'closed_baseline_bins.py'
HELPER_SHA='6a86c61fe46b453f7f9516d7b41169f0314cfc2b2716f82aab54b05c8df566ab'
assert hashlib.sha256(HELPER.read_bytes()).hexdigest()==HELPER_SHA,'frozen filesystem helper changed'
s=importlib.util.spec_from_file_location('combined_fixed_archive_parent',HELPER);B=importlib.util.module_from_spec(s);s.loader.exec_module(B)
require=B.require
SOURCE=Path('/mnt/usb-models/own-xpu-runtime-results/gsq-attention-qkv-p33-a')
CONTROL=Path('/home/steve/own-xpu-runtime-results/gsq-attention-qkv-p33-a.control')
DEST=Path('/home/steve/own-xpu-runtime-results/gsq-attention-qkv-bin-archive-a')
AUDIT=L/'qkv-q6-p33/engine/operating/evidence/device-a'
REVIEW_SHA='778ef93e796ec48fdb73c813b78984e8e7354bdd8417bdb53d18e9d06b101b9e'
INDEX_SHA='5f010c4b90445e7c8adc6db8ec40ca1211b5a20c241ab63eaf8fca963dee1a73'
TERMINAL_SHA='00b8b2926751c1e07a04f5a11e58f9291102ae87d317715f1c2edc41f3eaba9c'
PLAN_SHA='8a66bc6868787605274c92f6c798804b8706feb2d4924eff1054e812bc0f67d8'
CAP=256*1024**2;FLOOR=27000000000+64*1024**2
PER_FILES=2113;PER_BYTES=231442500
NAMES=['initial','warmup-none','warmup-mtp']+[f'prompt-{i:02d}-{mode}' for i in range(12) for mode in (['none','mtp'] if i%2==0 else ['mtp','none'])]

def validate_closure(r,t):
 require(r['passed'] and r['all12_exact'] and r['requests']==26 and r['measured_arms']==24 and r['same_persistent_rank_pair'] and r['physical_drain'] and r['kernel_fault_baseline_unchanged'],'closed full combined review')
 require(r['index_sha256']==INDEX_SHA and r['plan_sha256']==PLAN_SHA,'review authority binding')
 require(r['ownership']['returncodes']==[0,0] and not r['ownership']['retained_pids'] and r['ownership']['signals_sent']==0,'review owner closure')
 require(len(r['owners'])==2 and all(o['safe_to_exit'] and o['in_flight']==o['live_bytes']==o['exit_code']==0 for o in r['owners']),'safe native owners')
 require(t['passed'] and t['first_error'] is None and t['original_error'] is None and t['children_exited'] and t['target_descriptors_empty'] and t['observed_target_contact']==[True,True],'positive terminal closure')
 require(t['plan_sha256']==PLAN_SHA and [x[0] for x in t['rank_identities']]==r['rank_pids'] and t['result']['full_result_sha256']==r['full_result_sha256'],'terminal exact run/result join')

def select_batch(rows,batch):
 require(type(batch)is int and 0<=batch<27,'fixed batch0..26');name=NAMES[batch]
 selected={n:r for n,r in rows.items() if (n.split('/')[0] in ('rank0','rank1') if name=='initial' else n.split('/')[0]==name)}
 require(len(selected)==PER_FILES and sum(r['bytes'] for r in selected.values())==PER_BYTES,'complete target plus draft group')
 require(PER_BYTES+PER_FILES*8192+1024**2<CAP,'raw payload plus conservative container overhead fits quota')
 return name,selected

def read_authority():
 review=AUDIT/'review.json';index=AUDIT/'artifact-index.jsonl.gz';terminal=CONTROL/'terminal.json'
 require(B.sha(review)==REVIEW_SHA and B.sha(index)==INDEX_SHA and B.sha(terminal)==TERMINAL_SHA,'immutable review/index/terminal')
 validate_closure(json.loads(review.read_text()),json.loads(terminal.read_text()))
 rows={};bound_terminal=False
 with gzip.open(index,'rt') as f:
  for line in f:
   require(len(line)<=4096,'bounded index row');x=json.loads(line)
   if x['root']=='control' and x['path']=='terminal.json':require(not bound_terminal and x['sha256']==TERMINAL_SHA,'indexed terminal');bound_terminal=True
   if x['root']!='evidence' or not x['path'].endswith('.bin'):continue
   name=x['path'];B.relative(name);require(name not in rows,'duplicate indexed bin')
   require(type(x['bytes'])is int and x['bytes']>=0 and len(x['sha256'])==64,'audited bin fields');rows[name]={'bytes':x['bytes'],'sha256':x['sha256']}
 require(bound_terminal and len(rows)==57051 and sum(r['bytes'] for r in rows.values())==6248947500,'complete fixed closed bin census')
 groups=[select_batch(rows,i)[1] for i in range(27)]
 require(set().union(*groups)==set(rows) and sum(map(len,groups))==len(rows),'each audited bin assigned exactly once')
 return rows

def remote(batch):
 require(type(batch)is int and 0<=batch<27,'fixed remote batch')
 return Path('/mnt/usb-models/own-xpu-runtime-results')/f'gsq-attention-qkv-state-bins-{batch:02d}.tar.gz'
def authority(batch):
 name,rows=select_batch(read_authority(),batch)
 return B.Job(SOURCE,DEST/f'chunk-{batch:02d}',rows,set(),cap=CAP,floor=FLOOR,authority=dict(profile='combined',batch=batch,name=name,source=str(SOURCE),review_sha256=REVIEW_SHA,index_sha256=INDEX_SHA,terminal_sha256=TERMINAL_SHA,plan_sha256=PLAN_SHA,helper_sha256=B.sha(__file__),filesystem_helper_sha256=HELPER_SHA,archive_quota=CAP,unchanged_floor=FLOOR))
def prepare_destination(batch):
 require(DEST.parent.resolve()==DEST.parent,'canonical NVMe anchor parent')
 if not os.path.lexists(DEST):DEST.mkdir(mode=0o700);B.syncdir(DEST.parent)
 st=DEST.stat();require(not DEST.is_symlink() and DEST.resolve()==DEST and st.st_uid==os.getuid() and stat.S_IMODE(st.st_mode)==0o700,'private NVMe anchor')
 if batch:
  prior=json.loads((DEST/f'chunk-{batch-1:02d}/local-release-verified.json').read_text());a=prior['authority']
  require(prior['passed'] and a['profile']=='combined' and a['batch']==batch-1 and a['helper_sha256']==B.sha(__file__) and a['filesystem_helper_sha256']==HELPER_SHA and a['archive_quota']==CAP and a['terminal_sha256']==TERMINAL_SHA,'prior batch fully offloaded/released')
def plan():
 rows=read_authority()
 return dict(schema='gsq.combined-closed-storage-plan.v1',source=str(SOURCE),destination=str(DEST),review_sha256=REVIEW_SHA,index_sha256=INDEX_SHA,terminal_sha256=TERMINAL_SHA,files=len(rows),bytes=sum(x['bytes'] for x in rows.values()),batches=[dict(batch=i,name=select_batch(rows,i)[0],files=PER_FILES,bytes=PER_BYTES,usb=str(remote(i))) for i in range(27)],archive_quota_per_batch=CAP,conservative_container_bytes=PER_BYTES+PER_FILES*8192+1024**2,reserve_floor=FLOOR,usb_reserve=2*1024**3,filesystem_helper_sha256=HELPER_SHA,operations_performed=False,scope='Only independently indexed .bin files, including five draft bins per complete group; all JSON, logs, unindexed files and directories preserved; no model or other-run paths')
def main():
 ap=argparse.ArgumentParser(description=__doc__);g=ap.add_mutually_exclusive_group(required=True)
 for name in ('plan','archive','prune-verified','offload-verified','release-local-verified'):g.add_argument('--'+name,action='store_true')
 ap.add_argument('--batch',type=int);a=ap.parse_args()
 if a.plan:print(json.dumps(plan(),indent=2));return
 require(a.batch is not None,'explicit batch required');require(os.getpriority(os.PRIO_PROCESS,0)==19,'nice19');require(os.sched_getaffinity(0)<=set(range(8,16))|set(range(24,32)),'helper cores');resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
 job=authority(a.batch);usb=remote(a.batch)
 if a.archive:prepare_destination(a.batch);result=job.archive();phase='archive'
 elif a.prune_verified:result=job.prune();phase='prune'
 elif a.offload_verified:result=job.offload(usb);phase='offload'
 else:result=job.release_local(usb);phase='release'
 B.record(P/'evidence'/f'chunk-{a.batch:02d}-{phase}.json',result);print(json.dumps(result))
if __name__=='__main__':main()
