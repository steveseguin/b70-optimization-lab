"""Two fresh CPU arithmetic/layout checks per compiler; never SYCL initialization."""
import json,os,resource,subprocess
from build_engine import P,ROOT,sha,limits
from build_microbench import mirror
from compile_turn import turn
def main():
 limits();source=mirror(P/'cpu_bytes.cpp');records=[]
 for tag,compiler in [('gnu','/usr/bin/g++'),('intel','/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
  binary=P/'build'/('bytes-'+tag)
  command=[compiler,'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-DOWN_RT_HOST_ONLY','-Wno-unknown-pragmas',str(source),'-o',str(binary)]
  with turn(),(P/'evidence'/('bytes-build-'+tag+'.log')).open('w') as log:
   subprocess.run(command,check=True,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=180)
  outputs=[]
  for repeat in (1,2):
   p=subprocess.run([str(binary)],check=True,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120,env={**os.environ,'OMP_NUM_THREADS':'1'})
   (P/'evidence'/f'bytes-{tag}-{repeat}.json').write_text(p.stdout);r=json.loads(p.stdout);assert r['passed'] and r['checks']==24;outputs.append(r)
  assert outputs[0]==outputs[1]
  records.append(dict(compiler=tag,command=command,binary_sha256=sha(binary),fresh_processes=2,passed=True,result=outputs[0]))
 row=dict(passed=True,device_executed=False,records=records,source_sha256=sha(P/'cpu_bytes.cpp'),common_sha256=sha(P/'micro_common.hpp'),max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)
 (P/'evidence/cpu-bytes.json').write_text(json.dumps(row,indent=2)+'\n');print(json.dumps(row))
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,)*2);main()
