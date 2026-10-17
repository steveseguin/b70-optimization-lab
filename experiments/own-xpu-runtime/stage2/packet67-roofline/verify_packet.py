#!/usr/bin/env python3
"""CPU-only closure checks and screen-plan verification; no model or device."""
from pathlib import Path
from types import SimpleNamespace
import json,sys,os
P=Path(__file__).resolve().parent;ROOT=P.parents[3];sys.path.insert(0,str(P/'screen'))
from common import read,sha,save,sealed,verify_map,require
from conditions import cpu_gate
from cpu_seal import verify
sys.path.insert(0,str(P/'screen/quick'))
from quick_seal import verify as quick_verify
from prepare_views import CHOICES,ORDERS
def main():
 cpu_gate();verify();quick_verify();b=read(P/'build-device-receipt.json');verify_map(ROOT,b['sources']);verify_map(P,b['artifacts'])
 rows=[]
 for choice in CHOICES:
  v=P/'selections'/choice
  identity=sealed(SimpleNamespace(lineage=v,seal=v/'screen-seal.json',binary=v/'build/device/own-rt-iq3',dispatch=v/'dispatch-speed6.json',profile='tp2',timing='token',placement='1'))
  require(identity['placement']['supported'],'placement unsupported');rows.append(dict(choice=choice,seal_sha256=sha(v/'screen-seal.json')))
 require(len({sha(P/'selections'/c/'build/device/own-rt-iq3') for c in CHOICES})==1,'not one device binary')
 for mode in ('gnu','intel'):
  r=read(P/'evidence'/('cpu-'+mode)/'receipt.json');verify_map(ROOT,r['sources']);require(r['passed'] and len(r['runs'])==2,'CPU gate missing')
  require(r['fixture_driver_sha256']==sha(P/'cpu_fixture.py'),'CPU driver changed')
  for x in r['runs']:require(x['native']['cases']==60 and x['native']['passed'] and x['expected_sha256']==x['candidate_sha256'],'CPU byte identity')
 for lane in ORDERS:
  plan=read(P/'screen/quick'/('plans-'+lane+'.json'));require(len(plan['plans'])==6 and plan['device_executed'] is False,'incomplete screen plans')
 require(read(P/'evidence/selection-tests.json')['passed'],'actual-submit/parser failed')
 registers=read(P/'register-report.json');require(registers['passed'] and not registers['device_executed'],'offline build missing')
 for k in registers['kernels']:require(sha(ROOT/k['assembly'])==k['sha256'],'offline assembly changed')
 seen=set();size=0
 for f in (P/'build').rglob('*'):
  if f.is_file():
   st=f.stat();key=(st.st_dev,st.st_ino)
   if key not in seen:size+=st.st_size;seen.add(key)
 require(size<1024**3,'build exceeds 1 GiB');require(os.statvfs(P).f_bavail*os.statvfs(P).f_frsize>=10*1024**3,'below 10 GiB disk floor')
 save(P/'cpu-validation.json',dict(schema='packet67.cpu-validation.v1',passed=True,device_executed=False,cpu_model_executed=False,device_quality='pending',device_speed='unmeasured',selections=rows,
   build_receipt_sha256=sha(P/'build-device-receipt.json'),cpu_compilers=2,fresh_runs_per_compiler=2,cases_per_run=60,screen_plans=12,build_unique_bytes=size,verification_script_sha256=sha(Path(__file__)),
   evidence={str(x.relative_to(P)):sha(x) for x in (P/'evidence/selection-tests.json',P/'evidence/host-compilers.json',P/'screen/quick/wrapper-seal.json',P/'screen/quick/plans-A.json',P/'screen/quick/plans-B.json')}))
 print('PASS: five immutable choices, 240 fixture cases, actual submitters, twelve plans; no GPU/model execution')
if __name__=='__main__':main()
