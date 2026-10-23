"""Build and optionally run only a bounded synthetic HOST_ONLY cache fixture."""
from pathlib import Path
import argparse,hashlib,json,os,resource,shlex,shutil,subprocess,sys,time
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
SOURCES=('cache_probe.cpp','production-binding.json','build_engine.py')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def limits():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):assert os.environ.get(name)=='2'
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
 assert shutil.disk_usage(ROOT).free-256*1024**2>=27_000_000_000,'compile/write floor'
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run-host-only',action='store_true');a=ap.parse_args();limits()
 spec=json.loads((P/'production-binding.json').read_text())
 for path,want in spec['source_sha256'].items():assert sha(ROOT/path)==want,path
 for path,want in spec['object_sha256'].items():assert sha(path)==want,path
 binary=P/'build/cache-probe';dependency=P/'build/dependencies.d';binary.parent.mkdir(exist_ok=True)
 attempt=P/'evidence'/('build-'+str(time.time_ns()));attempt.mkdir(parents=True)
 before={str((P/n).relative_to(ROOT)):sha(P/n) for n in SOURCES}
 for n in SOURCES:(attempt/n).write_bytes((P/n).read_bytes())
 argv=['/usr/bin/g++','-std=c++20','-fopenmp','-O2','-fno-fast-math','-ffp-contract=off','-frounding-math','-DOWN_RT_HOST_ONLY','-MMD','-MF',str(dependency),str(P/'cache_probe.cpp'),*spec['object_sha256'],'-lcrypto','-o',str(binary)]
 row={'schema':'packet210.host-build.v1','passed':False,'device_executed':False,'model_executed':False,'synthetic_only':True,'reused_host_object_sha256':spec['object_sha256'],'argv':argv,'completion_scope':'real CPU byte operations; inherited simulated Host/LifetimeMock markers','compiler_version':subprocess.check_output(['/usr/bin/g++','--version'],text=True).splitlines()[0],'address_space_limit_bytes':4*1024**3,'cpu_affinity':sorted(os.sched_getaffinity(0))}
 sys.path.insert(0,str(ROOT/'experiments/own-xpu-runtime/ops'));from compile_turn import turn
 try:
  with turn(),(attempt/'compile.log').open('w') as log:
   cp=subprocess.run(argv,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=300)
  row['returncode']=cp.returncode
  if cp.returncode:raise RuntimeError('CPU compilation failed')
  paths=[Path(x).resolve() for x in shlex.split(dependency.read_text().replace('\\\n',' ').split(':',1)[1])]
  parent=json.loads((ROOT/'experiments/own-xpu-runtime/ops/packet201-window/actual-cpu-plan.json').read_text())['profile']['source_sha256'];sources=dict(before)
  for path in paths:
   assert path.is_relative_to(ROOT),str(path)
   rel=str(path.relative_to(ROOT));digest=sha(path)
   if not path.is_relative_to(P):assert digest==spec['source_sha256'].get(rel,parent.get(rel)),'unbound dependency '+rel
   sources[rel]=digest
  for path,want in {**before,**spec['source_sha256']}.items():assert sha(ROOT/path)==want,path
  for path,want in spec['object_sha256'].items():assert sha(path)==want,path
  row.update(passed=True,binary=str(binary.relative_to(ROOT)),binary_sha256=sha(binary),source_sha256=sources,inputs_rechecked_after_compile=True,parent_dependency_hashes_match=True)
 except BaseException as ex:row['error']=f'{type(ex).__name__}: {ex}'
 (attempt/'receipt.json').write_text(json.dumps(row,indent=2,sort_keys=True)+'\n')
 if not row['passed']:print(json.dumps({'passed':False,'attempt':str(attempt),'error':row.get('error')}));return 1
 (P/'evidence/build.json').write_text(json.dumps(row,indent=2,sort_keys=True)+'\n')
 if a.run_host_only:
  with (attempt/'proof.stdout').open('w') as out,(attempt/'proof.stderr').open('w') as err:
   cp=subprocess.run([str(binary)],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=out,stderr=err,timeout=60)
  (attempt/'execution.json').write_text(json.dumps({'returncode':cp.returncode,'binary_sha256':sha(binary),'device_executed':False})+'\n')
  if cp.returncode:print(json.dumps({'passed':False,'attempt':str(attempt),'returncode':cp.returncode}));return 1
  data=json.loads((attempt/'proof.stdout').read_text());assert data['passed']
  for path,want in sources.items():assert sha(ROOT/path)==want,path
  for path,want in spec['object_sha256'].items():assert sha(path)==want,path
  assert sha(binary)==row['binary_sha256']
  data.update(binary_sha256=sha(binary),source_sha256=sources,build_receipt_sha256=sha(P/'evidence/build.json'),command=[str(binary)])
  (P/'evidence/host-cache.json').write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')
 print(json.dumps({'passed':True,'attempt':str(attempt),'host_executed':a.run_host_only}));return 0
if __name__=='__main__':raise SystemExit(main())
