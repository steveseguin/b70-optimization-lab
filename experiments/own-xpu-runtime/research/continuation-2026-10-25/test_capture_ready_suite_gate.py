import copy
import json
from pathlib import Path
import tempfile
import unittest
import finalize_persistent_capture_ready_suite as gate
from test_persistent_rolling_suite_closure import fixture,digest,record,write


class CaptureGateTests(unittest.TestCase):
    def plans(self,root):
        _,current,_,runtime=fixture(root)
        capture=root/'rolling_provider/capture_ready.py';capture.parent.mkdir();capture.write_text('CAPTURE=1\n')
        current['capture_ready_overlap']=True
        current['pins'][str(capture)]=digest(capture)
        current['stages'][0]['argv'].append('--pipeline-ring-parent-capture-ack')
        return current,copy.deepcopy(current),runtime

    def test_exact_measured_closure_and_wrong_build_source_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            current,prior,runtime=self.plans(Path(folder))
            self.assertTrue(gate.prerequisite_closure(current,prior)['passed'])
            for path in (runtime,Path(folder)/'own-engine'):
                bad=copy.deepcopy(current);bad['pins'][str(path)]='0'*64
                with self.assertRaises(ValueError):gate.prerequisite_closure(bad,prior)
            # Mutating both alleged pin maps cannot conceal changed source bytes.
            current['pins'][str(runtime)]=prior['pins'][str(runtime)]='0'*64
            with self.assertRaisesRegex(ValueError,'source bytes'):gate.prerequisite_closure(current,prior)

    def test_gate_record_requires_capture_and_complete_two32_state(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);plan,_,_=self.plans(root)
            path=write(root/'plan.json',plan);qualified=write(root/'qualified.json',{'old':'comparison'})
            summary=dict(schema='ownrt.persistent-rolling-proof.v1',passed=True,requests=2,check_policy='measured',
                all_requests_full_state_parity=True,provenance_passed=True,target_state_exact=True,draft_state_exact=True,
                output_tokens_exact=True,original_plan=record(path),qualified_reference_parity=True,qualified_reference=record(qualified),
                capture_ready_overlap=True,output_tokens=64,request_summaries=[dict(passed=True,output_tokens=32,target_buffer_count=2065,draft_allocation_count=73)]*2,
                capture_ready_finalizer=record(Path(gate.__file__).with_name('finalize_persistent_capture_ready_proof.py')),
                capture_ready_auditor=record(Path(gate.__file__).with_name('persistent_capture_ready_trace_audit.py')))
            gate.prerequisite_record(summary,path,'measured',qualified)
            for key,value in [('capture_ready_overlap',False),('output_tokens',63),('draft_state_exact',False)]:
                bad=copy.deepcopy(summary);bad[key]=value
                with self.assertRaises(ValueError):gate.prerequisite_record(bad,path,'measured',qualified)
            bad=copy.deepcopy(summary);bad['capture_ready_auditor']['sha256']='0'*64
            with self.assertRaises(ValueError):gate.prerequisite_record(bad,path,'measured',qualified)
            write(qualified,{'old':'different'})
            with self.assertRaises(ValueError):gate.prerequisite_record(summary,path,'measured',qualified)

    def test_old_reference_has_no_same_build_qualification_claim(self):
        with tempfile.TemporaryDirectory() as folder:
            current,prior,_=self.plans(Path(folder));prior['check_policy']='qualification'
            prior['pins']={}
            self.assertIsNone(gate.prerequisite_closure(current,prior))
            current['capture_ready_overlap']=1
            with self.assertRaises(ValueError):gate.prerequisite_closure(current,prior)


if __name__=='__main__':unittest.main()
