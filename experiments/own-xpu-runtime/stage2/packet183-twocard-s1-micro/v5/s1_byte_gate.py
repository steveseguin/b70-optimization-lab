"""Packet183 S1 byte gate: lane, submission and census equality, GNU and Intel.

CPU only, synthetic weights (no model read). The fixture TU (native/s1_bytes.cpp)
is compiled by each compiler and linked against this packet's gnu-host engine
objects (every packet136 parent object unchanged, plus the recompiled
p49d_submit.o and the new s1_submit.o), so the production submissions and the
S1 submissions it compares are the exact linked host code. Two fresh runs per
compiler. Writes evidence/s1-bytes.json.
"""
import json,os,resource,subprocess
from p183_v5_build_engine import P,LOCAL,ROOT,B,CHECKED,sha,save,run,limits

def main():
 limits();out=B/'s1-bytes';out.mkdir(exist_ok=True);prior=json.loads((P/'engine-commands.json').read_text())
 args=list(next(r['command'] for r in prior if r['name']=='gnu-host-entry-main'));args=args[1:args.index('-o')];i=args.index('-c');del args[i:i+2]
 link0=list(next(r['command'] for r in prior if r['name']=='gnu-host-link'))
 rows=[];binaries={}
 for compiler,cxx in [('GNU','/usr/bin/g++'),('Intel','/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
  obj=out/(compiler+'.o');binary=out/('fixture-'+compiler)
  run([cxx,*args,'-c',P/'native/s1_bytes.cpp','-o',obj],'s1-bytes-'+compiler+'-compile')
  link=[str(obj) if x.endswith('/entry-main.o') else x for x in link0 if not x.endswith('own-rt-iq3-entry.cpp.o')];link[0]=cxx
  link[link.index('-o')+1]=str(binary)
  link+=['-no-pie','-Wl,-rpath,/opt/intel/oneapi/compiler/2026.0/lib']
  run(link,'s1-bytes-'+compiler+'-link');binaries[compiler]=binary
  for repeat in (1,2):
   cases=out/f'cases-{compiler}-{repeat}.jsonl'
   env=dict(os.environ,OMP_NUM_THREADS='2',LD_LIBRARY_PATH='/opt/intel/oneapi/compiler/2026.0/lib')
   cp=subprocess.run([str(binary),str(cases)],env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=1800)
   assert cp.returncode==0,cp.stderr[-4000:]
   row=json.loads(cp.stdout);assert row['passed'] and row['device_executed'] is False
   rows.append(dict(row,compiler=compiler,repeat=repeat,cases_sha256=sha(cases),case_count=len(cases.read_text().splitlines())))
 assert len({r['cases_sha256'] for r in rows})==1,'case transcripts differ across compilers/repeats'
 assert len({(r['lane_checks'],r['submission_checks'],r['mutation_checks']) for r in rows})==1 and rows[0]['mutation_checks']==18
 sources={str(f.relative_to(ROOT)):sha(f) for f in (P/'s1_byte_gate.py',P/'native/s1_bytes.cpp',CHECKED/'s1_lanes.hpp',CHECKED/'s1_kernels.hpp',CHECKED/'s1_submit.hpp',CHECKED/'s1_submit.cpp',P/'build/gnu-host/s1_submit.o',P/'build/gnu-host/p49d_submit.o')}
 save(P/'evidence/s1-bytes.json',dict(passed=True,device_executed=False,model_read=False,synthetic_weights=True,
   families=['p33.dense.segment Q6_K K2560/6144/10240 variants 6/7','p49c attention_combine Q6_K K6144 rows2560 batch1/2','p49d small.ffn.q6 tuple'],
   mutation_proof='zeroed FP32 words change production output and not S1; bumped metadata sub-scales change S1 output and not production (segment 12, attention 4, small 2: 18 checks per run)',
   d_cover='random normal fp16 plus 0x0000 0x8000 0x0001 0x8001 0x03ff 0x83ff 0x0400 0x7bff 0xfbff 0x3c00 0xbc00 0x1234 0x2e66; sub-scales incl. -128/127/0/-1/1',
   scenarios='8 per family: ordinary, inactive, error set, position 4096, position 0xffffffff, NaN input, +/-inf input, subnormal input (zero/negative inputs on attention batch rows)',
   runs=rows,binaries={k:sha(v) for k,v in binaries.items()},sources=sources))
 print('S1 lanes/submissions/census: GNU and Intel, two runs each, byte-identical PASS')
if __name__=='__main__':resource.setrlimit(resource.RLIMIT_AS,(6*1024**3,6*1024**3));main()
