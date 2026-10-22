"""Packet188 production-shape gate: every selection, both ranks, both start orders, real entry code.

Real v5 main.cpp/mtp.hpp/rank.hpp (k3 storage, trims, V3 boundary, vendored strict_snapshot.hpp) with numerical
device addresses and no payload (packet183 fixture generator). Loads, each with five bracket resets:
  * v3: packet187's record selection (0-25 storage) re-selecting itself; its captures must equal packet186's
    retained V3 captures (the record-line engine path is byte-identical in its prepared commands);
  * the k3 storage (rank0_layers 0-26) started from v3k (V3/k3+trims/V3/k3+trims/V3) and from k3trims
    (k3+trims/V3/...), plus k3/k3kio and k3prep/k3trims loads (every trim combination switched in-load).
Per load and rank: fresh startup, reset extents, arena identity, capture identity of every view with the
fresh startup (boundary/trim switches change which sites a half or a boundary issues, never a capture),
native refusals (storage keys, closed values, k3/0-25 cross values), half-skip census per view, the
speculative-image census (rank 0: no layer-24/25/26 buffer captured), the banked-state census, the
allocation census, the pinned kernel-io staging and the issued command list. Command comparisons: rank 0
k3 storage = V3 storage + the layer-26 sites, whose kernels/shapes/bindings equal rank 1's own layer-26
sites; rank 1 k3 storage = rank 1 V3 storage exactly. The census delta derives the k3 memory plan from the
v3 plan. Real-parser startup (--startup109) of every selection on both ranks must reproduce the census.
"""
import importlib.util,json,subprocess,time,sys,os
from pathlib import Path
from p188_v5_build_engine import P,ROOT,BASE,B,sha,save,limits,compiler_turn
from p188_v5_build_engine import CHECKED,LOCAL
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
        .replace('P98_PARENT_PATH',json.dumps(str(BASE))).replace('P185_DISPATCH_PATH',json.dumps(str(P/'lineage/v3/dispatch-speed6.json'))))
    return out


SELECTIONS=('v3','v3k','k3trims','k3','k3kio','k3prep')
K3=('v3k','k3trims','k3','k3kio','k3prep')
LOADS=(('v3','v3','v3'),('v3k-first','v3k','k3trims'),('k3trims-first','k3trims','v3k'),('k3-first','k3','k3kio'),('k3prep-first','k3prep','k3trims'))
K3_LOADS=tuple(l for l,_,_ in LOADS if l!='v3')
PLAN_KEYS=('target_modeled_allocations_bytes','target_total_bytes','total_with_mtp_bytes','arena_device_bytes')
MOVED=('blk.24.','blk.25.','blk.26.')
P186=BASE/'lineage-inputs/packet186-own/v5/evidence/full-shape.json'
# view sequence per load (control = argv 1, candidate = argv 5; views alternate control/candidate)
def views(first,second):return [first,second,first,second,first]


def key(x,with_operation=True):
    return (x['label'],x['op'],x['kernel'],tuple(x['shape']),x['operation_sha'] if with_operation else None,
            tuple((y['label'],y['bytes'],y['category']) for y in x['bindings']))


def compare_launches(out):
    """rank 0 k3 storage = V3 storage + layer-26 sites (= rank 1's own layer-26 sites); rank 1 identical."""
    load=lambda name,rank:json.loads((out/f'{name}-rank{rank}'/'launches-view0.json').read_text())
    v0,k0,v1,k1=load('v3',0),load('v3k-first',0),load('v3',1),load('v3k-first',1)
    l26=lambda x:x['label'].startswith('blk.26.')
    a=[key(x,False) for x in v0];b=[key(x,False) for x in k0 if not l26(x)]
    assert a==b,'rank 0: non-layer-26 commands differ between the V3 and k3 storages'
    m0=[key(x,False) for x in k0 if l26(x)];m1=[key(x,False) for x in v1 if l26(x)]
    assert m0 and m0==m1,'rank 0 must issue exactly rank 1\'s layer-26 kernels, shapes and bindings'
    c=[key(x) for x in v1];d=[key(x) for x in k1]
    assert c==d,'rank 1: commands differ between the V3 and k3 storages'
    return dict(rank0_v3_commands=len(v0),rank0_k3_commands=len(k0),rank0_layer26_commands=len(m0),rank1_commands=len(v1),
                rank1_identical=True,layer26_kernels=sorted({x['kernel'] for x in k0 if l26(x)}))


def derive_k3_plan(census):
    """V3 ledger + measured census delta per rank (actual allocation calls)."""
    plan=json.loads((P/'lineage/v3/memory-plan.json').read_text())
    delta=[census[('v3k-first',r)]-census[('v3',r)] for r in (0,1)]
    row=plan['placements']['1']['capacities']['4096']['ranks']
    for r in row:
        d=delta[r['rank']]
        for k in PLAN_KEYS:r[k]+=d
        r['free_with_mtp_bytes']=plan['capacity_bytes']-r['total_with_mtp_bytes']
        r['arena_headroom_bytes']=plan['arena_limit_bytes']-r['arena_device_bytes']
        r['allocation_margin_passed']=r['free_with_mtp_bytes']>=plan['minimum_free_bytes']
        r['arena_margin_passed']=r['arena_headroom_bytes']>=0
        if r['rank']==0:r['target_layers']=27
    plan['view']=plan['view'].replace('--v3-dual','--k3-dual')
    assert plan['view'].endswith('--k3-dual'),plan['view']
    plan['scope']=('packet188: packet186 V3 dual ledger plus the measured production-shape census delta of the k3 storage '
                   '(rank 0 also loads GDN layer 26; rank 1 unchanged); pinned kernel-io staging is host memory; '
                   'physical driver residency unmeasured')
    plan.pop('packet186_census_delta_bytes_per_rank',None);plan['packet188_census_delta_bytes_per_rank']=delta
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
            r=subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=900)
        assert r.returncode==0,(label,rank,(dest/'run.log').read_text()[-3000:])
        row=json.loads((dest/'census.json').read_text());census[(label,rank)]=row['totals']['device']
        result=json.loads((dest/'result.json').read_text())
        assert result['passed'] and result['views']==5 and result['fresh_start_capture_identity'] and result['layout_refused']
        assert result['native_refusals']==21 and result['rank0_extended'] is True,result
        assert all(v==result['initial_capture'] for v in result['view_captures']),'re-selected/switched capture differs'
        v3load=json.loads((dest/'v3-load.json').read_text())
        raw[(label,rank)]=dict(dest=dest,command=cmd,wall_seconds=time.monotonic()-started,result=result,census_row=row,v3_load=v3load,views=views(first,second))
        print('full-shape',label,'rank',rank,'PASS',flush=True)
    # Every k3-storage load is the same storage: identical census and captures whatever the start selection.
    for rank in (0,1):
        for label in K3_LOADS:
            assert census[(label,rank)]==census[('v3k-first',rank)],'start selection changed allocations: '+label
            assert raw[(label,rank)]['result']['initial_capture']==raw[('v3k-first',rank)]['result']['initial_capture'],'start selection changed captures: '+label
    # Record-line identity: packet188's V3 (0-25) load captures equal packet186's retained V3 captures.
    parent=json.loads(P186.read_text());parent_capture={(r['load'],r['rank']):r['result']['initial_capture'] for r in parent['runs']}
    v3_identity=all(raw[('v3',r)]['result']['initial_capture']==parent_capture[('v3-first',r)] for r in (0,1))
    assert v3_identity,'V3 captures differ from packet186'
    parent_census={(r['load'],r['rank']):r['memory'] for r in parent['runs']}
    stored0=raw[('v3k-first',0)]['v3_load']['stored_sites'];v3stored0=raw[('v3',0)]['v3_load']['stored_sites']
    skip=lambda label,rank:raw[(label,rank)]['result']['half_skips_per_view']
    # Rank-1 skip counts: V3 view = layers 24-25 sites, k3 view = 24-26 sites (counted from the rank-1 command list).
    assert skip('v3',0)==[v3stored0]*5 and skip('v3',1)==[skip('v3',1)[0]]*5 and skip('v3',1)[0]>0,'V3 half-skip census'
    k2_skip,k3_skip=skip('v3',1)[0],skip('k3-first',1)[0]
    assert k3_skip>k2_skip and stored0>v3stored0,'k3 skips/stored sites'
    for label in K3_LOADS:
        assert skip(label,0)==[stored0]*5,'rank-0 half skip census (all stored moved sites): '+label
        expected=[k3_skip if s!='v3k' else k2_skip for s in raw[(label,1)]['views']]
        assert skip(label,1)==expected,('rank-1 half skip census',label,skip(label,1),expected)
    private=raw[('v3k-first',0)]['v3_load']['private_buffers']
    assert private and all(n.startswith(MOVED) for n in private) and any(n.startswith('blk.26.') for n in private),'k3 private set must be exactly layer-24/25/26 buffers'
    banked=lambda label:raw[(label,0)]['v3_load']['banked_state']
    assert banked('v3k-first')==banked('v3') and not any(n.startswith(MOVED) for n in banked('v3k-first')),'layers 24-26 must not be banked'
    kio=raw[('v3k-first',0)]['v3_load'];assert kio['kio_cards']==1 and kio['kio_bytes']>0 and raw[('v3',0)]['v3_load']['kio_cards']==0,'kernel-io staging only in the k3 storage'
    images={label:json.loads((out/f'{label}-rank0'/'image-census.json').read_text()) for label,_,_ in LOADS}
    names=lambda label:[s['name'] for s in images[label]['sources']]
    for label in K3_LOADS:
        assert not any(n.startswith(MOVED) for n in names(label)),'a layer-24/25/26 buffer is in the speculative image: '+label
        assert images[label]['capture_bytes']==images['v3']['capture_bytes'] and images[label]['extents']==images['v3']['extents'],'speculative capture changed: '+label
    plan,delta=derive_k3_plan(census)
    for line in K3:
        target=P/'lineage'/line/'memory-plan.json'
        if not target.exists():save(target,plan)
        assert json.loads(target.read_text())==plan,'k3 memory plan differs from its measured derivation: '+line
    launches=compare_launches(out)
    draft_same=(out/'v3-rank1/draft-kernels-view0.txt').read_text()==(out/'v3k-first-rank1/draft-kernels-view0.txt').read_text()
    assert draft_same,'draft commands differ between layouts'
    runs=[]
    for (label,rank),row in raw.items():
        ledger=json.loads((P/'lineage'/('v3' if label=='v3' else 'v3k')/'memory-plan.json').read_text())
        memory=check(row['census_row'],ledger,rank,mtp=True,context=4096,draft_rank=1,target_split=0)
        runs.append(dict(load=label,rank=rank,views=row['views'],command=row['command'],wall_seconds=row['wall_seconds'],memory=memory,
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
        expected=census[('v3' if selection=='v3' else 'v3k-first',rank)]
        assert startup_census==expected,'real-parser startup census differs from the bracket fixture'
        startup_runs.append(dict(selection=selection,rank=rank,command=command,result=row,device_census_bytes=startup_census,artifact=retain(dest)))
        print('selected real-parser startup',selection,rank,'PASS',flush=True)
    memory_rows=[dict(layout=label,rank=r,device_allocation_bytes=census[(label,r)],arena_headroom_bytes=32212254720-census[(label,r)],
                      physical_free_bytes=34242297856-census[(label,r)]) for label in ('v3','v3k-first') for r in (0,1)]
    v3_parent_memory=[dict(rank=r,device_allocation_bytes=next(x['device_allocation_bytes'] for x in parent['memory'] if x['layout']=='u-first' and x['rank']==r)) for r in (0,1)]
    assert all(census[('v3',r)]==v3_parent_memory[r]['device_allocation_bytes'] for r in (0,1)),'V3 census differs from packet186'
    save(P/'evidence/full-shape.json',dict(passed=True,device_executed=False,model_payload_read=False,
        runs=runs,startup_runs=startup_runs,binary_sha256=sha(out/'fixture'),commands=[compile_cmd,audit_cmd,audit_dispatch,audit_s1,link],
        launches=launches,draft_commands_identical=draft_same,memory=memory_rows,census_delta_bytes_per_rank=delta,
        v3_capture_identity_with_packet186=v3_identity,v3_census_identity_with_packet186=True,
        image_census={k:dict(capture_bytes=v['capture_bytes'],extents=v['extents'],sources=len(v['sources'])) for k,v in images.items()},
        k3_private_buffers=private,stored_sites_rank0=dict(v3=v3stored0,k3=stored0),rank1_half_skips=dict(v3_view=k2_skip,k3_view=k3_skip),
        kernel_io_staging=dict(bytes=kio['kio_bytes'],stage_bytes=kio['kio_stage_bytes'],memory='pinned host (Memory::pinned), k3 storage only'),
        k3_memory_plan=str((P/'lineage/v3k/memory-plan.json').relative_to(ROOT)),k3_memory_plan_sha256=sha(P/'lineage/v3k/memory-plan.json'),
        one_load_switch='V3 <-> k3+trims (boundary rank0/rank0-k3, kernel_io, rank0_prepare) in-load with identical captures in both start orders; rank0_layers/head/dense_scales refuse',
        sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'p188_v5_full_shape.py',P/'p183_shape_mock.py',P/'native/full_shape_entry.cpp',P/'native/audit_s1.hpp',CHECKED/'s1_kernels.hpp',*selections.values(),P/'lineage/v3/memory-plan.json',*[P/'lineage'/s/'memory-plan.json' for s in K3],P186,*out.glob('*.cpp'),*out.glob('*.hpp')]},
        payload_mocks=['numerical device addresses','weight upload elision','scalar readback','state-dump payload elision','compute operations recorded, not executed'],
        real_paths=['initialize (incl. allocate_kio)','refresh_v3/v3_check_plan (k3 island)','banks','SpeculativeImage','DraftRuntime','bracket_select (trim domains)','request_reset','bracket_boundary','memory admission']))
    limits()
if __name__=='__main__':
 import resource
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
