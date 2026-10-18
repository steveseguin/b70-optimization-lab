"""Copy frozen v5 wrapper and packet103 source overlays, never device execution."""
import hashlib, json, os, resource, shutil
from pathlib import Path

P=Path(__file__).resolve().parent
ROOT=P.parents[4]
STAGE=P.parents[1]
BASE=STAGE/'packet111-record-bundle'
WRAPPER=STAGE/'packet109-other-fusion'
CHECKED=BASE/'build/checked'/BASE.relative_to(ROOT)
VALUES=('production','p117')

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
   text=text.replace("DOMAINS = {'other_fusion': ('production', 'fused')}","DOMAINS = {'hc_gate': "+repr(VALUES)+"}")
  if name in ('screen.py','tp2_worker.py'):
   # No resource limits are set here or by exec_limits; inherited finite limits refuse.
   text='from exec_limits import install as _install_exec_limits\n_install_exec_limits()\n'+text
  (P/name).write_text(text)
 for name in ('engine_bracket.hpp','bracket_boundary.hpp','draft_bracket.hpp','full_shape_entry.cpp','reset_bytes.cpp'):
  src=WRAPPER/'native'/name;sources[str(src.relative_to(ROOT))]=sha(src);text=src.read_text()
  if name=='engine_bracket.hpp':
   text=text.replace('key!="other_fusion"','key!="hc_gate"')
   text=text.replace('domain(selection->choices,"other_fusion",{"production","fused"});','domain(selection->choices,"other_fusion",{"fused"});')
   text=text.replace('domain(selection->choices,"hc_gate",{"production","wide"});','domain(selection->choices,"hc_gate",{"production","p117"});')
  if name=='reset_bytes.cpp':text=text.replace('../build/native/main.cpp','../native-src/main.cpp')
  if name=='full_shape_entry.cpp':
   start=text.index('  bool plus=false,parallel=false,route=false,wide=false;')
   end=text.index('  census(*e,a.output/',start)
   text=text[:start]+'''  const auto& choices=e->sealed_selection.choices;
  require(choices.at("experts")=="exp-halfcache+down-tile16","expert physical layout changed");
  unsigned candidate_gates=0,control_gates=0;
  for(const auto&[name,count]:p80_operations){
   if(name.find("p117dispatch::Kernel<2, true")!=std::string::npos)candidate_gates+=count;
   if(name.find("p60::Kernel<2, true")!=std::string::npos)control_gates+=count;
   require(name.find("p117dispatch::Kernel<0")==std::string::npos&&name.find("p117dispatch::Kernel<1")==std::string::npos,"candidate changed norm/low dispatch");
  }
  require((candidate_gates>0)==(choices.at("hc_gate")=="p117"),"selected HC candidate kernel missing");
  require((control_gates>0)==(choices.at("hc_gate")=="production"),"selected HC control kernel missing");

  // The exact capture bytes must change for a candidate and restore for control.
  if(view%2 && std::string(argv[1])!=std::string(argv[5]))
    require(capture()!=control_capture,"candidate HC selector did not change captures");
'''+text[end:]
   text=text.replace('{"other_fusion","unknown"}','{"hc_gate","unknown"}')
   text=text.replace('e->initialize();','e->initialize();std::unique_ptr<p105::Runtime> head_runtime;if(e->split_head())head_runtime=std::make_unique<p105::Runtime>(*e);')
  out=P/'native'/name;out.parent.mkdir(exist_ok=True);out.write_text(text)
 src=STAGE/'packet111-record-bundle/exec_limits.py'
 (P/'exec_limits.py').write_bytes(src.read_bytes());sources[str(src.relative_to(ROOT))]=sha(src)
 out=P/'native-src';out.mkdir(exist_ok=True)
 for name in ('main.cpp','rank.hpp','mtp.hpp','p49d_submit.cpp'):
  src=CHECKED/name;sources[str(src.relative_to(ROOT))]=sha(src);text=src.read_text()
  if name=='main.cpp':
   for leaf in ('rank.hpp','mtp.hpp'):
    text=once(text,json.dumps(str(CHECKED/leaf)),json.dumps(str(out/leaf)))
   text='#include '+json.dumps(str(P/'native-src/hc_submit.hpp'))+'\n'+text
   text=once(text,'  void guard() {','#include '+json.dumps(str(P/'native/engine_bracket.hpp'))+'\n  void guard() {')
   text=once(text,'    drain();\n    auto started=std::chrono::steady_clock::now();\n    for (size_t i = 0; i < n; i += 4 * 1024 * 1024) {','    require(!bracket_weights_locked||dev(c).arena.row(dst).category!=Category::weights,"bracket immutable weight write refused");\n    drain();\n    auto started=std::chrono::steady_clock::now();\n    for (size_t i = 0; i < n; i += 4 * 1024 * 1024) {')
   old='p60::submit(dev(c),ids,stage,p.g.context,sealed_selection.choices.at("hc_gate")=="wide",sealed_selection.choices.at("hc_norm")=="subgroup",sealed_selection.choices.at("hc_gate")=="hc-weightcache",sealed_selection.choices.at("hc_norm")=="consumer")'
   new='(stage==2&&sealed_selection.choices.at("hc_gate")=="p117"?p117dispatch::submit:p60::submit)(dev(c),ids,stage,p.g.context,true,sealed_selection.choices.at("hc_norm")=="subgroup",false,sealed_selection.choices.at("hc_norm")=="consumer")'
   text=once(text,old,new)
  elif name=='mtp.hpp':
   text=once(text,' void dump_all_state(const fs::path& path) {','#include '+json.dumps(str(P/'native/draft_bracket.hpp'))+'\n void dump_all_state(const fs::path& path) {')
  elif name=='rank.hpp':
   text=once(text,'static int run_rank(const Options& a) {','#include '+json.dumps(str(P/'native/bracket_boundary.hpp'))+'\nstatic int run_rank(const Options& a) {')
   text=once(text,'  Reply ready{};','  engine->bracket_weights_locked=true;\n  save(a.output/"loaded-arena-descriptors.txt",engine->bracket_arena_descriptors());\n  Reply ready{};')
   text=once(text,'   #ifdef OWN_RT_HOST_ONLY\n   else if(r.op==12)','   else if(r.op==13){\n    require(!async_half_ready,"bracket pending asynchronous half");\n    bracket_boundary(*engine,c,provider.get(),image,a.output/("bracket-"+std::to_string(r.sequence)+".txt"),accepted);\n    async_half_position=async_half_token=-1;\n   }\n   #ifdef OWN_RT_HOST_ONLY\n   else if(r.op==12)')
  else:
   text=once(text,'if(cls=="hc_gate"&&(choice=="production"||choice=="wide"))return production;',
       'if(cls=="hc_gate"&&(choice=="production"||choice=="p117"))return production;')
  (out/name).write_text(text)
 src=CHECKED/'p60_submit.cpp';sources[str(src.relative_to(ROOT))]=sha(src)
 text=src.read_text().replace('namespace p60 {','namespace p117dispatch {\nusing namespace p60;').replace('capacity','n')
 text=text.replace('p73hc::host(b)','p117hc::host(b)').replace('p73hc::device(q,b,deps)','p117hc::device(q,b,deps)')
 text='#include '+json.dumps(str(P/'build/hc_gate_checked.hpp'))+'\n'+text
 (out/'hc_submit.cpp').write_text(text)
 (out/'hc_submit.hpp').write_text('#pragma once\n#include '+json.dumps(str(CHECKED/'p60_submit.hpp'))+'\nnamespace p117dispatch { integrated::Launch submit(ownrt::Device&,const p60::IDs&,int,unsigned,bool,bool,bool,bool); }\n')
 (out/'entry-main.cpp').write_text('#define main packet26_model_entry\n#include "main.cpp"\n#undef main\n')
 for name in ('dispatch-speed6.json','memory-plan.json'):
  src=BASE/name;sources[str(src.relative_to(ROOT))]=sha(src)
  dest=P/'lineage'/name;dest.parent.mkdir(exist_ok=True);dest.write_bytes(src.read_bytes())
 sources[str((BASE/'selection.json').relative_to(ROOT))]=sha(BASE/'selection.json')
 row=json.loads((BASE/'selection.json').read_text());row['choices']['hc_gate']='production'
 save(P/'lineage/selection.json',row)
 save(P/'source-copy-provenance.json',dict(schema='packet117.v5.copy.v1',parent_commit_floor='9b49c03e7',sources=sources,device_executed=False))
 print('Copied v5 runtime and packet111 native overlays; no build or GPU execution')

if __name__=='__main__':main()
