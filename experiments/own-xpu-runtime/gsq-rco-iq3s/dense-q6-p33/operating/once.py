#!/usr/bin/env python3
"""Explicit candidate coordinator; source-only preparation until root admission."""
import argparse,hashlib,importlib.util,json
from pathlib import Path
P=Path(__file__).resolve().parent;L=P.parents[1]
CONTROL=Path('/home/steve/own-xpu-runtime-results/gsq-dense-q6-p33-engine-a.control')
EVIDENCE=Path('/mnt/usb-models/own-xpu-runtime-results/gsq-dense-q6-p33-engine-a')
UNIT='gsq-dense-q6-p33-engine-a.service'
PARENT=L/'baseline/once.py';PARENT_SHA='5e7539962f97cb42da560c8c027fa8a739bef94f8797d5dfc4f448c4e485a9ad'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(path,name):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
if sha(PARENT)!=PARENT_SHA:raise RuntimeError('frozen baseline coordinator changed')
O=load(PARENT,'gsq_dense_q6_frozen_coordinator');S=load(P/'generated/suite.py','gsq_dense_q6_suite');M=O.M
# Frozen run() resolves these private module globals. RetainedOwner consequently
# remains the exact class belonging to the candidate adapter used for startup.
O.S=S;O.CONTROL=CONTROL;O.EVIDENCE=EVIDENCE;O.UNIT=UNIT
M.CONTROL=CONTROL;M.EVIDENCE=EVIDENCE;M.UNIT=UNIT

def build_plan():
 S.C.verify_materialization();base=M.build_plan();suite=S.build_plan(CONTROL/'ranks',EVIDENCE)
 base.pop('prompt',None)
 base.update(schema='ownrt.gsq.dense-q6-once.v1',adapter=suite['adapter'],suite=suite,max_new=128,requests=26,unit=UNIT,scope='candidate all12 exact baseline arms; separate-process timings descriptive only')
 ledger=json.loads((P/'candidate-ledger.json').read_text());base['initial_mem_available_required']+=ledger['initial_mem_available_delta_bytes']
 files=[PARENT,Path(__file__),P/'checks.py',P/'prepare.py',P/'preparation.json',P/'overlay.patch',P/'candidate-ledger.json',P/'test_operating.py',P/'README.md',P/'generated/adapter.py',P/'generated/suite.py',P/'evidence/independent-review.json',P.parent/'evidence/native-build.json',P.parent/'evidence/cpu-proof.json',L/'attention-q8-p33/evidence/scale-census.json',L/'qkv-q6-p33/evidence/cpu-proof.json',L/'qkv-q6-p33/micro/evidence/device-a/review.json',P/'authority.json',P/'parent-pins.json',P/'overlay.patch',L/'state-bundle/evidence/device-a/review.json',L/'expert-iq3xxs-block/engine/operating/evidence/device-a/review.json',S.C.REVIEW,S.C.REFERENCE]
 base['source_sha256'].update({str(f):sha(f) for f in files})
 base['monitor_configuration']=dict(module_sha256=O.MODEL_SHA,coordinator_sha256=PARENT_SHA,CONTROL=str(CONTROL),EVIDENCE=str(EVIDENCE),UNIT=UNIT,initial_ram_delta_bytes=571473920,behavior='unchanged frozen Monitor/run lifecycle; candidate suite and explicit memory admission')
 return base
O.build_plan=build_plan

def main():
 ap=argparse.ArgumentParser();g=ap.add_mutually_exclusive_group(required=True);g.add_argument('--plan',action='store_true');g.add_argument('--run',type=Path);a=ap.parse_args()
 if a.plan:print(json.dumps(build_plan(),indent=2));return 0
 return O.run(a.run)
if __name__=='__main__':raise SystemExit(main())
