"""Corrected F32 target32/MTP32 same-owner proof; no historical state oracle."""
import hashlib,importlib.util,json,shutil
from pathlib import Path
P=Path(__file__).resolve().parent;CAND=P.parent;L=CAND.parent;R=L.parents[2]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def require(v,m):
 if not v:raise ValueError(m)
def load(p,n):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
for f,h in json.loads((P/'parent-pins.json').read_text()).items():require(sha(f)==h,'frozen parent '+f)
Q=load(L/'state-bundle/qualification.py','f32_bundle_helpers')
A=load(P/'generated/adapter.py','f32_rank_adapter');Q.A=A
BUDGET=load(P/'budget.py','f32_capture_budget')
REFERENCE=L/'reference-cpu/runtime-b/evidence/closed-readback-review.json'
RAW=3*(310364224+9699332)
def authority():
 a=json.loads((P/'authority.json').read_text());require(a['native_build_sha256'] and a['host_lifecycle_review_sha256'],'F32 native/Host lifecycle authority pending')
 n=CAND/'evidence/native-build.json';require(sha(n)==a['native_build_sha256'],'native build authority');b=json.loads(n.read_text());require(b['passed'] and b['objects_rebuilt']==21 and b['objects_reused']==19,'new full closure')
 h=Path(a['host_lifecycle_review_path']);require(sha(h)==a['host_lifecycle_review_sha256'] and json.loads(h.read_text())['passed'],'actual Host lifecycle review')
 review=P/'evidence/independent-review.json';d=json.loads(review.read_text());require(d['passed'],'independent operating review')
 for f,s in d['source_sha256'].items():require(sha(Path(f) if Path(f).is_absolute() else R/f)==s,'operating reviewed source drift')
 return n,h,review

def build_plan(output,evidence_output):
 n,h,review=authority();ref=json.loads(REFERENCE.read_text());require(ref['evidence_review_passed'] and ref['prompt_tokens']==87 and len(ref['output_tokens'])==32,'bounded CPU reference readback')
 prompt=Q.manifest();base=A.build_plan(output,mini=False,max_new=32,seconds=1800,evidence_output=evidence_output)
 require(base['request_cap']==2 and base['storage']['raw_state_bytes']==RAW,'new capture forecast')
 files=[Path(__file__),P/'once.py',P/'budget.py',P/'generated/adapter.py',P/'candidate-ledger.json',P/'authority.json',P/'parent-pins.json',P/'source-preparation.json',REFERENCE,n,h,review]
 return dict(schema='gsq.recurrent-f32.two-arm.v1',adapter=base,prompt_id=prompt['prompt_id'],prompt_tokens=prompt['tokens'],max_new=32,modes=['none','mtp'],requests=2,retained_state_dumps=3,reference_tokens=ref['output_tokens'],source_sha256={str(f):sha(f) for f in files},scope='New F32 target/MTP equality and bounded independent reference token comparison; no speed or general-quality claim',historical_bf16_state_oracle=False)
def validate_plan(p):
 require(p==build_plan(p['adapter']['output'],p['adapter']['evidence_output']),'plan/source binding');A.validate_plan(p['adapter'])
def storage_guard(plan,budget=None):
 budget=budget or BUDGET.Budget();a=plan['adapter'];c=Path(a['output']);e=Path(a['evidence_output']);c=c if c.exists() else c.parent;e=e if e.exists() else e.parent
 require(c.stat().st_dev!=e.stat().st_dev,'separate evidence filesystem');require(a['storage']['raw_state_bytes']==RAW,'new F32 payload total')
 return BUDGET.check_free(shutil.disk_usage(c).free,shutil.disk_usage(e).free,budget)
def run_attached(t,plan):
 rows=[];seals=[];budget=BUDGET.Budget();t.capture_budget=budget
 for mode in ('none','mtp'):
  t.check_alive();storage_guard(plan,budget);dest=t.out/('prompt-00-'+mode);A.reset(t,dest)
  budget.advance('initial_reset' if mode=='none' else 'second_reset');storage_guard(plan,budget)
  if rows:require(Q.closed_map(t.out/rows[-1]['name'])==rows[-1]['state_sha256'] and Q.snapshots(t.out/rows[-1]['name'])==seals[-1],'RESET changed closed first capture')
  result=A.BASE.NativeController(t,A.BASE.Draft(mode),True,False).run(plan['prompt_tokens'],32,(248044,248046));result.update(decode_tok_s=None,evidence_label='F32 correctness only')
  row=dict(name='prompt-00-'+mode,mode=mode,prompt_tokens=plan['prompt_tokens'],requested_max_new=32,result=result,state_sha256=A.state_hashes(t))
  budget.advance('target_dump' if mode=='none' else 'mtp_dump');storage_guard(plan,budget);A.save(dest/'request-result.json',row)
  if rows:require(result['tokens']==rows[0]['result']['tokens'] and row['state_sha256']==rows[0]['state_sha256'],'corrected target/MTP tokens and full state differ')
  tokens=result['tokens'];ref=plan['reference_tokens'];first=next((i for i,(x,y) in enumerate(zip(tokens,ref)) if x!=y),None)
  if first is None and len(tokens)!=len(ref):first=min(len(tokens),len(ref))
  row['reference_comparison']=dict(equal=tokens==ref,first_difference=first,reference_tokens=ref,scope='Independent reference comparison is diagnostic, not an old-state oracle or an automatic quality waiver')
  rows.append(row);seals.append(Q.snapshots(dest))
 require(A.state_hashes(t)==rows[-1]['state_sha256'] and Q.snapshots(t.out/rows[-1]['name'])==seals[-1],'final explicit DUMP repeat changed')
 return dict(passed=True,requests=2,rows=rows,capture_snapshots=seals,rank_pids=[p.pid for p in t.children],corrected_target_mtp_exact=True,reference_equal=rows[0]['reference_comparison']['equal'],capture_budget=budget.report(),no_speed_claim=True)
def qualification(plan,*,admit,check,launch_hook):
 validate_plan(plan);storage_guard(plan);admit(plan);t=A.Transport.__new__(A.Transport)
 try:
  t.__init__(plan['adapter'],admit=lambda p:require(p==plan['adapter'],'adapter binding'),check=check,launch_hook=launch_hook)
  result=run_attached(t,plan);t.close(True);t.capture_budget.advance('finish');storage_guard(plan,t.capture_budget)
  for row,sealed in zip(result['rows'],result['capture_snapshots']):require(Q.closed_map(t.out/row['name'])==row['state_sha256'] and Q.snapshots(t.out/row['name'])==sealed,'FINISH changed closed evidence')
  result['capture_budget']=t.capture_budget.report();result['normal_FINISH_and_closed_payload_verified']=True;path=t.out/'f32-correctness.json';A.save(path,result)
  return dict(passed=True,requests=2,rank_pids=result['rank_pids'],corrected_target_mtp_exact=True,reference_equal=result['reference_equal'],full_result_path=str(path),full_result_sha256=sha(path),scope=plan['scope'],no_speed_claim=True)
 except BaseException as error:
  secondary=A.cleanup_failure(t,error)
  if hasattr(t,'out') and t.out.exists():
   try:A.save(t.out/'f32-incident.json',dict(passed=False,error=repr(error),secondary=secondary,capture_budget=t.capture_budget.report() if hasattr(t,'capture_budget') else None))
   except BaseException:pass
  raise
