#!/usr/bin/env python3
"""Bind two immutable selections to the same binary and run four CPU-only plans."""
import json,os,subprocess,sys
from pathlib import Path
from build_engine import sha,save
from prepare_selections import CHOICES,configs
P=Path(__file__).resolve().parent;ROOT=P.parents[3];B=P/'build';E=P/'evidence'
def read(p):return json.loads(p.read_text())
def link(a,b):b.parent.mkdir(parents=True,exist_ok=True);os.link(a,b)
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 build=read(P/'build-device-receipt.json');gate=read(E/'cpu-gates.json');diagnosis=read(E/'diagnosis.json')
 assert build['passed'] and gate['passed'] and not build['device_executed'] and not gate['device_executed']
 assert gate['build_receipt_sha256']==sha(P/'build-device-receipt.json')
 assert gate['selections']==list(CHOICES) and diagnosis['decision']['rank_balance']=='skipped'
 assert all(sha(ROOT/n)==h for n,h in build['sources'].items())
 assert all(sha(P/n)==h for n,h in build['artifacts'].items())
 assert all(sha(ROOT/n)==h for n,h in gate['sources'].items())
 sources=dict(build['sources'],**gate['sources'])
 for f in (P/'seal_packet.py',P/'diagnose.py',P/'build-device-receipt.json',E/'cpu-gates.json',E/'diagnosis.json'):
  sources[str(f.relative_to(ROOT))]=sha(f)
 rows=[]
 for name,config in configs().items():
  dest=P/'selections'/name;assert not (dest/'screen-seal.json').exists()
  assert read(dest/'selection.json')==config
  runs=[r for r in gate['rows'] if r['label'] in (name+'-a',name+'-b')];assert len(runs)==2
  assert all(r['binary_sha256']==build['artifacts']['build/gnu-host/own-rt-iq3'] and r['target_fixture_count']==96 and r['target_token_count']==24 for r in runs)
  binary=dest/'build/device/own-rt-iq3';link(B/'device/own-rt-iq3',binary)
  scoped_sources=dict(sources)
  for leaf in ('selection.json','selection-decision.json','memory-plan.json','dispatch-speed6.json'):
   f=dest/leaf;scoped_sources[str(f.relative_to(ROOT))]=sha(f)
  for key in ('expected','actual'):link(E/(name+'-'+key+'.bin'),dest/('fixture-'+key+'.json'))
  save(dest/'build-receipt.json',dict(schema='packet63.selection-build.v1',passed=True,device_executed=False,selection=name,sources=scoped_sources,artifacts={'build/device/own-rt-iq3':sha(binary)},base_build_receipt_sha256=sha(P/'build-device-receipt.json')))
  save(dest/'fixture.json',dict(schema='own-runtime.screen.byte-fixture.v1',passed=True,device_executed=False,build_receipt_sha256=sha(dest/'build-receipt.json'),changed_class='Packet61x plus optional draft-only HC group: 96 target fixtures/24 tokens equal packet56, 27 proposals and five draft state files deterministic across fresh CPU processes',command=[sys.executable,'-B',str(P/'cpu_gate.py')],sources=scoped_sources,expected=dict(path='fixture-expected.json',sha256=sha(dest/'fixture-expected.json')),actual=dict(path='fixture-actual.json',sha256=sha(dest/'fixture-actual.json'))))
  cmd=[sys.executable,'-B',str(P.parent/'screen/seal.py'),'--profile','tp2','--lineage',str(dest),'--build-receipt',str(dest/'build-receipt.json'),'--fixture',str(dest/'fixture.json'),'--binary',str(binary),'--dispatch',str(dest/'dispatch-speed6.json'),'--output',str(dest/'screen-seal.json')]
  subprocess.run(cmd,cwd=ROOT,check=True)
  for lane in ('A','B'):
   cmd=[sys.executable,'-B',str(P.parent/'screen/v3/screen.py'),'--profile','tp2','--lane',lane,'--lineage',str(dest),'--seal',str(dest/'screen-seal.json'),'--output',str(P.parent/'screen/v3/evidence'/f'packet63-{name}-{lane}'),'--plan']
   r=subprocess.run(cmd,cwd=ROOT,check=True,capture_output=True,text=True);plan=json.loads(r.stdout)
   assert plan['device_executed'] is False and plan['supported'] is True and plan['identity']['binary_sha256']==sha(binary)
   save(dest/('plan-'+lane+'.json'),plan)
  rows.append(dict(selection=name,seal_sha256=sha(dest/'screen-seal.json'),binary_sha256=sha(binary),selection_sha256=sha(dest/'selection.json'),plans={lane:sha(dest/('plan-'+lane+'.json')) for lane in ('A','B')}))
  print(name,'seal and v3 plans A+B PASS',flush=True)
 files=[f for root in (B,P/'selections') for f in root.rglob('*') if f.is_file()]
 logical=sum(f.stat().st_size for f in files);unique={(f.stat().st_dev,f.stat().st_ino):f.stat().st_size for f in files};assert logical<400_000_000
 save(P/'packet.json',dict(schema='packet63.cpu-preparation.v1',passed=True,device_executed=False,rank_balance=diagnosis['decision'],selections=rows,build_and_selection_logical_bytes=logical,unique_inode_bytes=sum(unique.values()),cpu_gates_sha256=sha(E/'cpu-gates.json'),diagnosis_sha256=sha(E/'diagnosis.json'),qualification='CPU preparation only; coordinator screens and any full chain remain pending.'))
if __name__=='__main__':main()
