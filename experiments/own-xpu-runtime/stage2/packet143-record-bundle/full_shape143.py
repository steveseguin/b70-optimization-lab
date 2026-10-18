"""Production-sized initialization with numerical device storage and no model reads."""
import json,subprocess,resource,os,shutil,gzip,hashlib
from compositions import *
from compile_turn import turn
import full_shape as parent
from memory143 import plan
from memory_gate import check
S=P/'build/full-shape143'
def main():
 assert not __import__('subprocess').check_output(['systemctl','--user','list-units','--state=running','--plain','--no-legend','packet58-onecard-*'],text=True).strip(),'one-card timing hold'
 pause=ROOT/'experiments/own-xpu-runtime/ops/lane-queue/PAUSE-B'
 assert not pause.exists() or 'one-card' not in pause.read_text().lower(),'one-card timing hold'
 from build_engine import limits
 limits();parent.S=S;generated=parent.generate()
 f=S/'main.cpp';t=f.read_text().replace('if(w.mini)data=w.synthetic.at(t.name).data();','if(true)data=nullptr;');f.write_text(t)
 f=S/'mtp.hpp';m=f.read_text();m=parent.body(m,' void initialize_projection()', '\n embedding_staging=e.allocate(0,"draft:embedding-staging",p.g.h*2,Category::pinned_slab,Lifetime::transfer,Memory::pinned);std::memset(e.dev(0).arena.row(embedding_staging).pointer,0,p.g.h*2);projection_bytes=p137::table_bytes;\n');f.write_text(m)
 cmds=read(P/'v5/engine-commands.json');base=list(next(r['command'] for r in cmds if r['name']=='gnu-host-entry-main'));base=base[:base.index('-c')];base=[x for x in base if not x.startswith('-O')]+['-O0','-I'+str(P),'-c',str(S/'entry.cpp'),'-o',str(S/'entry.o')]
 link=list(next(r['command'] for r in cmds if r['name']=='gnu-host-link'));link=[x for x in link if not x.endswith('/entry-main.o') and not x.endswith('own-rt-iq3-entry.cpp.o')];link.insert(link.index('-o'),str(S/'entry.o'));link[link.index('-o')+1]=str(S/'fixture')
 for label,cmd in [('compile',base),('link',link)]:
  with turn(),(S/(label+'.log')).open('w') as f:subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,timeout=600,check=True)
 report=dict(passed=False,device_executed=False,model_payload_read=False,runs=[],commands=[base,link],sources={})
 from launch_env143 import environment
 for s in all_compositions():
  sel=S/'selection.json';save(sel,native(s))
  for rank in (0,1):
   out=S/'scratch';out.mkdir(exist_ok=False)
   cp=subprocess.run([str(S/'fixture'),str(sel),sha(sel),str(rank),str(out),'positive','1','0'],capture_output=True,text=True,stdin=subprocess.DEVNULL,env=environment(),timeout=120)
   if cp.returncode:raise AssertionError(key(s)+str(rank)+': '+cp.stderr)
   census=read(out/'census.json');gate=check(census,plan(s),rank,mtp=True,context=4096,draft_rank=1,target_split=0)
   artifacts={}
   for f in out.iterdir():
    if f.is_file():
     dest=P/'evidence'/('shape143-'+key(s)+'-'+str(rank)+'-'+f.name+'.gz');dest.write_bytes(gzip.compress(f.read_bytes(),mtime=0));artifacts[str(dest.relative_to(ROOT))]=sha(dest)
   report['runs'].append(dict(composition=s,rank=rank,memory=gate,artifacts=artifacts));shutil.rmtree(out)
  print(key(s),'full-shape PASS',flush=True)
 report.update(passed=True,binary_sha256=sha(S/'fixture'),sources={str(f.relative_to(ROOT)):sha(f) for f in [Path(__file__),*generated]})
 save(P/'evidence/full-shape143.json',report)
 # Retain source, command, binary and object hash; this generated object is reproducible.
 save(S/'object-retention.json',dict(path=str(S/'entry.o'),sha256=sha(S/'entry.o'),reason='300 MB build budget; rebuild with recorded command'))
 (S/'entry.o').unlink()
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
