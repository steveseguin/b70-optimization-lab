"""CPU-only serial builds; frozen packet97 objects are read-only inputs."""
import argparse,hashlib,json,os,resource,subprocess,shutil,shlex
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];B=P/'build';BASE=P.parent/'packet97-record-bundle'
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,v):Path(p).write_text(json.dumps(v,indent=2)+'\n')
from build_engine import limits

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['gnu-host','intel-host','device'],required=True);a=ap.parse_args();limits()
 from compile_turn import turn
 B.mkdir(exist_ok=True)
 if not (B/'fusion-rope.hpp').exists():os.link(BASE/'build/fusion-rope.hpp',B/'fusion-rope.hpp')
 from mirror import prepare
 source=prepare(P/'layer_bench.cpp');(B/'tmp').mkdir(exist_ok=True);os.environ['TMPDIR']=str(B/'tmp')
 rows=json.loads((BASE/'engine-commands.json').read_text());mode='device' if a.mode=='device' else 'gnu-host'
 cmd=next(r['command'] for r in rows if r['name']==mode+'-entry-main');cmd=cmd[:cmd.index('-o')]
 cmd=[x.replace(str(BASE),str(P)) if x.startswith('-I') else x for x in cmd]
 if a.mode=='intel-host':cmd[0]='/opt/intel/oneapi/compiler/2026.0/bin/icpx';cmd=[x for x in cmd if x!='-fopenmp'];cmd+=['-fdenormal-fp-math=ieee']
 dest=B/a.mode;dest.mkdir(exist_ok=True);commands=[]
 sources={}
 def run(c,label):
  c=list(map(str,c));commands.append(c)
  with turn(),(dest/(label+'.log')).open('w') as log:
   if label=='compile':
    prepare(P/'layer_bench.cpp')
   subprocess.run(c,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1200)
   if label=='compile':
    for name in shlex.split((dest/'layer.d').read_text().replace('\\\n',' ').split(':',1)[1]):
     x=Path(name).resolve()
     if x.is_relative_to(ROOT):
      sources[str(x.relative_to(ROOT))]=sha(x)
      if x.is_relative_to(B/'checked'):
       original=ROOT/x.relative_to(B/'checked');sources[str(original.relative_to(ROOT))]=sha(original)

  print(a.mode,label,'PASS',flush=True)
 # Re-link all parent inputs, at their original paths, to prove the frozen object
 # bytes still reproduce the parent executable. Remove the temporary proof only
 # after retaining its digest; no frozen output is written.
 link=list(next(r['command'] for r in rows if r['name']==mode+'-link'))
 objects={str(Path(x).relative_to(ROOT)):sha(x) for x in link if x.endswith('.o')}
 proof=list(link);proof[proof.index('-o')+1]=str(dest/'parent-proof')
 run(proof,'parent-proof');assert sha(dest/'parent-proof')==sha(BASE/'build'/mode/'own-rt-iq3'),'parent relink identity';proof_hash=sha(dest/'parent-proof');(dest/'parent-proof').unlink()
 run(cmd+['-MMD','-MF',dest/'layer.d','-o',dest/'layer.o','-c',source],'compile')
 link=[x for x in link if not (x.endswith('.o') and ('own-rt-iq3-entry' in x or 'entry-nongemv_fixture' in x or 'entry-k2_fixture' in x))]
 link=[str(dest/'layer.o') if x==str(BASE/'build'/mode/'entry-main.o') else x for x in link]
 link[link.index('-o')+1]=str(dest/'layer-bench')
 if a.mode=='intel-host':link[0]=cmd[0];link=[x for x in link if x!='-fopenmp'];link+=['-lgomp']
 run(link,'link')
 for n,h in sources.items():assert sha(ROOT/n)==h,n
 for n,h in objects.items():assert sha(ROOT/n)==h,n
 size=sum(x.stat().st_size for x in B.rglob('*') if x.is_file());assert size<=250_000_000,size
 save(P/'evidence'/('build-'+a.mode+'.json'),dict(passed=True,device_executed=False,mode=a.mode,sources=sources,objects=objects,parent_relink_sha256=proof_hash,commands=commands,artifacts={str((dest/'layer-bench').relative_to(P)):sha(dest/'layer-bench')},build_bytes=size,max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss))
if __name__=='__main__':main()
