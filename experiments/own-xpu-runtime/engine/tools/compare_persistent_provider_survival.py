"""Persistent-only qualification/measured survival evidence, preserving v5/v6."""
from compare_pipeline_state import require,provider_owner,speculative_depth
from compare_rolling_provider_survival import survival_bytes,validate_survival as qualified_survival
from persistent_ring_policy import EMPTY_SHA,validate_policy


def validate_survival(path,stage,dump,spec,layout,metadata,att):
    depth=speculative_depth(spec)
    owns_provider=provider_owner(spec,metadata,stage)
    validate_policy(att,policy=spec['verification_policy'],first=metadata['first'],provider=owns_provider,depth=depth)
    if spec['verification_policy']=='qualification':
        require(spec.get('provider_stage',0)==0, 'remote debug-policy survival qualification unsupported; measured full-state gate only')
        return qualified_survival(path,stage,dump,spec,layout,metadata,att)
    pending=att['provider_pending_borrows']
    require(isinstance(pending,dict) and set(pending)=={str(i) for i in range(1,depth+1)}
            and all(type(v)is int and 0<=v<=2**64-1 for v in pending.values()),'persistent observed pending depth counters')
    if not owns_provider:
        require(pending=={str(i):0 for i in range(1,depth+1)} and att['provider_quiescent_borrows']==0 and 'provider_survival' not in stage,
                'nonfirst persistent owner cannot claim provider borrowing')
        return []
    require(type(att['provider_quiescent_borrows'])is int and att['provider_quiescent_borrows']>=0
            and sum(pending.values())==att['provider_borrows_while_target_pending']
            and att['provider_quiescent_borrows']+sum(pending.values())==att['provider_commands'],
            'measured borrowing counts must remain complete')
    require(all(pending[str(d)]>0 for d in spec['required_provider_pending_depths']),'required actual pending depth absent')
    declared=path.parent/stage['provider_survival']
    require(not declared.is_symlink() and declared.resolve()==dump.parent/'ring-provider-survival.jsonl',
            'measured survival trace must be native sibling')
    raw,receipt=survival_bytes(declared)
    require(raw==b'' and receipt['sha256']==att['provider_survival_receipt_sha256']==EMPTY_SHA,
            'measured run cannot retain invented survival checks')
    return [receipt]
