"""Independent strict scalar comparisons under both host compilers."""
import hashlib,json,os,resource,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent;B=P/'build'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3));rows=[]
 (B/'tmp').mkdir(exist_ok=True);os.environ['TMPDIR']=str(B/'tmp')
 for label,compiler in [('gcc','/usr/bin/g++'),('icpx','/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
  binary=B/('expert-down-review-'+label)
  cmd=[compiler,'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-DOWN_RT_HOST_ONLY','-I'+str(P),'-I'+str(P.parents[1]/'stage1/packet3-prep/src'),'-I'+str(P.parent/'packet2/kernels'),'-I'+str(P.parent/'packet2/loader'),str(P/'expert_down_review_test.cpp'),'-o',str(binary)]
  with (B/('expert-down-review-'+label+'-build.log')).open('w') as out:subprocess.run(cmd,check=True,stdout=out,stderr=subprocess.STDOUT)
  for repeat in range(2):
   result=subprocess.run([str(binary)],capture_output=True,text=True)
   (B/('expert-down-review-'+label+'-'+str(repeat)+'.log')).write_text(result.stdout+result.stderr)
   receipt=json.loads(result.stdout);assert receipt['supported_finite_passed'],result.stdout+result.stderr
   rows.append(dict(compiler=label,repeat=repeat,binary_sha256=sha(binary),receipt=receipt))
 assert len({r['receipt']['finite_hash'] for r in rows})==1
 for compiler in ('gcc','icpx'):assert len({json.dumps(r['receipt'],sort_keys=True) for r in rows if r['compiler']==compiler})==1
 report=dict(passed=True,device_executed=False,source_sha256=sha(P/'expert_down_review_test.cpp'),processes=len(rows),checks_per_process=rows[0]['receipt']['finite_checks'],all_diagnostic_checks_per_process=rows[0]['receipt']['checks'],nonfinite_qualified=False,diagnostic_passed=all(r['receipt']['passed'] for r in rows),rows=rows)
 (P/'expert-down-review-gates.json').write_text(json.dumps(report,indent=2)+'\n');print('strict expert down',len(rows),'processes passed')
if __name__=='__main__':main()
