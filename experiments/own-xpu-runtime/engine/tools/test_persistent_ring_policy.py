import copy
import unittest
from persistent_ring_policy import validate_policy,EMPTY_SHA


def fixture(policy='qualification',first=True,aborts=2,restores=3):
    enabled=policy=='qualification';provider=enabled and first
    att=dict(schema='ownrt.ring-state.persistent.v1',mode='persistent-rolling',verification_policy=policy,
        target_restore_byte_checks_enabled=enabled,provider_recursive_byte_checks_enabled=provider,
        provider_abort_survival_checks_enabled=provider,restore_verification_enabled=enabled,
        provider_restore_verification_enabled=provider,provider_survival_verification_enabled=provider,
        abort_count=aborts,target_snapshot_restores=aborts,target_host_restore_checks=aborts,
        byteverified_restore_count=aborts if enabled else 0,all_aborts_byte_verified=enabled,
        provider_snapshot_captures=restores if first else 0,provider_snapshot_restores=restores if first else 0,
        provider_host_restore_checks=restores if first else 0,provider_commands=7 if first else 0,
        provider_canonical_commands_checked=7 if first else 0,provider_byteverified_restore_count=restores if provider else 0,
        provider_all_restores_byte_verified=provider,provider_survival_records=aborts if provider else 0,
        provider_survival_discarded_rows=aborts if provider else 0,provider_survival_advanced_records=aborts if provider else 0,
        provider_survival_receipt_sha256=('a'*64 if provider and aborts else EMPTY_SHA) if first else '')
    for key in ('bytes','host','sequence','private','bindings'):att['provider_survival_'+key+'_verified']=aborts if provider else 0
    return att


class PersistentPolicyTests(unittest.TestCase):
    def test_fixed_policies_keep_mandatory_restore_and_host_checks(self):
        for policy in ('qualification','measured'):
            for first in (False,True):
                for aborts in (0,2):
                    self.assertEqual(validate_policy(fixture(policy,first,aborts),policy=policy,first=first)['policy'],policy)

    def test_measured_cannot_claim_even_vacuous_byte_verification(self):
        original=fixture('measured',True,0,0)
        for key,value in [('all_aborts_byte_verified',True),('provider_all_restores_byte_verified',True),
            ('byteverified_restore_count',1),('provider_byteverified_restore_count',1),('provider_survival_records',1),
            ('provider_survival_receipt_sha256','a'*64),('provider_abort_survival_checks_enabled',True)]:
            att=copy.deepcopy(original);att[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):validate_policy(att,policy='measured',first=True)

    def test_missing_mandatory_checks_or_policy_change_refused(self):
        for policy in ('qualification','measured'):
            for key in ('target_snapshot_restores','target_host_restore_checks','provider_host_restore_checks','provider_canonical_commands_checked'):
                att=fixture(policy);att[key]-=1
                with self.subTest(policy=policy,key=key),self.assertRaises(ValueError):validate_policy(att,policy=policy,first=True)
        with self.assertRaises(ValueError):validate_policy(fixture('measured'),policy='qualification',first=True)


if __name__=='__main__':unittest.main()
