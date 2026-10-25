"""V6 rolling survival semantics; v5 forced-coverage validator stays unchanged.

Full payload/inventory primitives are shared. Trace causality and actual proposal
provenance are additionally required by the independent rolling finalizer.
"""
import json
import os
import stat
from compare_provider_survival import fields, integer, digest, row_identity, validate_payload
from compare_pipeline_state import BUNDLE, require


def survival_bytes(path):
    """A zero-event native trace is a valid empty, authenticated regular file."""
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
    try:
        before=os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and 0<=before.st_size<=16*1024**2,
                'bounded regular rolling survival trace required')
        data=bytearray()
        while len(data)<before.st_size:
            part=os.read(fd,min(65536,before.st_size-len(data)))
            require(part,'rolling survival trace truncated');data.extend(part)
        require(not os.read(fd,1) and BUNDLE.identity(before)==BUNDLE.identity(os.fstat(fd))
                ==BUNDLE.identity(os.stat(path,follow_symlinks=False)), 'rolling survival trace changed')
        raw=bytes(data)
        return raw,dict(path=str(path),bytes=len(raw),sha256=digest(raw))
    finally:os.close(fd)


def validate_records(records,spec,layout,metadata,att):
    require(isinstance(records,list) and 0<=len(records)<=128 and len(records)==att['provider_survival_records'],
            'complete bounded provider survival receipt inventory')
    prior=0;discarded=0;advanced_count=0
    for record in records:
        fields(record,'schema stage_id ring_request_sha256 ring_epoch abort_sequence oldest discarded_row_ids provider_at_capture provider_advanced_since_snapshot actual_position committed_position pending_tickets comparison_bytes canonical_allocations_checked private_allocations_checked all_bytes_equal host_equal sequence_equal prepared_bindings_equal before_payload before_payload_sha256 after_payload after_payload_sha256','provider survival receipt')
        require(record['schema']=='ownrt.provider-abort-survival.v1' and type(record['stage_id'])is int and record['stage_id']==0
                and record['ring_request_sha256']==spec['ring_request_sha256'] and type(record['ring_epoch'])is int
                and record['ring_epoch']==spec['ring_epoch'],'provider survival receipt owner/request')
        for key in ('abort_sequence','actual_position','committed_position','pending_tickets','comparison_bytes','canonical_allocations_checked','private_allocations_checked'):
            integer(record[key],key)
        require(prior<record['abort_sequence']<2**31,'provider abort receipt sequence order');prior=record['abort_sequence']
        require(all(record[k] is True for k in ('all_bytes_equal','host_equal','sequence_equal','prepared_bindings_equal')),
                'provider survival must verify bytes, host, Sequence and bindings')
        require(record['before_payload']==record['after_payload'] and record['before_payload_sha256']==record['after_payload_sha256']
                ==digest(record['before_payload'].encode()),'provider before/after exact payload or digest differs')
        payload=validate_payload(record['before_payload'],spec,layout,metadata,record['abort_sequence'])
        row_identity(record['oldest'],spec,payload['sequence']['vocab'])
        oldest=record['oldest'];captures=record['provider_at_capture'];ids=record['discarded_row_ids']
        require(isinstance(captures,list) and isinstance(ids,list) and 1<=len(captures)==len(ids)<=2
                and len(set(ids))==len(ids) and all(type(i)is int for i in ids),'provider suffix inventory')
        require(record['actual_position']==record['committed_position']==oldest['position']
                and record['pending_tickets']==0 and oldest['tentative'] is True,'provider target abort frontier')
        for index,capture in enumerate(captures):
            fields(capture,'row position serial','provider identity at target capture')
            row_identity(capture['row'],spec,payload['sequence']['vocab'])
            integer(capture['position'],'captured provider position');integer(capture['serial'],'captured provider serial')
            require(capture['position']==capture['serial']<=payload['position'] and capture['row']['id']==ids[index]
                    and capture['row']['tentative'] is True and capture['row']['position']==oldest['position']+index
                    and capture['row']['ticket']<record['abort_sequence'],
                    'provider capture provenance differs')
            if index==0:require(capture['row']==oldest,'provider oldest capture row differs')
            else:require(capture['row']['parent']==captures[index-1]['row']['id']
                         and capture['row']['before']==captures[index-1]['row']['after'],'provider discarded suffix prefix differs')
        advanced=payload['position']>captures[0]['position'] and payload['provider_serial']>captures[0]['serial']
        require(type(record['provider_advanced_since_snapshot']) is bool and record['provider_advanced_since_snapshot'] is advanced,
                'rolling provider advancement label differs from snapshot provenance')
        advanced_count+=int(advanced)
        require(payload['position']<oldest['position'], 'rolling provider advanced beyond committed target prefix')
        require(record['comparison_bytes']==sum(r['bytes'] for r in payload['allocations'])
                and record['canonical_allocations_checked']==len(layout['independent_draft_allocations'])
                and record['private_allocations_checked']==len(layout['provider_private_allocations'])==1,
                'provider byte/allocation comparison coverage differs')
        discarded+=len(ids)
    require(advanced_count==att['provider_survival_advanced_records'], 'rolling advanced survival count differs')
    require(discarded==att['provider_survival_discarded_rows']==att['discarded_rows'],
            'provider survival discarded-row accounting differs')
    return records


def validate_survival(path,stage,dump,spec,layout,metadata,att):
    numeric=('provider_quiescent_borrows','provider_survival_records','provider_survival_discarded_rows',
             'provider_survival_advanced_records','provider_survival_bytes_verified','provider_survival_host_verified',
             'provider_survival_sequence_verified','provider_survival_private_verified','provider_survival_bindings_verified')
    for key in numeric:integer(att[key],key)
    pending=att['provider_pending_borrows'];fields(pending,'1 2','pending depth counts')
    for key,value in pending.items():integer(value,'pending depth '+key)
    require(type(att['provider_survival_verification_enabled'])is bool,'provider survival policy boolean required')
    if not metadata['first']:
        require(not any(att[k] for k in numeric) and pending=={'1':0,'2':0}
                and att['provider_survival_receipt_sha256']=='' and att['provider_survival_verification_enabled'] is False
                and 'provider_survival' not in stage,
                'rolling nonfirst stage cannot own provider survival state')
        return []
    require(att['provider_survival_verification_enabled'] is True
            and all(pending[str(depth)]>0 for depth in spec['required_provider_pending_depths'])
            and sum(pending.values())==att['provider_borrows_while_target_pending']
            and att['provider_quiescent_borrows']+sum(pending.values())==att['provider_commands'],
            'pending-provider borrow policy/coverage differs')
    count=att['provider_survival_records']
    require(0<=att['provider_survival_advanced_records']<=count<=128
            and all(att[k]==count for k in numeric if k not in ('provider_quiescent_borrows','provider_survival_discarded_rows','provider_survival_advanced_records'))
            and count==att['abort_count'],'provider survival verification accounting differs')
    declared=path.parent/stage['provider_survival']
    require(not declared.is_symlink() and declared.resolve()==dump.parent/'ring-provider-survival.jsonl',
            'provider survival receipt must be exact native sibling')
    raw,receipt=survival_bytes(declared)
    require(receipt['sha256']==att['provider_survival_receipt_sha256'],'provider survival receipt SHA differs')
    records=[json.loads(line,object_pairs_hook=BUNDLE.pairs) for line in raw.decode().splitlines()]
    validate_records(records,spec,layout,metadata,att)
    return [receipt]
