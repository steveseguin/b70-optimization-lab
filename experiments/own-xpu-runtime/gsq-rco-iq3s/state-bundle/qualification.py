"""Two original prompt00 arms; format correctness only, no CLI device entry."""
import hashlib,importlib.util,json,time
from pathlib import Path
P=Path(__file__).resolve().parent;L=P.parent;R=L.parents[2]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p,n):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def require(x,m):
 if not x:raise ValueError(m)
A=load(P/'generated/adapter.py','bundle_qualification_adapter')
C=load(L/'qkv-q6-p33/engine/operating/checks.py','bundle_baseline_authority')
B=load(L/'baseline/suite.py','bundle_original_manifest')
def manifest():
 m=B.manifest();p=m['prompts'][0];require(p['order']==['none','mtp'],'fixed original prompt00 order');return p
def review():
 path=P/'evidence/independent-review.json';r=json.loads(path.read_text());require(r['passed'] and r.get('source_sha256'),'independent source/build review')
 for f,h in r['source_sha256'].items():require(sha(Path(f) if Path(f).is_absolute() else R/f)==h,'review source drift')
 return path
def build_plan(output,evidence_output):
 p=manifest();C.baseline();review_path=review();base=A.build_plan(output,mini=False,max_new=128,seconds=1800,evidence_output=evidence_output)
 files=[P/'qualification.py',P/'once.py',P/'test_qualification.py',P/'reader.py',P/'generated/adapter.py',P/'preparation.json',P/'parent-pins.json',P/'evidence/cpu-proof.json',P/'evidence/fs-pilot.json',P/'evidence/native-build.json',review_path,L/'baseline/manifest.json',C.REVIEW,C.REFERENCE]
 return dict(schema='gsq.state-bundle.two-arm-plan.v1',adapter=base,prompt_id=p['prompt_id'],prompt_tokens=p['tokens'],max_new=128,modes=['none','mtp'],requests=2,retained_state_dumps=3,baseline_review_sha256=C.REVIEW_SHA,baseline_result_sha256=C.REFERENCE_SHA,source_sha256={str(f):sha(f) for f in files},scope='evidence-format qualification only; no timing or model-quality claim')
def validate_plan(plan):
 require(plan==build_plan(plan['adapter']['output'],plan['adapter']['evidence_output']),'plan/source binding');A.validate_plan(plan['adapter']);return manifest()
def storage_guard(plan):return A.storage_guard(plan['adapter'],started=Path(plan['adapter']['output']).exists())
def snapshots(destination):
 return {str(rank):{f.name:[f.stat().st_dev,f.stat().st_ino,f.stat().st_size,f.stat().st_mtime_ns,f.stat().st_ctime_ns] for f in (destination/f'rank{rank}/state-2147483647').iterdir()} for rank in (0,1)}
def closed_map(destination):return {str(rank):A.BUNDLE.read_state(destination/f'rank{rank}/state-2147483647') for rank in (0,1)}
def run_attached(t,plan):
 refs=C.baseline();rows=[];paths=[];sealed=[]
 for mode in ('none','mtp'):
  t.check_alive();storage_guard(plan);destination=t.out/f'prompt-00-{mode}';A.reset(t,destination)
  if rows:require(closed_map(paths[-1])==rows[-1]['state_sha256'] and snapshots(paths[-1])==sealed[-1],'closed RESET capture changed')
  result=A.BASE.NativeController(t,A.BASE.Draft(mode),True,False).run(plan['prompt_tokens'],128,(248044,248046));result.update(evidence_label='state-bundle format qualification only',decode_tok_s=None)
  row=dict(name='prompt-00-'+mode,mode=mode,prompt_tokens=plan['prompt_tokens'],requested_max_new=128,result=result,state_sha256=A.state_hashes(t))
  A.save(destination/'request-result.json',row);ref=refs[row['name']]
  require(row['prompt_tokens']==ref['prompt_tokens'] and row['result']['tokens']==ref['result']['tokens'] and row['state_sha256']==ref['state_sha256'],'exact original baseline arm')
  rows.append(row);paths.append(destination);sealed.append(snapshots(destination))
 require(A.state_hashes(t)==rows[-1]['state_sha256'] and snapshots(paths[-1])==sealed[-1],'explicit final DUMP repeat changed')
 return dict(passed=True,requests=2,rows=rows,capture_snapshots=sealed,rank_pids=[p.pid for p in t.children],first_arm_RESET_redump_verified=True,last_arm_explicit_DUMP_repeat_verified=True,no_speed_claim=True)
def qualification(plan,*,admit,check,launch_hook):
 validate_plan(plan);storage_guard(plan);admit(plan);t=A.Transport.__new__(A.Transport)
 try:
  t.__init__(plan['adapter'],admit=lambda p:require(p==plan['adapter'],'adapter binding'),check=check,launch_hook=launch_hook)
  result=run_attached(t,plan);t.close(True)
  for row,before in zip(result['rows'],result['capture_snapshots']):
   dest=t.out/row['name'];require(closed_map(dest)==row['state_sha256'] and snapshots(dest)==before,'closed owner evidence changed')
  result['normal_FINISH_and_closed_payload_verified']=True;path=t.out/'bundle-qualification.json';A.save(path,result)
  return dict(passed=True,requests=2,rank_pids=result['rank_pids'],all_baseline_exact=True,closed_bundle_verified=True,full_result_path=str(path),full_result_sha256=sha(path),scope=plan['scope'],no_speed_claim=True)
 except BaseException as error:
  secondary=A.cleanup_failure(t,error)
  if hasattr(t,'out') and t.out.exists():
   try:A.save(t.out/'bundle-incident.json',dict(passed=False,error=repr(error),secondary=secondary))
   except BaseException:pass
  raise
