"""Explicit v5 binds complete provider survival receipts without weakening v4."""
import copy
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest

from test_compare_ring_live_state import make_live,COMPARE,digest,make_set
import compare_provider_survival as survival


def row(position,rowid,parent,before,ticket,tentative):
    return dict(epoch=0,id=rowid,parent=parent,ticket=ticket,position=position,token=7,fixture=1,tentative=tentative,
        request='d'*64,before=before,after=digest(b'ownrt.ring-prefix.v1\0'+bytes.fromhex(before)+struct.pack('<II',position,7)))


def payload(layout,meta,position,sequence):
    allocations=[]
    for role,key in [('canonical','independent_draft_allocations'),('recursive-image','provider_private_allocations')]:
        for allocation in layout[key]:
            value=dict(allocation,role=role,sha256='f'*64);value.pop('saved_bytes',None)
            if value['label']=='card0:draft:position':value['sha256']=digest(struct.pack('<i',position))
            allocations.append(value)
    private=layout['provider_private_allocations'][0]
    state=dict(position=position,extent=32,pending_confirmed=0,queued_probe=-1,queued_confirmed=-1,depth=0,
        disabled=False,async_pending=False,pending_head=False,reverse_present=False,captured=True,publication_event=0,
        pending_start_ticks=0,reverse_bytes=meta['stream_bytes'],reverse_sha256='b'*64)
    seed=row(position,position*3,position*3-1,'c'*64,sequence-10,False)
    return dict(schema='ownrt.provider-survival-state.v1',position=position,provider_serial=position,allocations=allocations,
        host=dict(current=state,saved=copy.deepcopy(state),saved_target_sha256='c'*64,saved_rows_sha256='d'*64,
            saved_class=1,captures=1,restores=1,verified_restores=1,private_bytes=private['bytes'],allocated_bytes=1000,
            image_id=private['id'],active=False),
        sequence=dict(epoch=0,request='d'*64,stage=0,stages=meta['stage_count'],stream_bytes=meta['stream_bytes'],vocab=97,
            next_position=position+1,last_sequence=sequence-2,last_commit=position*2,serial=position,last_seed=seed,poisoned=False,
            last_result=dict(position=position,guesses=[8,9],byte_verified=True,snapshot_bytes=private['bytes'],
                             canonical_ms=1.25,capture_ms=0.25,recursive_ms=1.5,restore_ms=0.5)),
        prepared_bindings_sha256='e'*64,excluded_shared_counter_values=['Engine timing/submission totals','Device copy_counter values'])


def make_pending(root):
    path=make_live(root);spec=json.loads(path.read_text())
    spec.update(schema='ownrt.pipeline-state-set.v5',mode='verified-ring-pending-provider',provider_borrow_mode='pending-target',
        require_byte_verified_restores=True,require_provider_survival_checks=True,required_provider_pending_depths=[1,2])
    spec['draft_input_identity'].update(vocab=97,context=32)
    dp=root/'draft-set.json';d=json.loads(dp.read_text());d['input_identity']=spec['draft_input_identity'];dp.write_text(json.dumps(d))
    for stage in spec['stages']:
        mp=root/stage['metadata'];meta=json.loads(mp.read_text());meta.update(mode=spec['mode'],provider_borrow_mode='pending-target');mp.write_text(json.dumps(meta))
        ap=root/stage['quiescence'];att=json.loads(ap.read_text());first=stage['id']==0
        att.update(schema='ownrt.ring-state.pending-provider.v1',mode=spec['mode'],provider_borrow_mode='pending-target',
            provider_pending_borrows={'1':1,'2':2} if first else {'1':0,'2':0},provider_quiescent_borrows=3 if first else 0,
            provider_borrows_while_target_pending=3 if first else 0,provider_survival_verification_enabled=first,
            provider_survival_records=2 if first else 0,provider_survival_discarded_rows=3 if first else 0,
            provider_survival_advanced_records=2 if first else 0,provider_survival_receipt_sha256='')
        for key in ('bytes','host','sequence','private','bindings'):att['provider_survival_'+key+'_verified']=2 if first else 0
        if first:
            att.update(rows=10,tentative_rows=4,accepted_tentative_rows=1,abort_count=2,discarded_rows=3,
                snapshot_captures=4,snapshot_releases=4,byteverified_restore_count=2,
                saved_bytes=4*att['target_mutable_checkpoint_bytes'],max_pending=2,trace_records=19)
            layout=json.loads((ap.parent/'ring-checkpoint-layout.json').read_text());records=[]
            for position,seq,count in [(2,20,2),(4,40,1)]:
                state=payload(layout,meta,position,seq);seed=state['sequence']['last_seed'];pending=[];parent=seed
                for index in range(count):
                    parent=row(position+1+index,seed['id']+index+1,parent['id'],parent['after'],seq-6+index,True)
                    pending.append(dict(row=parent,position=position-1,serial=position-1))
                raw=json.dumps(state,separators=(',',':'))
                records.append(dict(schema='ownrt.provider-abort-survival.v1',stage_id=0,ring_request_sha256='d'*64,ring_epoch=0,
                    abort_sequence=seq,oldest=pending[0]['row'],discarded_row_ids=[p['row']['id'] for p in pending],
                    provider_at_capture=pending,provider_advanced_since_snapshot=True,actual_position=position+1,
                    committed_position=position+1,pending_tickets=0,comparison_bytes=sum(r['bytes'] for r in state['allocations']),
                    canonical_allocations_checked=len(layout['independent_draft_allocations']),private_allocations_checked=1,
                    all_bytes_equal=True,host_equal=True,sequence_equal=True,prepared_bindings_equal=True,
                    before_payload=raw,after_payload=raw,before_payload_sha256=digest(raw.encode()),after_payload_sha256=digest(raw.encode())))
            rp=ap.parent/'ring-provider-survival.jsonl';rp.write_text(''.join(json.dumps(r)+'\n' for r in records))
            stage['provider_survival']=str(rp.relative_to(root));att['provider_survival_receipt_sha256']=digest(rp.read_bytes())
        ap.write_text(json.dumps(att))
    path.write_text(json.dumps(spec));return path


class PendingComparisonTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name)
        self.gold=make_set(self.root/'gold',[0,2,4]);self.path=make_pending(self.root/'pending');self.spec=json.loads(self.path.read_text())
        self.ap=self.path.parent/self.spec['stages'][0]['quiescence'];self.att=json.loads(self.ap.read_text())
        self.rp=self.path.parent/self.spec['stages'][0]['provider_survival'];self.records=[json.loads(r) for r in self.rp.read_text().splitlines()]

    def write_records(self,records):
        self.rp.write_text(''.join(json.dumps(r)+'\n' for r in records));att=dict(self.att,provider_survival_receipt_sha256=digest(self.rp.read_bytes()));self.ap.write_text(json.dumps(att))

    def test_complete_pending_survival_and_all_target_state(self):
        result=COMPARE.compare(COMPARE.load_set(self.gold),COMPARE.load_set(self.path));self.assertTrue(result['passed'])
        self.assertTrue(any(Path(r['path']).name=='ring-provider-survival.jsonl' for r in result['candidate']['sources']))
    def test_depth3_three_guess_survival_payload(self):
        layout=json.loads((self.ap.parent/'ring-checkpoint-layout.json').read_text());meta=json.loads((self.path.parent/self.spec['stages'][0]['metadata']).read_text())
        self.spec['speculative_depth']=3;meta['ring_depth']=3;state=payload(layout,meta,2,20);state['sequence']['last_result']['guesses']=[8,9,10]
        survival.validate_payload(json.dumps(state),self.spec,layout,meta,20)

    def test_quiescent_v4_cannot_relabel_pending_provider(self):
        self.spec.update(schema='ownrt.pipeline-state-set.v4',mode='verified-ring-live');self.path.write_text(json.dumps(self.spec))
        with self.assertRaises(ValueError):COMPARE.load_set(self.path)

    def test_survival_hash_count_policy_and_coverage_refused(self):
        for key,value in [('provider_survival_receipt_sha256','0'*64),('provider_survival_records',1),
            ('provider_survival_host_verified',1),('provider_survival_sequence_verified',1),('provider_survival_private_verified',1),
            ('provider_survival_bindings_verified',1),('provider_survival_advanced_records',1),('provider_survival_verification_enabled',False),
            ('provider_pending_borrows',{'1':0,'2':3}),('provider_quiescent_borrows',4)]:
            self.ap.write_text(json.dumps(dict(self.att,**{key:value})))
            with self.subTest(key=key),self.assertRaises(ValueError):COMPARE.load_set(self.path)

    def test_rehashed_record_cannot_omit_host_sequence_private_or_descriptors(self):
        for mutation in ('host-field','sequence-field','private','binding','position','capture-age','parent','false-compare'):
            records=copy.deepcopy(self.records);record=records[0];p=json.loads(record['before_payload'])
            if mutation=='host-field':del p['host']['current']['pending_start_ticks']
            elif mutation=='sequence-field':del p['sequence']['last_commit']
            elif mutation=='private':p['allocations'].pop()
            elif mutation=='binding':p['prepared_bindings_sha256']=''
            elif mutation=='position':p['host']['current']['position']+=1
            elif mutation=='capture-age':record['provider_at_capture'][0]['position']=record['provider_at_capture'][0]['serial']=p['position']
            elif mutation=='parent':record['oldest']['parent']=1
            else:record['all_bytes_equal']=False
            raw=json.dumps(p);record.update(before_payload=raw,after_payload=raw,before_payload_sha256=digest(raw.encode()),after_payload_sha256=digest(raw.encode()))
            self.write_records(records)
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):COMPARE.load_set(self.path)

    def test_after_payload_mutation_and_discard_omission_refused(self):
        for mutation in ('after','discard'):
            records=copy.deepcopy(self.records)
            if mutation=='after':records[0]['after_payload']+=' '
            else:records[0]['discarded_row_ids'].pop()
            self.write_records(records)
            with self.assertRaises(ValueError):COMPARE.load_set(self.path)


if __name__=='__main__':unittest.main()
