#!/usr/bin/env python3
"""Offline state parity for explicit dedicated-provider ownership; no device work.

Candidate manifest: schema ownrt.dedicated-parity-inputs.v1, reference_request,
plan, result, commands, draft_set, stages[{id,begin,end,dump,plan,metadata,
quiescence}], process_receipts (all target receipts plus provider receipt).
Paths are absolute. The original reference manifests and native metadata remain
unchanged. All reference bundles must already be extracted by the coordinator.
"""
import argparse
from hashlib import sha256
import json
import math
import os
import stat
from pathlib import Path
import struct
import sys

ENGINE=Path(__file__).resolve().parents[3]/'engine'
sys.path.insert(0,str(ENGINE/'tools'))
import compare_pipeline_state as T
import compare_draft_state as D
need=T.require

def trace_source(path,limit=128*1024**2):
    path=Path(path);fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd);need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and 0<before.st_size<=limit,'bounded actual trace')
        chunks=[];remaining=before.st_size
        while remaining:
            chunk=os.read(fd,min(1024**2,remaining));need(chunk,'trace truncated');chunks.append(chunk);remaining-=len(chunk)
        raw=b''.join(chunks)
        need(not os.read(fd,1) and T.BUNDLE.identity(before)==T.BUNDLE.identity(os.fstat(fd))==T.BUNDLE.identity(os.stat(path,follow_symlinks=False)),'trace changed')
        return raw,dict(path=str(path),bytes=len(raw),sha256=T.sha(raw))
    finally:os.close(fd)

def read(path):
    raw,receipt=D.small(Path(path))
    return json.loads(raw,object_pairs_hook=T.BUNDLE.pairs),receipt

def driver_result(path):
    raw,receipt=trace_source(path,limit=16*1024**2)
    value=json.loads(raw,object_pairs_hook=T.BUNDLE.pairs)
    need(value.get('schema')=='ownrt.dedicated-provider-driver-result.v1','explicit dedicated driver result schema')
    need(value.get('passed') is True and not value.get('error') and value.get('cancelled') is False
         and not value.get('live_pids') and isinstance(value['returncodes'],dict)
         and set(value['returncodes']) in ({'0','1','provider'},{'0','1','2','provider'})
         and all(type(code)is int and code==0 for code in value['returncodes'].values()),
         'dedicated driver clean completion')
    return value,receipt

def capture_event(issued,event,completed,serial,target_stages):
    row=issued['row'];sequence=issued['sequence'];result=completed['provider']
    need(target_stages in (2,3),'capture source target topology')
    need(event['row']==row and event['op']==issued['op']==27,'capture exact issued source row')
    native=bytes.fromhex(issued['parent_record_hex'])
    need(len(native)==360,'capture actual complete final record')
    header=struct.unpack('<4IQ',native[:24])
    parent=struct.unpack('<4I3Q10i32s32s32s32s16s',native[24:248])
    handoff=struct.unpack('<12i64s',native[248:])
    need(header==(0x52464331,1,360,target_stages-1,result['final_commit'])
         and parent[:4]==(0x52494e47,1,224,0)
         and parent[4]==row['epoch'] and parent[5]==row['parent'] and parent[7]==serial-1
         and parent[10:14]==(target_stages-1,1,-1,0) and parent[15:17]==(0,1)
         and parent[17].hex()==row['request'] and parent[19].hex()==row['before']
         and parent[20]==sha256(b'').digest() and parent[21]==bytes(16),
         'capture actual final journal source identity')
    need(handoff[:7]==(0x4d545031,1,40960,serial-1,target_stages-1,target_stages,parent[14])
         and handoff[7]==header[4] and 0<handoff[6]<handoff[7]
         and handoff[8]==parent[8] and handoff[10]==int(parent[9]>0) and handoff[11]==0
         and handoff[9]==(row['token'] if handoff[10] else -1)
         and handoff[12].decode('ascii')==issued['parent_hidden_sha256'],
         'capture actual final handoff hidden/token/commit binding')
    raw=bytes.fromhex(event['metadata_hex']);need(len(raw)==128,'capture exact metadata128')
    ack=struct.unpack('<QII6Q32s32s',raw)
    need(ack==(0x315950414352574f,1,128,row['epoch'],sequence,row['id'],row['parent'],
         header[4],serial,bytes.fromhex(row['request']),sha256(native).digest()),
         'capture ACK exact epoch/request/seed/parent/commit/serial/actual final record SHA')
    reply=struct.unpack('<8i4d',bytes.fromhex(event['reply_hex']))
    need(reply==(2,-1,0,128,sequence,-1,0x50525631,1,0.,0.,0.,0.),'capture dedicated raw nonterminal reply')
    timestamps=[record['monotonic_s'] for record in (issued,event,completed)]
    need(all(type(value)in(int,float) and math.isfinite(value) and value>=0 for value in timestamps)
         and timestamps==sorted(timestamps),'capture actual command timestamps/order')
    need(issued['provider_serial']==serial,'capture issued independent provider serial')

def canonical_pairs(commands, position, *, capture_ready=False,target_stages=None, prefix=None):
    need(type(capture_ready)is bool,'explicit capture-ready boolean')
    bulk=0 if prefix is None else prefix['positions']
    offset=0 if prefix is None else len(prefix['actual_native_chunks'])
    need(type(bulk)is int and 0<=bulk<position-1,'bounded actual native prefix')
    issued={};completed={};captured={};active=None;phase=0
    for command in commands:
        if command.get('owner')!='provider':
            continue
        sequence=command['sequence'];event=command['event']
        if event=='issued':
            need(active is None and sequence not in issued,'unique exclusive provider issue')
            issued[sequence]=command;active=sequence;phase=1
        elif event=='parent-captured':
            need(capture_ready and active==sequence and phase==1 and sequence not in captured,
                 'capture event requires exact opt-in outstanding provider command')
            captured[sequence]=command;phase=2
        elif event=='completed':
            need(active==sequence and phase==(2 if capture_ready else 1) and sequence not in completed,
                 'provider completion requires exact ordered capture policy')
            completed[sequence]=command;active=None;phase=0
        else:raise ValueError('unknown provider command event')
    need(active is None and set(issued)==set(completed) and len(issued)==position-1-bulk,
         'complete actual provider pair command coverage')
    need(set(captured)==set(issued) if capture_ready else not captured,'exact capture event coverage')
    need(prefix is None or sorted(issued)==list(range(offset+1,offset+1+len(issued))), 'actual prefix/suffix independent sequence seam')
    pairs=[] if prefix is None else [dict(position=r['position'],token=r['token'],hidden_bytes=r['hidden_bytes'],hidden_sha256=r['hidden_sha256']) for r in prefix['actual_native_pairs']]
    for serial,sequence in enumerate(sorted(issued),bulk+1):
        command=issued[sequence];result=completed[sequence]['provider'];row=command['row']
        if capture_ready:capture_event(command,captured[sequence],completed[sequence],serial,target_stages)
        wire=struct.unpack('<8i',bytes.fromhex(command['request_hex']))
        need(wire==(27,row['token'],serial,row['fixture'],3,sequence,0x50525631,1),
             'actual dedicated request token/position/role/depth')
        hidden=command['parent_hidden_sha256']
        need(result['provider_serial']==result['seed_position']==result['restored_position']==serial
             and result['parent_hidden_sha256']==hidden and result['restored'] is True
             and T.BUNDLE.hexhash(hidden),'actual native completion matches supplied canonical pair')
        proposal=bytes.fromhex(result['proposal_hex'])
        need(sha256(proposal).hexdigest()==result['proposal_sha256'] and len(proposal)==224
             and proposal[160:192].hex()==hidden,'native proposal raw hidden binding')
        fields=struct.unpack('<4I6Q8i32s32s32s',proposal[:192])
        need(fields[:14]==(0x44525032,2,224,2+int(row['fixture']>0),row['epoch'],sequence,
             row['id'],row['parent'],result['final_commit'],serial,serial,serial,3,
             result['available_depth']) and fields[16:18]==(0,1)
             and fields[18].hex()==row['request'] and fields[19].hex()==row['after'],
             'raw native proposal canonical source/serial/restoration identity')
        reply=struct.unpack('<8i4d',bytes.fromhex(result['reply_hex']))
        need(reply==(0,result['guesses'][0] if result['guesses'] else -1,0,224,sequence,-1,
              0x50525631,1,0.,0.,0.,0.),'actual successful dedicated completion reply')
        pairs.append(dict(position=serial,token=row['token'],hidden_bytes=40960,hidden_sha256=hidden))
    return pairs

def plan_pairs(plan,commands,position):
    """Explicit bulk opt-in; ingest original native rows, never synthesize commands."""
    enabled=plan.get('dedicated_bulk_prefill',False)
    need(type(enabled)is bool,'explicit bulk comparison boolean')
    prefix=None
    if enabled:
        sys.path.insert(0,str(ENGINE/'planning'))
        from rolling_provider.dedicated import DedicatedCoordinator
        from rolling_provider.dedicated_prefill import prefix_evidence
        need(plan.get('persistent_reset',False) is False,'bulk reset not qualified')
        model=DedicatedCoordinator(stages=len(plan['stages']),request=bytes.fromhex(plan['request_sha256']),
            epoch=plan.get('epoch',0),prompt=plan['prompt_tokens'],max_new=plan['max_new'],context=plan['context'],
            vocab=plan['vocab'],eos_token_ids=plan['eos_token_ids'],stream_bytes=40960,
            initial_sequences=[0]*len(plan['stages']),provider_sequence=0,speculative_depth=plan['speculative_depth'])
        output=Path(plan['output']);native=Path(plan['provider']['native_output'])
        prefix=prefix_evidence(output/'dedicated-prefill.jsonl',native/'provider-prefill-pairs.jsonl',
            native/'provider-prefill-chunks.jsonl',model,rows=plan['prefill_rows'],slots=plan.get('dedicated_prefill_slots',2))
    pairs=canonical_pairs(commands,position,capture_ready=plan.get('dedicated_capture_ready',False),
        target_stages=len(plan['stages']),prefix=prefix)
    return pairs,prefix

def target_candidate(spec,identity):
    canonical={};sources=[];excluded=[];cursor=0;history=None
    stages=spec['stages'];boundaries=[s['begin'] for s in stages]+[stages[-1]['end']]
    need(len(stages) in (2,3),'explicit dedicated target count')
    for ordinal,stage in enumerate(stages):
        begin,end=stage['begin'],stage['end'];need(stage['id']==ordinal and begin==cursor and begin<end<=48,'target partition')
        cursor=end;metadata,receipt=read(stage['metadata']);sources.append(receipt)
        need(metadata['mode']=='persistent-rolling' and metadata['stage_id']==ordinal
             and metadata['stage_count']==len(stages) and metadata['boundaries']==boundaries
             and metadata['begin']==begin and metadata['end']==end
             and metadata['first'] is (ordinal==0) and metadata['final'] is (ordinal==len(stages)-1)
             and metadata['provider_present'] is False and metadata['activation_dtype']=='F32' and metadata['verification_policy']=='qualification'
             and metadata['ring_epoch']==0 and metadata['ring_request_sha256']==spec['request_sha256'],
             'actual external target metadata identity')
        dump=Path(stage['dump']);hashes=T.BUNDLE.read_state(dump)
        state,sr=read(dump/'state.json');plan,pr=read(stage['plan']);att,ar=read(stage['quiescence']);sources += [sr,pr,ar]
        sealraw,seal=D.small(dump/'state-seal.txt');sources.append(seal)
        need(sr['sha256']==hashes['state.json']==sealraw.decode().splitlines()[4],'target state metadata still bound to sealed read')
        need(Path(stage['quiescence'])==dump.with_name(dump.name+'.ring-state.json')
             and att['state_seal_sha256']==seal['sha256'] and att['mode']=='persistent-rolling'
             and att['ring_epoch']==0 and att['ring_request_sha256']==spec['request_sha256']
             and att['stage_id']==ordinal and att['schema']=='ownrt.ring-state.persistent.v2', 'actual target attestation bound to dump')
        position=identity['position']
        need(att['pending_tickets']==att['active_slots']==att['sticky_error']==0
             and att['actual_position']==att['committed_position']==att['commits']==position,
             'native target quiescence/frontier')
        need(att['rows']==att['commits']+att['discarded_rows']
             and att['snapshot_captures']==att['snapshot_releases']==att['tentative_rows']
             ==att['accepted_tentative_rows']+att['discarded_rows']
             and att['byteverified_restore_count']==att['abort_count']
             and att['restore_verification_enabled'] is True and att['all_aborts_byte_verified'] is True
             and att['trace_omitted']==0
             and att['trace_records']+2*spec.get('authenticated_bulk',0)==att['rows']+att['commits']+att['abort_count'],
             'native target full scalar trace and restore conservation')
        need(hashes['position.bin']==T.sha(struct.pack('<I',position)) and hashes['error.bin']==T.sha(bytes(4)),
             'sealed target position/error')
        inactive=metadata['inactive_alternate_banks']
        need(set(att['inactive_alternate_banks'])==set(inactive) and len(inactive)==len(set(inactive))
             and set(att['canonical_bank_mapping'])==set(inactive), 'native canonical bank coverage')
        banks=[v for row in att['canonical_bank_mapping'].values() for v in row.values()]
        need(len(banks)==len(set(banks)),'native canonical bank alias')
        need(att['bank_parity']==(position%2 if ordinal==0 else 0),'native canonical bank parity')
        if ordinal==len(stages)-1:need(att['tentative_rows']==att['abort_count']==att['discarded_rows']==0,'final target never speculates')
        layout,lr=read(dump.parent/'ring-checkpoint-layout.json');sources.append(lr)
        need(lr['sha256']==att['checkpoint_layout_sha256'] and layout['provider_present'] is False
             and not layout.get('independent_draft_allocations') and not layout.get('provider_private_allocations'),
             'separate provider has no target-owned draft allocation')
        need(set(banks)<={r['id'] for r in layout['allocations']},'actual canonical banks belong to target inventory')
        for name in inactive:
            producers=[launch for launch in plan.get('launches',[]) if launch.get('op') in ('conv','gdn') and len(launch.get('outputs',[]))==2 and launch['outputs'][1]==name and name in launch.get('inputs',[])]
            need(len(producers)==1,'inactive bank unique registered temporal producer')
        layouts={}
        for buffer in plan['buffers']:
            key=buffer['name']+'.bin';dtype=buffer['dtype'].lower();shape=buffer['shape'];size=buffer['bytes']
            need(key not in layouts and bool(shape) and dtype in T.WIDTH and all(type(n)is int and n>0 for n in shape)
                 and math.prod(shape)*T.WIDTH[dtype]==size,'typed target plan inventory')
            layouts[key]=dict(dtype=dtype,shape=shape,bytes=size)
        need({k for k in hashes if k!='state.json' and not k.startswith('alternate-')}==set(layouts)
             and {k for k in hashes if k.startswith('alternate-')}=={'alternate-'+n+'.bin' for n in inactive},
             'exact target state/plan/spare inventory')
        raw,_=D.small(dump/'state-index.tsv');lengths={p[0]:int(p[2]) for p in (s.split('\t') for s in raw.decode().splitlines()[1:])}
        seen=set()
        for key,digest in hashes.items():
            if key=='state.json':continue
            base=key.removeprefix('alternate-');need(base in layouts and lengths[key]==layouts[base]['bytes'],'sealed target layout extent')
            match=T.LAYER.match(key)
            if match:
                layer=int(match[1]);need(begin<=layer<end,'absolute layer owner');seen.add(layer)
                if key.startswith('alternate-'):
                    need(base.removesuffix('.bin') in inactive,'native inactive spare');excluded.append(key);continue
                role='persistent-layer' if T.PERSISTENT.search(key) else 'layer-intermediate'
            elif key in T.GLOBAL_ALL:role='replicated-global'
            elif key in T.GLOBAL_FIRST:
                need(ordinal==0,'first target global owner');role='first-stage-global'
            elif key in T.GLOBAL_LAST:
                if ordinal==len(stages)-1:role='last-stage-global'
                elif key in ('streams.bin','next_token.bin'):excluded.append(key);continue
                else:raise ValueError('head state on nonfinal target')
            else:raise ValueError('unregistered target state '+key)
            entry=dict(sha256=digest,role=role,**layouts[base])
            need(key not in canonical or role=='replicated-global' and canonical[key]==entry,'replicated target globals')
            canonical[key]=entry
        need(seen==set(range(begin,end)),'complete target layers')
        if ordinal==0:history={key:state[key] for key in ('history0','history1')}
    need(cursor==48 and len(canonical)==2065,'complete target2065 inventory')
    return dict(input_identity=identity,layer_count=48,first_stage_host_history=history,canonical=canonical,sources=sources,excluded=excluded)

def run(path):
    spec,spec_receipt=read(path);need(spec['schema']=='ownrt.dedicated-parity-inputs.v1','explicit dedicated comparison schema')
    reference=Path(spec['reference_request']);plan,ps=read(spec['plan']);result,rs=driver_result(spec['result'])
    refplan,rps=read(reference/'selected-request-plan.json');refresult,rrs=read(reference/'result.json')
    need(plan['prompt_tokens']==refplan['prompt_tokens'] and result['output_ids']==refresult['output_ids'], 'actual prompt/output token equality')
    reference_target=T.load_set(reference/'target-set.prefill-provenance.json')
    identity=reference_target['input_identity']
    tokenhash=lambda ids:T.sha(b''.join(struct.pack('<I',token) for token in ids))
    need(tokenhash(plan['prompt_tokens'])==identity['prompt_token_sha256'] and tokenhash(result['output_ids'])==identity['output_token_sha256'],'declared target identity bound to actual prompt/output')
    need(result['input_position']==identity['position'],'actual candidate target frontier')
    need(plan['model_identity_sha256']==identity['model_sha256'],'actual model identity')
    raw,cs=trace_source(Path(spec['commands']));commands=[json.loads(line,object_pairs_hook=T.BUNDLE.pairs) for line in raw.splitlines()]
    pairs,prefix=plan_pairs(plan,commands,identity['position']);refpairs,rpairsource=read(reference/'canonical-pairs.json')
    pairhash=T.sha(json.dumps(pairs,sort_keys=True,separators=(',',':')).encode())
    need(pairs==refpairs['pairs'] and pairhash==refpairs['sha256'],'actual ordered hidden/token input pair parity')
    candidate=target_candidate(dict(spec,request_sha256=plan['request_sha256'],authenticated_bulk=0 if prefix is None else prefix['positions']),identity)
    target=T.compare(reference_target,candidate)
    refdraft=D.load_set(reference/'draft-set.json');draft=D.load_set(spec['draft_set'])
    need(draft['input_identity']['pair_sequence_sha256']==pairhash==refdraft['input_identity']['pair_sequence_sha256'], 'draft manifests bind actual verified pairs')
    draft_result=D.compare(refdraft,draft);need(len(draft['canonical'])==73,'complete draft73 inventory')
    receipts=[]
    need(len(set(spec['process_receipts']))==len(spec['process_receipts']),'distinct process receipts')
    need(len(spec['process_receipts'])==len(spec['stages'])+1,'all target/provider terminal receipts required')
    for receipt_path in spec['process_receipts']:
        receipt,source=read(receipt_path);need(receipt['passed'] is True and not receipt.get('error'),'clean native FINISH/shutdown');
        need(receipt.get('teardown') and all(t['status']=='complete' and t['safe_to_exit'] is True and t['idle_marker_complete'] is True and t['in_flight']==t['live_bytes']==0 and not t['error'] for t in receipt['teardown']),'complete idle native teardown')
        receipts.append(source)
    return dict(schema='ownrt.dedicated-state-parity.v1',passed=target['passed'] and draft_result['passed'],
        scope='Cross-partition target2065 and separate-provider draft73 sealed byte/layout parity; actual ordered input hidden/token pairs and output IDs equal; native scalar target restore checks and clean terminal receipts. Not independent model correctness or performance proof.',
        target=target,draft=draft_result,pair_sequence_sha256=pairhash,
        sources=[spec_receipt,ps,rs,rps,rrs,cs,rpairsource]+([] if prefix is None else prefix['sources'])+receipts,helper_sha256=T.sha(Path(__file__).read_bytes()))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('manifest',type=Path);parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    try:result=run(args.manifest)
    except (ValueError,KeyError,OSError,TypeError,struct.error,UnicodeError) as error:result=dict(passed=False,input_error=str(error))
    with args.out.open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    raise SystemExit(0 if result['passed'] else 1)
