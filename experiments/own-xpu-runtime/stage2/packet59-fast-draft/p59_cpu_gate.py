#!/usr/bin/env python3
"""Lean host gates: target byte parity and two fresh deterministic draft runs."""
import hashlib,json,os,shutil,subprocess,time
from pathlib import Path
import build,pipeline
P=Path(__file__).resolve().parent;ROOT=P.parents[3];B=P/'build'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(4,16))|set(range(20,32))
 assert os.environ.get('OMP_NUM_THREADS')=='2'
 start=time.monotonic();scratch=B/'p59-cpu-scratch';assert not scratch.exists();scratch.mkdir()
 evidence=P/'cpu-evidence';evidence.mkdir(exist_ok=True)
 baseline=None;new=None;rows=[]
 for name,binary in [('parent',P.parent/'packet56-draft-prefix/build/gnu-host/own-rt-iq3'),('new-a',B/'gnu-host/own-rt-iq3'),('new-b',B/'gnu-host/own-rt-iq3')]:
  dest=scratch/name
  args=pipeline.parser().parse_args(['--binary',str(binary.resolve()),'--output',str(dest),'--mini','--context','256','--tokens','24','--seconds','180','--wait-seconds','120','--native-nice','19','--draft','mtp','--draft-rank','1','--controller','native','--timing','token','--retain-steps','1-24'])
  args.host_memory='resident';args.draft='mtp'
  result=pipeline.run(args);assert result['passed']
  fixtures={str(f.relative_to(dest)):sha(f) for rank in ('rank0','rank1') for f in (dest/rank).glob('step*/layer-*.bf16')};assert fixtures
  target={'tokens':result['tokens'],'fixtures':fixtures}
  proposal=[json.loads(line)['guess'] for line in (dest/'rank1/draft-rows.jsonl').read_text().splitlines() if 'guess' in json.loads(line)]
  assert proposal and len(proposal)>=24
  if name=='parent':baseline=target
  else:
   assert target==baseline,'target fixture/token bytes changed'
   identity={'target':target,'proposals':proposal}
   if new is None:new=identity
   else:assert new==identity,'draft fresh process nondeterminism'
   (evidence/(name+'.json')).write_text(json.dumps(identity,sort_keys=True,separators=(',',':'))+'\n')
  rows.append({'arm':name,'binary_sha256':sha(binary),'target_identity_sha256':hashlib.sha256(json.dumps(target,sort_keys=True).encode()).hexdigest(),'proposal_sha256':hashlib.sha256(json.dumps(proposal).encode()).hexdigest(),'fixture_count':len(fixtures),'proposal_count':len(proposal)})
 # Exercise real K/format/fusion arithmetic with bounded synthetic allocations.
 cmd=['/usr/bin/g++','-std=c++20','-O2','-g0','-fno-fast-math','-ffp-contract=off','-ffunction-sections','-fdata-sections','-Wl,--gc-sections','-DOWN_RT_HOST_ONLY','-I'+str(P),'-I'+str(P.parent.parent/'stage1/packet3-prep/src'),'-I'+str(P.parent/'packet2/kernels'),'-I'+str(P.parent/'packet2/loader'),str(P/'p59_fixture.cpp'),'-o',str(B/'p59-fixture')]
 with (B/'p59-fixture-compile.log').open('w') as log:subprocess.run(cmd,check=True,stdout=log,stderr=subprocess.STDOUT,timeout=180)
 for name in ('a','b'):subprocess.run([str(B/'p59-fixture'),str(evidence/('production-'+name+'.bin'))],check=True,timeout=60)
 assert (evidence/'production-a.bin').read_bytes()==(evidence/'production-b.bin').read_bytes()
 # Parent target sources must be byte-identical. Only mtp.hpp changes among
 # the copied runtime sources; new p59 headers are reachable only from it.
 source_manifest=json.loads((P/'parent-source-manifest.json').read_text());checked=0
 for name,digest in source_manifest['files'].items():
  path=P/name
  if name=='mtp.hpp' or not path.exists():continue
  assert sha(path)==digest,'target or inherited source changed: '+name;checked+=1
 report={'schema':'packet59.lean-cpu-gates.v1','passed':True,'device_executed':False,'model_weights_read':False,'runs':rows,'target_source_files_identical':checked,'production_fixture_bytes':(evidence/'production-a.bin').stat().st_size,'production_fixture_sha256':sha(evidence/'production-a.bin'),'compile_command':cmd,'sources':build.compiled_sources(),'seconds':time.monotonic()-start,'scope':'Target mini fixture bytes equal packet56; fresh mini draft proposals and production-K synthetic draft arithmetic deterministic. Device target-oracle equality and acceptance remain pending.'}
 (P/'cpu-gates.json').write_text(json.dumps(report,indent=2)+'\n');shutil.rmtree(scratch);print(json.dumps({'passed':True,'seconds':report['seconds'],'target_source_files_identical':checked}))
if __name__=='__main__':main()
