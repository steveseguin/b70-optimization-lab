#!/usr/bin/env python3
"""Six fixed released attribution bundles; unchanged verified filesystem Job."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,os,resource,stat
P=Path(__file__).resolve().parent;L=P.parent.parent;R=L.parents[2]
PARENT=P.parent/'closed-bundles/closed_bundles.py';PARENT_SHA='23733bff9dc4261a88e1b45a6589f7d4707ea1ae2edc345d64c02c2eb37d52be'
assert hashlib.sha256(PARENT.read_bytes()).hexdigest()==PARENT_SHA
s=importlib.util.spec_from_file_location('private_attribution_closed_bundles',PARENT);C=importlib.util.module_from_spec(s);s.loader.exec_module(C);B=C.B;require=B.require
CAP=C.CAP;FLOOR=C.FLOOR;DEST=Path('/home/steve/own-xpu-runtime-results/gsq-attribution-bundle-archive-a')
PROFILE=dict(name='attribution',run='gsq-current-attribution-a',audit='profiling/current-attribution/evidence/device-a',review='469fe156e317fc1aa93a56cf2a803d8d0c1cf786e13fe6d391d7eb50c883c7aa',index='fada76de5c960fb7ee4a72774d8f13505b708def4aaa3e7dd773ebf7838113cc',terminal='f3072d56cce0c392977e1e00561b18a1f8a01e6d99e21ede3611b872ce63193c',plan='1c1512c80116979b4e336e2b708c01b63886d1b4c6579cac1a35fd5ceb51f0a5',captures=['','warmup-none','prompt-00-none'])
# Narrow the frozen canonical validator to these exact six names only.
C.ALLOWED=set(C.names(PROFILE))
RELEASE=P/'evidence/release.json';RELEASE_SHA='c209e3f7c4a12fa278f81d229654be8473c7addceddf8a23db78e7cca36fb7e5'
MICRO=L/'expert-iq3xxs-block/micro'
def release_authority():
 require(B.sha(RELEASE)==RELEASE_SHA,'immutable explicit release');r=json.loads(RELEASE.read_text());require(r['passed'] and r['root_explicit_release'] and r['fixture_count']==15 and r['retained_bytes']==19008480,'root released retained copies')
 for path,key in ((MICRO/'evidence/independent-extraction-review.json','extraction_review_sha256'),(MICRO/'evidence/extraction.json','extraction_receipt_sha256'),(MICRO/'fixed.hpp','fixed_header_sha256')):require(B.sha(path)==r[key],'extraction release authority drift')
 review=json.loads((MICRO/'evidence/independent-extraction-review.json').read_text());extraction=json.loads((MICRO/'evidence/extraction.json').read_text());require(review['passed'] and extraction['passed'] and 'error' not in extraction and review['local_bytes_read']==19008480 and review['expert_slices']==30,'actual retained fixture proof')
 require(review['extraction_receipt_sha256']==r['extraction_receipt_sha256'] and review['fixed_header_sha256']==extraction['fixed_header_sha256']==r['fixed_header_sha256'],'fixed header and extraction join')
 recorded={str(Path(f['path']).relative_to(R)):f['sha256'] for case in extraction['cases'] for f in case['files'].values()}
 require(recorded==review['local_fixture_sha256']=={k:v['sha256'] for k,v in r['local_fixture_metadata'].items()},'exact15 retained copy hashes')
 for name,v in r['local_fixture_metadata'].items():
  path=R/name;s=path.lstat();require(path.parent==MICRO/'fixtures' and path.resolve()==path and stat.S_ISREG(s.st_mode) and s.st_nlink==1 and [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]==v['identity'],'retained local fixture metadata changed')
 return r
def selected(batch):
 require(type(batch)is int and 0<=batch<6,'fixed attribution batch0..5');return C.names(PROFILE)[batch]
def remote(batch):selected(batch);return C.USB/f'gsq-attribution-state-bundle-{batch:02d}.tar.gz'
def authority(batch):
 release_authority();name=selected(batch);rows=C.read_authority(PROFILE)
 return B.Job(C.USB/PROFILE['run'],DEST/f'chunk-{batch:02d}',{name:rows[name]},set(),cap=CAP,floor=FLOOR,authority=dict(profile='attribution-closed',batch=batch,name=name,source=str(C.USB/PROFILE['run']),review_sha256=PROFILE['review'],index_sha256=PROFILE['index'],terminal_sha256=PROFILE['terminal'],plan_sha256=PROFILE['plan'],release_sha256=RELEASE_SHA,helper_sha256=B.sha(__file__),parent_adapter_sha256=PARENT_SHA,filesystem_helper_sha256=C.HELPER_SHA,archive_quota=CAP,unchanged_floor=FLOOR,restore=C.RESTORE))
def prepare_destination(batch):
 require(DEST.parent.resolve()==DEST.parent,'canonical NVMe parent')
 if not os.path.lexists(DEST):DEST.mkdir(mode=0o700);B.syncdir(DEST.parent)
 st=DEST.stat();require(not DEST.is_symlink() and DEST.resolve()==DEST and st.st_uid==os.getuid() and stat.S_IMODE(st.st_mode)==0o700,'private NVMe anchor')
 if batch:
  prior=json.loads((DEST/f'chunk-{batch-1:02d}/local-release-verified.json').read_text());a=prior['authority']
  require(prior['passed'] and a['profile']=='attribution-closed' and a['batch']==batch-1 and a['helper_sha256']==B.sha(__file__) and a['release_sha256']==RELEASE_SHA and a['parent_adapter_sha256']==PARENT_SHA and a['filesystem_helper_sha256']==C.HELPER_SHA and a['archive_quota']==CAP and a['terminal_sha256']==PROFILE['terminal'],'previous batch fully offloaded/released')
def plan():
 release_authority();rows=C.read_authority(PROFILE)
 return dict(schema='gsq.attribution-closed.plan.v1',source=str(C.USB/PROFILE['run']),destination=str(DEST),files=6,bytes=sum(x['bytes'] for x in rows.values()),batches=[dict(batch=i,name=selected(i),files=1,**rows[selected(i)],usb=str(remote(i))) for i in range(6)],archive_quota_per_batch=CAP,reserve_floor=FLOOR,initial_nvme_free_required=FLOOR+CAP,usb_reserve=2*1024**3,release_sha256=RELEASE_SHA,parent_adapter_sha256=PARENT_SHA,filesystem_helper_sha256=C.HELPER_SHA,operations_performed=False,payload_bytes_read=0,scope='Only six released audited attribution state.bundle files. All JSON/index/seal/draft/other files and retained micro15fixtures preserved; no model paths.',restore=C.RESTORE)
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
