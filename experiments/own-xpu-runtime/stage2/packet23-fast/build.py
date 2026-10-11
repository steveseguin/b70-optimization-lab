#!/usr/bin/env python3
"""CPU only; compile native binaries without executing them. Maximum two jobs."""
import os,subprocess,json,hashlib,time,shutil,resource
from pathlib import Path
P=Path(__file__).resolve().parent;B=P/'build';ROOT=P.parents[3]
PY='/home/steve/.venvs/vllm-xpu/bin/python';IC='/opt/intel/oneapi/compiler/2026.0/bin/icpx'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def save(n,x):(P/n).write_text(json.dumps(x,indent=2)+'\n')
def run(args,log):
 print('RUN',log,flush=True)
 with (P/log).open('w') as f:subprocess.run(list(map(str,args)),check=True,stdout=f,stderr=subprocess.STDOUT)
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
 assert 'idle' in subprocess.check_output(['ionice','-p',str(os.getpid())],text=True)
 os.environ['OPENBLAS_NUM_THREADS']='2';os.environ['TMPDIR']=str(B/'tmp');(B/'tmp').mkdir(exist_ok=True)
 run([PY,'-B',P/'kernel_gate.py'],'kernel-gate.log')
 # Per-process address space bound protects coordinator device windows.
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,resource.RLIM_INFINITY))
 for tag,compiler,host in [('host','g++','ON'),('icpx-host',IC,'ON'),('device',IC,'OFF')]:
  run(['cmake','-S',P,'-B',B/tag,'-DCMAKE_CXX_COMPILER='+compiler,'-DOWN_RT_HOST_ONLY='+host],'configure-'+tag+'.log')
  cmd=['cmake','--build',B/tag,'-j2']
  if tag=='icpx-host':cmd+=['--target','fused-fixtures','nongemv-fixtures']
  run(cmd,'build-'+tag+'.log')
 run([PY,'-B',P/'kernel_sizes.py'],'kernel-sizes.log')
 for n in ('authority-tests','owner-retirement-tests','chain-tests','queue-tests','lifetime-tests'):
  run([B/'host'/n],n+'.log')
 for mode in ('jit','borrower'):
  out=B/('failure-'+mode)
  result=subprocess.run([str(B/'host/failure-tests'),mode,str(out)],capture_output=True,text=True,timeout=10)
  r=read(out/'failure.json');assert result.returncode==1 and r['error'] in result.stderr and r['teardown']['in_flight']==0 and r['teardown']['safe_to_exit']
 result=subprocess.run([str(B/'host/failure-tests'),'parameters',str(B/'failure-parameters')],capture_output=True,text=True,timeout=10)
 assert result.returncode==0,result.stderr
 save('failure-tests.json',dict(passed=True,cases=2,parameter_cache_event_order_controls=1,normal_failure_exit=True,device_executed=False))
 canary=B/f'cpu-canary-repair-{time.time_ns()}'
 run([B/'host/own-rt-iq3','--canary' ,'--cards','2','--card','0','--memory','resident','--output',canary],'cpu-canary.log')
 save('cpu-canary.json',read(canary/'receipt.json'))
 for timing in ('token','drain','launch'):
  os.environ['PACKET23_TIMING']=timing
  for mode in ('core','parallel'):
   run([PY,'-B',P/'test.py','--binary',B/'host/own-rt-iq3','--scratch',B/f'mini-repair-{time.time_ns()}-{timing}-{mode}','--input',B/'input','--receipt',P/f'cpu-mini-{timing}-{mode}.json','--nongemv',mode],f'mini-{timing}-{mode}.log')
 os.environ.pop('PACKET23_TIMING',None)
 run([PY,'-B',P/'fixture_gate.py'],'fixture-gate.log')
 run([PY,'-B',P/'depcheck_build.py','--source',P,'--tag','sanitized'],'build-sanitizer.log')
 for mode in ('mini','integration'):run([PY,'-B',P/'sanitizer_gate.py',mode],'sanitizer-'+mode+'.log')
 resource.setrlimit(resource.RLIMIT_AS,(resource.RLIM_INFINITY,resource.RLIM_INFINITY))
 run([PY,'-B',P/'guard_tests.py'],'guard-tests.log')
 run([PY,'-B',P/'test_window.py'],'window-tests.log')
 for tag,src in [('before',P.with_name('packet21-fused')),('after',P)]:
  run(['g++','-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-I'+str(src),'-I'+str(P.parents[1]/'stage1/packet3-prep/src'),P/'submission_bench.cpp',src/'owner.cpp',src/'owner_retire.cpp','-o',B/('bench-'+tag)],'build-bench-'+tag+'.log')
  run([B/('bench-'+tag)],'bench-'+tag+'.json')
 save('submission-benchmark.json',dict(before=read(P/'bench-before.json'),after=read(P/'bench-after.json'),device_executed=False))
 run([PY,'-B',P/'stream_gate.py'],'streaming.log')
 run([PY,'-B',P/'test_mismatch.py'],'mismatch-tests.log')
 run([PY,'-B',P/'seal.py'],'seal.log')
 print('CPU PREPARATION PASS',flush=True)
if __name__=='__main__':main()
