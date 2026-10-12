#!/usr/bin/env python3
"""CPU-only independent launch-plan inventory; no model or device loading.

Full-write and partial-write contracts were reviewed against copied packet29
adapter.cpp, kernels.hpp and specialised.hpp. Plan inputs alone cannot prove
QSA whole-cache writes or implicit error writes; these contracts are explicit.
"""
import hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent
plan=json.loads((P/'launch-plan-rank0.json').read_text())
bs={b['name']:b['bytes'] for b in plan['buffers']}
first_read={}; first_write={}; writers={}
known={'begin','broadcast','check_status','commit','conv','expert_gate_up','gdn','gdn_norm_gate','gemv','hc_combine','hc_mix','lookup','moe_combine','norm','ple_add','ple_gate','ple_hash','qsa_append_pool','qsa_attention','qsa_prepare','qsa_select','route','routed_gemv','silu_div4','silu_product','expert_gather'}
temporal={}
for i,l in enumerate(plan['launches']):
    assert l['op'] in known, ('unreviewed write contract',l)
    for n in l['inputs']: first_read.setdefault(n,i)
    for n in l['outputs']:
        first_write.setdefault(n,i);writers.setdefault(n,[]).append(l['label'])
    if l['op'] in ('gdn','conv'):
        n=l['outputs'][1];assert n in l['inputs'] and n not in temporal
        temporal[n]=dict(name=n,bytes=bs[n],writer=l['label'],strategy='distinct committed input and candidate output; pointer/binding bank swap',bankable=True,hot_copy_bytes=0)
    if l['op']=='qsa_append_pool':
        for n,row in zip(l['outputs'],(1024,1024,256,256)):
            pooled=n.endswith('.pooled')
            temporal[n]=dict(name=n,bytes=bs[n],writer=l['label'],strategy='redo overwrites same append-only row; old rows untouched',bankable=False,hot_copy_bytes=0,row_bytes=row,offset='(position//4)*256' if pooled else f'position*{row}',write_condition='position%4==3' if pooled else 'every half')
for n,strategy,copy in [('token_history','snapshot before half; restore before redo (ple_hash mutates input)',16),('position','commit increments; restore attempted position before redo',4),('error','sticky implicit and explicit writers; any failure aborts; never cleared',0)]:
    temporal[n]=dict(name=n,bytes=bs[n],writers=writers[n],strategy=strategy,bankable=False,restore_bytes_per_miss=copy)
external={'active':'immutable initialized guard','ple_metadata':'immutable uploaded model metadata','token':'host uploads current token before half','next_token':'rank0 never reads or writes; initialized placeholder'}
overwrite=[]
for n in sorted(set(bs)-set(temporal)-set(external)):
    assert n in first_write, ('unclassified allocation',n)
    assert first_write[n]<first_read.get(n,10**9), ('unclassified old-value read',n,first_read[n],first_write[n])
    overwrite.append(dict(name=n,bytes=bs[n],first_writer=plan['launches'][first_write[n]]['label']))
assert len(bs)==len(temporal)+len(external)+len(overwrite)
banked=[v for v in temporal.values() if v['bankable']]
result=dict(schema='packet37.rollback-inventory.v1',passed=True,device_executed=False,
    provenance={n:hashlib.sha256((P/n).read_bytes()).hexdigest() for n in ['launch-plan-rank0.json','main.cpp','rank.hpp','adapter.cpp','kernels.hpp','specialised.hpp']},
    buffer_count=len(bs),launch_count=len(plan['launches']),
    banked_buffer_count=len(banked),alternate_bank_bytes=sum(v['bytes'] for v in banked),
    temporal_buffer_count=len(temporal),temporal=sorted(temporal.values(),key=lambda x:x['name']),
    externally_initialized=external,overwrite_only_count=len(overwrite),overwrite_only=overwrite,
    proof='Every allocation classified exactly once. Every overwrite-only buffer has a reviewed full-write producer before its first plan read. QSA partial writes and implicit sticky error writes are separately classified by kernel contracts. Streams first writer is broadcast, so no temporal HC carry.',
    host_state={'history0_history1_bytes':16,'rollback':'restored before prepare_token redo','lookup_ids':'cleared/recomputed','fp32_sources_extents':'invalidated on every bank swap and rollback','prepared_operator_maps':'two bank-specific binding maps swap with allocation IDs','prepared_command_vectors':'two captured issue-site vectors swap with the maps and explicit parity; fresh reconstruction audit after swaps','matrices':'no banked temporal allocation appears as GEMV input/output'},
    nonplan_storage={'snapshots':'only confirmed candidate fixture bytes published; scratch rewritten per captured layer','scratch_controls_scores_probabilities_workspace_routes_mixture':'producer-before-consumer within half; not cross-position model state','weights_rope_unit_scalar':'immutable','events_counters_profiling':'execution bookkeeping intentionally records attempts, not rolled back'},
    rollback_transfer_bytes={'device_to_host_per_rank0_half':16,'host_to_device_per_miss':20,'banked_state_copy':0,'qsa_cache_copy':0},
    rank1='No speculation: only confirmed stream handovers enter its half; no rollback needed')
(P/'rollback-inventory.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['passed','buffer_count','launch_count','banked_buffer_count','alternate_bank_bytes','temporal_buffer_count','overwrite_only_count']}))
