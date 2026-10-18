"""Actual packet131b cancellation/redo census against both token-input modes."""
import gzip,json,os,resource,shutil,subprocess,time
from build_engine import P,ROOT,B,sha,save,limits,compiler_turn
ORIGINAL=P.parents[1]/'packet131b-snapshot-banks/state131.cpp'
def main():
 limits();out=B/'state-regression';out.mkdir(exist_ok=True)
 source=ORIGINAL.read_text().replace('#include "main.cpp"','#include '+json.dumps(str(P/'native-src/main.cpp')))
 old=" for(auto&[name,value]:e.lookup_ids)out<<name<<':'<<hash(value)<<'\\n';"
 assert source.count(old)==1
 source=source.replace(old,' // Obsolete host lookup staging omitted; all device/model/history bytes remain compared.')
 src=out/'state.cpp';src.write_text(source)
 prior=json.loads((P/'evidence/build.json').read_text())['commands'];commands=[];runs=[]
 for compiler,mode in [('GNU','gnu-host'),('Intel','intel-host')]:
  args=next(r['command'] for r in prior if r['name']==mode+'-entry-main');args=args[:args.index('-o')]
  args=[x for x in args if not x.startswith('-O')]+['-O1']
  obj=out/(compiler+'.o');binary=out/('fixture-'+compiler)
  link=list(next(r['command'] for r in prior if r['name']==mode+'-link'))
  link=[str(obj) if x.endswith('/entry-main.o') else x for x in link if not x.endswith('own-rt-iq3-entry.cpp.o')]
  link[link.index('-o')+1]=str(binary);link.append('-no-pie')
  for name,cmd in [('compile',[*args,'-c',str(src),'-o',str(obj)]),('link',link)]:
   with compiler_turn(),(out/(compiler+'-'+name+'.log')).open('w') as f:subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,timeout=600,check=True)
   commands.append(cmd)
  for view in ('selection','candidate'):
   row=json.loads((P/'lineage'/(view+'.json')).read_text())
   for key in ('route','recurrence','hc','experts','hc_gate','hc_norm','head','other_fusion'):row['choices'][key]='production'
   row['choices']['route']='route-exp32-rank4';row['choices']['recurrence']='rows4-shared'
   selection=out/(view+'.json');save(selection,row)
   dest=out/(compiler+'-'+view)
   if dest.exists():dest.rename(out/(dest.name+'-incomplete-'+str(time.time_ns())))
   dest.mkdir();cmd=[str(binary),str(selection),sha(selection),str(dest),view]
   log=P/'evidence'/('state-'+compiler+'-'+view+'.log');start=time.monotonic()
   with log.open('w') as f:subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,timeout=1200,check=True,env=dict(os.environ,OMP_NUM_THREADS='2',LD_LIBRARY_PATH='/opt/intel/oneapi/compiler/2026.0/lib'))
   result=json.loads((dest/'result.json').read_text());assert result['passed'] and result['cases']==491 and result['position_classes']==43
   raw=(dest/'cases.txt').read_bytes();archive=P/'evidence'/('state-'+compiler+'-'+view+'.txt.gz');archive.write_bytes(gzip.compress(raw,mtime=0));assert gzip.decompress(archive.read_bytes())==raw
   runs.append(dict(**result,compiler=compiler,token_input=row['choices']['token_input'],seconds=time.monotonic()-start,command=cmd,archive=str(archive.relative_to(ROOT)),archive_sha256=sha(archive),binary_sha256=sha(binary)))
   shutil.rmtree(dest);print(compiler,view,'491 state cases PASS',flush=True)
 assert len({r['canonical_sha256'] for r in runs})==1
 files=[P/'state_regression.py',ORIGINAL,src,*out.glob('*.json'),*out.glob('fixture-*')]
 save(P/'evidence/state-regression.json',dict(passed=True,device_executed=False,runs=runs,commands=commands,cpu_workers=1,source_projection='Only include target and obsolete lookup_ids staging serialization changed; device/model/history comparison intact',sources={str(f.relative_to(ROOT)):sha(f) for f in files},max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss))
 limits()
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
