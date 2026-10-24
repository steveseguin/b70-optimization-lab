#!/usr/bin/env python3
"""Closed native three-target metadata audit, including expected token mismatch. No bundle payload reads."""
import argparse,hashlib,importlib.util,json,os,stat
from pathlib import Path
P=Path(__file__).resolve().parent;L=P.parents[2];R=L.parents[2]
C=Path('/home/steve/own-xpu-runtime-results/gsq-recurrent-f32-longer-a.control')
E=Path('/mnt/usb-models/own-xpu-runtime-results/gsq-recurrent-f32-longer-a')
PLAN_SHA='c34590d2d13d6590d0387c3a01690c18666d419fd78314d1fad92c3433d2f074'
REFERENCE_SHA='80895690ba537319cdb091b32cde971ff76d415bba667e32d337662919451b48'
BINARY='5926a24746c62c6b0ecdc5c3e4895f310145e0f9d74a90a5d657035b9a8151f4'
MISMATCH='corrected target differs from independent CPU reference; stop remaining requests'
B_PATH=L/'baseline/audit.py';B_SHA='43154e5b8101fb879eb08bbbebc29714443dd083cb90df6fbbb7e269d522d0ab'
def need(v,m):
 if not v:raise ValueError(m)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
# Only pure trace/timing validators are reused; no parent run() call.
s=importlib.util.spec_from_file_location('closed_native_trace_oracle',B_PATH);B=importlib.util.module_from_spec(s);s.loader.exec_module(B)
def stamp(s):return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
ARTIFACTS={};TOTAL=0
def read(p):
 global TOTAL
 p=Path(p);need(p.resolve()==p and p.suffix=='.json','fixed canonical JSON metadata only');fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
 try:
  a=os.fstat(fd);need(stat.S_ISREG(a.st_mode) and a.st_nlink==1 and a.st_size<=16<<20,'bounded regular metadata');data=bytearray()
  while len(data)<a.st_size:
   x=os.read(fd,min(65536,a.st_size-len(data)));need(x,'truncated metadata');data.extend(x)
  need(stamp(a)==stamp(os.fstat(fd))==stamp(os.stat(p,follow_symlinks=False)),'metadata changed');h=hashlib.sha256(data).hexdigest()
  if str(p)not in ARTIFACTS:TOTAL+=len(data)
  need(TOTAL<=64<<20,'64MiB metadata read bound');ARTIFACTS[str(p)]={'sha256':h,'bytes':len(data),'identity':stamp(a)};return json.loads(data)
 finally:os.close(fd)
def comparison(tokens,case):
 ref=case['tokens'];first=next((i for i,(x,y) in enumerate(zip(tokens,ref)) if x!=y),None)
 if first is None and len(tokens)!=len(ref):first=min(len(tokens),len(ref))
 stop='eos' if tokens and tokens[-1]in (248044,248046) else 'limit'
 return dict(equal=tokens==ref and stop==case['stop_type'],first_difference=first,native_stop_type=stop,reference_stop_type=case['stop_type'],reference_tokens=ref,scope='Full raw-ID trajectory equality; after first divergence later logits have different conditional prefixes')
def reference_at_difference(response,native_tokens,index):
 ref=response['tokens'];probs=response['completion_probabilities']
 aligned=len(probs)==len(ref) and [r['id'] for r in probs]==ref
 if not aligned or index>=len(ref) or index>=len(native_tokens):
  return dict(unambiguous_probability_position=False,reason='Missing probability rows or length-only divergence; no per-position rank inferred')
 row=probs[index];top=row['top_logprobs'];need(len(top)==32 and len({r['id'] for r in top})==32,'qualified reference top32')
 logs=[r['logprob'] for r in top];need(logs==sorted(logs,reverse=True) and row['logprob']==logs[0],'reference sorted greedy row')
 native=native_tokens[index];candidate=[(i,r) for i,r in enumerate(top) if r['id']==native];reference=[i for i,r in enumerate(top) if r['id']==ref[index]];need(len(reference)==1,'selected reference candidate')
 return dict(unambiguous_probability_position=True,generated_index_zero_based=index,reference_selected_token=ref[index],native_selected_token=native,reference_top2_logprob_margin=logs[0]-logs[1],reference_selected_rank_in_reference_top32=reference[0]+1,native_selected_rank_in_reference_top32=candidate[0][0]+1 if candidate else None,native_selected_logprob_in_reference=candidate[0][1]['logprob'] if candidate else None,native_selected_outside_reference_top32=not candidate,reference_selected_logprob=row['logprob'],reference_top32=top,scope='Ranks/probabilities are in the independent CPU reference distribution at the shared prefix; native first-divergence logits are not retained')

def passive(before,after,term):
 flags={}
 flags['physical_drain']=bool(term['children_exited'] and term['target_descriptors_empty'])
 flags['both_contacts']=term['observed_target_contact']==[True,True]
 flags['no_unexpected_actions']=term['retries']==term['hard_kills']==term['service_changes']==0
 flags['fault_baseline']=before['boot']==after['boot'] and before['kernel']['faults']==after['kernel']['faults'] and after['known_fault_baseline_matches']
 flags['topology_queue']=before['drm']==after['drm'] and before['queue']==after['queue']
 flags['vision_unit']=before['units']['qwen38-27b-vision']==after['units']['qwen38-27b-vision']
 flags['vision_identity']=after['holders'].get('3487303',{}).get('start_ticks')==63453537
 flags['complete_inventory']=not after['identity_races'] and not after['inventory']['errors']
 flags['only_vision_fds']=all(h['pid']==3487303 and after['drm'][h['node']]['bdf']in ('0000:27:00.0','0000:43:00.0') for h in after['inventory']['holders'])
 flags['same_vision_nodes']={h['node'] for h in before['inventory']['holders']}=={h['node'] for h in after['inventory']['holders']}
 return flags
def classify(term,ownership,owners,passive_flags,rows,incident,rank_errors):
 safe=all(passive_flags.values()) and not ownership['retained_pids'] and ownership['signals_sent']==0 and not ownership['diagnostic_errors'] and all(o['safe_to_exit'] and o['in_flight']==o['live_bytes']==o['exit_code']==0 for o in owners)
 mismatch=bool(rows and not rows[-1]['equal'])
 primary=repr(ValueError(MISMATCH))
 expected=mismatch and term['passed'] is False and term['result'] is None and term['original_error']==term['first_error']==primary and incident is not None and incident['error']==primary and ownership['stop_requested'] and ownership['returncodes']==[1,1] and rank_errors==['cooperative rank stop']*2
 if expected and safe:return 'numerical_mismatch_safely_closed',True
 if term['passed'] and len(rows)==3 and all(r['equal'] for r in rows) and safe and ownership['returncodes']==[0,0] and not ownership['stop_requested'] and rank_errors==['','']:return 'all_three_token_trajectories_equal_metadata_only',True
 return 'owner_fault_or_other_runtime_failure',False

def run():
 need(sha(B_PATH)==B_SHA,'pure trace source identity');plan=read(P/'plan.json');need(ARTIFACTS[str(P/'plan.json')]['sha256']==PLAN_SHA,'fixed admitted plan')
 need(read(C/'plan.json')==plan and ARTIFACTS[str(C/'plan.json')]['sha256']==PLAN_SHA,'actual plan')
 ad=read(C/'admission.json');term=read(C/'terminal.json');need(term['children_exited'] and term['target_descriptors_empty'],'closed owner prerequisite')
 need(ad['plan']==plan and ad['plan_sha256']==term['plan_sha256']==PLAN_SHA,'admission binding')
 need(hashlib.sha256(json.dumps(plan,sort_keys=True,separators=(',',':')).encode()).hexdigest()==ad['canonical_plan_sha256'],'canonical plan')
 for k,v in plan['unit_properties'].items():need(ad['unit'][k]==v,'safe unit properties')
 for mapping in [plan['source_sha256'],plan['suite']['source_sha256'],plan['adapter']['source_sha256']]:
  for f,h in mapping.items():need(sha(R/f)==h,'source identity '+f)
 need(plan['requests']==3 and plan['startup_max_new']==128 and plan['suite']['max_new']==512 and plan['adapter']['binary_sha256']==BINARY,'actual scope/binary')
 refpath=L/'reference-cpu/runtime-longer-a/evidence/closed-readback-review.json';ref=read(refpath);need(ARTIFACTS[str(refpath)]['sha256']==REFERENCE_SHA and ref['passed'] and ref['owner_exited'] and ref['returncode']==0,'independent closed reference')
 need(plan['suite']['cases']==ref['cases'],'reference cases identity')
 rows=[];seen_missing=False
 for i,case in enumerate(ref['cases']):
  p=E/f'prompt-{i:02d}-none/request-result.json'
  if not p.exists():seen_missing=True;continue
  need(not seen_missing and not (rows and not rows[-1]['equal']),'no request after missing/mismatched result')
  row=read(p);need(row['name']==f'prompt-{i:02d}-none' and row['prompt_id']==case['id'] and row['mode']=='none' and row['prompt_tokens']==case['prompt_tokens'] and row['requested_max_new']==512,'fixed raw target request')
  result=row['result'];tokens=result['tokens'];need(0<len(tokens)<=512 and all(type(t)is int and 0<=t<248320 for t in tokens),'native token extent')
  need(len(tokens)==512 or tokens[-1]in (248044,248046),'native natural EOS/cap')
  need(all(result['stats'][k]==0 for k in ('guesses','hits','misses')),'target-only mode')
  B.confirmed_inputs(result,case['prompt_tokens']);B.timing(result,len(tokens))
  expected_request=[0,512,1,0,len(case['prompt_tokens']),0,2,*case['prompt_tokens'],248044,248046];need(list(map(int,row['native_request'].split()))==expected_request,'actual serialized RPC')
  truth=comparison(tokens,case);need(row['reference_comparison']==truth,'independent mismatch truth')
  first=truth['first_difference'];localization=None
  if first is not None:
   # A length-only difference has no two emitted candidates; still retain its common prefix.
   prefix=case['prompt_tokens']+tokens[:first]
   localization=dict(first_difference_zero_based=first,shared_input_tokens=prefix,shared_input_length=len(prefix),next_input_position_zero_based=len(prefix)-1,native_token=tokens[first] if first<len(tokens) else None,reference_token=case['tokens'][first] if first<len(case['tokens']) else None,one_next_token_replay_required=True,saved_final_logits_are_first_divergence=False)
   answer=read(Path(case['response_path']));need(ARTIFACTS[case['response_path']]['sha256']==case['response_sha256'] and answer['status']==200 and answer['response']['tokens']==case['tokens'],'qualified raw CPU probability response')
   localization['reference_probability']=reference_at_difference(answer['response'],tokens,first)
  rows.append(dict(index=i,id=case['id'],tokens=tokens,reference_tokens=case['tokens'],equal=truth['equal'],first_difference=first,native_stop_type=truth['native_stop_type'],reference_stop_type=case['stop_type'],localization=localization))
  for rank in (0,1):
   reset=read(E/f'prompt-{i:02d}-none/rank{rank}/reset.json');need(reset['passed'] and reset['allocation_ids_preserved'],'acknowledged fresh RESET')
 ownership=read(E/'ownership.json');owners=[];rank_errors=[]
 for rank in (0,1):
  r=read(E/f'rank{rank}/receipt.json');need(r['rank']==rank and r['device_executed'] and len(r['teardown'])==1,'rank owner receipt');owners.append(r['teardown'][0]);rank_errors.append(r['error'])
  launch=read(C/f'ranks/rank{rank}-launch.json');need(launch['argv'].count('--recurrent-f32')==1 and launch['argv'][launch['argv'].index('--max-new')+1]=='128','actual startup precision/bound')
 incident=read(E/'f32-longer-incident.json') if (E/'f32-longer-incident.json').exists() else None
 flags=passive(ad['before'],term['after'],term);label,isolated=classify(term,ownership,owners,flags,rows,incident,rank_errors)
 if label=='numerical_mismatch_safely_closed':
  need(incident['capture_budget']['stage']==len(rows) and incident['capture_budget']['acknowledged']==[f'reset_{i:02d}' for i in range(len(rows))],'failed request not falsely DUMP-credited')
  need(not any((E/f'prompt-{i:02d}-none').exists() for i in range(len(rows),3)),'no later request started')
 for p,x in ARTIFACTS.items():need(stamp(os.stat(p,follow_symlinks=False))==x['identity'],'metadata changed after audit')
 return dict(schema='gsq.recurrent-f32.longer.closed-metadata.v1',evidence_review_passed=True,run_qualification_passed=False,classification=label,numerical_failure_isolated_from_runtime_failure=label=='numerical_mismatch_safely_closed',closed_safety_checks_passed=isolated,original_terminal_passed=term['passed'],plan_sha256=PLAN_SHA,native_binary_sha256=BINARY,reference_review_sha256=REFERENCE_SHA,rows=rows,passive_checks=flags,owners=owners,rank_errors=rank_errors,ownership=ownership,incident=incident,artifacts=ARTIFACTS,metadata_bytes_read=TOTAL,bundle_payload_bytes_read=0,full_state_qualification=False,quality_qualified=False,limitations=['This verifies retained request trajectories and closed-owner metadata only; no state.bundle payload was read.','Mismatch request has no guaranteed final target dump; previous matched captures remain preserved but unverified here.','First divergent prediction has a shared prefix; later free-running logits do not. A new one-next-token replay needs separate root admission.'])
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--run',action='store_true');a=p.parse_args();need(a.run,'root closed metadata invocation only');out=P/'evidence/closed-metadata-review.json'
 with out.open('x') as f:
  try:r=run()
  except BaseException as e:r={'evidence_review_passed':False,'error':repr(e),'artifacts':ARTIFACTS};json.dump(r,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno());raise
  r['auditor_sha256']=sha(__file__);json.dump(r,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
 print(json.dumps({'evidence_review_passed':True,'classification':r['classification'],'review_sha256':sha(out)}))
