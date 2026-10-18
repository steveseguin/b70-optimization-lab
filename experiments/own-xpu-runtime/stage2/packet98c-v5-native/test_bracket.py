"""CPU-only orchestration, total-reset contract and admission regression tests."""
import contextlib, copy, io, tempfile, types, unittest
from pathlib import Path
from unittest.mock import patch
import bracket as b
import common as C
import screen
import tp2_worker
from lane_admission import Reservation

class BracketTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.entries=[dict(prompt_id=p) for p in C.D.CHECK.PROMPT_IDS]
        self.views=[dict(choice=c,selection='/mock/'+c,selection_sha256=('a' if c=='control' else 'b')*64)
                    for c in ('control','candidate','control','candidate','control')]

    def backend(self, fail=None, drift=None):
        events=[];test=self
        class Backend:
            view=-1;dirty=True;requests=0
            def check(self):pass
            def switch_reset(self,view,dest):
                self.view+=1;events.append(('switch',self.view));self.dirty=False
                if fail==('switch',self.view):raise ValueError('injected switch')
                dest.mkdir(parents=True)
                return [dict(arena_descriptors_sha256=str(rank)+(str(self.view) if drift==self.view else ''),
                             weight_descriptors_sha256=str(rank)) for rank in (0,1)]
            def reset(self,dest):dest.mkdir();self.dirty=False;events.append(('reset',self.view))
            def request(self,entry,count):
                test.assertFalse(self.dirty);self.dirty=True;self.requests+=1
                events.append(('request',self.view,count))
                if fail==('request',self.view):raise ValueError('injected request')
                return dict(tokens=list(range(count)),passed=True,cached_tokens=0)
            def prompt_hash(self,entry):return 'c'*64
        return Backend(),events

    def execute(self,backend):
        with patch.object(C.D.CHECK,'token_record',return_value=list(range(128))):
            return b.execute_views(backend,self.views,self.entries,self.root)

    def test_switch_reset_full_suite_each_view_and_isolated_receipts(self):
        backend,events=self.backend();rows=self.execute(backend)
        self.assertEqual(len(rows),5);self.assertEqual(backend.requests,65)
        for i in range(5):
            self.assertEqual([e[2] for e in events if e[:2]==('request',i)],[64]+[128]*12)
            self.assertEqual(len(rows[i]['requests']),12)
            self.assertEqual(rows[i]['requests'][0]['cached_tokens'],0)
            self.assertTrue((Path(rows[i]['output'])/'incident64/receipt.json').exists())

    def test_each_switch_failure_stops_before_next_view(self):
        for i in range(5):
            with self.subTest(view=i),tempfile.TemporaryDirectory() as d:
                self.root=Path(d);backend,events=self.backend(fail=('switch',i))
                with self.assertRaisesRegex(ValueError,'injected switch'):self.execute(backend)
                self.assertEqual(max(e[1] for e in events),i)
                self.assertEqual(backend.requests,i*13)

    def test_each_request_failure_stops_bracket(self):
        for i in range(5):
            with self.subTest(view=i),tempfile.TemporaryDirectory() as d:
                self.root=Path(d);backend,events=self.backend(fail=('request',i))
                with self.assertRaisesRegex(ValueError,'injected request'):self.execute(backend)
                self.assertEqual(max(e[1] for e in events),i)

    def test_changed_loaded_descriptor_refuses_before_incident(self):
        backend,events=self.backend(drift=2)
        with self.assertRaisesRegex(ValueError,'arena identity'):self.execute(backend)
        self.assertEqual(backend.requests,26)

    def test_cached_or_wrong_output_refused(self):
        for field,value in (('cached_tokens',1),('tokens',[99]),('passed',False)):
            with self.subTest(field=field),tempfile.TemporaryDirectory() as d:
                self.root=Path(d);backend,_=self.backend();request=backend.request
                def bad(*args):
                    row=request(*args);row[field]=value;return row
                backend.request=bad
                with self.assertRaises(ValueError):self.execute(backend)

    def test_layout_and_draft_refused(self):
        control=C.read(C.HERE/'lineage/selection.json');candidate=C.read(C.HERE/'lineage/candidate.json')
        self.assertTrue(b.compatible([control,candidate,control]))
        for section,key,value in (('choices','packed_dense','head-transpose'),('choices','packed_dense','head-packed'),
                                  ('draft','head_format','q4-g32'),('draft','head_prefix','prefix985'),
                                  ('choices','miss','banks-batch')):
            bad=copy.deepcopy(candidate);bad[section][key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):b.compatible([control,bad])

    def test_registered_order_and_same_smoke_selection(self):
        for kind,count in (('smoke',3),('bracket',5),('attention',5)):
            config=b.load_config(C.HERE/'configs'/(kind+'.json'));self.assertEqual(len(config['views']),count)
        with patch.object(b,'read',return_value=dict(kind='bracket',views=self.views[:3])):
            with self.assertRaisesRegex(ValueError,'A/B/A/B/A'):b.load_config(C.HERE/'configs/bracket.json')

    def test_memory_refusal_precedes_reservation(self):
        args=['--lane','B','--lineage','/unused','--output',str(self.root/'out'),
              '--fault-review','/unused','--authorized-device-window']
        with patch.object(screen,'lane_gate'),patch('cpu_seal.verify'),patch.object(screen.fault_review,'validate'),\
             patch.object(screen,'memory_admit',side_effect=ValueError('memory refused')),\
             patch.object(screen,'Reservation') as lease:
            with self.assertRaisesRegex(ValueError,'memory refused'):screen.main(args)
            lease.assert_not_called()

    def test_raced_prelaunch_refusal_removes_own_marker(self):
        root=self.root/'leases'
        args=['--lane','B','--lineage','/unused','--output',str(self.root/'out'),
              '--fault-review','/unused','--authorized-device-window']
        def reserve(*args,**kw):return Reservation(*args,**kw,root=root)
        with patch.object(screen,'lane_gate'),patch('cpu_seal.verify'),patch.object(screen.fault_review,'validate'),\
             patch.object(screen,'memory_admit'),patch.object(screen.S,'journal',return_value=('','cursor')),\
             patch.object(screen,'Reservation',side_effect=reserve),\
             patch.object(screen,'screen_main',side_effect=ValueError('raced memory refusal')):
            with self.assertRaisesRegex(ValueError,'raced memory'):screen.main(args)
        self.assertFalse((root/'active-lane-B.json').exists())

    def test_worker_loads_once_drains_once_on_view_failure(self):
        import sys
        sys.path.insert(0,str(C.P56));self.addCleanup(lambda:sys.path.remove(str(C.P56)))
        import pipeline,suite,storage
        snapshots={e['prompt_id']:(self.root,[1,2,3]) for e in self.entries}
        calls=[]
        class Transport:
            def __init__(self,*args,**kw):
                calls.append('load');self.stop_write=123;self.closed=False;self.children=[]
        def monitor(lane,output):
            def poll(**kw):C.save(output/'device-isolation.json',dict(passed=True))
            return types.SimpleNamespace(poll=poll,register=lambda pid:None)
        def switched(transport,view,dest,suite):
            index=sum(c=='switch' for c in calls);calls.append('switch')
            if index==2:raise ValueError('failure in view k')
            dest.mkdir(parents=True)
            return [dict(arena_descriptors_sha256=str(r),weight_descriptors_sha256=str(r)) for r in (0,1)]
        def drained(transport,out,success,reason=None):calls.append(('drain',success));transport.closed=True
        def reset(transport,dest):dest.mkdir();calls.append('reset')
        def request(*args):return dict(tokens=list(range(args[-1])),passed=True,cached_tokens=0)
        identity=dict(lineage=str(C.P56),binary='/mock',dispatch='/mock',selection_sha256='a'*64,
                      lane='B',timing='token',placement=dict(draft_rank=1,target_split=0),bracket=dict(views=self.views))
        old=(pipeline.P,storage.P,storage.B,storage.admit)
        try:
            with patch.object(C.D,'oracle_inputs',return_value=dict(prompts=self.entries)),\
                 patch.object(C.D.CHECK,'token_record',return_value=list(range(128))),\
                 patch.object(pipeline,'Transport',Transport),patch.object(suite,'checker_module'),\
                 patch.object(suite,'admit_inputs',return_value=snapshots),patch.object(suite,'reset',side_effect=reset),\
                 patch.object(suite,'run_request',side_effect=request),patch.object(b,'switch_reset',side_effect=switched),\
                 patch('placement.verify_identity',return_value=(identity['placement'],C.module('mock_memory',C.P56/'memory_gate.py'))),\
                 patch.object(tp2_worker,'masked_environment',return_value={}),\
                 patch.object(tp2_worker,'DeviceMonitor',side_effect=monitor),patch.object(tp2_worker,'drain',side_effect=drained):
                self.assertEqual(tp2_worker.run(identity,self.root/'run',3600),1)
        finally:pipeline.P,storage.P,storage.B,storage.admit=old
        self.assertEqual(calls.count('load'),1);self.assertEqual(calls.count('switch'),3)
        self.assertEqual([c for c in calls if isinstance(c,tuple)],[('drain',False)])

if __name__=='__main__':unittest.main()
