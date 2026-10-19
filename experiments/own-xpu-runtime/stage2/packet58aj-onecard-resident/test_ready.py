"""Five-view exactness, inclusive rate/drift limits and fail-closed launch."""
import copy
from contextlib import ExitStack
from pathlib import Path
import json,tempfile,unittest
from unittest.mock import patch
import queue_runner as Q
import verify_ready as R

def rows(rates=(25,25,25,25,25)):
    return [dict(label=label,view='resident' if i%2 else 'mapped',passed=True,
                 **{R.METRIC:dict(median=rate)},requests=[dict(prompt_id=f'p{j}',prompt_token_sha256=f'h{j}',tokens=list(range(128)),passed=True,exact_oracle=True,cached_tokens=0) for j in range(12)])
            for i,(label,rate) in enumerate(zip(('A0','B0','A1','B1','A2'),rates))]
class ReadyTests(unittest.TestCase):
    def test_inclusive_gain(self):self.assertTrue(R.evaluate(rows())['passed'])
    def test_each_candidate_and_each_control(self):
        for rate in (24.875,25,25.125,32):self.assertTrue(R.evaluate(rows((10,rate,25,rate,25)))['passed'])
        for i in (1,3):
            for rate in (24.87499,):
                rates=[10,25,25,25,25];rates[i]=rate
                with self.subTest(i=i,rate=rate),self.assertRaisesRegex(ValueError,'EVERY'):R.evaluate(rows(rates))
    def test_warm_controls_not_cold_a0(self):
        self.assertTrue(R.evaluate(rows((1,25,25,25,25)))['passed'])
        self.assertTrue(R.evaluate(rows((1,25,24.8,25,25)))['passed'])
        with self.assertRaises(ValueError):R.evaluate(rows((1,25,25,25,25.2)))
    def test_drift_boundary(self):
        self.assertTrue(R.evaluate(rows((1,103,100,103,103)))['passed'])
        with self.assertRaises(ValueError):R.evaluate(rows((1,104,100,104,103.00001)))
    def test_measured_bracket_amendment(self):
        result=R.evaluate(rows((26.928,31.959,31.558,32.061,31.525)))
        self.assertTrue(result['resident_noninferior'])
        self.assertFalse(result['original_candidate_beats_all_controls'])
        self.assertFalse(result['submission_eligible'])
    def test_nonexact_first_view_refuses(self):
        data=rows((22,27,26,27,26));data[0]['requests'][0]['exact_oracle']=False
        with self.assertRaisesRegex(ValueError,'exact'):R.evaluate(data)
    def test_complete_views(self):
        for count in range(5):
            with self.assertRaises(ValueError):R.evaluate(rows()[:count])
    def test_every_token_and_prompt(self):
        for i in range(5):
            for key,value in [('passed',False),('exact_oracle',False),('tokens',[1]*128),('tokens',[1]*64),('cached_tokens',1),('prompt_id','p1')]:
                data=rows();data[i]['requests'][0][key]=value
                with self.subTest(view=i,key=key),self.assertRaises(ValueError):R.evaluate(data)
    def test_rates_and_mode(self):
        for rate in (True,0,-1,float('inf'),float('nan')):
            with self.assertRaises(ValueError):R.evaluate(rows((25,rate,25,26,25)))
        data=rows();data[1]['view']='serial'
        with self.assertRaises(ValueError):R.evaluate(data)
    def test_saved_ready_cannot_bypass(self):
        with tempfile.TemporaryDirectory() as tmp,ExitStack() as stack:
            root=Path(tmp);(root/'evidence').mkdir();(root/'ready.json').write_text('{"ready":true}')
            stack.enter_context(patch.object(Q,'P',root))
            for obj,name,value in ((Q.W,'build_gate',{}),(Q.W,'user_unit_gate',None),(Q.W,'closed_environment',{}),(Q.os,'getpriority',0),(Q.os,'sched_getaffinity',{0,1,2,3,16,17,18,19})):
                stack.enter_context(patch.object(obj,name,return_value=value))
            stack.enter_context(patch.object(R,'verify',side_effect=ValueError('missing smoke')))
            spawn=stack.enter_context(patch.object(Q.subprocess,'Popen',side_effect=AssertionError('launch forbidden')))
            with self.assertRaisesRegex(ValueError,'missing smoke'):Q.main(['--output-root',str(root/'evidence/card0-58aj-a'),'--fault-review','/unused','--view','down-tile16','--authorized-device-window'])
            spawn.assert_not_called();self.assertFalse((root/'evidence/card0-58aj-a').exists())
    def test_command_closed_embedded_environment(self):
        command=R.chain_command()
        for value in ('--unit=packet58-onecard-58aj-a','--property=Restart=no','--property=SendSIGKILL=no','--property=Nice=0','--view down-tile16','--fault-review','card0-58aj-a','< /dev/null','/usr/bin/env -i','LD_LIBRARY_PATH=/opt/intel/oneapi/'):
            self.assertIn(value,command)
        self.assertNotIn('$',command)
        import re
        review=re.search(r'evidence/fault-review-[A-Za-z0-9_-]+\.json',(R.P/'WINDOW.md').read_text()).group()
        self.assertIn(str(R.P/review),command)
if __name__=='__main__':unittest.main()

class ChainAttemptTests(unittest.TestCase):
    def test_old_unit_refused(self):
        import window as W
        with self.assertRaisesRegex(ValueError, 'systemd user service required'):
            W.user_unit_gate('0::/user.slice/user-1000.slice/user@1000.service/app.slice/packet58-onecard-58ah-a.service')
