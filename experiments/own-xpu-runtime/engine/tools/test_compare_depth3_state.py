import json
import tempfile
from pathlib import Path
import unittest
import test_compare_persistent_ring_state as fixture
C=fixture.COMPARE

def make_depth3(root):
    path=fixture.make_persistent(root,'measured');spec=json.loads(path.read_text());spec['speculative_depth']=3
    for stage in spec['stages']:
        mp=root/stage['metadata'];m=json.loads(mp.read_text());m.update(ring_capacity=3,depth=3,ring_depth=3);mp.write_text(json.dumps(m))
        ap=root/stage['quiescence'];a=json.loads(ap.read_text());a.update(schema='ownrt.ring-state.persistent.v2',ring_capacity=3,depth=3)
        lp=(root/stage['dump']).parent/'ring-checkpoint-layout.json';layout=json.loads(lp.read_text());layout.update(schema='ownrt.ring-checkpoint-layout.live.v2',ring_capacity=3)
        next_id=max(row['id'] for rows in layout.values() if isinstance(rows,list) for row in rows if isinstance(row,dict) and 'id' in row)+1
        for row in list(layout['checkpoint_private_allocations']):
            if 'ring:0:' in row['label']:
                new=dict(row,id=next_id,label=row['label'].replace('ring:0:','ring:2:'));next_id+=1;layout['checkpoint_private_allocations'].append(new)
        lp.write_text(json.dumps(layout));a['checkpoint_layout_sha256']=fixture.digest(lp.read_bytes());a['provider_pending_borrows']['3']=0;ap.write_text(json.dumps(a))
    path.write_text(json.dumps(spec));return path

class Depth3State(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
    def test_measured_depth3_compares_every_buffer_against_depth2(self):
        old=fixture.make_persistent(self.root/'old','measured');new=make_depth3(self.root/'new')
        result=C.compare(C.load_set(old),C.load_set(new));self.assertTrue(result['passed'])
    def test_depth3_requires_explicit_schema_capacity_and_all_three_images(self):
        for mutation in ['implicit','bool','oldschema','wrongcapacity','missingslot','privateoverlap','wrongmetadata','missingborrowdepth']:
            p=make_depth3(self.root/mutation);s=json.loads(p.read_text());stage=s['stages'][0];ap=p.parent/stage['quiescence'];a=json.loads(ap.read_text());lp=(p.parent/stage['dump']).parent/'ring-checkpoint-layout.json';layout=json.loads(lp.read_text());mp=p.parent/stage['metadata'];m=json.loads(mp.read_text())
            if mutation=='implicit':s.pop('speculative_depth')
            elif mutation=='bool':s['speculative_depth']=True
            elif mutation=='oldschema':a['schema']='ownrt.ring-state.persistent.v1'
            elif mutation=='wrongcapacity':a['ring_capacity']=2
            elif mutation=='missingslot':layout['checkpoint_private_allocations'].pop()
            elif mutation=='privateoverlap':layout['checkpoint_private_allocations'][-1]['id']=layout['checkpoint_private_allocations'][0]['id']
            elif mutation=='wrongmetadata':m['ring_depth']=2
            elif mutation=='missingborrowdepth':a['provider_pending_borrows'].pop('3')
            lp.write_text(json.dumps(layout));a['checkpoint_layout_sha256']=fixture.digest(lp.read_bytes());ap.write_text(json.dumps(a));mp.write_text(json.dumps(m));p.write_text(json.dumps(s))
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):C.load_set(p)
    def test_debug_depth3_and_old_schema_depth_override_refused(self):
        p=make_depth3(self.root/'new');original=json.loads(p.read_text())
        for changes in [dict(verification_policy='qualification'),dict(schema='ownrt.pipeline-state-set.v6',mode='verified-ring-pending-provider')]:
            p.write_text(json.dumps(dict(original,**changes)))
            with self.subTest(changes=changes),self.assertRaises(ValueError):C.load_set(p)
if __name__=='__main__':unittest.main()
