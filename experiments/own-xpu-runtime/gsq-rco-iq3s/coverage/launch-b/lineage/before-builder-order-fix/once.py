#!/usr/bin/env python3
"""Additive startup-only correction; the six-request coverage suite is unchanged."""
from pathlib import Path
import argparse,hashlib,importlib.util,json
P=Path(__file__).resolve().parent;C=P.parent;R=C.parents[3]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def require(v,m):
 if not v:raise ValueError(m)
for name,digest in json.loads((P/'parent-pins.json').read_text()).items():require(sha(name)==digest,'frozen coverage-a source/diagnosis changed')
spec=importlib.util.spec_from_file_location('coverage_b_private_parent',C/'once.py');Q=importlib.util.module_from_spec(spec);spec.loader.exec_module(Q)
S=Q.S;A=S.A;O=Q.O;M=Q.M
CONTROL=Path('/home/steve/own-xpu-runtime-results/gsq-coverage-b.control')
EVIDENCE=Path('/mnt/usb-models/own-xpu-runtime-results/gsq-coverage-b')
UNIT='gsq-coverage-b.service';STARTUP_MAX_NEW=128
Q.CONTROL=O.CONTROL=M.CONTROL=CONTROL;Q.EVIDENCE=O.EVIDENCE=M.EVIDENCE=EVIDENCE;Q.UNIT=O.UNIT=M.UNIT=UNIT
original_command=A.command;original_adapter_plan=A.build_plan;original_suite_plan=S.build_plan;original_outer_plan=Q.build_plan
def correction_pins():
 files=[Path(__file__),P/'parent-pins.json',P/'test_launch.py',P/'README.md',P/'evidence/independent-review.json']
 review=json.loads(files[-1].read_text());require(review['passed'] and review['source_sha256'],'independent launch-b review required')
 for name,digest in review['source_sha256'].items():
  f=Path(name);require(sha(f if f.is_absolute() else R/f)==digest,'reviewed launch-b source changed')
 return {str(f):sha(f) for f in files}
def adapter_plan(*args,**kwargs):
 p=original_adapter_plan(*args,**kwargs)
 require(not p['mini'] and p['max_new']==512,'fixed broader request ceiling')
 p.update(startup_max_new=STARTUP_MAX_NEW,request_max_new_by_case=[512,512,128])
 p['source_sha256'].update(correction_pins());return p
def command(plan,rank,channel,stop_fd):
 require(plan['startup_max_new']==128 and plan['max_new']==512 and plan['request_max_new_by_case']==[512,512,128],'startup/request distinction')
 launch=dict(plan,max_new=plan['startup_max_new'])
 return original_command(launch,rank,channel,stop_fd)
def suite_plan(*args,**kwargs):
 p=original_suite_plan(*args,**kwargs);p.update(startup_max_new=128,request_max_new_by_case=[512,512,128]);p['source_sha256'].update(correction_pins());return p
def build_plan():
 p=original_outer_plan();p.update(schema='gsq.coverage.launch-b.v1',startup_max_new=128,request_max_new_by_case=[512,512,128],correction_scope='Only native startup --max-new is 128. All six RPC request caps, prompts, context, quality and equality gates are unchanged. Coverage-a remains failed.')
 p['source_sha256'].update(correction_pins());return p
A.command=command;A.build_plan=adapter_plan;S.build_plan=suite_plan;O.build_plan=build_plan
if __name__=='__main__':
 ap=argparse.ArgumentParser();g=ap.add_mutually_exclusive_group(required=True);g.add_argument('--plan',action='store_true');g.add_argument('--run',type=Path);a=ap.parse_args()
 if a.plan:print(json.dumps(build_plan(),indent=2))
 else:raise SystemExit(O.run(a.run))
