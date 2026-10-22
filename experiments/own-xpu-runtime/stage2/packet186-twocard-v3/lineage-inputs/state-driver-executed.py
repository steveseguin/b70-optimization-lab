"""GNU and Intel host Engine byte equality; serial, synthetic miniature weights."""
import gzip,json,resource,subprocess,os,sys
from concurrent.futures import ThreadPoolExecutor
from p153_v5_build_engine import P,LOCAL,ROOT,B,CHECKED,sha,save,limits,run

def main():
 limits();prior=json.loads((P/'engine-commands.json').read_text());out=B/'state';out.mkdir(exist_ok=True)
 args=list(next(r['command'] for r in prior if r['name']=='gnu-host-entry-main'));args=args[1:args.index('-o')];i=args.index('-c');del args[i:i+2]
 rows=[];jobs=[]
 for mode in ('production','static'):
  row=json.loads((P/'lineage'/mode/'selection.json').read_text())
  for key in ('route','recurrence','hc','experts','hc_gate','hc_norm','head','other_fusion'):row['choices'][key]='production'
  row['choices'].update(route='route-exp32-rank4',recurrence='rows4-shared')
  save(out/(mode+'.json'),row)
 for compiler,cxx in [('GNU','/usr/bin/g++'),('Intel','/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
  obj=out/(compiler+'.o');binary=out/('fixture-'+compiler)
  if not binary.exists():run([cxx,*args,'-c',P/'native/state_bytes.cpp','-o',obj],'state-'+compiler+'-compile')
  link=list(next(r['command'] for r in prior if r['name']=='gnu-host-link'))
  link=[str(obj) if x.endswith('/entry-main.o') else x for x in link if not x.endswith('own-rt-iq3-entry.cpp.o')]
  link[0]=cxx;link[link.index('-o')+1]=str(binary);link+=['-no-pie','-Wl,-rpath,/opt/intel/oneapi/compiler/2026.0/lib']
  if not binary.exists():run(link,'state-'+compiler+'-link')
  jobs.extend((compiler,repeat,mode,binary) for repeat in (1,2) for mode in ('production','static'))
 def execute(job):
  compiler,repeat,mode,binary=job
  selection=out/(mode+'.json');dest=out/f'{compiler}-{repeat}-{mode}';
  if dest.exists():dest.rename(dest.with_name(dest.name+'-interrupted-'+str(__import__('time').time_ns())))
  dest.mkdir(exist_ok=False)
  env=dict(os.environ,OMP_NUM_THREADS='2',LD_LIBRARY_PATH='/opt/intel/oneapi/compiler/2026.0/lib')
  log=P/'evidence'/f'state-{compiler}-{repeat}-{mode}.log'
  with log.open('w') as stream:r=subprocess.run([sys.executable,'-B',str(P/'state_gate.py'),'--worker',str(binary),str(selection),sha(selection),str(dest),mode,'sequence-only'],env=env,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,timeout=900)
  assert r.returncode==0,log.read_text()[-6000:]
  result=json.loads((dest/'result.json').read_text());raw=dest/'cases.txt';archive=P/'evidence'/f'state-{compiler}-{repeat}-{mode}.txt.gz';archive.write_bytes(gzip.compress(raw.read_bytes(),mtime=0))
  result.update(compiler=compiler,repeat=repeat,mode=mode,transcript_sha256=sha(archive),snapshot=json.loads((dest/'speculative-snapshot.json').read_text()))
  print(compiler,repeat,mode,'PASS',flush=True);return result
 with ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(execute,jobs))
 assert len({r['canonical_sha256'] for r in rows})==1,'compiler/repeat/mode state bytes differ'
 save(P/'evidence/state.json',dict(passed=True,device_executed=False,model_read=False,full_shape_read=False,runs=rows,scope='98-step mixed sequence plus three corruption negatives; real extents separately checked',six_rotation_states=True,immutable_table_reset_checked=True,workers=2,worker_limit_bytes=1280*1024**2,peak_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,sources={str(f.relative_to(ROOT)):sha(f) for f in (P/'state_gate.py',P/'native/state_bytes.cpp',CHECKED/'strict_snapshot.hpp',CHECKED/'request_reset.hpp',P/'native-src/main.cpp')}))
if __name__=='__main__':
 if '--worker' in sys.argv:
  resource.setrlimit(resource.RLIMIT_AS,(1280*1024**2,1280*1024**2));os.execv(sys.argv[2],sys.argv[2:])
 else:resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
