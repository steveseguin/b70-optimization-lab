"""Real production startup/switch/reset with numerical allocations, no payloads."""
import importlib.util,json,subprocess,time,sys,os
from pathlib import Path
from p151_v5_build_engine import P,ROOT,BASE,B,sha,save,limits,compiler_turn
from p151_v5_build_engine import CHECKED,LOCAL
from prepare_sources import once
from retain_shape import retain

def generate():
    sys.path.append(str(BASE))
    spec=importlib.util.spec_from_file_location('parent_shape',LOCAL/'full_shape.py')
    parent=importlib.util.module_from_spec(spec);spec.loader.exec_module(parent)
    # The imported generator writes exclusively under S. P/B retain frozen
    # parent identities for read-only includes and manifest/plan inputs.
    parent.P=LOCAL;parent.B=LOCAL/'build';parent.S=B/'full-shape'
    parent.generate();out=parent.S
    old_checked=BASE/'build/checked'
    t=(out/'main.cpp').read_text()
    # Packet111's added shared-down functor stores capacity under a name not
    # recognized by the inherited CPU capture audit. Rename that test-only
    # field to n so the existing complete-member serializer binds its value.
    fusion=(CHECKED/'p109_fusion.hpp').read_text()
    fusion=once(fusion,'struct SharedDown final:p49c::Base {\n unsigned capacity;','struct SharedDown final:p49c::Base {\n unsigned n;')
    fusion=fusion.replace('auto b=bind(p,capacity);','auto b=bind(p,n);').replace('k.capacity=capacity','k.n=capacity')
    (out/'p109_fusion.hpp').write_text(fusion)
    t=once(t,json.dumps(str(CHECKED/'p109_fusion.hpp')),json.dumps(str(out/'p109_fusion.hpp')))
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
        '#include '+json.dumps(str(P/'native/draft_bracket.hpp'))+'\n void dump_all_state(const fs::path& path) {')
    m=parent.body(m,' void dump_all_state(const fs::path& path)', '')
    m=once(m,' void set_reverse_hidden(const void* bytes)', '''
 std::string bracket_test_digest()const {
  std::vector<uint8_t> bytes;
  for(const auto& site:issue_sites)for(const auto& cmd:site.commands){
   require(!cmd.operation_bytes.empty(),"draft empty capture audit");
   bytes.insert(bytes.end(),cmd.operation_bytes.begin(),cmd.operation_bytes.end());
   for(auto id:cmd.ids)ownrt::arguments::append(bytes,id);
  }
  require(!bytes.empty(),"draft empty captured commands");return hash(bytes);
 }
 void set_reverse_hidden(const void* bytes)''')
    (out/'mtp.hpp').write_text(m)
    rank=(P/'native-src/rank.hpp').read_text()
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
    limits();out=generate();prior=json.loads((P/'engine-commands.json').read_text())
    args=next(r['command'] for r in prior if r['name']=='gnu-host-entry-main');args=args[:args.index('-o')]
    if '-c' in args:
        i=args.index('-c');del args[i:i+2]
    args=[v for v in args if not v.startswith('-O')]+['-O0']
    compile_cmd=[*args,'-c',str(out/'entry.cpp'),'-o',str(out/'entry.o')]
    link=list(next(r['command'] for r in prior if r['name']=='gnu-host-link'))
    link=[str(out/'entry.o') if a.endswith('/entry-main.o') else a for a in link
          if not a.endswith('own-rt-iq3-entry.cpp.o')]
    link[link.index('-o')+1]=str(out/'fixture')
    audit_p60=out/'audit-p60.cpp'
    audit_p60.write_text((CHECKED/'p60_submit.cpp').read_text().replace('capacity','n'))
    audit_cmd=[*args,'-c',str(audit_p60),'-o',str(out/'audit-p60.o')]
    (out/'audit-parser.cpp').write_text('#include '+json.dumps(str(CHECKED/'p49d_small.hpp'))+'\n#include '+json.dumps(str(P/'native/audit_small.hpp'))+'\n#include '+json.dumps(str(CHECKED/'p49d_submit.cpp'))+'\n')
    audit_dispatch=[*args,'-c',str(out/'audit-parser.cpp'),'-o',str(out/'audit-dispatch.o')]
    link=[str(out/'audit-p60.o') if Path(a).name.endswith(('p60_submit.o','p60_submit.cpp.o')) else a for a in link]
    link=[str(out/'audit-dispatch.o') if a.endswith('/p49d_submit.o') else a for a in link]
    with compiler_turn():
        for name,cmd in (('compile',compile_cmd),('audit-p60',audit_cmd),('audit-dispatch',audit_dispatch),('link',link)):
            with (out/(name+'.log')).open('w') as log:
                subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
    runs=[]
    control=None
    import sys
    sys.path.insert(0,str(BASE))
    from memory_gate import check
    candidates=[P/'lineage'/v/'candidate.json' for v in ('router-order600','gdnz-order600')]
    for candidate,rank,fresh in __import__('itertools').product(candidates,(0,1),(False,True)):
        control=candidate.with_name('selection.json')
        dest=out/(candidate.parent.name+'-rank'+str(rank)+('-fresh' if fresh else ''));dest.mkdir(exist_ok=True)
        first=candidate if fresh else control
        cmd=[str(out/'fixture'),str(first),sha(first),str(rank),str(dest),str(candidate),sha(candidate)]
        started=time.monotonic()
        with (dest/'run.log').open('w') as log:
            subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
        census=json.loads((dest/'census.json').read_text())
        memory=check(census,json.loads((candidate.parent/'memory-plan.json').read_text()),rank,mtp=True,context=4096,draft_rank=1,target_split=0)
        result=json.loads((dest/'result.json').read_text())
        if fresh:
            switched=runs[-1]['result']
            assert all(v==result['initial_capture'] for v in switched['view_captures'][1::2]), 'fresh candidate capture mismatch'
        artifact=retain(dest)
        runs.append(dict(candidate=candidate.stem,rank=rank,fresh=fresh,command=cmd,wall_seconds=time.monotonic()-started,memory=memory,result=result,artifact=artifact))
        print('full-shape',candidate.stem,rank,'fresh' if fresh else 'switch','PASS',flush=True)
    startup_runs=[]
    for selection in [f for c in candidates for f in (c.with_name('selection.json'),c)]:
      for rank in (0,1):
        dest=out/f'startup-{selection.parent.name}-{selection.stem}-rank{rank}'
        command=[str(out/'fixture'),'--startup109','--rank',str(rank),'--draft-rank','1','--target-split','0',
          '--context','4096','--tokens','128','--memory','resident','--cards','1','--card','0',
          '--gemv','r5','--nongemv','parallel','--timing','token','--retain-steps','none',
          '--selection',str(selection),'--selection-sha256',sha(selection),
          '--dispatch',str(BASE/'dispatch-speed6.json'),'--plan',str(BASE/'lineage-inputs/vendor/repo/experiments/own-xpu-runtime/stage2/suite-inputs-20261012/code-review/plan.tsv'),
          '--draft-manifest',str(BASE/'mtp-manifest.tsv'),'--native-nice','19','--output',str(dest)]
        if rank==1:command+=['--draft-mtp']
        result=subprocess.run(command,stdin=subprocess.DEVNULL,capture_output=True,text=True,env=dict(os.environ,OMP_NUM_THREADS='2'),timeout=180)
        assert result.returncode==0,result.stderr
        row=json.loads((dest/'result.json').read_text());assert row['passed'] and row['prepared']
        startup_runs.append(dict(selection=selection.stem,rank=rank,command=command,result=row,artifact=retain(dest)))
        print('selected real-parser startup',selection.stem,rank,'PASS',flush=True)
    save(P/'evidence/full-shape.json',dict(passed=True,device_executed=False,model_payload_read=False,
        runs=runs,startup_runs=startup_runs,binary_sha256=sha(out/'fixture'),commands=[compile_cmd,audit_cmd,audit_dispatch,link],
        sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'p151_v5_full_shape.py',P/'native/full_shape_entry.cpp',*out.glob('*.cpp'),*out.glob('*.hpp')]},
        payload_mocks=['numerical device addresses','weight upload elision','scalar readback','state-dump payload elision'],
        real_paths=['initialize','banks','SpeculativeImage','DraftRuntime','bracket_select','request_reset','bracket_boundary','memory admission']))
    limits()
if __name__=='__main__':
 import resource
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
