#!/usr/bin/env python3
"""Seal immutable selection directories sharing a single built device binary."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
from prepare_selections import CHOICES
P=Path(__file__).resolve().parent;ROOT=P.parents[3];B=P/'build';E=P/'evidence'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def save(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def link(src,dst):
 dst.parent.mkdir(parents=True,exist_ok=True)
 if dst.exists():assert sha(src)==sha(dst),dst
 else:os.link(src,dst)
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 build=read(P/'build-device-receipt.json');fixture=read(E/'fixture.json');gates=read(E/'cpu-gates.json')
 assert build['passed'] and fixture['passed'] and gates['passed']
 assert fixture['build_receipt_sha256']==sha(P/'build-device-receipt.json')
 assert fixture['selections']==list(CHOICES)==gates['selections']
 assert all(sha(ROOT/n)==v for n,v in build['sources'].items())
 assert all(sha(P/n)==v for n,v in build['artifacts'].items())
 common_sources=dict(build['sources'],**fixture['sources'])
 for f in (P/'build-device-receipt.json',E/'fixture.json',P/'seal_packet.py',P/'diagnose.py',E/'diagnosis.json'):
  common_sources[str(f.relative_to(ROOT))]=sha(f)
 rows=[]
 for choice in CHOICES:
  d=P/'selections'/choice;assert not (d/'screen-seal.json').exists()
  selected=read(d/'selection.json');assert selected['choices']['miss']==choice
  assert sum(r['choice']==choice for r in gates['rows'])==14
  binary=d/'build/device/own-rt-iq3';link(B/'device/own-rt-iq3',binary)
  for leaf in ('expected.bin','actual.bin'):link(E/leaf,d/'evidence'/leaf)
  sources=dict(common_sources)
  sources[str((d/'selection-decision.json').relative_to(ROOT))]=sha(d/'selection-decision.json')
  scoped=dict(schema='packet62.selection-build.v1',passed=True,device_executed=False,selection=choice,
   sources=sources,artifacts={'build/device/own-rt-iq3':sha(binary)},base_build_receipt_sha256=sha(P/'build-device-receipt.json'))
  save(d/'build-receipt.json',scoped)
  scoped_fixture=dict(fixture,build_receipt_sha256=sha(d/'build-receipt.json'),sources=sources,selection=choice)
  save(d/'fixture.json',scoped_fixture)
  cmd=[sys.executable,'-B',str(P.parent/'screen/seal.py'),'--profile','tp2','--lineage',str(d),
   '--build-receipt',str(d/'build-receipt.json'),'--fixture',str(d/'fixture.json'),'--binary',str(binary),
   '--dispatch',str(d/'dispatch-speed6.json'),'--output',str(d/'screen-seal.json')]
  subprocess.run(cmd,check=True,cwd=ROOT)
  for lane in ('A','B'):
   cmd=[sys.executable,'-B',str(P.parent/'screen/v3/screen.py'),'--profile','tp2','--lane',lane,
    '--lineage',str(d),'--seal',str(d/'screen-seal.json'),'--plan',
    '--output',str(P.parent/'screen/v3/evidence'/f'packet62-{choice}-{lane}')]
   result=subprocess.run(cmd,check=True,cwd=ROOT,capture_output=True,text=True)
   plan=json.loads(result.stdout);assert plan['device_executed'] is False and plan['identity']['binary_sha256']==sha(binary)
   save(d/f'plan-{lane}.json',plan)
  rows.append(dict(selection=choice,seal_sha256=sha(d/'screen-seal.json'),binary_sha256=sha(binary),
   plan_sha256={lane:sha(d/f'plan-{lane}.json') for lane in ('A','B')}))
  print(choice,'sealed; plans A+B PASS',flush=True)
 files=[f for root in (B,P/'selections') for f in root.rglob('*') if f.is_file()]
 logical=sum(f.stat().st_size for f in files);unique={ (f.stat().st_dev,f.stat().st_ino):f.stat().st_size for f in files}
 assert logical<400_000_000
 save(P/'packet.json',dict(schema='packet62.cpu-preparation.v1',passed=True,device_executed=False,selections=rows,
  build_logical_bytes_including_selection_views=logical,build_unique_inode_bytes=sum(unique.values()),
  CPU_gates_sha256=sha(E/'cpu-gates.json'),diagnosis_sha256=sha(E/'diagnosis.json'),
  recommendation='Screen batch first against control; banks are an independently selectable capture experiment, with no expected critical-path gain from current rank1-limited receipts.'))
if __name__=='__main__':main()
