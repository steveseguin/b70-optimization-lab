import tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
import profile as Q
class Profile(unittest.TestCase):
 def fixture(self,path,wrong=False,repeat=False):
  state={'0':{'old.bin':'exact'},'1':{'old.bin':'exact'}};t=types.SimpleNamespace(out=Path(path),children=[types.SimpleNamespace(pid=11),types.SimpleNamespace(pid=12)],calls=[],resets=[],reads=0,check_alive=lambda:None)
  def reset(t,d):d.mkdir();t.request_output=d;t.resets.append(d)
  class Controller:
   def __init__(self,t,d,*args):self.t=t;self.mode=d.mode
   def run(self,prompt,cap,eos):self.t.calls.append((self.mode,prompt,cap,eos));return dict(tokens=[3 if wrong and cap==128 else 2]*cap)
  def hashes(t):
   t.reads+=1;return {'wrong':'repeat'} if repeat and t.reads==3 else state
  ref={'prompt-00-none':dict(prompt_tokens=[7,8],result={'tokens':[2]*128},state_sha256=state)}
  return t,reset,Controller,hashes,ref,state
 def run_mock(self,args):
  t,reset,controller,hashes,ref,state=args
  with patch.object(Q.C,'baseline',return_value=ref),patch.object(Q.A,'reset',reset),patch.object(Q.A.BASE,'NativeController',controller),patch.object(Q.A,'state_hashes',hashes),patch.object(Q,'storage_guard'),patch.object(Q.Q,'snapshots',return_value={'sealed':'same'}),patch.object(Q.Q,'closed_map',return_value=state):
   return Q.run_attached(t,dict(prompt_tokens=[7,8],warmup={'tokens':[9]}))
 def test_schedule_reset_repeat_and_no_speed(self):
  with tempfile.TemporaryDirectory() as d:
   a=self.fixture(d);r=self.run_mock(a);self.assertEqual(a[0].calls,[('none',[9],8,()),('none',[7,8],128,(248044,248046))]);self.assertEqual(len(a[0].resets),2);self.assertEqual(a[0].reads,3);self.assertTrue(r['rows'][0]['excluded']);self.assertIsNone(r['rows'][1]['result']['decode_tok_s'])
 def test_exactness_refusal_retains_result(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaisesRegex(ValueError,'baseline arm'):self.run_mock(self.fixture(d,wrong=True))
   self.assertTrue((Path(d)/'prompt-00-none/request-result.json').exists())
 def test_repeat_refusal(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaisesRegex(ValueError,'final DUMP'):self.run_mock(self.fixture(d,repeat=True))
 def test_argv_only_timing_both_ranks(self):
  p=dict(output='/tmp/control/ranks',evidence_output='/tmp/evidence',binary='/fixed/binary',context=4096,seconds=1800,max_new=128,mini=False)
  for rank in (0,1):
   a=Q.TOKEN_COMMAND(p,rank,51,52);b=Q.command(p,rank,51,52);i=a.index('--timing')+1;self.assertEqual([(x,y) for x,y in zip(a,b) if x!=y],[('token','attribution')]);a[i]='attribution';self.assertEqual(a,b)
 def test_forecast_and_binary_refusal(self):
  def fake(*a,**k):return dict(binary_sha256=Q.BINARY_SHA,storage={'raw_state_bytes':694327500},source_sha256={})
  with patch.object(Q,'TOKEN_PLAN',fake):
   p=Q.adapter_plan();self.assertEqual(p['storage']['evidence_forecast_bytes'],828545228);self.assertEqual(p['storage']['metadata_forecast_bytes'],128*1024**2)
  with patch.object(Q,'TOKEN_PLAN',return_value=dict(binary_sha256='wrong')):
   with self.assertRaisesRegex(ValueError,'binary'):Q.adapter_plan()
 def test_actual_qualified_review(self):self.assertEqual(Q.actual_review(),Q.ACTUAL)
 def test_retained_original(self):
  error=RuntimeError('original');retained=Q.A.RetainedOwner(error,object(),[])
  class Broken:
   def __init__(self,*a,**kw):raise error
  with patch.object(Q,'validate_plan'),patch.object(Q,'storage_guard'),patch.object(Q.A,'Transport',Broken),patch.object(Q.A,'cleanup_failure',side_effect=retained):
   with self.assertRaises(Q.A.RetainedOwner) as c:Q.qualification({'adapter':{}},admit=lambda _:None,check=lambda:None,launch_hook=lambda _:None)
   self.assertIs(c.exception.original,error)
class Events(unittest.TestCase):
 def rows(self):
  rows=[];eid=0
  for f in range(9,17):
   base=dict(rank=0,fixture=f,position=87+f-2,half=f,speculative=False)
   for layer in range(24):
    for cl in ('expsgate','expsup','expsdown'):
     eid+=1;rows.append(dict(base,schema='packet65.event.v1',diagnostic=True,label=f'blk.{layer}.{cl}',event=eid,start_ns=eid*1000,end_ns=eid*1000+100,**{'class':'moe_experts'}))
   rows.append(dict(base,schema='packet65.half.v1',cancelled=False))
  return rows
 def test_exact_graph_format_join_and_integer_sums(self):
  m=Q.EVENTS.mapping();r=Q.EVENTS.aggregate(self.rows(),0,87,m)
  self.assertEqual(r['event_count'],576);self.assertEqual(r['device_ns'],57600)
  self.assertEqual(sum(x['device_ns'] for x in r['by_class_format']),57600)
  combined=Q.EVENTS.combine({'0':{'report':r},'1':{'report':r}});self.assertEqual(sum(x['device_ns'] for x in combined),115200)
  for row in r['by_label']:self.assertEqual(row['weights'],m[row['label']]['weights'])
 def test_sample_duplicate_and_missing_refusals(self):
  import copy
  m=Q.EVENTS.mapping();rows=self.rows()
  for key,value in [('position',9),('speculative',True),('label','blk.0.gdn.qkv')]:
   bad=copy.deepcopy(rows);bad[0][key]=value
   with self.subTest(key=key),self.assertRaises(ValueError):Q.EVENTS.aggregate(bad,0,87,m)
  with self.assertRaisesRegex(ValueError,'duplicate'):Q.EVENTS.aggregate(rows+[rows[0]],0,87,m)
  with self.assertRaisesRegex(ValueError,'missing expert'):Q.EVENTS.aggregate(rows[1:],0,87,m)
if __name__=='__main__':unittest.main(verbosity=2)
