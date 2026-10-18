#!/usr/bin/env python3
"""GNU and Intel host-only bytes; never loads SYCL or model payloads."""
import hashlib,json,os,resource,subprocess,tempfile,time
from pathlib import Path
from compile_turn import turn
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 from math_gate import closure
 sources={str(f.relative_to(ROOT)):sha(f) for f in closure()}
 sources.update({str((P/n).relative_to(ROOT)):sha(P/n) for n in ('byte_gate.py','build_engine.py','compile_turn.py','p100_cpu.cpp','p82_cpu.cpp','p58j_route_cpu.cpp')})
 records=[];transcripts={};started=time.monotonic()
 with tempfile.TemporaryDirectory(prefix='bytes-',dir=P/'build') as tmp:
  tmp=Path(tmp)
  for compiler in ('/usr/bin/g++','/opt/intel/oneapi/compiler/2026.0/bin/icpx'):
   tag='gnu' if compiler.endswith('g++') else 'intel'
   for stem,args in [('p100_cpu',['down-tile16']),('p82_cpu',['rec-both-plus']),('p58j_route_cpu',[])]:
    binary=tmp/(tag+'-'+stem)
    cmd=[compiler,'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-DOWN_RT_HOST_ONLY','-Wno-unknown-pragmas','-I'+str(P),'-I'+str(P/'../../stage1/packet3-prep/src'),'-I'+str(P.parent/'packet2/kernels'),'-I'+str(P.parent/'packet2/loader'),str(P/(stem+'.cpp')),'-o',str(binary),'-lcrypto']
    with turn(),(P/'evidence'/f'{tag}-{stem}-build.log').open('w') as f:
     subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,check=True)
    for repeat in range(2):
     out=tmp/f'{tag}-{stem}-{repeat}';out.mkdir()
     result=subprocess.run([str(binary),*args,str(out)],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=600,env={'PATH':'/usr/bin:/bin','OMP_NUM_THREADS':'2'})
     (P/'evidence'/f'{tag}-{stem}-{repeat}.log').write_text(result.stdout+result.stderr)
     assert result.returncode==0,result.stdout+result.stderr
     assert (out/'expected.bin').read_bytes()==(out/'candidate.bin').read_bytes()
     transcripts[(tag,stem,repeat)]=(out/'expected.bin').read_text().splitlines()
     if repeat==0:(P/'evidence'/f'{tag}-{stem}-transcript.txt').write_bytes((out/'expected.bin').read_bytes())
     records.append(dict(compiler=tag,fixture=stem,repeat=repeat,passed=True,transcript_sha256=sha(out/'expected.bin'),binary_sha256=sha(binary),command=cmd,native=json.loads((out/'native.json').read_text()) if (out/'native.json').exists() else None))
     for leaf in ('native.json','cases.jsonl'):
      if (out/leaf).exists() and repeat==0:(P/'evidence'/f'{tag}-{stem}-{leaf}').write_bytes((out/leaf).read_bytes())
 cross_compiler={}
 for stem in ('p100_cpu','p82_cpu','p58j_route_cpu'):
  for tag in ('gnu','intel'):
   assert transcripts[tag,stem,0]==transcripts[tag,stem,1],'fresh process bytes differ'
  a=transcripts['gnu',stem,0];b=transcripts['intel',stem,0];assert len(a)==len(b)
  different=[i for i,(x,y) in enumerate(zip(a,b)) if x!=y]
  if different:
   assert stem=='p82_cpu','unexpected cross-compiler baseline difference'
   cases=[json.loads(x)['case'] for x in (P/'evidence/gnu-p82_cpu-cases.jsonl').read_text().splitlines()]
   assert all('-s6-' in cases[i] for i in different),'finite recurrence differs across compilers'
   cross_compiler[stem]=dict(equal=False,baseline_NaN_payload_cases=[cases[i] for i in different],explanation='GNU/Intel frozen58g reference NaN propagation differs; candidate equals its unchanged reference byte-for-byte on both. No arithmetic was changed to normalize it.')
  else:cross_compiler[stem]=dict(equal=True)
 assert all(sha(ROOT/n)==h for n,h in sources.items())
 rss=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024;assert rss<8*1024**3
 row=dict(passed=True,device_executed=False,schema='packet58j.byte-gates.v1',sources=sources,records=records,cross_compiler=cross_compiler,peak_rss_bytes=rss,elapsed_seconds=time.monotonic()-started)
 (P/'evidence/byte-gates.json').write_text(json.dumps(row,indent=2)+'\n');print(json.dumps({k:v for k,v in row.items() if k not in ('sources','records')}),flush=True)
if __name__=='__main__':main()
