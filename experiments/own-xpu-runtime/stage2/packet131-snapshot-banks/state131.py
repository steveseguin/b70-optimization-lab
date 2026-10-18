"""Compile the actual snapshot/target fixture with GNU and Intel; CPU only."""
import gzip,json,subprocess,shutil,resource,os,sys,time
from concurrent.futures import ThreadPoolExecutor
from build131 import P,ROOT,B,sha,save,cpu_main,limits,run
def main():
 prior=json.loads((P/'engine-commands.json').read_text());base=next(r['command'] for r in prior if r['name']=='gnu-host-entry-main');base=base[:base.index('-c')]
 base=[a for a in base[1:] if not a.startswith('-O')]+['-O1']
 out=B/'state131';out.mkdir(exist_ok=True);commands=[];jobs=[]
 # Include the exact checked Engine source, rather than bypassing the mirror.
 source=out/'state.cpp';source.write_text((P/'state131.cpp').read_text().replace('#include "main.cpp"','#include '+json.dumps(str(B/'checked'/P.relative_to(ROOT)/'main.cpp'))))
 for compiler,cxx in [('GNU','/usr/bin/g++'),('Intel','/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
  obj=out/(compiler+'.o');binary=out/('fixture-'+compiler)
  commands.append(run([cxx,*base,'-c',source,'-o',obj],'state-'+compiler+'-compile'))
  link=list(next(r['command'] for r in prior if r['name']=='gnu-host-link'));link=[str(obj) if a.endswith('/entry-main.o') else a for a in link if not a.endswith('own-rt-iq3-entry.cpp.o')];link[link.index('-o')+1]=str(binary)
  link[0]=cxx;link.append('-no-pie')  # icpx host objects are not PIE by default.
  commands.append(run(link,'state-'+compiler+'-link'))
  jobs.extend((compiler,repeat,view,binary) for repeat in (1,2) for view in ('control','candidate'))
 for view in ('control','candidate'):
  selection=P/'selections'/view/'mini.json';row=json.loads((selection.parent/'selection.json').read_text())
  # Production-only kernels reject synthetic miniature geometry.
  for key in ('route','recurrence','hc','experts','hc_gate','hc_norm','head','other_fusion'):row['choices'][key]='production'
  row['choices']['route']='route-exp32-rank4';row['choices']['recurrence']='rows4-shared';save(selection,row)
 def execute(job):
  compiler,repeat,view,binary=job;selection=P/'selections'/view/'mini.json'
  receipt=P/'evidence'/f'state-{compiler}-{repeat}-{view}.json'
  run_sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'state131.py',P/'state131.cpp',P/'strict_snapshot.hpp',P/'rank.hpp',P/'main.cpp',P/'request_reset.hpp',selection,binary]}
  try:
   prior_run=json.loads(receipt.read_text());assert prior_run['passed'] and prior_run['sources']==run_sources
   assert sha(ROOT/prior_run['artifact'])==prior_run['artifact_sha256']
  except (OSError,KeyError,AssertionError):pass
  else:print(compiler,repeat,view,'unchanged saved state receipt verified',flush=True);return prior_run
  dest=out/f'{compiler}-{repeat}-{view}'
  if dest.exists():dest.rename(out/(dest.name+'-incomplete-'+str(time.time_ns())))
  dest.mkdir();cmd=[str(binary),str(selection),sha(selection),str(dest),view]
  log=P/'evidence'/f'state-{compiler}-{repeat}-{view}.log'
  launch=['/usr/bin/env','OMP_NUM_THREADS=2','LD_LIBRARY_PATH=/opt/intel/oneapi/compiler/2026.0/lib',sys.executable,'-B',str(P/'state131.py'),'--cpu-worker',*cmd]
  with log.open('w') as stream:cp=subprocess.run(launch,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,timeout=1200)
  assert cp.returncode==0,str(log)
  result=json.loads((dest/'result.json').read_text());raw=dest/'cases.txt';archive=P/'evidence'/f'state-{compiler}-{repeat}-{view}.txt.gz';archive.write_bytes(gzip.compress(raw.read_bytes(),mtime=0))
  result.update(compiler=compiler,repeat=repeat,view=view,command=launch,artifact=str(archive.relative_to(ROOT)),artifact_sha256=sha(archive),snapshot=json.loads((dest/'speculative-snapshot.json').read_text()),sources=run_sources)
  save(receipt,result)
  shutil.rmtree(dest);print(compiler,repeat,view,'state PASS',flush=True);return result
 # No compilers run alongside this phase. Four CPU-only children each have a
 # 1.5-GiB address-space ceiling: at most 6 GiB plus the small Python parent.
 with ThreadPoolExecutor(max_workers=4) as pool:runs=list(pool.map(execute,jobs))
 assert len({r['canonical_sha256'] for r in runs})==1,'cross view/compiler/repeat bytes differ'
 sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'state131.cpp',P/'state131.py',P/'strict_snapshot.hpp',P/'rank.hpp',P/'main.cpp',P/'request_reset.hpp',*(P/'selections'/v/n for v in ('control','candidate') for n in ('selection.json','mini.json'))]}
 save(P/'evidence/state131.json',dict(passed=True,device_executed=False,runs=runs,sources=sources,commands=commands,cpu_workers=4,worker_address_space_limit_bytes=1536*1024**2,max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss))
 limits()
if __name__=='__main__':
 if '--cpu-worker' in sys.argv:
  resource.setrlimit(resource.RLIMIT_AS,(1536*1024**2,1536*1024**2));limits();os.execv(sys.argv[2],sys.argv[2:])
 else:cpu_main();main()
