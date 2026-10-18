"""Bounded strict CPU gates; compile and execute host-only binaries serially."""
import argparse, hashlib, json, os, resource, subprocess
from pathlib import Path
P=Path(__file__).resolve().parent; B=P/'build'; S=P.parent

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--fixtures',type=Path,default=B/'fusion-fixtures');args=ap.parse_args()
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and 1<=int(os.environ['OMP_NUM_THREADS'])<=4
 resource.setrlimit(resource.RLIMIT_AS,(3*1024**3,3*1024**3))
 (B/'p33-candidate-tmp').mkdir(parents=True,exist_ok=True);os.environ['TMPDIR']=str(B/'p33-candidate-tmp')
 rows=[]
 for label,cc in [('gcc','/usr/bin/g++'),('icpx','/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
  binary=B/('p33-candidate-cpu-'+label)
  command=[cc,'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-DOWN_RT_HOST_ONLY','-I'+str(P),'-I'+str(S.parent/'stage1/packet3-prep/src'),'-I'+str(S/'packet2/kernels'),'-I'+str(S/'packet2/loader'),str(P/'p33_candidate_cpu.cpp'),'-o',str(binary)]
  result=subprocess.run(command,capture_output=True,text=True);(B/(label+'-p33-build.log')).write_text(result.stdout+result.stderr)
  if result.returncode:raise RuntimeError(result.stderr)
  for repeat in range(2):
   run=subprocess.run([str(binary),str(args.fixtures)],capture_output=True,text=True);(B/(label+'-p33-'+str(repeat)+'.log')).write_text(run.stdout+run.stderr)
   receipt=json.loads(run.stdout);rows.append(dict(compiler=label,repeat=repeat,binary_sha256=sha(binary),command=command,returncode=run.returncode,receipt=receipt))
 report=dict(device_executed=False,passed=all(r['returncode']==0 and r['receipt']['passed'] for r in rows),processes=len(rows),rows=rows,source_sha256={n:sha(P/n) for n in ['p33_candidates.hpp','p33_candidate_cpu.cpp','p33_candidate_gates.py']},fixture_sha256={n:sha(args.fixtures/n) for n in ['qsa-attention-1.fixture','qsa-attention-3.fixture']})
 report['fresh_repeat_identical']=all(rows[i]['receipt']==rows[i+1]['receipt'] for i in [0,2]);report['finite_cross_compiler_identical']=all(rows[0]['receipt']['candidates'][k]['hash']==rows[2]['receipt']['candidates'][k]['hash'] for k in rows[0]['receipt']['candidates'])
 report['passed']=report['passed'] and report['fresh_repeat_identical'] and report['finite_cross_compiler_identical'];(P/'p33-candidate-gates.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({k:v for k,v in report.items() if k not in ['rows','source_sha256','fixture_sha256']}));raise SystemExit(0 if report['passed'] else 1)
if __name__=='__main__':main()
