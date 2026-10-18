"""CPU mock tests for confirmed MTP scheduling and publication validation."""
import unittest,json,copy
from pathlib import Path
from pipeline import P,Controller,Draft,DRAFT,PUBLICATION,SLOT,Transport
from test_state_machine import Mock
class MtpMock(Mock):
 def __init__(self,script=()):
  super().__init__();self.script=list(script);self.cache=[];self.pub=None;self.draft_overlap=0
 def start(self,r,op,token=0,position=0,fixture=0,speculative=0):
  if op==DRAFT:
   assert r==1 and self.candidate[1] is None
   self.draft_overlap+=self.pending[0] is not None
  super().start(r,op,token,position,fixture,speculative)
 def wait(self,r):
  op,token,pos,fixture,spec=self.pending[r]
  if op!=DRAFT:return super().wait(r)
  assert pos==len(self.cache)+1==len(self.state[1]['history'])
  self.pending[r]=None
  self.cache.append((pos-1,token,self.state[1]['recurrence']))
  guess=self.script.pop(0) if fixture and self.script else None
  self.pub=dict(position=pos+1,guess=guess,draft_wall_ms=1,draft_gpu_ms=None)
  return dict(token=-1)
 def draft_result(self,position):
  assert self.pub['position']==position
  return self.pub.copy()
class Tests(unittest.TestCase):
 def test_confirmed_cache_and_targets(self):
  count=8
  for prompt in ([1],[1,2,3,2,1]):
   ref=Mock();expected=Controller(ref,Draft()).run(prompt,count)
   controls=[]
   for script in ([],expected['tokens'],[(x+1)%31 for x in expected['tokens']]):
    b=MtpMock(script);r=Controller(b,Draft('mtp')).run(prompt,count)
    self.assertEqual(r['tokens'],expected['tokens']);self.assertEqual(b.state,ref.state);self.assertEqual(b.fixtures,ref.fixtures)
    self.assertEqual(len(b.cache),len(prompt)+count-2);controls.append(b.cache)
    if script and len(prompt)>1:self.assertGreater(b.draft_overlap,0)
   self.assertEqual(controls[0],controls[1]);self.assertEqual(controls[0],controls[2])
 def test_no_extra_draft_after_eos(self):
  prompt=[1,2,3];base=Mock();first=Controller(base,Draft()).run(prompt,1)['tokens'][0]
  b=MtpMock([17]*20);r=Controller(b,Draft('mtp')).run(prompt,8,[first])
  self.assertEqual(r['tokens'],[first]);self.assertEqual(len(b.cache),len(prompt)-1)
 def test_publication_firewall(self):
  t=Transport.__new__(Transport);t.a=type('A',(),dict(mini=True,timing='token'))();t.device=False;t.seq=[0,19];t.started=[0,0];t.mapping=bytearray(2*SLOT+4096)
  good=[1,7,3,0,100,19,0,0.0]
  def check(v):
   t.mapping[2*SLOT:2*SLOT+PUBLICATION.size]=PUBLICATION.pack(*v)
   return t.draft_result(7)['guess']
  self.assertEqual(check(good),3)
  for index,value in ((0,0),(1,6),(2,-1),(2,16),(3,1),(5,18)):
   bad=good.copy();bad[index]=value;self.assertIsNone(check(bad))
if __name__=='__main__':
 r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
 (P/'mtp-controller-tests.json').write_text(json.dumps(dict(passed=r.wasSuccessful(),tests=r.testsRun,device_executed=False),indent=2)+'\n')
 raise SystemExit(not r.wasSuccessful())
