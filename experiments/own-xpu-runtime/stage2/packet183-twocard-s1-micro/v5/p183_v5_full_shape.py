"""Real production startup/switch/reset with numerical allocations, no payloads."""
import importlib.util,json,subprocess,time,sys,os
from pathlib import Path
from p183_v5_build_engine import P,ROOT,BASE,B,sha,save,limits,compiler_turn
from p183_v5_build_engine import CHECKED,LOCAL
from prepare_sources import once
from retain_shape import retain

def generate():
    import p183_shape_mock as parent
    # The imported generator writes exclusively under S. P/B retain frozen
    # parent identities for read-only includes and manifest/plan inputs.
    # packet183: build the fixture from the engine's real v5 sources (S1 dispatch
    # lives there), served through a scratch mirror. The three includes the
    # generator re-injects (bracket, draft bracket) or rewires (mtp, rank) are
    # pre-adjusted so each appears exactly once at its original position.
    mirror_root=B/'fs-mirror';M=mirror_root/'checked'/LOCAL.relative_to(ROOT);M.mkdir(parents=True,exist_ok=True)
    main=(P/'native-src/main.cpp').read_text()
    main=once(main,'#include '+json.dumps(str(P/'native/engine_bracket.hpp'))+'\n','')
    main=once(main,'#include '+json.dumps(str(P/'native-src/mtp.hpp')),'#include '+json.dumps(str(M/'mtp.hpp')))
    main=once(main,'#include '+json.dumps(str(P/'native-src/rank.hpp')),'#include '+json.dumps(str(CHECKED/'rank.hpp')))
    (M/'main.cpp').write_text(main)
    mtp=once((P/'native-src/mtp.hpp').read_text(),'#include '+json.dumps(str(P/'native/draft_bracket.hpp'))+'\n','')
    (M/'mtp.hpp').write_text(mtp)
    out=parent.generate(M,B/'full-shape',LOCAL)
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
 std::vector<std::string> bracket_test_kernels()const {
  std::vector<std::string> out;
  for(const auto& site:issue_sites)for(const auto& cmd:site.commands){
   std::string name(reinterpret_cast<const char*>(cmd.operation_bytes.data()));int status=0;char* dem=abi::__cxa_demangle(name.c_str(),nullptr,nullptr,&status);
   if(dem){name=dem;std::free(dem);}out.push_back(name);
  }
  return out;
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
        .replace('P98_PARENT_PATH',json.dumps(str(BASE))).replace('P183_DISPATCH_PATH',json.dumps(str(P/'lineage/production/dispatch-speed6.json'))))
    return out

# Production kernel -> S1 kernel pairs allowed to differ between an expanded and a
# metadata view at the same issue site; everything else must be byte-identical.
def pair_ok(a,b):
    import re
    if a=='p33::Finish' and b=='p183::SegFinish':return True
    if a=='p49dvirtual::SmallKernel<4u>' and b=='p183::SmallKernel<4u>':return True
    m=re.fullmatch(r'p33::Kernel<0u, \(iq3::Type\)14, (\d+)u, ([14])u>',a)
    if m and b==f'p183::SegKernel<{m.group(1)}u, {m.group(2)}u>':return True
    return bool(re.fullmatch(r'p49c::DenseKernel<\(iq3::Type\)14, 6144u, 4u, \(p39::Kind\)\d+, 0u, false>',a)) and b=='p183::AttnKernel'
def s1_coverage(dest,rank,fresh):
    views=[json.loads((dest/f'launches-view{v}.json').read_text()) for v in range(5)]
    prod,meta=(views[1],views[0]) if fresh else (views[0],views[1])
    assert views[2]==views[0] and views[4]==views[0] and views[3]==views[1],'same selection must issue identical launches'
    assert len(prod)==len(meta),'launch count changed'
    converted={};unchanged_q6=[];pairs=set()
    for a,b in zip(prod,meta):
        assert (a['site'],a['command'],a['label'],a['op'])==(b['site'],b['command'],b['label'],b['op']),'site order changed'
        assert [x['id'] for x in a['bindings']]==[x['id'] for x in b['bindings']],'S1 changed bindings at '+a['label']
        if a['kernel']==b['kernel']:
            assert a['operation_sha']==b['operation_sha'],'non-S1 command changed: '+a['label']+' '+a['kernel']
            continue
        assert pair_ok(a['kernel'],b['kernel']),('unexpected kernel change',a['label'],a['kernel'],b['kernel'])
        cls=a['label'].split('.',2)[-1] if a['label'].startswith('blk.') else a['label']
        converted[cls]=converted.get(cls,0)+1;pairs.add((a['kernel'],b['kernel']))
    draft=None
    if (dest/'draft-kernels-view0.txt').exists():
        d=[(dest/f'draft-kernels-view{v}.txt').read_text().splitlines() for v in range(5)]
        dp,dm=(d[1],d[0]) if fresh else (d[0],d[1])
        assert len(dp)==len(dm)
        changed=[(x,y) for x,y in zip(dp,dm) if x!=y];assert all(pair_ok(x,y) for x,y in changed),changed
        draft=dict(commands=len(dp),converted=len(changed),pairs=sorted(set(changed)))
    return dict(rank=rank,commands=len(prod),converted=dict(sorted(converted.items())),converted_total=sum(converted.values()),pairs=sorted(pairs),draft=draft)

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
    (out/'audit-s1.cpp').write_text('#include '+json.dumps(str(CHECKED/'s1_kernels.hpp'))+'\n#include '+json.dumps(str(P/'native/audit_s1.hpp'))+'\n#include '+json.dumps(str(CHECKED/'s1_submit.cpp'))+'\n')
    audit_s1=[*args,'-c',str(out/'audit-s1.cpp'),'-o',str(out/'audit-s1.o')]
    assert sum(a.endswith('/s1_submit.o') for a in link)==1
    link=[str(out/'audit-s1.o') if a.endswith('/s1_submit.o') else a for a in link]
    with compiler_turn():
        for name,cmd in (('compile',compile_cmd),('audit-p60',audit_cmd),('audit-dispatch',audit_dispatch),('audit-s1',audit_s1),('link',link)):
            with (out/(name+'.log')).open('w') as log:
                subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
    runs=[]
    import sys
    sys.path.insert(0,str(BASE))
    from memory_gate import check
    control=P/'lineage/production/selection.json';candidate=P/'lineage/metadata/selection.json'
    coverage={}
    for rank,fresh in __import__('itertools').product((0,1),(False,True)):
        dest=out/('metadata-rank'+str(rank)+('-fresh' if fresh else ''));dest.mkdir(exist_ok=True)
        first,second=(candidate,control) if fresh else (control,candidate)
        cmd=[str(out/'fixture'),str(first),sha(first),str(rank),str(dest),str(second),sha(second)]
        started=time.monotonic()
        with (dest/'run.log').open('w') as log:
            subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=600)
        census=json.loads((dest/'census.json').read_text())
        memory=check(census,json.loads((candidate.parent/'memory-plan.json').read_text()),rank,mtp=True,context=4096,draft_rank=1,target_split=0)
        result=json.loads((dest/'result.json').read_text())
        coverage[(rank,fresh)]=s1_coverage(dest,rank,fresh)
        if fresh:
            switched=runs[-1]['result']
            assert all(v==result['initial_capture'] for v in switched['view_captures'][1::2]), 'fresh metadata capture differs from switched metadata capture'
        artifact=retain(dest)
        runs.append(dict(first=first.parent.name,second=second.parent.name,rank=rank,fresh=fresh,command=cmd,wall_seconds=time.monotonic()-started,memory=memory,result=result,s1_coverage=coverage[(rank,fresh)],artifact=artifact))
        print('full-shape metadata rank',rank,'fresh' if fresh else 'switch','PASS',flush=True)
    for rank in (0,1):
        assert coverage[(rank,False)]['converted']==coverage[(rank,True)]['converted'],'orientation changes S1 coverage'
    startup_runs=[]
    for selection in (control,candidate):
      for rank in (0,1):
        dest=out/f'startup-{selection.parent.name}-rank{rank}'
        command=[str(out/'fixture'),'--startup109','--rank',str(rank),'--draft-rank','1','--target-split','0',
          '--context','4096','--tokens','128','--memory','resident','--cards','1','--card','0',
          '--gemv','r5','--nongemv','parallel','--timing','token','--retain-steps','none',
          '--selection',str(selection),'--selection-sha256',sha(selection),
          '--dispatch',str(selection.parent/'dispatch-speed6.json'),'--plan',str(BASE/'lineage-inputs/vendor/repo/experiments/own-xpu-runtime/stage2/suite-inputs-20261012/code-review/plan.tsv'),
          '--draft-manifest',str(BASE/'mtp-manifest.tsv'),'--native-nice','19','--output',str(dest)]
        if rank==1:command+=['--draft-mtp']
        result=subprocess.run(command,stdin=subprocess.DEVNULL,capture_output=True,text=True,env=dict(os.environ,OMP_NUM_THREADS='2'),timeout=600)
        assert result.returncode==0,result.stderr
        row=json.loads((dest/'result.json').read_text());assert row['passed'] and row['prepared']
        startup_runs.append(dict(selection=selection.parent.name,rank=rank,command=command,result=row,artifact=retain(dest)))
        print('selected real-parser startup',selection.parent.name,rank,'PASS',flush=True)
    save(P/'evidence/full-shape.json',dict(passed=True,device_executed=False,model_payload_read=False,
        runs=runs,startup_runs=startup_runs,binary_sha256=sha(out/'fixture'),commands=[compile_cmd,audit_cmd,audit_dispatch,audit_s1,link],
        s1_coverage={f'rank{r}':coverage[(r,False)] for r in (0,1)},
        sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'p183_v5_full_shape.py',P/'p183_shape_mock.py',P/'native/full_shape_entry.cpp',P/'native/audit_s1.hpp',CHECKED/'s1_kernels.hpp',*out.glob('*.cpp'),*out.glob('*.hpp')]},
        payload_mocks=['numerical device addresses','weight upload elision','scalar readback','state-dump payload elision'],
        real_paths=['initialize','banks','SpeculativeImage','DraftRuntime','bracket_select','request_reset','bracket_boundary','memory admission','p183 dispatch at prepare time']))
    limits()
if __name__=='__main__':
 import resource
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
