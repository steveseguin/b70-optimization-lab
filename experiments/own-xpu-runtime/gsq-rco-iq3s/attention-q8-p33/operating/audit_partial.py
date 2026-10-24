#!/usr/bin/env python3
"""Closed incomplete candidate readback. Root must authorize --run after storage.
No runtime import or device/service operations. Completion remains false even
when every previously completed arm verifies against the original baseline.
"""
import argparse,gzip,hashlib,importlib.util,json,os,resource,stat,time
from pathlib import Path
P=Path(__file__).resolve().parent;L=P.parent.parent;R=L.parents[2]
BASE=L/'baseline/audit.py';BASE_SHA='43154e5b8101fb879eb08bbbebc29714443dd083cb90df6fbbb7e269d522d0ab'
if hashlib.sha256(BASE.read_bytes()).hexdigest()!=BASE_SHA:raise RuntimeError('frozen baseline auditor changed')
s=importlib.util.spec_from_file_location('candidate_partial_baseline_audit',BASE);B=importlib.util.module_from_spec(s);s.loader.exec_module(B)
read,sha,require=B.read,B.sha,B.require
C=Path('/home/steve/own-xpu-runtime-results/gsq-attention-p33-a.control');E=Path('/mnt/usb-models/own-xpu-runtime-results/gsq-attention-p33-a')
PRIOR=L/'baseline/evidence/independent-a/review.json';PRIOR_SHA='f662fcecf93c92f90006c09c05d4a4c02e71e84ae9d8c82dbff3fdfc39ebb5bb'
REFERENCE=Path('/mnt/usb-models/own-xpu-runtime-results/gsq-baseline-a/resident-suite.json')
INCIDENT=P/'evidence/storage-incident-a/review.json';INCIDENT_SHA='5a09935d92fdd5f3815146fabc2465d8240427db8813e3c4761d208c7fa9c212'

def expected_arms():
 return [f'prompt-{i:02d}-{mode}' for i in range(7) for mode in (['none','mtp'] if i%2==0 else ['mtp','none'])]
def exact_arm(row,reference):
 require(row['name']==reference['name'] and row['mode']==reference['mode'] and row['measured'] and row['requested_max_new']==128,'corresponding measured arm')
 require(row['prompt_tokens']==reference['prompt_tokens'],'original prompt tokens')
 require(row['result']['tokens']==reference['result']['tokens'],'candidate tokens differ from baseline')
 require(row['state_sha256']==reference['state_sha256'],'candidate state maps differ from baseline')
 B.timing(row['result'],128);B.confirmed_inputs(row['result'],row['prompt_tokens'])
 if row['mode']=='mtp':B.guess_outcomes(row['result'],row['prompt_tokens'],128)
 else:require(all(row['result']['stats'][k]==0 for k in ('guesses','hits','misses')),'target-only stats')
def run():
 require(os.getpriority(os.PRIO_PROCESS,0)==19,'nice19');require(os.sched_getaffinity(0)<=set(range(8,16))|set(range(24,32)),'helper cores');resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
 dest=P/'evidence/partial-independent-a';dest.mkdir(exist_ok=False);start=time.monotonic()
 result=dict(schema='ownrt.gsq.attention-incomplete-readback.v1',passed=False,incomplete=True,audit_passed=False,verified_prior_arms=0,owner_success_claimed=False,device_executed_by_reviewer=False,combined_resident_benchmark_claimed=False)
 try:
  require(sha(PRIOR)==PRIOR_SHA and sha(INCIDENT)==INCIDENT_SHA,'immutable reviews');prior=read(PRIOR);incident=read(INCIDENT)
  require(prior['passed'] and prior['all12_exact'] and incident['metadata_review_passed'] and not incident['candidate_full_qualification_passed'],'review scope')
  require(sha(REFERENCE)==prior['full_result_sha256'],'baseline full result');baseline=read(REFERENCE);refs={arm['name']:arm for pair in baseline['prompts'] for arm in pair['arms']};require(len(refs)==24,'baseline arms')
  plan=read(C/'plan.json');admission=read(C/'admission.json');terminal=read(C/'terminal.json')
  require(terminal['passed'] is False and terminal['result'] is None and terminal['children_exited'] and terminal['target_descriptors_empty'],'closed incomplete terminal')
  require(terminal['plan_sha256']==admission['plan_sha256']==sha(C/'plan.json') and admission['plan']==plan,'admitted plan')
  require(terminal['first_error']==terminal['original_error']==incident['first_controller_error'],'original incident')
  for name,description in incident['files'].items():require(sha(C/name)==description['sha256'],'incident source changed')
  require(plan['suite']['baseline_review_sha256']==PRIOR_SHA and plan['suite']['baseline_result_sha256']==prior['full_result_sha256'],'baseline plan reference')
  for mapping in (plan['source_sha256'],plan['suite']['source_sha256'],plan['adapter']['source_sha256']):
   for path,h in mapping.items():require(sha(R/path)==h,'admitted source '+path)
  native=read(plan['adapter']['build_receipt']);require(native['passed'] and sha(plan['adapter']['build_receipt'])==plan['adapter']['build_receipt_sha256'],'candidate build')
  require(sha(plan['adapter']['binary'])==native['binary_sha256']==plan['adapter']['binary_sha256'],'candidate binary')
  for mapping in (native['source_sha256'],native['object_sha256']):
   for path,h in mapping.items():require(sha(R/path)==h,'native source/object '+path)
  names=expected_arms();markers={p.parent.name for p in E.glob('prompt-*/baseline-exact.json')};require(markers==set(names),'exactly14 completed arm markers')
  require(not (E/'resident-suite.json').exists(),'no completed full result')
  require({p.name for p in E.glob('pair-*.json')}=={f'pair-{i:02d}.json' for i in range(7)},'exactly7 completed pairs')
  count=total=raw_states=0;arms=[]
  with (dest/'artifact-index.jsonl.gz').open('xb') as raw,gzip.GzipFile(fileobj=raw,mode='wb',filename='',mtime=0) as index:
   def retain(path):
    nonlocal count,total
    require(not path.is_symlink() and path.is_file(),'regular closed artifact');h=sha(path);size=path.stat().st_size;count+=1;total+=size;require(count<=40000 and total<=3500*1024**2,'partial readback bound')
    index.write((json.dumps(dict(path=str(path),bytes=size,sha256=h),separators=(',',':'))+'\n').encode());return h,size
   for number,name in enumerate(names,3):
    base=E/name;row=read(base/'suite-request.json');require(row['request']==number,'serial request ordinal');exact_arm(row,refs[name]);retain(base/'suite-request.json')
    marker=read(base/'baseline-exact.json');require(marker['passed'] and marker['reference_sha256']==prior['full_result_sha256'],'live baseline gate');retain(base/'baseline-exact.json')
    armbytes=0
    for rank in (0,1):
     resetpath=base/f'rank{rank}/reset.json';reset=read(resetpath);require(reset['passed'] and reset['allocation_ids_preserved'],'full RESET');retain(resetpath)
     directory=base/f'rank{rank}/state-2147483647';actual={}
     for path in sorted(directory.rglob('*')):
      require(not path.is_symlink(),'state symlink')
      if path.is_file():
       h,size=retain(path);actual[str(path.relative_to(directory))]=h
       if path.suffix=='.bin':armbytes+=size
     require(actual==row['state_sha256'][str(rank)]==refs[name]['state_sha256'][str(rank)],'raw state exact to baseline')
     state=read(directory/'state.json')
     for buffer,h in state['buffers'].items():
      filename=('alternate-'+buffer.split(':',1)[1] if buffer.startswith('alternate:') else buffer)+'.bin';require(actual[filename]==h,'native state manifest')
    require(armbytes==221743168,'full target state extent');raw_states+=armbytes
    arms.append(dict(name=name,mode=row['mode'],request=row['request'],tokens=row['result']['tokens'],baseline_tokens_exact=True,baseline_state_exact=True,raw_state_bytes=armbytes,termination='eos' if row['result']['tokens'][-1] in B.EOS else 'cap'))
   for i in range(7):
    pairpath=E/f'pair-{i:02d}.json';pair=read(pairpath);require(pair['exact_tokens'] and pair['exact_final_target_state'] and pair['prompt_id']==baseline['prompts'][i]['prompt_id'],'closed pair identity')
    for arm in pair['arms']:require(arm==read(E/arm['name']/'suite-request.json'),'pair/raw arm identity')
    retain(pairpath)
  # Only stat names/extents for the failed request; never hash its partial .bin.
  partial=[]
  failed=E/'prompt-07-mtp'
  if failed.exists():
   for path in sorted(failed.rglob('*')):
    st=path.lstat();require(not stat.S_ISLNK(st.st_mode),'failed request symlink')
    if stat.S_ISREG(st.st_mode):partial.append(dict(path=str(path.relative_to(failed)),bytes=st.st_size,mtime_ns=st.st_mtime_ns))
    require(len(partial)<=3000,'bounded partial file inventory')
  pfile=dest/'failed-request-inventory.json.gz'
  with pfile.open('xb') as raw,gzip.GzipFile(fileobj=raw,mode='wb',filename='',mtime=0) as z:z.write((json.dumps({'scope':'metadata only, no completion or byte-exactness claim','request':'prompt-07-mtp','files':partial},separators=(',',':'))+'\n').encode())
  result.update(audit_passed=True,verified_prior_arms=14,verified_prior_pairs=7,verified_prompt_indices=list(range(7)),arms=arms,raw_target_state_bytes=raw_states,indexed_artifacts=count,indexed_bytes=total,index_sha256=sha(dest/'artifact-index.jsonl.gz'),partial_inventory_sha256=sha(pfile),partial_files=len(partial),failed_request='prompt-07-mtp',baseline_review_sha256=PRIOR_SHA,baseline_full_result_sha256=prior['full_result_sha256'],incident_review_sha256=INCIDENT_SHA,plan_sha256=sha(C/'plan.json'),native_binary_sha256=native['binary_sha256'],rank_identities=terminal['rank_identities'],children_exited_and_physical_drain_attested=True,new_classified_gpu_fault=False,scope='Only14 completed arms raw-verified; qualification remains incomplete after storage write failure. Later experiments must not concatenate timings into a single resident benchmark.',limitations=['No clean native owner success claim: failure receipt writes aborted','No partial prompt07 output/state correctness or completion claim','Baseline original raw files may be losslessly archived; authority is immutable prior independent full readback and original full-result maps','Physical drain/fault classification uses retained NVMe incident evidence; no new host/device query'])
 except BaseException as e:result['audit_error']=type(e).__name__+': '+str(e);raise
 finally:
  result.update(auditor_sha256=sha(__file__),parent_auditor_sha256=BASE_SHA,elapsed_seconds=time.monotonic()-start)
  with (dest/'review.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
 print(json.dumps({'audit_passed':True,'qualification_passed':False,'verified_prior_arms':14,'review':str(dest/'review.json'),'sha256':sha(dest/'review.json')}))
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--run',action='store_true',required=True);ap.parse_args();run()
if __name__=='__main__':main()
