import copy,json,unittest
from prepare import P
from admit import plan,device_admission
class Admission(unittest.TestCase):
    def test_actual_proposals(self):
        for kind in ('smoke','v5'):
            p=json.loads((P/'proposals'/f'{kind}.json').read_text());p['output']+='-cpu-test-unused';self.assertTrue(plan(p)['passed'])
            with self.assertRaisesRegex(ValueError,'withheld'):device_admission(p,{'ready_for_device':False},{})
    def test_identity_follows_proposal(self):
        p=json.loads((P/'proposals/smoke.json').read_text());p['job_name']='fresh-another-smoke-name';p['output']+='-cpu-test-unused'
        with self.assertRaises(ValueError):plan(p)
        argv=p['native_argv'];argv[argv.index('--demand-identity')+1]=p['job_name'];self.assertEqual(plan(p)['job_name'],p['job_name'])
    def test_refusals(self):
        source=json.loads((P/'proposals/v5.json').read_text())
        for field,value in [('lane','B'),('model_loads',5),('prompts',1),('views',['B0']),('in_run_data_deadline_seconds',1)]:
            p=copy.deepcopy(source);p[field]=value
            with self.assertRaises(ValueError):plan(p)
if __name__=='__main__':unittest.main()
