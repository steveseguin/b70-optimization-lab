#!/usr/bin/env python3
"""One root-admitted resident suite using the proven first-run passive monitor."""
import argparse,hashlib,importlib.util,json,os,resource,signal,time
from pathlib import Path
P=Path(__file__).resolve().parent;L=P.parent
CONTROL=Path('/home/steve/own-xpu-runtime-results/gsq-baseline-a.control')
EVIDENCE=Path('/mnt/usb-models/own-xpu-runtime-results/gsq-baseline-a')
UNIT='gsq-baseline-a.service'
MODEL_ONCE=L/'operating/model_once.py'
MODEL_SHA='cea4ca122973976e1668954652e98d1590a7a2dfe8e62239d271a32a15153ce1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p,name):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
if sha(MODEL_ONCE)!=MODEL_SHA:raise RuntimeError('frozen first-run monitor changed')
M=load(MODEL_ONCE,'gsq_baseline_frozen_monitor');S=load(P/'suite.py','gsq_baseline_suite_runner')
# Only explicit per-run constants of this private imported module differ. Its
# observation, marker, PID/fault/memory guards, write bounds and drain code do not.
M.CONTROL=CONTROL;M.EVIDENCE=EVIDENCE;M.UNIT=UNIT

def review_binding():
 path=P/'evidence/independent-suite-review.json';r=M.read_json(path)
 M.require(r.get('passed') is True,'independent suite review required')
 # Review schemas use source_sha256; exact reviewed source bytes are mandatory.
 pins=r.get('source_sha256',{})
 M.require(pins,'review source pins required')
 for name,digest in pins.items():
  p=Path(name);p=p if p.is_absolute() else M.R/p
  M.require(sha(p)==digest,'reviewed source changed: '+name)
 return path

def build_plan():
 base=M.build_plan();suite=S.build_plan(CONTROL/'ranks',EVIDENCE);review=review_binding()
 base.pop('prompt',None)
 base.update(schema='ownrt.gsq.resident-baseline-once.v1',adapter=suite['adapter'],suite=suite,max_new=128,requests=26,unit=UNIT,scope='all12 original short prompts,balanced resident target/MTP;2excluded warmups;no cold-start claim')
 files=[Path(__file__).resolve(),P/'suite.py',P/'test_suite.py',P/'manifest.json',P/'README.md',review,MODEL_ONCE,L/'serving/evidence/real-model-a/review.json']
 base['source_sha256'].update({str(p):sha(p) for p in files})
 base['monitor_configuration']={'module_sha256':MODEL_SHA,'CONTROL':str(CONTROL),'EVIDENCE':str(EVIDENCE),'UNIT':UNIT,'all_other_monitor_behavior':'unchanged'}
 return base

def run(path):
 plan=M.read_json(path);M.require(plan==build_plan(),'reviewed plan/source/parent binding changed');S.validate_plan(plan['suite'])
 M.require(resource.getrlimit(resource.RLIMIT_AS)==(resource.RLIM_INFINITY,resource.RLIM_INFINITY),'unlimited native address space required')
 M.require(os.getpriority(os.PRIO_PROCESS,0)==plan['nice'] and sorted(os.sched_getaffinity(0))==plan['affinity'],'coordinator priority/affinity')
 M.require(not (Path('/home/steve')/'igdrcl.config').exists() and not (M.R/'igdrcl.config').exists(),'unadmitted driver config')
 monitor=M.Monitor(plan);result=None;retained=None;original=None
 for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,lambda s,f:M.STOP.append(s) if not M.STOP else None)
 monitor.sample(initial=True,force=True);S.storage_guard(plan['suite'])
 M.record('admission.json',dict(plan=plan,plan_sha256=sha(path),canonical_plan_sha256=hashlib.sha256(M.canonical(plan)).hexdigest(),before=monitor.latest,unit=monitor.unit),exclusive=True)
 try:
  result=S.qualification(plan['suite'],admit=lambda p:M.require(p==plan['suite'],'suite admission mismatch'),check=monitor.check,launch_hook=monitor.register)
 except S.A.RetainedOwner as error:
  original=error.original;retained=error.transport;monitor.latch(original)
 except BaseException as error:original=error;monitor.latch(error)
 # Exactly the proved stop-pipe and physical-drain retention behavior; no second
 # signal, owner restart, service action, state pruning or failure recovery.
 while True:
  snapshot=monitor.sample(force=True,draining=True)
  if monitor.drained(snapshot,retained):
   passed=bool(result and result.get('passed') and monitor.first is None and len(monitor.identities)==2 and all(monitor.contacts))
   terminal=dict(passed=passed,result=result,first_error=repr(monitor.first) if monitor.first else None,original_error=repr(original) if original else None,rank_identities=monitor.identities,observed_target_contact=monitor.contacts,children_exited=True,target_descriptors_empty=True,after=snapshot,elapsed=time.monotonic()-monitor.started,service_changes=0,retries=0,hard_kills=0,plan_sha256=sha(path),scope='resident baseline only; full external result is hash-bound in compact result join')
   try:M.record('terminal.json',terminal,exclusive=True)
   except BaseException as error:monitor.latch(error);time.sleep(1);continue
   print(json.dumps({'passed':passed,'terminal':str(CONTROL/'terminal.json')}),flush=True);return 0 if passed else 1
  try:time.sleep(1)
  except BaseException as error:monitor.latch(error)

def main():
 ap=argparse.ArgumentParser();g=ap.add_mutually_exclusive_group(required=True);g.add_argument('--plan',action='store_true');g.add_argument('--run',type=Path);a=ap.parse_args()
 if a.plan:print(json.dumps(build_plan(),indent=2));return 0
 return run(a.run)
if __name__=='__main__':raise SystemExit(main())
