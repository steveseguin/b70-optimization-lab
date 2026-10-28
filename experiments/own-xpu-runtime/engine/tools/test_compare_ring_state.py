"""CPU fixtures qualify the separate ring attestation and reject unsafe promotion."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from test_compare_pipeline_state import COMPARE, digest, make_set, make_wavefront


def make_ring(root):
    path=make_wavefront(root,[0,1,2,3,4])
    manifest=json.loads(path.read_text())
    manifest.update(schema='ownrt.pipeline-state-set.v3',mode='verified-ring',ring_request_sha256='d'*64,ring_epoch=0)
    for stage in manifest['stages']:
        meta_path=root/stage['metadata'];meta=json.loads(meta_path.read_text())
        meta.update(mode='verified-ring',ring_capacity=2,depth=2,ring_request_sha256='d'*64,ring_epoch=0);meta_path.write_text(json.dumps(meta))
        old=root/stage['quiescence'];wave=json.loads(old.read_text())
        target=[dict(id=1,label='card0:target',bytes=32)]
        mapping=wave['canonical_bank_mapping']
        for name,row in mapping.items():
            for label,key in [('active','active_allocation'),('spare','inactive_allocation')]:
                target.append(dict(id=row[key],label=name+':'+label,bytes=16))
        size=sum(r['bytes'] for r in target)
        for row in target:row.update(saved_bytes=row['bytes'],checkpoint='full-allocation')
        private=[dict(id=100+3*i+j,label=f'card0:ring:{i}:{kind}',bytes=size if kind=='image' else 32)
                 for i in (0,1) for j,kind in enumerate(('image','capture','restore'))]
        layout=dict(schema='ownrt.ring-checkpoint-layout.sparse.v1',complete_target_owned_mutable_allocations=False,
                    target_mutable_allocation_coverage='complete',checkpoint_policy='full-non-qsa+sparse-positional-qsa-rows',
                    provider_present=False,ring_capacity=2,slot_reserve_bytes=size,slot_bytes=size,allocations=target,
                    excluded_private_runtime_allocations=[],checkpoint_private_allocations=private)
        layout_path=old.parent/'ring-checkpoint-layout.json';layout_path.write_text(json.dumps(layout))
        final=meta['final'];discarded=0 if final else 3;captures=0 if final else 4;aborts=0 if final else 2
        att=dict(schema='ownrt.ring-state.v1',mode='verified-ring',stage_id=stage['id'],
            ring_request_sha256='d'*64,ring_epoch=0,ring_capacity=2,depth=2,dump_marker=2147483647,
            state_seal_sha256=wave['state_seal_sha256'],checkpoint_layout_sha256=digest(layout_path.read_bytes()),
            actual_position=7,committed_position=7,pending_tickets=0,active_slots=0,sticky_error=0,
            rows=7+discarded,tentative_rows=captures,commits=7,accepted_tentative_rows=captures-discarded,
            abort_count=aborts,discarded_rows=discarded,snapshot_captures=captures,snapshot_releases=captures,
            byteverified_restore_count=aborts,saved_bytes=size*captures,target_mutable_checkpoint_bytes=size,
            restore_verification_enabled=True,all_aborts_byte_verified=True,bank_parity=wave['bank_parity'],
            max_pending=1 if final else 2,trace_records=14+discarded+aborts,trace_omitted=0,
            inactive_alternate_banks=wave['inactive_alternate_banks'],canonical_bank_mapping=mapping)
        att_path=old.with_name(old.name.replace('.wavefront-state.json','.ring-state.json'))
        att_path.write_text(json.dumps(att));stage['quiescence']=str(att_path.relative_to(root))
    path.write_text(json.dumps(manifest))
    return path


class RingComparisonTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        self.reference=make_set(self.root/'gold',[0,2,4])
        self.ring=make_ring(self.root/'ring')
        self.spec=json.loads(self.ring.read_text())
        self.att_path=self.ring.parent/self.spec['stages'][0]['quiescence']
        self.att=json.loads(self.att_path.read_text())

    def test_ring_compares_all_canonical_state_without_new_omissions(self):
        result=COMPARE.compare(COMPARE.load_set(self.reference),COMPARE.load_set(self.ring))
        self.assertTrue(result['passed'])
        self.assertIn('blk.0.gdn.state.bin',result['compared_source_keys'])
        self.assertEqual(len(result['candidate']['quiescence_attestations']),4)

    def test_unsafe_attestation_changes_fail_closed(self):
        changes=dict(schema='ownrt.ring-state.v9',mode='verified-wavefront',stage_id=1,ring_request_sha256='e'*64,
            ring_epoch=1,ring_capacity=1,depth=1,dump_marker=0,state_seal_sha256='0'*64,
            checkpoint_layout_sha256='0'*64,actual_position=8,committed_position=8,pending_tickets=1,
            active_slots=1,sticky_error=1,rows=99,tentative_rows=3,commits=True,accepted_tentative_rows=2,
            abort_count=1,discarded_rows=4,snapshot_captures=3,snapshot_releases=3,
            byteverified_restore_count=1,saved_bytes=1,target_mutable_checkpoint_bytes=1,
            restore_verification_enabled=False,all_aborts_byte_verified=False,bank_parity=0,
            max_pending=3,trace_records=0,trace_omitted=1,
            inactive_alternate_banks=[],canonical_bank_mapping={})
        for field,value in changes.items():
            with self.subTest(field=field):
                self.att_path.write_text(json.dumps(dict(self.att,**{field:value})))
                with self.assertRaises(ValueError):COMPARE.load_set(self.ring)
        self.att_path.write_text(json.dumps(self.att))

    def test_hash_resealed_invalid_layout_still_fails(self):
        layout_path=self.att_path.parent/'ring-checkpoint-layout.json'
        original=json.loads(layout_path.read_text())
        variants=[]
        for field,value in [('schema','unknown'),('provider_present',True),('complete_target_owned_mutable_allocations',True),
                            ('ring_capacity',1),('slot_bytes',1),('slot_reserve_bytes',1),('checkpoint_private_allocations',[])]:
            variants.append(dict(original,**{field:value}))
        duplicate=copy.deepcopy(original);duplicate['checkpoint_private_allocations'][0]['id']=original['allocations'][0]['id'];variants.append(duplicate)
        omit=copy.deepcopy(original);omit['excluded_private_runtime_allocations']=[dict(id=77,label='card0:real-state',bytes=4)];variants.append(omit)
        for layout in variants:
            layout_path.write_text(json.dumps(layout))
            self.att_path.write_text(json.dumps(dict(self.att,checkpoint_layout_sha256=digest(layout_path.read_bytes()))))
            with self.assertRaises(ValueError):COMPARE.load_set(self.ring)

    def test_v1_v2_cannot_relabel_ring_quiescence(self):
        for schema,mode in [('ownrt.pipeline-state-set.v1','target-only'),('ownrt.pipeline-state-set.v2','verified-wavefront')]:
            self.ring.write_text(json.dumps(dict(self.spec,schema=schema,mode=mode)))
            with self.assertRaises(ValueError):COMPARE.load_set(self.ring)

    def test_require_verification_is_explicit_even_for_no_aborts(self):
        del self.spec['require_byte_verified_restores'];self.ring.write_text(json.dumps(self.spec))
        with self.assertRaisesRegex(ValueError,'explicitly declare'):COMPARE.load_set(self.ring)

    def test_disabled_verification_is_only_accepted_when_explicitly_requested(self):
        self.spec['require_byte_verified_restores']=False;self.ring.write_text(json.dumps(self.spec))
        for stage in self.spec['stages']:
            p=self.ring.parent/stage['quiescence'];att=json.loads(p.read_text())
            att.update(restore_verification_enabled=False,byteverified_restore_count=0,all_aborts_byte_verified=att['abort_count']==0)
            p.write_text(json.dumps(att))
        self.assertTrue(COMPARE.compare(COMPARE.load_set(self.reference),COMPARE.load_set(self.ring))['passed'])


if __name__=='__main__':unittest.main()
