"""Source-only Engine allocation ledger. No compiler, binary, model or Device access."""
from pathlib import Path
import collections,copy,hashlib,json,math,re,os,resource
P=Path(__file__).resolve().parent;ROOT=P.parents[3];LANE=P.parent
PRIVATE=LANE/'integration/build/private';SRC=PRIVATE/'source/diet-native/native-src';BASE=PRIVATE/'source/diet-native/native-base/experiments/own-xpu-runtime/stage2'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read=lambda p:json.loads(Path(p).read_text())
GIB=1024**3

def total(rows):return sum(r['bytes'] for r in rows)
def row(name,size,kind,**kw):return dict(name=name,bytes=size,kind=kind,**kw)
def size(b):return math.prod(b['shape'])*b['element_bytes']

def flatten(graph):
    # Exact gsq_build_plan(a.cards=1) semantics; rank split runs afterward.
    p=copy.deepcopy(graph)
    p['launches']=[l for l in p['launches'] if l['op'] not in ('handoff','handoff_result') and l['label'] not in ('begin.1','commit.0')]
    for b in p['buffers']:b['card']=0
    for l in p['launches']:l['card']=0;l['source_card']=-1
    return p

def split(p,rank,boundary):
    launches=[]
    for l in p['launches']:
        if l['label'].startswith('blk.'):
            layer=int(l['label'].split('.')[1]);keep=layer<boundary if rank==0 else layer>=boundary
        elif l['op'] in ('begin','commit'):keep=True
        else:keep=(rank==0) if l['label'] in ('embedding','streams') else (rank==1)
        if keep:launches.append(l)
    used={'streams','token','position','active','error','next_token'}
    for l in launches:used.update(l['inputs']);used.update(l['outputs'])
    return {'launches':launches,'buffers':[b for b in p['buffers'] if b['name'] in used]}

def draft_allocations(graph,draftweights):
    # Builder(g).build({true}) has the same QSA/MoE block as blk.3 of the
    # retained real plan; no directory-dependent buffer shapes. No layer1 PLE.
    buffers=[]
    for b in graph['buffers']:
        if b['name'].startswith('blk.3.'):
            b=copy.deepcopy(b);b['name']='blk.0.'+b['name'][6:];buffers.append(b)
        elif not b['name'].startswith('blk.') and b['name'] not in ('token_history','ple_metadata'):buffers.append(b)
    assert len({b['name'] for b in buffers})==len(buffers)
    allocations=[row('draft:'+b['name'],size(b),'draft_plan_buffer',shape=b['shape'],scalar_bytes=b['element_bytes']) for b in buffers]
    for name,elements in [('merge.hidden',4*2560),('merge.norm',4*2560),('merge.projected',4*2560),('merge.embedding_norm',2560),('merge.embedding_projected',2560)]:allocations.append(row('draft:'+name,elements*2,'draft_merge_buffer'))
    for name,n in [('scratch',8*1024**2),('controls',12),('scores',24*2051*4),('probabilities',24*2051*4),('head-workspace',248320*8*4),('head-fp32',2560*4)]:allocations.append(row('draft:'+name,n,'draft_auxiliary'))
    assert draftweights['device_expert_int8_g16_bytes']+draftweights['dense_and_gain_device_bytes']==3326953472
    return allocations

def rank_account(p,census,controls,rank,mtp,draft_rank,boundary,draftrows,draftweights):
    allocations=[];weights={}
    for l in p['launches']:
        if l['op']=='lookup':continue
        for name in l['weights']:
            t=census['tensors'][name];raw=t['bytes'];stored=raw
            if name in controls:stored=controls[name]['upload_bytes']
            if name=='output.weight':stored=248320*3380
            weights[name]=row(name,stored,'target_weight',source_bytes=raw,type=t['type'],delta=stored-raw)
    allocations.extend(weights.values())
    buffers={b['name']:b for b in p['buffers']}
    for name,b in buffers.items():
        kind='target_activation_or_control'
        if name.endswith(('.state','history')):kind='target_recurrent'
        if name.endswith(('.keys','.values','.pooled','.raw')):kind='target_kv'
        allocations.append(row(name,size(b),kind,shape=b['shape'],scalar_bytes=b['element_bytes']))
    aux=[('parallel-controls',12),('attention-scores',24*2051*4),('attention-probabilities',24*2051*4),('layer-snapshots',48*4*2560*2),('prepared-fp32-input',174080*4),('gemv-workspace',8*1024**2),('compact-routes',10*12),('ordered-mixture',2560*2),('mixture-one',4),('rope-v2',32768*128),('operator-scratch',256*1024**2)]
    allocations.extend(row(n,b,'target_auxiliary') for n,b in aux)
    # Real run_rank unconditionally constructs p149 Exchange on full shapes.
    allocations.append(row('p149:discard',65536,'target_probe_auxiliary'))
    banks=[];snapshot_names=[];snapshot_aux=[]
    if rank==0:
        for l in p['launches']:
            if l['op'] in ('conv','gdn'):
                assert len(l['outputs'])==2 and l['outputs'][1] in l['inputs']
                name=l['outputs'][1];assert name not in banks;banks.append(name)
                allocations.append(row('alternate:'+name,size(buffers[name]),'target_alternate_recurrent'))
        outputs={'token','position','token_history'}
        for l in p['launches']:outputs.update(l['outputs'])
        snapshot_names=[n for n in buffers if n in outputs]
        # Default miss=control, no third-bank/reserve, no V3 private, no head split.
        snapshot_aux=[(n,b) for n,b in aux if n not in ('rope-v2','mixture-one')]
        snapshot=sum(size(buffers[n]) for n in snapshot_names)+sum(b for n,b in snapshot_aux)
        allocations.append(row('speculative-private-image',snapshot,'target_snapshot_backup'))
    else:snapshot=0
    before_draft=total(allocations)
    if mtp and rank==draft_rank:
        for name,group in draftweights['expert_groups'].items():allocations.append(row('draft:expert-'+name,group['bytes'],'draft_expert_weights'))
        for t in draftweights['nonexpert_tensors']:
            if t['name'].endswith('index_qk_proj.weight'):
                for which in ('q','k'):allocations.append(row('draft:index-'+which,draftweights['index_projection_split'][which+'_device_bytes'],'draft_dense_gain_weights'))
            else:allocations.append(row('draft:'+t['name'],t['device_bytes'],'draft_dense_gain_weights'))
        allocations.extend(copy.deepcopy(draftrows))
        if 'output.weight' not in weights:allocations.append(row('draft:shared-head-host',248320*3380,'draft_private_full_head',allocation_count=1))
    pinned=[row('bounded-copy',4*1024**2,'host_pinned'),row('p149:staging',65536,'host_pinned')]
    if mtp and rank==draft_rank:pinned.extend([row('draft:publication',8,'host_pinned'),row('draft:half-staging',4+4*2560*2,'host_pinned')])
    device=total(allocations);categories=collections.Counter()
    for a in allocations:categories[a['kind']]+=a['bytes']
    count=sum(a.get('allocation_count',1) for a in allocations)
    # Illustrative reservation envelopes, not a measured/runtime allocator rule.
    rounded64k=sum(((a['bytes']+65535)//65536)*65536 if a.get('allocation_count',1)==1 else ((a['bytes']+65535)//65536)*65536+65535*(a['allocation_count']-1) for a in allocations)
    return dict(rank=rank,layers=[0,boundary-1] if rank==0 else [boundary,47],launches=len(p['launches']),plan_buffers=len(buffers),target_weight_count=len(weights),target_raw_loaded_bytes=sum(t['source_bytes'] for t in weights.values()),target_weight_bytes=total(list(weights.values())),target_weight_delta=sum(t['delta'] for t in weights.values()),target_before_draft_bytes=before_draft,device_logical_bytes=device,GiB=device/GIB,arena30GiB_headroom=30*GIB-device,card32GiB_unreserved=32*GIB-device,within30GiB_logical=device<=30*GIB,device_allocation_count=count,categories=dict(categories),illustrative_64KiB_perallocation_upper_bytes=rounded64k,illustrative_64KiB_headroom_30GiB=30*GIB-rounded64k,pinned_host_bytes=total(pinned),pinned_host=pinned,allocations=allocations,snapshot=dict(backup_bytes=snapshot,full_plan_sources=snapshot_names,standalone_sources=[n for n,b in snapshot_aux],bank_names=banks,third_banks=False,copy_tables_bytes=0,static_snapshot=False,initialization_status='source paths reviewed only; full Engine not executed'))

def main():
    assert os.getpriority(os.PRIO_PROCESS,0)==19 and set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
    graph=read(LANE/'graph/new-plan.json');census=read(LANE/'metadata/new-census.json');controls={r['name']:r for r in read(LANE/'controls/manifest.json')['rows']};draftweight=read(P/'draft-weight-accounting.json')
    main=(SRC/'main.cpp').read_text();rank=(SRC/'rank.hpp').read_text();mtp=(SRC/'mtp.hpp').read_text();snapshot=(SRC/'strict_snapshot.hpp').read_text()
    assert 'if(a.gsq_packed)return gsq_build_plan(w,a);' in main
    assert 'draft_rank==0?22:24' in rank and 'if(a.rank==0)banks(*engine)' in rank
    assert 'constexpr size_t legacy=256ull*1024*1024' in main
    assert 'rows.size()*sizeof(SnapshotStatic::Item)' in snapshot and 'zero_private();if(!e.a.gsq_packed||static_mode())prepare_static();' in snapshot
    assert 'if(e.a.rank!=0)return;' in snapshot
    assert 'scratch=alloc("scratch",8*1024*1024)' in mtp and 'size_t(p.g.vocab)*8*4' in mtp
    assert 'e.a.gsq_packed?p.g.vocab' in mtp
    admission=(PRIVATE/'additive/admission.hpp').read_text()
    assert 'if(a.gsq_packed)gsq_integration::baseline_selection(sealed_selection);' in main
    assert '{"snapshot_host","production"}' in admission and 's.draft=p59c::defaults()' in admission
    headers=read(LANE/'integration/evidence/header-check.json')
    assert headers['result']['launches']==1869 and headers['result']['rank_controller_defaults_checked']
    # The inherited Builder body is identical across the graph proof and native
    # materialization except generated guards/line labels/quoted include paths.
    def normalized(text):
        return '\n'.join(x for x in text.splitlines() if not x.startswith(('#line ','#include "')))
    assert normalized((BASE/'packet3/step/plan.hpp').read_text())==normalized((ROOT/'experiments/own-xpu-runtime/stage2/packet3/step/plan.hpp').read_text())
    for b in graph['buffers']:
        if b['name'].endswith(('.keys','.values')):assert b['shape']==[4096,2,256]
        if b['name'].endswith('.raw'):assert b['shape']==[4096,128]
        if b['name'].endswith('.pooled'):assert b['shape']==[1024,128]

    p=flatten(graph);assert len(p['launches'])==headers['result']['launches'];draftrows=draft_allocations(graph,draftweight)
    scenarios={}
    for boundary in (22,23,24):
        for mtp_on in (False,True):
            key=f'split{boundary}-{48-boundary}_'+('mtp-rank0' if mtp_on else 'target-only')
            scenarios[key]={'target_split_argument':0 if boundary==22 else boundary,'draft_rank':0,'mtp':mtp_on,'ranks':[rank_account(split(p,r,boundary),census,controls,r,mtp_on,0,boundary,draftrows,draftweight) for r in (0,1)]}
    # Cross-check the complete ledger independently of split membership totals.
    expected_weights={n for n,t in census['tensors'].items() if n not in ('token_embd.weight','per_layer_token_embd.weight')}
    for scenario in scenarios.values():
        ranks=scenario['ranks'];sets=[]
        for r in ranks:
            assert r['device_logical_bytes']==sum(r['categories'].values())==total(r['allocations'])
            names=[a['name'] for a in r['allocations']];assert len(names)==len(set(names))
            sets.append({a['name'] for a in r['allocations'] if a['kind']=='target_weight'})
        assert not sets[0]&sets[1] and sets[0]|sets[1]==expected_weights
        assert sum(r['target_raw_loaded_bytes'] for r in ranks)==sum(census['tensors'][n]['bytes'] for n in expected_weights)
        assert sum(r['target_weight_delta'] for r in ranks)==248320*3380-census['tensors']['output.weight']['bytes']+81920
    assert total(draftrows)==27410742
    for key,scenario in scenarios.items():
        if not scenario['mtp']:continue
        base=scenarios[key.replace('mtp-rank0','target-only')]
        assert scenario['ranks'][0]['device_logical_bytes']-base['ranks'][0]['device_logical_bytes']==4193685814
        assert scenario['ranks'][1]['device_logical_bytes']==base['ranks'][1]['device_logical_bytes']
    files=[LANE/'graph/new-plan.json',LANE/'graph/build-receipt.json',LANE/'metadata/new-census.json',LANE/'loader/inputs.json',LANE/'controls/manifest.json',P/'draft-weight-accounting.json',SRC/'main.cpp',SRC/'rank.hpp',SRC/'mtp.hpp',SRC/'strict_snapshot.hpp',LANE/'integration/generic_engine.hpp',BASE/'packet3/step/plan.hpp',BASE/'packet3/kernels/api.hpp',BASE/'packet194-expert-diet-engine/rope.hpp',PRIVATE/'source/diet-native/native/engine_bracket.hpp',PRIVATE/'source/diet-native/native/probe_exchange.hpp',P/'engine-accounting.py',LANE/'integration/evidence/header-check.json',PRIVATE/'additive/admission.hpp',BASE/'packet194-expert-diet-engine/p49d_submit.hpp',BASE/'packet194-expert-diet-engine/p59c_select.hpp',ROOT/'experiments/own-xpu-runtime/stage2/packet195-record-bundle-diet/diet-native/native-base/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/owner.cpp']
    record={'schema':'ownrt.gsq.engine-memory-source-ledger.v1','source_only':True,'model_reads':0,'device_constructed':False,'fit_qualified':False,'native_admitted':False,'context':4096,'geometry':{'h':2560,'vocab':248320,'experts':512,'top':10,'budget':2048,'qh':24,'kvh':2,'ad':256,'id':128},'assumptions':['Actual generic unfused Builder topology from retained full graph, flattened then actual rank split policy transcribed and source-pinned','No inherited selection/dispatch; no V3 moved layers, no compact/split/quantized head','Only actual launch-referenced weights load; mask3 permission does not itself cause unused duplicate HC uploads','Target scratch256MiB for rank0 draft scope; special8MiB policy only applies split23,draft_rank1,parallel','Logical allocation sums match Engine::allocate bytes; physical driver rounding/metadata are not bounded','Snapshot backup capacity counted in full even though actual capture may copy fewer bytes at a position','Latest GSQ baseline_selection has production snapshot and draft defaults; guarded static snapshot skip source-verified. Full Engine initialization remains unexecuted'], 'scenarios':scenarios,'draft_device_nonweight_bytes':total(draftrows),'draft_plan_buffers':sum(r['kind']=='draft_plan_buffer' for r in draftrows),'draft_qsa_kv_bytes':4096*(2*2*256+128)*2+1024*128*2,'rank_shared_host_mapping_bytes':4*65536+4096+64,'target_full_expanded_head_bytes':248320*3380,'target_head_expansion_delta_bytes':248320*3380-census['tensors']['output.weight']['bytes'],'host_file_backing_bytes':sum(t['bytes'] for n,t in census['tensors'].items() if n in ('token_embd.weight','per_layer_token_embd.weight')),'unknowns':['SYCL/LevelZero context, queues, command lists, compiled kernels/code, allocation reservation granularity and driver shadows','Host C++ vectors/prepared captures, GGUF metadata/headers, file pagecache, read/mmap windows and transient conversion buffers; bounded device ledger is not total host memory','Future fixes to GSQ snapshot/selection defaults or changes to split alter allocations and require this ledger refreshed','MTP draft checkpoint semantic quality for this quantized target and final GPU correctness are unqualified'], 'source_sha256':{str(f.relative_to(ROOT)):sha(f) for f in files}}
    record['internal_checks']={'six_scenarios_partition_all1222_nonlookup_weights_once':True,'all_weight_bytes_match_retained_census':True,'only_weight_deltas_fullQ6head_and_F16control':True,'unique_device_allocation_labels_per_rank':True,'category_and_allocation_totals_equal':True,'MTPincrement4193685814_exact':True,'actual4096_QSA_shapes':True,'flattened_plan_count_matches_actual_header_preflight':True,'private_and_original_Builder_bodies_identical':True}
    record['observed_header_preflight_counts']=headers['result']
    record['exact_qsa_cache_geometry']={'context_rows':4096,'index_budget':2048,'per_layer_kv_bytes':9699328,'24_split_qsa_layers_per_rank':6,'22_split_qsa_layers_rank0_rank1':[5,7]}
    record['source_review_corrections']=['Initial source read found unconditional static snapshot preparation with production miss; latest source conditionally skips it for GSQ production snapshot','Earlier concern that draft.at alone implied missing defaults was withdrawn after checking p49d::Selection initializes draft=p59c::defaults already']
    snapshots={str(f.relative_to(ROOT)):{'sha256':sha(f),'text':f.read_text()} for f in files if f.suffix in ('.hpp','.cpp','.py')}
    (P/'engine-accounting.sources.json').write_text(json.dumps({'schema':'ownrt.gsq.memory-source-snapshots.v1','sources':snapshots},indent=2)+'\n')
    record['source_snapshot_sha256']=sha(P/'engine-accounting.sources.json')
    full_text=json.dumps(record,indent=2)+'\n'
    full_path=LANE/'integration/build/memory-ledger-full.json'
    full_path.write_text(full_text)
    summary=copy.deepcopy(record)
    for key,scenario in summary['scenarios'].items():
        if key=='split24-24_mtp-rank0':continue
        for rank in scenario['ranks']:
            rank.pop('allocations')
            for field in ('full_plan_sources','standalone_sources','bank_names'):rank['snapshot'].pop(field)
    summary['full_generated_ledger']={'path':str(full_path.relative_to(ROOT)),'sha256':sha(full_path),'bytes':len(full_text.encode()),'retention':'ignored local generated output; reproducible from pinned recipe/source snapshots','full_details_tracked_for':'split24-24_mtp-rank0'}
    (P/'engine-accounting.json').write_text(json.dumps(summary,indent=2)+'\n')
    for key,s in scenarios.items():print(key,[(r['device_logical_bytes'],round(r['GiB'],4),r['arena30GiB_headroom']) for r in s['ranks']])
    print('draftnonweights',total(draftrows),'draftbuffers',record['draft_plan_buffers'])
if __name__=='__main__':main()
