import importlib.util,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
import qualification as Q
class Qualification(unittest.TestCase):
 def fixture(self,path,wrong=False,repeat_wrong=False):
  state={'0':{'old.bin':'exact'},'1':{'old.bin':'exact'}};t=types.SimpleNamespace(out=Path(path),children=[types.SimpleNamespace(pid=11),types.SimpleNamespace(pid=12)],calls=[],resets=[],reads=0,check_alive=lambda:None)
  def reset(t,d):d.mkdir();t.request_output=d;t.resets.append(d)
  class Controller:
   def __init__(self,t,d,*args):self.t=t;self.mode=d.mode
   def run(self,prompt,cap,eos):self.t.calls.append((self.mode,prompt,cap,eos));return dict(tokens=[3 if wrong else 2]*128)
  def hashes(t):
   t.reads+=1
   return {'wrong':'repeat'} if repeat_wrong and t.reads==3 else state
  refs={f'prompt-00-{mode}':dict(prompt_tokens=[7,8],result={'tokens':[2]*128},state_sha256=state) for mode in ('none','mtp')}
  return t,reset,Controller,hashes,refs,state
 def run_mock(self,args):
  t,reset,controller,hashes,refs,state=args
  with patch.object(Q.C,'baseline',return_value=refs),patch.object(Q.A,'reset',reset),patch.object(Q.A.BASE,'NativeController',controller),patch.object(Q.A,'state_hashes',hashes),patch.object(Q,'storage_guard'),patch.object(Q,'snapshots',return_value={'sealed':'unchanged'}),patch.object(Q,'closed_map',return_value=state):
   return Q.run_attached(t,dict(prompt_tokens=[7,8]))
 def test_two_requests_initial_reset_explicit_last_dump(self):
  with tempfile.TemporaryDirectory() as d:
   args=self.fixture(d);r=self.run_mock(args);t=args[0];self.assertTrue(r['passed']);self.assertEqual(['none','mtp'],[x[0] for x in t.calls]);self.assertEqual(2,len(t.resets));self.assertEqual(3,t.reads);self.assertTrue(r['first_arm_RESET_redump_verified']);self.assertTrue(r['last_arm_explicit_DUMP_repeat_verified'])
 def test_first_arm_mismatch_stops_before_second_request(self):
  with tempfile.TemporaryDirectory() as d:
   args=self.fixture(d,wrong=True)
   with self.assertRaisesRegex(ValueError,'baseline arm'):self.run_mock(args)
   self.assertEqual(1,len(args[0].calls));self.assertEqual(1,len(args[0].resets));self.assertTrue((Path(d)/'prompt-00-none/request-result.json').exists())
 def test_repeat_mismatch_refuses_success(self):
  with tempfile.TemporaryDirectory() as d:
   args=self.fixture(d,repeat_wrong=True)
   with self.assertRaisesRegex(ValueError,'final DUMP'):self.run_mock(args)
   self.assertEqual(2,len(args[0].calls))
 def test_three_dump_storage_and_unchanged_argv(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);plan=Q.A.build_plan(p/'ranks',max_new=128,evidence_output=p/'evidence');self.assertEqual(3*231442500,plan['storage']['raw_state_bytes']);self.assertEqual(3*231442500+64*1024**2,plan['storage']['evidence_forecast_bytes']);self.assertEqual(2,plan['storage']['request_count'])
   spec=importlib.util.spec_from_file_location('bundle_parent_adapter',Q.L/'qkv-q6-p33/engine/operating/generated/adapter.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
   for rank in (0,1):self.assertEqual(m.command(plan,rank,51,52),Q.A.command(plan,rank,51,52))
 def test_retained_owner_preserves_original_exception(self):
  error=RuntimeError('original owner error');retained=Q.A.RetainedOwner(error,object(),[])
  class Broken:
   def __init__(self,*a,**kw):raise error
  with patch.object(Q,'validate_plan'),patch.object(Q,'storage_guard'),patch.object(Q.A,'Transport',Broken),patch.object(Q.A,'cleanup_failure',side_effect=retained):
   with self.assertRaises(Q.A.RetainedOwner) as caught:Q.qualification({'adapter':{}},admit=lambda _:None,check=lambda:None,launch_hook=lambda _:None)
   self.assertIs(caught.exception.original,error)
if __name__=='__main__':unittest.main(verbosity=2)
