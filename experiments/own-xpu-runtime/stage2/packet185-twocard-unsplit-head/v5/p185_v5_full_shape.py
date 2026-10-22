"""Packet185 production-shape gate: both selections, both ranks, fresh startup each.

Real v5 main.cpp/mtp.hpp/rank.hpp with numerical device addresses and no payload (packet183
fixture generator). For each selection (production = bundle 8 split head; unsplit = full
target head on rank 1) and each rank: fresh startup, five bracket resets that re-select the
SAME selection (device rows are one fresh load per view), reset extents, arena identity,
capture identity with the fresh startup, the native refusals (including an in-load
head split <-> full head switch), the actual allocation census, and the issued command
list. The two selections must issue identical commands except at the target-head sites
of rank 1; their census difference is the measured allocation delta that derives the
unsplit memory plan (lineage/unsplit/memory-plan.json) from the production plan.
"""
import importlib.util,json,subprocess,time,sys,os
from pathlib import Path
from p185_v5_build_engine import P,ROOT,BASE,B,sha,save,limits,compiler_turn
from p185_v5_build_engine import CHECKED,LOCAL
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
        .replace('P98_PARENT_PATH',json.dumps(str(BASE))).replace('P185_DISPATCH_PATH',json.dumps(str(P/'lineage/production/dispatch-speed6.json'))))
    return out


SELECTIONS=('production','unsplit')
PLAN_KEYS=('target_modeled_allocations_bytes','target_total_bytes','total_with_mtp_bytes','arena_device_bytes')

def launches_equal_except_head(prod,unsplit,rank):
    """Identical issued commands except the rank-1 target-head sites."""
    a=json.loads(prod.read_text());b=json.loads(unsplit.read_text())
    def key(x):return (x['label'],x['op'],x['kernel'],x['operation_sha'],tuple((y['label'],y['bytes'],y['category']) for y in x['bindings']))
    head=lambda x:x['label'] in ('logits','argmax') or x['label'].startswith('final.') and any('output.weight' in y['label'] for y in x['bindings'])
    ka=[key(x) for x in a if not head(x)];kb=[key(x) for x in b if not head(x)]
    assert ka==kb,'non-head command differs between split and full head (rank %d)'%rank
    ha=[x for x in a if head(x)];hb=[x for x in b if head(x)]
    if rank==0:assert not ha and not hb,'rank 0 issues no target-head site in either selection'
    else:assert ha and hb,'rank 1 must issue the target head in both selections'
    def rows(xs):return [dict(label=x['label'],op=x['op'],kernel=x['kernel'],shape=x['shape'],
        bindings=[dict(label=y['label'],bytes=y['bytes']) for y in x['bindings']]) for x in xs]
    return dict(rank=rank,commands=len(a),identical_non_head_commands=len(ka),split_head_sites=rows(ha),full_head_sites=rows(hb))

def derive_unsplit_plan(census):
    """Production ledger + measured census delta per rank (actual allocation calls)."""
    plan=json.loads((P/'lineage/production/memory-plan.json').read_text())
    delta=[census[('unsplit',r)]-census[('production',r)] for r in (0,1)]
    row=plan['placements']['1']['capacities']['4096']['ranks']
    for r in row:
        d=delta[r['rank']]
        for k in PLAN_KEYS:r[k]+=d
        r['free_with_mtp_bytes']=plan['capacity_bytes']-r['total_with_mtp_bytes']
        r['arena_headroom_bytes']=plan['arena_limit_bytes']-r['arena_device_bytes']
        r['allocation_margin_passed']=r['free_with_mtp_bytes']>=plan['minimum_free_bytes']
        r['arena_margin_passed']=r['arena_headroom_bytes']>=0
    plan['view']=plan['view'].replace('--fused--split--','--fused--production--')
    assert '--production--80128--' in plan['view']
    plan['scope']=('packet185: packet183/153 production ledger plus the measured production-shape census delta of the '
                   'full target head (rank 1 loads all 248,320 head rows; rank 0 loads no suffix rows and no p105 '
                   'auxiliary buffers); physical driver residency unmeasured')
    plan['packet185_census_delta_bytes_per_rank']=delta
    return plan,delta

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
                subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=600)
    sys.path.insert(0,str(BASE))
    from memory_gate import check
    selections={s:P/'lineage'/s/'selection.json' for s in SELECTIONS}
    raw={};census={}
    for selection,rank in __import__('itertools').product(SELECTIONS,(0,1)):
        path=selections[selection];dest=out/f'{selection}-rank{rank}';dest.mkdir(exist_ok=True)
        cmd=[str(out/'fixture'),str(path),sha(path),str(rank),str(dest),str(path),sha(path)]
        started=time.monotonic()
        with (dest/'run.log').open('w') as log:
            subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=900)
        row=json.loads((dest/'census.json').read_text());census[(selection,rank)]=row['totals']['device']
        result=json.loads((dest/'result.json').read_text())
        assert result['passed'] and result['views']==5 and result['fresh_start_capture_identity'] and result['layout_refused'] and result['native_refusals']==15
        assert all(v==result['initial_capture'] for v in result['view_captures']),'re-selected capture differs'
        raw[(selection,rank)]=dict(dest=dest,command=cmd,wall_seconds=time.monotonic()-started,result=result,census_row=row)
        print('full-shape',selection,'rank',rank,'PASS',flush=True)
    plan,delta=derive_unsplit_plan(census)
    target=P/'lineage/unsplit/memory-plan.json'
    if not target.exists():save(target,plan)
    assert json.loads(target.read_text())==plan,'unsplit memory plan differs from its measured derivation'
    heads=[launches_equal_except_head(out/f'production-rank{r}'/'launches-view0.json',out/f'unsplit-rank{r}'/'launches-view0.json',r) for r in (0,1)]
    draft_same=(out/'production-rank1/draft-kernels-view0.txt').read_text()==(out/'unsplit-rank1/draft-kernels-view0.txt').read_text()
    assert draft_same,'draft commands differ between head selections'
    runs=[]
    for (selection,rank),row in raw.items():
        ledger=json.loads((P/'lineage'/selection/'memory-plan.json').read_text())
        memory=check(row['census_row'],ledger,rank,mtp=True,context=4096,draft_rank=1,target_split=0)
        runs.append(dict(selection=selection,rank=rank,command=row['command'],wall_seconds=row['wall_seconds'],memory=memory,
                         result=row['result'],artifact=retain(row['dest'])))
    startup_runs=[]
    for selection,path in selections.items():
      for rank in (0,1):
        dest=out/f'startup-{selection}-rank{rank}'
        command=[str(out/'fixture'),'--startup109','--rank',str(rank),'--draft-rank','1','--target-split','0',
          '--context','4096','--tokens','128','--memory','resident','--cards','1','--card','0',
          '--gemv','r5','--nongemv','parallel','--timing','token','--retain-steps','none',
          '--selection',str(path),'--selection-sha256',sha(path),
          '--dispatch',str(path.parent/'dispatch-speed6.json'),'--plan',str(BASE/'lineage-inputs/vendor/repo/experiments/own-xpu-runtime/stage2/suite-inputs-20261012/code-review/plan.tsv'),
          '--draft-manifest',str(BASE/'mtp-manifest.tsv'),'--native-nice','19','--output',str(dest)]
        if rank==1:command+=['--draft-mtp']
        result=subprocess.run(command,stdin=subprocess.DEVNULL,capture_output=True,text=True,env=dict(os.environ,OMP_NUM_THREADS='2'),timeout=900)
        assert result.returncode==0,result.stderr
        row=json.loads((dest/'result.json').read_text());assert row['passed'] and row['prepared']
        startup_census=json.loads((dest/'census.json').read_text())['totals']['device']
        assert startup_census==census[(selection,rank)],'real-parser startup census differs from the bracket fixture'
        startup_runs.append(dict(selection=selection,rank=rank,command=command,result=row,device_census_bytes=startup_census,artifact=retain(dest)))
        print('selected real-parser startup',selection,rank,'PASS',flush=True)
    memory_rows=[dict(selection=s,rank=r,device_allocation_bytes=census[(s,r)],arena_headroom_bytes=32212254720-census[(s,r)],
                      physical_free_bytes=34242297856-census[(s,r)]) for s in SELECTIONS for r in (0,1)]
    save(P/'evidence/full-shape.json',dict(passed=True,device_executed=False,model_payload_read=False,
        runs=runs,startup_runs=startup_runs,binary_sha256=sha(out/'fixture'),commands=[compile_cmd,audit_cmd,audit_dispatch,audit_s1,link],
        head_sites=heads,draft_commands_identical=draft_same,memory=memory_rows,census_delta_bytes_per_rank=delta,
        unsplit_memory_plan=str(target.relative_to(ROOT)),unsplit_memory_plan_sha256=sha(target),
        one_load_switch_refused='bracket_select refuses head head-split-compute <-> production in both directions (storage choice); allocations differ by the census delta',
        sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'p185_v5_full_shape.py',P/'p183_shape_mock.py',P/'native/full_shape_entry.cpp',P/'native/audit_s1.hpp',CHECKED/'s1_kernels.hpp',*selections.values(),P/'lineage/production/memory-plan.json',target,*out.glob('*.cpp'),*out.glob('*.hpp')]},
        payload_mocks=['numerical device addresses','weight upload elision','scalar readback','state-dump payload elision'],
        real_paths=['initialize','banks','SpeculativeImage','DraftRuntime','bracket_select','request_reset','bracket_boundary','p105::Runtime (split only)','memory admission']))
    limits()
if __name__=='__main__':
 import resource
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
