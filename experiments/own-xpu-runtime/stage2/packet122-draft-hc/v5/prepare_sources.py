"""Create checked packet122 bracket sources; frozen packet118 stays read-only."""
import hashlib,json,sys
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[4];STAGE=P.parents[1]
BASE=STAGE/'packet118-record-bundle';LOCAL=P.parent
CHECKED=LOCAL/'build/checked'/LOCAL.relative_to(ROOT)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,row):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(row,indent=2)+'\n')
def once(text,old,new):
 if text.count(old)!=1:raise ValueError('native boundary: '+old[:120])
 return text.replace(old,new,1)
def prepare():
 # This source mirror has its own output directory; the micro uses another.
 (LOCAL/'build').mkdir(exist_ok=True)
 (LOCAL/'build/fusion-rope.hpp').write_bytes((BASE/'lineage-inputs/fusion-rope.hpp').read_bytes())
 sys.path.insert(0,str(LOCAL))
 from kernel_gate import mirror
 mirror()
 sys.path.remove(str(LOCAL))
 wrapper=STAGE/'packet117-hc-gate/v5'
 sources={str(f.relative_to(ROOT)):sha(f) for f in [*wrapper.glob('*.py'),*wrapper.glob('native/*')] if f.is_file()}
 out=P/'native-src';out.mkdir(exist_ok=True)
 for name in ('main.cpp','rank.hpp','mtp.hpp'):
  src=CHECKED/name;sources[str(src.relative_to(ROOT))]=sha(src);text=src.read_text()
  if name=='main.cpp':
   for leaf in ('rank.hpp','mtp.hpp'):text=once(text,json.dumps(str(CHECKED/leaf)),json.dumps(str(out/leaf)))
   text=once(text,'  void guard() {','#include '+json.dumps(str(P/'native/engine_bracket.hpp'))+'\n  void guard() {')
   text=once(text,'    drain();\n    auto started=std::chrono::steady_clock::now();\n    for (size_t i = 0; i < n; i += 4 * 1024 * 1024) {','    require(!bracket_weights_locked||dev(c).arena.row(dst).category!=Category::weights,"bracket immutable weight write refused");\n    drain();\n    auto started=std::chrono::steady_clock::now();\n    for (size_t i = 0; i < n; i += 4 * 1024 * 1024) {')
  elif name=='mtp.hpp':text=once(text,' void dump_all_state(const fs::path& path) {','#include '+json.dumps(str(P/'native/draft_bracket.hpp'))+'\n void dump_all_state(const fs::path& path) {')
  else:
   text=once(text,'static int run_rank(const Options& a) {','#include '+json.dumps(str(P/'native/bracket_boundary.hpp'))+'\nstatic int run_rank(const Options& a) {')
   text=once(text,'  Reply ready{};','  engine->bracket_weights_locked=true;\n  save(a.output/"loaded-arena-descriptors.txt",engine->bracket_arena_descriptors());\n  Reply ready{};')
   text=once(text,'   #ifdef OWN_RT_HOST_ONLY\n   else if(r.op==12)','   else if(r.op==13){\n    require(!async_half_ready,"bracket pending asynchronous half");\n    bracket_boundary(*engine,c,provider.get(),image,a.output/("bracket-"+std::to_string(r.sequence)+".txt"),accepted);\n    async_half_position=async_half_token=-1;\n   }\n   #ifdef OWN_RT_HOST_ONLY\n   else if(r.op==12)')
  (out/name).write_text(text)
 (out/'entry-main.cpp').write_text('#define main packet26_model_entry\n#include "main.cpp"\n#undef main\n')
 for name in ('dispatch-speed6.json','memory-plan.json'):
  src=BASE/name;sources[str(src.relative_to(ROOT))]=sha(src)
  dest=P/'lineage'/name;dest.parent.mkdir(exist_ok=True);dest.write_bytes(src.read_bytes())
 row=json.loads((BASE/'selection.json').read_text());row['choices']['draft_hc_schedule']='production'
 save(P/'lineage/selection.json',row)
 sources[str((BASE/'selection.json').relative_to(ROOT))]=sha(BASE/'selection.json')
 save(P/'source-copy-provenance.json',dict(schema='packet122.v5.copy.v1',sources=sources,device_executed=False))
 from bracket_config import prepare as config
 config('p122')
if __name__=='__main__':
 from build_engine import limits
 limits();prepare()
