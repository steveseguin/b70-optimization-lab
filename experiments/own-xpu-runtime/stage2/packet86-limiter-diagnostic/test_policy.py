import json
from pathlib import Path
import subprocess
import sys
import unittest
from policy import guard,labels,classify,VIEWS,NONEXACT
from run_screen import expected_quality_refusal

class PolicyTests(unittest.TestCase):
    def test_every_view_refuses_every_promotion_path(self):
        for view in VIEWS:
            for purpose in ('bundle','chain','submission','headline'):
                with self.subTest(view=view,purpose=purpose),self.assertRaisesRegex(ValueError,'forbidden'):guard(view,purpose)
            with self.assertRaises(ValueError):guard(view,timing='token')
            self.assertTrue(labels(view)['diagnostic_nonexact'])
            self.assertFalse(labels(view)['submission_eligible'])
    def test_actual_runner_refuses_before_admission(self):
        script=Path(__file__).with_name('run_screen.py')
        for purpose in ('bundle','chain','submission'):
            r=subprocess.run([sys.executable,'-B',str(script),'--view','exp-nodeq','--purpose',purpose,'--output','/tmp/p86-never-created'],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=60)
            self.assertNotEqual(r.returncode,0);self.assertIn('paths forbidden',r.stderr)
    def test_expected_mismatch_is_not_a_fault(self):
        for view in NONEXACT:
            row=classify(view,[2],[1],1)
            self.assertEqual(row['outcome'],'diagnostic_output_mismatch');self.assertFalse(row['exact_oracle'])
        for view in set(VIEWS)-NONEXACT:
            with self.assertRaisesRegex(ValueError,'every-token mismatch'):classify(view,[2],[1],1)
        for view in VIEWS:
            with self.assertRaisesRegex(ValueError,'protocol'):classify(view,[],[1],1)
    def test_only_post_release_quality_refusal_is_accepted(self):
        record=dict(device_complete=True,lease_released=True,report_failed=True)
        failure=dict(passed=False,device_failure=False,error='screen quality incomplete')
        self.assertTrue(expected_quality_refusal('exp-nodeq',record,failure))
        for key in record:
            self.assertFalse(expected_quality_refusal('exp-nodeq',{**record,key:False},failure))
        self.assertFalse(expected_quality_refusal('production',record,failure))
        self.assertFalse(expected_quality_refusal('exp-nodeq',record,{**failure,'device_failure':True}))
        self.assertFalse(expected_quality_refusal('exp-nodeq',record,{**failure,'error':'memory floor'}))
