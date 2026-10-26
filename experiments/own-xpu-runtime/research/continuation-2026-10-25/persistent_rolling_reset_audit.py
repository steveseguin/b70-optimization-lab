"""Independent per-request RESET identity, cold metadata and wire continuity."""
import hashlib
import json
from pathlib import Path
import re
from persistent_rolling_trace_audit import base
from finalize_ring_proof import need
from compare_pipeline_state import BUNDLE


def sha(raw):return hashlib.sha256(raw).hexdigest()
def json_sha(value):return sha(json.dumps(value,sort_keys=True,separators=(',',':')).encode())


def request_identity(plan,row,index,epoch):
    return json_sha(dict(schema='ownrt.persistent-rolling-request-identity.v1',process_request_sha256=plan['request_sha256'],
        suite_sha256=plan['suite_sha256'],model_identity_sha256=plan['model_identity_sha256'],draft_model_sha256=plan['draft_model_sha256'],
        draft_experts=plan['draft_experts'],activation_dtype=plan['activation_dtype'],context=plan['context'],vocab=plan['vocab'],
        eos_token_ids=plan['eos_token_ids'],check_policy=plan['check_policy'],index=index,epoch=epoch,**row))


def audit_reset(plan,row,result,journal,*,previous_request,previous_sequences,previous_target_position,prior_inventories,read_raw):
    index=result['index'];epoch=index+1;count=len(previous_sequences);policy=plan['check_policy']
    provider=plan.get('provider_stage',0)
    need(type(provider)is int and 0<=provider<count-1,'reset provider role')
    need(type(index)is int and index>=0 and policy in ('qualification','measured'),'persistent request index/policy')
    request=request_identity(plan,row,index,epoch)
    need(result['schema']=='ownrt.persistent-rolling-request-result.v1' and result['passed'] is True
         and result['id']==row['id'] and result['epoch']==epoch and result['request_sha256']==request
         and result['check_policy']==policy,'persistent request identity differs')
    need(type(result['cached_tokens'])is int and result['cached_tokens']==0 and result['prompt_state_reused'] is False
         and result['process_reused'] is True,'cold state claim must be explicit')
    need(result['previous_sequences']==previous_sequences and result['initial_sequences']==[n+1 for n in previous_sequences],
         'RESET cannot restart or skip global owner wire sequence')
    need(len(journal)==2*count and len(result['reset_receipts'])==count,'complete all-owner reset witness inventory')
    outstanding={};completed={};inventories=[]
    for item in journal:
        descriptor=item['descriptor'];stage=descriptor['stage_id']
        need(type(stage)is int and 0<=stage<count,'reset stage identity')
        sequence=previous_sequences[stage]+1
        expected=dict(schema='ownrt.ring-reset-request.v1',stage_id=stage,global_sequence=sequence,
            previous_epoch=index,next_epoch=epoch,previous_request_sha256=previous_request,next_request_sha256=request,
            destination=descriptor['destination'],oracle='')
        need(descriptor==expected and previous_request!=request,'exact RESET descriptor/epoch/owner identity')
        destination=Path(descriptor['destination'])
        native=Path(plan['stages'][stage]['native_output'])
        need(destination==native/'requests'/f"request-{index:02d}-{row['id']}" and destination.is_absolute(),
             'RESET output destination differs from admitted owner/request')
        if item['event']=='issued':
            need(stage not in outstanding and stage not in completed and item['previous_wire_sequence']==previous_sequences[stage],
                 'duplicate/stale RESET issue')
            need(base.REQUEST.unpack(bytes.fromhex(item['request_hex']))==(11,0,0,0,0,sequence,stage,int(stage==count-1)),
                 'RESET raw request identity')
            outstanding[stage]=item
            continue
        need(item['event']=='completed' and stage in outstanding and stage not in completed,'unsolicited/duplicate RESET completion')
        issued=outstanding.pop(stage)
        need(item['descriptor_sha256']==issued['descriptor_sha256'] and item['stage_id']==stage,'RESET descriptor hash/owner changed')
        need(Path(item['descriptor_path'])==native/f'reset-{sequence}.json' and Path(item['receipt_path'])==destination/'ring-reset.json'
             and item['native_output']==str(destination),'RESET evidence paths differ')
        descriptor_raw=read_raw(Path(item['descriptor_path']));receipt_raw=read_raw(Path(item['receipt_path']))
        need(sha(descriptor_raw)==item['descriptor_sha256'] and json.loads(descriptor_raw,object_pairs_hook=BUNDLE.pairs)==descriptor,
             'actual native descriptor bytes differ')
        need(sha(receipt_raw)==item['receipt_sha256'] and json.loads(receipt_raw,object_pairs_hook=BUNDLE.pairs)==item['receipt'],
             'actual native reset receipt bytes differ')
        receipt=item['receipt'];first=stage==0;owns_provider=stage==provider
        expected_receipt=dict(expected,schema='ownrt.ring-reset.v1',passed=True,check_policy=policy,
            target_position=0,target_physical=0,target_committed=0,target_pending=0,draft_position=0 if owns_provider else None,
            provider_serial=0 if owns_provider else None,context_extent=32,alternate_extent=32,draft_context_extent=32 if owns_provider else None,
            pending_ticket=False,sticky_error=0,allocation_ids_preserved=True,counters_reset=True,trace_reset=True,
            shared_publication_invalidated=True,reset_index=epoch,metadata_sha256=item['descriptor_sha256'],
            previous_target_position=previous_target_position,cold_state_byte_verified=False)
        need(all(type(receipt.get(k))is type(v) and receipt[k]==v for k,v in expected_receipt.items()),
             'native cold boundary/policy/request/previous frontier differs')
        inventory=receipt['allocation_inventory_before_sha256']
        need(isinstance(inventory,str) and re.fullmatch('[0-9a-f]{64}',inventory)
             and inventory==receipt['allocation_inventory_after_sha256'],'native allocation inventory changed')
        if prior_inventories is not None:need(inventory==prior_inventories[stage],'allocation identity changed across requests')
        for key in ('provider_cold_host_sha256','provider_cold_sequence_sha256'):
            need(bool(re.fullmatch('[0-9a-f]{64}',receipt[key])) if owns_provider else receipt[key]=='','cold provider host/Sequence identity missing')
        reply=base.REPLY.unpack(bytes.fromhex(item['reply_hex']))
        need(reply[:8]==(0,0,0,0,sequence,0 if first else 1,stage,int(stage==count-1)),
             'RESET raw acknowledgment differs')
        completed[stage]=item
    need(not outstanding and set(completed)==set(range(count)),'partial RESET barrier')
    for stage,record in enumerate(result['reset_receipts']):
        need(record=={k:v for k,v in completed[stage].items() if k!='event'},'request reset receipt list differs from journal')
        inventories.append(record['receipt']['allocation_inventory_after_sha256'])
    final=result['final_sequences'];post=result['post_dump_sequences']
    need(len(final)==len(post)==count and all(type(n)is int and n>result['initial_sequences'][i] for i,n in enumerate(final)),
         'complete request must advance each owner wire sequence')
    if plan['dump_each']:
        need(post==result['dump_sequences']==[n+1 for n in final],'per-request DUMP global sequence differs')
    else:need(post==final and result['dump_sequences']==[],'undeclared per-request DUMP')
    return dict(passed=True,epoch=epoch,request_sha256=request,inventories=inventories,post_sequences=post,
        cached_tokens=0,cold_state_byte_verified=False,
        scope='Native reset operations/cold host metadata and all-owner barrier; full cold allocation bytes were not individually read back.')
