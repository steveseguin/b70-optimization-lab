"""COW packet97 entry only. All unchanged linked objects retain their identity."""
import hashlib,json,os,resource,shlex,subprocess,sys
from pathlib import Path
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
BASE=P.parent/'packet97-record-bundle'
B=P/'build'
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for block in iter(lambda:f.read(1048576),b''):h.update(block)
 return h.hexdigest()
def save(path,value):Path(path).write_text(json.dumps(value,indent=2)+'\n')
def limits():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
def replace(text,old,new):
 assert text.count(old)==1,old
 return text.replace(old,new)
def prepare():
 mirror=BASE/'build/checked'/BASE.relative_to(ROOT)
 source=B/'cow';source.mkdir(parents=True,exist_ok=True)
 main=(mirror/'main.cpp').read_text()
 main=replace(main,'  std::vector<Allocation> slab, scratch, workspace, compact_routes, mixture_out, one;',
   '  std::vector<Allocation> slab, scratch, workspace, compact_routes, mixture_out, one;\n#include '+json.dumps(str(P/'route_capture.hpp')))
 main=replace(main,'      buffers.emplace_back();',
   '      route_capture_buffers.push_back(allocate(c,"p100b-routes",route_capture_bytes,Category::scratch,Lifetime::transaction));\n      buffers.emplace_back();')
 main=replace(main,str(mirror/'rank.hpp'),str(source/'rank.hpp'))
 rank=(mirror/'rank.hpp').read_text()
 rank=replace(rank,' candidate={};candidate.pending=true;',
   ' e.route_capture_mask=0;\n candidate={};candidate.pending=true;')
 rank=replace(rank,'  e.enqueue(l,e.logical);','  e.enqueue(l,e.logical);\n  e.capture_down(l,request.fixture);')
 rank=replace(rank,'publish(*engine,c);if(c.speculative)',
   'engine->capture_accept(c.fixture,c.position,engine->route_capture_tokens[0],c.cancelled);publish(*engine,c);if(c.speculative)')
 # Candidate has no token field. Store input token at HALF, before any async work.
 rank=replace(rank,' e.route_capture_mask=0;',
   ' e.route_capture_mask=0;\n if(request.fixture>0&&request.fixture<=64)e.route_capture_tokens[request.fixture-1]=request.token;')
 rank=rank.replace('engine->route_capture_tokens[0],c.cancelled','engine->route_capture_tokens[c.fixture>0&&c.fixture<=64?c.fixture-1:0],c.cancelled')
 rank=replace(rank,'   else if(r.op==11){','   else if(r.op==13){require(!c.pending,"capture unresolved candidate");image.boundary();engine->capture_flush();}\n   else if(r.op==11){engine->route_capture_valid.fill(false);')
 rank=replace(rank,'if(provider)provider->dump_all_state(engine->a.output/"draft-final-state");break;',
   '/* p100b: no full-state dump in this bounded route diagnostic. */break;')
 rank=replace(rank,str(mirror/'request_reset.hpp'),str(source/'request_reset.hpp'))
 rank=replace(rank,str(mirror/'strict_snapshot.hpp'),str(source/'strict_snapshot.hpp'))
 snapshot=(mirror/'strict_snapshot.hpp').read_text()
 snapshot=replace(snapshot,'   require(owner.first==0&&row.memory==Memory::device,"snapshot owner/memory");',
   '   if(id==e.route_capture_buffers.at(0))continue; // diagnostic overwrite-only slots, never model state\n   require(owner.first==0&&row.memory==Memory::device,"snapshot owner/memory");')
 reset=(mirror/'request_reset.hpp').read_text()
 reset=replace(reset,' state_dump(e,2147483647);request_state_inventory(e);if(provider)provider->dump_all_state(e.a.output/"draft-final-state");',
   ' // p100b: full-state output omitted; reset arithmetic/allocation zeroing unchanged.')
 for name,text in [('main.cpp',main),('rank.hpp',rank),('request_reset.hpp',reset),('strict_snapshot.hpp',snapshot)]:
  (source/name).write_text(text)
 entry=B/'entry-main.cpp'
 entry.write_text('#define main packet26_model_entry\n#include '+json.dumps(str(source/'main.cpp'))+'\n#undef main\n')
 return entry
def main():
 limits();B.mkdir(exist_ok=True);(B/'tmp').mkdir(exist_ok=True);os.environ['TMPDIR']=str(B/'tmp')
 # Snapshot mutable selection/ledger/command inputs into this packet; never pin
 # their changing parent orchestration files in a descendant seal.
 commands_path=P/'parent-commands.snapshot.json'
 if not commands_path.exists():commands_path.write_bytes((BASE/'engine-commands.json').read_bytes())
 prior=json.loads(commands_path.read_text());entry=prepare()
 sys.path.insert(0,str(P.parent/'packet94-hc-norm-fusion'))
 from compile_turn import turn
 sources={};artifacts={};commands=[]
 def run(cmd,name):
  cmd=list(map(str,cmd));commands.append(dict(name=name,command=cmd))
  with turn(),(B/(name+'.log')).open('w') as log:
   subprocess.run(cmd,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=900)
  print(name,'PASS',flush=True)
 for mode in ('gnu-host','device'):
  dest=B/mode;dest.mkdir(exist_ok=True)
  cmd=next(r['command'] for r in prior if r['name']==mode+'-entry-main');cmd=cmd[:cmd.index('-o')]
  dep=dest/'entry.d'
  run([*cmd,'-MMD','-MF',dep,'-o',dest/'entry-main.o','-c',entry],mode+'-entry')
  for path in shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1]):
   f=Path(path).resolve()
   if f.is_relative_to(ROOT):sources[str(f.relative_to(ROOT))]=sha(f)
  link=list(next(r['command'] for r in prior if r['name']==mode+'-link'))
  link[link.index('-o')+1]=str(dest/'own-rt-iq3')
  count=0
  for i,arg in enumerate(link):
   if arg.endswith('/entry-main.o'):link[i]=str(dest/'entry-main.o');count+=1
   elif arg.endswith('.o'):sources[str(Path(arg).relative_to(ROOT))]=sha(arg)
  assert count==1
  run(link,mode+'-link');artifacts[str((dest/'own-rt-iq3').relative_to(P))]=sha(dest/'own-rt-iq3')
 for path in (P/'build_engine.py',P/'parent-commands.snapshot.json',P.parent/'packet94-hc-norm-fusion/compile_turn.py',BASE/'rope.bf16',BASE/'mtp-manifest.tsv'):
  sources[str(path.relative_to(ROOT))]=sha(path)
 total=sum(f.stat().st_size for f in B.rglob('*') if f.is_file());assert total<=300_000_000,total
 save(P/'build-receipt.json',dict(schema='packet100b.cpu-build.v1',passed=True,device_executed=False,sources=sources,artifacts=artifacts,commands=commands,build_bytes=total))
if __name__=='__main__':main()
