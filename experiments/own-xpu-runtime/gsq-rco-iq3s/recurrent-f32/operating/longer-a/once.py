#!/usr/bin/env python3
"""Root-only corrected F32 correctness pair; frozen monitor/cleanup."""
import argparse,hashlib,importlib.util,json
from pathlib import Path
P=Path(__file__).resolve().parent;L=P.parents[2]
CONTROL=Path('/home/steve/own-xpu-runtime-results/gsq-recurrent-f32-longer-a.control')
EVIDENCE=Path('/mnt/usb-models/own-xpu-runtime-results/gsq-recurrent-f32-longer-a');UNIT='gsq-recurrent-f32-longer-a.service'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p,n):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
PARENT=L/'baseline/once.py';require_sha='5e7539962f97cb42da560c8c027fa8a739bef94f8797d5dfc4f448c4e485a9ad'
if sha(PARENT)!=require_sha:raise RuntimeError('frozen coordinator drift')
O=load(PARENT,'f32_frozen_coordinator');S=load(P/'suite.py','f32_correctness_suite');M=O.M
O.S=S;O.CONTROL=CONTROL;O.EVIDENCE=EVIDENCE;O.UNIT=UNIT
M.CONTROL=CONTROL;M.EVIDENCE=EVIDENCE;M.UNIT=UNIT

def build_plan():
 base=M.build_plan();suite=S.build_plan(CONTROL/'ranks',EVIDENCE);base.pop('prompt',None)
 base.update(schema='gsq.recurrent-f32.longer-once.v1',adapter=suite['adapter'],suite=suite,max_new=512,requests=3,unit=UNIT,scope=suite['scope'])
 ledger=P.parent/'candidate-ledger.json';delta=json.loads(ledger.read_text())['initial_mem_available_delta_bytes'];base['initial_mem_available_required']+=delta
 base['source_sha256'].update({str(f):sha(f) for f in [Path(__file__),PARENT,P/'suite.py',P/'budget.py',ledger,P/'authority.json',P/'source-preparation.json',P/'evidence/independent-review.json']})
 base['startup_max_new']=128; base['initial_extra_metadata_bytes']=S.BUDGET.INITIAL_EXTRA
 base['monitor_configuration']=dict(module_sha256=O.MODEL_SHA,coordinator_sha256=require_sha,CONTROL=str(CONTROL),EVIDENCE=str(EVIDENCE),UNIT=UNIT,initial_ram_delta_bytes=delta,behavior='unchanged Monitor, both positive contacts, retained-owner failure/physical drain')
 return base
O.build_plan=build_plan
if __name__=='__main__':
 p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--plan',action='store_true');g.add_argument('--run',type=Path);a=p.parse_args()
 if a.plan:print(json.dumps(build_plan(),indent=2))
 else:raise SystemExit(O.run(a.run))
