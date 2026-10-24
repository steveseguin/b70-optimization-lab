import copy,importlib.util,unittest
from pathlib import Path
p=Path(__file__).with_name('audit.py');s=importlib.util.spec_from_file_location('closed_audit',p);A=importlib.util.module_from_spec(s);s.loader.exec_module(A)
class Tests(unittest.TestCase):
 def result(self,tokens=(7,8)):
  return dict(tokens=list(tokens),timing_rows=[dict(generated_index=i+1,token_id=t,completed_monotonic=10+i*.1) for i,t in enumerate(tokens)],decode_intervals=len(tokens)-1,decode_numerator=len(tokens)-1,decode_wall_ms=(len(tokens)-1)*100,prompt_wall_ms=5)
 def test_full_and_short_eos_timing(self):
  self.assertAlmostEqual(A.timing(self.result(),2)['decode_tok_s'],10)
  self.assertEqual(A.timing(self.result((248046,)),128)['decode_tok_s'],None)
  self.assertEqual(A.timing(self.result((7,248046)),128)['termination'],'eos')
  with self.assertRaisesRegex(ValueError,'short'):A.timing(self.result(),128)
 def test_nonfinite_or_wrong_time_refused(self):
  for change in ('nan','order','elapsed'):
   r=self.result()
   if change=='nan':r['timing_rows'][0]['completed_monotonic']=float('nan')
   elif change=='order':r['timing_rows'][1]['completed_monotonic']=9
   else:r['decode_wall_ms']=250
   with self.assertRaises(ValueError):A.timing(r,2)
 def test_consumed_prompt_and_pending_output(self):
  r=self.result();r['rank_trace']=[]
  for rank in (0,1):
   for i,t in enumerate([2,3,7]):
    r['rank_trace'] += [dict(rank=rank,op=1,position=i,token=t,rank_received=i*2),dict(rank=rank,op=2,position=0,token=0,rank_received=i*2+1)]
  self.assertEqual(A.confirmed_inputs(r,[2,3]),3)
  r['rank_trace'][0]['token']=99
  with self.assertRaisesRegex(ValueError,'rank0'):A.confirmed_inputs(r,[2,3])
 def test_eos_cancelled_proposal_is_not_counted_as_resolved(self):
  r=self.result((7,248046));r.update(stats=dict(guesses=2,hits=1,misses=0),guess_rows=[dict(position=2,guess=7,actual=7,hit=True)])
  self.assertEqual(A.guess_outcomes(r,[2,3],128),1)
  r['stats']['guesses']=3
  with self.assertRaisesRegex(ValueError,'unresolved'):A.guess_outcomes(r,[2,3],128)
 def test_weighted_aggregate_and_ordergroups(self):
  def arm(mode,n,ms):return dict(mode=mode,timing=dict(output_tokens=n+1,decode_intervals=n,decode_wall_ms=ms,decode_tok_s=n*1000/ms if n else None,prompt_wall_ms=1),stats=dict(guesses=0,hits=0,misses=0))
  pairs=[dict(order=['none','mtp'],arms=[arm('none',1,100),arm('mtp',1,50)]),dict(order=['mtp','none'],arms=[arm('mtp',9,900),arm('none',9,900)])]
  g=A.aggregate(pairs);self.assertAlmostEqual(g['all']['arms']['mtp']['interval_weighted_tok_s'],10000/950)
  self.assertEqual(g['none']['arms']['none']['prompts'],1)
  self.assertEqual(g['mtp']['arms']['mtp']['prompts'],1)
  A.compare_summary(g,copy.deepcopy(g));bad=copy.deepcopy(g);bad['all']['arms']['none']['decode_intervals']=11
  with self.assertRaises(ValueError):A.compare_summary(g,bad)
if __name__=='__main__':unittest.main(verbosity=2)
