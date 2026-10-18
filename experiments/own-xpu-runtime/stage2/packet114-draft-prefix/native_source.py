"""Copy the checked packet82b entry, retaining every kernel/object byte."""
import json
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
BASE=P.parent/'packet103-record-bundle'
CHECKED=P/'sources'/BASE.relative_to(ROOT)
def once(text,old,new):
    if text.count(old)!=1:raise ValueError('native integration boundary: '+old[:100])
    return text.replace(old,new,1)
def generate():
    out=P/'build/native';out.mkdir(parents=True,exist_ok=True)
    (out/'rope.bf16').write_bytes((BASE/'rope.bf16').read_bytes())
    # Frozen checked includes remain explicit read-only dependencies.
    for name in ('main.cpp','rank.hpp','mtp.hpp'):
        text=(CHECKED/name).read_text()
        if name=='main.cpp':
            for leaf in ('rank.hpp','mtp.hpp'):
                text=once(text,json.dumps(str(CHECKED/leaf)),json.dumps(str(out/leaf)))
            text=once(text,'  void guard() {','#include '+json.dumps(str(P/'native/engine_bracket.hpp'))+'\n  void guard() {')
            old='    drain();\n    auto started=std::chrono::steady_clock::now();\n    for (size_t i = 0; i < n; i += 4 * 1024 * 1024) {'
            text=once(text,old,'    require(!bracket_weights_locked||dev(c).arena.row(dst).category!=Category::weights,"bracket immutable weight write refused");\n'+old)
        elif name=='mtp.hpp':
            text=once(text,' void dump_all_state(const fs::path& path) {',
                '#include '+json.dumps(str(P/'native/draft_bracket.hpp'))+'\n void dump_all_state(const fs::path& path) {')
        else:
            text=once(text,'static int run_rank(const Options& a) {','#include '+json.dumps(str(P/'native/bracket_boundary.hpp'))+'\nstatic int run_rank(const Options& a) {')
            text=once(text,'  Reply ready{};',
                '  engine->bracket_weights_locked=true;\n  save(a.output/"loaded-arena-descriptors.txt",engine->bracket_arena_descriptors());\n  Reply ready{};')
            old='   #ifdef OWN_RT_HOST_ONLY\n   else if(r.op==12)'
            new='''   else if(r.op==13){
    require(!async_half_ready,"bracket pending asynchronous half");
    bracket_boundary(*engine,c,provider.get(),image,a.output/("bracket-"+std::to_string(r.sequence)+".txt"),accepted);
    async_half_position=async_half_token=-1;
   }
   #ifdef OWN_RT_HOST_ONLY
   else if(r.op==12)'''
            text=once(text,old,new)
        (out/name).write_text(text)
    (out/'entry-main.cpp').write_text('#define main packet26_model_entry\n#include "main.cpp"\n#undef main\n')
    return out
if __name__=='__main__':generate()
