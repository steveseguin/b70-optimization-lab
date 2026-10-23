"""Reproduce a synthetic host capture fixture; never starts the runtime owner."""
from pathlib import Path
import argparse,hashlib,json,os,resource,subprocess,sys,time
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
sys.path.insert(0,str(P));sys.path.insert(1,str(ROOT/'experiments/own-xpu-runtime/ops'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def limits():
 os.sched_setaffinity(0,set(range(8,16))|set(range(24,32)))
 if os.getpriority(os.PRIO_PROCESS,0)<19:os.nice(19-os.getpriority(os.PRIO_PROCESS,0))
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
 for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='2'
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--run',action='store_true',help='run synthetic owner/capture CPU proof after build');args=ap.parse_args()
 limits();from compile_turn import turn
 spec=json.loads((P/'production-binding.json').read_text())
 for path,wanted in spec['source_sha256'].items():assert sha(ROOT/path)==wanted, path
 for path,wanted in spec['object_sha256'].items():assert sha(Path(path))==wanted, path
 assert sha(P/'host_backend.hpp')==spec['host_backend_sha256']
 (P/'build').mkdir(exist_ok=True);(P/'evidence').mkdir(exist_ok=True)
 attempt=P/'evidence'/('build-'+str(time.time_ns()));attempt.mkdir()
 # Preserve tested local source for every compile attempt, including failures.
 for name in ('capture_probe.cpp','host_backend.hpp','production-binding.json','build_engine.py'):
  (attempt/name).write_bytes((P/name).read_bytes())
 binary=P/'build/capture-probe';dependency=P/'build/dependencies.d'
 argv=['/usr/bin/g++','-std=c++20','-fopenmp','-O2','-fno-fast-math','-ffp-contract=off','-frounding-math','-DOWN_RT_HOST_ONLY','-MMD','-MF',str(dependency),str(P/'capture_probe.cpp'),*spec['object_sha256'],'-lcrypto','-o',str(binary)]
 row={'reused_host_object_sha256':spec['object_sha256'],'completion_scope':'synchronous CPU execution with existing simulated Host/LifetimeMock/MockDevice markers','schema':'packet205.host-build.v1','passed':False,'device_executed':False,'synthetic_only':True,'argv':argv,'compiler_version':subprocess.check_output(['/usr/bin/g++','--version'],text=True).splitlines()[0],'address_space_limit_bytes':4*1024**3,'cpu_affinity':sorted(os.sched_getaffinity(0))}
 with turn(),(attempt/'compile.log').open('w') as log:
  result=subprocess.run(argv,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
 row['returncode']=result.returncode
 if result.returncode==0:
  words=dependency.read_text().replace('\\\n',' ').split()[1:]
  sources={str(Path(x).resolve().relative_to(ROOT)):sha(Path(x)) for x in words if Path(x).resolve().is_relative_to(ROOT)}
  sources[str((P/'production-binding.json').relative_to(ROOT))]=sha(P/'production-binding.json')
  sources[str((P/'build_engine.py').relative_to(ROOT))]=sha(P/'build_engine.py')
  for path,wanted in spec['source_sha256'].items():assert sha(ROOT/path)==wanted, 'input changed during compile: '+path
  for path,wanted in spec['object_sha256'].items():assert sha(Path(path))==wanted, 'host object changed: '+path
  assert sha(P/'host_backend.hpp')==spec['host_backend_sha256']
  parent=json.loads((ROOT/'experiments/own-xpu-runtime/ops/packet201-window/actual-cpu-plan.json').read_text())['profile']['source_sha256']
  for path,actual in sources.items():
   if path in parent:assert actual==parent[path], 'p201 dependency differs: '+path
   elif path in spec['source_sha256']:assert actual==spec['source_sha256'][path], 'parent dependency differs: '+path
   else:assert (ROOT/path).is_relative_to(P), 'unbound compiler dependency: '+path
  row.update(passed=True,binary=str(binary.relative_to(ROOT)),binary_sha256=sha(binary),source_sha256=sources,inputs_rechecked_after_compile=True,parent_dependency_hashes_match=True)
 (attempt/'receipt.json').write_text(json.dumps(row,indent=2,sort_keys=True)+'\n')
 if result.returncode:print(str(attempt));return result.returncode
 (P/'evidence/build.json').write_text(json.dumps(row,indent=2,sort_keys=True)+'\n')
 if args.run:
  with (attempt/'differential.stdout').open('w') as out,(attempt/'differential.stderr').open('w') as err:
   result=subprocess.run([str(binary)],stdin=subprocess.DEVNULL,stdout=out,stderr=err)
  if result.returncode:print(str(attempt));return result.returncode
  data=json.loads((attempt/'differential.stdout').read_text());assert data['passed']
  for path,wanted in sources.items():assert sha(ROOT/path)==wanted, 'source changed during run: '+path
  assert sha(binary)==row['binary_sha256'], 'CPU binary changed during run'
  data.update(binary_sha256=sha(binary),source_sha256=sources,build_receipt_sha256=sha(P/'evidence/build.json'),command=[str(binary)])
  (P/'evidence/host-capture.json').write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')
 print(json.dumps({'passed':True,'build_receipt':str(P/'evidence/build.json'),'differential_ran':args.run}));return 0
if __name__=='__main__':raise SystemExit(main())
