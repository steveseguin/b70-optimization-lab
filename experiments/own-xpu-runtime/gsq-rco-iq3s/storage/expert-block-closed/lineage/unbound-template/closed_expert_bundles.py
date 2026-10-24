#!/usr/bin/env python3
"""Fixed future closed54 bundles. Refuses all phases until actual closure is bound."""
from pathlib import Path
import argparse,gzip,hashlib,importlib.util,json,os,resource,stat
P=Path(__file__).resolve().parent;L=P.parent.parent
PARENT=P.parent/'closed-bundles/closed_bundles.py';PARENT_SHA='23733bff9dc4261a88e1b45a6589f7d4707ea1ae2edc345d64c02c2eb37d52be'
assert hashlib.sha256(PARENT.read_bytes()).hexdigest()==PARENT_SHA
s=importlib.util.spec_from_file_location('private_expert_closed_bundles',PARENT);C=importlib.util.module_from_spec(s);s.loader.exec_module(C);B=C.B;require=B.require
CAP=C.CAP;FLOOR=C.FLOOR
DEST=Path('/home/steve/own-xpu-runtime-results/gsq-expert-block-bundle-archive-a')
RUN='gsq-iq3xxs-block-engine-a';SOURCE=C.USB/RUN
CONTROL=Path('/home/steve/own-xpu-runtime-results')/(RUN+'.control')
AUDIT=L/'expert-iq3xxs-block/engine/operating/evidence/device-a'
PLAN_SHA='61e2e15a3577ae2d972f922cea8ff4a7e8f22567cf3354f761d4fa94b786359d'
BINARY_SHA='97348925367e1ad67313cf9863d0c4cba47abea871c386972983965e036ea4b2'
MANIFEST=L/'baseline/manifest.json';MANIFEST_SHA='c8ad4665ddad4cff54961181679d402525c19381af855434d046508840180e20'
# Deliberately unbound while the run is active. A reviewed additive binding of
# actual PASS artifacts must replace None; a caller cannot supply authority paths.
BINDING=P/'evidence/closure-binding.json';BINDING_SHA=None
require(B.sha(MANIFEST)==MANIFEST_SHA,'frozen original schedule')
m=json.loads(MANIFEST.read_text())
CAPTURES=['']+['warmup-'+w['mode'] for w in m['warmup']]+[f'prompt-{i:02d}-{mode}' for i,p in enumerate(m['prompts']) for mode in p['order']]
require(len(CAPTURES)==len(set(CAPTURES))==27,'exact original27 captures')
NAMES=C.names({'captures':CAPTURES});C.ALLOWED=set(NAMES)
def selected(batch):
 require(type(batch)is int and 0<=batch<54,'fixed expert batch0..53');return NAMES[batch]
def remote(batch):selected(batch);return C.USB/f'gsq-expert-block-state-bundle-{batch:02d}.tar.gz'
def validate_closure(binding,r,t):
 require(r['passed'] and r['requests']==26 and r['measured_arms']==24 and r['exact_pairs']==12 and r['all12_exact'] and r['bundles']==54 and r['paired_state_dump_groups']==27,'complete audited fullsuite')
 require(r['physical_drain'] and r['kernel_fault_baseline_unchanged'] and r['explicit_final_repeat_and_closed_stamps_verified'] and r['same_persistent_rank_pair'],'positive closed bundle review')
 require(r['index_sha256']==binding['index_sha256'] and r['plan_sha256']==PLAN_SHA and r['native_binary_sha256']==BINARY_SHA and r['full_result_sha256']==binding['full_result_sha256'],'review identity')
 require(r['ownership']['returncodes']==[0,0] and not r['ownership']['retained_pids'] and r['ownership']['signals_sent']==0 and not r['ownership']['stop_requested'],'closed processes')
 require(len(r['owners'])==2 and all(o['safe_to_exit'] and o['in_flight']==o['live_bytes']==o['exit_code']==0 for o in r['owners']),'safe owners')
 require(t['passed'] and t['first_error'] is None and t['original_error'] is None and t['children_exited'] and t['target_descriptors_empty'] and t['observed_target_contact']==[True,True],'positive terminal contacts')
 require(t['plan_sha256']==PLAN_SHA and [x[0] for x in t['rank_identities']]==r['rank_pids'] and t['result']['full_result_sha256']==r['full_result_sha256'],'terminal/result join')
def binding():
 require(type(BINDING_SHA)is str and len(BINDING_SHA)==64,'actual closed authority not yet bound')
 require(B.sha(BINDING)==BINDING_SHA,'immutable closure binding');b=json.loads(BINDING.read_text())
 require(b['passed'] and b['root_authorized_closed_release'] and b['run']==RUN and b['plan_sha256']==PLAN_SHA and b['native_binary_sha256']==BINARY_SHA,'explicit fixed closed release')
 for path,key in ((AUDIT/'review.json','review_sha256'),(AUDIT/'artifact-index.jsonl.gz','index_sha256'),(CONTROL/'terminal.json','terminal_sha256')):require(B.sha(path)==b[key],'bound actual authority')
 validate_closure(b,json.loads((AUDIT/'review.json').read_text()),json.loads((CONTROL/'terminal.json').read_text()));return b
def read_authority():
 b=binding();rows={};terminal=False;result=False
 with gzip.open(AUDIT/'artifact-index.jsonl.gz','rt') as f:
  for line in f:
   require(len(line)<=4096,'bounded index row');x=json.loads(line)
   if x['root']=='control' and x['path']=='terminal.json':require(not terminal and x['sha256']==b['terminal_sha256'],'indexed terminal');terminal=True
   if x['root']=='evidence' and x['path']=='resident-suite.json':require(not result and x['sha256']==b['full_result_sha256'],'indexed full result');result=True
   if x['root']!='evidence' or not x['path'].endswith('/state.bundle'):continue
   C.relative(x['path']);require(x['path'] not in rows,'duplicate bundle');rows[x['path']]={k:x[k] for k in ('bytes','sha256')}
 require(terminal and result and set(rows)==set(NAMES) and len(rows)==54,'exact54 audited bundles')
 for i,name in enumerate(NAMES):require(rows[name]['bytes']==(125561972 if i%2==0 else 96181196) and rows[name]['bytes']+8192+1024**2<CAP,'fixed rank extent/container bound')
 require(sum(x['bytes'] for x in rows.values())==5987065536,'all54 target payload bytes');return b,rows
def authority(batch):
 name=selected(batch);b,rows=read_authority()
 return B.Job(SOURCE,DEST/f'chunk-{batch:02d}',{name:rows[name]},set(),cap=CAP,floor=FLOOR,authority=dict(profile='expert-block-closed',batch=batch,name=name,source=str(SOURCE),closure_binding_sha256=BINDING_SHA,review_sha256=b['review_sha256'],index_sha256=b['index_sha256'],terminal_sha256=b['terminal_sha256'],plan_sha256=PLAN_SHA,helper_sha256=B.sha(__file__),parent_adapter_sha256=PARENT_SHA,filesystem_helper_sha256=C.HELPER_SHA,archive_quota=CAP,unchanged_floor=FLOOR,restore=C.RESTORE))
def prepare_destination(batch):
 require(DEST.parent.resolve()==DEST.parent,'canonical NVMe parent')
 if not os.path.lexists(DEST):DEST.mkdir(mode=0o700);B.syncdir(DEST.parent)
 st=DEST.stat();require(not DEST.is_symlink() and DEST.resolve()==DEST and st.st_uid==os.getuid() and stat.S_IMODE(st.st_mode)==0o700,'private NVMe anchor')
 if batch:
  prior=json.loads((DEST/f'chunk-{batch-1:02d}/local-release-verified.json').read_text());a=prior['authority']
  require(prior['passed'] and a['profile']=='expert-block-closed' and a['batch']==batch-1 and a['helper_sha256']==B.sha(__file__) and a['closure_binding_sha256']==BINDING_SHA and a['parent_adapter_sha256']==PARENT_SHA and a['filesystem_helper_sha256']==C.HELPER_SHA and a['archive_quota']==CAP,'previous batch fully offloaded/released')
def plan():
 b,rows=read_authority()
 return dict(schema='gsq.expert-block-closed.plan.v1',source=str(SOURCE),files=54,capture_groups=27,bytes=sum(x['bytes'] for x in rows.values()),batches=[dict(batch=i,name=n,files=1,**rows[n],usb=str(remote(i))) for i,n in enumerate(NAMES)],archive_quota_per_batch=CAP,reserve_floor=FLOOR,initial_nvme_free_required=FLOOR+CAP,usb_reserve=2*1024**3,closure_binding_sha256=BINDING_SHA,parent_adapter_sha256=PARENT_SHA,filesystem_helper_sha256=C.HELPER_SHA,operations_performed=False,payload_bytes_read=0,scope='Only54 fixed target state.bundle files; allJSON/index/seal/draft/other data preserved',restore=C.RESTORE)
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
