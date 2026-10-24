#!/usr/bin/env python3
"""Fixed24 closed expanded MTP bundles; retain same-run target-only originals."""
from pathlib import Path
import argparse,gzip,hashlib,importlib.util,json,os,resource,shutil,stat
P=Path(__file__).resolve().parent;L=P.parents[1];R=L.parents[2]
PARENT=P.parent/'blank-draft-canonical/reuse.py'
PARENT_SHA='e54d2ad9f0067445273e08b1501ebe3246abfa747cbbcfabd6b01d764b1c1f05'
RAW=Path('/mnt/usb-models/own-xpu-runtime-results/gsq-quality-expanded-a')
DEST=Path('/home/steve/own-xpu-runtime-results/gsq-quality-pair-canonical-a')
REVIEW=L/'quality-expanded/evidence/device-a/review.json'
TERMINAL=Path('/home/steve/own-xpu-runtime-results/gsq-quality-expanded-a.control/terminal.json')
BINDING=P/'closure-binding.json';BINDING_SHA='f0ce678c875dc9da8b41e6e250ebd3964b09693f586683c895b938ce9e49fea7'
BINARY='5aef74d5f803b33758711db352ee5e1a393a364e6c33aa9f8a4cdb4478f5fe6a'
PLAN='e95aba2d48f73b40ae4ef077cb8d2182da09e06bea61184697806c550a006169'
PAIRS=tuple((f'prompt-{i:02d}-mtp/rank{rank}/state-2147483647/state.bundle',f'prompt-{i:02d}-none/rank{rank}/state-2147483647/state.bundle',125561972 if rank==0 else 96181196) for i in range(12) for rank in (0,1))
TOTAL=2660918016;FLOOR=27000000000+64*1024**2
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(v,m):
 if not v:raise ValueError(m)
need(sha(PARENT)==PARENT_SHA,'frozen held-file primitives')
s=importlib.util.spec_from_file_location('quality_pair_private_raw_primitives',PARENT);M=importlib.util.module_from_spec(s);s.loader.exec_module(M);M.RAW=RAW

def closed(r,t):
 need(r['passed'] and r['all12_target_mtp_exact'] and r['all24_original_prefixes_exact'] and r['requests']==26 and r['measured_arms']==24 and r['bundles']==54,'complete expanded byte audit')
 need(r['native_binary_sha256']==BINARY and r['plan_sha256']==PLAN and r['physical_drain'] and r['kernel_fault_baseline_unchanged'],'exact closed physical qualification')
 need(r['quality_qualified'] is False and r['manual_full_output_review_required'] is True,'exactness is not manual task quality')
 b=r['capture_budget'];need(b['finished'] and b['remaining_payload_bytes']==0 and b['resets']==26 and b['target_dumps']==24 and b['final_repeats']==1 and len(b['events'])==52,'closed acknowledged captures')
 need(t['passed'] and t['children_exited'] and t['target_descriptors_empty'] and t['observed_target_contact']==[True,True] and t['first_error'] is None and t['original_error'] is None,'positive two-owner closure')
 need(r['full_result_sha256']==t['result']['full_result_sha256'] and t['plan_sha256']==PLAN,'terminal result identity')
 need(len(r['owners'])==2 and all(o['safe_to_exit'] and o['in_flight']==o['live_bytes']==o['exit_code']==0 for o in r['owners']),'safe native teardown')

def mapping(rows):
 names={n for a,b,_ in PAIRS for n in (a,b)};found={}
 for x in rows:
  if x['root']=='evidence' and x['path'] in names:
   need(x['path'] not in found,'duplicate audited bundle');found[x['path']]=x
 need(set(found)==names,'all48 measured physical bundles indexed')
 result=[]
 for i,(original,canonical,size) in enumerate(PAIRS):
  a,b=found[original],found[canonical];h=a['sha256']
  need(a['bytes']==b['bytes']==size and h==b['sha256'] and len(h)==64 and all(c in '0123456789abcdef' for c in h),'same-run full physical bundle equality')
  result.append(dict(batch=i,original=original,canonical=canonical,bytes=size,sha256=h))
 need(sum(x['bytes'] for x in result)==TOTAL,'fixed24 recovery extent');return result

def authority(batch):
 need(type(batch)is int and 0<=batch<24,'fixed batch0..23')
 need(BINDING_SHA is not None and sha(BINDING)==BINDING_SHA,'actual expanded closure/release binding pending')
 b=json.loads(BINDING.read_text());need(b['passed'] is True and b['released_paths']==[x[0] for x in PAIRS],'explicit24-path release')
 paths=dict(review=REVIEW,index=REVIEW.parent/'artifact-index.jsonl.gz',terminal=TERMINAL,full_result=RAW/'resident-suite.json')
 for k,p in paths.items():need(Path(b[k]['path'])==p and sha(p)==b[k]['sha256'],'fixed actual '+k+' identity')
 r=json.loads(REVIEW.read_text());closed(r,json.loads(TERMINAL.read_text()))
 need(r['index_sha256']==b['index']['sha256'] and r['full_result_sha256']==b['full_result']['sha256'],'audited index/result binding')
 with gzip.open(paths['index'],'rt') as f:
  rows=[]
  for line in f:need(len(line)<=16384,'bounded index row');rows.append(json.loads(line));need(len(rows)<=10000,'bounded artifact inventory')
 return mapping(rows)[batch]

def review():
 p=P/'evidence/independent-review.json';r=json.loads(p.read_text());need(r['passed'] and r['source_sha256'],'independent reviewed source')
 for f,h in r['source_sha256'].items():need(sha(R/f)==h,'reviewed source drift')
 return sha(p)
def syncdir(p):
 fd=os.open(p,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
 try:os.fsync(fd)
 finally:os.close(fd)
def anchor():
 need(os.getpriority(os.PRIO_PROCESS,0)==19 and os.sched_getaffinity(0)<=set(range(8,16))|set(range(24,32)),'bounded helper placement');resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
 need(shutil.disk_usage(DEST.parent).free>=FLOOR,'unchanged NVMe floor plus64MiB')
 need(RAW.resolve()==RAW and RAW.stat().st_dev==2050 and DEST.parent.resolve()==DEST.parent and DEST.parent.stat().st_dev!=2050,'expected USB and private NVMe roots')
 if not os.path.lexists(DEST):DEST.mkdir(mode=0o700);syncdir(DEST.parent)
 st=DEST.lstat();need(stat.S_ISDIR(st.st_mode) and not DEST.is_symlink() and st.st_uid==os.getuid() and stat.S_IMODE(st.st_mode)==0o700,'private metadata directory')
def held(row,role):
 M.SIZE=row['bytes'];M.ZERO=row['sha256'];return M.held(row[role])
def verify(batch):
 row=authority(batch);review_sha=review();anchor();d=DEST/f'batch-{batch:02d}';d.mkdir(mode=0o700);syncdir(DEST)
 result=dict(passed=False,phase='verify',mapping=row,helper_sha256=sha(__file__),binding_sha256=BINDING_SHA,source_review_sha256=review_sha);fds=[]
 try:
  for role in ('original','canonical'):
   fd,meta=held(row,role);fds.append(fd);result[role]=meta
  need(result['original']['identity'][:2]!=result['canonical']['identity'][:2],'distinct retained canonical inode')
  restore=dict(mapping=row,original=result['original'],canonical=result['canonical'],restore='Copy the retained canonical raw bundle into the original relative path exclusively, verify its length/SHA, then restore original mode/uid/gid/mtime. Keep existing index/seal/state JSON unchanged. No compressed container or unique state bytes are removed.')
  M.save(d/'restore.json',restore);result['restore_sha256']=sha(d/'restore.json')
  for fd,role in zip(fds,('original','canonical')):M.still_held(fd,row[role],result[role]['identity'])
  result['passed']=True
 except BaseException as e:result['error']=repr(e);raise
 finally:
  for fd in fds:os.close(fd)
  M.save(d/'verified.json',result)
 return result
def release(batch):
 row=authority(batch);review_sha=review();anchor();d=DEST/f'batch-{batch:02d}'
 need(d.resolve()==d and d.is_dir() and not os.path.lexists(d/'release-before.json') and not os.path.lexists(d/'released.json'),'verified fresh release phase')
 v=json.loads((d/'verified.json').read_text());need(v['passed'] and v['mapping']==row and v['helper_sha256']==sha(__file__) and v['binding_sha256']==BINDING_SHA and v['source_review_sha256']==review_sha,'exact successful verification')
 need(sha(d/'restore.json')==v['restore_sha256'],'durable restore identity');restore=json.loads((d/'restore.json').read_text());need(restore['mapping']==row and all(restore[k]==v[k] for k in ('original','canonical')),'complete restore metadata')
 result=dict(passed=False,phase='release',mapping=row,verified_sha256=sha(d/'verified.json'),restore_sha256=v['restore_sha256'],released=False);fds=[]
 try:
  for role in ('original','canonical'):
   fd,meta=held(row,role);fds.append(fd);need(meta==v[role],'verified full bytes and inode metadata unchanged')
  need(v['original']['identity'][:2]!=v['canonical']['identity'][:2],'never remove canonical inode')
  M.save(d/'release-before.json',result)
  for fd,role in zip(fds,('original','canonical')):M.still_held(fd,row[role],v[role]['identity'])
  os.unlink(RAW/row['original']);result['released']=True;syncdir((RAW/row['original']).parent)
  M.still_held(fds[1],row['canonical'],v['canonical']['identity']);need(not os.path.lexists(RAW/row['original']),'only mapped original absent');result['passed']=True
 except BaseException as e:result['error']=repr(e);raise
 finally:
  for fd in fds:os.close(fd)
  M.save(d/'released.json',result)
 return result
def main():
 ap=argparse.ArgumentParser(description=__doc__);g=ap.add_mutually_exclusive_group(required=True);g.add_argument('--plan',action='store_true');g.add_argument('--verify',action='store_true');g.add_argument('--release-verified',action='store_true');ap.add_argument('--batch',type=int);a=ap.parse_args()
 if a.plan:print(json.dumps(dict(rows=[authority(i) for i in range(24)],recoverable_bytes=TOTAL),indent=2));return
 need(a.batch is not None,'explicit batch');print(json.dumps(verify(a.batch) if a.verify else release(a.batch),indent=2))
if __name__=='__main__':main()
