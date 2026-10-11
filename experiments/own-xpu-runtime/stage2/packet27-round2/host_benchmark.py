"""Reproduce the same isolated CPU owner comparison; never starts a device."""
import hashlib,json,os,resource,subprocess,time
from pathlib import Path
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
 scratch=P/'build'/('owner-benchmark-'+str(time.time_ns()));scratch.mkdir(parents=True)
 os.environ['TMPDIR']=str(scratch)
 rows={};sources={};binaries={}
 flags=['-std=c++20','-O2','-fno-fast-math','-ffp-contract=off']
 for label,base in [('before',P.parent/'packet18-decode-v2'),('after',P)]:
  src=scratch/(label+'.cpp');src.write_bytes((P/'host_issue_benchmark.cpp').read_bytes());binary=scratch/label
  subprocess.run(['g++',*flags,'-I'+str(base),str(src),str(base/'owner.cpp'),str(base/'owner_retire.cpp'),'-o',str(binary)],check=True)
  rows[label]=json.loads(subprocess.check_output([str(binary)],text=True));binaries[label]=sha(binary)
  for f in [P/'host_issue_benchmark.cpp',base/'owner.cpp',base/'owner_retire.cpp',base/'owner.hpp']:sources[str(f.relative_to(ROOT))]=sha(f)
 receipt=dict(schema='packet26.host-owner-before-after.v1',passed=True,device_executed=False,limitation='CPU no-op owner bookkeeping only; excludes SYCL, device execution and Engine plan work.',**rows,compiler='g++ '+' '.join(flags),sources=sources,binaries=binaries)
 output=scratch/'receipt.json';data=json.dumps(receipt,indent=2)+'\n';output.write_text(data);(P/'host-issue-benchmark.json').write_text(data);print(output)
if __name__=='__main__':main()
