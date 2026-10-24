#!/usr/bin/env python3
"""Six-request coverage coordinator; root owns plan/live admission and launch."""
from pathlib import Path
import argparse,hashlib,importlib.util,json
P=Path(__file__).resolve().parent;L=P.parent
CONTROL=Path('/home/steve/own-xpu-runtime-results/gsq-coverage-a.control')
EVIDENCE=Path('/mnt/usb-models/own-xpu-runtime-results/gsq-coverage-a')
UNIT='gsq-coverage-a.service';PARENT=L/'baseline/once.py';PARENT_SHA='5e7539962f97cb42da560c8c027fa8a739bef94f8797d5dfc4f448c4e485a9ad'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p,name):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
if sha(PARENT)!=PARENT_SHA:raise RuntimeError('frozen coordinator changed')
O=load(PARENT,'coverage_frozen_coordinator');S=load(P/'suite.py','coverage_suite');M=O.M
O.S=S;O.CONTROL=M.CONTROL=CONTROL;O.EVIDENCE=M.EVIDENCE=EVIDENCE;O.UNIT=M.UNIT=UNIT

def build_plan():
 base=M.build_plan();suite=S.build_plan(CONTROL/'ranks',EVIDENCE);base.pop('prompt',None)
 base.update(schema='gsq.coverage.once.v1',adapter=suite['adapter'],suite=suite,max_new=512,requests=6,unit=UNIT,scope='Three preregistered broader pairs; exactsame-target checks and task readback, no speed/independent-model-quality claim')
 base['initial_mem_available_required']+=382730240
 files=[PARENT,Path(__file__),P/'suite.py',P/'manifest.json',P/'README.md',P/'test_coverage.py',P/'tokenizer.py',P/'evidence/independent-review.json',S.REVIEW]
 base['source_sha256'].update({str(f):sha(f) for f in files})
 base['monitor_configuration']=dict(module_sha256=O.MODEL_SHA,coordinator_sha256=PARENT_SHA,CONTROL=str(CONTROL),EVIDENCE=str(EVIDENCE),UNIT=UNIT,initial_ram_delta_bytes=382730240,behavior='unchanged Monitor/run; both physical contacts and safe drain mandatory')
 return base
O.build_plan=build_plan
if __name__=='__main__':
 ap=argparse.ArgumentParser();g=ap.add_mutually_exclusive_group(required=True);g.add_argument('--plan',action='store_true');g.add_argument('--run',type=Path);a=ap.parse_args()
 if a.plan:print(json.dumps(build_plan(),indent=2))
 else:raise SystemExit(O.run(a.run))
