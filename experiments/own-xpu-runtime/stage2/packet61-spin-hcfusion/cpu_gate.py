#!/usr/bin/env python3
"""One integrated HC capture check, then retained 96-layer/24-token target gate."""
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

P=Path(__file__).resolve().parent;ROOT=P.parents[3];B=P/'build';PARENT=P.parent/'packet56-draft-prefix'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 assert os.environ.get('OMP_NUM_THREADS')=='2'
 assert not (P/'screen-seal.json').exists()
 os.environ['TMPDIR']=str(B/'tmp')
 evidence=P/'integrated-fixture';evidence.mkdir(exist_ok=True)
 metadata=P/'evidence/production-plan.tsv'
 metadata.write_bytes((PARENT/'build/input/plan.tsv').read_bytes())
 commands=json.loads((P/'engine-commands.json').read_text())
 compile_cmd=next(x['command'] for x in commands if x['name']=='gnu-host-entry-main')
 compile_cmd=compile_cmd[:compile_cmd.index('-o')]+['-o',str(B/'integrated-fixture.o'),'-c',str(B/'engine/integrated_fixture.cpp')]
 # Resolve both includes to the same generated engine and primitive bodies.
 fixture_data=B/'engine/fixture-data.cpp'
 checked_math=B/'checked'/P.relative_to(ROOT)/'p60_math.hpp'
 fixture_data.write_text((P/'fixture.cpp').read_text().replace('#include "p60_math.hpp"','#include '+json.dumps(str(checked_math))))
 text=(P/'integrated_fixture.cpp').read_text().replace('#include "fixture.cpp"','#include '+json.dumps(str(fixture_data)))
 (B/'engine/integrated_fixture.cpp').write_text(text)
 link_cmd=next(x['command'] for x in commands if x['name']=='gnu-host-link')
 link_cmd=[x for x in link_cmd if not x.endswith('own-rt-iq3-entry.cpp.o')]
 link_cmd=[str(B/'integrated-fixture.o') if x==str(B/'gnu-host/entry-main.o') else x for x in link_cmd]
 link_cmd[link_cmd.index('-o')+1]=str(B/'integrated-fixture')
 def run(cmd,name):
  with (B/(name+'.log')).open('w') as log:subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
  print(name,'PASS',flush=True)
 run(compile_cmd,'compile-integrated-fixture');run(link_cmd,'link-integrated-fixture')
 run([str(B/'integrated-fixture'),str(evidence),str(metadata),str(P/'dispatch-speed6.json')],'integrated-fixture')
 integrated=json.loads((B/'integrated-fixture.log').read_text().splitlines()[-1])
 assert (evidence/'expected.bin').read_bytes()==(evidence/'actual.bin').read_bytes()
 sys.path.insert(0,str(PARENT));import pipeline
 rows=[];baseline=None
 for arm,binary in [('parent',PARENT/'build/gnu-host/own-rt-iq3'),('candidate',B/'gnu-host/own-rt-iq3')]:
  dest=B/('target-'+arm);assert not dest.exists(),dest
  args=pipeline.parser().parse_args(['--binary',str(binary),'--output',str(dest),'--mini','--context','256','--tokens','24','--seconds','180','--wait-seconds','120','--native-nice','19','--draft','mtp','--draft-rank','1','--controller','native','--timing','token','--retain-steps','1-24'])
  args.host_memory='resident';args.draft='mtp'
  result=pipeline.run(args);assert result['passed']
  fixtures={str(f.relative_to(dest)):sha(f) for rank in ('rank0','rank1') for f in (dest/rank).glob('step*/layer-*.bf16')}
  assert len(fixtures)==96
  target=dict(tokens=result['tokens'],fixtures=fixtures)
  assert len(target['tokens'])==24
  if baseline is None:baseline=target
  else:assert target==baseline,'target bytes/tokens differ'
  save(evidence/(arm+'-target.json'),target)
  rows.append(dict(arm=arm,binary_sha256=sha(binary),fixture_count=len(fixtures),tokens=len(target['tokens'])))
 # Seal one combined raw byte pair covering primitives and integrated dispatch.
 expected=(P/'fixture/expected.bin').read_bytes()+(evidence/'expected.bin').read_bytes()
 actual=(P/'fixture/actual.bin').read_bytes()+(evidence/'actual.bin').read_bytes()
 assert expected==actual
 (evidence/'combined-expected.bin').write_bytes(expected);(evidence/'combined-actual.bin').write_bytes(actual)
 sources={str(x.relative_to(ROOT)):sha(x) for x in (P/'integrated_fixture.cpp',P/'cpu_gate.py',P/'fixture.cpp',fixture_data,B/'engine/integrated_fixture.cpp',metadata)}
 controller_cmd=[sys.executable,'-B',str(P/'native_controller_gate.py'),'--binary',str(B/'native_controller_test'),'--output',str(P/'evidence/controller.json')]
 subprocess.run(controller_cmd,check=True)
 faults=json.loads(subprocess.check_output([str(B/'native_mailbox_fault_test')],text=True))
 assert faults['passed'] and faults['gates']==5
 save(P/'evidence/mailbox-faults.json',faults)
 for path in (P/'native_controller_gate.py',P/'pipeline.py',P/'test_state_machine.py',P/'evidence/controller.json',P/'evidence/mailbox-faults.json'):
  sources[str(path.relative_to(ROOT))]=sha(path)
 build=json.loads((P/'build-device-receipt.json').read_text())
 sources.update(build['sources'])
 save(evidence/'receipt.json',dict(schema='own-runtime.screen.byte-fixture.v1',passed=True,device_executed=False,
  changed_class='Both target HC sides: three prepared stages, production-shape intermediate/state bytes; unchanged 96 mini target fixtures and 24 tokens',
  command=[sys.executable,'-B',str(P/'cpu_gate.py')],compile_command=compile_cmd,link_command=link_cmd,
  build_receipt_sha256=sha(P/'build-device-receipt.json'),sources=sources,
  expected=dict(path='integrated-fixture/combined-expected.bin',sha256=sha(evidence/'combined-expected.bin')),
  actual=dict(path='integrated-fixture/combined-actual.bin',sha256=sha(evidence/'combined-actual.bin')),
  bytes_compared=len(expected),integrated=integrated,target_runs=rows,
  qualification='CPU synthetic only; coordinator target-oracle device screen pending'))
 print('Lean CPU gate PASS:',len(expected),'bytes; 96 target fixtures and 24 tokens',flush=True)
if __name__=='__main__':main()
