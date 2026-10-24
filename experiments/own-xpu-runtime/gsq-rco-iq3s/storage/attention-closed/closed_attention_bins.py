#!/usr/bin/env python3
"""Fixed audited attention states; explicit archive/prune/offload/release phases.
Reuses the exact tested filesystem machinery; no caller paths or automatic retry.
"""
from pathlib import Path
import argparse,gzip,hashlib,importlib.util,json,os,resource,stat
P=Path(__file__).resolve().parent;L=P.parent.parent;C=L/'attention-q8-p33'
HELPER=P.parent/'closed_baseline_bins.py';HELPER_SHA='6a86c61fe46b453f7f9516d7b41169f0314cfc2b2716f82aab54b05c8df566ab'
assert hashlib.sha256(HELPER.read_bytes()).hexdigest()==HELPER_SHA,'frozen filesystem helper changed'
s=importlib.util.spec_from_file_location('attention_fixed_archive_parent',HELPER);B=importlib.util.module_from_spec(s);s.loader.exec_module(B)
require=B.require
PROFILES={
 'prefix':dict(source='/mnt/usb-models/own-xpu-runtime-results/gsq-attention-p33-a',audit=str(C/'operating/evidence/partial-independent-a'),review_sha256='663fb5e463b6e9ee6b45f6e55562394522f1f30f593ef5003991ba51c2e887cf',index_sha256='4f4e6ce9e7922b1ba5e4eff070f808a4d32fdd1104e8e85356ea93b354858ecc',per_files=2108,per_bytes=221743168,names=[f'prompt-{i:02d}-{mode}' for i in range(7) for mode in (['none','mtp'] if i%2==0 else ['mtp','none'])]),
 'completion':dict(source='/mnt/usb-models/own-xpu-runtime-results/gsq-attention-p33-completion-a',audit=str(C/'completion/evidence/device-a'),review_sha256='068fe237589673cc7ef9545b5bcfbf65d1a51cfe9e8351a727b925bb9f6bd245',index_sha256='1210bc4eb507378ca9691d90e4eddbf4e7b7bcc70d54c6c3c3302e90b6b9be91',per_files=2113,per_bytes=231442500,names=['initial','warmup-none','warmup-mtp']+[f'prompt-{i:02d}-{mode}' for i in range(7,12) for mode in (['none','mtp'] if i%2==0 else ['mtp','none'])])}
# Q6 micro author confirmed inputs come exclusively from profile-a; untouched.
# Baseline six preserved micro inputs are also outside both fixed source roots.
def normalize(profile,row):
 source=Path(PROFILES[profile]['source'])
 if profile=='prefix':
  p=Path(row['path']);require(p.is_absolute(),'absolute prefix index path')
  try:name=str(p.relative_to(source))
  except ValueError:raise ValueError('prefix path outside fixed source')
 else:
  if row['root']!='evidence':return None
  name=row['path']
 if not name.endswith('.bin'):return None
 B.relative(name);return name

def read_authority(profile):
 cfg=PROFILES[profile];audit=Path(cfg['audit']);review=audit/'review.json';index=audit/'artifact-index.jsonl.gz'
 require(B.sha(review)==cfg['review_sha256'] and B.sha(index)==cfg['index_sha256'],'immutable independent review/index')
 r=json.loads(review.read_text());require(r['index_sha256']==cfg['index_sha256'],'review index binding')
 if profile=='prefix':require(r['audit_passed'] and not r['passed'] and r['incomplete'] and r['verified_prior_arms']==14 and r['children_exited_and_physical_drain_attested'],'closed incomplete prefix')
 else:require(r['passed'] and r['completion_exact_arms']==10 and r['physical_drain'] and r['ownership']['returncodes']==[0,0] and not r['ownership']['retained_pids'],'closed complete suffix')
 rows={}
 with gzip.open(index,'rt') as f:
  for line in f:
   require(len(line)<=4096,'bounded authority row');x=json.loads(line);name=normalize(profile,x)
   if name is None:continue
   require(name not in rows,'duplicate audited bin');rows[name]={'bytes':x['bytes'],'sha256':x['sha256']}
 require(len(rows)==len(cfg['names'])*cfg['per_files'] and sum(x['bytes'] for x in rows.values())==len(cfg['names'])*cfg['per_bytes'],'complete fixed bin census')
 for i in range(len(cfg['names'])):select_batch(profile,rows,i)
 return rows

def select_batch(profile,rows,batch):
 cfg=PROFILES[profile];require(type(batch)is int and 0<=batch<len(cfg['names']),'fixed profile batch range');name=cfg['names'][batch]
 chosen={n:r for n,r in rows.items() if (n.split('/')[0] in ('rank0','rank1') if name=='initial' else n.split('/')[0]==name)}
 require(len(chosen)==cfg['per_files'] and sum(r['bytes'] for r in chosen.values())==cfg['per_bytes'],'exact closed group census')
 # Prefix authority covers target state only, never scratch or failed request.
 if profile=='prefix':require(all(n.split('/')[2]=='state-2147483647' and n.split('/')[1] in ('rank0','rank1') for n in chosen),'prefix target-state extent only')
 return name,chosen

def anchor(profile):return Path('/home/steve/own-xpu-runtime-results')/f'gsq-attention-{profile}-bin-archive-a'
def remote(profile,batch):return Path('/mnt/usb-models/own-xpu-runtime-results')/f'gsq-attention-{profile}-state-bins-{batch:02d}.tar.gz'
def authority(profile,batch):
 cfg=PROFILES[profile];name,rows=select_batch(profile,read_authority(profile),batch)
 return B.Job(Path(cfg['source']),anchor(profile)/f'chunk-{batch:02d}',rows,set(),authority=dict(profile=profile,batch=batch,name=name,source=cfg['source'],review_sha256=cfg['review_sha256'],index_sha256=cfg['index_sha256'],helper_sha256=B.sha(__file__),filesystem_helper_sha256=HELPER_SHA))
def prepare_destination(profile,batch):
 root=anchor(profile);require(root.parent.resolve()==root.parent,'canonical NVMe anchor parent')
 if not os.path.lexists(root):root.mkdir(mode=0o700);B.syncdir(root.parent)
 st=root.stat();require(not root.is_symlink() and root.resolve()==root and st.st_uid==os.getuid() and stat.S_IMODE(st.st_mode)==0o700,'private NVMe anchor')
 if batch:
  prior=json.loads((root/f'chunk-{batch-1:02d}/local-release-verified.json').read_text());a=prior['authority']
  require(prior['passed'] and a['profile']==profile and a['batch']==batch-1 and a['helper_sha256']==B.sha(__file__) and a['filesystem_helper_sha256']==HELPER_SHA,'prior batch fully offloaded/released')
def plan():
 profiles={}
 for profile,cfg in PROFILES.items():
  rows=read_authority(profile);profiles[profile]=dict(source=cfg['source'],archive_anchor=str(anchor(profile)),review_sha256=cfg['review_sha256'],index_sha256=cfg['index_sha256'],files=len(rows),bytes=sum(x['bytes'] for x in rows.values()),batches=[dict(batch=i,name=select_batch(profile,rows,i)[0],files=cfg['per_files'],bytes=cfg['per_bytes'],usb=str(remote(profile,i))) for i in range(len(cfg['names']))])
 return dict(schema='gsq.attention-closed-storage-plan.v1',profiles=profiles,archive_quota_per_batch=B.CAP,reserve_floor=B.FLOOR,usb_reserve=2*1024**3,operations_performed=False,filesystem_helper_sha256=HELPER_SHA,exclusions=['Every JSON, log, directory and failure metadata','All unindexed prefix initial/warmup/scratch/failed prompt07-mtp bins','All model weights, baseline retained micro bins and all profile-a Q6 inputs','No active-run discovery or caller-supplied root'])
def main():
 ap=argparse.ArgumentParser(description=__doc__);g=ap.add_mutually_exclusive_group(required=True)
 for name in ('plan','archive','prune-verified','offload-verified','release-local-verified'):g.add_argument('--'+name,action='store_true')
 ap.add_argument('--profile',choices=PROFILES);ap.add_argument('--batch',type=int);a=ap.parse_args()
 if a.plan:print(json.dumps(plan(),indent=2));return
 require(a.profile is not None and a.batch is not None,'explicit profile and batch required');require(os.getpriority(os.PRIO_PROCESS,0)==19,'nice19');require(os.sched_getaffinity(0)<=set(range(8,16))|set(range(24,32)),'helper cores');resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
 job=authority(a.profile,a.batch);usb=remote(a.profile,a.batch)
 if a.archive:prepare_destination(a.profile,a.batch);result=job.archive();phase='archive'
 elif a.prune_verified:result=job.prune();phase='prune'
 elif a.offload_verified:result=job.offload(usb);phase='offload'
 else:result=job.release_local(usb);phase='release'
 B.record(P/'evidence'/f'{a.profile}-{a.batch:02d}-{phase}.json',result);print(json.dumps(result))
if __name__=='__main__':main()
