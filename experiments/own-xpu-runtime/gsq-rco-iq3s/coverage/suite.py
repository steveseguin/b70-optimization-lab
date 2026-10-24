#!/usr/bin/env python3
"""Six fixed broader requests on the qualified binary. Plan-only direct CLI."""
from pathlib import Path
import hashlib,importlib.util,json,shutil,time
P=Path(__file__).resolve().parent;L=P.parent;R=L.parents[2]
def require(v,msg):
 if not v:raise ValueError(msg)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p,name):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
for f,h in json.loads((P/'parent-pins.json').read_text()).items():require(sha(f)==h,'frozen helper changed')
A=load(P/'generated/adapter.py','coverage_private_adapter')
H=load(L/'expert-iq3xxs-block/engine/operating/generated/suite.py','coverage_metric_helpers')
C=H.C;B=load(L/'baseline/audit.py','coverage_input_audit_helpers');T=load(P/'tokenizer.py','coverage_local_tokenizer')
CAP=6;STATE_BYTES=231442500;BINARY='97348925367e1ad67313cf9863d0c4cba47abea871c386972983965e036ea4b2'
REVIEW=L/'expert-iq3xxs-block/engine/operating/evidence/device-a/review.json';REVIEW_SHA='4e97f8a533de01c64d299582e8cdb884bb1979f7e2a405bd5794f36f4869294b'
MANIFEST=P/'manifest.json';MANIFEST_SHA='90f8bf9f86ba5b4c8e082393509db0fde4111411ef9062417054ee60fa22dcd5'
def manifest():
 require(sha(MANIFEST)==MANIFEST_SHA,'preregistered coverage manifest');m=json.loads(MANIFEST.read_text())
 require(m['requests']==6 and len(m['cases'])==3 and m['context']==4096 and m['binary_sha256']==BINARY,'fixed coverage')
 require([x['max_new'] for x in m['cases']]==[512,512,128] and [x['order'] for x in m['cases']]==[['none','mtp'],['mtp','none'],['none','mtp']],'fixed caps/order')
 for f,h in m['source_sha256'].items():require(sha(f)==h,'prompt/tokenizer source')
 for f,h in m['prompt_sha256'].items():require(sha(P/'prompts'/f)==h,'fixed prompt text')
 for x in m['cases']:require(len(x['tokens'])==x['input_tokens'] and x['input_tokens']+x['max_new']<=4096,'context capacity')
 return m

def prefix_reference():
 require(sha(C.REVIEW)==C.REVIEW_SHA,'baseline review');r=json.loads(C.REVIEW.read_text());require(r['passed'] and r['all12_exact'],'baseline complete')
 require(sha(C.REFERENCE)==r['full_result_sha256'],'original baseline result');full=json.loads(C.REFERENCE.read_text())
 pair=full['prompts'][0];require(pair['prompt_id']=='incident-retrospective' and pair['exact_tokens'],'prefix case')
 ids=pair['arms'][0]['result']['tokens'];require(len(ids)==128 and ids[-1] not in (248044,248046),'existing128 nonEOS prefix')
 return ids

def prerequisites():
 require(sha(REVIEW)==REVIEW_SHA,'qualified current binary review');r=json.loads(REVIEW.read_text())
 require(r['passed'] and r['all12_exact'] and r['physical_drain'] and r['native_binary_sha256']==BINARY,'actual current binary qualification')
 prep=json.loads((P/'preparation.json').read_text());require(sha(P/'prepare.py')==prep['recipe_sha256'] and sha(P/'adapter.patch')==prep['patch_sha256'],'private adapter recipe')
 for f,h in {**prep['source_sha256'],**prep['generated_sha256']}.items():require(sha(f)==h,'private transport source')
 review=json.loads((P/'evidence/independent-review.json').read_text());require(review['passed'] and review['source_sha256'],'independent coverage review')
 for f,h in review['source_sha256'].items():require(sha(R/f)==h,'coverage review source')
 prefix_reference()
 return r

def build_plan(output,evidence):
 m=manifest();prerequisites();a=A.build_plan(output,mini=False,max_new=512,seconds=7200,evidence_output=evidence)
 require(a['binary_sha256']==BINARY and a['request_cap']==6 and a['storage']['raw_state_bytes']==7*STATE_BYTES,'qualified binary and6/7 budget')
 files=[Path(__file__),P/'manifest.json',P/'tokenizer.py',P/'prepare_prompts.py',P/'prepare.py',P/'preparation.json',P/'parent-pins.json',P/'adapter.patch',P/'generated/adapter.py',P/'README.md',P/'test_coverage.py',P/'evidence/independent-review.json',REVIEW,C.REVIEW,C.REFERENCE]
 return dict(schema='gsq.coverage.plan.v1',adapter=a,requests=6,pairs=3,captures=7,cases=m['cases'],manifest_sha256=sha(MANIFEST),prefix_reference_sha256=sha(C.REFERENCE),source_sha256={str(f):sha(f) for f in files},lifetime_seconds=7200,storage=dict(per_capture_bytes=STATE_BYTES,captures=7,raw_bytes=7*STATE_BYTES,evidence_forecast_bytes=7*STATE_BYTES+128*1024**2,root_cache_forecast_bytes=128*1024**2,root_floor_bytes=27000000000,external_floor_bytes=2*1024**3,hard_bound=False),no_speed_claim=True,order_balance=m['order_balance'],no_independent_new_output_oracle=True)
def validate_plan(plan):
 require(plan==build_plan(plan['adapter']['output'],plan['adapter']['evidence_output']),'coverage plan/source changed');A.validate_plan(plan['adapter']);return manifest()
def storage_guard(plan,completed=0,started=False):
 require(type(completed)is int and 0<=completed<=6,'request count')
 c=Path(plan['adapter']['output']);e=Path(plan['adapter']['evidence_output']);c=c if started else c.parent;e=e if started else e.parent
 require(c.stat().st_dev!=e.stat().st_dev,'external state filesystem')
 require(shutil.disk_usage(c).free>=27000000000+128*1024**2,'root cache floor')
 require(shutil.disk_usage(e).free>=2*1024**3+(7-completed)*STATE_BYTES+128*1024**2,'remaining evidence forecast')
def quality(case,text,tokens):
 # Literal full decoded bytes are retained separately. Only terminal EOS is
 # removed from the parser view; no answer repairs, substring extraction or retry.
 visible=text
 if tokens and tokens[-1] in (248044,248046):
  suffix=T.decode([tokens[-1]])
  if visible.endswith(suffix):visible=visible[:-len(suffix)]
 rubric=case['rubric']
 if rubric['kind']!='exact_json_facts':return dict(automated_passed=None,manual_review_required=True,rubric=rubric,word_count=len(visible.split()),scope='Complete output needs human readback; word count is not quality proof')
 try:
  def unique(pairs):
   d={}
   for k,v in pairs:require(k not in d,'duplicate JSON key');d[k]=v
   return d
  obj=json.loads(visible,object_pairs_hook=unique)
  passed=type(obj)is dict and obj==rubric['expected'] and type(obj.get('sensor_count'))is int
  return dict(automated_passed=passed,parsed=obj,expected=rubric['expected'],manual_review_required=True)
 except (ValueError,TypeError) as error:return dict(automated_passed=False,error=str(error),expected=rubric['expected'],manual_review_required=True)
def run_attached(t,plan,m=None):
 m=m or manifest();require(not getattr(t,'coverage_started',False),'one coverage suite');t.coverage_started=True
 prefix=prefix_reference();pairs=[];stamps={};count=0;start=time.monotonic()
 for case in m['cases']:
  arms=[]
  for mode in case['order']:
   require(count<6 and time.monotonic()-start<plan['lifetime_seconds'],'count/lifetime');require(sha(MANIFEST)==plan['manifest_sha256'],'manifest changed')
   t.check_alive();storage_guard(plan,count,True);name=case['id']+'-'+mode;dest=t.out/name
   A.reset(t,dest);C.verify_capture_stamps(t.out,stamps);count+=1
   result=A.BASE.NativeController(t,A.BASE.Draft(mode),True,False).run(case['tokens'],case['max_new'],(248044,248046))
   metric=H.metric(result,case['max_new']);metric['scope']='Coverage request without excluded warmups; raw N-1 decode intervals and prompt time, no aggregate speed claim';consumed=B.confirmed_inputs(result,case['tokens'])
   if mode=='mtp':B.guess_outcomes(result,case['tokens'],case['max_new'])
   else:require(all(result['stats'][k]==0 for k in ('guesses','hits','misses')),'target stats')
   state=A.state_hashes(t);stamps[name]=C.capture_stamp(dest)
   row=dict(request=count,name=name,case=case['id'],mode=mode,prompt_tokens=case['tokens'],requested_max_new=case['max_new'],result=result,metric=metric,state_sha256=state,consumed_positions=consumed,context_capacity=4096)
   A.save(dest/'request-result.json',row)
   if case['prefix_oracle_tokens']:require(len(result['tokens'])>=128 and result['tokens'][:128]==prefix,'original prompt00 first128 exact prefix')
   text=T.decode(result['tokens']);assessment=quality(case,text,result['tokens']);row.update(decoded_text=text,quality=assessment,prefix_baseline_exact=True if case['prefix_oracle_tokens'] else None)
   A.save(dest/'decoded-output.json',dict(tokens=result['tokens'],text=text,skip_special_tokens=False,tokenizer_sha256=T.TOKENIZER_SHA,quality=assessment))
   t.check_alive();arms.append(row)
  require(arms[0]['result']['tokens']==arms[1]['result']['tokens'],'target/MTP token mismatch')
  require(arms[0]['state_sha256']==arms[1]['state_sha256'],'target/MTP state mismatch')
  pair=dict(case=case['id'],order=case['order'],exact_tokens=True,exact_target_state=True,arms=arms);pairs.append(pair);A.save(t.out/(case['id']+'-pair.json'),pair)
 require(count==6,'all six requests');last=pairs[-1]['arms'][-1]
 require(A.state_hashes(t)==last['state_sha256'],'explicit final repeat changed');C.verify_capture_stamps(t.out,stamps)
 return dict(passed=True,requests=6,pairs=pairs,rank_pids=[p.pid for p in t.children],capture_stamps=stamps,explicit_final_DUMP=True,manifest_sha256=sha(MANIFEST),all_target_mtp_exact=True,quality_qualified=False,quality_scope='Preregistered facts plus full-output manual readback; no independent same-weight model oracle',order_balance=m['order_balance'],no_speed_claim=True,elapsed=time.monotonic()-start)
def qualification(plan,*,admit,check,launch_hook):
 m=validate_plan(plan);storage_guard(plan);admit(plan);t=A.Transport.__new__(A.Transport)
 try:
  t.__init__(plan['adapter'],admit=lambda p:A.require(p==plan['adapter'],'adapter binding'),check=check,launch_hook=launch_hook)
  result=run_attached(t,plan,m);t.close(True);C.verify_capture_stamps(t.out,result['capture_stamps']);result['closed_stamps_verified']=True
  f=t.out/'coverage-result.json';A.save(f,result)
  return dict(passed=True,requests=6,pairs=3,rank_pids=result['rank_pids'],full_result_path=str(f),full_result_sha256=sha(f),all_target_mtp_exact=True,quality_qualified=False,no_speed_claim=True)
 except BaseException as error:
  secondary=A.cleanup_failure(t,error)
  if hasattr(t,'out') and t.out.exists():
   try:A.save(t.out/'coverage-incident.json',dict(passed=False,error=repr(error),secondary=secondary))
   except BaseException:pass
  raise
