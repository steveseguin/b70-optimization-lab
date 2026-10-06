"""Offline launcher-status tests. Does not start a server, Harbor, Docker, or a model."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SOURCE = Path(os.environ.get('B70_CONTEXT_SOURCE_DIR', Path(__file__).resolve().parent))
COMPARISON = SOURCE / 'second-comparison.sh'
SUMMARY = SOURCE / 'summarize_results.py'
SUBMIT = 'COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT'

class ComparisonStatusTests(unittest.TestCase):
    def run_case(self, rc=0, fixture='valid', earlier=False, call=True):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); tools=root/'tools'; tools.mkdir(); runs=root/'runs';runs.mkdir()
            (tools/'summarize_results.py').write_bytes(SUMMARY.read_bytes())
            trial=runs/'jobs/B32__task/trial'
            def write_fixture():
                (trial/'agent').mkdir(parents=True)
                (trial/'result.json').write_text(json.dumps({'verifier_result':{'rewards':{'reward':1}}}))
                (trial/'agent/usage.json').write_text(json.dumps({'hit_lm_call_cap':True} if fixture=='invalid' else {}))
                (trial/'agent/trajectory.json').write_text(json.dumps([{'role':'tool','content':SUBMIT}] if fixture=='valid' else []))
            if earlier:
                write_fixture();(trial/'verifier').mkdir();(trial/'verifier/reward.txt').write_text('1')
            template=root/'template'
            if fixture!='none' and not earlier:
                write_fixture();shutil.move(str(trial),str(template));shutil.rmtree(runs/'jobs')
            launcher=tools/'run-context-job.sh'
            launcher.write_text('#!/bin/bash\nprintf called > "$2/launcher-called"\n'+
                ('mkdir -p "$2/jobs/$JOB_NAME"\ncp -R "$FIXTURE_TEMPLATE" "$2/jobs/$JOB_NAME/trial"\n' if fixture!='none' and not earlier else '')+
                'exit "$FIXTURE_RC"\n')
            launcher.chmod(0o700)
            source=COMPARISON.read_text();start=source.index('run_one() {');end=source.index('\nwhile IFS=',start)
            function=source[start:end]
            script='\n'.join(['set -uo pipefail','D="$1"; RUNS="$2"; PY="$3"; ENABLE_THINKING=true; FAILED=0',function,
                'run_one B32 clm 32768 "$4" B32__task 0' if call else ': # all campaign entries intentionally excluded',
                'echo "FINAL_FAILED=$FAILED"','[[ "$FAILED" == 0 ]]'])
            result=subprocess.run(['bash','-c',script,'status-test',str(tools),str(runs),sys.executable,str(root/'task')],
                capture_output=True,text=True,timeout=10,env={**os.environ,'FIXTURE_TEMPLATE':str(template),'FIXTURE_RC':str(rc)})
            return result,(runs/'launcher-called').exists()
    def test_nonzero_before_any_trial_is_failed(self):
        r,called=self.run_case(17,'none');self.assertTrue(called);self.assertNotEqual(r.returncode,0,r.stdout);self.assertIn('status 17',r.stdout)
    def test_nonzero_with_valid_partial_output_is_failed(self):
        r,called=self.run_case(17,'valid');self.assertTrue(called);self.assertNotEqual(r.returncode,0,r.stdout);self.assertIn('status 17',r.stdout)
    def test_successful_valid_trial_passes(self):
        r,called=self.run_case(0,'valid');self.assertTrue(called);self.assertEqual(r.returncode,0,r.stdout+r.stderr);self.assertIn('FINAL_FAILED=0',r.stdout)
    def test_zero_exit_invalid_trial_still_fails(self):
        r,_=self.run_case(0,'invalid');self.assertNotEqual(r.returncode,0,r.stdout);self.assertIn('FINAL_FAILED=1',r.stdout)
    def test_completed_trial_stays_skipped(self):
        r,called=self.run_case(17,'valid',earlier=True);self.assertFalse(called);self.assertEqual(r.returncode,0,r.stdout);self.assertIn('done earlier, skipped',r.stdout)
    def test_empty_excluded_campaign_remains_success(self):
        r,called=self.run_case(17,'none',call=False);self.assertFalse(called);self.assertEqual(r.returncode,0,r.stdout)
    def test_summary_zero_results_still_reports_success(self):
        with tempfile.TemporaryDirectory() as d:
            r=subprocess.run([sys.executable,str(SUMMARY),'--check','--brief',str(Path(d)/'missing')],capture_output=True,text=True,timeout=5)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
if __name__=='__main__':unittest.main(verbosity=2)
