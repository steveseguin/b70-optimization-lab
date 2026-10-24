#!/usr/bin/env python3
"""Fixed six F32 bundles plus ten draft files; failed A stays unqualified and every B canonical remains retained."""
from pathlib import Path
import argparse,gzip,hashlib,importlib.util,json,os,resource,shutil,stat
P=Path(__file__).resolve().parent;L=P.parents[1];R=L.parents[2]
PARENT=P.parent/'blank-draft-canonical/reuse.py'
PARENT_SHA='e54d2ad9f0067445273e08b1501ebe3246abfa747cbbcfabd6b01d764b1c1f05'
RAW=Path('/mnt/usb-models/own-xpu-runtime-results')
DEST=Path('/home/steve/own-xpu-runtime-results/gsq-recurrent-f32-canonical-a')
BINDING=P/'closure-binding.json';BINDING_SHA='39b90f1ac8f821ad43f7b98a7e3ca13121ad5845603d38d3b23f4dc8a6c1babd'
BINARY='5926a24746c62c6b0ecdc5c3e4895f310145e0f9d74a90a5d657035b9a8151f4'
PLAN='67add3de84d91bf85d09e3d98d73ac1d5dc46306b24056682ad8b249b576e1ee'
PAIRS=(('gsq-recurrent-f32-a/rank0/state-2147483647/state.bundle', 'gsq-recurrent-f32-b/rank0/state-2147483647/state.bundle', 184765556), ('gsq-recurrent-f32-a/rank1/state-2147483647/state.bundle', 'gsq-recurrent-f32-b/rank1/state-2147483647/state.bundle', 125598668), ('gsq-recurrent-f32-a/prompt-00-none/rank0/state-2147483647/state.bundle', 'gsq-recurrent-f32-b/prompt-00-none/rank0/state-2147483647/state.bundle', 184765556), ('gsq-recurrent-f32-a/prompt-00-none/rank1/state-2147483647/state.bundle', 'gsq-recurrent-f32-b/prompt-00-none/rank1/state-2147483647/state.bundle', 125598668), ('gsq-recurrent-f32-b/prompt-00-mtp/rank0/state-2147483647/state.bundle', 'gsq-recurrent-f32-b/prompt-00-none/rank0/state-2147483647/state.bundle', 184765556), ('gsq-recurrent-f32-b/prompt-00-mtp/rank1/state-2147483647/state.bundle', 'gsq-recurrent-f32-b/prompt-00-none/rank1/state-2147483647/state.bundle', 125598668), ('gsq-recurrent-f32-a/rank0/draft-final-state/blk.0.qsa.keys.bin', 'gsq-recurrent-f32-b/prompt-00-none/rank0/draft-final-state/blk.0.qsa.keys.bin', 4194304), ('gsq-recurrent-f32-a/rank0/draft-final-state/blk.0.qsa.pooled.bin', 'gsq-recurrent-f32-b/prompt-00-none/rank0/draft-final-state/blk.0.qsa.pooled.bin', 262144), ('gsq-recurrent-f32-a/rank0/draft-final-state/blk.0.qsa.raw.bin', 'gsq-recurrent-f32-b/prompt-00-none/rank0/draft-final-state/blk.0.qsa.raw.bin', 1048576), ('gsq-recurrent-f32-a/rank0/draft-final-state/blk.0.qsa.values.bin', 'gsq-recurrent-f32-b/prompt-00-none/rank0/draft-final-state/blk.0.qsa.values.bin', 4194304), ('gsq-recurrent-f32-a/rank0/draft-final-state/position.bin', 'gsq-recurrent-f32-b/prompt-00-none/rank0/draft-final-state/position.bin', 4), ('gsq-recurrent-f32-b/rank0/draft-final-state/blk.0.qsa.keys.bin', 'gsq-recurrent-f32-b/prompt-00-none/rank0/draft-final-state/blk.0.qsa.keys.bin', 4194304), ('gsq-recurrent-f32-b/rank0/draft-final-state/blk.0.qsa.pooled.bin', 'gsq-recurrent-f32-b/prompt-00-none/rank0/draft-final-state/blk.0.qsa.pooled.bin', 262144), ('gsq-recurrent-f32-b/rank0/draft-final-state/blk.0.qsa.raw.bin', 'gsq-recurrent-f32-b/prompt-00-none/rank0/draft-final-state/blk.0.qsa.raw.bin', 1048576), ('gsq-recurrent-f32-b/rank0/draft-final-state/blk.0.qsa.values.bin', 'gsq-recurrent-f32-b/prompt-00-none/rank0/draft-final-state/blk.0.qsa.values.bin', 4194304), ('gsq-recurrent-f32-b/rank0/draft-final-state/position.bin', 'gsq-recurrent-f32-b/prompt-00-none/rank0/draft-final-state/position.bin', 4))
TOTAL=950491336;FLOOR=27000000000+64*1024**2
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(v,m):
 if not v:raise ValueError(m)
need(sha(PARENT)==PARENT_SHA,'frozen held-file primitives')
s=importlib.util.spec_from_file_location('quality_pair_private_raw_primitives',PARENT);M=importlib.util.module_from_spec(s);s.loader.exec_module(M);M.RAW=RAW

def closed(a,at,b,bt):
 need(a['evidence_review_passed'] and a['run_qualification_passed'] is False and not a['completed_pair'] and a['safe_owner_teardowns']==2 and a['physical_drain'] and a['both_physical_contacts'] and a['kernel_baseline_unchanged'],'failed A safely closed forensic authority')
 need(at['passed'] is False and at['children_exited'] and at['target_descriptors_empty'] and at['observed_target_contact']==[True,True] and at['result'] is None,'failed A not promoted')
 need(b['passed'] and b['corrected_target_mtp_exact'] and b['target_bundles']==6 and b['native_binary_sha256']==BINARY and b['plan_sha256']==PLAN and b['physical_drain'] and b['kernel_fault_baseline_unchanged'],'qualified B closed byte authority')
 need(b['capture_budget']['stage']==5 and b['capture_budget']['remaining_payload_bytes']==0,'B complete captures')
 need(bt['passed'] and bt['children_exited'] and bt['target_descriptors_empty'] and bt['observed_target_contact']==[True,True] and bt['first_error'] is None and bt['original_error'] is None and bt['plan_sha256']==PLAN,'B two-owner physical closure')
 need(b['full_result_sha256']==bt['result']['full_result_sha256'] and len(b['owners'])==2 and all(x['safe_to_exit'] and x['in_flight']==x['live_bytes']==x['exit_code']==0 for x in b['owners']),'B safe native owners')

def mapping(index,seals,draft):
 found={}
 for x in index:
  if x['root']=='evidence':
   key='gsq-recurrent-f32-b/'+x['path'];need(key not in found,'duplicate B inventory');found[key]=x
 result=[]
 for i,(original,canonical,size) in enumerate(PAIRS):
  b=found[canonical];h=b['sha256'];need(b['bytes']==size and len(h)==64 and all(c in '0123456789abcdef' for c in h),'canonical full extent/hash')
  if i<4:
   fields=seals[i].splitlines();need(len(fields)==5 and fields[0]=='GSQ_STATE_SEAL_V1' and int(fields[1])==size and fields[2]==h,'A declared seal matches B; root full bytes still required')
  elif original.startswith('gsq-recurrent-f32-a/'):
   key='card0:draft:'+Path(original).name[:-4];need(draft['position']==0 and draft['disabled'] is False and draft['mutable_sha256'][key]==h,'failed A draft declared identity; full readback still required')
  else:
   a=found[original];need(a['bytes']==size and a['sha256']==h,'audited B original equals retained canonical')
  result.append(dict(batch=i,original=original,canonical=canonical,bytes=size,sha256=h))
 need(len(result)==16 and sum(x['bytes'] for x in result)==TOTAL,'fixed sixteen recovery extent');return result

def authority(batch):
 need(type(batch)is int and 0<=batch<16,'fixed batch0..15')
 need(sha(BINDING)==BINDING_SHA,'exact closed binding');v=json.loads(BINDING.read_text())
 need(v['passed'] and v['A_qualified'] is False and v['released_paths']==[x[0] for x in PAIRS],'fixed sixteen release scope')
 files={k:Path(x['path']) for k,x in v['files'].items()}
 for k,f in files.items():need(sha(f)==v['files'][k]['sha256'],'closure metadata '+k)
 a=json.loads(files['a_review'].read_text());b=json.loads(files['b_review'].read_text())
 closed(a,json.loads(files['a_terminal'].read_text()),b,json.loads(files['b_terminal'].read_text()))
 need(a['terminal_sha256']==v['files']['a_terminal']['sha256'] and b['index_sha256']==v['files']['b_index']['sha256'] and b['full_result_sha256']==v['files']['b_result']['sha256'],'actual index/result closure joins')
 with gzip.open(files['b_index'],'rt') as f:
  rows=[]
  for line in f:need(len(line)<=16384,'bounded index row');rows.append(json.loads(line));need(len(rows)<=10000,'bounded inventory')
 return mapping(rows,{i:files['a_seal_'+str(i)].read_text() for i in range(4)},json.loads(files['a_draft_metadata'].read_text()))[batch]

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
 if a.plan:print(json.dumps(dict(rows=[authority(i) for i in range(16)],recoverable_bytes=TOTAL),indent=2));return
 need(a.batch is not None,'explicit batch');print(json.dumps(verify(a.batch) if a.verify else release(a.batch),indent=2))
if __name__=='__main__':main()
