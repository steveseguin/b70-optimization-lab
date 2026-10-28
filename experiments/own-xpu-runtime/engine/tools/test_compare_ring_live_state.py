"""Separate live-ring authority binds canonical draft bytes and target quiescence."""
import copy
import json
import shutil
import struct
import tempfile
from pathlib import Path
import unittest

from test_compare_ring_state import make_ring,COMPARE,digest
from test_compare_pipeline_state import make_set
from test_compare_draft_state import fixture,seal


def make_live(root):
    path=make_ring(root)
    spec=json.loads(path.read_text())
    draft_path,buffers,state=fixture(root/'draft-source')
    first=spec['stages'][0]
    meta=json.loads((root/first['metadata']).read_text())
    buffers['card0:draft:position']=struct.pack('<i',6)
    buffers['card0:draft:half-staging']=bytes(4+meta['stream_bytes'])
    state['host']['position']=6
    state['layouts']['card0:draft:half-staging']['bytes']=len(buffers['card0:draft:half-staging'])
    seal(draft_path.parent/'dump',buffers,state)
    draft_spec=json.loads(draft_path.read_text());draft_spec['input_identity']['position']=6
    destination=(root/first['dump']).with_name(Path(first['dump']).name+'.draft')
    shutil.move(draft_path.parent/'dump',destination)
    draft_spec['dump']=str(destination.relative_to(root));draft_path=root/'draft-set.json'
    draft_path.write_text(json.dumps(draft_spec));first['draft_state_set']='draft-set.json'
    spec.update(schema='ownrt.pipeline-state-set.v4',mode='verified-ring-live',
                provider_borrow_mode='quiescent-target',require_provider_byte_verified_restores=True,
                draft_input_identity=draft_spec['input_identity'])
    for stage in spec['stages']:
        metadata_path=root/stage['metadata'];metadata=json.loads(metadata_path.read_text())
        metadata['mode']='verified-ring-live';metadata['provider_borrow_mode']='quiescent-target';metadata_path.write_text(json.dumps(metadata))
        att_path=root/stage['quiescence'];att=json.loads(att_path.read_text())
        layout_path=att_path.parent/'ring-checkpoint-layout.json';layout=json.loads(layout_path.read_text())
        first=stage['id']==0
        canonical=[dict(id=200+i,label=key,bytes=value['bytes'],saved_bytes=value['bytes'],memory=value['memory'])
                   for i,(key,value) in enumerate(state['layouts'].items())] if first else []
        size=sum(row['bytes'] for row in canonical if row['memory']=='device')
        layout.update(schema='ownrt.ring-checkpoint-layout.live.sparse.v1',provider_present=first,
                      independent_draft_allocations=canonical,
                      provider_private_allocations=[dict(id=300,label='card0:draft:recursive-private-image',bytes=size,memory='device')] if first else [])
        layout_path.write_text(json.dumps(layout))
        for key in ('tentative_rows','accepted_tentative_rows','abort_count','discarded_rows','snapshot_captures','snapshot_releases','byteverified_restore_count','saved_bytes'):
            att[key]=0
        att.update(schema='ownrt.ring-state.live.v1',mode='verified-ring-live',rows=7,max_pending=1,trace_records=14,
                   checkpoint_layout_sha256=digest(layout_path.read_bytes()),provider_borrow_mode='quiescent-target',
                   provider_present=first,provider_borrows_while_target_pending=0,
                   canonical_draft_state_seal_sha256=digest((destination/'state-seal.txt').read_bytes()) if first else '',
                   provider_position=6 if first else None,provider_serial=6 if first else 0,provider_commands=6 if first else 0,
                   provider_recursive_active=False,provider_snapshot_captures=3 if first else 0,
                   provider_snapshot_restores=3 if first else 0,provider_byteverified_restore_count=3 if first else 0,
                   provider_restore_verification_enabled=first,provider_all_restores_byte_verified=True,
                   provider_private_bytes=size,provider_canonical_allocation_count=len(canonical),
                   provider_trace_records=6 if first else 0,provider_trace_omitted=0)
        att_path.write_text(json.dumps(att))
    path.write_text(json.dumps(spec))
    return path


class LiveRingTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name)
        self.reference=make_set(self.root/'gold',[0,2,4]);self.path=make_live(self.root/'live')
        self.spec=json.loads(self.path.read_text());self.att_path=self.path.parent/self.spec['stages'][0]['quiescence']
        self.att=json.loads(self.att_path.read_text())

    def test_exact_target_and_bound_full_draft_inventory(self):
        result=COMPARE.compare(COMPARE.load_set(self.reference),COMPARE.load_set(self.path))
        self.assertTrue(result['passed'])
        self.assertTrue(any(Path(r['path']).name=='draft-set.json' for r in result['candidate']['sources']))

    def test_sparse_private_reserve_uses_saved_bytes(self):
        path=self.att_path.parent/'ring-checkpoint-layout.json';layout=json.loads(path.read_text())
        for row in layout['independent_draft_allocations']:
            if row['memory']=='device':row['saved_bytes']=1
        reserve=sum(row['saved_bytes'] for row in layout['independent_draft_allocations'] if row['memory']=='device')
        layout['provider_private_allocations'][0]['bytes']=reserve;path.write_text(json.dumps(layout))
        self.att.update(provider_private_bytes=reserve,checkpoint_layout_sha256=digest(path.read_bytes()));self.att_path.write_text(json.dumps(self.att))
        self.assertTrue(COMPARE.compare(COMPARE.load_set(self.reference),COMPARE.load_set(self.path))['passed'])

    def test_262k_accounting_geometry(self):
        target=3853756052+2*3783064464+3780215860
        fixed=17752386
        full_draft=fixed+2*268435456+67108864+16777216
        depth2=fixed+2*(1024+1024+256)+256
        depth3=fixed+3*(1024+1024+256)+256
        self.assertGreater(target+full_draft,4*1024**3)
        self.assertEqual(full_draft,638509378)
        self.assertEqual(depth2,17757250)
        self.assertEqual(depth3,17759554)
        self.assertLess(depth3,full_draft)
    def test_live_mode_cannot_be_relabelled_as_old_ring(self):
        self.spec.update(schema='ownrt.pipeline-state-set.v3',mode='verified-ring')
        self.path.write_text(json.dumps(self.spec))
        with self.assertRaises(ValueError):COMPARE.load_set(self.path)

    def test_provider_state_and_policy_tampering_refused(self):
        changes=dict(provider_borrow_mode='overlap',provider_present=False,provider_borrows_while_target_pending=1,
            canonical_draft_state_seal_sha256='0'*64,provider_position=7,provider_serial=7,provider_commands=7,
            provider_recursive_active=True,provider_snapshot_captures=4,provider_snapshot_restores=2,
            provider_byteverified_restore_count=2,provider_restore_verification_enabled=False,
            provider_all_restores_byte_verified=False,provider_private_bytes=1,provider_canonical_allocation_count=4,
            provider_trace_records=5,provider_trace_omitted=1)
        for key,value in changes.items():
            with self.subTest(key=key):
                self.att_path.write_text(json.dumps(dict(self.att,**{key:value})))
                with self.assertRaises(ValueError):COMPARE.load_set(self.path)

    def test_resealed_layout_cannot_omit_alias_or_reclassify_draft(self):
        path=self.att_path.parent/'ring-checkpoint-layout.json';original=json.loads(path.read_text())
        variants=[]
        removed=copy.deepcopy(original);removed['independent_draft_allocations'].pop();variants.append(removed)
        for collection,key,value in [('independent_draft_allocations','memory','pinned'),
                                      ('provider_private_allocations','id',original['allocations'][0]['id']),
                                      ('provider_private_allocations','label','card0:draft:scratch'),
                                      ('provider_private_allocations','bytes',1)]:
            changed=copy.deepcopy(original);changed[collection][0][key]=value;variants.append(changed)
        for variant in variants:
            path.write_text(json.dumps(variant));self.att_path.write_text(json.dumps(dict(self.att,checkpoint_layout_sha256=digest(path.read_bytes()))))
            with self.assertRaises(ValueError):COMPARE.load_set(self.path)

    def test_actual_speculative_target_history_refused_even_if_conserved(self):
        self.att.update(rows=8,tentative_rows=1,discarded_rows=1,abort_count=1,snapshot_captures=1,
                        snapshot_releases=1,byteverified_restore_count=1,
                        saved_bytes=self.att['target_mutable_checkpoint_bytes'],trace_records=16)
        self.att_path.write_text(json.dumps(self.att))
        with self.assertRaisesRegex(ValueError,'speculative target rows'):COMPARE.load_set(self.path)

    def test_draft_raw_corruption_not_hidden_by_attestation(self):
        dump=(self.path.parent/self.spec['stages'][0]['dump']).with_name('state-2147483647.draft')
        raw=(dump/'state.bundle').read_bytes();(dump/'state.bundle').write_bytes(b'x'+raw[1:])
        with self.assertRaises(ValueError):COMPARE.load_set(self.path)


if __name__=='__main__':unittest.main()
