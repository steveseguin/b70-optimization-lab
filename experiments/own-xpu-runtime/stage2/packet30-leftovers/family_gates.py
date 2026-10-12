#!/usr/bin/env python3
"""Rebuild and repeat every independent CPU family gate; no SYCL/device link."""
import hashlib,json,os,resource,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent
FLAGS=['-std=c++20','-O2','-Werror=return-type','-fno-fast-math','-ffp-contract=off','-fno-associative-math','-fno-unsafe-math-optimizations','-DOWN_RT_HOST_ONLY']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2'
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3));out=P/'build/families';out.mkdir(parents=True,exist_ok=True)
 os.environ['TMPDIR']=str(out)
 rows=[]
 for label,compiler in [('gcc','/usr/bin/g++'),('icpx','/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
  for family in ['route','attention','small','fusion']:
   binary=out/(family+'-'+label)
   flags=FLAGS+(['-fdenormal-fp-math=ieee'] if label=='icpx' else [])+(['-DHOST_ONLY','-DP30_ROUTE_CPU_MAIN'] if family=='route' else [])
   cmd=[compiler,*flags,str(P/(family+'_cpu.cpp')),'-o',str(binary)]
   r=subprocess.run(cmd,capture_output=True,text=True);assert r.returncode==0,r.stderr
   row=dict(family=family,compiler=label,compile_and_link_argv=cmd,compile_stdout=r.stdout,compile_stderr=r.stderr,binary_sha256=sha(binary),runs=[])
   for repeat in range(2):
    r=subprocess.run([binary],capture_output=True,text=True);assert r.returncode==0,(family,r.stdout,r.stderr)
    row['runs'].append(dict(returncode=r.returncode,stdout=r.stdout,stderr=r.stderr))
   assert row['runs'][0]==row['runs'][1],family+' nondeterministic CPU gate output'
   rows.append(row);print(family+' '+label+' PASS twice',flush=True)
 assert all('-fno-fast-math' in r['compile_and_link_argv'] and '-ffp-contract=off' in r['compile_and_link_argv'] for r in rows)
 receipt=dict(passed=True,device_executed=False,rows=rows,source_sha256={f.name:sha(f) for f in P.iterdir() if f.suffix in ('.cpp','.hpp')},max_compile_jobs=1,memory_limit_bytes=8*1024**3)
 (P/'family-gates.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()
