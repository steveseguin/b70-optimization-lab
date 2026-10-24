#!/usr/bin/env python3
"""Explicit root-admitted two-arm capture check using frozen Monitor/run lifecycle."""
import argparse,hashlib,importlib.util,json
from pathlib import Path
P=Path(__file__).resolve().parent;L=P.parent
CONTROL=Path('/home/steve/own-xpu-runtime-results/gsq-state-bundle-a.control')
EVIDENCE=Path('/mnt/usb-models/own-xpu-runtime-results/gsq-state-bundle-a')
UNIT='gsq-state-bundle-a.service';PARENT=L/'baseline/once.py';PARENT_SHA='5e7539962f97cb42da560c8c027fa8a739bef94f8797d5dfc4f448c4e485a9ad'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p,n):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
if sha(PARENT)!=PARENT_SHA:raise RuntimeError('frozen coordinator drift')
O=load(PARENT,'bundle_frozen_coordinator');S=load(P/'qualification.py','bundle_two_arm_qualification');M=O.M
O.S=S;O.CONTROL=CONTROL;O.EVIDENCE=EVIDENCE;O.UNIT=UNIT
M.CONTROL=CONTROL;M.EVIDENCE=EVIDENCE;M.UNIT=UNIT
def build_plan():
 base=M.build_plan();suite=S.build_plan(CONTROL/'ranks',EVIDENCE);base.pop('prompt',None)
 base.update(schema='gsq.state-bundle.once.v1',adapter=suite['adapter'],suite=suite,max_new=128,requests=2,unit=UNIT,scope='two fixed prompt00 arms; evidence format only; no speed claim')
 ledger=L/'qkv-q6-p33/engine/operating/candidate-ledger.json';base['initial_mem_available_required']+=json.loads(ledger.read_text())['initial_mem_available_delta_bytes']
 files=[Path(__file__),PARENT,P/'qualification.py',P/'test_qualification.py',P/'reader.py',P/'preparation.json',P/'parent-pins.json',P/'evidence/independent-review.json',P/'evidence/native-build.json',ledger]
 base['source_sha256'].update({str(f):sha(f) for f in files});base['monitor_configuration']=dict(module_sha256=O.MODEL_SHA,coordinator_sha256=PARENT_SHA,CONTROL=str(CONTROL),EVIDENCE=str(EVIDENCE),UNIT=UNIT,initial_ram_delta_bytes=382730240,behavior='unchanged Monitor and two-rank retained-owner cleanup')
 return base
O.build_plan=build_plan
def main():
 ap=argparse.ArgumentParser();g=ap.add_mutually_exclusive_group(required=True);g.add_argument('--plan',action='store_true');g.add_argument('--run',type=Path);a=ap.parse_args()
 if a.plan:print(json.dumps(build_plan(),indent=2));return
 raise SystemExit(O.run(a.run))
if __name__=='__main__':main()
