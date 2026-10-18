import copy, importlib, json, resource, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from qualification import analyze, evaluate

def fixture(candidate=14400):
    receipt=dict(passed=True,safe_to_exit=True,device_executed=True,cpu_mock=False,
                 recurrence_checks=768,checks=500,timing_pair_checks=100)
    cases=[dict(case=f'm{m}-s{s}-a{a}-p{p}-t{t}',tokens=m,bytes=1572864+m*12288+12,sha256='a'*64,equal=True)
           for m in (1,2,4) for s in range(16) for a in range(2) for p in range(2) for t in range(4)]
    rows=[]
    for context in (128,4096):
        for i in range(50):
            for view in (['current','specialized'] if i%2==0 else ['specialized','current']):
                dt=candidate if view=='specialized' else 24000
                rows.append(dict(layer=4,occupied_context=context,position=context-1,iteration=i,mode=view,warmup=i<10,
                    submissions=1,gpu_ns=dt,classes_ns={'gdn.recurrence':dt},
                    events=[dict(id=1,start_ns=100,end_ns=100+dt,**{'class':'gdn.recurrence'})]))
    return rows,receipt,cases

class Gates(unittest.TestCase):
    def test_boundary(self): self.assertTrue(analyze(*fixture())['qualified'])
    def test_just_slow(self): self.assertFalse(analyze(*fixture(14401))['qualified'])
    def test_missing_pair(self):
        r,s,c=fixture();r.pop()
        with self.assertRaises(ValueError):analyze(r,s,c)
    def test_duplicate_pair(self):
        r,s,c=fixture();r[-2:]=copy.deepcopy(r[-4:-2])
        with self.assertRaises(ValueError):analyze(r,s,c)
    def test_wrong_order(self):
        r,s,c=fixture();r[-2:]=r[-2:][::-1]
        with self.assertRaises(ValueError):analyze(r,s,c)
    def test_missing_exceptional_state(self):
        r,s,c=fixture();c.pop(100)
        with self.assertRaises(ValueError):analyze(r,s,c)
    def test_failed_byte(self):
        r,s,c=fixture();c[100]['equal']=False
        with self.assertRaises(ValueError):analyze(r,s,c)
    def test_state_extent(self):
        r,s,c=fixture();c[100]['bytes']-=2
        with self.assertRaises(ValueError):analyze(r,s,c)
    def test_cpu_is_not_device(self):
        r,s,c=fixture();s['cpu_mock']=True
        with self.assertRaises(ValueError):analyze(r,s,c)
    def test_partial_native(self):
        r,s,c=fixture();s['timing_pair_checks']=99
        with self.assertRaises(ValueError):analyze(r,s,c)
    def test_timestamp_accounting(self):
        r,s,c=fixture();r[25]['events'][0]['end_ns']+=1
        with self.assertRaises(ValueError):analyze(r,s,c)
    def test_missing_recurrence(self):
        r,s,c=fixture();r[25]['events'][0]['class']='gdn.conv';r[25]['classes_ns']={'gdn.conv':14400}
        with self.assertRaises(ValueError):analyze(r,s,c)
    def test_one_stratum_slow(self):
        for context,order in [(128,0),(128,1),(4096,0),(4096,1)]:
            r,s,c=fixture(10000)
            for x in r:
                if x['occupied_context']==context and x['iteration']%2==order and x['mode']=='specialized':
                    x['events'][0]['end_ns']=20100;x['gpu_ns']=20000;x['classes_ns']['gdn.recurrence']=20000
            self.assertFalse(analyze(r,s,c)['qualified'])
    def test_missing_owners_is_pending(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d)/'evidence').mkdir();r=evaluate(Path(d));self.assertFalse(r['integration_allowed']);self.assertFalse(r['device_speed_measured'])
    def test_import_preserves_limits(self):
        before=resource.getrlimit(resource.RLIMIT_AS)
        for name in ('build_engine','qualification','run_micro','cpu_layers','cpu_leaf','seal'):importlib.import_module(name)
        self.assertEqual(before,resource.getrlimit(resource.RLIMIT_AS))

if __name__=='__main__':unittest.main()
