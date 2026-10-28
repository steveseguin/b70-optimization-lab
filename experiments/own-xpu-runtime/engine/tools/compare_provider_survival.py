"""Strict typed identities for provider survival across target-only rollback."""
import hashlib
import json
import math
import struct

from compare_pipeline_state import BUNDLE, require, speculative_depth


def digest(raw):return hashlib.sha256(raw).hexdigest()
def fields(value, expected, label):
    require(isinstance(value,dict) and set(value)==set(expected.split()),label+' field inventory differs')

def integer(value,label,low=0,high=2**64-1):
    require(type(value)is int and low<=value<=high,'bounded integer required: '+label)

def row_identity(row,spec,vocab):
    fields(row,'epoch id parent ticket position token fixture tentative request before after','provider row')
    for key in ('epoch','id','parent','ticket','position','token','fixture'):integer(row[key],key)
    require(row['epoch']==spec['ring_epoch'] and row['request']==spec['ring_request_sha256']
            and row['id']>row['parent'] and row['ticket']>0 and 0<=row['token']<vocab
            and type(row['tentative'])is bool,'provider row request/token/ticket identity')
    require(BUNDLE.hexhash(row['before']) and BUNDLE.hexhash(row['after']) and row['position']<2**32,
            'provider row prefix identity')
    require(row['after']==digest(b'ownrt.ring-prefix.v1\0'+bytes.fromhex(row['before'])+struct.pack('<II',row['position'],row['token'])),
            'provider row full prefix differs')


def validate_payload(raw,spec,layout,metadata,abort_sequence):
    require(isinstance(raw,str) and 0<len(raw.encode())<=8*1024**2,'bounded provider identity payload')
    payload=json.loads(raw,object_pairs_hook=BUNDLE.pairs)
    fields(payload,'schema position provider_serial allocations host sequence prepared_bindings_sha256 excluded_shared_counter_values','provider payload')
    require(payload['schema']=='ownrt.provider-survival-state.v1','provider payload schema')
    position=payload['position'];integer(position,'provider position',1,2**31-1)
    require(type(payload['provider_serial'])is int and payload['provider_serial']==position
            and position<spec['input_identity']['position'],'provider survival canonical position')
    expected={r['label']:{**{k:v for k,v in r.items() if k!='saved_bytes'},'role':'canonical'} for r in layout['independent_draft_allocations']}
    for r in layout['provider_private_allocations']:
        require(r['label'] not in expected,'provider private/canonical overlap');expected[r['label']]={**{k:v for k,v in r.items() if k!='saved_bytes'},'role':'recursive-image'}
    rows=payload['allocations'];require(isinstance(rows,list) and len(rows)==len(expected),'provider survival complete allocation inventory')
    seen=set()
    for row in rows:
        fields(row,'id label bytes memory role sha256','provider allocation')
        integer(row['id'],'provider allocation ID',1);integer(row['bytes'],'provider allocation bytes',1)
        label=row['label'];require(label in expected and label not in seen,'provider survival missing/duplicate/unknown allocation');seen.add(label)
        require({k:row[k] for k in expected[label]}==expected[label] and BUNDLE.hexhash(row['sha256']),
                'provider allocation role/identity/hash differs from checkpoint partition')
        if label=='card0:draft:position':require(row['sha256']==digest(struct.pack('<i',position)),'provider canonical device position differs')
    private=layout['provider_private_allocations'][0]
    host=payload['host']
    fields(host,'current saved saved_target_sha256 saved_rows_sha256 saved_class captures restores verified_restores private_bytes allocated_bytes image_id active','provider host')
    require(BUNDLE.hexhash(host['saved_target_sha256']) and BUNDLE.hexhash(host['saved_rows_sha256']),'provider saved host digest identity')
    for key in ('saved_class','captures','restores','verified_restores','private_bytes','allocated_bytes','image_id'):
        integer(host[key],key,-2**31 if key=='saved_class' else 0)
    require(host['captures']==host['restores']==host['verified_restores'] and host['active'] is False
            and host['private_bytes']==private['bytes'] and host['image_id']==private['id']
            and host['allocated_bytes']>=host['private_bytes'],'provider host ownership/counter identity')
    for role in ('current','saved'):
        state=host[role]
        fields(state,'position extent pending_confirmed queued_probe queued_confirmed depth disabled async_pending pending_head reverse_present captured publication_event pending_start_ticks reverse_bytes reverse_sha256','provider '+role+' host')
        for key in ('position','extent','pending_confirmed','queued_probe','queued_confirmed','depth','publication_event','pending_start_ticks','reverse_bytes'):
            integer(state[key],key,-2**63 if key=='pending_start_ticks' else -1)
        require(all(type(state[k])is bool for k in ('disabled','async_pending','pending_head','reverse_present','captured')),
                'provider host boolean identity')
        require(not any(state[k] for k in ('disabled','async_pending','pending_head','reverse_present'))
                and state['pending_confirmed']==state['depth']==state['publication_event']==0
                and state['queued_probe']==state['queued_confirmed']==-1 and max(1,state['position'])<=state['extent']<=spec['draft_input_identity']['context']
                and 0<=state['reverse_bytes']<=metadata['stream_bytes'] and BUNDLE.hexhash(state['reverse_sha256']),
                'provider host not synchronous and quiescent')
    require(host['current']['position']==position,'provider host/device position differs')
    sequence=payload['sequence']
    fields(sequence,'epoch request stage stages stream_bytes vocab next_position last_sequence last_commit serial last_seed poisoned last_result','provider Sequence')
    for key in ('epoch','stage','stages','stream_bytes','vocab','next_position','last_sequence','last_commit','serial'):
        integer(sequence[key],key)
    require(sequence['epoch']==spec['ring_epoch'] and sequence['request']==spec['ring_request_sha256']
            and sequence['stage']==0 and sequence['stages']==metadata['stage_count']
            and sequence['stream_bytes']==metadata['stream_bytes'] and sequence['vocab']==spec['draft_input_identity']['vocab']
            and sequence['next_position']==position+1 and sequence['serial']==position
            and 0<sequence['last_sequence']<abort_sequence and sequence['last_commit']>0 and sequence['poisoned'] is False,
            'provider complete Sequence identity differs')
    row_identity(sequence['last_seed'],spec,sequence['vocab'])
    require(sequence['last_seed']['position']==position and sequence['last_seed']['ticket']<sequence['last_sequence'],
            'provider Sequence retained seed differs')
    result=sequence['last_result'];fields(result,'position guesses byte_verified snapshot_bytes canonical_ms capture_ms recursive_ms restore_ms','provider last result')
    require(type(result['position'])is int and result['position']==position and isinstance(result['guesses'],list)
            and len(result['guesses'])<=metadata.get('ring_depth',spec.get('speculative_depth',2))
            and all(type(t)is int and 0<=t<sequence['vocab'] for t in result['guesses'])
            and type(result['byte_verified'])is bool and type(result['snapshot_bytes'])is int,'provider last result bounds')
    if len(result['guesses'])>=2:
        require(result['byte_verified'] is True and result['snapshot_bytes']==private['bytes']
                and host['saved']['position']==position and host['captures']>0,'provider recursive result/save identity')
    else:require(result['byte_verified'] is False and result['snapshot_bytes']==0,'provider censored result identity')
    for key in ('canonical_ms','capture_ms','recursive_ms','restore_ms'):
        require(type(result[key])in (int,float) and math.isfinite(result[key]) and result[key]>=0,'provider finite result timing')
    require(BUNDLE.hexhash(payload['prepared_bindings_sha256']) and payload['excluded_shared_counter_values']==
            ['Engine timing/submission totals','Device copy_counter values'],'provider prepared binding/shared counter scope differs')
    return payload


def validate_records(records,spec,layout,metadata,att):
    depth=speculative_depth(spec)
    require(isinstance(records,list) and 0<len(records)<=128 and len(records)==att['provider_survival_records'],
            'complete bounded provider survival receipt inventory')
    prior=0;discarded=0
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
        require(isinstance(captures,list) and isinstance(ids,list) and 1<=len(captures)==len(ids)<=depth
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
        require(advanced and record['provider_advanced_since_snapshot'] is True,'provider did not advance beyond restored target snapshot')
        require(payload['position']+1==oldest['position']
                and oldest['parent']==payload['sequence']['last_seed']['id']
                and oldest['before']==payload['sequence']['last_seed']['after'],
                'provider not at latest confirmed target frontier before abort')
        require(record['comparison_bytes']==sum(r['bytes'] for r in payload['allocations'])
                and record['canonical_allocations_checked']==len(layout['independent_draft_allocations'])
                and record['private_allocations_checked']==len(layout['provider_private_allocations'])==1,
                'provider byte/allocation comparison coverage differs')
        discarded+=len(ids)
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
                and 'provider_survival' not in stage and att['tentative_rows']==att['abort_count']==0,
                'pending-provider proof permits only first-stage target speculation/survival ownership')
        return []
    require(att['provider_survival_verification_enabled'] is True
            and all(pending[str(depth)]>0 for depth in spec['required_provider_pending_depths'])
            and sum(pending.values())==att['provider_borrows_while_target_pending']
            and att['provider_quiescent_borrows']+sum(pending.values())==att['provider_commands'],
            'pending-provider borrow policy/coverage differs')
    count=att['provider_survival_records']
    require(count>0 and all(att[k]==count for k in numeric if k not in ('provider_quiescent_borrows','provider_survival_discarded_rows'))
            and count==att['abort_count'],'provider survival verification accounting differs')
    from compare_draft_state import small
    declared=path.parent/stage['provider_survival']
    require(not declared.is_symlink() and declared.resolve()==dump.parent/'ring-provider-survival.jsonl',
            'provider survival receipt must be exact native sibling')
    raw,receipt=small(declared)
    require(receipt['sha256']==att['provider_survival_receipt_sha256'],'provider survival receipt SHA differs')
    records=[json.loads(line,object_pairs_hook=BUNDLE.pairs) for line in raw.decode().splitlines()]
    validate_records(records,spec,layout,metadata,att)
    return [receipt]
