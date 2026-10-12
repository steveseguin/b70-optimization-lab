"""Pure host state-machine tests; real Controller, deterministic mock halves."""
import copy,itertools,json,random,unittest
from pipeline import Controller,Draft,HALF,ACCEPT,ROLLBACK,DUMP,P
class Mock:
    device=False
    def __init__(self):
        self.state=[dict(history=[],recurrence=7,rows=[]),dict(history=[],recurrence=11,rows=[])]
        self.pending=[None,None];self.candidate=[None,None];self.saved=None;self.fixtures=[[],[]];self.overlap=0
    def start(self,r,op,token=0,position=0,fixture=0,speculative=0):
        assert self.pending[r] is None
        assert r==0 or not speculative
        self.pending[r]=(op,token,position,fixture,speculative)
        self.overlap+=all(x is not None for x in self.pending)
    def wait(self,r):
        op,token,pos,fixture,spec=self.pending[r];self.pending[r]=None
        s=self.state[r]
        if op==HALF:
            assert len(s['history'])==pos and self.candidate[r] is None
            if r==0:self.saved=copy.deepcopy(s)
            s['history'].append(token);s['recurrence']=(s['recurrence']*13+token+(self.incoming if r else 0)+pos)%104729
            s['rows'].append(s['recurrence']);self.candidate[r]=(fixture,s['recurrence'],spec)
            if r==0:self.stream=s['recurrence']
            return dict(token=s['recurrence']%31)
        if op==ACCEPT:
            assert self.candidate[r] is not None
            if self.candidate[r][0]:self.fixtures[r].append(self.candidate[r][:2])
            self.candidate[r]=None
        elif op==ROLLBACK:
            assert r==0 and self.candidate[r][2]
            self.state[r]=self.saved;self.candidate[r]=None
        elif op==DUMP:assert self.candidate[r] is None
        return dict(token=-1)
    def call(self,r,op,token=0,position=0,fixture=0,speculative=0):
        self.start(r,op,token,position,fixture,speculative);return self.wait(r)
    def handover(self):
        assert not self.pending[1] and self.candidate[0] is None
        self.incoming=self.stream
class StateMachine(unittest.TestCase):
    def compare(self,prompt,count,provider,overlap=True):
        base=Mock();expected=Controller(base,Draft(),False).run(prompt,count)
        actual=Mock();observed=Controller(actual,provider,overlap).run(prompt,count)
        self.assertEqual(observed['tokens'],expected['tokens']);self.assertEqual(actual.state,base.state);self.assertEqual(actual.fixtures,base.fixtures)
        return observed,actual
    def test_all_ternary_patterns(self):
        prompt=[1,2,1,2,3];b=Mock();reference=Controller(b,Draft()).run(prompt,8)['tokens']
        for n in range(7):
            for pattern in itertools.product((0,1,2),repeat=n):
                guesses=[reference[i] if x==1 else (reference[i]+1)%31 if x==0 else -1 for i,x in enumerate(pattern)]
                self.compare(prompt,8,Draft('script',guesses))
    def test_long_random(self):
        for seed in range(12):
            rng=random.Random(seed);prompt=[rng.randrange(31) for _ in range(15)];b=Mock();tokens=Controller(b,Draft()).run(prompt,128)['tokens']
            self.compare(prompt,128,Draft('script',[t if rng.randrange(2) else (t+1)%31 for t in tokens]))
    def test_ngram(self):
        self.assertEqual(Draft('ngram').guess([1,2,7,1,2],5),7)
        self.assertEqual(Draft('ngram').guess([4,8,9,4],4),8)
        self.assertIsNone(Draft('ngram').guess([1,2,3],3))
        self.assertEqual(Draft('ngram').guess([1,2,7,1,2,9,1,2],8),9)
        self.compare([1,2,7,1,2,9,1,2],64,Draft('ngram'))
    def test_prompt_overlap(self):
        _,overlap=self.compare([1,2,3,4],1,Draft())
        _,serial=self.compare([1,2,3,4],1,Draft(),False)
        self.assertGreater(overlap.overlap,0);self.assertEqual(serial.overlap,0)
    def test_terminal_discard(self):
        base=Mock();first=Controller(base,Draft()).run([1,2,3],1)['tokens'][0]
        b=Mock();r=Controller(b,Draft('script',[17])).run([1,2,3],8,(first,))
        self.assertEqual(r['tokens'],[first]);self.assertEqual(b.state,base.state);self.assertEqual(b.fixtures,base.fixtures)
if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(StateMachine);result=unittest.TextTestRunner(verbosity=2).run(suite)
    (P/'state-machine-tests.json').write_text(json.dumps(dict(passed=result.wasSuccessful(),tests=result.testsRun,ternary_patterns=sum(3**n for n in range(7)),long_random_cases=12,device_executed=False),indent=2)+'\n')
    raise SystemExit(not result.wasSuccessful())
