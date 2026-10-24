#!/usr/bin/env python3
"""Fixed12 closed state.bundle files; explicit verified phases, no retries."""
from pathlib import Path,PurePosixPath
import argparse,gzip,hashlib,importlib.util,json,os,resource,stat
P=Path(__file__).resolve().parent;L=P.parent.parent
HELPER=P.parent/'closed_baseline_bins.py'
HELPER_SHA='6a86c61fe46b453f7f9516d7b41169f0314cfc2b2716f82aab54b05c8df566ab'
assert hashlib.sha256(HELPER.read_bytes()).hexdigest()==HELPER_SHA
s=importlib.util.spec_from_file_location('private_closed_bundle_archive_parent',HELPER);B=importlib.util.module_from_spec(s);s.loader.exec_module(B)
require=B.require
CAP=128*1024**2;FLOOR=27000000000+64*1024**2
DEST=Path('/home/steve/own-xpu-runtime-results/gsq-closed-bundle-archive-a')
USB=Path('/mnt/usb-models/own-xpu-runtime-results')
PROFILES=[dict(name='bundle',run='gsq-state-bundle-a',audit='state-bundle/evidence/device-a',review='1c41b70d7b13f149ad8642b5de055937be3301488228e47120fd8bab6e21b82e',index='600668ce17d82e7cb1ed4821d77bb2bd2e05a8d24790b252d7584e4c689d166e',terminal='223d2bc9659918398917767011641632843fc5802df7fd1e84e5a42b9624e236',plan='13897666770be4f6cc7a6c6a21e7d9d833b543c9f76e13ad6d997beb2a217f31',captures=['','prompt-00-none','prompt-00-mtp']),dict(name='class',run='gsq-current-class-a',audit='profiling/current-combined/evidence/device-a',review='24082f1789623e317c4447b374cf11bf1c7d568dcd25d5a6421505dd3b2321d0',index='1f68151bf9c5a1c0f7b51887a90bc38f681eac5fa3501a619d6edc7767ab8907',terminal='24b9e008725d6b3116e8687cfe32331a49d16fae3814d67e98e77def40be01d3',plan='8a12f2b92b218b93c66e788b5b802d2fa140a812d9065b85a3dfcb23bd32c298',captures=['','warmup-none','prompt-00-none'])]
def names(profile):return [str(PurePosixPath(prefix)/f'rank{rank}/state-2147483647/state.bundle') for prefix in profile['captures'] for rank in (0,1)]
ALLOWED=set().union(*(set(names(p)) for p in PROFILES))
def relative(name):
 # The ONLY imported-module override: exact fixed bundle names replace .bin suffix.
 require(type(name)is str,'string bundle path');p=PurePosixPath(name)
 require(not p.is_absolute() and p.parts and all(c not in ('','..','.') for c in p.parts) and str(p)==name,'canonical relative bundle path')
 require(name in ALLOWED,'fixed relative bundle path');return p.parts
B.relative=relative
RESTORE='Tar members retain exact original relative state.bundle paths. Restore a missing bundle under its authority.source root; verify its byte count/SHA against the bound independent index. Preserve existing state-index.tsv/state-seal.txt/state.json. Never overwrite an existing path without separate review. Generic inherited .bin wording does not change these exact member names.'
def validate_closure(p,r,t):
 require(r['passed'] and r['requests']==2 and r['captures']==3 and r['bundles']==6 and r['physical_drain'] and r['kernel_fault_baseline_unchanged'] and r['explicit_repeat_and_closed_stamp_verified'],'closed bundle review')
 require(r['index_sha256']==p['index'] and r['plan_sha256']==p['plan'],'review pins')
 require(r['ownership']['returncodes']==[0,0] and not r['ownership']['retained_pids'] and r['ownership']['signals_sent']==0,'closed processes')
 require(len(r['owners'])==2 and all(o['safe_to_exit'] and o['in_flight']==o['live_bytes']==o['exit_code']==0 for o in r['owners']),'safe native owners')
 require(t['passed'] and t['first_error'] is None and t['original_error'] is None and t['children_exited'] and t['target_descriptors_empty'] and t['observed_target_contact']==[True,True],'positive terminal')
 require(t['plan_sha256']==p['plan'] and t['rank_identities']==r['rank_identities'] and t['result']['full_result_sha256']==r['full_result_sha256'],'exact terminal/result join')
def read_authority(p):
 audit=L/p['audit'];control=Path('/home/steve/own-xpu-runtime-results')/(p['run']+'.control')
 for path,h in ((audit/'review.json',p['review']),(audit/'artifact-index.jsonl.gz',p['index']),(control/'terminal.json',p['terminal'])):require(B.sha(path)==h,'immutable authority')
 validate_closure(p,json.loads((audit/'review.json').read_text()),json.loads((control/'terminal.json').read_text()))
 rows={};terminal=False
 with gzip.open(audit/'artifact-index.jsonl.gz','rt') as f:
  for line in f:
   require(len(line)<=4096,'bounded index row');x=json.loads(line)
   if x['root']=='control' and x['path']=='terminal.json':require(not terminal and x['sha256']==p['terminal'],'indexed terminal');terminal=True
   if x['root']!='evidence' or not x['path'].endswith('/state.bundle'):continue
   relative(x['path']);require(x['path'] not in rows,'duplicate bundle');rows[x['path']]={k:x[k] for k in ('bytes','sha256')}
 require(terminal and set(rows)==set(names(p)) and len(rows)==6,'exact six bundles')
 for i,n in enumerate(names(p)):
  require(rows[n]['bytes']==(125561972 if i%2==0 else 96181196),'rank bundle extent')
  require(rows[n]['bytes']+8192+1024**2<CAP,'container fits128MiB')
 require(sum(x['bytes'] for x in rows.values())==665229504,'complete six payload bytes');return rows

def selected(batch):
 require(type(batch)is int and 0<=batch<12,'fixed batch0..11');p=PROFILES[batch//6];name=names(p)[batch%6];return p,name

def remote(batch):
 selected(batch);return USB/f'gsq-closed-state-bundle-{batch:02d}.tar.gz'
def authority(batch):
 p,name=selected(batch);rows=read_authority(p);source=USB/p['run']
 return B.Job(source,DEST/f'chunk-{batch:02d}',{name:rows[name]},set(),cap=CAP,floor=FLOOR,authority=dict(profile='closed-bundles',run_profile=p['name'],batch=batch,name=name,source=str(source),review_sha256=p['review'],index_sha256=p['index'],terminal_sha256=p['terminal'],plan_sha256=p['plan'],helper_sha256=B.sha(__file__),filesystem_helper_sha256=HELPER_SHA,archive_quota=CAP,unchanged_floor=FLOOR,path_boundary='private exact bundle-path validator; Job methods unchanged',restore=RESTORE))
def prepare_destination(batch):
 require(DEST.parent.resolve()==DEST.parent,'canonical NVMe parent')
 if not os.path.lexists(DEST):DEST.mkdir(mode=0o700);B.syncdir(DEST.parent)
 st=DEST.stat();require(not DEST.is_symlink() and DEST.resolve()==DEST and st.st_uid==os.getuid() and stat.S_IMODE(st.st_mode)==0o700,'private NVMe anchor')
 if batch:
  prior=json.loads((DEST/f'chunk-{batch-1:02d}/local-release-verified.json').read_text());a=prior['authority'];prev,_=selected(batch-1)
  require(prior['passed'] and a['profile']=='closed-bundles' and a['batch']==batch-1 and a['helper_sha256']==B.sha(__file__) and a['filesystem_helper_sha256']==HELPER_SHA and a['archive_quota']==CAP and a['terminal_sha256']==prev['terminal'],'prior batch fully offloaded/released')
def plan():
 batches=[]
 for j,p in enumerate(PROFILES):
  rows=read_authority(p)
  for i,name in enumerate(names(p)):
   batch=6*j+i;batches.append(dict(batch=batch,profile=p['name'],source=str(USB/p['run']),name=name,files=1,**rows[name],usb=str(remote(batch)),review_sha256=p['review'],index_sha256=p['index'],terminal_sha256=p['terminal'],plan_sha256=p['plan']))
 return dict(schema='gsq.closed-bundles.plan.v1',batches=batches,files=12,bytes=sum(b['bytes'] for b in batches),archive_quota_per_batch=CAP,max_conservative_container_bytes=125561972+8192+1024**2,reserve_floor=FLOOR,initial_nvme_free_required=FLOOR+CAP,usb_reserve=2*1024**3,filesystem_helper_sha256=HELPER_SHA,attribution_excluded=True,operations_performed=False,restore=RESTORE,scope='Only12 exact independently audited state.bundle files. All index/seal/stateJSON/draft/other data preserved. Attribution needs separate source-bound amendment after explicit extraction release; no current operational path.')
def main():
 ap=argparse.ArgumentParser(description=__doc__);g=ap.add_mutually_exclusive_group(required=True)
 for name in ('plan','archive','prune-verified','offload-verified','release-local-verified'):g.add_argument('--'+name,action='store_true')
 ap.add_argument('--batch',type=int);a=ap.parse_args()
 if a.plan:print(json.dumps(plan(),indent=2));return
 require(a.batch is not None,'explicit batch');require(os.getpriority(os.PRIO_PROCESS,0)==19,'nice19');require(os.sched_getaffinity(0)<=set(range(8,16))|set(range(24,32)),'helpercores');resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
 job=authority(a.batch);usb=remote(a.batch)
 if a.archive:prepare_destination(a.batch);result=job.archive();phase='archive'
 elif a.prune_verified:result=job.prune();phase='prune'
 elif a.offload_verified:result=job.offload(usb);phase='offload'
 else:result=job.release_local(usb);phase='release'
 B.record(P/'evidence'/f'chunk-{a.batch:02d}-{phase}.json',result);print(json.dumps(result))
if __name__=='__main__':main()
