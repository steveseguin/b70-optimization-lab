"""Copy frozen v5 wrapper and packet103 source overlays, never device execution."""
import hashlib, json, os, resource, shutil
from pathlib import Path

P=Path(__file__).resolve().parent
ROOT=P.parents[4]
STAGE=P.parents[1]
BASE=STAGE/'packet103-record-bundle'
WRAPPER=STAGE/'packet109-other-fusion'
CHECKED=BASE/'build/checked'/BASE.relative_to(ROOT)
VALUES=('production','e3-next','iq4-bytepair','v4-batch2-shared','e5-shared')

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,row):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(row,indent=2)+'\n')
def once(text,old,new):
 if text.count(old)!=1: raise ValueError('native boundary: '+old[:120])
 return text.replace(old,new,1)
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
 assert shutil.disk_usage(P).free>=25_000_000_000
 sources={}
 names='common.py screen.py bracket.py conditions.py tp2_worker.py devices.py placement.py chain_devices.py drain_gate.py lane_admission.py fault_review.py compare.py'.split()
 for name in names:
  src=WRAPPER/name;sources[str(src.relative_to(ROOT))]=sha(src);text=src.read_text()
  text=text.replace('HERE.parents[3]','HERE.parents[4]').replace('HERE.parent /','HERE.parents[1] /')
  if name=='screen.py':text=text.replace('12_000_000_000','25_000_000_000').replace('12 GB free-storage floor','25 GB free-storage floor')
  if name=='bracket.py':
   text=text.replace("DOMAINS = {'other_fusion': ('production', 'fused')}","DOMAINS = {'expert_kernels': "+repr(VALUES)+"}")
  if name in ('screen.py','tp2_worker.py'):
   # No resource limits are set here or by exec_limits; inherited finite limits refuse.
   text='from exec_limits import install as _install_exec_limits\n_install_exec_limits()\n'+text
  (P/name).write_text(text)
 for name in ('engine_bracket.hpp','bracket_boundary.hpp','draft_bracket.hpp','full_shape_entry.cpp','reset_bytes.cpp'):
  src=WRAPPER/'native'/name;sources[str(src.relative_to(ROOT))]=sha(src);text=src.read_text()
  if name=='engine_bracket.hpp':
   text=text.replace('key!="other_fusion"','key!="expert_kernels"')
   text=text.replace('domain(selection->choices,"other_fusion",{"production","fused"});','domain(selection->choices,"expert_kernels",{'+','.join(json.dumps(v) for v in VALUES)+'});')
  if name=='reset_bytes.cpp':text=text.replace('../build/native/main.cpp','../native-src/main.cpp')
  if name=='full_shape_entry.cpp':
   start=text.index('  bool plus=false,parallel=false,route=false,wide=false;')
   end=text.index('  census(*e,a.output/',start)
   text=text[:start]+'''  const auto& choices=e->sealed_selection.choices;
  require(choices.at("experts")=="exp-halfcache+down-tile16","expert physical layout changed");
  // The exact capture bytes must change for a candidate and restore for control.
  if(view%2 && std::string(argv[1])!=std::string(argv[5]))
    require(capture()!=control_capture,"candidate expert selector did not change captures");
'''+text[end:]
   text=text.replace('{"other_fusion","unknown"}','{"expert_kernels","unknown"}')
  out=P/'native'/name;out.parent.mkdir(exist_ok=True);out.write_text(text)
 src=STAGE/'packet111-record-bundle/exec_limits.py'
 (P/'exec_limits.py').write_bytes(src.read_bytes());sources[str(src.relative_to(ROOT))]=sha(src)
 out=P/'native-src';out.mkdir(exist_ok=True)
 for name in ('main.cpp','rank.hpp','mtp.hpp','p49d_submit.cpp'):
  src=CHECKED/name;sources[str(src.relative_to(ROOT))]=sha(src);text=src.read_text()
  if name=='main.cpp':
   for leaf in ('rank.hpp','mtp.hpp'):
    text=once(text,json.dumps(str(CHECKED/leaf)),json.dumps(str(out/leaf)))
   text='#include '+json.dumps(str(P.parent/'expert_dispatch.hpp'))+'\n'+text
   text=once(text,'  void guard() {','#include '+json.dumps(str(P/'native/engine_bracket.hpp'))+'\n  void guard() {')
   text=once(text,'    drain();\n    auto started=std::chrono::steady_clock::now();\n    for (size_t i = 0; i < n; i += 4 * 1024 * 1024) {','    require(!bracket_weights_locked||dev(c).arena.row(dst).category!=Category::weights,"bracket immutable weight write refused");\n    drain();\n    auto started=std::chrono::steady_clock::now();\n    for (size_t i = 0; i < n; i += 4 * 1024 * 1024) {')
   old='p49d::expert(dev(c),selected,kind,b,sealed_selection.choices.contains("experts")?sealed_selection.choices.at("experts"):"production")'
   new='p115::expert(dev(c),selected,kind,b,sealed_selection.choices.at("experts"),sealed_selection.choices.at("expert_kernels"))'
   text=once(text,old,new)
  elif name=='mtp.hpp':
   text=once(text,' void dump_all_state(const fs::path& path) {','#include '+json.dumps(str(P/'native/draft_bracket.hpp'))+'\n void dump_all_state(const fs::path& path) {')
  elif name=='rank.hpp':
   text=once(text,'static int run_rank(const Options& a) {','#include '+json.dumps(str(P/'native/bracket_boundary.hpp'))+'\nstatic int run_rank(const Options& a) {')
   text=once(text,'  Reply ready{};','  engine->bracket_weights_locked=true;\n  save(a.output/"loaded-arena-descriptors.txt",engine->bracket_arena_descriptors());\n  Reply ready{};')
   text=once(text,'   #ifdef OWN_RT_HOST_ONLY\n   else if(r.op==12)','   else if(r.op==13){\n    require(!async_half_ready,"bracket pending asynchronous half");\n    bracket_boundary(*engine,c,provider.get(),image,a.output/("bracket-"+std::to_string(r.sequence)+".txt"),accepted);\n    async_half_position=async_half_token=-1;\n   }\n   #ifdef OWN_RT_HOST_ONLY\n   else if(r.op==12)')
  else:
   text=once(text,'Submit resolve(std::string_view cls,std::string_view choice){','Submit resolve(std::string_view cls,std::string_view choice){\n if(cls=="expert_kernels"&&('+ '||'.join('choice=='+json.dumps(v) for v in VALUES)+'))return production;')
   text=once(text,'values.size()!=10','values.size()!=11')
   text=once(text,'auto target_values=values;','auto target_values=values;target_values.erase("expert_kernels");')
  (out/name).write_text(text)
 (out/'entry-main.cpp').write_text('#define main packet26_model_entry\n#include "main.cpp"\n#undef main\n')
 for name in ('dispatch-speed6.json','memory-plan.json'):
  src=BASE/name;sources[str(src.relative_to(ROOT))]=sha(src)
  dest=P/'lineage'/name;dest.parent.mkdir(exist_ok=True);dest.write_bytes(src.read_bytes())
 sources[str((BASE/'selection.json').relative_to(ROOT))]=sha(BASE/'selection.json')
 row=json.loads((BASE/'selection.json').read_text());row['choices']['expert_kernels']='production'
 save(P/'lineage/selection.json',row)
 save(P/'source-copy-provenance.json',dict(schema='packet115.v5.copy.v1',parent_commit_floor='932df6642',sources=sources,device_executed=False))
 print('Copied v5 runtime and packet103 native overlays; no build or GPU execution')

if __name__=='__main__':main()
