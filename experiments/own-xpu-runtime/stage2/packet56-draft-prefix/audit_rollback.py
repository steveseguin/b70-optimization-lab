#!/usr/bin/env python3
"""CPU-only independent launch-plan inventory; no model or device loading.

Full-write and partial-write contracts were reviewed against copied packet29
adapter.cpp, kernels.hpp and specialised.hpp. Plan inputs alone cannot prove
QSA whole-cache writes or implicit error writes; these contracts are explicit.
"""
import base64,gzip,hashlib,json,time
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
        temporal[n]=dict(name=n,bytes=bs[n],writer=l['label'],strategy='active committed bank excluded from snapshot; inactive candidate bank saved before issue and restored after conditional swap-back',bankable=True,snapshot_copy_bytes=bs[n])
    if l['op']=='qsa_append_pool':
        for n,row in zip(l['outputs'],(1024,1024,256,256)):
            pooled=n.endswith('.pooled')
            temporal[n]=dict(name=n,bytes=bs[n],writer=l['label'],strategy='already-valid prefix excluded; entire invalid tail saved before issue and restored on rollback',bankable=False,row_bytes=row,offset='(position//4)*256' if pooled else f'position*{row}',write_condition='position%4==3' if pooled else 'every half')
for n,strategy,copy in [('token_history','strict image saves/restores all bytes; ple_hash mutates input',16),('position','strict image saves/restores original position',4),('error','saved only when zero; guards reject sticky failure before restore; never erased after failure',4)]:
    temporal[n]=dict(name=n,bytes=bs[n],writers=writers[n],strategy=strategy,bankable=False,restore_bytes_per_miss=copy)
external={'active':'immutable initialized guard','ple_metadata':'immutable uploaded model metadata','token':'strict image saves previous token before guessed upload; rollback restores it','next_token':'rank0 never reads or writes; initialized placeholder'}
overwrite=[]
for n in sorted(set(bs)-set(temporal)-set(external)):
    assert n in first_write, ('unclassified allocation',n)
    assert first_write[n]<first_read.get(n,10**9), ('unclassified old-value read',n,first_read[n],first_write[n])
    overwrite.append(dict(name=n,bytes=bs[n],first_writer=plan['launches'][first_write[n]]['label']))
assert len(bs)==len(temporal)+len(external)+len(overwrite)
banked=[v for v in temporal.values() if v['bankable']]
def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def archive_members(path, wanted):
    """Read only bounded selected JSON members; authenticate retained bytes."""
    found={};current=None;chunks=[]
    with gzip.open(path,'rt') as source:
        assert json.loads(next(source))=={'schema':'packet38.scratch-stream.v1'}
        for line in source:
            row=json.loads(line)
            if row['kind']=='file':current=row;chunks=[]
            elif row['kind']=='chunk' and any(current['path'].endswith('/'+name) for name in wanted):
                chunks.append(base64.b64decode(row['base64'],validate=True))
            elif row['kind']=='end' and chunks:
                raw=b''.join(chunks);assert len(raw)==current['bytes'] and hashlib.sha256(raw).hexdigest()==current['sha256']
                key=next(name for name in wanted if current['path'].endswith('/'+name))
                assert key not in found;found[key]=json.loads(raw)
    assert set(found)==set(wanted)
    return found

def payload_bytes(capacity,position,qsa_rows):
    assert position>=0
    excluded=sum((position//4 if row['pooled'] else position)*row['row_bytes'] for row in qsa_rows)
    assert 0<=excluded<=capacity
    return capacity-excluded

def strict_evidence():
    receipt_path=P/'terminal-eos-all-state-real-both.json';receipt=json.loads(receipt_path.read_text())
    assert receipt['passed'] and receipt['real_model'] and not receipt['device_executed'] and not receipt['screen']
    for name,digest in receipt['source_sha256'].items():assert sha(P/name)==digest,('strict source changed',name)
    qsa_rows=[dict(name=row['name'],row_bytes=row['row_bytes'],pooled=row['name'].endswith('.pooled')) for row in temporal.values() if 'row_bytes' in row]
    outputs={'token','position','token_history'}|{n for launch in plan['launches'] for n in launch['outputs']}
    plan_bytes=sum(bs[n] for n in outputs);examples=[];capacities=set()
    for position in receipt['sampled_positions']:
        owner=next(row for row in receipt['owners'] if row['prompt_tokens']==position and row['controller']=='native' and row['retain_steps']=='none' and row['cancel_launch']==0 and row['corruption'] is None)
        archive=owner['archive'];path=P/archive['path'];assert sha(path)==archive['sha256']
        members=archive_members(path,('rank0/launch-plan.json','rank0/request-state-inventory.json','rank0/speculative-snapshot.json'))
        assert members['rank0/launch-plan.json']==plan
        snapshot=members['rank0/speculative-snapshot.json'];inventory=members['rank0/request-state-inventory.json']['standalone_target_mutable']
        private=[row for name,row in inventory.items() if name.endswith(':speculative-private-image')]
        assert len(private)==1
        standalone_bytes=sum(row['bytes'] for name,row in inventory.items() if not name.endswith((':speculative-private-image',':mixture-one')))
        capacity=plan_bytes+standalone_bytes;assert capacity==private[0]['bytes']==snapshot['capacity_bytes']
        payload=payload_bytes(capacity,position,qsa_rows)
        assert snapshot['captures']==snapshot['restores']==1 and snapshot['snapshot_payload_bytes']==payload
        assert snapshot['private_backup_zeroed'] and snapshot['private_host_backup_empty'] and not snapshot['committed_state_scrubbed'] and not snapshot['snapshot_valid']
        capacities.add(capacity)
        examples.append(dict(position=position,capacity_bytes=capacity,plan_candidate_bytes=plan_bytes,standalone_mutable_bytes=standalone_bytes,
                             snapshot_device_to_device_bytes=payload,restore_device_to_device_bytes=payload,
                             protected_qsa_prefix_bytes=capacity-payload,archive=archive['path'],archive_sha256=archive['sha256']))
    assert len(capacities)==1 and len(examples)>=2
    return dict(receipt=receipt_path.name,receipt_sha256=sha(receipt_path),binary_sha256=receipt['binary_sha256'],
                diagnostic_prompt_scope=receipt['real_prompt_scope'],capacity_bytes=capacities.pop(),examples=examples,
                payload_formula='capacity_bytes - sum(valid_rows * row_bytes); valid_rows=position for keys/values/raw, floor(position/4) for pooled',
                qsa_rows=qsa_rows)

def main():
    evidence=strict_evidence()
    result=dict(schema='packet40.rollback-inventory.v2',passed=True,device_executed=False,performance_claim=False,
        provenance={n:sha(P/n) for n in ['launch-plan-rank0.json','main.cpp','rank.hpp','strict_snapshot.hpp','owner_api.hpp','owner.cpp','request_state_inventory.hpp','adapter.cpp','kernels.hpp','specialised.hpp','audit_rollback.py']},
        buffer_count=len(bs),launch_count=len(plan['launches']),banked_buffer_count=len(banked),alternate_bank_bytes=sum(v['bytes'] for v in banked),
        temporal_buffer_count=len(temporal),temporal=sorted(temporal.values(),key=lambda x:x['name']),
        externally_initialized=external,overwrite_only_count=len(overwrite),overwrite_only=overwrite,
        proof='Every plan allocation is classified exactly once. Producer-before-consumer identifies old logical dependencies; it is NOT permission to omit scratch from strict physical rollback. All declared outputs and token/position/history are saved, using inactive recurrent banks and invalid QSA tails. Already-active banks and valid QSA prefixes are excluded so illegal writes remain observable.',
        host_state={'history0_history1_bytes':16,'rollback':'exact saved values restored after drain and conditional bank swap-back',
                    'lookup_ids_selected_loaded_layer_fp32_sources_extents':'saved before guessed token preparation and restored exactly; streaming layers must already be released; restored FP32 allocation IDs must remain live',
                    'prepared_operator_maps':'two bank-specific binding maps swap with allocation IDs',
                    'prepared_command_vectors':'two captured issue-site vectors swap with maps and explicit parity; no reconstruction during restore',
                    'rank0_transport_slot':'65536 host bytes saved/restored; rank1 streams, verification and draft publication regions untouched'},
        nonplan_storage={'mutable_standalone':'all live device allocations except represented plan/spare buffers, weights, pinned slabs and immutable one scalar are saved/restored, including scratch and snapshots',
                         'private_backup':'zeroed at construction and resolved dump/reset/finish boundaries; host vectors/slot retired; no model buffers scrubbed',
                         'weights_rope_unit_scalar':'immutable and excluded from snapshot',
                         'events_counters_profiling':'attempt telemetry is retained, not rolled back; raw counters/hashes recorded separately'},
        rollback_transfer_bytes={'scope':'source-level byte accounting, not measured latency or exhaustive half-step traffic',
                                 'private_device_capacity':evidence['capacity_bytes'],
                                 'device_to_device_per_capture':'position-dependent payload_bytes; see authenticated examples',
                                 'device_to_device_per_rollback':'same saved extents as capture',
                                 'private_zero_host_to_device_per_construction_or_dirty_boundary':evidence['capacity_bytes'],
                                 'host_to_host_transport_per_capture_or_restore':65536,
                                 'additional_snapshot_begin_scalar_device_to_host':8,
                                 'additional_undo_and_snapshot_restore_scalar_device_to_host':8,
                                 'existing_candidate_history_device_to_host_per_rank0_half':16,
                                 'host_metadata_copy_bytes':'variable; exact vectors/maps saved and restored, not included in device capacity',
                                 'active_committed_bank_copy':0,'valid_qsa_prefix_copy':0,
                                 'inactive_bank_and_invalid_qsa_tail_copy':'included in payload; not zero'},
        strict_snapshot_evidence=evidence,
        rank1='Never speculates; no strict image allocation or restore. Draft state is private and only checked target results authorize emitted tokens.')
    destination=P/'rollback-inventory.json'
    if destination.exists():
        from storage import archive_files
        result['prior_inventory_archive']=archive_files([destination],P/'evidence'/f'prior-rollback-inventory-{time.time_ns()}.jsonl.gz')
    destination.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['passed','buffer_count','launch_count','banked_buffer_count','alternate_bank_bytes','temporal_buffer_count','overwrite_only_count']}))
if __name__=='__main__':main()
