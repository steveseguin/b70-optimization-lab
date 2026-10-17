#!/usr/bin/env python3
"""Lean exact host Engine checks; synthetic miniature only, no weights/GPU."""
import hashlib,json,os,shutil,subprocess,time
from pathlib import Path
import build,pipeline
P=Path(__file__).resolve().parent;B=P/'build'
def require(ok,message):
 if not ok:raise ValueError(message)
def main():
 require(os.getpriority(os.PRIO_PROCESS,0)==19,'nice19 required')
 require(set(os.sched_getaffinity(0))<=set(range(4,16))|set(range(20,32)),'helper affinity required')
 require(os.environ.get('OMP_NUM_THREADS')=='2','OMP2 required')
 root=B/'p57-cpu-scratch';require(not root.exists(),'fresh scratch only');root.mkdir()
 start=time.monotonic();rows=[];passed=False
 binaries={'parent':P.parent/'packet56-draft-prefix/build/gnu-host/own-rt-iq3','new':B/'gnu-host/own-rt-iq3'}
 expected=None
 try:
  for name,binary,timing in [('parent-token',binaries['parent'],'token'),('new-token',binaries['new'],'token'),('new-attribution-a',binaries['new'],'attribution'),('new-attribution-b',binaries['new'],'attribution')]:
   dest=root/name
   args=pipeline.parser().parse_args(['--binary',str(binary.resolve()),'--output',str(dest),'--mini','--context','256','--tokens','24','--seconds','600','--wait-seconds','120','--native-nice','19','--draft','mtp','--draft-rank','1','--controller','native','--timing',timing,'--retain-steps','1-24'])
   args.host_memory='resident';args.draft='mtp'
   result=pipeline.run(args)
   require(result['passed'],'mini Engine run failed')
   hashes={str(f.relative_to(dest)):pipeline.sha(f) for rank in ('rank0','rank1') for f in (dest/rank).glob('step*/layer-*.bf16')}
   require(hashes,'missing mini layer fixtures')
   identity={'tokens':result['tokens'],'guess_sequence':result.get('guess_sequence'),'stats':{k:result['stats'][k] for k in ('guesses','hits','misses','no_guess')},'fixtures':hashes}
   if expected is None:expected=identity
   require(identity==expected,'observation changed token/proposal/fixture identity: '+name)
   rows.append({'arm':name,'binary_sha256':pipeline.sha(binary),'timing':timing,'tokens':len(result['tokens']),'fixture_count':len(hashes),'exact_identity_sha256':hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()})
  tests=subprocess.run(['/usr/bin/python3','-B','-m','unittest','discover','-s',str(P),'-p','test_packet57.py','-v'],capture_output=True,text=True)
  (B/'p57-tests.log').write_text(tests.stdout+tests.stderr);require(tests.returncode==0,'packet57 unit gates failed')
  row={'schema':'packet57.lean-cpu-gate.v1','passed':True,'device_executed':False,'real_model_executed':False,'binary_sha256':pipeline.sha(binaries['new']),'compiled_sources_sha256':build.compiled_sources(),'runs':rows,'unit_test_sources_sha256':{f.name:pipeline.sha(f) for f in P.glob('test_packet57.py')},'unit_tests_log_sha256':pipeline.sha(B/'p57-tests.log'),'seconds':time.monotonic()-start,'scope':'Four fresh synthetic mini processes compare original56 token, new57 token, two new57 attribution runs: all target tokens, guesses, hit/miss counts and retained layer fixtures; new real-model device oracle equality pending'}
  (P/'p57-cpu-gates.json').write_text(json.dumps(row,indent=2)+'\n');passed=True;print(json.dumps({'passed':True,'runs':len(rows),'seconds':row['seconds']}))
 finally:
  # New synthetic model scratch only; compact exact evidence above is retained.
  if passed:shutil.rmtree(root)
  else:(root/'failure-retention.json').write_text(json.dumps({'passed':False,'device_executed':False,'completed_runs':rows,'scope':'Preserved failed CPU evidence; review before any cleanup'},indent=2)+'\n')
if __name__=='__main__':main()
