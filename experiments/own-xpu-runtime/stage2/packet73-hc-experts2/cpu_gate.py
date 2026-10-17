"""GNU then Intel, two fresh tiny operator lifetimes each; no model/backend."""
from pathlib import Path
import hashlib,json,os,resource,shlex,subprocess
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
 result=dict(passed=False,device_executed=False,runs=[],sources={})
 for name,compiler in [('gnu','/usr/bin/g++'),('intel','/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
  out=P/'build'/('cpu-'+name);out.mkdir(parents=True,exist_ok=True)
  cmd=[compiler,'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-DOWN_RT_HOST_ONLY','-I'+str(P),'-I'+str(P.parents[1]/'stage1/packet3-prep/src'),'-I'+str(P.parent/'packet2/kernels'),'-I'+str(P.parent/'packet2/loader'),'-MMD','-MF',str(out/'deps.d'),str(P/'p73_cpu.cpp'),'-o',str(out/'fixture')]
  with (out/'compile.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,check=True,timeout=300)
  for n in shlex.split((out/'deps.d').read_text().replace('\\\n',' ').split(':',1)[1]):result['sources'][str(Path(n).resolve().relative_to(ROOT))]=sha(n)
  for repeat in (1,2):
   dest=out/f'repeat-{repeat}';dest.mkdir(exist_ok=True)
   with (dest/'run.log').open('w') as f:subprocess.run([str(out/'fixture'),str(dest)],stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,check=True,timeout=300)
   native=json.loads((dest/'native.json').read_text());a=sha(dest/'expected.bin');b=sha(dest/'candidate.bin')
   assert native['passed'] and native['cases']==24 and a==b
   result['runs'].append(dict(compiler=name,command=cmd,repeat=repeat,native=native,expected_sha256=a,candidate_sha256=b,path=str(dest.relative_to(ROOT))))
   print(name,repeat,'PASS',flush=True)
 assert len({r['candidate_sha256'] for r in result['runs']})==1
 result['sources'][str((P/'cpu_gate.py').relative_to(ROOT))]=sha(P/'cpu_gate.py')
 result.update(passed=True,max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)
 (P/'evidence/cpu-byte-identity.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
