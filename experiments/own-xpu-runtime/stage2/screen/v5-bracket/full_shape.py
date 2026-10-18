"""Real production startup/switch/reset with numerical allocations, no payloads."""
import importlib.util,json,subprocess,time,sys
from pathlib import Path
from build_engine import P,ROOT,BASE,B,sha,save,limits,compiler_turn
from native_source import CHECKED,once

def generate():
    sys.path.append(str(BASE))
    spec=importlib.util.spec_from_file_location('parent_shape',BASE/'full_shape.py')
    parent=importlib.util.module_from_spec(spec);spec.loader.exec_module(parent)
    # The imported generator writes exclusively under S. P/B retain frozen
    # parent identities for read-only includes and manifest/plan inputs.
    parent.P=BASE;parent.B=BASE/'build';parent.S=B/'full-shape'
    parent.generate();out=parent.S
    t=(out/'main.cpp').read_text()
    t=once(t,'  void guard() {','#include '+json.dumps(str(P/'native/engine_bracket.hpp'))+'\n  void guard() {')
    t=once(t,'class Engine final', 'static std::map<Allocation,std::vector<std::pair<size_t,size_t>>> p98_writes;\nclass Engine final')
    t=once(t,'  void upload(int c, Allocation dst, size_t offset, const void *src, size_t n) {',
        '  void upload(int c, Allocation dst, size_t offset, const void *src, size_t n) {\n'
        '    require(!bracket_weights_locked||dev(c).arena.row(dst).category!=Category::weights,"bracket immutable weight write refused");\n'
        '    p98_writes[dst].emplace_back(offset,n);')
    # Scalar payload readback is mocked; real guards and reset loops still run.
    t=parent.body(t,'  int integer(int c, const std::string &name)', 'return 0;')
    t=once(t,json.dumps(str(CHECKED/'rank.hpp')),json.dumps(str(out/'rank.hpp')))
    (out/'main.cpp').write_text(t)
    m=(out/'mtp.hpp').read_text()
    m=once(m,' void dump_all_state(const fs::path& path) {',
        ' void bracket_reset_metadata(){require(!async_pending,"bracket pending draft");pending_head=false;pending_confirmed=0;pending_start={};admit_position();}\n void dump_all_state(const fs::path& path) {')
    m=parent.body(m,' void dump_all_state(const fs::path& path)', '')
    (out/'mtp.hpp').write_text(m)
    rank=(B/'native/rank.hpp').read_text()
    rank=parent.body(rank,'static void state_dump(Engine& e,int sequence)', '')
    rank=once(rank,json.dumps(str(CHECKED/'request_reset.hpp')),json.dumps(str(out/'request_reset.hpp')))
    (out/'rank.hpp').write_text(rank)
    reset=(CHECKED/'request_reset.hpp').read_text()
    reset=once(reset,'#include '+json.dumps(str(CHECKED/'request_state_inventory.hpp')),
               'namespace pipeline {static void request_state_inventory(Engine&) {}}')
    (out/'request_reset.hpp').write_text(reset)
    (out/'entry.cpp').write_text((P/'native/full_shape_entry.cpp').read_text()
        .replace('P98_PARENT_PATH',json.dumps(str(BASE))))
    return out

def main():
    limits();out=generate();prior=json.loads((BASE/'engine-commands.json').read_text())
    args=next(r['command'] for r in prior if r['name']=='gnu-host-entry-main');args=args[:args.index('-o')]
    args=[v for v in args if not v.startswith('-O')]+['-O0']
    compile_cmd=[*args,'-c',str(out/'entry.cpp'),'-o',str(out/'entry.o')]
    link=list(next(r['command'] for r in prior if r['name']=='gnu-host-link'))
    link=[str(out/'entry.o') if a.endswith('/entry-main.o') else a for a in link
          if not a.endswith('own-rt-iq3-entry.cpp.o')]
    link[link.index('-o')+1]=str(out/'fixture')
    with compiler_turn():
        for name,cmd in (('compile',compile_cmd),('link',link)):
            with (out/(name+'.log')).open('w') as log:
                subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
    runs=[]
    control=P/'lineage/selection.json';candidate=P/'lineage/candidate.json'
    import sys
    sys.path.insert(0,str(BASE))
    from memory_gate import check
    for rank in (0,1):
        dest=out/('rank'+str(rank));dest.mkdir(exist_ok=True)
        cmd=[str(out/'fixture'),str(control),sha(control),str(rank),str(dest),str(candidate),sha(candidate)]
        started=time.monotonic()
        with (dest/'run.log').open('w') as log:
            subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
        census=json.loads((dest/'census.json').read_text())
        memory=check(census,json.loads((P/'lineage/memory-plan.json').read_text()),rank,mtp=True,context=4096,draft_rank=1,target_split=0)
        runs.append(dict(rank=rank,command=cmd,wall_seconds=time.monotonic()-started,memory=memory,
                         result=json.loads((dest/'result.json').read_text())))
        print('full-shape switch/reset rank',rank,'PASS',flush=True)
    save(P/'evidence/full-shape.json',dict(passed=True,device_executed=False,model_payload_read=False,
        runs=runs,binary_sha256=sha(out/'fixture'),commands=[compile_cmd,link],
        sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'full_shape.py',P/'native/full_shape_entry.cpp',*out.glob('*.cpp'),*out.glob('*.hpp')]},
        payload_mocks=['numerical device addresses','weight upload elision','scalar readback','state-dump payload elision'],
        real_paths=['initialize','banks','SpeculativeImage','DraftRuntime','bracket_select','request_reset','bracket_boundary','memory admission']))
    limits()
if __name__=='__main__':main()
