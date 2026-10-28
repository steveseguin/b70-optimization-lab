"""Scoped measured-long derivative; no claim of byte-verified abort restores.
Original qualification helper remains unchanged. All inventory/bank/scalar trace checks retained.
"""
from compare import *

def measured_target_candidate(spec,identity):
    need(spec.get("registered_verification_policy")=="measured","explicit measured-long policy")
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
             and metadata['provider_present'] is False and metadata['activation_dtype']=='F32' and metadata['verification_policy']=='measured'
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
             and att['byteverified_restore_count']==0
             and att['restore_verification_enabled'] is False and att['all_aborts_byte_verified'] is False
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
