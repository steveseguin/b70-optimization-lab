"""Actual full-size initialization and prepared sequence; numerical CPU backend."""
import ast,gzip,json,os,resource,subprocess,sys
from pathlib import Path
from build_engine import P,ROOT,BASE,B,sha,save,limits
sys.path.insert(0,str(P.parents[1]/'ops'))
from compile_turn import turn

def main():
 limits();S=B/'full-shape';S.mkdir(exist_ok=True)
 prior=json.loads((P/'parent-commands.snapshot.json').read_text())
 base=next(r['command'] for r in prior if r['name']=='gnu-host-entry-main');base=base[:base.index('-o')]
 mirror=Path(next(x[2:] for x in base if x.startswith('-I') and '/checked/' in x))
 parent=BASE/'full_shape.py';text=parent.read_text();tree=ast.parse(text)
 code='\n\n'.join(ast.get_source_segment(text,n) for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('replace','body','generate'))
 code=code.replace("mirror=B/'checked'/P.relative_to(ROOT)",'mirror=Path('+repr(str(mirror))+')').replace("t=(mirror/'main.cpp').read_text()","t=(B/'cow/main.cpp').read_text()")
 scope=dict(P=P,ROOT=ROOT,BASE=BASE,B=B,S=S,json=json,Path=Path);exec(compile(code,str(parent),'exec'),scope);scope['generate']()
 entry=S/'entry.cpp';text=entry.read_text();marker=' auto count=[](const std::string& key)'
 probe=r'''
 if(a.rank==0){
  size_t mutable_bytes=0,kernels=0,sites=0;std::set<int>layers;std::set<std::string>classes;
  for(const auto&[id,owner]:e->allocations){const auto&r=e->dev(owner.first).arena.row(id);if(owner.first==0&&r.live&&r.memory==Memory::device&&r.category!=Category::weights)mutable_bytes+=r.bytes;}
  require(mutable_bytes<=1500ull*1024*1024,"probe snapshot bound");
  std::ofstream plan(a.output/"probe-plan.json");plan<<"{\"mutable_bytes\":"<<mutable_bytes<<",\"sites\":[";bool comma=false;
  for(size_t i=0;i<e->p.launches.size();++i){const auto&l=e->p.launches[i];const auto&s=e->issue_sites[i];if(!l.label.starts_with("blk."))continue;
   ++sites;kernels+=s.commands.size();layers.insert(s.layer);classes.insert(e->class_names.at(s.cls));
   plan<<(comma?",":"")<<"{\"site\":"<<i<<",\"label\":"<<ownrt::quote(l.label)<<",\"class\":"<<ownrt::quote(e->class_names.at(s.cls))<<",\"kernel_count\":"<<s.commands.size()<<"}";comma=true;
  }
  plan<<"],\"kernels\":"<<kernels<<",\"layers\":"<<layers.size()<<"}\n";plan.close();
  require(layers.size()==24&&*layers.begin()==0&&*layers.rbegin()==23&&kernels>400,"complete target half");
  e->allocate(0,"p141-evict",256ull*1024*1024,Category::scratch,Lifetime::transaction);
  e->allocate(0,"p141-touch-sink",256*1024,Category::scratch,Lifetime::transaction);
 }
'''
 assert marker in text;entry.write_text(text.replace(marker,probe+marker))
 base=[x for x in base if not x.startswith('-O')]+['-O0','-I'+str(P)]
 compile_cmd=[*base,'-c',str(entry),'-o',str(S/'entry.o')]
 link=list(next(r['command'] for r in prior if r['name']=='gnu-host-link'))
 link=[x for x in link if not x.endswith('own-rt-iq3-entry.cpp.o')]
 link=[str(S/'entry.o') if x.endswith('/entry-main.o') else x for x in link];link[link.index('-o')+1]=str(S/'fixture')
 for name,cmd in [('compile',compile_cmd),('link',link)]:
  with turn(),(S/(name+'.log')).open('w') as log:subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=600)
 from memory_gate import check
 ledger=json.loads((P/'memory-plan.json').read_text());runs=[]
 for rank in (0,1):
  dest=S/('rank'+str(rank));dest.mkdir(exist_ok=True)
  cmd=[str(S/'fixture'),str(P/'selection.json'),sha(P/'selection.json'),str(rank),str(dest),'positive','1','0']
  with (P/'evidence'/('startup-rank'+str(rank)+'.log')).open('w') as log:subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
  census=json.loads((dest/'census.json').read_text());gate=check(census,ledger,rank,True,4096,1,0)
  if rank==0:
   (P/'probe-plan.json').write_bytes((dest/'probe-plan.json').read_bytes())
   assert sum(a['bytes'] for a in census['allocations'] if a['label'].startswith('card0:p141-'))==268697600
  target=P/'evidence'/('startup-rank'+str(rank)+'.json.gz');target.write_bytes(gzip.compress(json.dumps(census).encode(),mtime=0))
  runs.append(dict(rank=rank,passed=True,memory=gate,census_sha256=sha(target)));print('rank',rank,'startup PASS',flush=True)
 sources={str(f.relative_to(ROOT)):sha(f) for f in [parent,P/'full_shape.py',P/'memory-plan.json',P/'selection.json',entry,S/'main.cpp',S/'mtp.hpp']}
 save(P/'evidence/full-shape.json',dict(passed=True,device_executed=False,model_payload_read=False,runs=runs,sources=sources))
 limits()
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
