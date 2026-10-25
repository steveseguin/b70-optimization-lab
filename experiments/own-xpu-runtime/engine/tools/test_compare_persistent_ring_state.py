import json
from pathlib import Path
import tempfile
import unittest
import test_compare_pending_provider_state as fixture

COMPARE,digest=fixture.COMPARE,fixture.digest


def make_persistent(root,policy):
    path=fixture.make_pending(root);spec=json.loads(path.read_text());enabled=policy=='qualification'
    spec.update(schema='ownrt.pipeline-state-set.v7',mode='persistent-rolling',controller_mode='persistent-rolling',
        actual_proposals_only=True,verification_policy=policy,ring_epoch=1,require_byte_verified_restores=enabled,
        require_provider_byte_verified_restores=enabled,require_provider_survival_checks=enabled,required_provider_pending_depths=[])
    for stage in spec['stages']:
        mp=root/stage['metadata'];meta=json.loads(mp.read_text());meta.update(mode=spec['mode'],ring_epoch=1,verification_policy=policy);mp.write_text(json.dumps(meta))
        ap=root/stage['quiescence'];att=json.loads(ap.read_text());first=meta['first'];provider=enabled and first
        att.update(schema='ownrt.ring-state.persistent.v1',mode=spec['mode'],verification_policy=policy,ring_epoch=1,
            target_restore_byte_checks_enabled=enabled,provider_recursive_byte_checks_enabled=provider,
            provider_abort_survival_checks_enabled=provider,target_snapshot_restores=att['abort_count'],target_host_restore_checks=att['abort_count'],
            provider_host_restore_checks=att['provider_snapshot_restores'],provider_canonical_commands_checked=att['provider_commands'],
            restore_verification_enabled=enabled,provider_restore_verification_enabled=provider,provider_survival_verification_enabled=provider,
            byteverified_restore_count=att['abort_count'] if enabled else 0,all_aborts_byte_verified=enabled,
            provider_byteverified_restore_count=att['provider_snapshot_restores'] if provider else 0,provider_all_restores_byte_verified=provider)
        if first:
            rp=root/stage['provider_survival'];rows=[json.loads(line) for line in rp.read_text().splitlines()]
            if not enabled:
                rows=[]
                for key in list(att):
                    if key.startswith('provider_survival_') and type(att[key])is int:att[key]=0
            for record in rows:
                record['ring_epoch']=1;record['oldest']['epoch']=1
                for capture in record['provider_at_capture']:capture['row']['epoch']=1
                payload=json.loads(record['before_payload']);payload['sequence']['epoch']=1;payload['sequence']['last_seed']['epoch']=1
                raw=json.dumps(payload);record.update(before_payload=raw,after_payload=raw,
                    before_payload_sha256=digest(raw.encode()),after_payload_sha256=digest(raw.encode()))
            rp.write_text(''.join(json.dumps(r)+'\n' for r in rows));att['provider_survival_receipt_sha256']=digest(rp.read_bytes())
        ap.write_text(json.dumps(att))
    path.write_text(json.dumps(spec));return path


class PersistentStateTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name)
        self.gold=fixture.make_set(self.root/'gold',[0,2,4])

    def test_both_policies_compare_all_canonical_target_and_draft_state(self):
        for policy in ('qualification','measured'):
            path=make_persistent(self.root/policy,policy)
            self.assertTrue(COMPARE.compare(COMPARE.load_set(self.gold),COMPARE.load_set(path))['passed'])

    def test_measured_cannot_relabel_old_v6_or_claim_omitted_checks(self):
        path=make_persistent(self.root/'measured','measured');spec=json.loads(path.read_text())
        ap=path.parent/spec['stages'][0]['quiescence'];original=json.loads(ap.read_text())
        for key,value in [('provider_byteverified_restore_count',3),('provider_all_restores_byte_verified',True),
                          ('target_host_restore_checks',0),('provider_canonical_commands_checked',0)]:
            ap.write_text(json.dumps(dict(original,**{key:value})))
            with self.subTest(key=key),self.assertRaises(ValueError):COMPARE.load_set(path)
        ap.write_text(json.dumps(original));spec.update(schema='ownrt.pipeline-state-set.v6',mode='verified-ring-pending-provider')
        path.write_text(json.dumps(spec))
        with self.assertRaises(ValueError):COMPARE.load_set(path)

    def test_policy_override_or_epoch_zero_is_not_persistent_request(self):
        path=make_persistent(self.root/'qualified','qualification');spec=json.loads(path.read_text())
        for key,value in [('ring_epoch',0),('verification_policy','measured'),('require_byte_verified_restores',False)]:
            path.write_text(json.dumps(dict(spec,**{key:value})))
            with self.subTest(key=key),self.assertRaises(ValueError):COMPARE.load_set(path)


if __name__=='__main__':unittest.main()
