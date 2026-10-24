"""One existing-binary replay at the audited first divergent shared prefix."""
import hashlib,importlib.util,json,shutil
from pathlib import Path
P=Path(__file__).resolve().parent;BASE=P.parent;CAND=BASE.parent;L=CAND.parent;R=L.parents[2]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def require(v,m):
 if not v:raise ValueError(m)
def load(p,n):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
for f,h in json.loads((P/'parent-pins.json').read_text()).items():require(sha(f)==h,'frozen parent '+f)
Q=load(L/'state-bundle/qualification.py','longer_bundle_helpers')
A=load(P/'generated/adapter.py','longer_f32_adapter');Q.A=A
BUDGET=load(P/'budget.py','longer_capture_budget')
RAW=2*(BUDGET.T+BUDGET.D);EOS=(248044,248046)
def authority():
 a=json.loads((P/'authority.json').read_text());f=Path(a['failure_review_path']);require(sha(f)==a['failure_review_sha256'],'closed failure authority')
 failure=json.loads(f.read_text());require(failure['native_binary_sha256']=='5926a24746c62c6b0ecdc5c3e4895f310145e0f9d74a90a5d657035b9a8151f4','unchanged native binary authority');require(failure['evidence_review_passed'] and not failure['run_qualification_passed'] and failure['classification']=='numerical_mismatch_safely_closed' and failure['closed_safety_checks_passed'],'safe failed original remains unqualified')
 require(len(failure['rows'])==1 and failure['rows'][0]['first_difference']==a['index']==70,'fixed first divergence')
 loc=failure['rows'][0]['localization'];require(loc['native_token']==a['expected_native_token']==220 and loc['reference_token']==a['expected_reference_token']==264 and loc['shared_input_length']==157,'fixed diagnostic tokens/prefix')
 rp=Path(a['reference_review_path']);require(sha(rp)==a['reference_review_sha256']==failure['reference_review_sha256'],'closed CPU authority');ref=json.loads(rp.read_text());require(ref['evidence_review_passed'] and ref['owner_exited'] and ref['returncode']==0,'CPU closed')
 c=ref['cases'][0];prefix=c['prompt_tokens']+c['tokens'][:70];require(prefix==loc['shared_input_tokens'] and len(prefix)==157 and c['tokens'][70]==264,'exact shared prefix from independent reference')
 require(failure['rows'][0]['tokens'][:70]==c['tokens'][:70],'matched prior generated prefix')
 case=dict(index=0,id='prompt00-first-divergence70',prompt_tokens=prefix,tokens=[264],stop_type='limit',native_expected=[220],original_output_index=70,conditional_position=156)
 review=P/'evidence/independent-review.json';v=json.loads(review.read_text());require(v['passed'],'independent replay source review')
 for f,h in v['source_sha256'].items():require(sha(Path(f) if Path(f).is_absolute() else R/f)==h,'reviewed source drift')
 return [case],review

def build_plan(output,evidence_output):
 cases,review=authority();a=A.build_plan(output,mini=False,max_new=128,seconds=3600,evidence_output=evidence_output)
 require(a['binary_sha256']=='5926a24746c62c6b0ecdc5c3e4895f310145e0f9d74a90a5d657035b9a8151f4','same native replay binary');require(a['request_cap']==1 and a['max_new']==128 and a['storage']['raw_state_bytes']==RAW,'bootstrap/capture forecast')
 files=[Path(__file__),P/'once.py',P/'budget.py',P/'generated/adapter.py',P/'authority.json',P/'parent-pins.json',P/'source-preparation.json',review,L/'reference-cpu/runtime-longer-a/requests.json',Path(json.loads((P/'authority.json').read_text())['reference_review_path']),Path(json.loads((P/'authority.json').read_text())['failure_review_path'])]
 return dict(schema='gsq.recurrent-f32.first-divergence-replay.v1',adapter=a,requests=1,cases=cases,max_new=1,startup_max_new=128,modes=['none'],retained_state_dumps=2,initial_extra_metadata_bytes=BUDGET.INITIAL_EXTRA,initial_root_free_required_bytes=BUDGET.ROOT_FLOOR+2*BUDGET.ROOT_CACHE,initial_external_required_bytes=RAW+BUDGET.META+BUDGET.EXTERNAL_FLOOR+BUDGET.INITIAL_EXTRA,source_sha256={str(f):sha(f) for f in files},scope='Existing5926 shared-prefix reproduction of native220 versus CPU264; diagnostic only, no quality/speed claim',historical_bf16_state_oracle=False)
def validate_plan(p):
 require(p==build_plan(p['adapter']['output'],p['adapter']['evidence_output']),'plan/source binding');A.validate_plan(p['adapter'])
def storage_guard(plan,budget=None,initial=False):
 budget=budget or BUDGET.Budget();a=plan['adapter'];c=Path(a['output']);e=Path(a['evidence_output']);c=c if c.exists() else c.parent;e=e if e.exists() else e.parent
 require(c.stat().st_dev!=e.stat().st_dev and a['storage']['raw_state_bytes']==RAW,'separate evidence/F32 extent')
 return BUDGET.check_free(shutil.disk_usage(c).free,shutil.disk_usage(e).free,budget,initial)
def comparison(tokens,case):
 ref=case['tokens'];first=next((i for i,(x,y) in enumerate(zip(tokens,ref)) if x!=y),None)
 if first is None and len(tokens)!=len(ref):first=min(len(tokens),len(ref))
 stop='eos' if tokens and tokens[-1] in EOS else 'limit'
 return dict(equal=tokens==ref and stop==case['stop_type'],first_difference=first,native_stop_type=stop,reference_stop_type=case['stop_type'],reference_tokens=ref,scope='Full raw-ID trajectory equality; after first divergence later logits have different conditional prefixes')
def capture(t,row):
 d=t.out/row['name'];row['state_sha256']=Q.closed_map(d);row['capture_snapshot']=Q.snapshots(d)
def run_attached(t,plan):
 rows=[];budget=BUDGET.Budget();t.capture_budget=budget
 for i,case in enumerate(plan['cases']):
  t.check_alive();storage_guard(plan,budget);dest=t.out/f'prompt-{i:02d}-none';A.reset(t,dest)
  budget.advance(f'reset_{i:02d}');storage_guard(plan,budget)
  if rows:capture(t,rows[-1])
  result=A.BASE.NativeController(t,A.BASE.Draft('none'),True,False).run(case['prompt_tokens'],1,EOS);result.update(decode_tok_s=None,evidence_label='Same-prefix first-divergence replay only')
  require(len(result['tokens'])==1 and all(result['stats'][k]==0 for k in ('guesses','hits','misses')),'target-only output bounds/stats')
  request_text=(t.shared_path.parent/'native-request.txt').read_text();expected=[0,1,1,0,len(case['prompt_tokens']),0,len(EOS),*case['prompt_tokens'],*EOS]
  require(list(map(int,request_text.split()))==expected,'actual native RPC1 identity')
  row=dict(name=dest.name,prompt_id=case['id'],mode='none',prompt_tokens=case['prompt_tokens'],requested_max_new=1,result=result,native_reproduction=result['tokens']==case['native_expected'],reference_comparison=comparison(result['tokens'],case),native_request=request_text)
  A.save(dest/'request-result.json',row);rows.append(row)
  require(row['native_reproduction'],'replay does not reproduce audited native220 divergence; preserve failure, no logit attribution')
 A.state_hashes(t);budget.advance('last_dump');storage_guard(plan,budget);capture(t,rows[-1])
 require(A.state_hashes(t)==rows[-1]['state_sha256'] and Q.snapshots(t.out/rows[-1]['name'])==rows[-1]['capture_snapshot'],'last explicit DUMP repeat changed')
 return dict(passed=True,requests=1,rows=rows,rank_pids=[p.pid for p in t.children],native_divergence_reproduced=True,reference_equal=False,diagnostic_only=True,capture_budget=budget.report(),no_speed_claim=True,quality_qualified=False)
def qualification(plan,*,admit,check,launch_hook):
 validate_plan(plan);storage_guard(plan,initial=True);admit(plan);t=A.Transport.__new__(A.Transport)
 try:
  # Recheck the initial-only margins immediately before owner construction.
  storage_guard(plan,initial=True)
  t.__init__(plan['adapter'],admit=lambda p:require(p==plan['adapter'],'adapter identity'),check=check,launch_hook=launch_hook)
  result=run_attached(t,plan);t.close(True);t.capture_budget.advance('finish');storage_guard(plan,t.capture_budget)
  for row in result['rows']:require(Q.closed_map(t.out/row['name'])==row['state_sha256'] and Q.snapshots(t.out/row['name'])==row['capture_snapshot'],'post-FINISH capture changed')
  result['capture_budget']=t.capture_budget.report();result['normal_FINISH_and_closed_payload_verified']=True;f=t.out/'f32-prefix-replay.json';A.save(f,result)
  return dict(passed=True,requests=1,rank_pids=result['rank_pids'],native_divergence_reproduced=True,reference_equal=False,diagnostic_only=True,full_result_path=str(f),full_result_sha256=sha(f),scope=plan['scope'],no_speed_claim=True)
 except BaseException as error:
  secondary=A.cleanup_failure(t,error)
  if hasattr(t,'out') and t.out.exists():
   try:A.save(t.out/'f32-prefix-incident.json',dict(passed=False,error=repr(error),secondary=secondary,capture_budget=t.capture_budget.report() if hasattr(t,'capture_budget') else None))
   except BaseException:pass
  raise
