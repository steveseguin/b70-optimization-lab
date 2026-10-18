import copy, importlib, resource, unittest
from qualification import analyze
def fixture(candidate=9000):
    rows=[dict(kind='process',pid=123,input_sha256='inputs')]
    rows += [dict(kind='correctness',case=i,exact=True,nonfinite=i>=1536) for i in range(2048)]
    for row in range(16):
        for rep in range(64):
            for pos in range(2):
                is_candidate=bool(pos^(rep%2));dt=candidate if is_candidate else 18000
                rows.append(dict(kind='sample',row=row,repeat=rep,position=pos,view='p112' if is_candidate else 'production',start_ns=100,end_ns=100+dt,event_ns=dt,wall_ns=dt+50000))
    rows.append(dict(kind='summary',passed=True,drained=True,cases=2048,nonfinite_cases=512,output_sha256='outputs'))
    return rows
class Gates(unittest.TestCase):
    def test_boundary(self):self.assertTrue(analyze(fixture())['qualified'])
    def test_just_slow(self):self.assertFalse(analyze(fixture(9001))['qualified'])
    def test_partial(self):
        r=fixture();del r[20]
        with self.assertRaises(ValueError):analyze(r)
    def test_mismatch(self):
        r=fixture();r[1]['exact']=False
        with self.assertRaises(ValueError):analyze(r)
    def test_missing_sample(self):
        r=fixture();del r[-2]
        with self.assertRaises(ValueError):analyze(r)
    def test_duplicate(self):
        r=fixture();r[-3]=copy.deepcopy(r[-2])
        with self.assertRaises(ValueError):analyze(r)
    def test_wrong_order(self):
        r=fixture();r[-2]['position']=1-r[-2]['position']
        with self.assertRaises(ValueError):analyze(r)
    def test_timestamps(self):
        r=fixture();r[-2]['end_ns']+=1
        with self.assertRaises(ValueError):analyze(r)
    def test_one_order_slow(self):
        r=fixture(7000)
        for v in r:
            if v['kind']=='sample' and v['view']=='p112' and v['repeat']%2:
                v['event_ns']=11000;v['end_ns']=v['start_ns']+11000
        self.assertFalse(analyze(r)['qualified'])
    def test_one_layer_slow(self):
        r=fixture(7000)
        for v in r:
            if v['kind']=='sample' and v['view']=='p112' and v['row']<8:
                v['event_ns']=11000;v['end_ns']=v['start_ns']+11000
        self.assertFalse(analyze(r)['qualified'])
    def test_import_preserves_limits(self):
        before=resource.getrlimit(resource.RLIMIT_AS)
        for name in ('build_engine','qualification','run_micro','cpu_gate','seal'):importlib.import_module(name)
        self.assertEqual(before,resource.getrlimit(resource.RLIMIT_AS))
if __name__=='__main__':unittest.main()
