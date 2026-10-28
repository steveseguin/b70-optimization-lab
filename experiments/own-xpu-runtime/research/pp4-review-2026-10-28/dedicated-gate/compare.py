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

def trace_source(path):
    path=Path(path);fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd);need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and 0<before.st_size<=128*1024**2,'bounded actual trace')
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

def canonical_pairs(commands, position):
    issued={};completed={}
    for command in commands:
        if command.get('owner')!='provider':
            continue
        sequence=command['sequence'];event=command['event']
        destination=issued if event=='issued' else completed if event=='completed' else None
        need(destination is not None and sequence not in destination,'unique actual provider command event')
        destination[sequence]=command
    need(set(issued)==set(completed) and len(issued)==position-1,'complete actual provider pair command coverage')
    pairs=[]
    for serial,sequence in enumerate(sorted(issued),1):
        command=issued[sequence];result=completed[sequence]['provider'];row=command['row']
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
             and att['trace_records']==att['rows']+att['commits']+att['abort_count'],
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
    reference=Path(spec['reference_request']);plan,ps=read(spec['plan']);result,rs=read(spec['result'])
    refplan,rps=read(reference/'selected-request-plan.json');refresult,rrs=read(reference/'result.json')
    need(plan['prompt_tokens']==refplan['prompt_tokens'] and result['output_ids']==refresult['output_ids'], 'actual prompt/output token equality')
    reference_target=T.load_set(reference/'target-set.prefill-provenance.json')
    identity=reference_target['input_identity']
    tokenhash=lambda ids:T.sha(b''.join(struct.pack('<I',token) for token in ids))
    need(tokenhash(plan['prompt_tokens'])==identity['prompt_token_sha256'] and tokenhash(result['output_ids'])==identity['output_token_sha256'],'declared target identity bound to actual prompt/output')
    need(result['input_position']==identity['position'],'actual candidate target frontier')
    need(plan['model_identity_sha256']==identity['model_sha256'],'actual model identity')
    raw,cs=trace_source(Path(spec['commands']));commands=[json.loads(line,object_pairs_hook=T.BUNDLE.pairs) for line in raw.splitlines()]
    pairs=canonical_pairs(commands,identity['position']);refpairs,rpairsource=read(reference/'canonical-pairs.json')
    pairhash=T.sha(json.dumps(pairs,sort_keys=True,separators=(',',':')).encode())
    need(pairs==refpairs['pairs'] and pairhash==refpairs['sha256'],'actual ordered hidden/token input pair parity')
    candidate=target_candidate(dict(spec,request_sha256=plan['request_sha256']),identity)
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
        sources=[spec_receipt,ps,rs,rps,rrs,cs,rpairsource]+receipts,helper_sha256=T.sha(Path(__file__).read_bytes()))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('manifest',type=Path);parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    try:result=run(args.manifest)
    except (ValueError,KeyError,OSError,TypeError) as error:result=dict(passed=False,input_error=str(error))
    with args.out.open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    raise SystemExit(0 if result['passed'] else 1)
