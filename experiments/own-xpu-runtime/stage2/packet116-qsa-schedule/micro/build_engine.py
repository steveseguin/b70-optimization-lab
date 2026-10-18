"""CPU-only incremental micro build; inherited objects are read-only inputs."""
import argparse,hashlib,importlib.util,json,os,resource,shutil,subprocess,time
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[4];B=P/'build';BASE=P.parents[1]/'packet111-record-bundle'
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,v):
 Path(p).parent.mkdir(parents=True,exist_ok=True);Path(p).write_text(json.dumps(v,indent=2)+'\n')
def limits():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
 assert shutil.disk_usage('/').free>=25_000_000_000,'root free <25GB'
 size=sum(f.stat().st_size for f in P.parent.rglob('*') if f.is_file() and not f.is_symlink() and 'build' in f.parts)
 assert size<=250_000_000,('combined packet build >250MB',size)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['gnu-host','intel-host','device'],required=True);a=ap.parse_args();limits()
 spec=importlib.util.spec_from_file_location('p94_compile_turn',P.parents[1]/'packet94-hc-norm-fusion/compile_turn.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 dest=B/a.mode;dest.mkdir(parents=True,exist_ok=True);tmp=B/'tmp';tmp.mkdir(exist_ok=True);os.environ['TMPDIR']=str(tmp)
 rows=json.loads((BASE/'engine-commands.json').read_text());mode='device' if a.mode=='device' else 'gnu-host'
 cmd=next(r['command'] for r in rows if r['name']==mode+'-entry-main');cmd=cmd[:cmd.index('-o')]
 checked=BASE/'build/checked'/BASE.relative_to(ROOT)
 cmd=[x for x in cmd if not x.startswith('-I')]+['-I'+str(checked),'-I'+str(P.parent),'-I'+str(BASE/'build/checked/experiments/own-xpu-runtime/stage1/packet3-prep/src')]
 if a.mode=='intel-host':cmd[0]='/opt/intel/oneapi/compiler/2026.0/bin/icpx';cmd=[x for x in cmd if x!='-fopenmp'];cmd+=['-fdenormal-fp-math=ieee']
 sources_before={str(f.relative_to(ROOT)):sha(f) for f in [*P.glob('native-src/*'),*P.glob('native/*.hpp'),*P.parent.glob('p116*'),P/'layer_bench.cpp',P/'fixture_bytes.hpp'] if f.is_file()}
 commands=[]
 def run(c,label):
  limits();c=list(map(str,c));commands.append(dict(name=label,command=c));started=time.monotonic()
  with m.turn(),(dest/(label+'.log')).open('w') as log:subprocess.run(c,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1200)
  print(a.mode,label,'PASS',round(time.monotonic()-started,2),flush=True)
 run(cmd+['-o',dest/'layer.o','-c',P/'layer_bench.cpp'],'compile')
 run(cmd+['-o',dest/'p49d_submit.o','-c',P/'native-src/p49d_submit.cpp'],'compile-dispatch')
 run(cmd+['-o',dest/'p116_submit.o','-c',P.parent/'p116_qsa_submit.cpp'],'compile-p116')
 link=list(next(r['command'] for r in rows if r['name']==mode+'-link'))
 link=[x for x in link if not (x.endswith('.o') and ('own-rt-iq3-entry' in x or 'entry-nongemv_fixture' in x or 'entry-k2_fixture' in x))]
 for i,x in enumerate(link):
  if x.endswith('/entry-main.o'):link[i]=str(dest/'layer.o')
  elif x.endswith('/p49d_submit.o'):link[i]=str(dest/'p49d_submit.o')
 link.append(str(dest/'p116_submit.o'))
 link[link.index('-o')+1]=str(dest/'layer-bench')
 if a.mode=='intel-host':link[0]=cmd[0];link=[x for x in link if x!='-fopenmp'];link+=['-lgomp']
 objects={str(Path(x).relative_to(ROOT)):sha(x) for x in link if x.endswith('.o')}
 run(link,'link')
 parent=json.loads((BASE/'build-device-receipt.json').read_text());sources={}
 for n,h in parent['sources'].items():
  if Path(n).suffix in ('.cpp','.hpp','.inc','.o','.bf16','.tsv'):
   assert sha(ROOT/n)==h,n;sources[n]=h
 for f in [*P.glob('native-src/*'),*P.glob('native/*.hpp'),*P.parent.glob('p116*'),P/'layer_bench.cpp',P/'fixture_bytes.hpp',P/'build_engine.py']:
  if f.is_file():sources[str(f.relative_to(ROOT))]=sha(f)
 for n,h in sources_before.items():assert sha(ROOT/n)==h,('source changed during compile',n)
 for n,h in objects.items():assert sha(ROOT/n)==h,n
 limits()
 save(P/'evidence'/('build-'+a.mode+'.json'),dict(passed=True,device_executed=False,mode=a.mode,sources=sources,objects=objects,commands=commands,artifacts={str((dest/'layer-bench').relative_to(P)):sha(dest/'layer-bench')},max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss))
if __name__=='__main__':main()
