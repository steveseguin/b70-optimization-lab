"""Packet186 production-shape gate: every selection, both ranks, both start orders, real entry code.

Real v5 main.cpp/mtp.hpp/rank.hpp (V3 boundary, vendored strict_snapshot.hpp) with numerical device
addresses and no payload (packet183 fixture generator). Loads, each with five bracket resets:
  * production (bundle 8: split head, rank 0 holds 0-23) re-selecting itself;
  * the V3 dual layout started from U (U/V3/U/V3/U) and from V3 (V3/U/V3/U/V3).
Per load and rank: fresh startup, reset extents, arena identity, capture identity of every view
with the fresh startup (the U <-> V3 switch changes which sites a half issues, never a capture),
native refusals (storage keys, closed values), half-skip census per view, the speculative-image
census (rank 0: no layer-24/25 buffer captured), the banked-state census, the allocation census
and the issued command list. Command comparisons: rank 0 dual = production + the layer-24/25
sites, whose kernels/shapes/bindings equal rank 1's own layer-24/25 sites; rank 1 dual = production
except the target-head sites (the packet185 unsplit head). Census deltas derive the dual memory plan
(lineage/u|v3/memory-plan.json) from the production ledger. The production captures must equal
packet185's retained production captures (bundle-8 identity of the rebuilt engine sources).
Real-parser startup (--startup109) of every selection on both ranks must reproduce the census.
"""
import importlib.util,json,subprocess,time,sys,os
from pathlib import Path
from p186_v5_build_engine import P,ROOT,BASE,B,sha,save,limits,compiler_turn
from p186_v5_build_engine import CHECKED,LOCAL
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


SELECTIONS=('production','u','v3')
LOADS=(('production','production','production'),('u-first','u','v3'),('v3-first','v3','u'))
PLAN_KEYS=('target_modeled_allocations_bytes','target_total_bytes','total_with_mtp_bytes','arena_device_bytes')
MOVED=('blk.24.','blk.25.')
P185=BASE/'lineage-inputs/packet185-own/v5/evidence/full-shape.json'


def key(x,with_operation=True):
    return (x['label'],x['op'],x['kernel'],tuple(x['shape']),x['operation_sha'] if with_operation else None,
            tuple((y['label'],y['bytes'],y['category']) for y in x['bindings']))


def head(x):
    return x['label'] in ('logits','argmax') or x['label'].startswith('final.') and any('output.weight' in y['label'] for y in x['bindings'])


def compare_launches(out):
    """rank 0 dual = production + moved sites; moved sites = rank 1's own; rank 1 dual = production except head."""
    load=lambda name,rank:json.loads((out/f'{name}-rank{rank}'/'launches-view0.json').read_text())
    p0,u0,p1,u1=load('production',0),load('u-first',0),load('production',1),load('u-first',1)
    moved=lambda x:x['label'].startswith(MOVED)
    a=[key(x,False) for x in p0];b=[key(x,False) for x in u0 if not moved(x)]
    assert a==b,'rank 0: non-moved commands differ between production and the V3 dual layout'
    m0=[key(x,False) for x in u0 if moved(x)];m1=[key(x,False) for x in p1 if moved(x)]
    assert m0 and m0==m1,'rank 0 must issue exactly rank 1\'s layer-24/25 kernels, shapes and bindings'
    c=[key(x) for x in p1 if not head(x)];d=[key(x) for x in u1 if not head(x)]
    assert c==d,'rank 1: non-head commands differ between production and the dual layout'
    rows=lambda xs:[dict(label=x['label'],op=x['op'],kernel=x['kernel'],shape=x['shape'],bindings=[dict(label=y['label'],bytes=y['bytes']) for y in x['bindings']]) for x in xs]
    return dict(rank0_production_commands=len(p0),rank0_dual_commands=len(u0),rank0_moved_commands=len(m0),
                rank1_commands=len(p1),rank1_identical_non_head=len(c),
                rank1_split_head_sites=rows([x for x in p1 if head(x)]),rank1_full_head_sites=rows([x for x in u1 if head(x)]),
                moved_kernels=sorted({x['kernel'] for x in u0 if moved(x)}))


def derive_dual_plan(census):
    """Production ledger + measured census delta per rank (actual allocation calls)."""
    plan=json.loads((P/'lineage/production/memory-plan.json').read_text())
    delta=[census[('u-first',r)]-census[('production',r)] for r in (0,1)]
    row=plan['placements']['1']['capacities']['4096']['ranks']
    for r in row:
        d=delta[r['rank']]
        for k in PLAN_KEYS:r[k]+=d
        r['free_with_mtp_bytes']=plan['capacity_bytes']-r['total_with_mtp_bytes']
        r['arena_headroom_bytes']=plan['arena_limit_bytes']-r['arena_device_bytes']
        r['allocation_margin_passed']=r['free_with_mtp_bytes']>=plan['minimum_free_bytes']
        r['arena_margin_passed']=r['arena_headroom_bytes']>=0
        if r['rank']==0:r['target_layers']=26
    plan['view']=plan['view'].replace('--fused--split--','--fused--production--').replace('--banks','--banks--v3-dual')
    assert '--production--80128--' in plan['view'] and plan['view'].endswith('--v3-dual')
    plan['scope']=('packet186: packet183/153 production ledger plus the measured production-shape census delta of the V3 dual '
                   'layout (rank 0 also loads layers 24-25 and no suffix head rows; rank 1 loads all 248,320 head rows and keeps '
                   'layers 24-47); physical driver residency unmeasured')
    plan['packet186_census_delta_bytes_per_rank']=delta
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
    for (label,first,second),rank in __import__('itertools').product(LOADS,(0,1)):
        a,b=selections[first],selections[second];dest=out/f'{label}-rank{rank}';dest.mkdir(exist_ok=True)
        cmd=[str(out/'fixture'),str(a),sha(a),str(rank),str(dest),str(b),sha(b)]
        started=time.monotonic()
        with (dest/'run.log').open('w') as log:
            subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=900)
        row=json.loads((dest/'census.json').read_text());census[(label,rank)]=row['totals']['device']
        result=json.loads((dest/'result.json').read_text())
        extended=label!='production'
        assert result['passed'] and result['views']==5 and result['fresh_start_capture_identity'] and result['layout_refused']
        assert result['native_refusals']==(19 if extended else 16) and result['rank0_extended']==extended,result
        assert all(v==result['initial_capture'] for v in result['view_captures']),'re-selected/switched capture differs'
        v3load=json.loads((dest/'v3-load.json').read_text())
        raw[(label,rank)]=dict(dest=dest,command=cmd,wall_seconds=time.monotonic()-started,result=result,census_row=row,v3_load=v3load)
        print('full-shape',label,'rank',rank,'PASS',flush=True)
    # Both start orders of the dual load are the same storage: identical census and captures.
    for rank in (0,1):
        assert census[('u-first',rank)]==census[('v3-first',rank)],'start order changed allocations'
        assert raw[('u-first',rank)]['result']['initial_capture']==raw[('v3-first',rank)]['result']['initial_capture'],'start order changed captures'
    moved0=raw[('u-first',0)]['v3_load']['moved_sites'];skip=lambda label,rank:raw[(label,rank)]['result']['half_skips_per_view']
    assert moved0>0 and skip('production',0)==[0]*5 and skip('production',1)==[0]*5 and skip('u-first',0)==[moved0]*5 and skip('v3-first',0)==[moved0]*5
    assert skip('u-first',1)==[0,moved0,0,moved0,0] and skip('v3-first',1)==[moved0,0,moved0,0,moved0],'rank-1 half skip census'
    private=raw[('u-first',0)]['v3_load']['private_buffers']
    assert private and all(n.startswith(MOVED) for n in private),'V3 private set must be exactly layer-24/25 buffers'
    banked=lambda label:raw[(label,0)]['v3_load']['banked_state']
    assert banked('u-first')==banked('production') and not any(n.startswith(MOVED) for n in banked('u-first')),'layers 24-25 must not be banked'
    images={label:json.loads((out/f'{label}-rank0'/'image-census.json').read_text()) for label in ('production','u-first','v3-first')}
    names=lambda label:[s['name'] for s in images[label]['sources']]
    assert not any(n.startswith(MOVED) for n in names('u-first')),'a layer-24/25 buffer is in the speculative image'
    assert images['u-first']['capture_bytes']==images['production']['capture_bytes'] and images['u-first']['extents']==images['production']['extents'],'speculative capture changed'
    plan,delta=derive_dual_plan(census)
    for line in ('u','v3'):
        target=P/'lineage'/line/'memory-plan.json'
        if not target.exists():save(target,plan)
        assert json.loads(target.read_text())==plan,'dual memory plan differs from its measured derivation: '+line
    launches=compare_launches(out)
    draft_same=(out/'production-rank1/draft-kernels-view0.txt').read_text()==(out/'u-first-rank1/draft-kernels-view0.txt').read_text()
    assert draft_same,'draft commands differ between layouts'
    parent=json.loads(P185.read_text());parent_capture={(r['selection'],r['rank']):r['result']['initial_capture'] for r in parent['runs']}
    bundle8_identity=all(raw[('production',r)]['result']['initial_capture']==parent_capture[('production',r)] for r in (0,1))
    assert bundle8_identity,'production captures differ from packet185 bundle 8'
    runs=[]
    for (label,rank),row in raw.items():
        ledger=json.loads((P/'lineage'/('production' if label=='production' else 'u')/'memory-plan.json').read_text())
        memory=check(row['census_row'],ledger,rank,mtp=True,context=4096,draft_rank=1,target_split=0)
        runs.append(dict(load=label,rank=rank,command=row['command'],wall_seconds=row['wall_seconds'],memory=memory,
                         result=row['result'],v3_load=row['v3_load'],artifact=retain(row['dest'])))
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
        expected=census[('production' if selection=='production' else 'u-first',rank)]
        assert startup_census==expected,'real-parser startup census differs from the bracket fixture'
        startup_runs.append(dict(selection=selection,rank=rank,command=command,result=row,device_census_bytes=startup_census,artifact=retain(dest)))
        print('selected real-parser startup',selection,rank,'PASS',flush=True)
    memory_rows=[dict(layout=label,rank=r,device_allocation_bytes=census[(label,r)],arena_headroom_bytes=32212254720-census[(label,r)],
                      physical_free_bytes=34242297856-census[(label,r)]) for label in ('production','u-first') for r in (0,1)]
    save(P/'evidence/full-shape.json',dict(passed=True,device_executed=False,model_payload_read=False,
        runs=runs,startup_runs=startup_runs,binary_sha256=sha(out/'fixture'),commands=[compile_cmd,audit_cmd,audit_dispatch,audit_s1,link],
        launches=launches,draft_commands_identical=draft_same,memory=memory_rows,census_delta_bytes_per_rank=delta,
        bundle8_capture_identity_with_packet185=bundle8_identity,image_census={k:dict(capture_bytes=v['capture_bytes'],extents=v['extents'],sources=len(v['sources'])) for k,v in images.items()},
        v3_private_buffers=private,moved_sites_rank0=moved0,
        dual_memory_plan=str((P/'lineage/u/memory-plan.json').relative_to(ROOT)),dual_memory_plan_sha256=sha(P/'lineage/u/memory-plan.json'),
        one_load_switch='U <-> V3 (boundary, snapshot_host) switch in-load with identical captures in both start orders; rank0_layers/head/dense_scales refuse',
        sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'p186_v5_full_shape.py',P/'p183_shape_mock.py',P/'native/full_shape_entry.cpp',P/'native/audit_s1.hpp',CHECKED/'s1_kernels.hpp',*selections.values(),P/'lineage/production/memory-plan.json',P/'lineage/u/memory-plan.json',P/'lineage/v3/memory-plan.json',P185,*out.glob('*.cpp'),*out.glob('*.hpp')]},
        payload_mocks=['numerical device addresses','weight upload elision','scalar readback','state-dump payload elision'],
        real_paths=['initialize','refresh_v3/v3_check_plan','banks','SpeculativeImage','DraftRuntime','bracket_select','request_reset','bracket_boundary','p105::Runtime (split only)','memory admission']))
    limits()
if __name__=='__main__':
 import resource
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
