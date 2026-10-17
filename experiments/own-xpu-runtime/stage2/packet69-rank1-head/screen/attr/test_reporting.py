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
            root=Path(d); here=root/'packet/screen/attr';here.mkdir(parents=True)
            shared=root/'experiments/own-xpu-runtime/stage2/screen/v3';shared.mkdir(parents=True)
            out=here/'evidence/run';(here/'evidence').mkdir()
            lineage=here.parents[1]/'selections/preset';lineage.mkdir(parents=True)
            wrapper=here/'wrapper-seal.json';wrapper.write_text('{}')
            # __file__ is only used for wrapper hash and source inventory.
            stack.enter_context(patch.object(s,'__file__',str(here/'screen.py')))
            identity=dict(placement=dict(supported=True,reason='test'), binary='/fake',timing='attribution')
            manifest=dict(prompts=[dict(prompt_id='incident-retrospective',input_bundle='fake')])
            child=SimpleNamespace(pid=12345,returncode=0,poll=lambda:0)
            isolation=dict(passed=True)
            proof=dict(passed=True,lane='B',placement={},requests=[dict(passed=True,exact_oracle=True)]*12,
                       incident64=dict(passed=True),device_isolation=isolation)
            proof['arms']={arm:list(proof['requests']) for arm in ('control','attribution')}
            lease=Reservation('B',root=root/'leases',check=lambda:None)
            events=[]
            def supervise(*args,**kwargs):
                run=out/'run';run.mkdir();(run/'control').mkdir();(run/'attribution').mkdir()
                teardown=dict(drained=fault!='drain')
                s.save(run/'teardown.json',teardown)
                proof['teardown_sha256']=s.sha(run/'teardown.json')
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
            stack.enter_context(patch.object(s,'ROOT',root))
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
            stack.enter_context(patch.object(s,'summary',return_value={'passed':True}))
            stack.enter_context(patch('attribution_summary.summarize',side_effect=report))
            stack.enter_context(patch('attribution_summary.markdown',return_value='test report'))
            argv=['--timing','attribution','--lane','B','--placement','1','--lineage',str(lineage),'--output',str(out),
                  '--fault-review',str(root/'review.json'),'--authorized-device-window']
            with lease: code=s.screen_main(argv,release=release)
            record=s.read(out/'window.json')
            latch=list(shared.glob('fault-*.json'))
            retained=(root/'leases/active-lane-B.json').exists()
            if fault in ('worker','drain','postflight'):
                self.assertEqual(code,1);self.assertTrue(retained);self.assertTrue(latch)
                self.assertNotIn('report',events)
            else:
                self.assertFalse(retained,record);self.assertFalse(latch)
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
