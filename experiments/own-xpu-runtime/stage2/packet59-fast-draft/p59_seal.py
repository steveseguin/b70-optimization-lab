#!/usr/bin/env python3
"""Bind the lean gates and immutable compiler products; screen-only seal."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
import build
P=Path(__file__).resolve().parent;ROOT=P.parents[3];B=P/'build'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(4,16))|set(range(20,32))
 assert not (P/'build-receipt.json').exists(),'never replace a seal'
 sources=build.compiled_sources();artifacts={}
 for mode in ('gnu-host','device'):
  row=json.loads((P/('build-'+mode+'-receipt.json')).read_text());assert row['passed'] and not row['device_executed']
  assert row['compiled_sources_sha256']==sources,'stale build'
  for n,h in row['checked_mirror_sha256'].items():assert sha(B/n)==h
  assert sha(B/mode/'compile_commands.json')==row['compile_commands_sha256']
  for n,h in row['artifacts_sha256'].items():assert sha(B/n)==h;artifacts['build/'+n]=h
 gate=json.loads((P/'cpu-gates.json').read_text());assert gate['passed'] and gate['sources']==sources
 for row in gate['runs']:
  if row['arm'].startswith('new'):assert row['binary_sha256']==artifacts['build/gnu-host/own-rt-iq3']
 for p in P.glob('p59_*.py'):sources[str(p.relative_to(ROOT))]=sha(p)
 for name in ('p59_fixture.cpp','parent-source-manifest.json','cpu-gates.json','dispatch-speed6.json','selection.json','memory-plan.json','build.py','storage.py','pipeline.py','suite_metrics.py'):
  sources[str((P/name).relative_to(ROOT))]=sha(P/name)
 for name in ('p59-fixture',):artifacts['build/'+name]=sha(B/name)
 save(P/'compile-receipt.json',{'schema':'packet59.cpu-build.v1','passed':True,'device_executed':False,'sources':sources,'artifacts':artifacts})
 save(P/'byte-fixture.json',{'schema':'own-runtime.screen.byte-fixture.v1','passed':True,'device_executed':False,'build_receipt_sha256':sha(P/'compile-receipt.json'),'changed_class':'draft only: target fixtures byte-identical to packet56; two fresh draft proposal sequences identical','command':['nice','-n','19','taskset','-c','4-15,20-31','env','OMP_NUM_THREADS=2','python3','-B',str(P/'p59_cpu_gate.py')],'sources':sources,'expected':{'path':'cpu-evidence/new-a.json','sha256':sha(P/'cpu-evidence/new-a.json')},'actual':{'path':'cpu-evidence/new-b.json','sha256':sha(P/'cpu-evidence/new-b.json')}})
 subprocess.run([sys.executable,'-B',str(P.parent/'screen/seal.py'),'--profile','tp2','--lineage',str(P),'--build-receipt',str(P/'compile-receipt.json'),'--fixture',str(P/'byte-fixture.json'),'--binary',str(B/'device/own-rt-iq3'),'--dispatch',str(P/'dispatch-speed6.json'),'--output',str(P/'build-receipt.json')],check=True)
 print(json.dumps({'passed':True,'device_executed':False,'seal_sha256':sha(P/'build-receipt.json')}))
if __name__=='__main__':main()
