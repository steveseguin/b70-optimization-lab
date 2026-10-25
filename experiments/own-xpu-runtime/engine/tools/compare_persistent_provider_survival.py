"""Persistent-only qualification/measured survival evidence, preserving v5/v6."""
from compare_pipeline_state import require
from compare_rolling_provider_survival import survival_bytes,validate_survival as qualified_survival
from persistent_ring_policy import EMPTY_SHA,validate_policy


def validate_survival(path,stage,dump,spec,layout,metadata,att):
    validate_policy(att,policy=spec['verification_policy'],first=metadata['first'])
    if spec['verification_policy']=='qualification':
        return qualified_survival(path,stage,dump,spec,layout,metadata,att)
    pending=att['provider_pending_borrows']
    require(isinstance(pending,dict) and set(pending)=={'1','2'}
            and all(type(v)is int and 0<=v<=2**64-1 for v in pending.values()),'persistent observed pending depth counters')
    if not metadata['first']:
        require(pending=={'1':0,'2':0} and att['provider_quiescent_borrows']==0 and 'provider_survival' not in stage,
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
