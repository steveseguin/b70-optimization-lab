#!/usr/bin/env python3
"""Small CPU fixtures only; fresh rank pair twice for every registered choice set."""
import hashlib,json,os,shutil,subprocess,time
from pathlib import Path
import build,pipeline
from p59c_selection import P,sha,save,read,profiles,selection
B=P/'build';ROOT=P.parents[3];E=P/'cpu-evidence'
def constraints():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 assert os.environ.get('OMP_NUM_THREADS')=='2'
def run_one(binary,dest,config=None):
 adapter=dest.parent/(dest.name+'-adapter');adapter.mkdir()
 (adapter/'memory-plan.json').write_bytes((P/'memory-plan.json').read_bytes())
 if config is not None:save(adapter/'selection.json',config)
 pipeline.P=adapter
 args=pipeline.parser().parse_args(['--binary',str(binary.resolve()),'--output',str(dest),'--mini','--context','256','--tokens','24','--seconds','180','--wait-seconds','120','--native-nice','19','--draft','mtp','--draft-rank','1','--controller','native','--timing','token','--retain-steps','1-24'])
 args.host_memory='resident';args.draft='mtp'
 if config is not None:args.selection_sha256=sha(adapter/'selection.json')
 result=pipeline.run(args);assert result['passed']
 fixtures={str(f.relative_to(dest)):sha(f) for rank in ('rank0','rank1') for f in (dest/rank).glob('step*/layer-*.bf16')};assert len(fixtures)==96
 target={'tokens':result['tokens'],'fixtures':fixtures}
 proposals=[r['guess'] for line in (dest/'rank1/draft-rows.jsonl').read_text().splitlines() if 'guess' in (r:=json.loads(line))]
 assert len(proposals)>=24
 choices=json.loads((dest/'rank1/draft-kernel-choices.json').read_text())
 if config is not None:
  assert choices['choices']==config['draft'] and choices['selection_sha256']==args.selection_sha256
 identity={'target':target,'proposals':proposals}
 evidence={'binary_sha256':sha(binary),'target_identity_sha256':hashlib.sha256(json.dumps(target,sort_keys=True).encode()).hexdigest(),'proposal_sha256':hashlib.sha256(json.dumps(proposals).encode()).hexdigest(),'fixture_count':len(fixtures),'proposal_count':len(proposals)}
 return identity,evidence,choices

def pair(config,destination,baseline):
 destination.mkdir(parents=True,exist_ok=False);scratch=B/('cpu-'+destination.name+'-'+str(time.time_ns()));scratch.mkdir()
 values=[];rows=[]
 try:
  for suffix in ('a','b'):
   identity,row,choices=run_one(B/'gnu-host/own-rt-iq3',scratch/suffix,config)
   assert identity['target']==baseline,'target fixture/token change'
   save(destination/(suffix+'.json'),identity);save(destination/('choices-'+suffix+'.json'),choices)
   values.append(identity);rows.append(row)
  assert values[0]==values[1],'fresh-process draft nondeterminism'
  report={'passed':True,'device_executed':False,'selection':config,'selection_canonical_sha256':hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest(),'runs':rows,'expected':{'path':str((destination/'a.json').relative_to(P)),'sha256':sha(destination/'a.json')},'actual':{'path':str((destination/'b.json').relative_to(P)),'sha256':sha(destination/'b.json')}}
  save(destination/'receipt.json',report)
  return report
 finally:
  # Only this run's disposable mini model files. Compact identities are retained.
  shutil.rmtree(scratch)

def main():
 constraints();start=time.monotonic();E.mkdir(exist_ok=True)
 scratch=B/('cpu-baseline-'+str(time.time_ns()));scratch.mkdir()
 parent,parent_row,_=run_one(P.parent/'packet56-draft-prefix/build/gnu-host/own-rt-iq3',scratch/'parent')
 old59,old59_row,_=run_one(P.parent/'packet59-fast-draft/build/gnu-host/own-rt-iq3',scratch/'packet59')
 assert parent['target']==old59['target'];save(E/'parent.json',parent);save(E/'packet59.json',old59);shutil.rmtree(scratch)
 reports={}
 for name,config in profiles().items():
  report=pair(config,E/name,parent['target']);reports[name]=sha(E/name/'receipt.json')
  if name=='default':assert json.loads((E/name/'a.json').read_text())==parent,'production default differs from packet56'
  if name=='all-packet59':assert json.loads((E/name/'a.json').read_text())==old59,'all choices differ from packet59'
  print(name,'PASS',flush=True)
 # Production-width synthetic BF16/INT8, fusions and trees in two fresh processes.
 cmd=['/usr/bin/g++','-std=c++20','-O2','-g0','-fno-fast-math','-ffp-contract=off','-ffunction-sections','-fdata-sections','-Wl,--gc-sections','-DOWN_RT_HOST_ONLY','-I'+str(P),'-I'+str(P.parent.parent/'stage1/packet3-prep/src'),'-I'+str(P.parent/'packet2/kernels'),'-I'+str(P.parent/'packet2/loader'),str(P/'p59_fixture.cpp'),'-o',str(B/'p59-fixture')]
 with (B/'p59-fixture-compile.log').open('w') as log:subprocess.run(cmd,check=True,stdout=log,stderr=subprocess.STDOUT,timeout=180)
 for name in ('a','b'):subprocess.run([str(B/'p59-fixture'),str(E/('production-'+name+'.bin'))],check=True,timeout=60)
 assert sha(E/'production-a.bin')==sha(E/'production-b.bin')
 # Target source arithmetic is untouched. The sole inherited target-facing delta
 # is the strict init-time selection parser, which freezes all target choices.
 manifest=json.loads((P/'parent-source-manifest.json').read_text());checked=0
 for name,digest in manifest['files'].items():
  if name in ('mtp.hpp','p49d_submit.cpp','p49d_submit.hpp') or not (P/name).exists():continue
  assert sha(P/name)==digest,'inherited target source changed: '+name;checked+=1
 report={'schema':'packet59c.lean-cpu-gates.v1','passed':True,'device_executed':False,'model_weights_read':False,'sources':build.compiled_sources(),'gate_sources':{n:sha(P/n) for n in ('p59c_cpu_gate.py','p59c_selection.py','p59_fixture.cpp')},'choice_sets':reports,'parent':parent_row,'packet59':old59_row,'target_source_files_identical':checked,'parent_fixture':{'path':'cpu-evidence/parent.json','sha256':sha(E/'parent.json')},'production_fixture_sha256':sha(E/'production-a.bin'),'fixture_binary_sha256':sha(B/'p59-fixture'),'compile_command':cmd,'seconds':time.monotonic()-start,'limits':'Mini target fixtures and draft proposals; production-width synthetic draft kernels. Route and split32 production-only branches use separate host operator checks. No device qualification.'}
 save(P/'cpu-gates.json',report);print(json.dumps({'passed':True,'choice_sets':len(reports),'seconds':report['seconds']}))
if __name__=='__main__':main()
