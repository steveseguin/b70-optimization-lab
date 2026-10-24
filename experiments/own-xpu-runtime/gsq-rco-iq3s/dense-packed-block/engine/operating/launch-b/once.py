#!/usr/bin/env python3
"""Additive acknowledged-capture accounting only; original26-suite sources frozen."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,shutil
P=Path(__file__).resolve().parent;BASE=P.parent
CONTROL=Path('/home/steve/own-xpu-runtime-results/gsq-dense-packed-block-engine-b.control')
EVIDENCE=Path('/mnt/usb-models/own-xpu-runtime-results/gsq-dense-packed-block-engine-b');UNIT='gsq-dense-packed-block-engine-b.service'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p,n):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
PINS=json.loads((P/'parent-pins.json').read_text())
for f,h in PINS.items():
 if sha(f)!=h:raise ValueError('frozen parent drift '+f)
X=load(BASE/'once.py','dense_fullsuite_storage_parent');S=X.S;A=S.A;O=X.O;M=X.M;B=load(P/'budget.py','dense_fullsuite_budget');require=S.require
for module in (X,O,M):module.CONTROL=CONTROL;module.EVIDENCE=EVIDENCE;module.UNIT=UNIT
ORIGINAL_BUILD=X.build_plan;SUITE_BUILD=S.build_plan;RUN=S.run_attached;RESET=A.reset;DUMP=A.state_hashes;CLOSE=A.Transport.close
CURRENT=None

def check_space(plan,budget,started=False):
 a=plan['adapter'];c=Path(a['output']);e=Path(a['evidence_output']);c=c if started else c.parent;e=e if started else e.parent
 require(c.stat().st_dev!=e.stat().st_dev,'separate evidence filesystem')
 b=plan['storage'];require(b['retained_state_dumps']==27 and b['per_request_state_bytes']==B.PER,'exact retained capture groups/extent')
 require(b['evidence_forecast_bytes']==27*B.PER+B.META and b['root_floor_bytes']==B.ROOT_FLOOR and b['root_cache_forecast_bytes']==B.ROOT_CACHE and b['external_floor_bytes']==B.EXTERNAL_FLOOR,'unchanged full forecast and reserves')
 return B.check_free(shutil.disk_usage(c).free,shutil.disk_usage(e).free,budget)
def storage_guard(plan,completed=0,started=False):
 require(type(completed)is int and 0<=completed<=B.CAP,'suite count budget')
 budget=CURRENT or B.Budget();require(budget.resets==completed,'count agrees with acknowledged RESETs')
 return check_space(plan,budget,started)
def reset(t,destination):
 result=RESET(t,destination);t.capture_budget.reset();return result
def state_hashes(t):
 result=DUMP(t);t.capture_budget.dump();return result
def close(t,normal=True):
 result=CLOSE(t,normal)
 if normal:
  t.capture_budget.finish();check_space(t.capture_plan,t.capture_budget,True)
  t.capture_budget_result['capture_budget']=t.capture_budget.report()
 return result
def run_attached(t,plan,m=None):
 global CURRENT
 require(CURRENT is None and not hasattr(t,'capture_budget'),'one capture budget per suite');budget=B.Budget();t.capture_budget=budget;t.capture_plan=plan;CURRENT=budget
 try:
  result=RUN(t,plan,m);require(budget.resets==26 and budget.dumps==24 and budget.repeats==1 and budget.remaining==B.D,'complete pre-FINISH capture acknowledgements')
  result['capture_budget']=budget.report();t.capture_budget_result=result;return result
 finally:CURRENT=None
A.reset=reset;A.state_hashes=state_hashes;A.Transport.close=close;S.storage_guard=storage_guard;S.run_attached=run_attached

def sources():return [Path(__file__),P/'budget.py',P/'test_budget.py',P/'README.md',P/'parent-pins.json',P/'evidence/independent-review.json']
def suite_build(*args,**kwargs):
 p=SUITE_BUILD(*args,**kwargs);p['capture_accounting']='acknowledged RESET target+draft / DUMP target / final FINISH draft; no file-existence credit'
 p['source_sha256'].update({str(f):sha(f) for f in sources()});return p
S.build_plan=suite_build

def build_plan():
 r=json.loads((P/'evidence/independent-review.json').read_text());require(r['passed'] and r.get('source_sha256'),'independent storage correction review')
 for f,h in r['source_sha256'].items():require(sha(Path(f) if Path(f).is_absolute() else S.R/f)==h,'review source drift')
 plan=ORIGINAL_BUILD();plan['schema']='ownrt.gsq.dense-packed-storage-b.v1';plan['source_sha256'].update({str(f):sha(f) for f in sources()});plan['capture_accounting']=plan['suite']['capture_accounting'];return plan
O.build_plan=build_plan

def main():
 p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--plan',action='store_true');g.add_argument('--run',type=Path);a=p.parse_args()
 if a.plan:print(json.dumps(build_plan(),indent=2));return
 raise SystemExit(O.run(a.run))
if __name__=='__main__':main()
