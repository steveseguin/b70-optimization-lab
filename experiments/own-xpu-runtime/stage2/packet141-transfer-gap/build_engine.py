"""CPU-only incremental build; original kernel objects are immutable inputs."""
import hashlib,json,os,resource,shlex,shutil,subprocess,sys
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];B=P/'build';BASE=P.with_name('packet136-record-bundle')
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,v):Path(p).write_text(json.dumps(v,indent=2)+'\n')
def limits():
 assert shutil.disk_usage('/').free>=25_000_000_000,'root reserve'
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 assert sum(f.stat().st_size for f in B.rglob('*') if f.is_file() and not f.is_symlink())<=300_000_000

def replace(s,a,b):
 assert s.count(a)==1,(a,s.count(a));return s.replace(a,b)
def prepare():
 prior=json.loads((P/'parent-commands.snapshot.json').read_text())
 cmd=next(r['command'] for r in prior if r['name']=='device-entry-main')
 mirror=Path(next(x[2:] for x in cmd if x.startswith('-I') and '/checked/' in x))
 raw_parent=P.with_name('packet131-snapshot-banks')
 for name in ('main.cpp','rank.hpp','request_reset.hpp'):
  assert sha(BASE/name)==sha(raw_parent/name), 'packet136 native drift: '+name
 main=(mirror/'main.cpp').read_text();rank=(mirror/'rank.hpp').read_text();reset=(mirror/'request_reset.hpp').read_text()
 main=replace(main,'class Engine final : public flash::Backend {','#define P141_PACKET '+json.dumps(str(P))+'\n#include '+json.dumps(str(P/'probe_touch.hpp'))+'\nclass Engine final : public flash::Backend {')
 main=replace(main,'  std::vector<Allocation> slab, scratch, workspace, compact_routes, mixture_out, one;', '  std::vector<Allocation> slab, scratch, workspace, compact_routes, mixture_out, one;\n#include '+json.dumps(str(P/'probe.hpp')))
 # Share the original constructor's exact selection checks with the CPU entry gate.
 start=main.index('    const auto down_choice=')
 end=main.index('    const auto host_choice=',start)
 checks=main[start:end]
 head='auto head_choice=[&](){auto i=sealed_selection.choices.find("head");return i==sealed_selection.choices.end()?std::string("production"):i->second;};'
 helper='static void p141_validate_selection(const Options& a,const p49d::Selection& sealed_selection){'+head+'\n'+checks+'}\n'
 main=main[:start]+'    p141_validate_selection(a,sealed_selection);\n'+main[end:]
 main=replace(main,'class Engine final : public flash::Backend {',helper+'class Engine final : public flash::Backend {')
 main=replace(main,'struct Options {','struct Options {\n  bool p141_cpu_entry_gate=false;')
 main=replace(main,'    if (k == "--retain-steps")', '    if(k=="--p141-cpu-entry-gate")a.p141_cpu_entry_gate=true;\n    else if (k == "--retain-steps")')
 main=replace(main,'getpriority(PRIO_PROCESS, 0) == a.native_nice','getpriority(PRIO_PROCESS, 0) == (a.p141_cpu_entry_gate?19:a.native_nice)')
 gate=(P/'cpu_entry.hpp').read_text()
 main=replace(main,'int main(int argc, char **argv) {',gate+'\nint main(int argc, char **argv) {')
 main=replace(main,'    require(!fs::exists(a.output), "output already exists");','    if(a.p141_cpu_entry_gate)return p141_cpu_entry(a);\n    require(!fs::exists(a.output), "output already exists");')
 rank=replace(rank,'  error=ex.what();','  error=ex.what();\n  std::cerr<<"rank "<<a.rank<<" failure: "<<error<<std::endl;')
 main=replace(main,str(mirror/'rank.hpp'),str(B/'cow/rank.hpp'))
 rank=replace(rank,'   else if(r.op==11){','   else if(r.op==13){require(a.rank==0&&!c.pending,"p141 unresolved candidate/rank");image.boundary();engine->p141_probe(r.token,r.position);}\n   else if(r.op==11){')
 rank=replace(rank,str(mirror/'request_reset.hpp'),str(B/'cow/request_reset.hpp'))
 rank=replace(rank,'if(provider)provider->dump_all_state(engine->a.output/"draft-final-state");break;','/* p141: no full-state file output. */break;')
 reset=replace(reset,' state_dump(e,2147483647);request_state_inventory(e);if(provider)provider->dump_all_state(e.a.output/"draft-final-state");',' // p141: omit full-state files; allocation reset and arithmetic unchanged.')
 for name,body in [('main.cpp',main),('rank.hpp',rank),('request_reset.hpp',reset)]: (B/'cow'/name).write_text(body)
 entry=B/'entry-main.cpp';entry.write_text('#define main packet26_model_entry\n#include '+json.dumps(str(B/'cow/main.cpp'))+'\n#undef main\n');return prior,entry

def main():
 limits();(B/'cow').mkdir(parents=True,exist_ok=True);(B/'tmp').mkdir(exist_ok=True);os.environ['TMPDIR']=str(B/'tmp')
 sys.path.insert(0,str(P.parents[1]/'ops'));from compile_turn import turn
 prior,entry=prepare();commands=[];sources={};artifacts={}
 def run(cmd,name):
  limits();cmd=list(map(str,cmd));commands.append(dict(name=name,command=cmd))
  with (B/(name+'.log')).open('w') as log:subprocess.run(cmd,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1500)
  print(name,'PASS',flush=True)
 for mode in ('device','gnu-host'):
  dest=B/mode;dest.mkdir(exist_ok=True)
  cmd=next(r['command'] for r in prior if r['name']==mode+'-entry-main');cmd=cmd[:cmd.index('-o')]
  # Preserve all arithmetic and kernel flags. Host orchestration diagnostic is
  # compiled at O1 to fit the CPU preparation box; kernel objects stay original.
  cmd=[x for x in cmd if x not in ('-O2','-O3')]+['-O1']
  dep=dest/'entry.d';run([*cmd,'-MMD','-MF',dep,'-o',dest/'entry-main.o','-c',entry],mode+'-entry')
  for path in shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1]):
   f=Path(path).resolve()
   if f.is_relative_to(ROOT):sources[str(f.relative_to(ROOT))]=sha(f)
  link=list(next(r['command'] for r in prior if r['name']==mode+'-link'));link[link.index('-o')+1]=str(dest/'own-rt-iq3');count=0
  for i,arg in enumerate(link):
   if not arg.endswith('.o'):continue
   if Path(arg).name=='entry-main.o':link[i]=str(dest/'entry-main.o');count+=1
   else:sources[str(Path(arg).relative_to(ROOT))]=sha(arg)
  assert count==1,count
  if mode=='device':link+=['-Wl,--no-as-needed',str(P/'runtime/libumf.so.1'),'-Wl,--as-needed','-Wl,-rpath,'+str(P/'runtime'),'-ldl']
  run(link,mode+'-link');artifacts[str((dest/'own-rt-iq3').relative_to(P))]=sha(dest/'own-rt-iq3')
 for f in (P/'build_engine.py',P/'parent-commands.snapshot.json',P/'probe.hpp',P/'probe_touch.hpp',P/'cpu_entry.hpp',*sorted((P/'runtime').iterdir())):
  sources[str(f.relative_to(ROOT))]=sha(f)
 limits();save(P/'build-receipt.json',dict(passed=True,device_executed=False,sources=sources,artifacts=artifacts,commands=commands,host_entry_optimization='O1 diagnostic; unchanged original kernel objects',max_child_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss))
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
 sys.path.insert(0,str(P.parents[1]/'ops'))
 from compile_turn import turn
 with turn():main()
