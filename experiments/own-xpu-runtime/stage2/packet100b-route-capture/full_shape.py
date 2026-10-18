"""Real full-size startup and capture extents; payload/backend are CPU mocks."""
import ast,gzip,json,os,subprocess,sys
from build_engine import P,ROOT,BASE,B,sha,save,limits
sys.path.insert(0,str(P.parent/'packet94-hc-norm-fusion'))
from compile_turn import turn

def main():
 limits();S=B/'full-shape';S.mkdir(exist_ok=True)
 parent=BASE/'full_shape.py';tree=ast.parse(parent.read_text())
 parts=[ast.get_source_segment(parent.read_text(),n) for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('replace','body','generate')]
 code='\n\n'.join(parts)
 code=code.replace("mirror=B/'checked'/P.relative_to(ROOT)","mirror=BASE/'build/checked'/BASE.relative_to(ROOT)")
 code=code.replace("t=(mirror/'main.cpp').read_text()","t=(B/'cow/main.cpp').read_text()")
 scope=dict(P=P,ROOT=ROOT,BASE=BASE,B=B,S=S,json=json)
 exec(compile(code,str(parent),'exec'),scope)
 for leaf in ('rope.bf16','mtp-manifest.tsv'):
  dest=P/leaf
  if not dest.exists():dest.write_bytes((BASE/leaf).read_bytes())
 scope['generate']()
 entry=S/'entry.cpp';text=entry.read_text()
 marker=' auto count=[](const std::string& key)'
 assert marker in text
 probe='''
 // Real plan route ownership/extent and all 64 slot offsets, no host readback.
 unsigned route_sites=0;
 for(int fixture=1;fixture<=64;++fixture){
  e->route_capture_mask=0;
  for(const auto& l:e->p.launches)e->capture_down(l,fixture);
  require(e->route_capture_mask==0xffffff,"24 full target DOWN sites required");
  e->capture_accept(fixture,fixture+100,fixture+10,false);route_sites+=24;
 }
 bool rejected=false;try{e->capture_accept(64,164,74,false);}catch(const std::exception&){rejected=true;}
 require(rejected,"duplicate capture must refuse");
 e->route_capture_valid.fill(false);e->route_capture_mask=1;
 rejected=false;try{e->capture_accept(1,101,11,false);}catch(const std::exception&){rejected=true;}
 require(rejected,"partial cancelled half must not qualify");
 e->drain();
 require(route_sites==1536,"capture cardinality");
'''
 entry.write_text(text.replace(marker,probe+marker))
 prior=json.loads((P/'parent-commands.snapshot.json').read_text())
 base=next(r['command'] for r in prior if r['name']=='gnu-host-entry-main');base=base[:base.index('-o')]
 base=[x for x in base if not x.startswith('-O')]+['-O0','-I'+str(P)]
 compile_cmd=[*base,'-c',str(entry),'-o',str(S/'entry.o')]
 link=list(next(r['command'] for r in prior if r['name']=='gnu-host-link'))
 link=[x for x in link if not x.endswith('own-rt-iq3-entry.cpp.o')]
 link=[str(S/'entry.o') if x.endswith('/entry-main.o') else x for x in link]
 link[link.index('-o')+1]=str(S/'fixture')
 for name,cmd in [('compile',compile_cmd),('link',link)]:
  with turn(),(S/(name+'.log')).open('w') as log:
   subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=600)
 import importlib.util
 spec=importlib.util.spec_from_file_location('p100b_memory',P/'memory_gate.py');gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
 ledger=json.loads((P/'memory-plan.json').read_text());runs=[]
 for rank in (0,1):
  dest=S/('rank'+str(rank));dest.mkdir(exist_ok=True)
  cmd=[str(S/'fixture'),str(P/'selection.json'),sha(P/'selection.json'),str(rank),str(dest),'positive','1','0']
  with (P/'evidence'/('startup-rank'+str(rank)+'.log')).open('w') as log:
   subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
  census=json.loads((dest/'census.json').read_text())
  admission=gate.check(census,ledger,rank,True,4096,1,0)
  captures=[a for a in census['allocations'] if a['label']=='card0:p100b-routes']
  assert len(captures)==1 and captures[0]['bytes']==184320
  routes=json.loads((dest/'native-plan.json').read_text())
  # Preserve small evidence; the large numerical mock's prepared-argument logs
  # remain build scratch and are never used as model execution evidence.
  archived=P/'evidence'/('startup-rank'+str(rank)+'.json.gz')
  archived.write_bytes(gzip.compress(json.dumps(dict(census=census,result=json.loads((dest/'result.json').read_text()))).encode(),mtime=0))
  runs.append(dict(rank=rank,passed=True,memory=admission,capture_sites=1536,partial_and_duplicate_refused=True,evidence=str(archived.relative_to(ROOT)),sha256=sha(archived)))
  print('rank',rank,'full shape/capture/admission PASS',flush=True)
 save(P/'evidence/full-shape.json',dict(passed=True,device_executed=False,model_payload_read=False,runs=runs,sources={str(f.relative_to(ROOT)):sha(f) for f in [parent,P/'full_shape.py',P/'route_capture.hpp',B/'cow/main.cpp',B/'cow/rank.hpp',B/'cow/strict_snapshot.hpp',B/'cow/request_reset.hpp',P/'memory-plan.json',P/'selection.json',entry,S/'main.cpp',S/'mtp.hpp']}))
if __name__=='__main__':main()
