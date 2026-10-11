#!/usr/bin/env python3
"""CPU-only build and gates. Never executes a device binary; <=2 compiler jobs."""
import os,subprocess,resource,struct,json,time
from pathlib import Path
P=Path(__file__).resolve().parent;B=P/'build';PY='/home/steve/.venvs/vllm-xpu/bin/python';IC='/opt/intel/oneapi/compiler/2026.0/bin/icpx'
def run(args,log):
 print(log,flush=True)
 with (P/log).open('w') as f:subprocess.run(list(map(str,args)),check=True,stdout=f,stderr=subprocess.STDOUT)
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
 assert 'idle' in subprocess.check_output(['ionice','-p',str(os.getpid())],text=True)
 os.environ['OPENBLAS_NUM_THREADS']='2';B.mkdir(exist_ok=True);(B/'tmp').mkdir(exist_ok=True);os.environ['TMPDIR']=str(B/'tmp')
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,resource.RLIM_INFINITY))
 if not (B/'input').exists():run([PY,'-B',P/'prepare.py','--output',B/'input'],'prepare.log')
 if not (B/'fusion-fixtures').exists():run([PY,'-B',P/'prototype/fixtures.py','--output',B/'fusion-fixtures'],'prepare-fixtures.log')
 values=struct.unpack('<262144H',(P/'rope.bf16').read_bytes());(B/'fusion-rope.hpp').write_text('#pragma once\nnamespace rope_constants { inline constexpr int positions=4096; inline constexpr uint16_t table[]={'+','.join(map(str,values))+'};}\n')
 run([PY,'-B',P/'k2.py','prepare','--output',B/'k2-input'],'k2-prepare.log')
 run([PY,'-B',P/'kernel_gate.py'],'kernel-gate.log')
 for tag,compiler,host in [('host','g++','ON'),('icpx-host',IC,'ON'),('device',IC,'OFF')]:
  run(['cmake','-S',P,'-B',B/tag,'-DCMAKE_CXX_COMPILER='+compiler,'-DOWN_RT_HOST_ONLY='+host],'configure-'+tag+'.log')
  cmd=['cmake','--build',B/tag,'-j2']
  if tag=='icpx-host':cmd+=['--target','fused-fixtures','nongemv-fixtures']
  run(cmd,'build-'+tag+'.log')
 run([B/'host/k2-fixtures','--validate-only','--input',B/'k2-input','--output',B/('k2-manifest-'+str(time.time_ns()))],'k2-manifest.log')
 for script in ['kernel_sizes.py','entry_smoke_test.py'] :run([PY,'-B',P/script],script+'.log')
 run([PY,'-B',P/'cpu_gates.py','cheap'],'cpu-gates.log')
 run([PY,'-B',P/'fixture_gate.py'],'fixture-gate.log')
 run([PY,'-B',P/'real_eight_gate.py'],'real-eight.log')
 # ASan's shadow consumes virtual address space, not resident memory. The tiny
 # fixed mini fixture uses <1GiB RSS. Do not apply the8GiB VA cap to that runtime.
 resource.setrlimit(resource.RLIMIT_AS,(resource.RLIM_INFINITY,resource.RLIM_INFINITY))
 run(['cmake','-S',P,'-B',B/'asan','-DCMAKE_CXX_COMPILER=g++','-DOWN_RT_HOST_ONLY=ON','-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined,float-cast-overflow -fno-omit-frame-pointer','-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined,float-cast-overflow'],'configure-asan.log')
 run(['cmake','--build',B/'asan','-j2','--target','own-rt-iq3'],'build-asan.log')
 run([PY,'-B',P/'cpu_gates.py','sanitizer'],'sanitizer-mini.log')
 for script in ['guard_tests.py','test_window.py','k2_test.py','reuse.py','seal.py','cleanup.py']:run([PY,'-B',P/script],script+'.log')
 print('CPU gates complete; coordinator device gates remain pending',flush=True)
if __name__=='__main__':main()
