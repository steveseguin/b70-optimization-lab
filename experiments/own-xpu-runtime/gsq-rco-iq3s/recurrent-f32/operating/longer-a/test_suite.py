import importlib.util,json,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
P=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('longer_suite_tests',P/'suite.py');S=importlib.util.module_from_spec(s);s.loader.exec_module(S)
class Tests(unittest.TestCase):
 def test_authority_pending(self):
  with patch.object(Path,'read_text',return_value=json.dumps({'reference_review_sha256':None})):
   with self.assertRaisesRegex(ValueError,'CPU3 closed authority pending'):S.authority()
 def test_remaining_exact(self):
  b=S.BUDGET.Budget();consumed=0;start=4*(S.BUDGET.T+S.BUDGET.D)
  for event,n in zip(S.BUDGET.EVENTS,[S.BUDGET.T+S.BUDGET.D]*3+[S.BUDGET.T,S.BUDGET.D]):
   b.advance(event);consumed+=n;self.assertEqual(b.report()['remaining_payload_bytes'],start-consumed)
  self.assertEqual(b.stage,5)
 def test_margin_and_failed_ack(self):
  b=S.BUDGET.Budget();B=S.BUDGET;root=B.ROOT_FLOOR+B.ROOT_CACHE+B.INITIAL_EXTRA;ext=B.EXTERNAL_FLOOR+B.META+B.REMAINING[0]+B.INITIAL_EXTRA
  B.check_free(root,ext,b,True)
  with self.assertRaises(ValueError):B.check_free(root-1,ext,b,True)
  with self.assertRaises(ValueError):B.check_free(root,ext-1,b,True)
  with self.assertRaises(ValueError):b.advance('reset_01')
  self.assertEqual(b.stage,0)
 def test_bootstrap_and_actual_rpc(self):
  plan=dict(output='/control',evidence_output='/evidence',binary='/binary',context=4096,seconds=3600,max_new=128,mini=False)
  for rank in (0,1):
   a=S.A.command(plan,rank,'3','4');self.assertEqual(a[a.index('--max-new')+1],'128');self.assertEqual(a.count('--recurrent-f32'),1)
  class T:
   def __init__(self,p):self.shared_path=p/'shared.bin';self.trace=[];self.a=types.SimpleNamespace(draft_fault='none');self.device=False
   def start(self,*args):pass
   def wait(self,*args):pass
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);r=dict(rank_trace=[],work_start=0,work_end=1,stats=dict(hits=0,guesses=0,misses=0),decode_wall_ms=0);(p/'native-result.json').write_text(json.dumps(r));t=T(p)
   S.A.BASE.NativeController(t,S.A.BASE.Draft('none'),True,False).run([1,2,3],512,S.EOS)
   self.assertEqual(list(map(int,(p/'native-request.txt').read_text().split())),[0,512,1,0,3,0,2,1,2,3,*S.EOS])
 def test_exact_eos_and_divergence(self):
  c=dict(tokens=[1,2,248046],stop_type='eos');self.assertTrue(S.comparison(c['tokens'],c)['equal']);self.assertEqual(S.comparison([1,4],c)['first_difference'],1)
 def test_three_request_lifecycle(self):
  calls=[];cases=[dict(id=str(i),prompt_tokens=[i],tokens=[7,248046],stop_type='eos') for i in range(3)];plan=dict(cases=cases)
  class T:
   out=Path('/fake');children=[types.SimpleNamespace(pid=1),types.SimpleNamespace(pid=2)];capture_budget=None
   def check_alive(self):pass
  t=T()
  class RPC:
   def __init__(self,*a):pass
   def run(self,prompt,count,eos):
    calls.append(('rpc',prompt,count));t.request=' '.join(map(str,[0,512,1,0,len(prompt),0,2,*prompt,*eos]));return dict(tokens=[7,248046],stats=dict(guesses=0,hits=0,misses=0))
  t.shared_path=Path('/fake/shared.bin')
  def capture(t,row):calls.append(('capture',row['name']));row['state_sha256']={'x':'h'};row['capture_snapshot']={'s':1}
  with patch.object(S,'storage_guard'),patch.object(S.A,'reset',side_effect=lambda t,d:calls.append(('reset',d.name))),patch.object(S.A.BASE,'NativeController',RPC),patch.object(Path,'read_text',lambda self:t.request),patch.object(S.A,'save'),patch.object(S,'capture',capture),patch.object(S.A,'state_hashes',return_value={'x':'h'}),patch.object(S.Q,'snapshots',return_value={'s':1}):r=S.run_attached(t,plan)
  self.assertEqual([x for x in calls if x[0]=='reset'],[('reset',f'prompt-{i:02d}-none') for i in range(3)]);self.assertEqual(len(r['rows']),3);self.assertEqual(t.capture_budget.stage,4);self.assertEqual([x for x in calls if x[0]=='capture'],[('capture',f'prompt-{i:02d}-none') for i in range(3)])
if __name__=='__main__':unittest.main()
