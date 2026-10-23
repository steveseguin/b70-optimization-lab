"""Build/run metadata-only CPU bindings fixture; no native runtime is linked."""
from pathlib import Path
import hashlib,json,os,resource,subprocess,sys,time
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 os.sched_setaffinity(0,set(range(8,16))|set(range(24,32)))
 if os.getpriority(os.PRIO_PROCESS,0)<19:os.nice(19-os.getpriority(os.PRIO_PROCESS,0))
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
 for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='2'
 sys.path.insert(0,str(ROOT/'experiments/own-xpu-runtime/ops'))
 from compile_turn import turn
 sources=[P/'row_bindings.hpp',P/'binding_probe.cpp',P/'build_probe.py',P.parent/'packet202-prefill-chunk-prep/chunk_plan.hpp',ROOT/'experiments/own-xpu-runtime/ops/compile_turn.py']
 pins={str(p.relative_to(ROOT)):sha(p) for p in sources}
 (P/'build').mkdir(exist_ok=True)
 attempt=P/'evidence'/('bindings-'+str(time.time_ns()));attempt.mkdir(parents=True)
 for p in sources[:3]:(attempt/p.name).write_bytes(p.read_bytes())
 binary=P/'build/binding-probe'
 argv=['/usr/bin/g++','-std=c++20','-O2','-Wall','-Wextra','-Werror',str(P/'binding_probe.cpp'),'-o',str(binary)]
 receipt={'schema':'packet204.metadata-bindings.v1','passed':False,'native_executed':False,'device_executed':False,'source_sha256':pins,'compile_argv':argv,'cpu_affinity':sorted(os.sched_getaffinity(0)),'address_space_limit_bytes':4*1024**3}
 with turn(),(attempt/'compile.log').open('w') as log:
  result=subprocess.run(argv,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
 receipt['compile_returncode']=result.returncode
 if result.returncode==0:
  receipt['binary_sha256']=sha(binary);receipt['binary']=str(binary.relative_to(ROOT))
  result=subprocess.run([str(binary),'--self-test'],stdin=subprocess.DEVNULL,capture_output=True,text=True)
  (attempt/'stdout.json').write_text(result.stdout);(attempt/'stderr.log').write_text(result.stderr)
  receipt['test_returncode']=result.returncode
  if result.returncode==0:
   data=json.loads(result.stdout);receipt.update(passed=data['passed'],checks=data['checks'])
 for path,want in pins.items():
  if sha(ROOT/path)!=want:receipt.update(passed=False,source_changed=path)
 (attempt/'receipt.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
 if receipt['passed']:(P/'evidence/binding-cpu.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
 print(json.dumps({'passed':receipt['passed'],'attempt':str(attempt)}))
 return 0 if receipt['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
