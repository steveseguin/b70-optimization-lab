#!/usr/bin/env python3
"""Fixed16 closed bundles; preserve via existing canonical member, separate release."""
from pathlib import Path
import argparse,gzip,hashlib,importlib.util,json,os,stat
P=Path(__file__).resolve().parent;L=P.parents[1];R=L.parents[2]
PARENT=P.parent/'dense-prompt01-canonical/reuse.py'
PARENT_SHA='51fba80be57bdbdb6693877b30eeea435155f8c6c36b8e90e06e0f719446ef59'
BINDING=P/'closure-binding.json';BINDING_SHA='aec735b3304d799f1fe6479f3ccea71f66eaf65cdfb9726951bf857c6ebe7aee'
USB=Path('/mnt/usb-models/own-xpu-runtime-results')
PROFILES=(('dense-q6','gsq-dense-q6-p33-engine-a',('', 'warmup-none/','warmup-mtp/')),('class-a-failed','gsq-dense-q6-class-a',('', 'warmup-none/')),('class-b','gsq-dense-q6-class-b',('', 'warmup-none/','prompt-00-none/')))
EXPECTED=tuple(str(USB/root/(prefix+f'rank{rank}/state-2147483647/state.bundle')) for _,root,prefixes in PROFILES for prefix in prefixes for rank in (0,1))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(v,m):
 if not v:raise ValueError(m)
need(sha(PARENT)==PARENT_SHA,'frozen raw canonical machinery')
s=importlib.util.spec_from_file_location('fixed16_raw_private',PARENT);M=importlib.util.module_from_spec(s);s.loader.exec_module(M);C=M.C
M.P=P;M.__file__=__file__;M.BINDING_SHA=BINDING_SHA
C.DEST=Path('/home/steve/own-xpu-runtime-results/gsq-dense-tail-canonical-a')

def authority(batch):
 need(type(batch)is int and 0<=batch<16,'fixed batch0..15');need(sha(BINDING)==BINDING_SHA,'immutable preservation authority')
 b=json.loads(BINDING.read_text());need(b['preservation_authorized'] is True and set(b['raw_paths'])==set(EXPECTED) and len(b['raw_paths'])==16,'fixed16 allowlist')
 need(sha(b['appraisal_path'])==b['appraisal_sha256'],'fixed capacity appraisal')
 for f,h in b['authority_sha256'].items():need(sha(f)==h,'closed metadata/source authority '+f)
 rows={x['raw_path']:x for x in b['rows']};need(set(rows)==set(EXPECTED) and len(b['rows'])==16 and sum(x['bytes'] for x in rows.values())==1773945344,'complete exact16 mapping')
 prior=json.loads((L/'expert-iq3xxs-block/engine/operating/evidence/device-a/review.json').read_text());inventory=json.loads((P.parent/'expert-block-closed/evidence/complete.json').read_text())
 need(prior['passed'] and prior['all12_exact'] and prior['physical_drain'] and inventory['passed'] and inventory['all_four_phases_passed'],'completed canonical owner/archive authority')
 indexpath=L/'expert-iq3xxs-block/engine/operating/evidence/device-a/artifact-index.jsonl.gz';need(sha(indexpath)==prior['index_sha256'],'canonical member index')
 with gzip.open(indexpath,'rt') as f:prior_rows={x['path']:x for line in f if (x:=json.loads(line))['root']=='evidence'}
 archive_rows={x['batch']:x for x in inventory['batches']}
 for profile,root,_ in PROFILES:
  selected=[x for x in rows.values() if x['profile']==profile];review=json.loads(Path(selected[0]['source_review_path']).read_text())
  if profile=='class-a-failed':
   need(review['run_passed'] is False and review['metadata_closure_review_passed'] and review['full_payload_audit_performed'] is False and review['measured_requests']==0 and review['physical_drain'] and review['both_physical_contacts'] and review['unchanged_faults_vision_queue'],'failed A preservation-only closure')
   need(review['ownership']['returncodes']==[1,1] and not review['ownership']['retained_pids'] and review['ownership']['signals_sent']==0 and not review['ownership']['diagnostic_errors'],'failed A owners closed without signals')
   for owner in review['owners']:need(owner['safe_to_exit'] and owner['idle_marker_complete'] and owner['exit_code']==owner['in_flight']==owner['live_bytes']==0 and not owner['error'],'failed A positive backend closure')
   for path,h in review['artifacts'].items():need(sha(path)==h,'failed A incident artifact')
  else:
   need(review['passed'] and review['physical_drain'] and review['kernel_fault_baseline_unchanged'],'audited success closure')
   need(review['native_binary_sha256']=='a0f9ffc58de704a276b237cbeec2b338ee873c0872bcae2da2214286aa5cce50','same qualified target')
   ip=Path(selected[0]['source_review_path']).parent/'artifact-index.jsonl.gz';need(sha(ip)==review['index_sha256'],'current physical member index')
   with gzip.open(ip,'rt') as f:current={x['path']:x for line in f if (x:=json.loads(line))['root']=='evidence'}
   for x in selected:need((current[x['relative_path']]['bytes'],current[x['relative_path']]['sha256'])==(x['bytes'],x['raw_sha256']),'current audited raw bytes')
  for x in selected:
   need(x['raw_path']==str(USB/root/x['relative_path']),'fixed raw root/member')
   lines=Path(x['sealed_metadata']['state-seal.txt']['path']).read_text().splitlines();need(lines[0]=='GSQ_STATE_SEAL_V1' and (int(lines[1]),lines[2])==(x['bytes'],x['raw_sha256']),'sealed raw length/hash')
   need(lines[3]==x['sealed_metadata']['state-index.tsv']['sha256'] and lines[4]==x['sealed_metadata']['state.json']['sha256'],'seal metadata join')
   c=x['canonical'];member=prior_rows[c['member']];a=archive_rows[c['batch']]
   need((member['bytes'],member['sha256'])==(x['bytes'],x['raw_sha256']),'canonical raw SHA equality')
   need((a['name'],a['usb'],a['archive_bytes'],a['archive_sha256'])==(c['member'],c['path'],c['bytes'],c['sha256']),'completed canonical inventory')
 x=rows[EXPECTED[batch]];c=x['canonical']
 return dict(raw_path=x['raw_path'],relative_path=c['member'],bytes=x['bytes'],raw_sha256=x['raw_sha256'],canonical_archive=c['path'],canonical_archive_bytes=c['bytes'],canonical_archive_sha256=c['sha256'],profile=x['profile'],failed_run_stays_failed=x['failed_run_stays_failed'])

def raw_held(path,size):
 need(str(path) in EXPECTED and path.resolve()==path and C.USB.resolve()==C.USB and C.USB.stat().st_dev==C.USB_DEVICE,'fixed canonical raw path/device')
 fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
 try:
  st=os.fstat(fd);need(stat.S_ISREG(st.st_mode) and st.st_nlink==1 and st.st_dev==C.USB_DEVICE and st.st_size==size,'raw inode/extent/device');return fd,C.identity(st),dict(mode=stat.S_IMODE(st.st_mode),uid=st.st_uid,gid=st.st_gid,mtime_ns=st.st_mtime_ns,atime_ns=st.st_atime_ns)
 except BaseException:os.close(fd);raise

def descriptors(row):
 raw=Path(row['raw_path']);fd,stamp,metadata=raw_held(raw,row['bytes']);out=[(fd,raw,stamp)]
 try:
  target=Path(row['canonical_archive']);fd,stamp=C.held(target,row['canonical_archive_bytes']);out.append((fd,target,stamp));need(out[0][2][:2]!=out[1][2][:2],'distinct raw and canonical inode');return out,metadata
 except BaseException:
  for fd,_,_ in out:os.close(fd)
  raise
M.authority=authority;M.raw_held=raw_held;M.descriptors=descriptors
# Original verification/hash/member-readback/fsync/restore/separate-release bodies
# are used unchanged. __file__/P bind their receipts and review to this adapter.
def main():
 ap=argparse.ArgumentParser(description=__doc__);g=ap.add_mutually_exclusive_group(required=True);g.add_argument('--plan',action='store_true');g.add_argument('--verify',action='store_true');g.add_argument('--release-verified',action='store_true');ap.add_argument('--batch',type=int);a=ap.parse_args()
 if a.plan:
  authority(0);b=json.loads(BINDING.read_text());print(json.dumps(dict(source_only=True,rows=b['rows'],recoverable_bytes=1773945344,failed_class_a_stays_failed=True),indent=2));return
 need(a.batch is not None,'explicit batch');print(json.dumps(M.verify(a.batch) if a.verify else M.release(a.batch),indent=2))
if __name__=='__main__':main()
