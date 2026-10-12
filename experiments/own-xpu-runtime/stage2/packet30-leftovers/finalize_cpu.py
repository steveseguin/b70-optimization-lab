#!/usr/bin/env python3
"""Seal CPU evidence, inspect ELF symbols/loader only; never run device binary."""
import gzip,hashlib,json,os,re,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,r):Path(p).write_text(json.dumps(r,indent=2,ensure_ascii=False)+"\n")
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2'
 evidence={};rows=[];hashes=[]
 for compiler in ('host','icpx-host'):
  root=P/'build'/compiler;binary=root/'g3'
  for mode in ('validation','fixtures'):
   for repeat in (1,2):
    directory=root/(mode+str(repeat));r=read(directory/'receipt.json')
    assert r['passed'] and not r['device_executed'] and r['safe_to_exit'] and r['live_bytes']==r['in_flight']==0
    assert r['checks']==54
    if mode=='validation':assert r['negative_validation_checks']==88
    rows.append(dict(compiler=compiler,mode=mode,repeat=repeat,binary_sha256=sha(binary),checks=r['checks'],negative_validation_checks=r['negative_validation_checks']))
    for f in directory.iterdir():
     if f.is_file():evidence[str(f.relative_to(P))]=f.read_text()
    if mode=='fixtures':hashes.append(sha(directory/'exactness.jsonl'))
 assert len(set(hashes))==1,'both compilers/fresh processes must return identical output hashes'
 families={n:read(P/n) for n in ('route-gates.json','attention-gates.json','small-fusion-cpu-receipt.json','family-gates.json')}
 assert families['family-gates.json']['passed']
 for n,digest in families['family-gates.json']['source_sha256'].items():assert sha(P/n)==digest,n+' changed since family gates'
 assert families['attention-gates.json']['passed'] and families['small-fusion-cpu-receipt.json']['passed']
 assert all(p['exit_code']==0 for r in families['route-gates.json']['runs'] for p in r['processes'])
 from test_protocol import Protocol
 import unittest,io
 stream=io.StringIO();result=unittest.TextTestRunner(stream=stream).run(unittest.defaultTestLoader.loadTestsFromTestCase(Protocol))
 assert result.wasSuccessful(),stream.getvalue()
 save(P/'protocol-tests.json',dict(passed=True,device_executed=False,tests=result.testsRun,output=stream.getvalue()))
 binary=P/'build/device/g3'
 ldd=subprocess.run(['ldd',str(binary)],capture_output=True,text=True,timeout=10)
 assert ldd.returncode==0 and 'not found' not in ldd.stdout+ldd.stderr
 save(P/'ldd-preflight.json',dict(passed=True,device_executed=False,argv=['ldd',str(binary)],stdout=ldd.stdout,stderr=ldd.stderr,binary_sha256=sha(binary)))
 nm=subprocess.run(['nm','-S','--defined-only',str(binary)],capture_output=True,text=True,check=True)
 sizes=[]
 for line in nm.stdout.splitlines():
  if 'p30_guard' in line and 'capture_size' in line:
   fields=line.split();sizes.append(int(fields[1],16))
 assert sizes and max(sizes)<=1024
 save(P/'kernel-sizes.json',dict(passed=True,device_executed=False,guarded_instantiations=len(sizes),maximum_instrumented_capture_bytes=max(sizes),all_captures_limit_bytes=1024,named_small_fusion_captures='by-value lambda static_assert(sizeof(kernel)<=1024); listed in kernel-submissions.json',binary_sha256=sha(binary)))
 for mode in ('host','icpx-host','device'):
  for f in (P/'build'/mode).glob('*.log'):evidence[str(f.relative_to(P))]=f.read_text()
 for f in (P/'build').glob('*repeat*.log'):evidence[str(f.relative_to(P))]=f.read_text()
 for f in (P/'build').glob('*build*.log'):evidence[str(f.relative_to(P))]=f.read_text()
 raw=json.dumps(evidence,ensure_ascii=False,sort_keys=True).encode();(P/'cpu-evidence.json.gz').write_bytes(gzip.compress(raw,mtime=0))
 receipts={n:sha(P/n) for n in (*families,'protocol-tests.json','kernel-sizes.json','ldd-preflight.json','cpu-evidence.json.gz')}
 save(P/'cpu-tests.json',dict(passed=True,device_executed=False,arithmetic='iq3-p17-detmath-v2',harness=rows,exactness_jsonl_sha256=hashes[0],families=families,receipt_hashes=receipts,protocol_tests=result.testsRun,empty_attention_three_way_gate='not passed: existing Core/incumbent disagreement; excluded runtime domain',source_sha256={f.name:sha(f) for f in P.iterdir() if f.suffix in ('.hpp','.cpp','.py')},no_speed_claim=True))
 print('CPU seal PASS: '+str(len(rows))+' harness invocations, '+str(result.testsRun)+' protocol tests; native never executed')
if __name__=='__main__':main()
