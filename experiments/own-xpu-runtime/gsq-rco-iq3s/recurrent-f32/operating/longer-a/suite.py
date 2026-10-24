"""Three corrected target512 requests against independent fixed CPU references."""
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
RAW=4*(BUDGET.T+BUDGET.D);EOS=(248044,248046)
def authority():
 a=json.loads((P/'authority.json').read_text());require(a['reference_review_sha256'] is not None,'actual CPU3 closed authority pending')
 f=Path(a['reference_review_path']);require(sha(f)==a['reference_review_sha256'],'CPU3 review bytes');ref=json.loads(f.read_text())
 require(ref['evidence_review_passed'] and ref['plan_sha256']==a['reference_plan_sha256'] and ref['owner_exited'] and ref['returncode']==0,'CPU3 clean closed reference')
 fixed=json.loads((L/'reference-cpu/runtime-longer-a/requests.json').read_text())['cases'];require(len(ref['cases'])==3,'exact three references')
 for i,(c,x) in enumerate(zip(ref['cases'],fixed)):
  require(c['index']==i and c['id']==x['id'] and c['prompt_tokens']==x['request']['prompt'] and 0<len(c['tokens'])<=512 and c['stop_type'] in ('eos','limit'),'fixed reference case')
  require(sha(c['response_path'])==c['response_sha256'],'raw CPU response binding')
  require((c['stop_type']=='eos')==(c['tokens'][-1] in EOS) and (c['stop_type']!='limit' or len(c['tokens'])==512),'CPU natural EOS/cap identity')
 old=Path(a['corrected32_review_path']);require(sha(old)==a['corrected32_review_sha256'],'corrected32 authority');o=json.loads(old.read_text());require(o['passed'] and o['corrected_target_mtp_exact'] and o['physical_drain'],'corrected actual baseline')
 rp=P/'evidence/independent-review.json';review=json.loads(rp.read_text());require(review['passed'],'independent source review')
 for f,h in review['source_sha256'].items():require(sha(Path(f) if Path(f).is_absolute() else R/f)==h,'reviewed source drift')
 return ref,fixed,rp

def build_plan(output,evidence_output):
 ref,fixed,review=authority();a=A.build_plan(output,mini=False,max_new=128,seconds=3600,evidence_output=evidence_output)
 require(a['request_cap']==3 and a['max_new']==128 and a['storage']['raw_state_bytes']==RAW,'bootstrap/capture forecast')
 files=[Path(__file__),P/'once.py',P/'budget.py',P/'generated/adapter.py',P/'authority.json',P/'parent-pins.json',P/'source-preparation.json',review,L/'reference-cpu/runtime-longer-a/requests.json',Path(json.loads((P/'authority.json').read_text())['reference_review_path'])]
 return dict(schema='gsq.recurrent-f32.longer-three-target.v1',adapter=a,requests=3,cases=ref['cases'],max_new=512,startup_max_new=128,modes=['none']*3,retained_state_dumps=4,initial_extra_metadata_bytes=BUDGET.INITIAL_EXTRA,initial_root_free_required_bytes=BUDGET.ROOT_FLOOR+2*BUDGET.ROOT_CACHE,initial_external_required_bytes=RAW+BUDGET.META+BUDGET.EXTERNAL_FLOOR+BUDGET.INITIAL_EXTRA,source_sha256={str(f):sha(f) for f in files},scope='Three fixed corrected target/CPU token comparisons; no MTP512, speed or broad quality claim',historical_bf16_state_oracle=False)
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
  result=A.BASE.NativeController(t,A.BASE.Draft('none'),True,False).run(case['prompt_tokens'],512,EOS);result.update(decode_tok_s=None,evidence_label='Corrected target512 independent token comparison only')
  require(0<len(result['tokens'])<=512 and all(result['stats'][k]==0 for k in ('guesses','hits','misses')),'target-only output bounds/stats')
  request_text=(t.shared_path.parent/'native-request.txt').read_text();expected=[0,512,1,0,len(case['prompt_tokens']),0,len(EOS),*case['prompt_tokens'],*EOS]
  require(list(map(int,request_text.split()))==expected,'actual native RPC512 identity')
  row=dict(name=dest.name,prompt_id=case['id'],mode='none',prompt_tokens=case['prompt_tokens'],requested_max_new=512,result=result,reference_comparison=comparison(result['tokens'],case),native_request=request_text)
  A.save(dest/'request-result.json',row);rows.append(row)
  require(row['reference_comparison']['equal'],'corrected target differs from independent CPU reference; stop remaining requests')
 A.state_hashes(t);budget.advance('last_dump');storage_guard(plan,budget);capture(t,rows[-1])
 require(A.state_hashes(t)==rows[-1]['state_sha256'] and Q.snapshots(t.out/rows[-1]['name'])==rows[-1]['capture_snapshot'],'last explicit DUMP repeat changed')
 return dict(passed=True,requests=3,rows=rows,rank_pids=[p.pid for p in t.children],all3_reference_exact=True,capture_budget=budget.report(),no_speed_claim=True,mtp512_qualified=False)
def qualification(plan,*,admit,check,launch_hook):
 validate_plan(plan);storage_guard(plan,initial=True);admit(plan);t=A.Transport.__new__(A.Transport)
 try:
  # Recheck the initial-only margins immediately before owner construction.
  storage_guard(plan,initial=True)
  t.__init__(plan['adapter'],admit=lambda p:require(p==plan['adapter'],'adapter identity'),check=check,launch_hook=launch_hook)
  result=run_attached(t,plan);t.close(True);t.capture_budget.advance('finish');storage_guard(plan,t.capture_budget)
  for row in result['rows']:require(Q.closed_map(t.out/row['name'])==row['state_sha256'] and Q.snapshots(t.out/row['name'])==row['capture_snapshot'],'post-FINISH capture changed')
  result['capture_budget']=t.capture_budget.report();result['normal_FINISH_and_closed_payload_verified']=True;f=t.out/'f32-longer-correctness.json';A.save(f,result)
  return dict(passed=True,requests=3,rank_pids=result['rank_pids'],all3_reference_exact=True,full_result_path=str(f),full_result_sha256=sha(f),scope=plan['scope'],no_speed_claim=True)
 except BaseException as error:
  secondary=A.cleanup_failure(t,error)
  if hasattr(t,'out') and t.out.exists():
   try:A.save(t.out/'f32-longer-incident.json',dict(passed=False,error=repr(error),secondary=secondary,capture_budget=t.capture_budget.report() if hasattr(t,'capture_budget') else None))
   except BaseException:pass
  raise
