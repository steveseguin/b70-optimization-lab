"""No devices or models: real lane leases and injected post-drain report failures."""
import contextlib
import fcntl
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import tempfile
import screen as s
from lane_admission import Reservation

class ReportingTests(unittest.TestCase):
    def scenario(self, fault):
        with tempfile.TemporaryDirectory() as d, contextlib.ExitStack() as stack:
            root=Path(d); here=root/'packet/screen';here.mkdir(parents=True)
            shared=root/'screen/v3';shared.mkdir(parents=True)
            out=here/'evidence/run';(here/'evidence').mkdir()
            lineage=here.parent
            wrapper=here/'wrapper-seal.json';wrapper.write_text('{}')
            # __file__ is only used for wrapper hash and source inventory.
            stack.enter_context(patch.object(s,'__file__',str(here/'screen.py')))
            identity=dict(placement=dict(supported=True,reason='test'), binary='/fake',timing='token')
            manifest=dict(prompts=[dict(prompt_id='incident-retrospective',input_bundle='fake')])
            child=SimpleNamespace(pid=12345,returncode=0,poll=lambda:0)
            isolation=dict(passed=True)
            proof=dict(passed=True,lane='B',placement={},requests=[dict(passed=True,exact_oracle=True)]*12,
                       incident64=dict(passed=True),device_isolation=isolation)
            lease=Reservation('B',root=root/'leases',check=lambda:None)
            events=[]
            def supervise(*args,**kwargs):
                run=out/'run';run.mkdir()
                teardown=dict(drained=fault!='drain')
                s.save(run/'teardown.json',teardown)
                s.save(run/'report-inputs.json',proof)
                if fault=='worker':child.returncode=1
                return dict(child_still_running=False)
            def release(row):
                events.append('postflight')
                if fault=='postflight':raise ValueError('postflight failed')
                lease.complete(drained=True);events.append('released')
                return dict(passed=True,released_before_report=True)
            def report(*unused):
                events.append('report')
                self.assertFalse((root/'leases/active-lane-B.json').exists())
                self.assertTrue(lease.completed)
                with (shared/'lane-B.lock').open('a') as legacy:
                    fcntl.flock(legacy, fcntl.LOCK_EX | fcntl.LOCK_NB)
                if fault=='report':raise ValueError('injected CPU summary error')
                return dict(passed=True)
            original=Path.read_text
            def read_text(path,*args,**kwargs):
                if str(path)=='/proc/self/cgroup':return '/user@1000.service/screen-test.service'
                return original(path,*args,**kwargs)
            stack.enter_context(patch.object(Path,'read_text',read_text))
            stack.enter_context(patch.object(s,'HERE',here))
            stack.enter_context(patch.object(s,'sealed',return_value=identity))
            stack.enter_context(patch.object(s.D,'oracle_inputs',return_value=manifest))
            stack.enter_context(patch.object(s,'sha',side_effect=lambda path: '0'*64 if str(path).endswith('completion.json') else __import__('hashlib').sha256(Path(path).read_bytes()).hexdigest()))
            for name in ('lane_gate','screen_teardown_admit','unit_gate','topology_admit','selected_clients','memory_admit'):
                stack.enter_context(patch.object(s,name,return_value={}))
            stack.enter_context(patch.object(s,'unit_conditions',return_value={}))
            stack.enter_context(patch.object(s,'masked_environment',return_value={}))
            stack.enter_context(patch('quick_seal.verify',return_value={}))
            stack.enter_context(patch.object(s.fault_review,'validate',return_value=({},'','','cursor')))
            stack.enter_context(patch.object(s.W,'memory_fence',return_value={}))
            stack.enter_context(patch.object(s.SUPPORT,'storage',return_value={}))
            stack.enter_context(patch.object(s.SUPPORT,'process_start',return_value=123))
            stack.enter_context(patch.object(s.S,'ldd_preflight',return_value={}))
            stack.enter_context(patch.object(s.S,'supervise',side_effect=supervise))
            stack.enter_context(patch.object(s.subprocess,'Popen',return_value=child))
            stack.enter_context(patch.object(s,'summary',side_effect=report))
            argv=['--lane','B','--placement','1','--lineage',str(lineage),'--output',str(out),
                  '--fault-review',str(root/'review.json'),'--authorized-device-window']
            with lease: code=s.screen_main(argv,release=release)
            record=s.read(out/'window.json')
            latch=list(shared.glob('fault-*.json'))
            retained=(root/'leases/active-lane-B.json').exists()
            if fault in ('worker','drain','postflight'):
                self.assertEqual(code,1);self.assertTrue(retained);self.assertTrue(latch)
                self.assertNotIn('report',events)
            else:
                self.assertFalse(retained);self.assertFalse(latch)
                self.assertEqual(events,['postflight','released','report'])
                self.assertEqual(code,1 if fault=='report' else 0)
                if fault=='report':
                    self.assertTrue(record['report_failed']);self.assertFalse(record['passed'])
                    self.assertFalse(s.read(out/'report-failure.json')['device_failure'])
                    # A new lease admits immediately, proving neither latch nor marker blocks it.
                    with Reservation('B',root=root/'leases',check=lambda:None) as next_lease:
                        next_lease.complete(drained=True)
    def test_report_failure_releases_without_fault(self):self.scenario('report')
    def test_success_releases_before_report(self):self.scenario(None)
    def test_worker_failure_latches(self):self.scenario('worker')
    def test_drain_failure_latches(self):self.scenario('drain')
    def test_postflight_failure_latches(self):self.scenario('postflight')



import tp2_worker
import types
from common import D, P56, module, read, save

class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)

    def check_worker(self, kind):
        import sys
        sys.path.insert(0,str(P56))
        self.addCleanup(lambda:sys.path.remove(str(P56)))
        import pipeline,suite,storage
        entries=[dict(prompt_id=p) for p in D.CHECK.PROMPT_IDS]
        snapshots={e['prompt_id']:(self.root,[1,2,3]) for e in entries}
        calls=[]
        output=self.root/'run'
        test=self
        class Transport:
            def __init__(self,*a,**kw):calls.append('load')
            def close(self,success):
                test.assertTrue((output/'report-inputs.json').exists())
                test.assertFalse((output/'summary.json').exists())
                calls.append(('close',success))
        def reset(t,path):path.mkdir();calls.append(('reset',path.name))
        def request(t,args,prompt,count):
            calls.append(('request',count))
            return dict(tokens=list(range(count)),passed=True,prompt_tokens=3)
        def monitor(lane,output):
            def poll(**kw):save(output/'device-isolation.json',dict(passed=True))
            return types.SimpleNamespace(poll=poll,register=lambda pid:None)
        identity=dict(lineage=str(P56),binary='/mock',dispatch='/mock',selection_sha256='a'*64,
                      lane='A',kind=kind,timing='token',placement=dict(draft_rank=1,target_split=0))
        old=(pipeline.P,storage.P,storage.B,storage.admit)
        try:
            with patch.object(D,'oracle_inputs',return_value={'prompts':entries}),patch.object(D.CHECK,'token_record',return_value=list(range(128))),patch.object(pipeline,'Transport',Transport),patch.object(suite,'checker_module'),patch.object(suite,'admit_inputs',return_value=snapshots),patch.object(suite,'reset',side_effect=reset),patch.object(suite,'run_request',side_effect=request),patch('placement.verify_identity',return_value=(identity['placement'],module('mock_memory',P56/'memory_gate.py'))),patch.object(tp2_worker,'summary',side_effect=AssertionError('worker must not report')),patch.object(tp2_worker,'Teardown'),patch.object(tp2_worker,'masked_environment',return_value={}),patch.object(tp2_worker,'DeviceMonitor',side_effect=monitor):
                self.assertEqual(tp2_worker.run(identity,self.root/'run',3600),0)
        finally:
            pipeline.P,storage.P,storage.B,storage.admit=old
        self.assertEqual([c for c in calls if isinstance(c,tuple) and c[0]=='request'],([('request',32)] if kind=='smoke' else [('request',64)]+[('request',128)]*12))
        self.assertEqual(calls[-1],('close',True))
        self.assertTrue(read(self.root/'run/report-inputs.json')['passed'])
        self.assertFalse((self.root/'run/summary.json').exists())

    def test_full_worker_mock_incident_then_twelve_requests_and_drain(self):self.check_worker('quick')
    def test_smoke_is_one_32_token_request(self):self.check_worker('smoke')

if __name__=='__main__':unittest.main()
