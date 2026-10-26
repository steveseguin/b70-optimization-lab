"""New persistent policy authority; old v5/v6 verification semantics stay intact."""
import hashlib
from compare_pipeline_state import require

EMPTY_SHA=hashlib.sha256(b'').hexdigest()


def validate_policy(att, *, policy, first, provider=None):
    require(policy in ('qualification','measured') and type(first)is bool,'explicit persistent fixed policy/owner required')
    require(att['schema']=='ownrt.ring-state.persistent.v1' and att['mode']=='persistent-rolling'
            and att['verification_policy']==policy,'persistent attestation policy identity differs')
    require(provider is None or type(provider)is bool,'provider policy role must be boolean')
    first=first if provider is None else provider
    enabled=policy=='qualification'
    controls=dict(target_restore_byte_checks_enabled=enabled,
                  provider_recursive_byte_checks_enabled=enabled and first,
                  provider_abort_survival_checks_enabled=enabled and first)
    require(all(att[k] is v for k,v in controls.items()),'persistent per-domain check controls differ from process policy')
    require(att['restore_verification_enabled'] is enabled
            and att['provider_restore_verification_enabled'] is (enabled and first)
            and att['provider_survival_verification_enabled'] is (enabled and first),'legacy flags differ from fixed persistent policy')
    integer_keys=('abort_count','target_snapshot_restores','target_host_restore_checks','byteverified_restore_count',
        'provider_snapshot_captures','provider_snapshot_restores','provider_host_restore_checks',
        'provider_canonical_commands_checked','provider_commands','provider_byteverified_restore_count',
        'provider_survival_records','provider_survival_discarded_rows','provider_survival_advanced_records',
        'provider_survival_bytes_verified','provider_survival_host_verified','provider_survival_sequence_verified',
        'provider_survival_private_verified','provider_survival_bindings_verified')
    require(all(type(att[k])is int and 0<=att[k]<=2**64-1 for k in integer_keys),'persistent actual counters require bounded integers')
    require(att['target_snapshot_restores']==att['target_host_restore_checks']==att['abort_count'],
            'target restore/cold host checks must remain mandatory')
    require(att['provider_snapshot_captures']==att['provider_snapshot_restores']==att['provider_host_restore_checks']
            and att['provider_canonical_commands_checked']==att['provider_commands'],
            'provider copy/host/canonical command checks must remain mandatory')
    require(att['byteverified_restore_count']==(att['abort_count'] if enabled else 0)
            and att['all_aborts_byte_verified'] is enabled,'target byte verification claimed while omitted or incomplete')
    require(att['provider_byteverified_restore_count']==(att['provider_snapshot_restores'] if enabled and first else 0)
            and att['provider_all_restores_byte_verified'] is (enabled and first),
            'provider byte verification claimed while omitted or incomplete')
    if not first:
        require(all(att[k]==0 for k in integer_keys if k.startswith('provider_'))
                and att['provider_survival_receipt_sha256']=='','nonfirst stage cannot own provider checks')
    elif not enabled:
        require(all(att[k]==0 for k in integer_keys if k.startswith('provider_survival_'))
                and att['provider_survival_receipt_sha256']==EMPTY_SHA,
                'measured run must not invent provider survival evidence')
    else:
        count=att['provider_survival_records']
        require(count==att['abort_count'] and 0<=att['provider_survival_advanced_records']<=count
                and all(att[k]==count for k in ('provider_survival_bytes_verified','provider_survival_host_verified',
                    'provider_survival_sequence_verified','provider_survival_private_verified','provider_survival_bindings_verified')),
                'qualification requires actual complete provider survival checks')
    return dict(policy=policy,target_restore_checks_performed=enabled,
                provider_restore_checks_performed=enabled and first,
                provider_abort_survival_checks_performed=enabled and first)
