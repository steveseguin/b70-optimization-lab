import copy,unittest
from unittest.mock import patch
import verify_ready as R
def rows(rates=(1,25.125,25,25.125,25)):
    return [dict(label=label,view='demand' if i%2 else 'parent',passed=True,
        **{R.METRIC:dict(median=rate)},requests=[dict(prompt_id=f'p{j}',prompt_token_sha256=f'h{j}',tokens=list(range(128)),passed=True,exact_oracle=True,cached_tokens=0) for j in range(12)])
        for i,(label,rate) in enumerate(zip(('A0','B0','A1','B1','A2'),rates))]
class ReadyTests(unittest.TestCase):
    def test_inclusive_gain(self):self.assertTrue(R.evaluate(rows())['passed'])
    def test_each_candidate_and_each_control(self):
        for i in (1,3):
            for rate in (25.124999,25,24):
                r=[1,26,25,26,25];r[i]=rate
                with self.subTest(i=i,rate=rate),self.assertRaisesRegex(ValueError,'EVERY'):R.evaluate(rows(r))
        with self.assertRaises(ValueError):R.evaluate(rows((1,25.125,25,26,25.001)))
    def test_drift_boundary(self):
        self.assertTrue(R.evaluate(rows((1,104,100,104,103)))['passed'])
        with self.assertRaisesRegex(ValueError,'drift'):R.evaluate(rows((1,104,100,104,103.00001)))
    def test_cold_view_not_speed_control(self):
        self.assertTrue(R.evaluate(rows((999,25.125,25,25.125,25)))['passed'])
    def test_every_view_exact_including_warmup(self):
        for i in range(5):
            for key,value in [('passed',False),('exact_oracle',False),('tokens',[1]*128),('tokens',[1]*64),('cached_tokens',1),('prompt_id','p1')]:
                r=rows();r[i]['requests'][0][key]=value
                with self.subTest(i=i,key=key),self.assertRaises(ValueError):R.evaluate(r)
    def test_complete_views(self):
        for n in range(5):
            with self.assertRaises(ValueError):R.evaluate(rows()[:n])
    def test_invalid_rates(self):
        for rate in (True,0,-1,float('inf'),float('nan')):
            with self.assertRaises(ValueError):R.evaluate(rows((1,rate,25,26,25)))
    def test_saved_flag_not_used(self):
        with patch.object(R,'PROPOSAL',R.P/'absent-v5.txt'),self.assertRaises(FileNotFoundError):R.parent_evidence()
    def test_command_identity(self):
        command=R.chain_command()
        for value in ('--unit=packet58-onecard-58ap-a','--property=Restart=no','--property=SendSIGKILL=no','--property=Nice=0','card0-58ap-a','fault-review-58ap-a.json','< /dev/null','/usr/bin/env -i'):
            self.assertIn(value,command)
        self.assertNotIn('$',command)
