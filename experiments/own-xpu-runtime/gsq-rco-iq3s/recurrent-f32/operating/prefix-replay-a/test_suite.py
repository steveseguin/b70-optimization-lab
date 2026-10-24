import importlib.util,json,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
P=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('prefix_suite_tests',P/'suite.py');S=importlib.util.module_from_spec(s);s.loader.exec_module(S)
class Tests(unittest.TestCase):
 def test_actual_authority_metadata(self):
  original=Path.read_text
  def read(p,*a,**kw):
   if p==P/'evidence/independent-review.json':return json.dumps(dict(passed=True,source_sha256={}))
   return original(p,*a,**kw)
  with patch.object(Path,'read_text',read):cases,_=S.authority()
  c=cases[0];self.assertEqual(len(c['prompt_tokens']),157);self.assertEqual(c['native_expected'],[220]);self.assertEqual(c['tokens'],[264]);self.assertEqual(c['conditional_position'],156)
 def test_budget(self):
  b=S.BUDGET.Budget();B=S.BUDGET
  self.assertEqual(B.REMAINING,(640127112,320063556,9699332,0))
  self.assertEqual(B.EXTERNAL_FLOOR+B.META+B.REMAINING[0]+B.INITIAL_EXTRA,3056046216)
  for event,remaining in zip(B.EVENTS,B.REMAINING[1:]):b.advance(event);self.assertEqual(b.report()['remaining_payload_bytes'],remaining)
  b=B.Budget()
  with self.assertRaises(ValueError):b.advance('last_dump')
  self.assertEqual(b.stage,0)
  for i in range(4):
   b.stage=i;root=B.ROOT_FLOOR+B.ROOT_CACHE;ext=B.EXTERNAL_FLOOR+B.META+B.REMAINING[i]
   B.check_free(root,ext,b)
   with self.assertRaises(ValueError):B.check_free(root-1,ext,b)
   with self.assertRaises(ValueError):B.check_free(root,ext-1,b)
 def test_bootstrap128_rpc1(self):
  plan=dict(output='/control',evidence_output='/evidence',binary='/binary',context=4096,seconds=3600,max_new=128,mini=False)
  for rank in (0,1):
   a=S.A.command(plan,rank,'3','4');self.assertEqual(a[a.index('--max-new')+1],'128');self.assertEqual(a.count('--recurrent-f32'),1)
  class T:
   def __init__(self,p):self.shared_path=p/'shared.bin';self.trace=[];self.a=types.SimpleNamespace(draft_fault='none');self.device=False
   def start(self,*a):pass
   def wait(self,*a):pass
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'native-result.json').write_text(json.dumps(dict(rank_trace=[],work_start=0,work_end=1,stats=dict(hits=0,guesses=0,misses=0),decode_wall_ms=0)))
   S.A.BASE.NativeController(T(p),S.A.BASE.Draft('none'),True,False).run([1]*157,1,S.EOS)
   self.assertEqual(list(map(int,(p/'native-request.txt').read_text().split())),[0,1,1,0,157,0,2,*([1]*157),*S.EOS])
 def flow(self,token=220,reset_error=False):
  calls=[];case=dict(id='replay',prompt_tokens=[1]*157,tokens=[264],native_expected=[220],stop_type='limit');plan=dict(cases=[case],adapter={},scope='diagnostic')
  class T:
   def __init__(self,*a,**kw):self.out=Path('/fake');self.children=[types.SimpleNamespace(pid=1),types.SimpleNamespace(pid=2)];self.shared_path=Path('/fake/shared.bin')
   def check_alive(self):pass
   def close(self,ok):calls.append(('finish',ok))
  class RPC:
   def __init__(self,t,*a):self.t=t
   def run(self,prompt,count,eos):calls.append(('rpc',count));return dict(tokens=[token],stats=dict(guesses=0,hits=0,misses=0))
  def reset(t,d):
   calls.append(('reset',d.name))
   if reset_error:raise ValueError('injected reset')
  def capture(t,row):row['state_sha256']={'x':'h'};row['capture_snapshot']={'s':1};calls.append(('capture',row['name']))
  def save(p,r):calls.append(('save',p.name))
  request=' '.join(map(str,[0,1,1,0,157,0,2,*([1]*157),*S.EOS]))
  with patch.object(S,'validate_plan'),patch.object(S,'storage_guard'),patch.object(S.A,'Transport',T),patch.object(S.A,'reset',side_effect=reset),patch.object(S.A.BASE,'NativeController',RPC),patch.object(Path,'read_text',return_value=request),patch.object(S.A,'save',side_effect=save),patch.object(S,'capture',capture),patch.object(S.A,'state_hashes',side_effect=lambda t:calls.append(('dump',)) or {'x':'h'}),patch.object(S.Q,'snapshots',return_value={'s':1}),patch.object(S.Q,'closed_map',return_value={'x':'h'}),patch.object(S,'sha',return_value='hash'),patch.object(S.A,'cleanup_failure',side_effect=lambda t,e:calls.append(('cleanup',t.capture_budget.stage)) or []):
   try:r=S.qualification(plan,admit=lambda p:None,check=None,launch_hook=None)
   except ValueError:r=None
  return r,calls
 def test_successful_diagnostic_lifecycle(self):
  r,c=self.flow();self.assertTrue(r['passed']);self.assertTrue(r['diagnostic_only']);self.assertFalse(r['reference_equal']);self.assertEqual(c.count(('dump',)),2);self.assertIn(('finish',True),c);self.assertEqual([x for x in c if x[0]=='rpc'],[('rpc',1)])
 def test_unreproduced_token_saved_and_halts(self):
  r,c=self.flow(264);self.assertIsNone(r);self.assertIn(('save','request-result.json'),c);self.assertIn(('cleanup',1),c);self.assertNotIn(('dump',),c);self.assertNotIn(('finish',True),c)
 def test_failed_reset_no_credit(self):
  r,c=self.flow(reset_error=True);self.assertIsNone(r);self.assertIn(('cleanup',0),c);self.assertFalse(any(x[0]=='rpc' for x in c))
if __name__=='__main__':unittest.main()
