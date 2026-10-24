"""Current qualified binary, fixed target-only class diagnostic; no device CLI."""
import hashlib,importlib.util,json,math
from pathlib import Path
P=Path(__file__).resolve().parent;L=P.parents[1];R=L.parents[2]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def require(x,m):
 if not x:raise ValueError(m)
def load(p,n):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
PARENT=L/'state-bundle/qualification.py'
PARENT_SHA='98e55149be798ce8294c3774dec531f96870ecac14ce34f9f454c3c14f1bd184'
require(sha(PARENT)==PARENT_SHA,'bundle qualification source drift')
Q=load(PARENT,'current_class_bundle_qualification');A=Q.A;C=Q.C;B=Q.B
ACTUAL=L/'state-bundle/evidence/device-a/review.json'
ACTUAL_SHA='1c41b70d7b13f149ad8642b5de055937be3301488228e47120fd8bab6e21b82e'
BINARY_SHA='5a8c9d3b58606022e21e2f0347360e4dd9cfdf6a869c8daac145e928fe4d4306'
TOKEN_COMMAND=A.command;TOKEN_PLAN=A.build_plan
RAW_BYTES=694327500;METADATA_BYTES=128*1024**2

def command(plan,rank,channel,stop_fd):
 argv=TOKEN_COMMAND(plan,rank,channel,stop_fd)
 require(argv.count('--timing')==1,'single timing argument');i=argv.index('--timing')+1
 require(argv[i]=='token','original token mode');argv[i]='class';return argv
A.command=command

def adapter_plan(*args,**kwargs):
 plan=TOKEN_PLAN(*args,**kwargs)
 require(plan['binary_sha256']==BINARY_SHA,'qualified current binary required')
 require(plan['storage']['raw_state_bytes']==RAW_BYTES,'three capture forecast')
 plan['storage'].update(evidence_forecast_bytes=RAW_BYTES+METADATA_BYTES,metadata_forecast_bytes=METADATA_BYTES)
 plan['source_sha256'].update({str(f):sha(f) for f in (Path(__file__),PARENT,ACTUAL)})
 return plan
A.build_plan=adapter_plan

def actual_review():
 require(sha(ACTUAL)==ACTUAL_SHA,'qualified bundle actual review drift');r=json.loads(ACTUAL.read_text())
 require(r['passed'] is True and r['native_binary_sha256']==BINARY_SHA and r['explicit_repeat_and_closed_stamp_verified'] and r['completed_arm_state_json_bytes_exact'],'actual bundle qualification required')
 return ACTUAL

def build_plan(output,evidence_output):
 p=Q.manifest();C.baseline();prior=Q.review();actual_review();base=A.build_plan(output,mini=False,max_new=128,seconds=1800,evidence_output=evidence_output)
 files=[Path(__file__),P/'once.py',P/'test_profile.py',P/'README.md',PARENT,prior,ACTUAL,L/'state-bundle/generated/adapter.py',L/'state-bundle/reader.py',L/'state-bundle/evidence/native-build.json',L/'baseline/manifest.json',C.REVIEW,C.REFERENCE]
 return dict(schema='gsq.current-combined.class-plan.v1',adapter=base,prompt_id=p['prompt_id'],prompt_tokens=p['tokens'],warmup=B.manifest()['warmup'][0],max_new=128,requests=2,measured_requests=1,retained_state_dumps=3,baseline_review_sha256=C.REVIEW_SHA,baseline_result_sha256=C.REFERENCE_SHA,bundle_actual_review_sha256=ACTUAL_SHA,source_sha256={str(f):sha(f) for f in files},timing='class',only_native_argv_delta='--timing token -> class',rank1_queue_profiling_property_changed=True,scope='current combined binary whole-request class diagnostic including prefill; no speed or per-format attribution claim',no_speed_claim=True)
def validate_plan(plan):
 require(plan==build_plan(plan['adapter']['output'],plan['adapter']['evidence_output']),'plan/source binding');A.validate_plan(plan['adapter'])
def storage_guard(plan):return A.storage_guard(plan['adapter'],started=Path(plan['adapter']['output']).exists())
def classes(path):
 require(path.is_file() and not path.is_symlink() and path.stat().st_size<=2*1024**2,'bounded class report');r=json.loads(path.read_text())
 require(r['profiling'] is True and r['classes'] and any(x['device_ms']>0 and x['launches']>0 for x in r['classes']),'actual profiled classes')
 for x in r['classes']:require(math.isfinite(x['device_ms']) and x['device_ms']>=0 and type(x['launches'])is int and x['launches']>=0 and type(x['groups'])is int and x['groups']>=0,'valid class counters')
 return dict(path=str(path),sha256=sha(path),report=r)
def run_attached(t,plan):
 ref=C.baseline()['prompt-00-none'];rows=[];seals=[]
 for name,prompt,cap,eos in [('warmup-none',plan['warmup']['tokens'],8,()),('prompt-00-none',plan['prompt_tokens'],128,(248044,248046))]:
  t.check_alive();storage_guard(plan);dest=t.out/name;A.reset(t,dest)
  if rows:require(Q.closed_map(t.out/rows[-1]['name'])==rows[-1]['state_sha256'] and Q.snapshots(t.out/rows[-1]['name'])==seals[-1],'warmup RESET redump changed')
  result=A.BASE.NativeController(t,A.BASE.Draft('none'),True,False).run(prompt,cap,eos);result.update(decode_tok_s=None,evidence_label='class diagnostic only; no speed claim')
  row=dict(name=name,mode='none',excluded=name=='warmup-none',prompt_tokens=prompt,requested_max_new=cap,result=result,state_sha256=A.state_hashes(t))
  A.save(dest/'request-result.json',row)
  if row['excluded']:require(len(result['tokens'])==8,'complete excluded warmup')
  else:require(prompt==ref['prompt_tokens'] and result['tokens']==ref['result']['tokens'] and row['state_sha256']==ref['state_sha256'],'exact original baseline arm')
  rows.append(row);seals.append(Q.snapshots(dest))
 require(A.state_hashes(t)==rows[-1]['state_sha256'] and Q.snapshots(t.out/rows[-1]['name'])==seals[-1],'explicit final DUMP repeat changed')
 return dict(passed=True,requests=2,measured_requests=1,rows=rows,capture_snapshots=seals,rank_pids=[p.pid for p in t.children],warmup_RESET_redump_verified=True,last_arm_explicit_DUMP_repeat_verified=True,exact_baseline_tokens=True,exact_baseline_target_state=True,no_speed_claim=True)
def qualification(plan,*,admit,check,launch_hook):
 validate_plan(plan);storage_guard(plan);admit(plan);t=A.Transport.__new__(A.Transport)
 try:
  t.__init__(plan['adapter'],admit=lambda p:require(p==plan['adapter'],'adapter binding'),check=check,launch_hook=launch_hook)
  result=run_attached(t,plan);t.close(True)
  for row,before in zip(result['rows'],result['capture_snapshots']):
   dest=t.out/row['name'];require(Q.closed_map(dest)==row['state_sha256'] and Q.snapshots(dest)==before,'closed owner evidence changed')
  result['classes']={str(r):classes(t.out/f'prompt-00-none/rank{r}/class-times.json') for r in (0,1)}
  result['normal_FINISH_and_closed_payload_verified']=True;path=t.out/'profile-result.json';A.save(path,result)
  return dict(passed=True,requests=2,measured_requests=1,rank_pids=result['rank_pids'],exact_baseline_tokens=True,exact_baseline_target_state=True,closed_bundle_verified=True,full_result_path=str(path),full_result_sha256=sha(path),scope=plan['scope'],no_speed_claim=True)
 except BaseException as error:
  secondary=A.cleanup_failure(t,error)
  if hasattr(t,'out') and t.out.exists():
   try:A.save(t.out/'profile-incident.json',dict(passed=False,error=repr(error),secondary=secondary))
   except BaseException:pass
  raise
